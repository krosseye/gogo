from datetime import UTC, datetime

from gogo.core import feed

XML = b"""<?xml version="1.0"?>
<rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
  <item>
    <title>Dev snapshot</title>
    <link>https://godotengine.org/article/dev-snapshot/</link>
    <dc:creator>Someone</dc:creator>
    <pubDate>Mon, 02 Nov 2026 12:00:00 +0000</pubDate>
    <image>https://godotengine.org/a.webp</image>
    <category>Pre-release</category>
  </item>
  <item><pubDate>not a date</pubDate></item>
</channel></rss>"""


def test_parse_reads_items_and_defaults() -> None:
    full, bare = feed.parse(XML)

    assert full["title"] == "Dev snapshot"
    assert full["author"] == "Someone"
    assert full["date"] == datetime(2026, 11, 2, 12, tzinfo=UTC)
    assert full["image_url"] == "https://godotengine.org/a.webp"
    assert full["category"] == "Pre-release"
    assert bare["title"] == "No title"
    assert bare["date"] is None
    assert bare["image_url"] is None
    assert bare["category"] is None


def test_parse_empty_feed() -> None:
    assert feed.parse(b"  ") == []
