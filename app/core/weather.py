import time
import logging
import requests
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Constants

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Request timeout in seconds
REQUEST_TIMEOUT = 8

# Daily variables to request from Open-Meteo
DAILY_VARIABLES = [
    "temperature_2m_max",           # daily max temp °C
    "temperature_2m_min",           # daily min temp °C
    "apparent_temperature_max",     # feels-like max °C
    "precipitation_probability_max",# rain probability 0–100
    "windspeed_10m_max",            # max wind speed km/h
    "uv_index_max",                 # UV index 0–11+
    "weathercode",                  # WMO weather interpretation code
    "sunrise",                      # ISO 8601 datetime string
    "sunset",                       # ISO 8601 datetime string
]

# Hourly variables that will be used to compute max humidity across the day
HOURLY_VARIABLES = [
    "relativehumidity_2m",
]

# WMO Weather Interpretation Code
WMO_MAP = {
    0:  "clear",
    1:  "mainly_clear",
    2:  "partly_cloudy",
    3:  "overcast",
    45: "fog",
    48: "fog",
    51: "light_drizzle",
    53: "moderate_drizzle",
    55: "heavy_drizzle",
    56: "light_drizzle",
    57: "heavy_drizzle",
    61: "light_rain",
    63: "moderate_rain",
    65: "heavy_rain",
    66: "light_rain",
    67: "heavy_rain",
    71: "light_snow",
    73: "moderate_snow",
    75: "heavy_snow",
    77: "snow_grains",
    80: "rain_showers",
    81: "moderate_rain_showers",
    82: "heavy_rain_showers",
    85: "snow_showers",
    86: "heavy_snow_showers",
    95: "thunderstorm",
    96: "thunderstorm_hail",
    99: "thunderstorm_heavy_hail",
}

# Condition slug → emoji for template use
CONDITION_EMOJI = {
    "clear":                  "☀️",
    "mainly_clear":           "🌤",
    "partly_cloudy":          "⛅",
    "overcast":               "☁️",
    "fog":                    "🌫",
    "light_drizzle":          "🌦",
    "moderate_drizzle":       "🌦",
    "heavy_drizzle":          "🌧",
    "light_rain":             "🌧",
    "moderate_rain":          "🌧",
    "heavy_rain":             "🌧",
    "rain_showers":           "🌦",
    "moderate_rain_showers":  "🌧",
    "heavy_rain_showers":     "🌧",
    "light_snow":             "🌨",
    "moderate_snow":          "❄️",
    "heavy_snow":             "❄️",
    "snow_grains":            "🌨",
    "snow_showers":           "🌨",
    "heavy_snow_showers":     "❄️",
    "thunderstorm":           "⛈",
    "thunderstorm_hail":      "⛈",
    "thunderstorm_heavy_hail":"⛈",
}

# Custom exceptions

class WeatherFetchError(Exception):
    pass

class WeatherRateLimitError(WeatherFetchError):
    """Open-Meteo returned 429 Too Many Requests."""
    pass

# Retry settings for transient 429 errors
_MAX_RETRIES   = 3
_RETRY_DELAYS  = (1, 2, 4)  # seconds between attempts

