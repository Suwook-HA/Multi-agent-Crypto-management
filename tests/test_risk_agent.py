import asyncio
from datetime import datetime, timezone

import pytest

from multi_agent_crypto.agents.risk_management_agent import RiskManagementAgent, RiskParameters
from multi_agent_crypto.types import (
    AgentState,
    MarketTicker,
    PortfolioPosition,
    TradeAction,
    TradeDecision,
)


def test_risk_agent_triggers_stop_loss():
    state = AgentState()
    state.market_data["BTC"] = MarketTicker(
        symbol="BTC",
        price=36_000_000.0,
        change_24h=-4.5,
        volume_24h=1200.0,
        base_currency="KRW",
        timestamp=datetime.now(timezone.utc),
    )
    state.portfolio.positions["BTC"] = PortfolioPosition(
        symbol="BTC",
        quantity=0.5,
        average_price=40_000_000.0,
    )
    agent = RiskManagementAgent(
        params=RiskParameters(stop_loss_pct=5.0, take_profit_pct=12.0, min_confidence=0.25)
    )

    asyncio.run(agent.run(state))

    assert state.decisions, "Stop-loss should generate an exit decision"
    decision = state.decisions[0]
    assert decision.action == TradeAction.SELL
    assert decision.symbol == "BTC"
    assert decision.quantity == pytest.approx(0.5)
    assert "Stop loss" in decision.reasoning


def test_risk_agent_overrides_buy_decision_when_take_profit_hits():
    state = AgentState()
    state.market_data["ETH"] = MarketTicker(
        symbol="ETH",
        price=3_200_000.0,
        change_24h=6.2,
        volume_24h=950.0,
        base_currency="KRW",
        timestamp=datetime.now(timezone.utc),
    )
    state.portfolio.positions["ETH"] = PortfolioPosition(
        symbol="ETH",
        quantity=1.0,
        average_price=2_800_000.0,
    )
    state.add_decision(
        TradeDecision(
            symbol="ETH",
            action=TradeAction.BUY,
            confidence=0.7,
            price=3_200_000.0,
            reasoning="Strategy wants to add exposure",
        )
    )
    agent = RiskManagementAgent(
        params=RiskParameters(stop_loss_pct=5.0, take_profit_pct=10.0, min_confidence=0.3)
    )

    asyncio.run(agent.run(state))

    assert len(state.decisions) == 1
    decision = state.decisions[0]
    assert decision.action == TradeAction.SELL
    assert decision.symbol == "ETH"
    assert "Take profit" in decision.reasoning
