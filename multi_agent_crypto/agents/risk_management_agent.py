"""Agent that enforces stop-loss and take-profit rules on open positions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict

from ..types import AgentState, TradeAction, TradeDecision
from .base import BaseAgent


@dataclass
class RiskParameters:
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 8.0
    min_confidence: float = 0.35


class RiskManagementAgent(BaseAgent):
    """Adds exit decisions when portfolio positions breach risk thresholds."""

    def __init__(self, params: RiskParameters | None = None) -> None:
        super().__init__(name="RiskManagementAgent")
        self.params = params or RiskParameters()

    async def run(self, state: AgentState) -> AgentState:
        if not state.portfolio.positions or not state.market_data:
            return state

        decision_map: Dict[str, TradeDecision] = {
            decision.symbol: decision for decision in state.decisions
        }

        for symbol, position in state.portfolio.positions.items():
            if position.quantity <= 0 or position.average_price <= 0:
                continue

            ticker = state.market_data.get(symbol)
            if not ticker:
                continue

            change_pct = ((ticker.price - position.average_price) / position.average_price) * 100
            trigger = self._determine_trigger(change_pct)
            if not trigger:
                continue

            existing = decision_map.get(symbol)
            if existing and existing.action == TradeAction.SELL:
                continue
            if existing and existing.action == TradeAction.BUY:
                try:
                    state.decisions.remove(existing)
                except ValueError:
                    pass
                decision_map.pop(symbol, None)

            confidence = self._confidence(abs(change_pct), trigger)
            reasoning = (
                f"{trigger} triggered at {change_pct:+.2f}% from average entry price"
            )
            decision = TradeDecision(
                symbol=symbol,
                action=TradeAction.SELL,
                confidence=confidence,
                price=ticker.price,
                reasoning=reasoning,
                quantity=position.quantity,
                created_at=datetime.now(timezone.utc),
            )
            state.add_decision(decision)
            decision_map[symbol] = decision
            self.logger.info("%s for %s", trigger, symbol)

        return state

    def _determine_trigger(self, change_pct: float) -> str | None:
        if change_pct <= -self.params.stop_loss_pct:
            return "Stop loss"
        if change_pct >= self.params.take_profit_pct:
            return "Take profit"
        return None

    def _confidence(self, move_pct: float, trigger: str) -> float:
        threshold = (
            self.params.stop_loss_pct
            if trigger == "Stop loss"
            else self.params.take_profit_pct
        )
        if threshold <= 0:
            return 1.0
        ratio = move_pct / threshold
        confidence = max(self.params.min_confidence, min(1.0, ratio))
        return confidence

