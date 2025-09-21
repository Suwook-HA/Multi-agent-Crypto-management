import asyncio
from datetime import datetime, timezone

from multi_agent_crypto.agents.sentiment_agent import SentimentAgent
from multi_agent_crypto.llm import RuleBasedLLM
from multi_agent_crypto.types import AgentState, NewsArticle, SentimentLabel


def test_sentiment_agent_generates_scores():
    state = AgentState()
    article = NewsArticle(
        id="1",
        title="Bitcoin surges to new record as adoption grows",
        url="https://example.com/bitcoin",
        summary="Investors celebrate as BTC price hits a new high on strong growth",
        published_at=datetime.now(timezone.utc),
        source="UnitTest",
        symbols=["BTC"],
    )
    state.add_news([article])
    agent = SentimentAgent(RuleBasedLLM())
    asyncio.run(agent.run(state))
    sentiment = state.sentiments[article.id]
    assert sentiment.label == SentimentLabel.POSITIVE
    assert sentiment.score > 0
