from typing import Optional

ACTIVITY_ITEMS: dict[str, list[dict]] = {

    "cycling": [
        {
            "name": "Cycling jersey",
            "key":  "cycling_jersey",
            "cat":  "activity",
            "must": True,
        },
        {
            "name": "Bib shorts",
            "key":  "bib_shorts",
            "cat":  "activity",
            "must": True,
        },
        {
            "name": "Cycling shoes",
            "key":  "cycling_shoes",
            "cat":  "shoes",
            "must": True,
        },
        {
            "name": "Helmet",
            "key":  "helmet",
            "cat":  "activity",
            "must": True,
        },
        {
            "name": "Cycling gloves",
            "key":  "cycling_gloves",
            "cat":  "activity",
            "must": False,
        },
        {
            "name": "Rain cape",
            "key":  "rain_cape",
            "cat":  "layers",
            "must": False,
            "weather_condition": "rain_prob > 0.4",
        },
        {
            "name": "Sun sleeves",
            "key":  "sun_sleeves",
            "cat":  "activity",
            "must": False,
            "weather_condition": "uv_index >= 6",
        },
    ],

    "hiking": [
        {
            "name": "Trail shoes",
            "key":  "trail_shoes",
            "cat":  "shoes",
            "must": True,
        },
        {
            "name": "Moisture-wicking tee",
            "key":  "wick_tee",
            "cat":  "tops",
            "must": True,
        },
        {
            "name": "Hiking socks x2",
            "key":  "hiking_socks",
            "cat":  "extras",
            "must": True,
        },
        {
            "name": "Trekking poles",
            "key":  "poles",
            "cat":  "activity",
            "must": False,
        },
        {
            "name": "First aid kit",
            "key":  "first_aid",
            "cat":  "extras",
            "must": True,
        },
        {
            "name": "Headlamp",
            "key":  "headlamp",
            "cat":  "extras",
            "must": False,
        },
        {
            "name": "Hydration pack / water bottle",
            "key":  "hydration",
            "cat":  "extras",
            "must": True,
        },
        {
            "name": "Rain jacket",
            "key":  "rain_jacket",
            "cat":  "layers",
            "must": False,
            "weather_condition": "rain_prob > 0.3",
        },
    ],

    "swimming": [
        {
            "name": "Swimwear",
            "key":  "swimwear",
            "cat":  "activity",
            "must": True,
        },
        {
            "name": "Rash vest",
            "key":  "rash_vest",
            "cat":  "activity",
            "must": False,
        },
        {
            "name": "Reef-safe SPF50",
            "key":  "reef_spf",
            "cat":  "extras",
            "must": True,
        },
        {
            "name": "Waterproof bag",
            "key":  "waterproof_bag",
            "cat":  "extras",
            "must": True,
        },
        {
            "name": "Goggles",
            "key":  "goggles",
            "cat":  "activity",
            "must": False,
        },
        {
            "name": "Beach towel",
            "key":  "beach_towel",
            "cat":  "extras",
            "must": True,
        },
        {
            "name": "Flip-flops",
            "key":  "flip_flops",
            "cat":  "shoes",
            "must": True,
        },
    ],

    "running": [
        {
            "name": "Running shoes",
            "key":  "running_shoes",
            "cat":  "shoes",
            "must": True,
        },
        {
            "name": "Technical tee",
            "key":  "tech_tee",
            "cat":  "tops",
            "must": True,
        },
        {
            "name": "Running shorts",
            "key":  "run_shorts",
            "cat":  "bottoms",
            "must": True,
        },
        {
            "name": "Running socks x2",
            "key":  "run_socks",
            "cat":  "extras",
            "must": True,
        },
        {
            "name": "Running cap",
            "key":  "run_cap",
            "cat":  "extras",
            "must": False,
            "weather_condition": "uv_index >= 5",
        },
        {
            "name": "Light rain jacket",
            "key":  "light_rain_jacket",
            "cat":  "layers",
            "must": False,
            "weather_condition": "rain_prob > 0.4",
        },
    ],
}

# Display name overrides for activity-specific item keys
ACTIVITY_ITEM_DISPLAY_NAMES = {
    "cycling_jersey":  "Cycling jersey",
    "bib_shorts":      "Bib shorts",
    "cycling_shoes":   "Cycling shoes",
    "helmet":          "Helmet",
    "cycling_gloves":  "Cycling gloves",
    "rain_cape":       "Rain cape",
    "sun_sleeves":     "Sun sleeves",
    "trail_shoes":     "Trail shoes",
    "wick_tee":        "Moisture-wicking tee",
    "hiking_socks":    "Hiking socks x2",
    "poles":           "Trekking poles",
    "first_aid":       "First aid kit",
    "headlamp":        "Headlamp",
    "hydration":       "Hydration pack / water bottle",
    "rain_jacket":     "Rain jacket",
    "light_rain_jacket":"Light rain jacket",
    "swimwear":        "Swimwear",
    "rash_vest":       "Rash vest",
    "reef_spf":        "Reef-safe SPF50",
    "waterproof_bag":  "Waterproof bag",
    "goggles":         "Goggles",
    "beach_towel":     "Beach towel",
    "flip_flops":      "Flip-flops",
    "running_shoes":   "Running shoes",
    "tech_tee":        "Technical tee",
    "run_shorts":      "Running shorts",
    "run_socks":       "Running socks x2",
    "run_cap":         "Running cap",
}

# Public API

def get_activity_items(
        activities: list[str],
        signal: dict,
) -> list[dict]:
    seen_keys: set[str] = set()
    result: list[dict]  = []

    for activity in activities:
        gear = ACTIVITY_ITEMS.get(activity, [])

        for item in gear:
            # Skip if already added from another activity
            if item["key"] in seen_keys:
                continue

            # Evaluate weather condition filter if present
            condition = item.get("weather_condition")
            if condition and not _eval_condition(condition, signal):
                continue

            seen_keys.add(item["key"])
            result.append({
                "name":            item["name"],
                "key":             item["key"],
                "cat":             item["cat"],
                "must":            item["must"],
                "activity_source": activity,
            })

    return result


def get_activity_display_name(item_key: str) -> Optional[str]:
    return ACTIVITY_ITEM_DISPLAY_NAMES.get(item_key)


def list_supported_activities() -> list[str]:
    return list(ACTIVITY_ITEMS.keys())

# Private helpers

def _eval_condition(condition: str, signal: dict) -> bool:
    try:
        # Restrict eval namespace to signal keys only
        namespace = {k: v for k, v in signal.items() if isinstance(v, (int, float, bool))}
        return bool(eval(condition, {"__builtins__": {}}, namespace))
    except Exception:
        # If evaluation fails for any reason, include the item
        return True