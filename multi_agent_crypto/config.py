"""Configuration utilities for building the multi-agent system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .agents.market_data_agent import MarketDataAgent
from .agents.news_agent import NewsAgent, NewsSource
from .agents.portfolio_agent import PortfolioAgent
from .agents.risk_management_agent import RiskManagementAgent, RiskParameters
from .agents.sentiment_agent import SentimentAgent
from .agents.strategy_agent import StrategyAgent
from .llm import LLMClient, RuleBasedLLM


def default_news_sources() -> List[NewsSource]:
    return [
        NewsSource(
            name="CoinDesk",
            url="https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
            max_items=20,
        ),
        NewsSource(
            name="CoinTelegraph",
            url="https://cointelegraph.com/rss",
            max_items=20,
        ),
        NewsSource(
            name="GoogleNews",
            url="https://news.google.com/rss/search?q=cryptocurrency+OR+bitcoin+OR+ethereum&hl=en-US&gl=US&ceid=US:en",
            max_items=20,
        ),
    ]


@dataclass
class SystemConfig:
    quote_currency: str = "KRW"
    tracked_symbols: List[str] = field(default_factory=lambda: ["BTC", "ETH", "XRP", "ADA", "SOL"])
    initial_cash: float = 1_000_000.0
    trade_fraction: float = 0.2
    min_cash_reserve: float = 0.1
    min_trade_value: float = 10_000.0
    news_sources: List[NewsSource] = field(default_factory=default_news_sources)
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 8.0
    risk_min_confidence: float = 0.35
    max_position_allocation: float = 0.35
    rebalance_buffer: float = 0.1

    def create_agents(self, llm_client: LLMClient | None = None):
        llm = llm_client or RuleBasedLLM()
        return [
            MarketDataAgent(
                quote_currency=self.quote_currency,
                tracked_symbols=self.tracked_symbols,
            ),
            NewsAgent(
                sources=self.news_sources,
                tracked_symbols=self.tracked_symbols,
            ),
            SentimentAgent(llm_client=llm),
            StrategyAgent(tracked_symbols=self.tracked_symbols),
            RiskManagementAgent(
                params=RiskParameters(
                    stop_loss_pct=self.stop_loss_pct,
                    take_profit_pct=self.take_profit_pct,
                    min_confidence=self.risk_min_confidence,
                )
            ),
            PortfolioAgent(
                base_currency=self.quote_currency,
                initial_cash=self.initial_cash,
                trade_fraction=self.trade_fraction,
                min_cash_reserve=self.min_cash_reserve,
                min_trade_value=self.min_trade_value,
                max_position_allocation=self.max_position_allocation,
                rebalance_buffer=self.rebalance_buffer,
            ),
        ]
