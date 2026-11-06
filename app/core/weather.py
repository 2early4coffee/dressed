import os
import time
import logging
import requests
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

WEATHERAPI_URL  = "https://api.weatherapi.com/v1/forecast.json"
REQUEST_TIMEOUT = 8

# WeatherAPI condition code -> internal slug
WEATHERAPI_CODE_MAP: dict[int, str] = {
    1000: "clear",
    1003: "partly_cloudy",
    1006: "overcast",
    1009: "overcast",
    1030: "fog",
    1135: "fog",
    1147: "fog",
    1063: "rain_showers",
    1066: "light_snow",
    1069: "light_drizzle",
    1072: "light_drizzle",
    1087: "thunderstorm",
    1114: "moderate_snow",
    1117: "heavy_snow",
    1150: "light_drizzle",
    1153: "light_drizzle",
    1168: "light_drizzle",
    1171: "heavy_drizzle",
    1180: "light_rain",
    1183: "light_rain",
    1186: "moderate_rain",
    1189: "moderate_rain",
    1192: "heavy_rain",
    1195: "heavy_rain",
    1198: "light_rain",
    1201: "heavy_rain",
    1204: "light_drizzle",
    1207: "moderate_drizzle",
    1210: "light_snow",
    1213: "light_snow",
    1216: "moderate_snow",
    1219: "moderate_snow",
    1222: "heavy_snow",
    1225: "heavy_snow",
    1237: "snow_grains",
    1240: "rain_showers",
    1243: "moderate_rain_showers",
    1246: "heavy_rain_showers",
    1249: "light_drizzle",
    1252: "moderate_drizzle",
    1255: "snow_showers",
    1258: "heavy_snow_showers",
    1261: "rain_showers",
    1264: "heavy_rain_showers",
    1273: "thunderstorm",
    1276: "thunderstorm",
    1279: "thunderstorm_hail",
    1282: "thunderstorm_heavy_hail",
}

# Condition slug → emoji
CONDITION_EMOJI: dict[str, str] = {
    "clear":                   "☀️",
    "mainly_clear":            "🌤",
    "partly_cloudy":           "⛅",
    "overcast":                "☁️",
    "fog":                     "🌫",
    "light_drizzle":           "🌦",
    "moderate_drizzle":        "🌦",
    "heavy_drizzle":           "🌧",
    "light_rain":              "🌧",
    "moderate_rain":           "🌧",
    "heavy_rain":              "🌧",
    "rain_showers":            "🌦",
    "moderate_rain_showers":   "🌧",
    "heavy_rain_showers":      "🌧",
    "light_snow":              "🌨",
    "moderate_snow":           "❄️",
    "heavy_snow":              "❄️",
    "snow_grains":             "🌨",
    "snow_showers":            "🌨",
    "heavy_snow_showers":      "❄️",
    "thunderstorm":            "⛈",
    "thunderstorm_hail":       "⛈",
    "thunderstorm_heavy_hail": "⛈",
}


# Exceptions

class WeatherFetchError(Exception):
    pass

class WeatherRateLimitError(WeatherFetchError):
    pass


# Retry settings

_MAX_RETRIES  = 3
_RETRY_DELAYS = (1, 2, 4)


# Public API

