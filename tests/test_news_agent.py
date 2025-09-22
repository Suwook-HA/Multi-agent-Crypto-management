import asyncio
from datetime import timezone

import httpx

from multi_agent_crypto.agents.news_agent import NewsAgent, NewsSource


def test_parse_rss_handles_invalid_pubdate():
    agent = NewsAgent(
        sources=[NewsSource(name="UnitTest", url="https://example.com/rss")],
        tracked_symbols=["BTC"],
    )
    raw_xml = """<?xml version='1.0' encoding='UTF-8'?>
    <rss version='2.0'>
        <channel>
            <title>Unit Test Feed</title>
            <item>
                <title>BTC rally continues</title>
                <link>https://example.com/articles/btc</link>
                <description>Market observers discuss the latest BTC surge.</description>
                <pubDate>not-a-valid-date</pubDate>
            </item>
        </channel>
    </rss>
    """

    source = agent.sources[0]
    articles = agent._parse_rss(raw_xml, source)

    assert len(articles) == 1
    article = articles[0]
    assert article.title == "BTC rally continues"
    assert article.published_at.tzinfo == timezone.utc


def test_fetch_source_follows_redirect():
    redirect_url = "https://example.com/rss"
    final_url = "https://example.com/rss-final"
    rss_body = """<?xml version='1.0' encoding='UTF-8'?>
    <rss version='2.0'>
        <channel>
            <title>Unit Test Feed</title>
            <item>
                <title>BTC rally continues</title>
                <link>https://example.com/articles/btc</link>
                <description>Market observers discuss the latest BTC surge.</description>
                <pubDate>Wed, 01 May 2024 15:00:00 GMT</pubDate>
            </item>
        </channel>
    </rss>
    """

    agent = NewsAgent(
        sources=[NewsSource(name="UnitTest", url=redirect_url)],
        tracked_symbols=["BTC"],
    )
    source = agent.sources[0]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL(redirect_url):
            return httpx.Response(307, headers={"Location": final_url})
        if request.url == httpx.URL(final_url):
            return httpx.Response(200, text=rss_body)
        raise AssertionError(f"Unexpected URL requested: {request.url}")

    transport = httpx.MockTransport(handler)

    async def run_fetch() -> list:
        async with httpx.AsyncClient(transport=transport) as client:
            return await agent._fetch_source(client, source)

    articles = asyncio.run(run_fetch())

    assert len(articles) == 1
    assert articles[0].title == "BTC rally continues"
