"""Portfolio management agent that reacts to trade decisions."""

from __future__ import annotations

from datetime import datetime, timezone

from ..types import AgentState, PortfolioPosition, TradeAction, TransactionRecord
from .base import BaseAgent


class PortfolioAgent(BaseAgent):
    def __init__(
        self,
        base_currency: str = "KRW",
        initial_cash: float = 1_000_000.0,
        trade_fraction: float = 0.2,
        min_cash_reserve: float = 0.1,
        min_trade_value: float = 10_000.0,
    ) -> None:
        super().__init__(name="PortfolioAgent")
        self.base_currency = base_currency
        self.initial_cash = initial_cash
        self.trade_fraction = trade_fraction
        self.min_cash_reserve = min_cash_reserve
        self.min_trade_value = min_trade_value
        self._initialized = False

    async def run(self, state: AgentState) -> AgentState:
        portfolio = state.portfolio
        portfolio.ensure_balance(self.base_currency)
        if not self._initialized and portfolio.balances.get(self.base_currency, 0.0) <= 0:
            portfolio.update_balance(self.base_currency, self.initial_cash)
            self._initialized = True
        for decision in state.decisions:
            ticker = state.market_data.get(decision.symbol)
            if not ticker:
                continue
            if decision.action == TradeAction.BUY:
                self._handle_buy(state, decision.confidence, ticker.price, decision.reasoning, decision.symbol)
            elif decision.action == TradeAction.SELL:
                self._handle_sell(state, decision.confidence, ticker.price, decision.reasoning, decision.symbol)
        return state

    def _handle_buy(
        self,
        state: AgentState,
        confidence: float,
        price: float,
        reasoning: str,
        symbol: str,
    ) -> None:
        portfolio = state.portfolio
        cash = portfolio.balances.get(self.base_currency, 0.0)
        reserve = cash * self.min_cash_reserve
        investable = max(0.0, cash - reserve)
        budget = min(investable, cash * self.trade_fraction * confidence)
        if budget < self.min_trade_value:
            return
        quantity = budget / price
        position = portfolio.get_position(symbol)
        position.update(quantity, price)
        portfolio.update_balance(self.base_currency, -budget)
        portfolio.record_transaction(
            TransactionRecord(
                symbol=symbol,
                action=TradeAction.BUY,
                quantity=quantity,
                price=price,
                timestamp=datetime.now(timezone.utc),
                reasoning=reasoning,
            )
        )

    def _handle_sell(
        self,
        state: AgentState,
        confidence: float,
        price: float,
        reasoning: str,
        symbol: str,
    ) -> None:
        portfolio = state.portfolio
        position: PortfolioPosition = portfolio.positions.get(symbol)
        if not position or position.quantity <= 0:
            return
        quantity = position.quantity * max(0.1, min(1.0, self.trade_fraction * confidence))
        if quantity * price < self.min_trade_value:
            quantity = position.quantity
        proceeds = quantity * price
        position.update(-quantity, price)
        portfolio.update_balance(self.base_currency, proceeds)
        portfolio.record_transaction(
            TransactionRecord(
                symbol=symbol,
                action=TradeAction.SELL,
                quantity=quantity,
                price=price,
                timestamp=datetime.now(timezone.utc),
                reasoning=reasoning,
            )
        )
