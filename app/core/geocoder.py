import time
import requests
from typing import Optional

# Constants

NOMINATIM_URL         = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

# Required by Nominatim usage policy. Identifies the app and provides contact info for abuse reports.
DEFAULT_USER_AGENT = "Dressed/1.0 (walteniumroy@gmail.com)"

# Timeout in seconds for Nominatim requests.
REQUEST_TIMEOUT = 5

# Coordinate precision - rounded to 2 decimal places. This gives city-level precision (~1km) which is all weather.py needs. Rounding also improves cache hit rates - "Nairobi" and "Nairobi, Kenya" both resolve to the same rounded coordinates.
COORD_PRECISION = 2

# Delay between consecutive Nominatim requests in seconds. Nominatim policy: max 1 request per second. The routes.py caches results so this is rarely hit, but the delay is here as a safety net for any burst of new cities.
REQUEST_DELAY = 1.1

# Custom exception
class GeocoderError(Exception):
    pass


# Result dataclass (plain dict, no dependencies)
def _make_result(lat: float, lng: float, display_name: str, short_name: str = "") -> dict:
    if not short_name:
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

    # Respect Nominatim's 1 req/s rate limit. In production, routes.py checks the cache first so this is only hit for genuinely new city queries.
    if delay:
        time.sleep(REQUEST_DELAY)

    params = {
        "q":              city_string,
        "format":         "json",
        "limit":          1,           # need only the best match
        "addressdetails": 0,           # no detailed address breakdown needed
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
        # Non-2xx response - Nominatim occasionally returns 429 if rate limit is hit. Return None, caller handles it.
        return None
    except Exception:
        # Catch-all for any unexpected exception.geocoder.py must never crash the calling route.
        return None

    try:
        results = response.json()
    except ValueError:
        # Non-JSON response, should not happen but handle defensively.
        return None

    if not results or not isinstance(results, list):
        # Empty result, city not found in Nominatim's database.
        return None

    best = results[0]

    try:
        lat = float(best["lat"])
        lng = float(best["lon"])        # Nominatim uses "lon" not "lng"
        display_name = best.get("display_name", city_string)
    except (KeyError, TypeError, ValueError):
        # Unexpected response structure, return None gracefully.
        return None

    return _make_result(lat, lng, display_name)


def reverse_geocode(
        lat: float,
        lng: float,
        user_agent: str = DEFAULT_USER_AGENT,
        delay: bool = True,
) -> Optional[dict]:
    if delay:
        time.sleep(REQUEST_DELAY)

    params = {
        "lat":            lat,
        "lon":            lng,
        "format":         "json",
        "zoom":           10,    # city-level resolution
        "addressdetails": 1,     # needed to extract city/town/village
    }
    headers = {"User-Agent": user_agent, "Accept": "application/json"}

    try:
        resp = requests.get(
            NOMINATIM_REVERSE_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    if not data or "error" in data:
        # "Unable to geocode" or empty response
        return None

    try:
        r_lat        = float(data["lat"])
        r_lng        = float(data["lon"])
        display_name = data.get("display_name", "")
        address      = data.get("address", {})
        # Prefer city > town > village > county > municipality
        short_name = (
                address.get("city")
                or address.get("town")
                or address.get("village")
                or address.get("municipality")
                or address.get("county")
                or display_name.split(",")[0].strip()
        )
    except (KeyError, TypeError, ValueError):
        return None

    return _make_result(r_lat, r_lng, display_name, short_name=short_name)


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