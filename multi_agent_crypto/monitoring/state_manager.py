"""Background task that continuously refreshes the agent state for monitoring."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any

from ..config import SystemConfig
from ..orchestrator import AgentOrchestrator
from ..types import AgentState
from .serialization import serialize_agent_state


class MonitoringStateManager:
    """Runs the agent orchestrator on a schedule and exposes serialized state."""

    def __init__(
        self,
        config: SystemConfig | None = None,
        *,
        refresh_interval: float = 120.0,
        log_level: int = logging.INFO,
    ) -> None:
        self.config = config or SystemConfig()
        self.refresh_interval = refresh_interval
        self.state: AgentState = AgentState()
        self.last_updated: datetime | None = None
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[Any] | None = None
        self._orchestrator: AgentOrchestrator | None = None
        self.logger = logging.getLogger("multi_agent_crypto.monitoring")
        self.logger.setLevel(log_level)

    async def start(self) -> None:
        """Create the orchestrator and launch the periodic refresh task."""

        if self._task is not None:
            return
        agents = self.config.create_agents()
        for agent in agents:
            agent.configure_logger(level=self.logger.level)
        self._orchestrator = AgentOrchestrator(agents)
        await self.refresh()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the refresh loop and close agents."""

        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._orchestrator is not None:
            await self._orchestrator.aclose()
            self._orchestrator = None

    async def refresh(self) -> None:
        """Execute a single orchestrator cycle and update the shared snapshot."""

        if self._orchestrator is None:
            raise RuntimeError("MonitoringStateManager has not been started")
        async with self._lock:
            try:
                self.state = await self._orchestrator.run_cycle(self.state)
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - logging path
                self.logger.exception("Failed to refresh monitoring state")
            else:
                self.last_updated = datetime.now(timezone.utc)

    async def get_state(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the latest agent state."""

        async with self._lock:
            return serialize_agent_state(self.state, self.last_updated)

    async def _run_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.refresh_interval)
                try:
                    await self.refresh()
                except RuntimeError:
                    # The orchestrator was stopped; exit gracefully.
                    break
        except asyncio.CancelledError:
            pass
