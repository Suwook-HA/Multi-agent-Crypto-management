"""Simple orchestrator that executes agents sequentially."""

from __future__ import annotations

import asyncio
from typing import Iterable, List, Sequence

from .agents.base import BaseAgent
from .types import AgentState


class AgentOrchestrator:
    def __init__(self, agents: Sequence[BaseAgent]) -> None:
        self.agents: List[BaseAgent] = list(agents)

    async def run_cycle(self, state: AgentState) -> AgentState:
        for agent in self.agents:
            state = await agent(state)
        return state

    async def run(
        self,
        cycles: int = 1,
        delay: float = 0.0,
        state: AgentState | None = None,
    ) -> AgentState:
        shared_state = state or AgentState()
        for _ in range(cycles):
            shared_state = await self.run_cycle(shared_state)
            if delay:
                await asyncio.sleep(delay)
        return shared_state

    async def aclose(self) -> None:
        for agent in self.agents:
            await agent.aclose()


def build_default_orchestrator(agents: Iterable[BaseAgent]) -> AgentOrchestrator:
    return AgentOrchestrator(list(agents))
