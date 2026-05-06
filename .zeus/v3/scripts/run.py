#!/usr/bin/env python3
"""
ZeusOpen v3 CLI entrypoint.

One-shot execution:
  1. Import task.json into the database state store
  2. Start the worker pool
  3. Run the scheduler loop until all tasks are done
  4. Print a summary report

Usage:
  python run.py --project-root . --max-workers 3
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from api.bus import EventBus
from api.server import create_app
from config import ZeusConfig
from core.scheduler import ZeusScheduler
from core.tracing import init_tracing
from core.worker_pool import WorkerPool
from db.engine import make_async_engine
from db.models import Base
from dispatcher.cli import build_dispatcher
from importer import import_tasks_from_json
from store.sqlite_store import SQLiteStateStore
from task_queue.memory_queue import MemoryTaskQueue
from task_queue.sqlite_queue import SqliteTaskQueue
from workspace import build_workspace_manager


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ZeusOpen v3 Runner")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--version", default="v3", help="Zeus version folder")
    parser.add_argument("--max-workers", type=int, default=3, help="Max concurrent workers")
    parser.add_argument("--database-url", default=None, help="SQLAlchemy async DB URL")
    parser.add_argument("--queue-backend", default="memory", choices=["memory", "sqlite", "redis"], help="Task queue backend")
    parser.add_argument("--redis-url", default=None, help="Redis URL (required if queue-backend=redis)")
    parser.add_argument("--dispatcher", default=None, choices=["mock", "kimi", "claude", "auto"], help="Override dispatcher mode")
    parser.add_argument("--import-only", action="store_true", help="Only import task.json into DB and exit")
    parser.add_argument("--export-plan", action="store_true", help="Export current DB plan to task.json and exit")
    parser.add_argument("--mode", default="combined", choices=["combined", "scheduler", "worker", "serve"], help="Execution mode")
    parser.add_argument("--host", default="0.0.0.0", help="API server host")
    parser.add_argument("--port", type=int, default=8234, help="API server port")
    parser.add_argument("--trace", action="store_true", help="Enable OpenTelemetry console trace output")
    parser.add_argument("--embedded-scheduler", action="store_true", default=True, help="Start embedded scheduler+workers in serve mode (default: True)")
    parser.add_argument("--no-embedded-scheduler", action="store_true", default=False, help="Disable embedded scheduler in serve mode")
    parser.add_argument("--status", action="store_true", help="Print human-readable project status and exit")
    parser.add_argument("--wave", type=int, default=None, help="Only enqueue tasks in the specified wave")
    parser.add_argument("--init", action="store_true", help="Initialize project directory with minimal Zeus v3 files and exit")
    parser.add_argument("--dispatch", type=str, default=None, metavar="TASK_ID", help="Prepare a task for manual sub-agent execution (create workspace + mark running)")
    parser.add_argument("--finalize", type=str, default=None, metavar="TASK_ID", help="Collect results after manual sub-agent execution (scan workspace + generate ai-log)")
    parser.add_argument("--dispatch-list", action="store_true", help="List pending tasks whose dependencies are all satisfied")
    parser.add_argument("--wave-advance", type=int, default=None, const=0, nargs="?", metavar="WAVE", help="Advance current_wave to the next wave with work, or to a specific wave number")
    parser.add_argument("--worker-id", type=str, default=None, help="Override worker ID for dispatch/finalize (default: 'zeus-dispatch')")
    return parser.parse_args(argv)


async def _print_status(store: SQLiteStateStore) -> None:
    """Print human-readable project status from the DB."""
    tasks = await store.list_tasks()
    total = len(tasks)
    passed = sum(1 for t in tasks if t.get("passes"))
    pending = total - passed
    running = sum(1 for t in tasks if t.get("status") == "running")
    failed = sum(1 for t in tasks if t.get("status") == "failed")
    quarantined = len(await store.list_quarantine())

    # Read project meta from DB (fallback to defaults)
    project_name = await store.get_meta("project_name", "ZeusOpen Project")
    north_star = await store.get_meta("north_star", "N/A")
    current_wave = await store.get_meta("current_wave", 1)

    print("\nZeusOpen v3 Status")
    print(f"Project    : {project_name}")
    print(f"North Star : {north_star}")
    print(f"Current Wave: {current_wave}")
    print(f"Tasks      : {passed}/{total} completed ({pending} pending, {running} running, {failed} failed)")
    print(f"Quarantined: {quarantined}")

    recent = [t for t in tasks if t.get("passes")][-5:]
    if recent:
        print("\nRecent completed:")
        for t in recent:
            sha = t.get("commit_sha", "N/A")
            sha_short = sha[:7] if sha else "N/A"
            print(f"  [OK] {t['id']}: {t.get('title', '')} -> {sha_short}")

    wave_pending = [t for t in tasks if not t.get("passes", False) and t.get("wave") == current_wave]
    print(f"\nPending in current wave ({current_wave}): {len(wave_pending)}")
    for t in wave_pending[:5]:
        print(f"  [WAIT] {t['id']}: {t.get('title', '')}")
    print()


async def ensure_schema(database_url: str) -> None:
    engine = make_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root).resolve()
    version = args.version

    # --init: bootstrap minimal project structure and exit
    if args.init:
        from init_project import init_project
        framework_root = Path(__file__).resolve().parent.parent.parent.parent
        created = init_project(project_root, framework_root, force=False)
        # Ensure state.db schema is created so the project is fully bootstrapped
        database_url = args.database_url or f"sqlite+aiosqlite:///{project_root / '.zeus' / version / 'state.db'}"
        await ensure_schema(database_url)
        created.append(str(project_root / ".zeus" / version / "state.db"))
        print(f"[INIT] Project initialized at {project_root}")
        for c in created:
            print(f"  + {c}")
        print(f"\nTo start: cd {project_root} && .zeus/v3/start.ps1 --mode serve")
        return 0

    task_json_path = project_root / ".zeus" / version / "task.json"
    if not task_json_path.exists():
        # Auto-detect project root when run.py is executed from .zeus/<version>/scripts/
        run_py = Path(__file__).resolve()
        if run_py.name == "run.py" and run_py.parent.name == "scripts":
            candidate = run_py.parent.parent.parent.parent
            candidate_task_json = candidate / ".zeus" / version / "task.json"
            if candidate_task_json.exists():
                project_root = candidate
                task_json_path = candidate_task_json

    # Warn if run from unexpected cwd without explicit --project-root
    explicit_project_root = any(arg.startswith("--project-root") for arg in (argv or sys.argv[1:]))
    if not explicit_project_root:
        auto_root = Path(__file__).resolve().parent.parent.parent.parent
        if Path.cwd().resolve() != auto_root.resolve():
            print(f"[WARN] Current working directory is {Path.cwd()}")
            print(f"[WARN] Detected project root is {auto_root}")
            print(f"[INFO] To avoid loading the wrong project, cd into the project root or use --project-root")

    database_url = args.database_url or f"sqlite+aiosqlite:///{project_root / '.zeus' / version / 'state.db'}"
    tracer = init_tracing(export_to_console=args.trace)
    print(">> ZeusOpen v3 Runner")
    print(f"   Project : {project_root}")
    print(f"   Version : {version}")
    print(f"   DB      : {database_url}")
    print(f"   Workers : {args.max_workers}")
    print(f"   Queue   : {args.queue_backend}")

    # 1. Ensure schema
    await ensure_schema(database_url)

    # 2. Create store
    store = SQLiteStateStore(database_url)

    # 2a. Dispatch / finalize / dispatch-list / wave-advance — no import needed
    if args.dispatch or args.finalize or args.dispatch_list or args.wave_advance is not None:
        from workspace import build_workspace_manager
        worker_id = args.worker_id or "zeus-dispatch"

        if args.dispatch_list:
            from core.dispatch import list_dispatachable
            ready = await list_dispatachable(store)
            if not ready:
                print("[DISPATCH-LIST] No ready tasks (no pending tasks with satisfied dependencies)")
            else:
                print(f"[DISPATCH-LIST] {len(ready)} task(s) ready for dispatch:")
                for t in ready:
                    deps = ", ".join(t.get("depends_on") or []) or "none"
                    print(f"  {t['id']:10s}  wave={t.get('wave', '?')}  deps=[{deps}]  {t.get('title', '')}")
            await store.close()
            return 0

        if args.dispatch or args.finalize:
            ws_manager = build_workspace_manager(project_root, version)

        if args.dispatch:
            from core.dispatch import dispatch_task
            result = await dispatch_task(args.dispatch, store, worker_id, ws_manager)
            if not result["ok"]:
                print(f"[DISPATCH] Failed: {result['error']}")
                await store.close()
                return 1
            t = result["task"]
            print(f"[DISPATCH] {args.dispatch} ready for sub-agent execution")
            print(f"   Title    : {t.get('title', '')}")
            print(f"   Wave     : {t.get('wave', '?')}")
            print(f"   Files    : {', '.join(t.get('files') or []) or 'N/A'}")
            print(f"   Depends  : {', '.join(t.get('depends_on') or []) or 'none'}")
            print(f"   Workspace: {result['workspace']}")
            print(f"   PROMPT   : {result['prompt']}")
            print()
            print("─" * 50)
            print("Copy the following to your sub-agent:")
            print("─" * 50)
            print(result.get("agent_instruction", ""))
            print("─" * 50)
            print(f"After sub-agent completes, run: --finalize {args.dispatch}")
            await store.close()
            return 0

        if args.finalize:
            from core.dispatch import finalize_task
            result = await finalize_task(args.finalize, store, worker_id, ws_manager)
            if not result["ok"]:
                print(f"[FINALIZE] Failed: {result['error']}")
                await store.close()
                return 1
            print(f"[FINALIZE] {args.finalize} → {result['status']}")
            if result["changed_files"]:
                print(f"   Changed: {', '.join(result['changed_files'][:10])}")
                if len(result["changed_files"]) > 10:
                    print(f"   ... and {len(result['changed_files']) - 10} more")
            print(f"   Zeus-result: {'found' if result['has_zeus_result'] else 'not found (file diff fallback)'}")
            print(f"   AI Log: {result['ai_log_ref'] or 'N/A'}")
            if result.get("advanced_to_wave"):
                print(f"   Wave advanced to: {result['advanced_to_wave']}")
            await store.close()
            return 0

        if args.wave_advance is not None:
            from core.dispatch import advance_wave
            target = args.wave_advance if args.wave_advance > 0 else None
            result2 = await advance_wave(store, target_wave=target)
            if not result2["ok"]:
                print(f"[WAVE-ADVANCE] {result2['error']}")
            else:
                print(f"[WAVE-ADVANCE] current_wave: {result2['from']} → {result2['to']}")
            await store.close()
            return 0

    # 2b. Import tasks (skip auto-import in serve mode to preserve runtime state)

    if args.status:
        await _print_status(store)
        await store.close()
        return 0

    if args.export_plan:
        from exporter import export_plan_to_file
        result = await export_plan_to_file(store, task_json_path, include_runtime=True)
        await store.close()
        print(f"[EXPORT] {result['task_count']} tasks, {result['phase_count']} phases, {result['milestone_count']} milestones")
        print(f"         written to {result['output_path']}")
        return 0

    # Import tasks from task.json if it exists (cold-start or explicit request)
    existing_tasks = await store.list_tasks()
    if task_json_path.exists():
        if args.mode == "serve" and not existing_tasks:
            import_result = await import_tasks_from_json(store, task_json_path)
            print(f"[SERVE] Cold-start auto-import: {import_result['imported_tasks']} tasks imported")
        elif args.mode != "serve":
            import_result = await import_tasks_from_json(store, task_json_path)
            print(f"[IMPORT] Imported {import_result['imported_tasks']} tasks, "
                  f"{import_result['quarantine_count']} quarantined, "
                  f"meta keys: {import_result['meta_keys']}")

            if args.import_only:
                await store.close()
                print("[OK] Import complete.")
                return 0
        else:
            import_result = {"imported_tasks": 0, "quarantine_count": 0, "meta_keys": []}
    else:
        if not existing_tasks and args.mode != "serve":
            print("[WARN] No task.json found and DB is empty. Nothing to run.")
            await store.close()
            return 0
        import_result = {"imported_tasks": 0, "quarantine_count": 0, "meta_keys": []}

    # 3. API server mode
    if args.mode == "serve":
        from api.control_plane import ControlPlane
        bus = EventBus()
        control_plane = ControlPlane(store, bus, project_root, database_url)
        embedded = None
        if args.embedded_scheduler and not args.no_embedded_scheduler:
            config_obj = ZeusConfig(project_root, version)
            embedded = {
                "project_root": str(project_root),
                "version": version,
                "max_workers": args.max_workers,
                "queue_backend": args.queue_backend,
                "redis_url": args.redis_url,
                "config": config_obj.raw(),
            }
            print(f"[SERVE] Embedded scheduler enabled with {args.max_workers} workers")
        app = create_app(store, bus, control_plane, embedded, project_root=project_root)

        # Pre-flight port check: fail fast instead of letting uvicorn hang
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((args.host, args.port))
            except OSError:
                print(f"[FATAL] Port {args.port} already in use on {args.host}.")
                print(f"        Find the process: netstat -ano | findstr :{args.port}")
                print(f"        Or use --port to pick a different port.")
                await store.close()
                return 1

        import uvicorn
        print(f"[SERVE] Starting API server at http://{args.host}:{args.port}")
        config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info", timeout_graceful_shutdown=1)
        server = uvicorn.Server(config)
        await server.serve()
        return 0

    # 4. Runner mode: prepare queue, dispatcher, workspace manager
    config = ZeusConfig(project_root, version)

    if args.queue_backend == "sqlite":
        queue = SqliteTaskQueue(str(project_root / ".zeus" / version / "queue.sqlite"), max_retries=config.queue_retry_max)
    elif args.queue_backend == "redis":
        redis_url = args.redis_url or config.raw().get("queue", {}).get("redis_url", "redis://localhost:6379/0")
        from task_queue.redis_queue import RedisTaskQueue
        queue = RedisTaskQueue(redis_url)
    else:
        queue = MemoryTaskQueue(max_retries=config.queue_retry_max)

    dispatcher_cfg = config.raw()
    if args.dispatcher:
        dispatcher_cfg.setdefault("subagent", {})["dispatcher"] = args.dispatcher
    dispatcher = build_dispatcher(dispatcher_cfg)

    bus = EventBus()
    workspace_manager = build_workspace_manager(project_root, version)
    scheduler = ZeusScheduler(store, queue, bus)
    pool = WorkerPool(store, queue, dispatcher, workspace_manager, max_workers=args.max_workers, bus=bus)

    # 5. Start workers and/or scheduling loop based on mode
    ticks = 0
    idle_count = 0
    max_idle_ticks = config.worker_max_idle_ticks
    scheduler_tick_interval = config.scheduler_tick_interval
    worker_heartbeat_interval = config.worker_heartbeat_interval
    enqueued_ids: set[str] = set()

    if args.mode in ("combined", "worker"):
        await pool.start()
        print(">> Workers started")

    if args.mode == "worker":
        await store.set_meta("worker_actual_count", len(pool._workers))
        print(">> Worker watch mode started")
        try:
            while True:
                target = await store.get_meta("worker_target_count", args.max_workers)
                if target != len(pool._workers):
                    await pool.scale_to(target)
                    await store.set_meta("worker_actual_count", len(pool._workers))
                    print(f"   Workers scaled to {len(pool._workers)}")
                if target == 0:
                    print("[Workers] target count is 0, exiting")
                    break
                qsize = await queue.size()
                pending = len(await store.list_tasks(status="pending"))
                running = len(await store.list_tasks(status="running"))
                if qsize == 0 and pending == 0 and running == 0:
                    print("[Workers] no more work, exiting")
                    break
                await asyncio.sleep(worker_heartbeat_interval)
        except KeyboardInterrupt:
            print("\n[STOP] Interrupted by user")
        finally:
            await pool.stop()
            await store.set_meta("worker_actual_count", 0)

    if args.mode in ("combined", "scheduler"):
        if args.mode == "scheduler":
            print(">> Scheduler watch mode started")
            await store.set_meta("scheduler_actual_state", "idle")
            import os
            await store.set_meta("scheduler_pid", os.getpid())
            await store.set_meta("scheduler_active", False)
            with tracer.start_as_current_span("scheduler-watch") as span:
                span.set_attribute("max_workers", args.max_workers)
                span.set_attribute("database_url", database_url)
                span.set_attribute("mode", args.mode)
                if args.wave is not None:
                    span.set_attribute("wave_filter", args.wave)
                    print(f"   Wave filter: {args.wave}")
                try:
                    while True:
                        target = await store.get_meta("scheduler_target_state", "stopped")
                        if target != "running":
                            await store.set_meta("scheduler_actual_state", "stopped")
                            await store.set_meta("scheduler_active", False)
                            print("[Scheduler] target state is not running, exiting")
                            break
                        await store.set_meta("scheduler_actual_state", "running")
                        await store.set_meta("scheduler_active", True)
                        with tracer.start_as_current_span("scheduler-tick") as tick_span:
                            ready = await scheduler.tick(enqueued_ids, wave_filter=args.wave)
                            ticks += 1
                            tick_span.set_attribute("tick", ticks)
                            tick_span.set_attribute("enqueued_count", len(ready))
                            if ready:
                                idle_count = 0
                                print(f"   Tick {ticks}: enqueued {len(ready)} task(s) — {', '.join(t['id'] for t in ready)}")
                            else:
                                idle_count += 1
                                qsize = await queue.size()
                                if qsize == 0 and idle_count >= max_idle_ticks:
                                    pending = len(await store.list_tasks(status="pending"))
                                    running = len(await store.list_tasks(status="running"))
                                    tick_span.set_attribute("pending", pending)
                                    tick_span.set_attribute("running", running)
                                    if pending == 0 and running == 0:
                                        await scheduler.mark_global_completed()
                                        print("[Scheduler] all tasks complete, exiting")
                                        break
                                await asyncio.sleep(scheduler_tick_interval)
                except KeyboardInterrupt:
                    print("\n[STOP] Interrupted by user")
                finally:
                    await store.set_meta("scheduler_actual_state", "stopped")
                    await store.set_meta("scheduler_active", False)
        else:
            # combined mode: old inline behavior
            print(">> Scheduler started")
            if args.wave is not None:
                print(f"   Wave filter: {args.wave}")
            with tracer.start_as_current_span("scheduler-run") as span:
                span.set_attribute("max_workers", args.max_workers)
                span.set_attribute("database_url", database_url)
                span.set_attribute("mode", args.mode)
                if args.wave is not None:
                    span.set_attribute("wave_filter", args.wave)
                try:
                    while True:
                        with tracer.start_as_current_span("scheduler-tick") as tick_span:
                            ready = await scheduler.tick(enqueued_ids, wave_filter=args.wave)
                            ticks += 1
                            tick_span.set_attribute("tick", ticks)
                            tick_span.set_attribute("enqueued_count", len(ready))
                            if ready:
                                idle_count = 0
                                print(f"   Tick {ticks}: enqueued {len(ready)} task(s) — {', '.join(t['id'] for t in ready)}")
                            else:
                                idle_count += 1
                                qsize = await queue.size()
                                if qsize == 0 and idle_count >= max_idle_ticks:
                                    pending = len(await store.list_tasks(status="pending"))
                                    running = len(await store.list_tasks(status="running"))
                                    tick_span.set_attribute("pending", pending)
                                    tick_span.set_attribute("running", running)
                                    if pending == 0 and running == 0:
                                        break
                                await asyncio.sleep(0.2)
                except KeyboardInterrupt:
                    print("\n[STOP] Interrupted by user")

    if args.mode == "combined":
        await pool.stop()
        await scheduler.mark_global_completed()

    if args.mode == "scheduler":
        await scheduler.mark_global_completed()

    await store.close()
    await queue.close()

    # 6. Report
    if args.mode in ("combined", "scheduler"):
        print("\n[DONE] Run complete")
        print(f"   Total ticks : {ticks}")
        print(f"   Enqueued    : {len(enqueued_ids)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n[STOP] Aborted")
        sys.exit(130)
