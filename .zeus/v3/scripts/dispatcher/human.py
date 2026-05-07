"""
Human dispatcher — leaves the task in "running" state for manual execution.

Writes a HUMAN.md marker and a pending zeus-result.json so the worker
does not mark the task as completed or failed. The user then runs
--finalize when done.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dispatcher.base import SubagentDispatcher


class HumanSubagentDispatcher(SubagentDispatcher):
    """Marks a task for manual execution instead of running it automatically."""

    async def run(self, task: dict[str, Any], workspace: Path, prompt: str, bus=None) -> dict[str, Any]:
        tid = task["id"]
        title = task.get("title", tid)

        marker = workspace / "HUMAN.md"
        marker.write_text(
            f"# Manual Execution Required: {tid}\n\n"
            f"**Task**: {tid} — {title}\n"
            f"**Workspace**: {workspace}\n"
            f"**Prompt**: {workspace / 'PROMPT.md'}\n\n"
            "The dispatcher is in 'human' mode, so this task was not executed automatically.\n"
            "After completing the work manually:\n"
            "1. Write zeus-result.json in this workspace\n"
            '2. Run: --finalize ' + tid + '\n',
            encoding="utf-8",
        )

        result = {
            "status": "pending",
            "changed_files": [],
            "test_summary": {"passed": 0, "failed": 0, "skipped": 0},
            "commit_sha": None,
            "artifacts": {
                "mode": "human",
                "message": f"Manual execution required. See HUMAN.md in workspace.",
            },
        }
        (workspace / "zeus-result.json").write_text(
            __import__("json").dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result
