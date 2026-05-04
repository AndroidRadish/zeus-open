"""
ZeusOpen v3 dispatch — manual sub-agent execution support.

Bridges the gap between opencode-launched Task agents and the zeus
execution pipeline: --dispatch creates a workspace + worker_run,
--finalize collects results and generates ai-log.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.ai_logger import generate_ai_log
from schemas.zeus_result import ZeusResult
from store.base import AsyncStateStore
from workspace.base import BaseWorkspaceManager


async def dispatch_task(
    task_id: str,
    store: AsyncStateStore,
    worker_id: str,
    workspace_manager: BaseWorkspaceManager,
) -> dict[str, Any]:
    """Prepare a task for manual sub-agent execution.

    Verifies dependencies, creates workspace, registers worker_run,
    marks task as running. Returns task info for the caller.
    """
    task = await store.get_task(task_id)
    if not task:
        return {"ok": False, "error": f"Task {task_id} not found"}

    if task["status"] != "pending":
        return {"ok": False, "error": f"Task {task_id} is {task['status']}, not pending"}

    # Check dependencies
    deps = task.get("depends_on") or []
    if deps:
        for dep_id in deps:
            dep = await store.get_task(dep_id)
            if not dep or dep.get("status") != "completed":
                return {"ok": False, "error": f"Dependency {dep_id} not completed"}

    # Create workspace
    try:
        workspace = await workspace_manager.prepare(task)
    except Exception as exc:
        return {"ok": False, "error": f"Workspace prepare failed: {exc}"}

    workspace_path = str(workspace)
    prompt_path = str(workspace_manager.prompt_path(task_id))

    # Register worker run
    run_id = await store.create_worker_run(worker_id, task_id, workspace=workspace_path)
    await store.update_task_status(task_id, "running", worker_id=worker_id)
    await store.log_event(
        event_type="task.dispatched",
        task_id=task_id,
        agent_id=worker_id,
        wave=task.get("wave"),
        payload={"workspace": workspace_path},
    )

    # Build copy-paste instruction for the sub-agent
    files = task.get("files") or []
    files_str = ", ".join(files) if files else "N/A"
    deps = task.get("depends_on") or []
    deps_str = ", ".join(deps) if deps else "none"
    agent_instruction = (
        f"## Task: {task_id} — {task.get('title', '')}\n\n"
        f"{task.get('description', '')}\n\n"
        f"**Files**: {files_str}\n"
        f"**Depends**: {deps_str}\n"
        f"**Wave**: {task.get('wave', '?')}\n\n"
        f"### Execution Steps\n\n"
        f"1. Read the involved files and understand the codebase.\n"
        f"2. Implement the changes described above.\n"
        f"3. **After each significant step**, append a progress line to progress.jsonl in the workspace root:\n"
        f'   `{{"ts": "<ISO timestamp>", "step": "<planning|reading|writing|testing|completed>", "message": "<what you did>"}}`\n'
        f"4. Run relevant tests or build to verify.\n"
        f"5. **When done**, write zeus-result.json in the workspace root:\n"
        f'   `{{"status": "completed", "changed_files": ["path/to/file1", "path/to/file2"], "test_summary": {{"passed": N, "failed": 0, "skipped": 0}}, "commit_sha": "abc1234", "artifacts": {{}}}}`\n"
        f"6. All done — the orchestrator will pick up the result.\n\n"
        f"### Workspace\n"
        f"{workspace_path}\n"
    )

    return {
        "ok": True,
        "task": task,
        "workspace": workspace_path,
        "prompt": prompt_path,
        "run_id": run_id,
        "agent_instruction": agent_instruction,
    }


async def finalize_task(
    task_id: str,
    store: AsyncStateStore,
    worker_id: str,
    workspace_manager: BaseWorkspaceManager,
) -> dict[str, Any]:
    """Collect results after a manually dispatched task completes.

    Scans workspace for zeus-result.json (primary) or file changes (fallback),
    generates ai-log, marks task completed/failed.
    """
    task = await store.get_task(task_id)
    if not task:
        return {"ok": False, "error": f"Task {task_id} not found"}

    if task["status"] != "running":
        return {"ok": False, "error": f"Task {task_id} is {task['status']}, not running"}

    # Find workspace from worker_runs
    runs = await store.list_worker_runs(task_id=task_id, limit=1)
    workspace_path = runs[0].get("workspace") if runs else task.get("extra", {}).get("workspace")
    workspace = Path(workspace_path) if workspace_path else None

    # Try to read zeus-result.json
    result_path = workspace / "zeus-result.json" if workspace else None
    zeus_result = None
    if result_path and result_path.exists():
        try:
            data = json.loads(result_path.read_text("utf-8"))
            zeus_result = ZeusResult.model_validate(data)
        except Exception:
            pass

    # If no zeus-result, scan workspace for git changes as fallback
    changed_files: list[str] = []
    if zeus_result is None and workspace:
        try:
            import subprocess
            r = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=ACMR"],
                cwd=str(workspace),
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                changed_files = [f.strip() for f in r.stdout.splitlines() if f.strip()]
        except Exception:
            pass

    # Determine status
    error: str | None = None
    status = "completed"
    passes = True

    if zeus_result:
        if zeus_result.status != "completed":
            status = "failed"
            passes = False
            error = zeus_result.artifacts.get("error", "partial_or_failed")
        else:
            changed_files = zeus_result.changed_files or changed_files
    elif not changed_files:
        # Neither zeus-result nor git changes found — still mark completed
        # but note it as a minimal completion
        pass

    # Close worker run
    run_id = runs[0]["id"] if runs else None
    if run_id is not None:
        summary = f"commit: {zeus_result.commit_sha}"[:200] if zeus_result and zeus_result.commit_sha else status
        await store.finish_worker_run(run_id, status, result_summary=summary)

    # Log event
    await store.log_event(
        event_type=f"task.{status}",
        task_id=task_id,
        agent_id=worker_id,
        wave=task.get("wave"),
        payload={
            "changed_files": changed_files,
            "source": "dispatch-finalize",
        },
    )

    # Update task status
    await store.update_task_status(
        task_id, status,
        passes=passes,
        commit_sha=zeus_result.commit_sha if zeus_result else None,
        worker_id=None,
    )

    # Generate ai-log
    ai_log_ref = await generate_ai_log(
        task, workspace, store, worker_id,
        validated=zeus_result,
        error=error,
        project_root=workspace_manager.project_root,
    )
    if ai_log_ref:
        await store.update_task_status(task_id, status, ai_log_ref=ai_log_ref)

    # Auto-advance current_wave if this task was the last in its wave
    advanced_to = await _advance_wave_if_done(store, task)

    return {
        "ok": True,
        "status": status,
        "changed_files": changed_files,
        "has_zeus_result": zeus_result is not None,
        "ai_log_ref": ai_log_ref,
        "advanced_to_wave": advanced_to,
    }


async def _advance_wave_if_done(
    store: AsyncStateStore,
    completed_task: dict[str, Any],
) -> int | None:
    """If all tasks in the completed task's wave are done, advance current_wave."""
    wave = completed_task.get("wave")
    if wave is None:
        return None

    tasks_in_wave = await store.list_tasks(wave=wave)
    remaining = [t for t in tasks_in_wave if t.get("status") != "completed"]
    if remaining:
        return None  # still have pending/running tasks in this wave

    # All done in this wave — find next wave with pending tasks
    all_tasks = await store.list_tasks()
    waves = sorted(set(t.get("wave") for t in all_tasks if t.get("wave") is not None))
    current = await store.get_meta("current_wave", 1)

    for w in waves:
        if w <= current:
            continue
        wave_tasks = [t for t in all_tasks if t.get("wave") == w]
        pending = [t for t in wave_tasks if t.get("status") == "pending"]
        failed = [t for t in wave_tasks if t.get("status") == "failed"]
        if pending or failed:
            await store.set_meta("current_wave", w)
            return w

    return None


