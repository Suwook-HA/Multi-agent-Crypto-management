"""OpenAI GPT-5 client implementation."""

from __future__ import annotations

import inspect
import json
import os
from datetime import timezone
from typing import Any, Dict, Iterable, Optional

from .base import LLMClient
from ..types import NewsArticle, SentimentLabel, SentimentResult

try:  # pragma: no cover - import guard is exercised indirectly in tests
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover - handled by runtime checks
    AsyncOpenAI = None  # type: ignore[assignment]


class OpenAIGPT5LLM(LLMClient):
    """LLM client that delegates sentiment analysis to OpenAI's GPT-5 models."""

    SYSTEM_PROMPT = (
        "You are an expert financial sentiment analyst. Analyse cryptocurrency news "
        "headlines and summaries. Always respond with valid JSON using the schema "
        "{label: string, score: float, reasoning: string}. Valid labels are "
        '"positive", "negative", and "neutral". Scores must be within [-1, 1] and '
        "reflect sentiment strength."
    )

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "gpt-5.0-mini",
        temperature: float = 0.2,
        client: Optional[Any] = None,
    ) -> None:
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            if AsyncOpenAI is None:
                raise RuntimeError(
                    "The 'openai' package is required to use OpenAIGPT5LLM. Install it via "
                    "'pip install openai' or the project extra '.[llm]'."
                )
            resolved_key = api_key or os.getenv("OPENAI_API_KEY")
            if not resolved_key:
                raise ValueError(
                    "OPENAI_API_KEY is not configured. Provide api_key or set the "
                    "OPENAI_API_KEY environment variable."
                )
            self._client = AsyncOpenAI(api_key=resolved_key)
            self._owns_client = True
        self.model = model
        self.temperature = temperature

    async def analyze_sentiment(self, article: NewsArticle) -> SentimentResult:
        """Call GPT-5 to analyse sentiment for the provided article."""

        response = await self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": self._build_prompt(article)},
            ],
        )
        if not getattr(response, "choices", None):
            raise ValueError("OpenAI GPT-5 response did not include choices")
        choice = response.choices[0]
        content = self._choice_content_to_text(choice)
        if not content:
            raise ValueError("OpenAI GPT-5 response contained no content")
        return self.parse_response_content(article, content)

    async def aclose(self) -> None:
        """Close the underlying OpenAI client if this instance owns it."""

        close = getattr(self._client, "close", None)
        if not close or not self._owns_client:
            return
        result = close()
        if inspect.isawaitable(result):
            await result

    @staticmethod
    def _build_prompt(article: NewsArticle) -> str:
        published_at = article.published_at
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        published = published_at.astimezone(timezone.utc).isoformat()
        symbols = ", ".join(article.symbols) if article.symbols else "(none detected)"
        return (
            "다음은 암호화폐 관련 뉴스 기사 정보입니다. 내용을 분석하여 투자 관점의 감성을 판단해 주세요. "
            "요청 사항:\n"
            "1. label 은 positive, negative, neutral 중 하나로만 출력\n"
            "2. score 는 -1.0 에서 1.0 사이의 소수\n"
            "3. reasoning 에는 핵심 근거를 1~2문장으로 작성\n\n"
            f"제목: {article.title}\n"
            f"요약: {article.summary}\n"
            f"원문 링크: {article.url}\n"
            f"게시 시각(UTC): {published}\n"
            f"관련 심볼: {symbols}\n"
        )

    @staticmethod
    def _choice_content_to_text(choice: Any) -> str:
        message = getattr(choice, "message", None)
        if message is None:
            return ""
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, Iterable):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
                else:
                    text = getattr(item, "text", None)
                    if text is not None:
                        parts.append(str(text))
            return "".join(parts).strip()
        return str(content).strip()

    @staticmethod
    def parse_response_content(article: NewsArticle, content: str) -> SentimentResult:
        """Parse the JSON payload returned by GPT-5 into a SentimentResult."""

        try:
            payload: Dict[str, Any] = json.loads(content)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
            raise ValueError("OpenAI GPT-5 response was not valid JSON") from exc

        label_value = payload.get("label")
        if not isinstance(label_value, str):
            raise ValueError("OpenAI GPT-5 response missing 'label'")
        normalized_label = label_value.strip().lower()
        label_map = {
            "positive": SentimentLabel.POSITIVE,
            "neg": SentimentLabel.NEGATIVE,
            "negative": SentimentLabel.NEGATIVE,
            "neutral": SentimentLabel.NEUTRAL,
            "pos": SentimentLabel.POSITIVE,
        }
        label = label_map.get(normalized_label)
        if label is None:
            raise ValueError(f"Unsupported sentiment label from GPT-5: {label_value}")

        score_value = payload.get("score")
        try:
            score = float(score_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("OpenAI GPT-5 response missing numeric 'score'") from exc
        score = max(-1.0, min(1.0, score))

        reasoning = payload.get("reasoning", "")
        if not isinstance(reasoning, str):
            reasoning = str(reasoning)
        reasoning = reasoning.strip() or "Reasoning not provided by model."

        return SentimentResult(
            article_id=article.id,
            label=label,
            score=score,
            reasoning=reasoning,
        )

