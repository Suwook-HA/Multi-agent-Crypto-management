"""Agent that gathers external news relevant to tracked assets."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Iterable, List, Optional
from xml.etree import ElementTree
from xml.etree.ElementTree import ParseError

import httpx

from ..types import AgentState, NewsArticle
from .base import BaseAgent


@dataclass
class NewsSource:
    name: str
    url: str
    max_items: Optional[int] = None


class NewsAgent(BaseAgent):
    """Fetches and parses crypto related news from RSS feeds."""

    def __init__(
        self,
        sources: Iterable[NewsSource],
        tracked_symbols: Iterable[str],
        symbol_aliases: Optional[Dict[str, List[str]]] = None,
        timeout: float = 10.0,
        max_articles: int = 30,
    ) -> None:
        super().__init__(name="NewsAgent")
        self.sources = list(sources)
        self.timeout = timeout
        self.max_articles = max_articles
        self.tracked_symbols = [symbol.upper() for symbol in tracked_symbols]
        self.symbol_aliases = symbol_aliases or self._default_aliases(self.tracked_symbols)

    async def run(self, state: AgentState) -> AgentState:
        articles: List[NewsArticle] = []
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for source in self.sources:
                fetched = await self._fetch_source(client, source)
                articles.extend(fetched)
        if articles:
            # sort by date desc and limit
            articles.sort(key=lambda article: article.published_at, reverse=True)
            state.add_news(articles[: self.max_articles])
        return state

    async def _fetch_source(self, client: httpx.AsyncClient, source: NewsSource) -> List[NewsArticle]:
        try:
            response = await client.get(source.url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self.logger.warning(
                "Failed to fetch news from %s (%s): %s", source.name, source.url, exc
            )
            return []
        return self._parse_rss(response.text, source)

    def _parse_rss(self, raw_xml: str, source: NewsSource) -> List[NewsArticle]:
        articles: List[NewsArticle] = []
        try:
            root = ElementTree.fromstring(raw_xml)
        except ParseError:
            return []
        channel = root.find("channel")
        if channel is None:
            return articles
        items = channel.findall("item")
        limit = source.max_items or len(items)
        for item in items[:limit]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            description = (item.findtext("description") or "").strip()
            pub_date_raw = item.findtext("pubDate")
            published_at = parsedate_to_datetime(pub_date_raw) if pub_date_raw else datetime.now(timezone.utc)
            uid_basis = f"{source.name}:{link or title}"
            article_id = hashlib.sha256(uid_basis.encode("utf-8")).hexdigest()
            symbols = self._detect_symbols(title, description)
            article = NewsArticle(
                id=article_id,
                title=title,
                url=link,
                summary=description,
                published_at=published_at,
                source=source.name,
                symbols=symbols,
            )
            articles.append(article)
        return articles

    def _detect_symbols(self, title: str, description: str) -> List[str]:
        text = f"{title} {description}".upper()
        detected: List[str] = []
        for symbol in self.tracked_symbols:
            aliases = self.symbol_aliases.get(symbol, [symbol])
            for alias in aliases:
                if alias.upper() in text:
                    detected.append(symbol)
                    break
        return detected

    @staticmethod
    def _default_aliases(symbols: Iterable[str]) -> Dict[str, List[str]]:
        defaults: Dict[str, List[str]] = {
            "BTC": ["BTC", "BITCOIN"],
            "ETH": ["ETH", "ETHEREUM"],
            "XRP": ["XRP", "RIPPLE"],
            "ADA": ["ADA", "CARDANO"],
            "DOGE": ["DOGE", "DOGECOIN"],
            "SOL": ["SOL", "SOLANA"],
        }
        return {symbol: defaults.get(symbol, [symbol]) for symbol in symbols}
