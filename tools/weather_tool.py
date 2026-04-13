# tools/weather_tool.py
import requests
from typing import Dict, Optional

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def _geocode_city(city: str) -> Optional[Dict[str, float]]:
    """
    Get Coordinates by the City name
    """
    resp = requests.get(
        GEOCODE_URL,
        params={"name": city, "count": 1, "language": "en", "format": "json"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    print(">>>>> GEO CODE DATA: ", data)

    results = data.get("results")
    if not results:
        print(">>>>> GEO CODE NO RESULT")
        return None

    r = results[0]
    print(">>>>> GEO CODE FIRST RESULT", r)
    return {"lat": r["latitude"], "lon": r["longitude"]}


def get_weather(location: str) -> Dict[str, float]:
    """
    User-friendly weather tool.

    Input:
      - location (city name)

    Output:
      - temperature, windspeed
    """

    location = normalize_location(location)
    coords = _geocode_city(location)
    if not coords:
        raise ValueError(f"Could not resolve location: {location}")

    resp = requests.get(
        WEATHER_URL,
        params={
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "current": ["temperature_2m", "wind_speed_10m"],
        },
        timeout=10,
    )

    resp.raise_for_status()
    data = resp.json()["current"]
    print(">>>> WEATHER DATA:", data)
    return {
        "temperature_celsius": data["temperature_2m"],
        "windspeed_kmh": data["wind_speed_10m"],
    }


def normalize_location(location: str) -> str:
    """
    Normalize user-friendly location strings for geocoding.
    """
    return location.split(",")[0].strip()
