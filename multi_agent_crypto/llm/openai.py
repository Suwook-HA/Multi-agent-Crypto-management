"""OpenAI-powered implementation of the :class:`LLMClient` interface."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from openai import AsyncOpenAI, OpenAIError


logger = logging.getLogger(__name__)

from ..types import NewsArticle, SentimentLabel, SentimentResult
from .base import LLMClient


class OpenAIChatLLM(LLMClient):
    """LLM client that delegates sentiment analysis to the OpenAI Chat API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.2,
    ) -> None:
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError(
                "OpenAI API key is required. Provide it via the OPENAI_API_KEY environment "
                "variable or the openai_api_key CLI flag."
            )
        self.model = model
        self.temperature = temperature
        self._client = AsyncOpenAI(api_key=key)
        self._system_prompt = (
            "You are a financial sentiment analyst specialising in cryptocurrency markets. "
            "When given a news article title and summary, reply with a JSON object that "
            "contains the keys 'label', 'score', and 'reasoning'. The label must be one of "
            "'positive', 'negative', or 'neutral'. The score must be a numeric value between "
            "-1 and 1 representing the sentiment intensity. Keep the reasoning concise and "
            "grounded in the article facts."
        )

    async def analyze_sentiment(self, article: NewsArticle) -> SentimentResult:
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {
                        "role": "user",
                        "content": (
                            "Evaluate the sentiment of the following cryptocurrency news article "
                            "and respond ONLY with JSON containing 'label', 'score', and 'reasoning'.\n\n"
                            f"Title: {article.title}\n"
                            f"Summary: {article.summary or 'N/A'}\n"
                            f"URL: {article.url}"
                        ),
                    },
                ],
            )
        except OpenAIError as exc:
            logger.warning("OpenAI sentiment request failed: %s", exc)
            return self._fallback_result(
                article,
                f"OpenAI API error: {exc}",
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Unexpected error while calling OpenAI Chat API")
            return self._fallback_result(
                article,
                f"Unexpected OpenAI client error: {exc}",
            )
        content = self._message_content_to_text(response)
        result = self._build_result(article, content)
        return result

    async def aclose(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            await close()

    def _build_result(self, article: NewsArticle, raw_content: str) -> SentimentResult:
        data = self._extract_structured_data(raw_content)
        if data is not None:
            label = self._normalise_label(data.get("label"))
            score = self._normalise_score(data.get("score"))
            reasoning = self._extract_reasoning(data, raw_content)
        else:
            label = SentimentLabel.NEUTRAL
            score = 0.0
            reasoning = raw_content.strip() or "OpenAI response did not include structured sentiment data."
        return SentimentResult(
            article_id=article.id,
            label=label,
            score=score,
            reasoning=reasoning,
        )

    def _fallback_result(self, article: NewsArticle, reason: str) -> SentimentResult:
        reason_text = str(reason).strip() or "OpenAI request failed without details."
        return SentimentResult(
            article_id=article.id,
            label=SentimentLabel.NEUTRAL,
            score=0.0,
            reasoning=reason_text,
        )

    @staticmethod
    def _message_content_to_text(response: Any) -> str:
        try:
            choices = getattr(response, "choices") or []
        except AttributeError:
            return ""
        if not choices:
            return ""
        message = getattr(choices[0], "message", None)
        if message is None:
            return ""
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            fragments: list[str] = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    fragments.append(str(item["text"]))
                elif hasattr(item, "text"):
                    fragments.append(str(getattr(item, "text")))
                else:
                    fragments.append(str(item))
            return "".join(fragments)
        return str(content)

    @staticmethod
    def _extract_structured_data(raw_content: str) -> Dict[str, Any] | None:
        text = raw_content.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = text[start : end + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None
        return None

    @staticmethod
    def _normalise_label(label_value: Any) -> SentimentLabel:
        if label_value is None:
            return SentimentLabel.NEUTRAL
        label_text = str(label_value).strip().lower()
        if label_text in {"positive", "pos", "bullish", "optimistic"}:
            return SentimentLabel.POSITIVE
        if label_text in {"negative", "neg", "bearish", "pessimistic"}:
            return SentimentLabel.NEGATIVE
        return SentimentLabel.NEUTRAL

    @staticmethod
    def _normalise_score(score_value: Any) -> float:
        if score_value is None:
            return 0.0
        try:
            score = float(score_value)
        except (TypeError, ValueError):
            return 0.0
        return max(-1.0, min(1.0, score))

    @staticmethod
    def _extract_reasoning(data: Dict[str, Any], fallback: str) -> str:
        reasoning = data.get("reasoning") or data.get("analysis") or fallback
        return str(reasoning).strip()

__all__ = ["OpenAIChatLLM"]
