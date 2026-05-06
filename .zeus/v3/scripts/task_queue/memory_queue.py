"""
In-memory asyncio queue for local development and testing.
"""
from __future__ import annotations

import asyncio
import math
from typing import Any

from task_queue.base import TaskQueue


class MemoryTaskQueue(TaskQueue):
    """Simple in-memory queue using asyncio.Queue."""

    def __init__(self, max_retries: int = 3) -> None:
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._inflight: dict[str, dict[str, Any]] = {}
        self._max_retries = max_retries

    async def enqueue(self, task: dict[str, Any]) -> None:
        await self._queue.put(task)

    async def dequeue(self) -> dict[str, Any] | None:
        try:
            task = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None
        self._inflight[task["id"]] = task
        return task

    async def ack(self, task_id: str) -> None:
        self._inflight.pop(task_id, None)

    async def nack(self, task_id: str, reason: str) -> None:
        task = self._inflight.pop(task_id, None)
        if task:
            task.setdefault("retry_count", 0)
            task["retry_count"] += 1
            task["last_failure_reason"] = reason
            if task["retry_count"] >= self._max_retries:
                return  # dead-letter — drop from queue
            backoff = min(task["retry_count"] ** 2, 30)
            await asyncio.sleep(backoff * 0.1)
            await self._queue.put(task)

    async def size(self) -> int:
        return self._queue.qsize()

    async def close(self) -> None:
        pass
