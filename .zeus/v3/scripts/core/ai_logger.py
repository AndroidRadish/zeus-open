"""
ZeusOpen v3 AI log generator.

Auto-generates structured ai-log markdown files from workspace artifacts
after a task execution completes. Called by the worker as a post-task hook.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from store.base import AsyncStateStore


async def generate_ai_log(
    task: dict[str, Any],
    workspace: Path | None,
    store: AsyncStateStore,
    worker_id: str,
    validated: Any = None,
    error: str | None = None,
    project_root: Path | None = None,
) -> str | None:
    """Collect execution artifacts and write an ai-log markdown file.

    Returns the relative path of the written log (for ai_log_ref),
    or None if writing failed.
    """
    task_id = task["id"]
    title = task.get("title", task_id)
    status = validated.status if validated else ("failed" if error else "unknown")

    # 1. Read zeus-result.json from workspace
    changed_files: list[str] = []
    test_summary: dict[str, Any] = {}
    result_artifacts: dict[str, Any] = {}
    commit_sha: str | None = None
    if validated:
        changed_files = getattr(validated, "changed_files", []) or []
        ts = getattr(validated, "test_summary", None)
        if ts:
            try:
                test_summary = ts.model_dump() if hasattr(ts, "model_dump") else dict(ts)
            except Exception:
                test_summary = {}
        result_artifacts = getattr(validated, "artifacts", {}) or {}
        commit_sha = getattr(validated, "commit_sha", None)

    # 2. Read stdout.txt from workspace
    stdout_lines: list[str] = []
    if workspace:
        stdout_path = workspace / f"{task_id}-stdout.txt"
        if stdout_path.exists():
            try:
                raw = stdout_path.read_text("utf-8", errors="replace")
                stdout_lines = raw.splitlines()
            except Exception:
                pass

    # 3. Read progress.jsonl from workspace
    progress_steps: list[dict[str, Any]] = []
    if workspace:
        progress_path = workspace / "progress.jsonl"
        if progress_path.exists():
            try:
                for line in progress_path.read_text("utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line:
                        try:
                            progress_steps.append(json.loads(line))
                        except json.JSONDecodeError:
                            progress_steps.append({"raw": line})
            except Exception:
                pass

    # 4. Query EventLog for this task
    events = await store.query_events(task_id=task_id, limit=200)
    events.reverse()

    # 5. Determine the project's ai-logs directory
    if project_root is None:
        if workspace:
            project_root = workspace.parent.parent.parent.parent
        else:
            project_root = Path.cwd()
    ai_logs_dir = project_root / ".zeus" / "v3" / "ai-logs"
    ai_logs_dir.mkdir(parents=True, exist_ok=True)

    # 6. Compose markdown
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = [
        f"# AI Log: {task_id} — {title}",
        "",
        f"- **Task**: {task_id}",
        f"- **Title**: {title}",
        f"- **Status**: {status}",
        f"- **Worker**: {worker_id}",
        f"- **Timestamp**: {now}",
        "",
    ]

    if commit_sha:
        lines.append(f"- **Commit**: {commit_sha}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Execution Summary")
    lines.append("")

    if error:
        lines.append(f"**Error**: {error}")
        lines.append("")

    if changed_files:
        lines.append(f"**Changed Files**: {', '.join(changed_files)}")
        lines.append("")

    if test_summary:
        lines.append(f"**Test Summary**: {json.dumps(test_summary, ensure_ascii=False)}")
        lines.append("")

    if result_artifacts:
        lines.append("**Artifacts**:")
        for k, v in result_artifacts.items():
            lines.append(f"  - {k}: {v}")
        lines.append("")

    # Progress steps
    lines.append("---")
    lines.append("")
    lines.append("## Progress Steps")
    lines.append("")
    if progress_steps:
        for ps in progress_steps:
            ts = ps.get("ts", "")
            step = ps.get("step", "")
            msg = ps.get("message", "")
            lines.append(f"- **{ts}** — *{step}*: {msg}" if ts and step else f"- {json.dumps(ps, ensure_ascii=False)}")
        lines.append("")
    else:
        lines.append("*(no progress steps recorded)*")
        lines.append("")

    # Raw stdout (truncated to last 200 lines)
    lines.append("---")
    lines.append("")
    lines.append("## Agent Output")
    lines.append("")
    if stdout_lines:
        MAX_STDOUT = 200
        if len(stdout_lines) > MAX_STDOUT:
            lines.append(f"*(showing last {MAX_STDOUT} of {len(stdout_lines)} lines)*")
            lines.append("")
            stdout_lines = stdout_lines[-MAX_STDOUT:]
        lines.append("```text")
        lines.extend(stdout_lines)
        lines.append("```")
    else:
        lines.append("*(no stdout captured)*")
    lines.append("")

    # Event timeline
    lines.append("---")
    lines.append("")
    lines.append("## Event Timeline")
    lines.append("")
    if events:
        for ev in events:
            et = ev.get("event_type", "?")
            ts = ev.get("ts", "")
            payload = ev.get("payload", {})
            payload_str = ""
            if payload:
                try:
                    payload_str = json.dumps(payload, ensure_ascii=False)
                except Exception:
                    payload_str = str(payload)
            lines.append(f"- **{ts}** — `{et}` {payload_str}")
    else:
        lines.append("*(no events recorded)*")
    lines.append("")

    # Decision Rationale (placeholder since we can't know the agent's reasoning)
    lines.append("---")
    lines.append("")
    lines.append("## Decision Rationale")
    lines.append("")
    lines.append("*(auto-generated from execution artifacts)*")
    lines.append("")

    content = "\n".join(lines)

    # 7. Write the file
    log_filename = f"{task_id}.md"
    log_path = ai_logs_dir / log_filename
    try:
        log_path.write_text(content, encoding="utf-8")
    except OSError:
        return None

    return str(log_path.relative_to(project_root))
