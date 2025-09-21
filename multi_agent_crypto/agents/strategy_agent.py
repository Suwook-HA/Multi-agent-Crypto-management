"""Agent that fuses market data and sentiment into actionable trades."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
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
        sentiment_half_life_hours: float = 6.0,
        min_sentiment_articles: int = 1,
    ) -> None:
        super().__init__(name="StrategyAgent")
        self.tracked_symbols = [symbol.upper() for symbol in tracked_symbols]
        self.max_trades = max_trades
        self.sentiment_buy_threshold = sentiment_buy_threshold
        self.sentiment_sell_threshold = sentiment_sell_threshold
        self.price_buy_threshold = price_buy_threshold
        self.price_sell_threshold = price_sell_threshold
        self.sentiment_half_life_hours = sentiment_half_life_hours
        self.min_sentiment_articles = min_sentiment_articles

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
        now = datetime.now(timezone.utc)
        aggregated: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"weighted": 0.0, "weight": 0.0, "count": 0}
        )
        for article in state.news:
            sentiment: SentimentResult | None = state.sentiments.get(article.id)
            if not sentiment or not article.symbols:
                continue
            published_at = article.published_at
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            age_hours = max(0.0, (now - published_at).total_seconds() / 3600)
            weight = self._sentiment_weight(age_hours)
            for symbol in article.symbols:
                metrics = aggregated[symbol.upper()]
                metrics["weighted"] += sentiment.score * weight
                metrics["weight"] += weight
                metrics["count"] += 1
        results: Dict[str, float] = {}
        for symbol, metrics in aggregated.items():
            if metrics["count"] < self.min_sentiment_articles or metrics["weight"] <= 0:
                continue
            results[symbol] = metrics["weighted"] / metrics["weight"]
        return results

    def _rank_symbols(self, state: AgentState, sentiment_scores: Dict[str, float]) -> List[str]:
        # prioritize symbols present both in market data and sentiment
        max_volume = max(
            (ticker.volume_24h for ticker in state.market_data.values() if ticker.volume_24h),
            default=0.0,
        )
        total_value = state.portfolio.total_value(state.market_data)

        def score(symbol: str) -> float:
            ticker = state.market_data.get(symbol)
            if not ticker:
                return -999
            sentiment = sentiment_scores.get(symbol, 0.0)
            price_component = math.tanh(ticker.change_24h / 10)
            volume_component = 0.0
            if max_volume > 0 and ticker.volume_24h:
                volume_component = min(1.0, ticker.volume_24h / max_volume)
            exposure_penalty = 0.0
            if total_value > 0:
                position = state.portfolio.positions.get(symbol)
                if position and position.quantity > 0:
                    exposure = (position.quantity * ticker.price) / total_value
                    exposure_penalty = min(0.3, exposure)
            return sentiment * 0.5 + price_component * 0.3 + volume_component * 0.2 - exposure_penalty

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

    def _sentiment_weight(self, age_hours: float) -> float:
        if self.sentiment_half_life_hours <= 0:
            return 1.0
        decay = math.log(2) / self.sentiment_half_life_hours
        return math.exp(-decay * age_hours)
