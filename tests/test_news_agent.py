from datetime import timezone

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
