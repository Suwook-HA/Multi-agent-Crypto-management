"""FastAPI application exposing the monitoring dashboard API and static site."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ..config import SystemConfig
from .state_manager import MonitoringStateManager


def create_app(
    config: SystemConfig | None = None,
    *,
    refresh_interval: float = 120.0,
    log_level: int = logging.INFO,
) -> FastAPI:
    """Create the monitoring FastAPI application."""

    manager = MonitoringStateManager(config=config, refresh_interval=refresh_interval, log_level=log_level)
    app = FastAPI(
        title="Multi-agent Crypto Monitoring",
        description="Real-time dashboard for inspecting agent activity and portfolio state.",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.manager = manager

    @app.on_event("startup")
    async def _startup() -> None:
        await manager.start()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await manager.stop()

    @app.get("/api/state")
    async def _get_state() -> Any:
        return await manager.get_state()

    @app.get("/api/health")
    async def _healthcheck() -> JSONResponse:
        payload = {
            "status": "ok",
            "lastUpdated": manager.last_updated.isoformat() if manager.last_updated else None,
            "refreshInterval": refresh_interval,
        }
        return JSONResponse(payload)

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
