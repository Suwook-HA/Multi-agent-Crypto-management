"""Agent that fuses market data and sentiment into actionable trades."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from ..types import AgentState, MarketTicker, SentimentResult, TradeAction, TradeDecision
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
        strategy_mode: str = "expert",
        expert_buy_score: float = 0.35,
        expert_sell_score: float = 0.35,
        breakout_margin: float = 0.01,
        mean_reversion_margin: float = 0.02,
        momentum_scale: float = 5.0,
        volume_threshold: float = 1_000.0,
        volatility_threshold: float = 0.12,
    ) -> None:
        super().__init__(name="StrategyAgent")
        self.tracked_symbols = [symbol.upper() for symbol in tracked_symbols]
        self.max_trades = max_trades
        self.sentiment_buy_threshold = sentiment_buy_threshold
        self.sentiment_sell_threshold = sentiment_sell_threshold
        self.price_buy_threshold = price_buy_threshold
        self.price_sell_threshold = price_sell_threshold
        self.strategy_mode = strategy_mode.lower()
        self.expert_buy_score = expert_buy_score
        self.expert_sell_score = expert_sell_score
        self.breakout_margin = breakout_margin
        self.mean_reversion_margin = mean_reversion_margin
        self.momentum_scale = momentum_scale
        self.volume_threshold = volume_threshold
        self.volatility_threshold = volatility_threshold

    async def run(self, state: AgentState) -> AgentState:
        state.reset_decisions()
        if not state.market_data:
            return state

        sentiment_scores = self._aggregate_sentiment(state)
        signal_cache: Dict[str, Dict[str, float]] = {}
        for symbol, ticker in state.market_data.items():
            sentiment = sentiment_scores.get(symbol, 0.0)
            signal_cache[symbol] = self._generate_signal(symbol, ticker, sentiment)

        ranked_symbols = self._rank_symbols(state, sentiment_scores, signal_cache)
        for symbol in ranked_symbols[: self.max_trades]:
            ticker = state.market_data.get(symbol)
            if not ticker:
                continue
            sentiment_score = sentiment_scores.get(symbol, 0.0)
            signal = signal_cache.get(symbol)
            if signal is None:
                signal = self._generate_signal(symbol, ticker, sentiment_score)
                signal_cache[symbol] = signal
            action = self._decide_action(signal)
            if action == TradeAction.HOLD:
                continue
            confidence = self._confidence(action, signal)
            reasoning = self._build_reasoning(action, signal)
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

    def _rank_symbols(
        self,
        state: AgentState,
        sentiment_scores: Dict[str, float],
        signal_cache: Dict[str, Dict[str, float]],
    ) -> List[str]:
        # prioritize symbols present both in market data and sentiment
        def score(symbol: str) -> float:
            signal = signal_cache.get(symbol)
            if signal:
                return signal.get("composite_score", -999)
            ticker = state.market_data.get(symbol)
            if not ticker:
                return -999
            sentiment = sentiment_scores.get(symbol, 0.0)
            price_component = max(-1.0, min(1.0, ticker.change_24h / 10))
            return sentiment * 0.6 + price_component * 0.4

        candidates = [symbol for symbol in self.tracked_symbols if symbol in state.market_data]
        candidates.extend(symbol for symbol in sentiment_scores.keys() if symbol not in candidates)
        unique_candidates = []
        for symbol in candidates:
            if symbol not in unique_candidates:
                unique_candidates.append(symbol)
        unique_candidates.sort(key=score, reverse=True)
        return unique_candidates

    def _generate_signal(
        self, symbol: str, ticker: MarketTicker, sentiment: float
    ) -> Dict[str, float]:
        price_change = ticker.change_24h
        signal: Dict[str, float]
        if self.strategy_mode == "expert":
            signal = self._generate_expert_signal(symbol, ticker, sentiment, price_change)
        else:
            signal = self._generate_basic_signal(ticker, sentiment, price_change)
        return signal

    def _generate_basic_signal(
        self, ticker: MarketTicker, sentiment: float, price_change: float
    ) -> Dict[str, float]:
        price_component = max(-1.0, min(1.0, price_change / 10))
        composite = sentiment * 0.6 + price_component * 0.4
        return {
            "sentiment": sentiment,
            "price_change": price_change,
            "composite_score": composite,
            "momentum": price_component,
        }

    def _generate_expert_signal(
        self,
        symbol: str,
        ticker: MarketTicker,
        sentiment: float,
        price_change: float,
    ) -> Dict[str, float]:
        price = ticker.price
        high = ticker.high_24h or price
        low = ticker.low_24h or price
        volume = ticker.volume_24h or 0.0

        # Momentum scaled to [-1, 1]
        momentum = max(-1.5, min(1.5, price_change / self.momentum_scale))
        momentum = max(-1.0, min(1.0, momentum))

        # Breakout / breakdown bias based on proximity to extremes
        breakout_bias = 0.0
        if high > 0 and price >= high * (1 - self.breakout_margin):
            breakout_bias = 1.0
        elif low > 0 and price <= low * (1 + self.breakout_margin):
            breakout_bias = -1.0

        # Mean reversion bias based on deviation from 24h midpoint
        mean_reversion_bias = 0.0
        if high != low:
            midpoint = (high + low) / 2
            deviation = (price - midpoint) / midpoint if midpoint else 0.0
            if deviation > self.mean_reversion_margin:
                mean_reversion_bias = -1.0
            elif deviation < -self.mean_reversion_margin:
                mean_reversion_bias = 1.0

        # Volatility filter using a simplified ATR proxy
        volatility_range = abs(high - low) / price if price else 0.0
        volatility_penalty = min(1.0, volatility_range / self.volatility_threshold) if price else 0.0
        volatility_bias = 1.0 - 0.5 * volatility_penalty

        # Volume strength relative to configured floor
        if self.volume_threshold > 0:
            volume_strength = max(0.0, min(1.0, volume / self.volume_threshold))
        else:
            volume_strength = 0.0

        composite = (
            0.45 * sentiment
            + 0.25 * momentum
            + 0.15 * breakout_bias
            + 0.10 * volume_strength
            + 0.05 * volatility_bias
            + 0.10 * mean_reversion_bias
        )

        return {
            "symbol": symbol,
            "sentiment": sentiment,
            "price_change": price_change,
            "momentum": momentum,
            "breakout_bias": breakout_bias,
            "mean_reversion_bias": mean_reversion_bias,
            "volatility_range": volatility_range,
            "volatility_penalty": volatility_penalty,
            "volatility_bias": volatility_bias,
            "volume_strength": volume_strength,
            "composite_score": composite,
        }

    def _decide_action(self, signal: Dict[str, float]) -> TradeAction:
        if self.strategy_mode == "expert":
            score = signal.get("composite_score", 0.0)
            if score >= self.expert_buy_score:
                return TradeAction.BUY
            if score <= -self.expert_sell_score:
                return TradeAction.SELL
            return TradeAction.HOLD

        sentiment = signal.get("sentiment", 0.0)
        price_change = signal.get("price_change", 0.0)
        if sentiment >= self.sentiment_buy_threshold and price_change >= self.price_buy_threshold:
            return TradeAction.BUY
        if sentiment <= -self.sentiment_sell_threshold and price_change <= self.price_sell_threshold:
            return TradeAction.SELL
        return TradeAction.HOLD

    def _confidence(self, action: TradeAction, signal: Dict[str, float]) -> float:
        if action == TradeAction.HOLD:
            return 0.0
        if self.strategy_mode == "expert":
            composite = abs(signal.get("composite_score", 0.0))
            volume_strength = max(0.2, signal.get("volume_strength", 0.0))
            volatility_penalty = signal.get("volatility_penalty", 0.0)
            adjusted = composite * volume_strength * (1 - 0.5 * volatility_penalty)
            return max(0.0, min(1.0, adjusted))

        sentiment = signal.get("sentiment", 0.0)
        price_change = signal.get("price_change", 0.0)
        sentiment_component = max(-1.0, min(1.0, sentiment))
        price_component = max(-1.0, min(1.0, price_change / 10))
        combined = 0.6 * sentiment_component + 0.4 * price_component
        return max(0.0, min(1.0, (combined + 1) / 2))

    def _build_reasoning(self, action: TradeAction, signal: Dict[str, float]) -> str:
        sentiment = signal.get("sentiment", 0.0)
        price_change = signal.get("price_change", 0.0)
        direction = "bullish" if action == TradeAction.BUY else "bearish"
        sentiment_pct = sentiment * 100
        if self.strategy_mode == "expert":
            volume_strength = signal.get("volume_strength", 0.0)
            volatility_range = signal.get("volatility_range", 0.0)
            breakout_bias = signal.get("breakout_bias", 0.0)
            mean_reversion_bias = signal.get("mean_reversion_bias", 0.0)
            tags: List[str] = []
            if breakout_bias > 0:
                tags.append("breakout confirmation")
            elif breakout_bias < 0:
                tags.append("breakdown risk")
            if mean_reversion_bias > 0:
                tags.append("oversold rebound")
            elif mean_reversion_bias < 0:
                tags.append("overbought pressure")
            tag_text = f" ({', '.join(tags)})" if tags else ""
            return (
                f"{direction.title()} expert signal: sentiment {sentiment_pct:+.1f}%, "
                f"momentum {price_change:+.2f}%, volume strength {volume_strength:.2f}, "
                f"volatility {volatility_range:.2f}{tag_text}"
            )

        return (
            f"{direction.title()} setup: sentiment {sentiment_pct:+.1f}% and price change {price_change:+.2f}%"
        )
