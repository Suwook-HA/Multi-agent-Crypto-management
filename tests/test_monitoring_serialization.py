from datetime import datetime, timezone

import pytest

from multi_agent_crypto.monitoring.serialization import serialize_agent_state
from multi_agent_crypto.types import (
    AgentState,
    MarketTicker,
    NewsArticle,
    PortfolioPosition,
    SentimentLabel,
    SentimentResult,
    TradeAction,
    TradeDecision,
    TransactionRecord,
)


def test_serialize_agent_state_produces_dashboard_payload():
    state = AgentState()
    timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    state.metadata["market_timestamp"] = timestamp.isoformat()

    state.market_data["BTC"] = MarketTicker(
        symbol="BTC",
        price=100_000.0,
        change_24h=5.0,
        volume_24h=1_250.0,
        base_currency="KRW",
        high_24h=110_000.0,
        low_24h=95_000.0,
        timestamp=timestamp,
    )

    state.portfolio.base_currency = "KRW"
    state.portfolio.update_balance("KRW", 500_000.0)
    state.portfolio.positions["BTC"] = PortfolioPosition(symbol="BTC", quantity=1.2, average_price=90_000.0)
    state.portfolio.history.append(
        TransactionRecord(
            symbol="BTC",
            action=TradeAction.BUY,
            quantity=1.2,
            price=90_000.0,
            timestamp=timestamp,
            reasoning="portfolio initial buy",
        )
    )

    state.decisions.append(
        TradeDecision(
            symbol="BTC",
            action=TradeAction.BUY,
            confidence=0.75,
            price=100_000.0,
            reasoning="momentum and sentiment aligned",
        )
    )

    article = NewsArticle(
        id="news-1",
        title="Bitcoin surges to new highs",
        url="https://example.com/news",
        summary="Price momentum continues as buyers dominate the market.",
        published_at=timestamp,
        source="CoinDesk",
        symbols=["BTC"],
    )
    state.news.append(article)
    state.add_sentiment(
        SentimentResult(
            article_id=article.id,
            label=SentimentLabel.POSITIVE,
            score=0.8,
            reasoning="Strong positive catalysts identified",
        )
    )

    last_updated = datetime(2024, 1, 1, 12, 5, tzinfo=timezone.utc)
    payload = serialize_agent_state(state, last_updated)

    assert payload["lastUpdated"] == last_updated.isoformat()
    assert payload["market"]["items"][0]["symbol"] == "BTC"
    assert payload["portfolio"]["baseCurrency"] == "KRW"
    expected_total = 500_000.0 + 1.2 * 100_000.0
    assert payload["portfolio"]["totalValue"] == pytest.approx(expected_total)
    assert payload["decisions"][0]["action"] == "buy"
    assert payload["decisionSummary"]["buy"] == 1
    assert payload["sentiment"]["summary"]["positive"] == 1
    assert payload["news"][0]["sentiment"]["label"] == "positive"
    assert "BTC" in payload["trackedSymbols"]
