"""Asynchronous client utilities for Bithumb public/private endpoints."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


class BithumbAPIError(RuntimeError):
    """Raised when Bithumb API returns a non-success response."""

    def __init__(self, status: str, message: str) -> None:
        super().__init__(f"Bithumb API error {status}: {message}")
        self.status = status
        self.message = message


@dataclass
class BithumbTickerResponse:
    status: str
    data: Dict[str, Any]
    timestamp: datetime


class BithumbClient:
    """Minimal async client for Bithumb public endpoints."""

    BASE_URL = "https://api.bithumb.com"

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    async def fetch_all_tickers(self, quote_currency: str = "KRW") -> BithumbTickerResponse:
        url = f"{self.BASE_URL}/public/ticker/ALL_{quote_currency}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
            status = payload.get("status")
            if status != "0000":
                raise BithumbAPIError(status=status or "unknown", message=payload.get("message", ""))
            data = payload.get("data", {})
            if "date" in data:
                timestamp = datetime.fromtimestamp(int(data.get("date")) / 1000, tz=timezone.utc)
            else:
                timestamp = datetime.now(timezone.utc)
            data.pop("date", None)
            return BithumbTickerResponse(status=status, data=data, timestamp=timestamp)

    @staticmethod
    def stable_id_for_symbol(symbol: str) -> str:
        return hashlib.sha256(symbol.encode("utf-8")).hexdigest()

    async def close(self) -> None:
        """Provided for API symmetry with authenticated clients."""
        return None


async def fetch_ticker_snapshot(quote_currency: str = "KRW", timeout: float = 10.0) -> BithumbTickerResponse:
    client = BithumbClient(timeout=timeout)
    try:
        return await client.fetch_all_tickers(quote_currency=quote_currency)
    finally:
        await client.close()
