"""
JSON-file-backed AsyncStateStore implementation for ZeusOpen v3.

Replaces SQLAlchemy with flat JSON files. Throws nothing away — all the same
data models, just stored as diff-friendly JSON instead of SQLite rows.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from store.base import AsyncStateStore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_from_str(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def _atomic_write(path: Path, data: Any) -> None:
    """Write JSON to a temp file, then atomically rename to the target path."""
    tmp = path.with_suffix(".tmp." + str(os.getpid()))
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )
    tmp.replace(path)


def _json_default(obj: Any) -> str:
    """Convert non-serializable types (e.g. datetime) to ISO string."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _append_jsonl(path: Path, obj: dict[str, Any]) -> int:
    """Append a JSON line to a .jsonl file, return line number (1-indexed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        line = json.dumps(obj, ensure_ascii=False)
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())
    return _count_jsonl(path)


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for _ in f:
            count += 1
    return count


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    result: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    result.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return result


class JsonStateStore(AsyncStateStore):
    """Async state store backed by flat JSON files.

    File layout under project_root /.zeus / version /:
      state.json        — tasks, phases, milestones, quarantine, scheduler_meta
      events.jsonl      — append-only event log
      worker_runs.jsonl — append-only worker run history
      mailbox.jsonl     — append-only agent messages
      plan_history.jsonl — append-only plan mutations
    """

    def __init__(self, project_root: Path, version: str = "v3") -> None:
        self._root = Path(project_root)
        self._version = version
        self._dir = self._root / ".zeus" / version
        self._dir.mkdir(parents=True, exist_ok=True)

        self._state_path = self._dir / "state.json"
        self._events_path = self._dir / "events.jsonl"
        self._runs_path = self._dir / "worker_runs.jsonl"
        self._mailbox_path = self._dir / "mailbox.jsonl"
        self._plan_history_path = self._dir / "plan_history.jsonl"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_state(self) -> dict[str, Any]:
        if not self._state_path.exists():
            return {"tasks": {}, "phases": {}, "milestones": {},
                    "quarantine": {}, "meta": {}, "next_run_id": 1}
        try:
            return json.loads(self._state_path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"tasks": {}, "phases": {}, "milestones": {},
                    "quarantine": {}, "meta": {}, "next_run_id": 1}

    def _save_state(self, state: dict[str, Any]) -> None:
        _atomic_write(self._state_path, state)

    def _tasks_dict(self) -> dict[str, dict[str, Any]]:
        return self._load_state()["tasks"]

    def _tasks_save(self, tasks: dict[str, dict[str, Any]]) -> None:
        state = self._load_state()
        state["tasks"] = tasks
        self._save_state(state)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        return {"type": "json", "ok": True, "state_file": str(self._state_path)}

    # ------------------------------------------------------------------
    # TaskState
    # ------------------------------------------------------------------

    async def upsert_task(self, task: dict[str, Any]) -> None:
        state = self._load_state()
        state["tasks"][task["id"]] = task
        self._save_state(state)

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        tasks = self._tasks_dict()
        return tasks.get(task_id)

    async def list_tasks(self, *, status: str | None = None, wave: int | None = None) -> list[dict[str, Any]]:
        tasks = list(self._tasks_dict().values())
        if status is not None:
            tasks = [t for t in tasks if t.get("status") == status]
        if wave is not None:
            tasks = [t for t in tasks if t.get("wave") == wave]
        return tasks

    async def update_task_status(self, task_id: str, status: str, passes: bool | None = None, **fields) -> None:
        state = self._load_state()
        task = state["tasks"].get(task_id)
        if task is None:
            return
        task["status"] = status
        if passes is not None:
            task["passes"] = passes
        task["updated_at"] = _now_iso()
        for k, v in fields.items():
            task[k] = v
        self._save_state(state)

    async def update_task_heartbeat(self, task_id: str, worker_id: str) -> None:
        state = self._load_state()
        task = state["tasks"].get(task_id)
        if task is None:
            return
        task["worker_id"] = worker_id
        task["heartbeat_at"] = _now_iso()
        self._save_state(state)

    async def delete_task(self, task_id: str) -> None:
        state = self._load_state()
        state["tasks"].pop(task_id, None)
        self._save_state(state)

    # ------------------------------------------------------------------
    # Quarantine
    # ------------------------------------------------------------------

    async def quarantine_task(self, task_id: str, reason: str, workspace: str | None = None, extra: dict | None = None) -> None:
        state = self._load_state()
        state["quarantine"][task_id] = {
            "task_id": task_id,
            "reason": reason,
            "quarantined_at": _now_iso(),
            "workspace": workspace,
            "extra": extra or {},
        }
        self._save_state(state)

    async def unquarantine_task(self, task_id: str) -> None:
        state = self._load_state()
        state["quarantine"].pop(task_id, None)
        self._save_state(state)

    async def list_quarantine(self) -> list[dict[str, Any]]:
        return list(self._load_state()["quarantine"].values())

    async def is_quarantined(self, task_id: str) -> bool:
        return task_id in self._load_state()["quarantine"]

    # ------------------------------------------------------------------
    # SchedulerMeta
    # ------------------------------------------------------------------

    async def set_meta(self, key: str, value: Any) -> None:
        state = self._load_state()
        state["meta"][key] = value
        self._save_state(state)

    async def get_meta(self, key: str, default: Any = None) -> Any:
        return self._load_state()["meta"].get(key, default)

    async def delete_meta(self, key: str) -> None:
        state = self._load_state()
        state["meta"].pop(key, None)
        self._save_state(state)

    # ------------------------------------------------------------------
    # Phase
    # ------------------------------------------------------------------

    async def upsert_phase(self, phase: dict[str, Any]) -> None:
        state = self._load_state()
        state["phases"][phase["id"]] = phase
        self._save_state(state)

    async def get_phase(self, phase_id: str) -> dict[str, Any] | None:
        return self._load_state()["phases"].get(phase_id)

    async def list_phases(self) -> list[dict[str, Any]]:
        return list(self._load_state()["phases"].values())

    async def delete_phase(self, phase_id: str) -> None:
        state = self._load_state()
        state["phases"].pop(phase_id, None)
        self._save_state(state)

    # ------------------------------------------------------------------
    # Milestone
    # ------------------------------------------------------------------

    async def upsert_milestone(self, milestone: dict[str, Any]) -> None:
        state = self._load_state()
        state["milestones"][milestone["id"]] = milestone
        self._save_state(state)

    async def get_milestone(self, milestone_id: str) -> dict[str, Any] | None:
        return self._load_state()["milestones"].get(milestone_id)

    async def list_milestones(self) -> list[dict[str, Any]]:
        return list(self._load_state()["milestones"].values())

    async def delete_milestone(self, milestone_id: str) -> None:
        state = self._load_state()
        state["milestones"].pop(milestone_id, None)
        self._save_state(state)

    async def list_tasks_by_milestone(self, milestone_id: str) -> list[dict[str, Any]]:
        tasks = self._tasks_dict()
        return [t for t in tasks.values() if t.get("milestone_id") == milestone_id]

    # ------------------------------------------------------------------
    # Mailbox
    # ------------------------------------------------------------------

    async def send_message(self, message: dict[str, Any]) -> int:
        msg = dict(message)
        msg["id"] = _count_jsonl(self._mailbox_path) + 1
        msg.setdefault("ts", _now_iso())
        msg.setdefault("read", False)
        return _append_jsonl(self._mailbox_path, msg)

    async def list_messages(self, to_agent: str | None = None, read: bool | None = None, limit: int = 100) -> list[dict[str, Any]]:
        msgs = _read_jsonl(self._mailbox_path)
        if to_agent is not None:
            msgs = [m for m in msgs if m.get("to_agent") == to_agent]
        if read is not None:
            msgs = [m for m in msgs if m.get("read") == read]
        return msgs[:limit]

    async def mark_message_read(self, message_id: int, read: bool = True) -> None:
        msgs = _read_jsonl(self._mailbox_path)
        for m in msgs:
            if m.get("id") == message_id:
                m["read"] = read
                break
        # Rewrite the file
        self._mailbox_path.write_text(
            "\n".join(json.dumps(m, ensure_ascii=False) for m in msgs) + "\n",
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # EventLog
    # ------------------------------------------------------------------

    async def log_event(self, event_type: str, task_id: str | None = None,
                        agent_id: str | None = None, wave: int | None = None,
                        payload: dict[str, Any] | None = None,
                        ts: Any | None = None) -> int:
        event = {
            "id": _count_jsonl(self._events_path) + 1,
            "event_type": event_type,
            "task_id": task_id,
            "agent_id": agent_id,
            "wave": wave,
            "payload": payload or {},
            "ts": ts or _now_iso(),
        }
        return _append_jsonl(self._events_path, event)

    async def query_events(self, *, event_type: str | None = None,
                           task_id: str | None = None,
                           agent_id: str | None = None,
                           limit: int = 100,
                           offset: int = 0) -> list[dict[str, Any]]:
        events = _read_jsonl(self._events_path)
        if event_type is not None:
            events = [e for e in events if e.get("event_type") == event_type]
        if task_id is not None:
            events = [e for e in events if e.get("task_id") == task_id]
        if agent_id is not None:
            events = [e for e in events if e.get("agent_id") == agent_id]
        # Reverse to newest-first (same as SQLAlchemy default ordering)
        events.reverse()
        return events[offset:offset + limit]

    # ------------------------------------------------------------------
    # Plan History
    # ------------------------------------------------------------------

    async def log_plan_history(self, entity_type: str, entity_id: str, action: str,
                               *, changed_by: str | None = None,
                               snapshot_before: dict | None = None,
                               snapshot_after: dict | None = None) -> int:
        entry = {
            "id": _count_jsonl(self._plan_history_path) + 1,
            "ts": _now_iso(),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "changed_by": changed_by,
            "snapshot_before": snapshot_before,
            "snapshot_after": snapshot_after,
        }
        return _append_jsonl(self._plan_history_path, entry)

    async def query_plan_history(self, *, entity_type: str | None = None,
                                 entity_id: str | None = None,
                                 limit: int = 100,
                                 offset: int = 0) -> list[dict[str, Any]]:
        entries = _read_jsonl(self._plan_history_path)
        if entity_type is not None:
            entries = [e for e in entries if e.get("entity_type") == entity_type]
        if entity_id is not None:
            entries = [e for e in entries if e.get("entity_id") == entity_id]
        entries.reverse()
        return entries[offset:offset + limit]

    # ------------------------------------------------------------------
    # Plan Export
    # ------------------------------------------------------------------

    async def export_plan(self, *, include_runtime: bool = False) -> dict[str, Any]:
        state = self._load_state()
        tasks = list(state["tasks"].values())
        if include_runtime:
            pass  # runtime fields are already on the task dicts
        else:
            # Strip runtime fields
            runtime_fields = {"status", "passes", "commit_sha", "worker_id",
                              "heartbeat_at", "ai_log_ref"}
            for t in tasks:
                for f in runtime_fields:
                    t.pop(f, None)
        phases = list(state["phases"].values())
        milestones = list(state["milestones"].values())
        meta = dict(state["meta"])

        return {
            "version": self._version,
            "updated_at": _now_iso(),
            "tasks": tasks,
            "phases": phases,
            "milestones": milestones,
            "meta": meta,
        }

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    async def list_active_workers(self) -> list[dict[str, Any]]:
        tasks = self._tasks_dict()
        active: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        for t in tasks.values():
            if t.get("status") != "running":
                continue
            hb = t.get("heartbeat_at")
            if hb:
                try:
                    hb_dt = _utc_from_str(hb)
                    if (now - hb_dt).total_seconds() < 30:
                        active.append({
                            "worker_id": t.get("worker_id", ""),
                            "task_id": t["id"],
                            "task_status": "running",
                            "heartbeat_at": hb,
                        })
                except (ValueError, TypeError):
                    pass
        return active

    async def create_worker_run(self, worker_id: str, task_id: str, workspace: str | None = None) -> int:
        state = self._load_state()
        run_id = state.setdefault("next_run_id", 1)
        state["next_run_id"] = run_id + 1
        self._save_state(state)

        run = {
            "id": run_id,
            "worker_id": worker_id,
            "task_id": task_id,
            "started_at": _now_iso(),
            "status": "running",
            "workspace": workspace,
        }
        _append_jsonl(self._runs_path, run)
        return run_id

    async def finish_worker_run(self, run_id: int, status: str, result_summary: str | None = None) -> None:
        runs = _read_jsonl(self._runs_path)
        for r in runs:
            if r.get("id") == run_id:
                r["status"] = status
                r["ended_at"] = _now_iso()
                if result_summary:
                    r["result_summary"] = result_summary
                started = r.get("started_at")
                if started:
                    try:
                        start_dt = _utc_from_str(started)
                        r["duration_ms"] = int((datetime.now(timezone.utc) - start_dt).total_seconds() * 1000)
                    except (ValueError, TypeError):
                        pass
                break
        # Rewrite file
        with self._runs_path.open("w", encoding="utf-8") as f:
            for run in runs:
                f.write(json.dumps(run, ensure_ascii=False) + "\n")

    async def list_worker_runs(self, *, worker_id: str | None = None,
                               task_id: str | None = None,
                               limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        runs = _read_jsonl(self._runs_path)
        if worker_id is not None:
            runs = [r for r in runs if r.get("worker_id") == worker_id]
        if task_id is not None:
            runs = [r for r in runs if r.get("task_id") == task_id]
        runs.reverse()
        return runs[offset:offset + limit]

    async def get_worker_run(self, run_id: int) -> dict[str, Any] | None:
        for r in _read_jsonl(self._runs_path):
            if r.get("id") == run_id:
                return r
        return None

    async def close(self) -> None:
        """No-op for JSON store — no connections to close."""
        pass
