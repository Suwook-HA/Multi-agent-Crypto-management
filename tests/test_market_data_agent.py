from datetime import datetime, timezone

from multi_agent_crypto.agents.market_data_agent import MarketDataAgent
from multi_agent_crypto.exchanges.bithumb import BithumbTickerResponse


def test_parse_market_data_snapshot():
    agent = MarketDataAgent(tracked_symbols=["BTC"], quote_currency="KRW")
    response = BithumbTickerResponse(
        status="0000",
        data={
            "BTC": {
                "closing_price": "36000000",
                "opening_price": "34000000",
                "units_traded_24H": "123.45",
                "max_price": "37000000",
                "min_price": "33000000",
            }
        },
        timestamp=datetime.now(timezone.utc),
    )
    tickers = agent._parse_response(response)
    assert len(tickers) == 1
    ticker = tickers[0]
    assert ticker.symbol == "BTC"
    assert ticker.price == 36_000_000
    assert round(ticker.change_24h, 2) == round(((36_000_000 - 34_000_000) / 34_000_000) * 100, 2)
    assert ticker.high_24h == 37_000_000
    assert ticker.low_24h == 33_000_000
