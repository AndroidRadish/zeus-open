"""
Metrics route registration for ZeusOpen v3 API.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Query, Request as FastAPIRequest

from api.metrics import MetricsCollector


def register_metrics_routes(app: FastAPI) -> None:
    """Register /metrics/* endpoints on the given FastAPI app."""

    @app.get("/metrics/summary")
    async def metrics_summary(request: FastAPIRequest) -> dict[str, Any]:
        collector = MetricsCollector(request.app.state.store)
        return await collector.summary()

    @app.get("/metrics/tasks")
    async def metrics_tasks(request: FastAPIRequest) -> list[dict[str, Any]]:
        collector = MetricsCollector(request.app.state.store)
        return await collector.task_metrics()

    @app.get("/metrics/bottleneck")
    async def metrics_bottleneck(request: FastAPIRequest, top_n: int = Query(5, ge=1, le=100)) -> list[dict[str, Any]]:
        collector = MetricsCollector(request.app.state.store)
        return await collector.bottleneck_tasks(top_n=top_n)

    @app.get("/metrics/blocked")
    async def metrics_blocked(request: FastAPIRequest) -> list[dict[str, Any]]:
        collector = MetricsCollector(request.app.state.store)
        return await collector.blocked_chains()