async def advance_wave(
    store: AsyncStateStore,
    target_wave: int | None = None,
) -> dict[str, Any]:
    """Manually advance current_wave to a target wave or the next wave with work."""
    current = await store.get_meta("current_wave", 1)
    all_tasks = await store.list_tasks()

    if target_wave:
        await store.set_meta("current_wave", target_wave)
        return {"ok": True, "from": current, "to": target_wave}

    # Auto-find next wave with pending/failed tasks
    waves = sorted(set(t.get("wave") for t in all_tasks if t.get("wave") is not None))
    for w in waves:
        if w <= current:
            continue
        wave_tasks = [t for t in all_tasks if t.get("wave") == w]
        has_work = any(t.get("status") in ("pending", "failed") for t in wave_tasks)
        if has_work:
            await store.set_meta("current_wave", w)
            return {"ok": True, "from": current, "to": w}

    return {"ok": False, "error": "No next wave with work found", "from": current}


async def list_dispatachable(
    store: AsyncStateStore,
) -> list[dict[str, Any]]:
    """List pending tasks whose dependencies are all completed."""
    tasks = await store.list_tasks(status="pending")
    ready: list[dict[str, Any]] = []
    for t in tasks:
        deps = t.get("depends_on") or []
        blocked = False
        for dep_id in deps:
            dep = await store.get_task(dep_id)
            if not dep or dep.get("status") != "completed":
                blocked = True
                break
        if not blocked:
            ready.append(t)
    return ready
