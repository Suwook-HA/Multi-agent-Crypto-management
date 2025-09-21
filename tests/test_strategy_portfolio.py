import asyncio
from datetime import datetime, timezone

import pytest

from multi_agent_crypto.agents.portfolio_agent import PortfolioAgent
from multi_agent_crypto.agents.strategy_agent import StrategyAgent
from multi_agent_crypto.types import (
    AgentState,
    MarketTicker,
    NewsArticle,
    PortfolioPosition,
    SentimentLabel,
    SentimentResult,
    TradeAction,
)


def test_strategy_and_portfolio_flow():
    state = AgentState()
    ticker = MarketTicker(
        symbol="BTC",
        price=36_000_000.0,
        change_24h=5.0,
        volume_24h=1200.0,
        base_currency="KRW",
        high_24h=37_000_000.0,
        low_24h=34_000_000.0,
        timestamp=datetime.now(timezone.utc),
    )
    state.market_data[ticker.symbol] = ticker
    article = NewsArticle(
        id="article-1",
        title="Institutional investors show strong support for BTC",
        url="https://example.com/article",
        summary="Positive outlook as major funds accumulate Bitcoin",
        published_at=datetime.now(timezone.utc),
        source="UnitTest",
        symbols=["BTC"],
    )
    state.add_news([article])
    state.add_sentiment(
        SentimentResult(
            article_id=article.id,
            label=SentimentLabel.POSITIVE,
            score=0.6,
            reasoning="Strong institutional inflows",
        )
    )
    strategy = StrategyAgent(tracked_symbols=["BTC"], max_trades=1)
    asyncio.run(strategy.run(state))
    assert state.decisions
    decision = state.decisions[0]
    assert decision.action == TradeAction.BUY
    portfolio_agent = PortfolioAgent(
        base_currency="KRW",
        initial_cash=100_000.0,
        trade_fraction=0.5,
        min_cash_reserve=0.1,
        min_trade_value=1_000.0,
    )
    asyncio.run(portfolio_agent.run(state))
    position = state.portfolio.positions.get("BTC")
    assert position is not None
    assert position.quantity > 0
    assert state.portfolio.balances["KRW"] < 100_000.0


def test_portfolio_rebalance_trims_overweight_position():
    state = AgentState()
    ticker = MarketTicker(
        symbol="XRP",
        price=1_000.0,
        change_24h=2.5,
        volume_24h=5_000_000.0,
        base_currency="KRW",
        high_24h=1_050.0,
        low_24h=950.0,
        timestamp=datetime.now(timezone.utc),
    )
    state.market_data[ticker.symbol] = ticker
    state.portfolio.positions[ticker.symbol] = PortfolioPosition(
        symbol=ticker.symbol,
        quantity=10.0,
        average_price=950.0,
    )
    portfolio_agent = PortfolioAgent(
        base_currency="KRW",
        initial_cash=0.0,
        trade_fraction=0.5,
        min_cash_reserve=0.0,
        min_trade_value=1.0,
        max_position_allocation=0.3,
        rebalance_buffer=0.0,
    )

    asyncio.run(portfolio_agent.run(state))

    position = state.portfolio.positions[ticker.symbol]
    assert position.quantity == pytest.approx(3.0)
    assert state.portfolio.balances["KRW"] == pytest.approx(7_000.0)
    assert state.portfolio.history
    assert state.portfolio.history[0].reasoning.startswith("Rebalance")
