import time
import logging
import requests
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Constants

NOMINATIM_URL         = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

DEFAULT_USER_AGENT = "Dressed/1.0 (walteniumroy@gmail.com)"
REQUEST_TIMEOUT    = 5
COORD_PRECISION    = 2
REQUEST_DELAY      = 1.1


class GeocoderError(Exception):
    pass


def _make_result(lat: float, lng: float, display_name: str, short_name: str = "") -> dict:
    if not short_name:
        short_name = display_name.split(",")[0].strip() if display_name else ""
    return {
        "lat":          round(lat, COORD_PRECISION),
        "lng":          round(lng, COORD_PRECISION),
        "display_name": display_name,
        "short_name":   short_name,
    }


def _nominatim_geocode(
        city_string: str,
        user_agent: str = DEFAULT_USER_AGENT,
        delay: bool = True,
) -> Optional[dict]:
    """Raw Nominatim lookup, no caching."""
    if delay:
        time.sleep(REQUEST_DELAY)

    params = {
        "q":              city_string,
        "format":         "json",
        "limit":          1,
        "addressdetails": 0,
    }
    headers = {"User-Agent": user_agent, "Accept": "application/json"}

    try:
        response = requests.get(
            NOMINATIM_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.warning("Geocoder timed out for: %s", city_string)
        return None
    except requests.exceptions.ConnectionError:
        logger.warning("Geocoder connection error for: %s", city_string)
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
        lat          = float(best["lat"])
        lng          = float(best["lon"])
        display_name = best.get("display_name", city_string)
    except (KeyError, TypeError, ValueError):
        return None

    return _make_result(lat, lng, display_name)


def geocode(
        city_string: str,
        user_agent: str = DEFAULT_USER_AGENT,
        delay: bool = True,
) -> Optional[dict]:
    """Geocode a city string, using DB cache to avoid repeat Nominatim calls."""
    city_string = city_string.strip()
    if not city_string:
        return None

    key = city_string.lower()

    # 1. Check DB cache
    try:
        from app.models import GeoCache
        from app.extensions import db
        from sqlalchemy.exc import SQLAlchemyError

        cached = GeoCache.query.filter_by(query=key).first()
        if cached and cached.is_fresh():
            return {
                "lat":          cached.lat,
                "lng":          cached.lng,
                "short_name":   cached.short_name,
                "display_name": cached.display_name,
            }
    except Exception:
        pass  # DB unavailable -- fall through to live lookup

    # 2. Live Nominatim lookup
    result = _nominatim_geocode(city_string, user_agent=user_agent, delay=delay)

    # 3. Write to cache
    if result:
        try:
            from app.models import GeoCache
            from app.extensions import db
            from sqlalchemy.exc import SQLAlchemyError

            entry = GeoCache.query.filter_by(query=key).first()
            if entry:
                entry.lat          = result["lat"]
                entry.lng          = result["lng"]
                entry.short_name   = result["short_name"]
                entry.display_name = result["display_name"]
                entry.fetched_at   = datetime.now(timezone.utc)
            else:
                entry = GeoCache(
                    query        = key,
                    lat          = result["lat"],
                    lng          = result["lng"],
                    short_name   = result["short_name"],
                    display_name = result["display_name"],
                )
                db.session.add(entry)
            db.session.commit()
        except Exception as e:
            logger.warning("GeoCache write failed: %s", e)
            try:
                db.session.rollback()
            except Exception:
                pass

    return result


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
        "zoom":           10,
        "addressdetails": 1,
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
        return None

    try:
        r_lat        = float(data["lat"])
        r_lng        = float(data["lon"])
        display_name = data.get("display_name", "")
        address      = data.get("address", {})
        short_name   = (
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