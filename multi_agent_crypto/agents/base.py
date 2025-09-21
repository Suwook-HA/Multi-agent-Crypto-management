"""Base classes and utilities for building agents."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from ..types import AgentState


class BaseAgent(ABC):
    """Abstract base class for all agents in the system."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.logger = logging.getLogger(name)

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        """Execute the agent logic and mutate the shared state."""

    async def __call__(self, state: AgentState) -> AgentState:
        self.logger.debug("Running agent %s", self.name)
        return await self.run(state)

    async def aclose(self) -> None:
        """Hook for cleaning up resources when orchestrator stops."""
        return None

    def configure_logger(self, level: int = logging.INFO) -> None:
        handler_exists = any(isinstance(h, logging.StreamHandler) for h in self.logger.handlers)
        if not handler_exists:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(level)


class StatefulAgent(BaseAgent):
    """Extension of :class:`BaseAgent` that keeps internal state across runs."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._internal_state: dict[str, Any] = {}

    def get_internal_state(self) -> dict[str, Any]:
        return self._internal_state

    def set_internal_state(self, key: str, value: Any) -> None:
        self._internal_state[key] = value
