import json

from llm.llm_client import LLMClient
from tools.weather_tool import get_weather
from tools.news_tool import get_latest_news
from helper.safe_jason_parser import safe_json_parse


class Orchestrator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def handle(self, user_query: str) -> str:
        intent = self._detect_intent(user_query)

        parts = []

        if intent in ("weather", "both"):
            weather = self._handle_weather(user_query)
            parts.append(weather)

        if intent in ("news", "both"):
            news = self._handle_news(user_query)
            parts.append(news)

        if intent == "none":
            return (
                "I can help with weather or news. "
                "Try: 'weather today' or 'technology news in Germany'."
            )

        return "\n\n".join(parts)
    

    def _detect_intent(self, text: str) -> str:
        system_prompt = """
            You classify user requests.

            Possible intents:
            - weather
            - news
            - both
            - none

            Return ONLY one word.
            """

        result = self.llm.generate(
            prompt=text,
            system_prompt=system_prompt
        ).lower()

        if "both" in result:
            return "both"
        if "weather" in result:
            return "weather"
        if "news" in result:
            return "news"
        return "none"
    

    def _extract_weather_location(self, text: str) -> str:
        system_prompt = """
    Extract the location (city) for a weather request.

    Return JSON ONLY:
    { "location": "City Name" }
    """

        raw = self.llm.generate(prompt=text, system_prompt=system_prompt)
        data = safe_json_parse(raw)

        location = data.get("location")
        if isinstance(location, str) and location.strip():
            return location.strip()

        # fallback to something reasonable
        return "New York"


    def _handle_weather(self, user_query: str) -> str:
        location = self._extract_weather_location(user_query)
        try:
            data = get_weather(location)
        except Exception as e:
            return f"🌦️ Unable to fetch weather for **{location}**."

        return (
            f"**Current Weather in {location}**\n"
            f"- Temperature: {data['temperature_celsius']} °C\n"
            f"- Wind speed: {data['windspeed_kmh']} km/h"
        )

    def _handle_news(self, user_query: str) -> str:
        params = self._extract_news_params(user_query)

        items = get_latest_news(
            country=params["country"],
            query=params.get("query"),
            topic=params.get("topic"),
            limit=params["limit"],
        )

        if not items:
            return (
                f"**News** ({params['query']} in {params['country']})\n"
                "No headlines found."
            )

        headlines = "\n".join(
            f"- [{n['title']}]({n['link']})"
            for n in items
        )

        return (
            f"**News** ({params['query']} in {params['country']})\n"
            f"{headlines}"
        )
    
    def _extract_news_params(self, text: str) -> dict:
        system_prompt = """
    Extract parameters for a news request.

    Rules:
    - query: city, location, or free-text (e.g., Philadelphia, Dallas)
    - topic: optional topic keyword (e.g., medical, health, sports)
    - country: OPTIONAL ISO code ONLY (US, DE, UK, CA)
    - limit: optional integer

    If a field is not present, omit it or set to null.
    Return JSON ONLY.
    """

        raw = self.llm.generate(prompt=text, system_prompt=system_prompt)
        data = safe_json_parse(raw)

        query = data.get("query")
        if isinstance(query, str):
            query = query.strip() or None
        else:
            query = None

        topic = data.get("topic")
        if isinstance(topic, str):
            topic = topic.strip() or None
        else:
            topic = None

        country = data.get("country")
        if isinstance(country, str) and country.upper() in {"US", "UK", "DE", "CA"}:
            country = country.upper()
        else:
            country = "US"   # default region bias only

        limit = data.get("limit", 5)
        try:
            limit = int(limit)
        except Exception:
            limit = 5

        return {
            "country": country,
            "query": query,
            "topic": topic,
            "limit": max(1, min(limit, 20)),
        }