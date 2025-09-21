"""Agent that applies an LLM to compute sentiment scores."""

from __future__ import annotations

from ..llm import LLMClient
from ..types import AgentState
from .base import BaseAgent


class SentimentAgent(BaseAgent):
    def __init__(self, llm_client: LLMClient) -> None:
        super().__init__(name="SentimentAgent")
        self.llm_client = llm_client

    async def run(self, state: AgentState) -> AgentState:
        for article in state.news:
            if article.id in state.sentiments:
                continue
            sentiment = await self.llm_client.analyze_sentiment(article)
            state.add_sentiment(sentiment)
        return state

    async def aclose(self) -> None:
        await self.llm_client.aclose()
