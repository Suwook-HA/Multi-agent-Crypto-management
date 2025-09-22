from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from openai import OpenAIError

from multi_agent_crypto.llm.openai import OpenAIChatLLM
from multi_agent_crypto.types import NewsArticle, SentimentLabel


def test_openai_llm_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        OpenAIChatLLM(model="gpt-test")


def test_openai_llm_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyChatCompletions:
        async def create(self, **kwargs):  # type: ignore[no-untyped-def]
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"label": "negative", "score": -0.5, "reasoning": "Regulatory concerns."}'
                        )
                    )
                ]
            )

    class DummyClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.chat = SimpleNamespace(completions=DummyChatCompletions())
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    monkeypatch.setattr("multi_agent_crypto.llm.openai.AsyncOpenAI", DummyClient)

    article = NewsArticle(
        id="article-1",
        title="Regulators tighten oversight",
        url="https://example.com/news",
        summary="Global watchdogs announce stricter rules for digital asset platforms.",
        published_at=datetime.now(timezone.utc),
    )

    client = OpenAIChatLLM(api_key="test", model="gpt-test")

    async def _run() -> None:
        result = await client.analyze_sentiment(article)
        assert result.label is SentimentLabel.NEGATIVE
        assert result.score == pytest.approx(-0.5)
        assert "Regulatory" in result.reasoning
        await client.aclose()
        assert client._client.closed  # type: ignore[attr-defined]

    asyncio.run(_run())


def test_openai_llm_returns_neutral_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyError(OpenAIError):
        pass

    class DummyChatCompletions:
        async def create(self, **kwargs):  # type: ignore[no-untyped-def]
            raise DummyError("unauthorized")

    class DummyClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.chat = SimpleNamespace(completions=DummyChatCompletions())
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    monkeypatch.setattr("multi_agent_crypto.llm.openai.AsyncOpenAI", DummyClient)

    article = NewsArticle(
        id="article-1",
        title="Regulators tighten oversight",
        url="https://example.com/news",
        summary="Global watchdogs announce stricter rules for digital asset platforms.",
        published_at=datetime.now(timezone.utc),
    )

    client = OpenAIChatLLM(api_key="test", model="gpt-test")

    async def _run() -> None:
        result = await client.analyze_sentiment(article)
        assert result.label is SentimentLabel.NEUTRAL
        assert result.score == pytest.approx(0.0)
        assert "unauthorized" in result.reasoning.lower()
        await client.aclose()
        assert client._client.closed  # type: ignore[attr-defined]

    asyncio.run(_run())
