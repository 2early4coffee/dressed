import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from flask import (
    Blueprint, render_template, request, session,
    redirect, url_for, jsonify, make_response, g,
    current_app, abort,
)
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import (
    User, AnonymousSession, Profile, Trip, TripLeg,
    PackingItem, ForecastCache, Feedback, LoginAttempt,
)
from app.core import packing as packing_ops
from app.core.weather import fetch_forecast, get_dominant_signal, WeatherFetchError, signals_from_cache, forecast_date_range
from app.core.geocoder import geocode, geocode_multiple, build_cache_key, extract_country
from app.core.advisor import get_outfit, build_packing_list, DEFAULT_PROFILE
from app.core.sequence import get_zone_tip

logger = logging.getLogger(__name__)

main = Blueprint("main", __name__)


# Request hooks - session + profile resolution


@main.before_request
def load_current_user_and_session():
    # Resolve the current user and anonymous session before every request.
    g.user_id       = session.get("user_id")
    g.user          = None
    g.session_token = None
    g.anon_session  = None
    g.profile       = None
    g.profile_dict  = dict(DEFAULT_PROFILE)

    if g.user_id:
        g.user = User.query.filter_by(id=g.user_id, deleted_at=None).first()
        if g.user is None:
            # User was deleted - clear the stale session
            session.clear()
            g.user_id = None
        else:
            g.profile = Profile.query.filter_by(user_id=g.user_id).first()
    else:
        # Anonymous user - read cookie
        g.session_token = request.cookies.get("dressed_anon_token")
        if g.session_token:
            g.anon_session = AnonymousSession.query.filter_by(
                token=g.session_token
            ).first()
            if g.anon_session and not g.anon_session.is_expired:
                # Update last_seen
                g.anon_session.last_seen = datetime.now(timezone.utc)
                db.session.commit()
                g.profile = Profile.query.filter_by(
                    session_token=g.session_token
                ).first()
            else:
                # Expired or not found - clear cookie on response
                g.session_token = None
                g.anon_session  = None

    if g.profile:
        g.profile_dict = g.profile.to_dict()


