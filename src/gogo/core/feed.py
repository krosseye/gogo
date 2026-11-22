import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import TypedDict

from gogo.core import constants

FEED_URL = "https://godotengine.org/rss.xml"
TIMEOUT = 10
_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S %z"
_NS = {"dc": "http://purl.org/dc/elements/1.1/"}


class RSSArticle(TypedDict):
    title: str
    link: str
    summary: str
    author: str
    date: datetime | None
    image_url: str | None
    category: str | None  # e.g. "Release", "Pre-release", "News", "Showcase"


def fetch() -> list[RSSArticle]:
    """Download and parse the feed.

    Raises:
        OSError: On a network or HTTP error (`urllib.error.URLError` is an `OSError`).
        xml.etree.ElementTree.ParseError: If the feed isn't valid XML.
    """
    request = urllib.request.Request(
        FEED_URL, headers={"User-Agent": f"GoGo/{constants.APP_VERSION}"}
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return parse(response.read())


def parse(xml: bytes) -> list[RSSArticle]:
    if not xml.strip():
        return []
    return [_article(item) for item in ET.fromstring(xml).iter("item")]


def _article(item: ET.Element) -> RSSArticle:
    try:
        date = datetime.strptime(item.findtext("pubDate", ""), _DATE_FORMAT)
    except ValueError:
        date = None
    return {
        "title": item.findtext("title", "No title"),
        "link": item.findtext("link", "https://godotengine.org/blog/"),
        "summary": item.findtext("summary", "No summary available"),
        "author": item.findtext("dc:creator", "Unknown author", _NS),
        "date": date,
        "image_url": item.findtext("image"),
        "category": item.findtext("category"),
    }
