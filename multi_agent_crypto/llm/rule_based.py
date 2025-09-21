"""A simple rule-based LLM implementation used for offline testing."""

from __future__ import annotations

from dataclasses import dataclass

from ..types import NewsArticle, SentimentLabel, SentimentResult
from .base import LLMClient


@dataclass
class KeywordSet:
    positive: tuple[str, ...]
    negative: tuple[str, ...]


class RuleBasedLLM(LLMClient):
    """Uses keyword scoring to emulate sentiment analysis."""

    def __init__(self, keywords: KeywordSet | None = None) -> None:
        self.keywords = keywords or KeywordSet(
            positive=("surge", "bull", "record", "partnership", "growth", "launch", "support"),
            negative=("hack", "decline", "drop", "lawsuit", "ban", "scam", "loss"),
        )

    async def analyze_sentiment(self, article: NewsArticle) -> SentimentResult:
        text = f"{article.title} {article.summary}".lower()
        score = 0
        for word in self.keywords.positive:
            if word in text:
                score += 1
        for word in self.keywords.negative:
            if word in text:
                score -= 1
        normalized = max(-1.0, min(1.0, score / 3))
        if normalized > 0.15:
            label = SentimentLabel.POSITIVE
        elif normalized < -0.15:
            label = SentimentLabel.NEGATIVE
        else:
            label = SentimentLabel.NEUTRAL
        reasoning = self._build_reasoning(label, normalized)
        return SentimentResult(
            article_id=article.id,
            label=label,
            score=normalized,
            reasoning=reasoning,
        )

    @staticmethod
    def _build_reasoning(label: SentimentLabel, score: float) -> str:
        base = {
            SentimentLabel.POSITIVE: "Positive catalysts identified",
            SentimentLabel.NEGATIVE: "Negative risk factors highlighted",
            SentimentLabel.NEUTRAL: "Balanced signals detected",
        }[label]
        return f"{base} (score={score:+.2f})"