# Public API
def fetch_forecast(
        lat: float,
        lng: float,
        start_date: date,
        end_date: date,
        timezone: str = "auto",
) -> list[dict]:
    params = _build_params(lat, lng, start_date, end_date, timezone)

    last_exc: Exception = Exception("unknown")
    for attempt in range(_MAX_RETRIES):
        try:
            response = requests.get(
                OPEN_METEO_URL,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            break  # success
        except requests.exceptions.Timeout:
            raise WeatherFetchError(
                f"Open-Meteo request timed out after {REQUEST_TIMEOUT}s "
                f"for ({lat}, {lng}) {start_date}–{end_date}"
            )
        except requests.exceptions.ConnectionError:
            raise WeatherFetchError(
                "Could not connect to Open-Meteo API. Check network connectivity."
            )
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                if attempt < _MAX_RETRIES - 1:
                    delay = _RETRY_DELAYS[attempt]
                    logger.warning(
                        "Open-Meteo rate limited (attempt %d/%d), retrying in %ds",
                        attempt + 1, _MAX_RETRIES, delay,
                        )
                    time.sleep(delay)
                    last_exc = e
                    continue
                raise WeatherRateLimitError(
                    f"Open-Meteo returned HTTP 429: {e}"
                )
            raise WeatherFetchError(
                f"Open-Meteo returned HTTP {response.status_code}: {e}"
            )
    else:
        # All retries exhausted on 429
        raise WeatherRateLimitError(
            f"Open-Meteo rate limited after {_MAX_RETRIES} attempts: {last_exc}"
        )

    try:
        data = response.json()
    except ValueError:
        raise WeatherFetchError("Open-Meteo returned non-JSON response.")

    if "daily" not in data:
        raise WeatherFetchError(
            f"Open-Meteo response missing 'daily' key. "
            f"Response keys: {list(data.keys())}"
        )

    return _normalise(data)


def get_dominant_signal(signals: list[dict]) -> dict:
    if not signals:
        raise ValueError("get_dominant_signal() called with empty signals list.")

    conditions = [s["condition"] for s in signals]
    dominant_condition = max(set(conditions), key=conditions.count)

    return {
        "date":           signals[0]["date"],          # first date of the leg
        "temp_c":         round(
            sum(s["temp_c"] for s in signals) / len(signals), 1
        ),
        "temp_min_c":     min(s["temp_min_c"] for s in signals),
        "feels_like_c":   round(
            sum(s["feels_like_c"] for s in signals) / len(signals), 1
        ),
        "rain_prob":      max(s["rain_prob"] for s in signals),
        "wind_kph":       max(s["wind_kph"] for s in signals),
        "uv_index":       max(s["uv_index"] for s in signals),
        "humidity_pct":   round(
            sum(s["humidity_pct"] for s in signals) / len(signals)
        ),
        "condition":      dominant_condition,
        "condition_emoji":CONDITION_EMOJI.get(dominant_condition, "🌡"),
        "evening_drop_c": max(s["evening_drop_c"] for s in signals),
        "is_rainy_day":   max(s["rain_prob"] for s in signals) > 0.5,
        "altitude_m":     signals[0].get("altitude_m", 0),
        "is_dominant":    True,
    }


def forecast_date_range(start_date: date, end_date: date) -> str:
    return f"{start_date.isoformat()}:{end_date.isoformat()}"


def signals_from_cache(raw_response: dict) -> list[dict]:
    return _normalise(raw_response)


def is_high_altitude(altitude_m: float) -> bool:
    return altitude_m >= 2500

# Private helpers

def _build_params(
        lat: float,
        lng: float,
        start_date: date,
        end_date: date,
        timezone: str,
) -> dict:
    return {
        "latitude":       lat,
        "longitude":      lng,
        "daily":          ",".join(DAILY_VARIABLES),
        "hourly":         ",".join(HOURLY_VARIABLES),
        "start_date":     start_date.isoformat(),
        "end_date":       end_date.isoformat(),
        "timezone":       timezone,
        "windspeed_unit": "kmh",
        "precipitation_unit": "mm",
    }


def _normalise(data: dict) -> list[dict]:
    daily = data["daily"]
    hourly = data.get("hourly", {})
    altitude_m = data.get("elevation", 0) or 0

    required_daily_keys = [
        "time",
        "temperature_2m_max",
        "temperature_2m_min",
        "apparent_temperature_max",
        "precipitation_probability_max",
        "windspeed_10m_max",
        "uv_index_max",
        "weathercode",
    ]

    for key in required_daily_keys:
        if key not in daily:
            raise WeatherFetchError(
                f"Open-Meteo response missing expected daily key: '{key}'. "
                f"Available keys: {list(daily.keys())}"
            )

    # Hourly humidity average per day (returns 24 values per day)
    hourly_humidity = hourly.get("relativehumidity_2m", [])
    n_days = len(daily["time"])
    daily_humidity = []
    for day_idx in range(n_days):
        start = day_idx * 24
        hours = hourly_humidity[start: start + 24]
        avg = round(sum(hours) / len(hours)) if hours else 60  # default 60% if missing
        daily_humidity.append(avg)

    signals = []
    for i, day_str in enumerate(daily["time"]):
        temp_max    = _safe_float(daily["temperature_2m_max"][i], 22.0)
        temp_min    = _safe_float(daily["temperature_2m_min"][i], 15.0)
        feels_like  = _safe_float(daily["apparent_temperature_max"][i], temp_max)
        rain_prob   = _safe_int(daily["precipitation_probability_max"][i], 0) / 100
        wind_kph    = _safe_float(daily["windspeed_10m_max"][i], 0.0)
        uv_index    = _safe_float(daily["uv_index_max"][i], 0.0)
        wmo_code    = _safe_int(daily["weathercode"][i], 0)
        humidity    = daily_humidity[i] if i < len(daily_humidity) else 60
        sunrise     = daily.get("sunrise", [None] * n_days)[i]
        sunset      = daily.get("sunset", [None] * n_days)[i]

        evening_drop = round(temp_max - temp_min, 1)
        condition    = WMO_MAP.get(wmo_code, "partly_cloudy")

        signals.append({
            # Core date
            "date":            day_str,                   # format "2026-07-14"

            # Temperature
            "temp_c":          round(temp_max, 1),        # daily high temp
            "temp_min_c":      round(temp_min, 1),        # daily low temp
            "feels_like_c":    round(feels_like, 1),      # apparent max temp

            # Precipitation
            "rain_prob":       round(rain_prob, 2),       # format 0.0–1.0
            "is_rainy_day":    rain_prob > 0.5,

            # Wind
            "wind_kph":        round(wind_kph, 1),

            # UV
            "uv_index":        round(uv_index, 1),

            # Humidity
            "humidity_pct":    humidity,                  # 0–100

            # Condition
            "condition":       condition,
            "condition_emoji": CONDITION_EMOJI.get(condition, "🌡"),
            "wmo_code":        wmo_code,                  # raw code for reference

            # Derived signals used by advisor.py
            "evening_drop_c":  evening_drop,             # temp swing during day
            "is_high_uv":      uv_index >= 6,
            "is_windy":        wind_kph > 25,
            "is_humid":        humidity > 75,

            # Sunrise / sunset
            "sunrise":         sunrise,
            "sunset":          sunset,

            # Altitude
            "altitude_m":      round(altitude_m),
            "is_high_altitude": is_high_altitude(altitude_m),
        })

    return signals


def _safe_float(value, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default