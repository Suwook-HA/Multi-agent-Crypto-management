"""Portfolio management agent that reacts to trade decisions."""

from __future__ import annotations

from datetime import datetime, timezone

from ..types import (
    AgentState,
    PortfolioPosition,
    TradeAction,
    TradeDecision,
    TransactionRecord,
)
from .base import BaseAgent


class PortfolioAgent(BaseAgent):
    def __init__(
        self,
        base_currency: str = "KRW",
        initial_cash: float = 1_000_000.0,
        trade_fraction: float = 0.2,
        min_cash_reserve: float = 0.1,
        min_trade_value: float = 10_000.0,
        max_position_allocation: float = 0.35,
        rebalance_buffer: float = 0.1,
    ) -> None:
        super().__init__(name="PortfolioAgent")
        self.base_currency = base_currency
        self.initial_cash = initial_cash
        self.trade_fraction = trade_fraction
        self.min_cash_reserve = min_cash_reserve
        self.min_trade_value = min_trade_value
        self.max_position_allocation = max_position_allocation
        self.rebalance_buffer = rebalance_buffer
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
                self._handle_buy(
                    state,
                    decision,
                    ticker.price,
                )
            elif decision.action == TradeAction.SELL:
                self._handle_sell(
                    state,
                    decision,
                    ticker.price,
                )
        self._rebalance_positions(state)
        return state

    def _handle_buy(
        self,
        state: AgentState,
        decision: TradeDecision,
        price: float,
    ) -> None:
        symbol = decision.symbol
        portfolio = state.portfolio
        cash = portfolio.balances.get(self.base_currency, 0.0)
        reserve = cash * self.min_cash_reserve
        investable = max(0.0, cash - reserve)
        budget = min(investable, cash * self.trade_fraction * decision.confidence)
        position = portfolio.get_position(symbol)
        total_value = portfolio.total_value(state.market_data)
        if total_value <= 0:
            total_value = cash
        current_value = position.quantity * price
        allowed_value = max(0.0, total_value * self.max_position_allocation - current_value)
        budget = min(budget, allowed_value)
        if decision.quantity is not None:
            budget = min(budget, decision.quantity * price)
        if budget < self.min_trade_value:
            return
        quantity = budget / price
        position.update(quantity, price)
        portfolio.update_balance(self.base_currency, -budget)
        portfolio.record_transaction(
            TransactionRecord(
                symbol=symbol,
                action=TradeAction.BUY,
                quantity=quantity,
                price=price,
                timestamp=datetime.now(timezone.utc),
                reasoning=decision.reasoning,
            )
        )

    def _handle_sell(
        self,
        state: AgentState,
        decision: TradeDecision,
        price: float,
    ) -> None:
        symbol = decision.symbol
        portfolio = state.portfolio
        position: PortfolioPosition = portfolio.positions.get(symbol)
        if not position or position.quantity <= 0:
            return
        if decision.quantity is not None:
            quantity = min(position.quantity, decision.quantity)
        else:
            quantity = position.quantity * max(0.1, min(1.0, self.trade_fraction * decision.confidence))
        if quantity * price < self.min_trade_value:
            if position.quantity * price < self.min_trade_value:
                return
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
                reasoning=decision.reasoning,
            )
        )

    def _rebalance_positions(self, state: AgentState) -> None:
        if self.max_position_allocation <= 0:
            return
        portfolio = state.portfolio
        total_value = portfolio.total_value(state.market_data)
        if total_value <= 0:
            return
        for symbol, position in list(portfolio.positions.items()):
            if position.quantity <= 0:
                continue
            ticker = state.market_data.get(symbol)
            if not ticker:
                continue
            position_value = position.quantity * ticker.price
            target_value = total_value * self.max_position_allocation
            threshold = target_value * (1 + self.rebalance_buffer)
            if position_value <= threshold:
                continue
            excess_value = position_value - target_value
            quantity_to_sell = min(position.quantity, excess_value / ticker.price)
            if quantity_to_sell * ticker.price < self.min_trade_value:
                continue
            position.update(-quantity_to_sell, ticker.price)
            proceeds = quantity_to_sell * ticker.price
            portfolio.update_balance(self.base_currency, proceeds)
            portfolio.record_transaction(
                TransactionRecord(
                    symbol=symbol,
                    action=TradeAction.SELL,
                    quantity=quantity_to_sell,
                    price=ticker.price,
                    timestamp=datetime.now(timezone.utc),
                    reasoning="Rebalance: reduce overweight exposure",
                )
            )
            total_value = portfolio.total_value(state.market_data)