def fetch_forecast(
        lat: float,
        lng: float,
        start_date: date,
        end_date: date,
        timezone: str = "auto",
) -> list[dict]:
    api_key = os.environ.get("WEATHER_API_KEY", "")
    if not api_key:
        raise WeatherFetchError("WEATHER_API_KEY environment variable is not set.")

    days_needed = (end_date - start_date).days + 1
    days_param  = min(max(days_needed, 1), 14)

    params = {
        "key":    api_key,
        "q":      f"{lat},{lng}",
        "days":   days_param,
        "aqi":    "no",
        "alerts": "no",
    }

    last_exc: Exception = Exception("unknown")
    response = None

    for attempt in range(_MAX_RETRIES):
        try:
            response = requests.get(WEATHERAPI_URL, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            break
        except requests.exceptions.Timeout:
            raise WeatherFetchError(
                f"WeatherAPI request timed out after {REQUEST_TIMEOUT}s "
                f"for ({lat}, {lng}) {start_date}–{end_date}"
            )
        except requests.exceptions.ConnectionError:
            raise WeatherFetchError("Could not connect to WeatherAPI. Check network connectivity.")
        except requests.exceptions.HTTPError as e:
            if response is not None and response.status_code == 429:
                if attempt < _MAX_RETRIES - 1:
                    delay = _RETRY_DELAYS[attempt]
                    logger.warning(
                        "WeatherAPI rate limited (attempt %d/%d), retrying in %ds",
                        attempt + 1, _MAX_RETRIES, delay,
                        )
                    time.sleep(delay)
                    last_exc = e
                    continue
                raise WeatherRateLimitError(f"WeatherAPI returned HTTP 429: {e}")
            raise WeatherFetchError(
                f"WeatherAPI returned HTTP "
                f"{response.status_code if response is not None else '?'}: {e}"
            )
    else:
        raise WeatherRateLimitError(
            f"WeatherAPI rate limited after {_MAX_RETRIES} attempts: {last_exc}"
        )

    try:
        data = response.json()
    except ValueError:
        raise WeatherFetchError("WeatherAPI returned a non-JSON response.")

    if "forecast" not in data or "forecastday" not in data.get("forecast", {}):
        raise WeatherFetchError(
            f"WeatherAPI response missing 'forecast.forecastday'. Keys: {list(data.keys())}"
        )

    return _normalise(data, start_date, end_date)


def get_dominant_signal(signals: list[dict]) -> dict:
    if not signals:
        raise ValueError("get_dominant_signal() called with empty signals list.")

    conditions = [s["condition"] for s in signals]
    dominant_condition = max(set(conditions), key=conditions.count)

    return {
        "date":           signals[0]["date"],
        "temp_c":         round(sum(s["temp_c"] for s in signals) / len(signals), 1),
        "temp_min_c":     min(s["temp_min_c"] for s in signals),
        "feels_like_c":   round(sum(s["feels_like_c"] for s in signals) / len(signals), 1),
        "rain_prob":      max(s["rain_prob"] for s in signals),
        "wind_kph":       max(s["wind_kph"] for s in signals),
        "uv_index":       max(s["uv_index"] for s in signals),
        "humidity_pct":   round(sum(s["humidity_pct"] for s in signals) / len(signals)),
        "condition":      dominant_condition,
        "condition_emoji": CONDITION_EMOJI.get(dominant_condition, "🌡"),
        "evening_drop_c": max(s["evening_drop_c"] for s in signals),
        "is_rainy_day":   max(s["rain_prob"] for s in signals) > 0.5,
        "altitude_m":     signals[0].get("altitude_m", 0),
        "is_dominant":    True,
    }


def forecast_date_range(start_date: date, end_date: date) -> str:
    return f"{start_date.isoformat()}:{end_date.isoformat()}"


def signals_from_cache(raw_response: dict) -> list[dict]:
    if "signals" in raw_response:
        return raw_response["signals"]
    if "forecast" in raw_response:
        return _normalise_forecastdays(raw_response["forecast"]["forecastday"])
    raise ValueError(f"Unrecognised cache format. Keys: {list(raw_response.keys())}")


def is_high_altitude(altitude_m: float) -> bool:
    return altitude_m >= 2500


# Private helpers

def _normalise(data: dict, start_date: date, end_date: date) -> list[dict]:
    forecastdays = data["forecast"]["forecastday"]

    start_str = start_date.isoformat()
    end_str   = end_date.isoformat()
    days_in_range = [fd for fd in forecastdays if start_str <= fd["date"] <= end_str]

    if not days_in_range:
        # WeatherAPI returns dates in the location's local timezone, which can be ahead of UTC (e.g. Japan is UTC+9). Fall back to whatever days the API returned rather than failing entirely.
        logger.warning(
            "WeatherAPI date mismatch: requested %s–%s but got %s. Using available data.",
            start_str, end_str, [fd["date"] for fd in forecastdays],
        )
        days_in_range = forecastdays

    return _normalise_forecastdays(days_in_range)


def _normalise_forecastdays(forecastdays: list[dict]) -> list[dict]:
    signals = []
    for fd in forecastdays:
        day   = fd.get("day", {})
        astro = fd.get("astro", {})
        hour  = fd.get("hour", [])

        temp_max  = _safe_float(day.get("maxtemp_c"), 22.0)
        temp_min  = _safe_float(day.get("mintemp_c"), 15.0)
        wind_kph  = _safe_float(day.get("maxwind_kph"), 0.0)
        humidity  = _safe_int(day.get("avghumidity"), 60)
        uv_index  = _safe_float(day.get("uv"), 0.0)
        rain_prob = _safe_int(day.get("daily_chance_of_rain"), 0) / 100

        # Average hourly feels-like; fall back to max temp if no hourly data
        if hour:
            feels_like = round(
                sum(_safe_float(h.get("feelslike_c"), temp_max) for h in hour) / len(hour), 1
            )
        else:
            feels_like = temp_max

        cond_code = _safe_int(day.get("condition", {}).get("code"), 1003)
        condition = WEATHERAPI_CODE_MAP.get(cond_code, "partly_cloudy")

        evening_drop = round(temp_max - temp_min, 1)

        signals.append({
            "date":             fd["date"],
            "temp_c":           round(temp_max, 1),
            "temp_min_c":       round(temp_min, 1),
            "feels_like_c":     feels_like,
            "rain_prob":        round(rain_prob, 2),
            "is_rainy_day":     rain_prob > 0.5,
            "wind_kph":         round(wind_kph, 1),
            "uv_index":         round(uv_index, 1),
            "humidity_pct":     humidity,
            "condition":        condition,
            "condition_emoji":  CONDITION_EMOJI.get(condition, "🌡"),
            "wmo_code":         cond_code,
            "evening_drop_c":   evening_drop,
            "is_high_uv":       uv_index >= 6,
            "is_windy":         wind_kph > 25,
            "is_humid":         humidity > 75,
            "sunrise":          astro.get("sunrise"),
            "sunset":           astro.get("sunset"),
            "altitude_m":       0,
            "is_high_altitude": False,
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