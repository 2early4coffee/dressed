import time
import requests
from typing import Optional

# Constants

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Identifies the app and provides contact info for abuse reports.
DEFAULT_USER_AGENT = "Dressed/1.0 (walteniumroy@gmail.com)"

# Timeout (sec) for Nominatim requests.
REQUEST_TIMEOUT = 5

# round coordinate precision to 2 decimal places.
COORD_PRECISION = 2

# Delay between consecutive Nominatim requests in seconds.
REQUEST_DELAY = 1.1

# Custom exception
class GeocoderError(Exception):
    pass

# Result dataclass in plain dict format, since we want to return a JSON-serializable dict.
def _make_result(lat: float, lng: float, display_name: str) -> dict:
    short_name = display_name.split(",")[0].strip() if display_name else ""
    return {
        "lat":          round(lat, COORD_PRECISION),
        "lng":          round(lng, COORD_PRECISION),
        "display_name": display_name,
        "short_name":   short_name,
    }

# Public API
def geocode(
        city_string: str,
        user_agent: str = DEFAULT_USER_AGENT,
        delay: bool = True,
) -> Optional[dict]:

    city_string = city_string.strip()
    if not city_string:
        return None

    if delay:
        time.sleep(REQUEST_DELAY)

    params = {
        "q":              city_string,
        "format":         "json",
        "limit":          1,
        "addressdetails": 0,
    }

    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }

    try:
        response = requests.get(
            NOMINATIM_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.ConnectionError:
        return None
    except requests.exceptions.HTTPError:
        return None
    except Exception:
        return None

    try:
        results = response.json()
    except ValueError:
        return None

    if not results or not isinstance(results, list):
        return None

    best = results[0]

    try:
        lat = float(best["lat"])
        lng = float(best["lon"])
        display_name = best.get("display_name", city_string)
    except (KeyError, TypeError, ValueError):
        return None

    return _make_result(lat, lng, display_name)


def geocode_multiple(
        city_strings: list[str],
        user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, Optional[dict]]:
    results = {}
    for i, city in enumerate(city_strings):
        result = geocode(city, user_agent=user_agent, delay=(i > 0))
        results[city] = result
    return results


def build_cache_key(city_string: str) -> str:
        return city_string.strip().lower()


def extract_country(display_name: str) -> Optional[str]:
    if not display_name:
        return None
    parts = [p.strip() for p in display_name.split(",")]
    if len(parts) < 2:
        return None
    return parts[-1]