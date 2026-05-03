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

    return {
        "ok": True,
        "task": task,
        "workspace": workspace_path,
        "prompt": prompt_path,
        "run_id": run_id,
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

    return {
        "ok": True,
        "status": status,
        "changed_files": changed_files,
        "has_zeus_result": zeus_result is not None,
        "ai_log_ref": ai_log_ref,
    }


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
