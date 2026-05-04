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
    lines: list[str] = []

    # -------- Header --------
    badge = "✅" if status == "completed" else "❌"
    lines.append(f"# {task_id} — {title}")
    lines.append("")

    # Metadata table
    lines.append("| | |")
    lines.append("|---|---|")
    lines.append(f"| **Status** | {badge} {status} |")
    lines.append(f"| **Worker** | `{worker_id}` |")
    lines.append(f"| **Timestamp** | `{now}` |")
    if commit_sha:
        lines.append(f"| **Commit** | `{commit_sha}` |")
    passed = test_summary.get("passed", "?")
    failed = test_summary.get("failed", "?")
    skipped = test_summary.get("skipped", "?")
    if test_summary:
        lines.append(f"| **Tests** | {passed} passed / {failed} failed / {skipped} skipped |")
    lines.append(f"| **Files** | {len(changed_files)} changed |")
    if error:
        lines.append(f"| **Error** | {error} |")
    lines.append("")

    # -------- Error callout (if failed) --------
    if error:
        lines.append("> **⚠️ Error**")
        lines.append(">")
        for line_text in error.splitlines():
            lines.append(f"> {line_text}")
        lines.append("")

    # -------- Changed Files --------
    if changed_files:
        lines.append("## 📦 Changed Files")
        lines.append("")
        # Group by extension for visual organization
        for cf in changed_files:
            lines.append(f"- `{cf}`")
        lines.append("")

    # -------- Execution Summary --------
    lines.append("## 📋 Execution Summary")
    lines.append("")
    if test_summary:
        total = passed + failed + skipped
        rate = f"{passed / total * 100:.0f}%" if total > 0 else "N/A"
        lines.append(f"- **Test Results**: {rate} pass rate ({passed}/{total})")
    if result_artifacts:
        lines.append("- **Artifacts**:")
        for k, v in result_artifacts.items():
            lines.append(f"  - `{k}`: {v}")
    if commit_sha:
        lines.append(f"- **Commit**: `{commit_sha}`")
    lines.append("")

    # -------- Progress Steps --------
    if progress_steps:
        lines.append("## 📈 Progress Steps")
        lines.append("")
        lines.append("| Timestamp | Step | Message |")
        lines.append("|---|---|---|")
        for ps in progress_steps:
            ts = ps.get("ts", "")
            step = ps.get("step", "")
            msg = ps.get("message", "")
            lines.append(f"| `{ts}` | `{step}` | {msg} |")
        lines.append("")

    # -------- Agent Output --------
    if stdout_lines:
        lines.append("## 💬 Agent Output")
        lines.append("")
        MAX_STDOUT = 200
        if len(stdout_lines) > MAX_STDOUT:
            lines.append(f"> Showing last {MAX_STDOUT} of {len(stdout_lines)} lines.")
            lines.append("")
            stdout_lines = stdout_lines[-MAX_STDOUT:]
        lines.append("```ansi")
        lines.extend(stdout_lines)
        lines.append("```")
        lines.append("")

    # -------- Event Timeline --------
    lines.append("## 📡 Event Timeline")
    lines.append("")
    if events:
        lines.append("| Time | Event | Details |")
        lines.append("|---|---|---|")
        for ev in events:
            et = ev.get("event_type", "")
            ts = ev.get("ts", "") or ""
            payload = ev.get("payload", {})
            payload_str = ""
            if payload:
                try:
                    payload_str = json.dumps(payload, ensure_ascii=False)
                except Exception:
                    payload_str = str(payload)
            # Truncate long payloads in table
            display = payload_str[:120] + "..." if len(payload_str) > 120 else payload_str
            lines.append(f"| `{ts}` | `{et}` | `{display}` |")
    else:
        lines.append("*(no events recorded)*")
    lines.append("")

    # -------- Raw Event Payloads (expandable) --------
    if events:
        lines.append("<details>")
        lines.append("<summary>Raw Event Payloads</summary>")
        lines.append("")
        lines.append("```json")
        payloads = []
        for ev in events:
            ts = ev.get("ts", "")
            et = ev.get("event_type", "")
            payload = ev.get("payload", {})
            payloads.append({ts: {"event": et, "payload": payload}})
        lines.append(json.dumps(payloads, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # -------- Decision Rationale --------
    lines.append("---")
    lines.append("")
    lines.append("## 🧠 Decision Rationale")
    lines.append("")
    lines.append("*Auto-generated from execution artifacts.*")
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
