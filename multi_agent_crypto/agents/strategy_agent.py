"""Agent that fuses market data and sentiment into actionable trades."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from ..types import AgentState, SentimentResult, TradeAction, TradeDecision
from .base import BaseAgent


class StrategyAgent(BaseAgent):
    def __init__(
        self,
        tracked_symbols: Iterable[str],
        max_trades: int = 3,
        sentiment_buy_threshold: float = 0.25,
        sentiment_sell_threshold: float = 0.25,
        price_buy_threshold: float = 1.0,
        price_sell_threshold: float = -1.0,
    ) -> None:
        super().__init__(name="StrategyAgent")
        self.tracked_symbols = [symbol.upper() for symbol in tracked_symbols]
        self.max_trades = max_trades
        self.sentiment_buy_threshold = sentiment_buy_threshold
        self.sentiment_sell_threshold = sentiment_sell_threshold
        self.price_buy_threshold = price_buy_threshold
        self.price_sell_threshold = price_sell_threshold

    async def run(self, state: AgentState) -> AgentState:
        state.reset_decisions()
        if not state.market_data:
            return state

        sentiment_scores = self._aggregate_sentiment(state)
        ranked_symbols = self._rank_symbols(state, sentiment_scores)
        for symbol in ranked_symbols[: self.max_trades]:
            ticker = state.market_data.get(symbol)
            if not ticker:
                continue
            sentiment_score = sentiment_scores.get(symbol, 0.0)
            price_change = ticker.change_24h
            action = self._decide_action(sentiment_score, price_change)
            if action == TradeAction.HOLD:
                continue
            confidence = self._confidence(sentiment_score, price_change)
            reasoning = self._build_reasoning(action, sentiment_score, price_change)
            decision = TradeDecision(
                symbol=symbol,
                action=action,
                confidence=confidence,
                price=ticker.price,
                reasoning=reasoning,
            )
            state.add_decision(decision)
        return state

    def _aggregate_sentiment(self, state: AgentState) -> Dict[str, float]:
        aggregated: Dict[str, List[float]] = defaultdict(list)
        for article in state.news:
            sentiment: SentimentResult | None = state.sentiments.get(article.id)
            if not sentiment or not article.symbols:
                continue
            for symbol in article.symbols:
                aggregated[symbol.upper()].append(sentiment.score)
        return {symbol: sum(scores) / len(scores) for symbol, scores in aggregated.items() if scores}

    def _rank_symbols(self, state: AgentState, sentiment_scores: Dict[str, float]) -> List[str]:
        # prioritize symbols present both in market data and sentiment
        def score(symbol: str) -> float:
            ticker = state.market_data.get(symbol)
            if not ticker:
                return -999
            sentiment = sentiment_scores.get(symbol, 0.0)
            return sentiment * 0.6 + max(-1.0, min(1.0, ticker.change_24h / 10)) * 0.4

        candidates = [symbol for symbol in self.tracked_symbols if symbol in state.market_data]
        candidates.extend(symbol for symbol in sentiment_scores.keys() if symbol not in candidates)
        unique_candidates = []
        for symbol in candidates:
            if symbol not in unique_candidates:
                unique_candidates.append(symbol)
        unique_candidates.sort(key=score, reverse=True)
        return unique_candidates

    def _decide_action(self, sentiment: float, price_change: float) -> TradeAction:
        if sentiment >= self.sentiment_buy_threshold and price_change >= self.price_buy_threshold:
            return TradeAction.BUY
        if sentiment <= -self.sentiment_sell_threshold and price_change <= self.price_sell_threshold:
            return TradeAction.SELL
        return TradeAction.HOLD

    @staticmethod
    def _confidence(sentiment: float, price_change: float) -> float:
        sentiment_component = max(-1.0, min(1.0, sentiment))
        price_component = max(-1.0, min(1.0, price_change / 10))
        combined = 0.6 * sentiment_component + 0.4 * price_component
        return max(0.0, min(1.0, (combined + 1) / 2))

    @staticmethod
    def _build_reasoning(action: TradeAction, sentiment: float, price_change: float) -> str:
        direction = "bullish" if action == TradeAction.BUY else "bearish"
        sentiment_pct = sentiment * 100
        return (
            f"{direction.title()} setup: sentiment {sentiment_pct:+.1f}% and price change {price_change:+.2f}%"
        )