@main.after_request
def set_anon_cookie(response):
    # Set or refresh the anonymous session cookie on every response.
    if g.user_id:
        # Logged-in users don't need the anon cookie
        return response

    if not g.session_token:
        # Create a new anonymous session
        token      = str(uuid.uuid4())
        anon_sess  = AnonymousSession(
            token      = token,
            expires_at = datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.session.add(anon_sess)
        try:
            db.session.commit()
            g.session_token = token
        except SQLAlchemyError:
            db.session.rollback()
            return response

    # Set or refresh the cookie
    is_secure = not current_app.debug
    response.set_cookie(
        "dressed_anon_token",
        value     = g.session_token,
        max_age   = 30 * 24 * 60 * 60,   # 30 days in seconds
        httponly  = True,
        samesite  = "Lax",
        secure    = is_secure,
    )
    return response

# Helpers
def _get_or_create_forecast(city: str, lat: float, lng: float,start_date: str, end_date: str) -> Optional[list]:
    # Fetch a forecast from cache or Open-Meteo.
    from datetime import date as date_type
    date_range_key = forecast_date_range(
        date_type.fromisoformat(start_date),
        date_type.fromisoformat(end_date),
    )
    cache_key = build_cache_key(city)

    # Check cache
    cached = ForecastCache.query.filter_by(
        city=cache_key, date_range=date_range_key
    ).first()

    ttl = current_app.config.get("FORECAST_CACHE_TTL_SECONDS", 3600)

    if cached and cached.is_fresh(ttl):
        return _fetch_signals_from_cache_response(cached.response)

    # Fetch from Open-Meteo
    try:
        start = date_type.fromisoformat(start_date)
        end   = date_type.fromisoformat(end_date)
        signals = fetch_forecast(lat, lng, start, end)
    except WeatherFetchError as e:
        logger.warning("Weather fetch failed for %s: %s", city, e)
        # Serve stale cache if available
        if cached:
            logger.info("Serving stale cache for %s", city)
            return _fetch_signals_from_cache_response(cached.response)
        return None

    # Store in cache
    try:
        if cached:
            cached.response    = signals[0]["__raw"] if signals and "__raw" in signals[0] else {}
            cached.fetched_at  = datetime.now(timezone.utc)
        else:
            new_cache = ForecastCache(
                city       = cache_key,
                lat        = lat,
                lng        = lng,
                date_range = date_range_key,
                response   = {"signals": signals},
            )
            db.session.add(new_cache)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()

    return signals


def _fetch_signals_from_cache_response(response: dict) -> list:
    if "signals" in response:
        return response["signals"]
    return _fetch_signals_from_cache_response(cached.response)


def _get_today_range():
    from datetime import date
    today = date.today()
    end   = today + timedelta(days=5)
    return today.isoformat(), end.isoformat()


def _rate_limited(endpoint: str) -> bool:
    max_requests = current_app.config.get("RATE_LIMIT_REQUESTS", 60)
    window_secs  = current_app.config.get("RATE_LIMIT_WINDOW_SECONDS", 3600)
    cutoff       = datetime.now(timezone.utc) - timedelta(seconds=window_secs)

    # Use login_attempts table as a general request log
    count = LoginAttempt.query.filter(
        LoginAttempt.ip_address == request.remote_addr,
        LoginAttempt.attempted_at >= cutoff,
        LoginAttempt.username == endpoint,
    ).count()

    if count >= max_requests:
        return True

    # Log this request
    attempt = LoginAttempt(
        ip_address   = request.remote_addr,
        username     = endpoint,
        success      = True,
        attempted_at = datetime.now(timezone.utc),
    )
    db.session.add(attempt)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()

    return False

# Page routes
@main.route("/")
def index():
    last_city = request.cookies.get("dressed_last_city", "")
    return render_template(
        "index.html",
        last_city    = last_city,
        profile      = g.profile_dict,
        user         = g.user,
    )


@main.route("/trip", methods=["GET"])
def trip():
    trip_id   = request.args.get("trip_id", type=int)
    saved_trip = None

    if trip_id:
        saved_trip = Trip.query.filter_by(id=trip_id, deleted_at=None).first()
        # Verify ownership before showing
        if saved_trip and not packing_ops.verify_trip_owner(
                trip_id, g.user_id, g.session_token
        ):
            abort(403)

    return render_template(
        "trip.html",
        saved_trip = saved_trip,
        profile    = g.profile_dict,
        user       = g.user,
    )


@main.route("/trip", methods=["POST"])
def trip_create():
    # Parse form
    name            = request.form.get("name", "").strip()[:200] or "My Trip"
    purpose         = request.form.get("purpose",         "leisure")
    trip_mode       = request.form.get("trip_mode",       "regular")
    bag_type        = request.form.get("bag_type",        "carry_on")
    activities_raw  = request.form.get("activities",      "")
    laundry_access  = request.form.get("laundry_access",  "some")
    travelling_with = request.form.get("travelling_with", "solo")

    activities = [a.strip() for a in activities_raw.split(",") if a.strip()]

    # Parse leg data from form fields like legs[0][city], legs[0][start], etc.
    legs_raw = _parse_legs_from_form(request.form)

    if not legs_raw:
        return render_template(
            "trip.html",
            error   = "Please add at least one destination.",
            profile = g.profile_dict,
            user    = g.user,
        )

    # Create Trip
    new_trip = Trip(
        user_id         = g.user_id,
        session_token   = g.session_token if not g.user_id else None,
        name            = name,
        purpose         = purpose,
        trip_mode       = trip_mode,
        bag_type        = bag_type,
        activities      = activities,
        laundry_access  = laundry_access,
        travelling_with = travelling_with,
    )
    db.session.add(new_trip)
    db.session.flush()

    # Geocode + forecast per leg
    leg_instances = []
    leg_dicts     = []

    for order, leg_raw in enumerate(legs_raw, start=1):
        city_str   = leg_raw.get("city", "").strip()
        start_date = leg_raw.get("start", "")
        end_date   = leg_raw.get("end",   "")

        if not city_str or not start_date or not end_date:
            continue

        # Geocode
        geo = geocode(city_str)
        if geo is None:
            db.session.rollback()
            return render_template(
                "trip.html",
                error   = f"Could not find city: {city_str}. Please check the spelling.",
                profile = g.profile_dict,
                user    = g.user,
            )

        # Determine context flags
        from app.core.weather import is_high_altitude
        context_flags = {
            "conservative": leg_raw.get("conservative") == "true",
            "high_altitude": is_high_altitude(0),  # updated after forecast fetch
            "remote": leg_raw.get("remote") == "true",
        }

        # Fetch forecast
        signals = _get_or_create_forecast(
            city       = geo["short_name"],
            lat        = geo["lat"],
            lng        = geo["lng"],
            start_date = start_date,
            end_date   = end_date,
        )

        if signals:
            # Update altitude flag from first signal
            context_flags["high_altitude"] = signals[0].get("is_high_altitude", False)

        # Create TripLeg
        leg = TripLeg(
            trip_id           = new_trip.id,
            leg_order         = order,
            city              = geo["short_name"],
            country           = extract_country(geo["display_name"]),
            lat               = geo["lat"],
            lng               = geo["lng"],
            start_date        = start_date,
            end_date          = end_date,
            forecast_snapshot = {"signals": signals} if signals else None,
            context_flags     = context_flags,
        )
        db.session.add(leg)
        db.session.flush()

        from datetime import date as date_type
        duration = max(
            (date_type.fromisoformat(end_date) - date_type.fromisoformat(start_date)).days,
            1,
        )

        leg_instances.append(leg)
        leg_dicts.append({
            "id":            leg.id,
            "leg_order":     order,
            "city":          geo["short_name"],
            "country":       extract_country(geo["display_name"]),
            "duration_days": duration,
            "forecast":      signals or [],
            "context_flags": context_flags,
        })

    if not leg_dicts:
        db.session.rollback()
        return render_template(
            "trip.html",
            error   = "Could not build the trip. Please check your destinations and dates.",
            profile = g.profile_dict,
            user    = g.user,
        )

    # Build packing list
    trip_config = new_trip.to_config_dict()
    items       = build_packing_list(leg_dicts, g.profile_dict, trip_config)

    # Commit trip + legs
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error("Failed to save trip: %s", e)
        return render_template(
            "trip.html",
            error   = "Something went wrong saving your trip. Please try again.",
            profile = g.profile_dict,
            user    = g.user,
        )

    # Save packing items
    try:
        packing_ops.save_packing_list(new_trip.id, items)
    except SQLAlchemyError as e:
        logger.error("Failed to save packing list: %s", e)
        # Trip is saved - redirect anyway, user sees empty list
        pass

    return redirect(url_for("main.packing_view", trip_id=new_trip.id))


@main.route("/packing/<int:trip_id>")
def packing_view(trip_id: int):
    if not packing_ops.verify_trip_owner(trip_id, g.user_id, g.session_token):
        abort(403)

    trip = Trip.query.filter_by(id=trip_id, deleted_at=None).first_or_404()
    items         = packing_ops.get_packing_list(trip_id)
    counts        = packing_ops.get_counts(trip_id)
    cat_summary   = packing_ops.get_category_summary(trip_id)
    dest_summary  = packing_ops.get_destination_summary(trip_id, trip.legs)
    zone_tip      = get_zone_tip(trip.bag_type, [l.__dict__ for l in trip.legs])

    return render_template(
        "packing.html",
        trip         = trip,
        items        = items,
        counts       = counts,
        cat_summary  = cat_summary,
        dest_summary = dest_summary,
        zone_tip     = zone_tip,
        user         = g.user,
    )


@main.route("/trips")
def trips_list():
    if g.user_id:
        trips = Trip.query.filter_by(
            user_id=g.user_id, deleted_at=None
        ).order_by(Trip.created_at.desc()).all()
    elif g.session_token:
        trips = Trip.query.filter_by(
            session_token=g.session_token, deleted_at=None
        ).order_by(Trip.created_at.desc()).all()
    else:
        trips = []

    return render_template("trips.html", trips=trips, user=g.user)


@main.route("/profile", methods=["GET"])
def profile():
    return render_template("profile.html", profile=g.profile_dict, user=g.user)


@main.route("/profile", methods=["POST"])
def profile_save():
    temp_sensitivity   = request.form.get("temp_sensitivity",   "neutral")
    wardrobe_pref      = request.form.get("wardrobe_pref",      "neutral")
    style_pref         = request.form.get("style_pref",         "smart_casual")
    layering_pref      = request.form.get("layering_pref",      "minimal")
    default_trip_mode  = request.form.get("default_trip_mode",  "regular")
    activities_raw     = request.form.getlist("default_activities")

    allowed = {
        "temp_sensitivity":  {"warm", "neutral", "cold"},
        "wardrobe_pref":     {"menswear", "womenswear", "both", "neutral"},
        "style_pref":        {"casual", "smart_casual", "formal"},
        "layering_pref":     {"minimal", "yes"},
        "default_trip_mode": {"regular", "carry_on", "backpacking"},
    }
    values = {
        "temp_sensitivity":   temp_sensitivity,
        "wardrobe_pref":      wardrobe_pref,
        "style_pref":         style_pref,
        "layering_pref":      layering_pref,
        "default_trip_mode":  default_trip_mode,
    }
    for field, value in values.items():
        if value not in allowed[field]:
            values[field] = DEFAULT_PROFILE[field]

    if g.profile:
        g.profile.temp_sensitivity   = values["temp_sensitivity"]
        g.profile.wardrobe_pref      = values["wardrobe_pref"]
        g.profile.style_pref         = values["style_pref"]
        g.profile.layering_pref      = values["layering_pref"]
        g.profile.default_trip_mode  = values["default_trip_mode"]
        g.profile.default_activities = activities_raw
    else:
        # Create new
        new_profile = Profile(
            user_id            = g.user_id,
            session_token      = g.session_token if not g.user_id else None,
            temp_sensitivity   = values["temp_sensitivity"],
            wardrobe_pref      = values["wardrobe_pref"],
            style_pref         = values["style_pref"],
            layering_pref      = values["layering_pref"],
            default_trip_mode  = values["default_trip_mode"],
            default_activities = activities_raw,
        )
        db.session.add(new_profile)

    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error("Profile save failed: %s", e)
        return render_template(
            "profile.html",
            error   = "Could not save preferences. Please try again.",
            profile = g.profile_dict,
            user    = g.user,
        )

    return redirect(url_for("main.index"))

# API routes - return JSON

@main.route("/api/outfit", methods=["POST"])
def api_outfit():
    if _rate_limited("api_outfit"):
        return jsonify({"error": "Too many requests. Please slow down."}), 429

    data = request.get_json(silent=True) or {}
    lat  = data.get("lat")
    lng  = data.get("lng")
    city = data.get("city", "").strip()

    # Resolve coordinates
    if lat is None or lng is None:
        if not city:
            return jsonify({"error": "Provide lat/lng or city."}), 400
        geo = geocode(city)
        if geo is None:
            return jsonify({"error": f"City not found: {city}"}), 404
        lat, lng = geo["lat"], geo["lng"]
        city     = geo["short_name"]

    # Fetch forecast for today + 1 day
    start_date, end_date = _get_today_range()
    start_date_only = start_date

    signals = _get_or_create_forecast(
        city       = city or f"{lat},{lng}",
        lat        = float(lat),
        lng        = float(lng),
        start_date = start_date_only,
        end_date   = start_date_only,
    )

    if not signals:
        return jsonify({"error": "Could not fetch weather for this location."}), 503

    signal  = signals[0]
    outfit  = get_outfit(signal, g.profile_dict)

    outfit["uv_index"]     = signal.get("uv_index", 0)
    outfit["wind_kph"]     = signal.get("wind_kph", 0)
    outfit["humidity_pct"] = signal.get("humidity_pct", 0)
    outfit["temp_min_c"]   = signal.get("temp_min_c", 0)
    outfit["city_name"]    = city or "Your location"

    # Save last-used city in cookie (set on response)
    response = make_response(jsonify(outfit))
    if city:
        response.set_cookie(
            "dressed_last_city", city,
            max_age=7 * 24 * 60 * 60,
            httponly=False,
            samesite="Lax",
        )
    return response


@main.route("/api/forecast", methods=["GET"])
def api_forecast():
    if _rate_limited("api_forecast"):
        return jsonify({"error": "Too many requests."}), 429

    city = request.args.get("city", "").strip()
    if not city:
        return jsonify({"error": "city parameter required."}), 400

    geo = geocode(city)
    if geo is None:
        return jsonify({"error": f"City not found: {city}"}), 404

    from datetime import date
    today    = date.today()
    end_date = (today + timedelta(days=5)).isoformat()

    signals = _get_or_create_forecast(
        city       = geo["short_name"],
        lat        = geo["lat"],
        lng        = geo["lng"],
        start_date = today.isoformat(),
        end_date   = end_date,
    )

    if not signals:
        return jsonify({"error": "Could not fetch forecast."}), 503

    # Add outfit tier to each signal for the strip UI
    sensitivity = g.profile_dict.get("temp_sensitivity", "neutral")
    from app.core.advisor import get_temp_tier
    for s in signals:
        s["tier"] = get_temp_tier(s["temp_c"], sensitivity)

    return jsonify({"signals": signals, "city": geo["short_name"]})


@main.route("/api/geocode", methods=["POST"])
def api_geocode():
    if _rate_limited("api_geocode"):
        return jsonify({"error": "Too many requests."}), 429

    data = request.get_json(silent=True) or {}
    city = data.get("city", "").strip()

    if not city:
        return jsonify({"error": "city is required."}), 400

    geo = geocode(city)
    if geo is None:
        return jsonify({"error": f"City not found: {city}"}), 404

    return jsonify(geo)


@main.route("/api/packing/check", methods=["POST"])
def api_packing_check():
    data     = request.get_json(silent=True) or {}
    item_id  = data.get("item_id")
    checked  = bool(data.get("checked", False))

    if item_id is None:
        return jsonify({"error": "item_id required."}), 400

    # Get the item to verify trip ownership
    item = PackingItem.query.get(item_id)
    if item is None:
        return jsonify({"error": "Item not found."}), 404

    if not packing_ops.verify_trip_owner(item.trip_id, g.user_id, g.session_token):
        abort(403)

    result = packing_ops.toggle_checked(item_id, item.trip_id, checked)
    if result is None:
        return jsonify({"error": "Item not found."}), 404

    return jsonify(result)


@main.route("/api/packing/quantity", methods=["POST"])
def api_packing_quantity():
    data     = request.get_json(silent=True) or {}
    item_id  = data.get("item_id")
    quantity = data.get("quantity")   # None restores advisor default

    if item_id is None:
        return jsonify({"error": "item_id required."}), 400

    item = PackingItem.query.get(item_id)
    if item is None:
        return jsonify({"error": "Item not found."}), 404

    if not packing_ops.verify_trip_owner(item.trip_id, g.user_id, g.session_token):
        abort(403)

    result = packing_ops.update_quantity(item_id, item.trip_id, quantity)
    if result is None:
        return jsonify({"error": "Item not found."}), 404

    return jsonify(result)


@main.route("/api/packing/reset", methods=["POST"])
def api_packing_reset():
    data     = request.get_json(silent=True) or {}
    trip_id  = data.get("trip_id")
    category = data.get("category", "all")

    if trip_id is None:
        return jsonify({"error": "trip_id required."}), 400

    if not packing_ops.verify_trip_owner(trip_id, g.user_id, g.session_token):
        abort(403)

    result = packing_ops.reset_items(trip_id, category)
    return jsonify(result)


@main.route("/api/packing/add", methods=["POST"])
def api_packing_add():
    data      = request.get_json(silent=True) or {}
    trip_id   = data.get("trip_id")
    item_name = data.get("item_name", "").strip()
    category  = data.get("category", "extras")

    if not trip_id or not item_name:
        return jsonify({"error": "trip_id and item_name required."}), 400

    if not packing_ops.verify_trip_owner(trip_id, g.user_id, g.session_token):
        abort(403)

    item = packing_ops.add_custom_item(trip_id, item_name, category)
    return jsonify(item.to_dict()), 201


@main.route("/api/packing/item/<int:item_id>", methods=["DELETE"])
def api_packing_delete_item(item_id: int):
    item = PackingItem.query.get(item_id)
    if item is None:
        return jsonify({"error": "Item not found."}), 404

    if not packing_ops.verify_trip_owner(item.trip_id, g.user_id, g.session_token):
        abort(403)

    deleted = packing_ops.delete_custom_item(item_id, item.trip_id)
    if not deleted:
        return jsonify({"error": "Only custom items can be deleted."}), 403

    return "", 204


@main.route("/api/trip/add-leg", methods=["POST"])
def api_trip_add_leg():
    data       = request.get_json(silent=True) or {}
    trip_id    = data.get("trip_id")
    city_str   = data.get("city", "").strip()
    start_date = data.get("start_date", "")
    end_date   = data.get("end_date",   "")

    if not trip_id or not city_str or not start_date or not end_date:
        return jsonify({"error": "trip_id, city, start_date, end_date required."}), 400

    if not packing_ops.verify_trip_owner(trip_id, g.user_id, g.session_token):
        abort(403)

    trip = Trip.query.filter_by(id=trip_id, deleted_at=None).first_or_404()

    geo = geocode(city_str)
    if geo is None:
        return jsonify({"error": f"City not found: {city_str}"}), 404

    next_order = len(trip.legs) + 1

    from app.core.weather import is_high_altitude
    signals = _get_or_create_forecast(
        city       = geo["short_name"],
        lat        = geo["lat"],
        lng        = geo["lng"],
        start_date = start_date,
        end_date   = end_date,
    )

    context_flags = {
        "conservative": bool(data.get("conservative", False)),
        "high_altitude": signals[0].get("is_high_altitude", False) if signals else False,
        "remote":        bool(data.get("remote", False)),
    }

    from datetime import date as date_type
    duration = max(
        (date_type.fromisoformat(end_date) - date_type.fromisoformat(start_date)).days, 1
    )

    leg = TripLeg(
        trip_id           = trip_id,
        leg_order         = next_order,
        city              = geo["short_name"],
        country           = extract_country(geo["display_name"]),
        lat               = geo["lat"],
        lng               = geo["lng"],
        start_date        = start_date,
        end_date          = end_date,
        forecast_snapshot = {"signals": signals} if signals else None,
        context_flags     = context_flags,
    )
    db.session.add(leg)

    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Could not add leg."}), 500

    all_legs = []
    for l in trip.legs:
        sigs = _fetch_signals_from_cache_response(l.forecast_snapshot or {})
        dur  = max(
            (date_type.fromisoformat(l.end_date) - date_type.fromisoformat(l.start_date)).days, 1
        )
        all_legs.append({
            "id":            l.id,
            "leg_order":     l.leg_order,
            "city":          l.city,
            "duration_days": dur,
            "forecast":      sigs,
            "context_flags": l.context_flags or {},
        })

    trip_config = trip.to_config_dict()
    items       = build_packing_list(all_legs, g.profile_dict, trip_config)
    packing_ops.save_packing_list(trip_id, items)

    return jsonify({
        "leg":    leg.to_dict(),
        "items":  packing_ops.get_packing_list(trip_id),
        "counts": packing_ops.get_counts(trip_id),
    })


@main.route("/api/feedback", methods=["POST"])
def api_feedback():
    data    = request.get_json(silent=True) or {}
    trip_id = data.get("trip_id")
    rating  = data.get("rating")
    comment = data.get("comment", "")[:500]

    if trip_id is None or rating not in (1, -1):
        return jsonify({"error": "trip_id and rating (1 or -1) required."}), 400

    if not packing_ops.verify_trip_owner(trip_id, g.user_id, g.session_token):
        abort(403)

    feedback = Feedback(
        trip_id       = trip_id,
        user_id       = g.user_id,
        session_token = g.session_token,
        rating        = rating,
        comment       = comment or None,
    )
    db.session.add(feedback)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Could not save feedback."}), 500

    return jsonify({"ok": True})

# Form parsing helper
def _parse_legs_from_form(form) -> list[dict]:
    legs  = {}
    for key, value in form.items():
        if not key.startswith("legs["):
            continue
        # Parse legs[N][field] format
        try:
            bracket   = key.index("]")
            index     = int(key[5:bracket])
            field_raw = key[bracket + 2:-1]
        except (ValueError, IndexError):
            continue

        if index not in legs:
            legs[index] = {}
        legs[index][field_raw] = value

    return [legs[i] for i in sorted(legs.keys())]
