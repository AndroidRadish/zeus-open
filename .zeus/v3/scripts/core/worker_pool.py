"""
ZeusOpen v3 worker pool.

Manages a dynamic number of ZeusWorker coroutines.
"""
from __future__ import annotations

import asyncio

from core.worker import ZeusWorker
from dispatcher.base import SubagentDispatcher
from store.base import AsyncStateStore
from task_queue.base import TaskQueue
from workspace.manager import WorkspaceManager


class WorkerPool:
    """Pool of workers consuming from a shared queue."""

    def __init__(
        self,
        store: AsyncStateStore,
        queue: TaskQueue,
        dispatcher: SubagentDispatcher,
        workspace_manager: WorkspaceManager,
        max_workers: int = 3,
        bus=None,
    ) -> None:
        self.store = store
        self.queue = queue
        self.dispatcher = dispatcher
        self.workspace_manager = workspace_manager
        self.max_workers = max_workers
        self.bus = bus
        self._workers: list[ZeusWorker] = []
        self._tasks: set[asyncio.Task] = set()
        self._stop = False

    async def start(self) -> None:
        """Launch all worker coroutines."""
        for i in range(self.max_workers):
            worker = ZeusWorker(
                worker_id=f"worker-{i}",
                store=self.store,
                queue=self.queue,
                dispatcher=self.dispatcher,
                workspace_manager=self.workspace_manager,
                bus=self.bus,
            )
            self._workers.append(worker)
            t = asyncio.create_task(worker.run())
            self._tasks.add(t)

    async def scale_to(self, count: int) -> None:
        """Dynamically adjust the number of active workers."""
        done = {t for t in self._tasks if t.done()}
        self._tasks -= done

        current = len(self._workers)
        if count > current:
            for i in range(current, count):
                worker = ZeusWorker(
                    worker_id=f"worker-{i}",
                    store=self.store,
                    queue=self.queue,
                    dispatcher=self.dispatcher,
                    workspace_manager=self.workspace_manager,
                    bus=self.bus,
                )
                self._workers.append(worker)
                t = asyncio.create_task(worker.run())
                self._tasks.add(t)
        elif count < current:
            excess = self._workers[count:]
            self._workers = self._workers[:count]
            for w in excess:
                w.stop()

    async def stop(self, timeout: float = 3.0) -> None:
        """Signal all workers to stop and await their exit.

        Default timeout is short (3s) because shutdown should be fast;
        callers doing graceful shutdown can pass a larger value.
        """
        self._stop = True
        for worker in self._workers:
            worker.stop()
        if self._tasks:
            # Phase 1: wait for natural exit (workers should respond quickly
            # to self._stop and break out of their loops)
            done, pending = await asyncio.wait(self._tasks, timeout=timeout)
            # Phase 2: hard-cancel stragglers (e.g. stuck in subprocess I/O)
            if pending:
                for t in pending:
                    t.cancel()
                await asyncio.wait(pending, timeout=2.0)
            self._tasks.clear()
        self._workers.clear()

    async def __aenter__(self) -> "WorkerPool":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()
