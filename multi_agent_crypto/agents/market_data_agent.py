"""Agent responsible for fetching market data from Bithumb."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional

from ..exchanges.bithumb import BithumbClient, BithumbTickerResponse
from ..types import AgentState, MarketTicker
from .base import BaseAgent


class MarketDataAgent(BaseAgent):
    """Fetches ticker information for the configured trading pairs."""

    def __init__(
        self,
        quote_currency: str = "KRW",
        tracked_symbols: Optional[Iterable[str]] = None,
        client: Optional[BithumbClient] = None,
    ) -> None:
        super().__init__(name="MarketDataAgent")
        self.quote_currency = quote_currency
        self.tracked_symbols = set(symbol.upper() for symbol in tracked_symbols or [])
        self.client = client or BithumbClient()

    async def run(self, state: AgentState) -> AgentState:
        response = await self.client.fetch_all_tickers(self.quote_currency)
        tickers = self._parse_response(response)
        for ticker in tickers:
            if self.tracked_symbols and ticker.symbol not in self.tracked_symbols:
                continue
            state.market_data[ticker.symbol] = ticker
        state.metadata["market_timestamp"] = response.timestamp.isoformat()
        return state

    def _parse_response(self, response: BithumbTickerResponse) -> List[MarketTicker]:
        tickers: List[MarketTicker] = []
        for symbol, payload in response.data.items():
            if not isinstance(payload, Dict):
                continue
            try:
                tickers.append(self._parse_single(symbol, payload, response.timestamp))
            except (TypeError, ValueError):
                continue
        return tickers

    @staticmethod
    def _parse_single(symbol: str, payload: Dict[str, str], timestamp: datetime) -> MarketTicker:
        price = float(payload.get("closing_price", 0.0))
        opening_price = float(payload.get("opening_price", 0.0))
        change_24h = ((price - opening_price) / opening_price * 100) if opening_price else 0.0
        volume = float(payload.get("units_traded_24H", 0.0))
        high_24h = float(payload.get("max_price", 0.0)) if payload.get("max_price") else None
        low_24h = float(payload.get("min_price", 0.0)) if payload.get("min_price") else None
        return MarketTicker(
            symbol=symbol,
            price=price,
            change_24h=change_24h,
            volume_24h=volume,
            base_currency="KRW",
            high_24h=high_24h,
            low_24h=low_24h,
            timestamp=timestamp,
        )
