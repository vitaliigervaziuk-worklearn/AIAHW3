# tools/news_tool.py
import feedparser
from typing import Optional, List, Dict
from urllib.parse import urlencode, quote_plus

DEFAULT_COUNTRY = "US"

COUNTRY_CONFIG = {
    "US": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
    "DE": {"hl": "de-DE", "gl": "DE", "ceid": "DE:de"},
    "UK": {"hl": "en-GB", "gl": "GB", "ceid": "GB:en"},
    "CA": {"hl": "en-CA", "gl": "CA", "ceid": "CA:en"},
}


def get_latest_news(
    country: Optional[str],
    query: Optional[str],
    topic: Optional[str],
    limit: int = 5,
) -> List[Dict[str, str]]:
    """
    Google News RSS tool.
    """

    cfg = COUNTRY_CONFIG.get(country, COUNTRY_CONFIG[DEFAULT_COUNTRY])
    base = "https://news.google.com/rss"

    # Build search query (q)
    q_parts = []
    if query:
        q_parts.append(query)
    if topic:
        q_parts.append(topic)

    params = {
        "hl": cfg["hl"],
        "gl": cfg["gl"],
        "ceid": cfg["ceid"],
    }

    if q_parts:
        params["q"] = " ".join(q_parts)

        url = f"{base}/search?{urlencode(params, quote_via=quote_plus)}"
    else:
        # Top headlines feed
        url = f"{base}?{urlencode(params)}"

    feed = feedparser.parse(url)

    return [
        {"title": entry.title, "link": entry.link}
        for entry in feed.entries[:limit]
    ]
