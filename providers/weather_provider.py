# tools/weather_tool.py
import datetime
import requests
import openmeteo_requests
from typing import Any, Dict, List, Optional

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# use openmeteo client instead of raw requests, handles response parsing better
_openmeteo = openmeteo_requests.Client()

# WMO weather interpretation codes, full list from open-meteo docs
_WMO_CODES: Dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Heavy freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snowfall", 73: "Moderate snowfall", 75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}

# codes that should produce a warning to user
_WARNING_CODES: Dict[int, str] = {
    65: "Heavy rain warning",
    67: "Heavy freezing rain warning",
    75: "Heavy snowfall warning",
    82: "Violent rain showers warning",
    95: "Thunderstorm warning",
    96: "Thunderstorm and hail warning",
    99: "Thunderstorm and heavy hail warning",
}

# order here is very important, must match Variables(i) index below
_CURRENT_VARS = [
    "temperature_2m",        # 0
    "apparent_temperature",  # 1
    "relative_humidity_2m",  # 2
    "weather_code",          # 3
    "precipitation",         # 4
    "cloud_cover",           # 5
    "wind_speed_10m",        # 6
    "wind_gusts_10m",        # 7
    "is_day",                # 8
]

_DAILY_VARS = [
    "weather_code",                  # 0
    "temperature_2m_max",            # 1
    "temperature_2m_min",            # 2
    "precipitation_sum",             # 3
    "precipitation_probability_max", # 4
    "wind_speed_10m_max",            # 5
    "wind_gusts_10m_max",            # 6
]


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

    results = data.get("results")
    if not results:
        return None

    r = results[0]
    return {"lat": r["latitude"], "lon": r["longitude"]}


def _decode_condition(code: int, is_day: int) -> str:
    # special case - clear sky at night looks different
    if code == 0 and not is_day:
        return "Clear night"
    return _WMO_CODES.get(code, f"Unknown (code {code})")


def _build_warnings(code: int, wind_gusts_kmh: float) -> List[str]:
    warnings = []
    if code in _WARNING_CODES:
        warnings.append(_WARNING_CODES[code])
    if wind_gusts_kmh >= 75:
        warnings.append("Strong wind gusts warning")
    elif wind_gusts_kmh >= 55:
        warnings.append("Elevated wind gusts advisory")
    return warnings


def get_weather(location: str) -> Dict[str, Any]:
    """
    User-friendly weather tool.

    Input:
      - location (city name)

    Output:
      - current conditions with temperature, wind, humidity and more
    """
    location = normalize_location(location)
    coords = _geocode_city(location)
    if not coords:
        raise ValueError(f"Could not resolve location: {location}")

    responses = _openmeteo.weather_api(
        WEATHER_URL,
        params={
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "current": _CURRENT_VARS,
        },
    )
    c = responses[0].Current()

    weather_code = int(c.Variables(3).Value())
    is_day       = int(c.Variables(8).Value())
    wind_gusts   = round(c.Variables(7).Value(), 1)

    return {
        "condition":           _decode_condition(weather_code, is_day),
        "temperature_celsius": round(c.Variables(0).Value(), 1),
        "feels_like_celsius":  round(c.Variables(1).Value(), 1),
        "humidity_pct":        int(c.Variables(2).Value()),
        "precipitation_mm":    round(c.Variables(4).Value(), 1),
        "cloud_cover_pct":     int(c.Variables(5).Value()),
        "windspeed_kmh":       round(c.Variables(6).Value(), 1),
        "wind_gusts_kmh":      wind_gusts,
        "warnings":            _build_warnings(weather_code, wind_gusts),
    }


def get_forecast(location: str, days: int = 7) -> List[Dict[str, Any]]:
    """
    Get daily weather forecast for a city, up to 16 days ahead.

    Input:
      - location (city name)
      - days (1-16, default 7)

    Output:
      - list of daily forecasts with condition, temps, precipitation and warnings
    """
    location = normalize_location(location)
    coords = _geocode_city(location)
    if not coords:
        raise ValueError(f"Could not resolve location: {location}")

    days = max(1, min(days, 16))

    responses = _openmeteo.weather_api(
        WEATHER_URL,
        params={
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "daily": _DAILY_VARS,
            "forecast_days": days,
            "timezone": "auto",
        },
    )
    daily = responses[0].Daily()

    forecast = []
    for i in range(days):
        code   = int(daily.Variables(0).ValuesAsNumpy()[i])
        gusts  = round(float(daily.Variables(6).ValuesAsNumpy()[i]), 1)
        # convert unix timestamp to readable day name
        date   = (
            datetime.date.fromtimestamp(daily.Time()) + datetime.timedelta(days=i)
        ).strftime("%A, %b %d")

        forecast.append({
            "date":                   date,
            "condition":              _WMO_CODES.get(code, f"Unknown (code {code})"),
            "temp_max_celsius":       round(float(daily.Variables(1).ValuesAsNumpy()[i]), 1),
            "temp_min_celsius":       round(float(daily.Variables(2).ValuesAsNumpy()[i]), 1),
            "precipitation_mm":       round(float(daily.Variables(3).ValuesAsNumpy()[i]), 1),
            "precipitation_prob_pct": int(daily.Variables(4).ValuesAsNumpy()[i]),
            "wind_speed_max_kmh":     round(float(daily.Variables(5).ValuesAsNumpy()[i]), 1),
            "wind_gusts_max_kmh":     gusts,
            "warnings":               _build_warnings(code, gusts),
        })

    return forecast


def normalize_location(location: str) -> str:
    """
    Normalize user-friendly location strings for geocoding.
    """
    return location.split(",")[0].strip()
