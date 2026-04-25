# mcp_servers/weather_server.py
# MCP server for weather data, wraps our weather tool functions
# run directly: python mcp_servers/weather_server.py

import json
import os
import sys

# need parent dir in path so we can import from tools/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server.fastmcp import FastMCP
from providers.weather_provider import get_weather as _get_weather, get_forecast as _get_forecast

mcp = FastMCP("weather")


@mcp.tool()
def get_weather(location: str) -> str:
    """
    Get current weather conditions for any city.

    Args:
        location: city name, for example "Paris" or "New York".
                  If not stated in current message, infer from conversation context.

    Returns:
        JSON with condition, temperature, feels-like, humidity,
        precipitation, cloud cover, wind, gusts and any warnings.
    """
    try:
        return json.dumps(_get_weather(location))
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
def get_forecast(location: str, days: int = 7) -> str:
    """
    Get daily weather forecast for any city.

    Use this when user asks about future weather, upcoming week,
    what to wear or pack for a trip, or any multi-day forecast.

    Args:
        location: city name, for example "Paris" or "New York".
                  If not stated in current message, infer from conversation context.
        days: how many days to forecast, between 1 and 16 (default 7)

    Returns:
        JSON array with one entry per day - condition, high/low temps,
        precipitation, probability of rain, wind and warnings.
    """
    try:
        return json.dumps(_get_forecast(location, days))
    except Exception as exc:
        return json.dumps({"error": str(exc)})


if __name__ == "__main__":
    mcp.run(transport="stdio")
