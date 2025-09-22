import asyncio
from datetime import datetime, timezone

from multi_agent_crypto.agents.strategy_agent import StrategyAgent
from multi_agent_crypto.types import (
    AgentState,
    MarketTicker,
    NewsArticle,
    SentimentLabel,
    SentimentResult,
    TradeAction,
)


def _build_state(
    symbol: str,
    price: float,
    change_24h: float,
    volume_24h: float,
    high_24h: float,
    low_24h: float,
    sentiment_score: float,
    sentiment_label: SentimentLabel,
) -> AgentState:
    state = AgentState()
    ticker = MarketTicker(
        symbol=symbol,
        price=price,
        change_24h=change_24h,
        volume_24h=volume_24h,
        high_24h=high_24h,
        low_24h=low_24h,
        timestamp=datetime.now(timezone.utc),
        base_currency="KRW",
    )
    state.market_data[symbol] = ticker
    article = NewsArticle(
        id=f"article-{symbol}-{sentiment_label}",
        title="Test article",
        url="https://example.com",
        summary="unit-test summary",
        published_at=datetime.now(timezone.utc),
        source="UnitTest",
        symbols=[symbol],
    )
    state.add_news([article])
    state.add_sentiment(
        SentimentResult(
            article_id=article.id,
            label=sentiment_label,
            score=sentiment_score,
            reasoning="unit-test",
        )
    )
    return state


def test_expert_strategy_generates_buy_signal():
    state = _build_state(
        symbol="ETH",
        price=2_098_000.0,
        change_24h=4.5,
        volume_24h=5_000.0,
        high_24h=2_110_000.0,
        low_24h=2_000_000.0,
        sentiment_score=0.65,
        sentiment_label=SentimentLabel.POSITIVE,
    )
    agent = StrategyAgent(
        tracked_symbols=["ETH"],
        strategy_mode="expert",
        volume_threshold=1_000.0,
        volatility_threshold=0.2,
    )
    asyncio.run(agent.run(state))
    assert len(state.decisions) == 1
    decision = state.decisions[0]
    assert decision.action == TradeAction.BUY
    assert "expert signal" in decision.reasoning.lower()


def test_expert_strategy_triggers_sell_on_breakdown():
    state = _build_state(
        symbol="XRP",
        price=882.0,
        change_24h=-8.0,
        volume_24h=700.0,
        high_24h=1_050.0,
        low_24h=880.0,
        sentiment_score=-0.8,
        sentiment_label=SentimentLabel.NEGATIVE,
    )
    agent = StrategyAgent(
        tracked_symbols=["XRP"],
        strategy_mode="expert",
        volume_threshold=1_000.0,
        volatility_threshold=0.3,
    )
    asyncio.run(agent.run(state))
    assert len(state.decisions) == 1
    decision = state.decisions[0]
    assert decision.action == TradeAction.SELL
    assert "expert signal" in decision.reasoning.lower()


def test_expert_strategy_holds_when_signals_conflict():
    state = _build_state(
        symbol="ADA",
        price=1_500.0,
        change_24h=0.5,
        volume_24h=12.0,
        high_24h=2_000.0,
        low_24h=1_000.0,
        sentiment_score=0.4,
        sentiment_label=SentimentLabel.POSITIVE,
    )
    agent = StrategyAgent(
        tracked_symbols=["ADA"],
        strategy_mode="expert",
        volume_threshold=1_000.0,
        volatility_threshold=0.15,
    )
    asyncio.run(agent.run(state))
    assert not state.decisions
