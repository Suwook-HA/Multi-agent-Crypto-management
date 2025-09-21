"""Interfaces for large language model providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import NewsArticle, SentimentResult


class LLMClient(ABC):
    """Abstract interface describing sentiment analysis capability."""

    @abstractmethod
    async def analyze_sentiment(self, article: NewsArticle) -> SentimentResult:
        """Analyse sentiment of a news article."""

    async def aclose(self) -> None:
        """Hook for async clients that need cleanup."""
        return None
