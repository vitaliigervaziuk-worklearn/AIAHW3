# mcp_servers/news_server.py
# MCP server for news headlines using Google News RSS feed
# run directly: python mcp_servers/news_server.py

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server.fastmcp import FastMCP
from providers.news_provider import get_latest_news as _get_latest_news

mcp = FastMCP("news")


@mcp.tool()
def get_news(
    query: str = "",
    country: str = "US",
    topic: str = "",
    limit: int = 5,
) -> str:
    """
    Get latest news headlines from Google News RSS, no API key needed.

    Args:
        query:   search text or location, e.g. "Philadelphia" or "AI technology".
                 leave empty for top headlines.
        country: country code - US, DE, UK or CA (default US)
        topic:   optional topic like "sports", "medical", "business"
        limit:   how many headlines to return, between 1 and 20 (default 5)

    Returns:
        JSON array of objects with title and link fields.
    """
    try:
        items = _get_latest_news(
            country=country or "US",
            query=query or None,
            topic=topic or None,
            limit=max(1, min(int(limit), 20)),
        )
        return json.dumps(items)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


if __name__ == "__main__":
    mcp.run(transport="stdio")
