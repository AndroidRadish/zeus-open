"""
ZeusOpen v3 configuration loader.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ZeusConfig:
    def __init__(self, project_root: Path, version: str = "v3") -> None:
        self.project_root = Path(project_root)
        self.version = version
        self._config_path = self.project_root / ".zeus" / version / "config.json"
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if not self._config_path.exists():
            return {}
        with open(self._config_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    @property
    def project_name(self) -> str:
        return self._data.get("project", {}).get("name", "ZeusOpen Project")

    @property
    def north_star(self) -> str:
        return self._data.get("metrics", {}).get("north_star", "N/A")

    @property
    def subagent(self) -> dict[str, Any]:
        return self._data.get("subagent", {})

    @property
    def dispatcher_mode(self) -> str:
        return self.subagent.get("dispatcher", "auto")

    @property
    def dispatcher_timeout(self) -> float:
        val = self.subagent.get("timeout_seconds")
        return float(val) if val else 600.0

    @property
    def bootstrap_files(self) -> list[str]:
        default = ["AGENTS.md", "USER.md", "IDENTITY.md", "SOUL.md"]
        return self.subagent.get("bootstrap", {}).get("files", default)

    @property
    def workspace_backend(self) -> str:
        return self._data.get("workspace", {}).get("backend", "copytree")

    @property
    def sqlite_busy_timeout(self) -> float:
        val = self._data.get("database", {}).get("sqlite_busy_timeout")
        return float(val) if val else 30.0

    @property
    def sqlite_max_retries(self) -> int:
        val = self._data.get("database", {}).get("sqlite_max_retries")
        return int(val) if val else 3

    @property
    def scheduler_lease_timeout(self) -> float:
        val = self._data.get("scheduler", {}).get("lease_timeout_seconds")
        return float(val) if val else 60.0

    @property
    def scheduler_tick_interval(self) -> float:
        val = self._data.get("scheduler", {}).get("tick_interval")
        return float(val) if val else 0.2

    @property
    def worker_max_idle_ticks(self) -> int:
        val = self._data.get("worker", {}).get("max_idle_ticks")
        return int(val) if val else 10

    @property
    def worker_heartbeat_interval(self) -> float:
        val = self._data.get("worker", {}).get("heartbeat_interval")
        return float(val) if val else 2.0

    @property
    def queue_retry_max(self) -> int:
        val = self._data.get("queue", {}).get("retry_max")
        return int(val) if val else 3

    def raw(self) -> dict[str, Any]:
        return self._data
