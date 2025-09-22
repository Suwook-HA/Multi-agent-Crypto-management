"""Utilities for transforming agent state into JSON-serialisable payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from ..types import AgentState, SentimentLabel, TradeAction


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def serialize_agent_state(state: AgentState, last_updated: datetime | None) -> Dict[str, Any]:
    """Convert :class:`AgentState` into a JSON friendly dictionary."""

    market_items: List[Dict[str, Any]] = []
    for symbol in sorted(state.market_data.keys()):
        ticker = state.market_data[symbol]
        market_items.append(
            {
                "symbol": ticker.symbol,
                "price": ticker.price,
                "change24h": ticker.change_24h,
                "volume24h": ticker.volume_24h,
                "baseCurrency": ticker.base_currency,
                "high24h": ticker.high_24h,
                "low24h": ticker.low_24h,
                "timestamp": _format_datetime(ticker.timestamp),
            }
        )

    portfolio = state.portfolio
    base_currency = portfolio.base_currency
    cash_balance = portfolio.balances.get(base_currency, 0.0)
    total_value = portfolio.total_value(state.market_data)
    balances = [
        {"currency": currency, "amount": amount}
        for currency, amount in sorted(portfolio.balances.items())
    ]

    positions = []
    for symbol, position in sorted(portfolio.positions.items()):
        ticker = state.market_data.get(symbol)
        current_price = ticker.price if ticker else None
        current_value = (position.quantity * current_price) if current_price is not None else None
        positions.append(
            {
                "symbol": symbol,
                "quantity": position.quantity,
                "averagePrice": position.average_price,
                "currentPrice": current_price,
                "currentValue": current_value,
            }
        )

    history = [
        {
            "symbol": record.symbol,
            "action": record.action.value,
            "quantity": record.quantity,
            "price": record.price,
            "timestamp": _format_datetime(record.timestamp),
            "reasoning": record.reasoning,
        }
        for record in sorted(portfolio.history, key=lambda r: r.timestamp, reverse=True)
    ]

    decisions = [
        {
            "symbol": decision.symbol,
            "action": decision.action.value,
            "confidence": decision.confidence,
            "price": decision.price,
            "reasoning": decision.reasoning,
            "createdAt": _format_datetime(decision.created_at),
        }
        for decision in sorted(state.decisions, key=lambda d: d.created_at, reverse=True)
    ]

    decision_summary: Dict[str, int] = {action.value: 0 for action in TradeAction}
    for decision in state.decisions:
        decision_summary[decision.action.value] += 1

    sentiment_items = []
    sentiment_summary: Dict[str, int] = {label.value: 0 for label in SentimentLabel}
    sentiment_scores: List[float] = []
    for result in state.sentiments.values():
        sentiment_summary[result.label.value] += 1
        sentiment_scores.append(result.score)
        sentiment_items.append(
            {
                "articleId": result.article_id,
                "label": result.label.value,
                "score": result.score,
                "reasoning": result.reasoning,
            }
        )
    sentiment_items.sort(key=lambda item: item["score"], reverse=True)
    average_score = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0

    news_items = []
    for article in sorted(state.news, key=lambda a: a.published_at, reverse=True):
        sentiment = state.sentiments.get(article.id)
        news_items.append(
            {
                "id": article.id,
                "title": article.title,
                "url": article.url,
                "summary": article.summary,
                "source": article.source,
                "publishedAt": _format_datetime(article.published_at),
                "symbols": list(article.symbols),
                "sentiment": (
                    {
                        "label": sentiment.label.value,
                        "score": sentiment.score,
                        "reasoning": sentiment.reasoning,
                    }
                    if sentiment
                    else None
                ),
            }
        )

    return {
        "lastUpdated": _format_datetime(last_updated),
        "metadata": dict(state.metadata),
        "trackedSymbols": sorted({*state.market_data.keys(), *state.portfolio.positions.keys()}),
        "market": {
            "timestamp": state.metadata.get("market_timestamp"),
            "items": market_items,
        },
        "portfolio": {
            "baseCurrency": base_currency,
            "cash": cash_balance,
            "totalValue": total_value,
            "balances": balances,
            "positions": positions,
            "positionsCount": sum(1 for position in positions if position["quantity"] > 0),
            "history": history,
        },
        "decisions": decisions,
        "decisionSummary": decision_summary,
        "sentiment": {
            "summary": sentiment_summary,
            "averageScore": average_score,
            "items": sentiment_items,
        },
        "news": news_items,
    }
