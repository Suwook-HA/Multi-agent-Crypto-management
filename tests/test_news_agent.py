import asyncio

import httpx

from multi_agent_crypto.agents.news_agent import NewsAgent, NewsSource
from multi_agent_crypto.types import AgentState


RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Bitcoin rally continues as adoption grows</title>
      <link>https://example.com/bitcoin</link>
      <description>BTC pushes higher on renewed interest from institutions.</description>
      <pubDate>Wed, 01 Jan 2020 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_news_agent_follows_redirect(monkeypatch):
    captured_kwargs = {}

    class DummyAsyncClient:
        def __init__(self, *_, **kwargs):
            captured_kwargs.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str):
            request = httpx.Request("GET", url)
            return httpx.Response(200, text=RSS_FEED, request=request)

    monkeypatch.setattr(httpx, "AsyncClient", DummyAsyncClient)

    state = AgentState()
    source = NewsSource(name="TestFeed", url="https://example.com/rss")
    agent = NewsAgent([source], tracked_symbols=["BTC"])

    asyncio.run(agent.run(state))

    assert captured_kwargs.get("follow_redirects") is True
    assert len(state.news) == 1
    article = state.news[0]
    assert article.source == "TestFeed"
    assert article.symbols == ["BTC"]
    assert article.published_at.tzinfo is not None
