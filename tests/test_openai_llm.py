import asyncio
import json
from datetime import datetime, timezone

import pytest

from multi_agent_crypto.llm.openai import OpenAIGPT5LLM
from multi_agent_crypto.types import NewsArticle, SentimentLabel


@pytest.fixture
def sample_article() -> NewsArticle:
    return NewsArticle(
        id="article-1",
        title="BTC rallies on institutional inflows",
        url="https://example.com/btc",
        summary="Major funds allocate more capital to bitcoin as risk appetite improves.",
        published_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        symbols=["BTC"],
    )


def test_parse_response_content_positive(sample_article: NewsArticle) -> None:
    payload = json.dumps(
        {
            "label": "POSITIVE",
            "score": 0.72,
            "reasoning": "Institutional demand supports further upside.",
        }
    )
    result = OpenAIGPT5LLM.parse_response_content(sample_article, payload)
    assert result.article_id == sample_article.id
    assert result.label == SentimentLabel.POSITIVE
    assert result.score == pytest.approx(0.72)
    assert "Institutional" in result.reasoning


def test_parse_response_content_clamps_score(sample_article: NewsArticle) -> None:
    payload = json.dumps({"label": "neg", "score": -2.5, "reasoning": "Severe sell-off."})
    result = OpenAIGPT5LLM.parse_response_content(sample_article, payload)
    assert result.label == SentimentLabel.NEGATIVE
    assert result.score == -1.0


def test_parse_response_content_invalid_label(sample_article: NewsArticle) -> None:
    payload = json.dumps({"label": "mixed", "score": 0.1, "reasoning": "Unclear."})
    with pytest.raises(ValueError):
        OpenAIGPT5LLM.parse_response_content(sample_article, payload)


class DummyResponse:
    def __init__(self, content: str) -> None:
        self.choices = [DummyChoice(content)]


class DummyChoice:
    def __init__(self, content: str) -> None:
        self.message = DummyMessage(content)


class DummyMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class DummyCompletions:
    def __init__(self, response: DummyResponse) -> None:
        self._response = response
        self.last_kwargs = None

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


class DummyChat:
    def __init__(self, response: DummyResponse) -> None:
        self.completions = DummyCompletions(response)


class DummyClient:
    def __init__(self, response: DummyResponse) -> None:
        self.chat = DummyChat(response)
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def test_analyze_sentiment_calls_openai(sample_article: NewsArticle) -> None:
    response_payload = json.dumps(
        {
            "label": "neutral",
            "score": 0.05,
            "reasoning": "Mixed signals with limited momentum.",
        }
    )
    dummy_response = DummyResponse(response_payload)
    client = DummyClient(dummy_response)
    llm = OpenAIGPT5LLM(client=client, model="gpt-5.0-mini", temperature=0.15)

    result = asyncio.run(llm.analyze_sentiment(sample_article))

    assert result.label == SentimentLabel.NEUTRAL
    assert result.score == pytest.approx(0.05)
    kwargs = client.chat.completions.last_kwargs
    assert kwargs["model"] == "gpt-5.0-mini"
    assert kwargs["temperature"] == 0.15
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["messages"][0]["role"] == "system"
    assert "label 은 positive" in kwargs["messages"][1]["content"]
    # OpenAIGPT5LLM should not close externally provided clients
    asyncio.run(llm.aclose())
    assert client.closed is False
