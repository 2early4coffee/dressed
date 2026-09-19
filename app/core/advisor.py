from typing import Optional
from app.core.activities import get_activity_items
from app.core import sequence

# Default profile

DEFAULT_PROFILE = {
    "temp_sensitivity":   "neutral",
    "wardrobe_pref":      "neutral",
    "style_pref":         "smart_casual",
    "layering_pref":      "minimal",
    "default_trip_mode":  "regular",
    "default_activities": [],
}

# Layer 1 - Temperature tier
SENSITIVITY_OFFSET = {
    "warm":    -2,
    "neutral":  0,
    "cold":    +2,
}

# Temperature tier thresholds in Celsius.
TIER_THRESHOLDS = [
    (28, "hot"),
    (22, "warm"),
    (16, "mild"),
    (10, "cool"),
    (float("-inf"), "cold"),
]

def get_temp_tier(temp_c: float, sensitivity: str = "neutral") -> str:
    offset = SENSITIVITY_OFFSET.get(sensitivity, 0)
    adjusted = temp_c + offset

    for threshold, tier in TIER_THRESHOLDS:
        if adjusted >= threshold:
            return tier

    return "cold"

# Layer 2 - Base outfit matrix
BASE_OUTFITS = {
    #hot weather
    ("hot", "casual",       "neutral"):    ["lightweight_tee",   "shorts",          "sandals"],
    ("hot", "casual",       "menswear"):   ["lightweight_tee",   "chino_shorts",    "loafers"],
    ("hot", "casual",       "womenswear"): ["cotton_top",        "linen_shorts",    "sandals"],
    ("hot", "casual",       "both"):       ["lightweight_tee",   "linen_shorts",    "sandals"],

    ("hot", "smart_casual", "neutral"):    ["linen_shirt",       "chinos",          "clean_sneakers"],
    ("hot", "smart_casual", "menswear"):   ["linen_shirt",       "chinos",          "loafers"],
    ("hot", "smart_casual", "womenswear"): ["blouse",            "linen_trousers",  "sandals"],
    ("hot", "smart_casual", "both"):       ["linen_shirt",       "chinos",          "clean_sneakers"],

    ("hot", "formal",       "neutral"):    ["light_dress_shirt", "linen_trousers",  "loafers"],
    ("hot", "formal",       "menswear"):   ["light_dress_shirt", "linen_trousers",  "loafers"],
    ("hot", "formal",       "womenswear"): ["blouse",            "tailored_trousers","heels"],
    ("hot", "formal",       "both"):       ["light_dress_shirt", "linen_trousers",  "loafers"],

    # warm weather
    ("warm", "casual",       "neutral"):    ["fitted_tee",        "chinos",          "clean_sneakers"],
    ("warm", "casual",       "menswear"):   ["fitted_tee",        "slim_jeans",      "clean_sneakers"],
    ("warm", "casual",       "womenswear"): ["fitted_tee",        "midi_skirt",      "sandals"],
    ("warm", "casual",       "both"):       ["fitted_tee",        "chinos",          "clean_sneakers"],

    ("warm", "smart_casual", "neutral"):    ["cotton_shirt",      "chinos",          "clean_sneakers"],
    ("warm", "smart_casual", "menswear"):   ["cotton_shirt",      "slim_trousers",   "loafers"],
    ("warm", "smart_casual", "womenswear"): ["blouse",            "chinos",          "clean_sneakers"],
    ("warm", "smart_casual", "both"):       ["cotton_shirt",      "chinos",          "loafers"],

    ("warm", "formal",       "neutral"):    ["dress_shirt",       "dress_trousers",  "oxford_shoes"],
    ("warm", "formal",       "menswear"):   ["dress_shirt",       "dress_trousers",  "oxford_shoes"],
    ("warm", "formal",       "womenswear"): ["blouse",            "tailored_trousers","heels"],
    ("warm", "formal",       "both"):       ["dress_shirt",       "dress_trousers",  "oxford_shoes"],

    # mild weather
    ("mild", "casual",       "neutral"):    ["fitted_tee",        "light_overshirt", "slim_jeans",      "trainers"],
    ("mild", "casual",       "menswear"):   ["fitted_tee",        "light_overshirt", "slim_jeans",      "trainers"],
    ("mild", "casual",       "womenswear"): ["fitted_tee",        "cardigan",        "slim_jeans",      "clean_sneakers"],
    ("mild", "casual",       "both"):       ["fitted_tee",        "light_overshirt", "slim_jeans",      "trainers"],

    ("mild", "smart_casual", "neutral"):    ["cotton_shirt",      "chinos",          "clean_sneakers"],
    ("mild", "smart_casual", "menswear"):   ["cotton_shirt",      "chinos",          "loafers"],
    ("mild", "smart_casual", "womenswear"): ["blouse",            "slim_trousers",   "clean_sneakers"],
    ("mild", "smart_casual", "both"):       ["cotton_shirt",      "chinos",          "clean_sneakers"],

    ("mild", "formal",       "neutral"):    ["dress_shirt",       "blazer",          "dress_trousers",  "oxford_shoes"],
    ("mild", "formal",       "menswear"):   ["dress_shirt",       "blazer",          "dress_trousers",  "oxford_shoes"],
    ("mild", "formal",       "womenswear"): ["blouse",            "blazer",          "tailored_trousers","heels"],
    ("mild", "formal",       "both"):       ["dress_shirt",       "blazer",          "dress_trousers",  "oxford_shoes"],

    # cool weather
    ("cool", "casual",       "neutral"):    ["long_sleeve_tee",   "slim_jeans",      "trainers"],
    ("cool", "casual",       "menswear"):   ["long_sleeve_tee",   "slim_jeans",      "trainers"],
    ("cool", "casual",       "womenswear"): ["knit_top",          "slim_jeans",      "ankle_boots"],
    ("cool", "casual",       "both"):       ["long_sleeve_tee",   "slim_jeans",      "trainers"],

    ("cool", "smart_casual", "neutral"):    ["cotton_shirt",      "light_jacket",    "slim_trousers",   "loafers"],
    ("cool", "smart_casual", "menswear"):   ["cotton_shirt",      "light_jacket",    "slim_trousers",   "loafers"],
    ("cool", "smart_casual", "womenswear"): ["blouse",            "cardigan",        "slim_trousers",   "ankle_boots"],
    ("cool", "smart_casual", "both"):       ["cotton_shirt",      "light_jacket",    "slim_trousers",   "loafers"],

    ("cool", "formal",       "neutral"):    ["dress_shirt",       "blazer",          "dress_trousers",  "oxford_shoes"],
    ("cool", "formal",       "menswear"):   ["dress_shirt",       "blazer",          "dress_trousers",  "oxford_shoes"],
    ("cool", "formal",       "womenswear"): ["blouse",            "blazer",          "tailored_trousers","heels"],
    ("cool", "formal",       "both"):       ["dress_shirt",       "blazer",          "dress_trousers",  "oxford_shoes"],

    # cold weather
    ("cold", "casual",       "neutral"):    ["thermal_base",      "knit_sweater",    "slim_jeans",      "boots"],
    ("cold", "casual",       "menswear"):   ["thermal_base",      "knit_sweater",    "slim_jeans",      "boots"],
    ("cold", "casual",       "womenswear"): ["thermal_base",      "knit_sweater",    "slim_jeans",      "ankle_boots"],
    ("cold", "casual",       "both"):       ["thermal_base",      "knit_sweater",    "slim_jeans",      "boots"],

    ("cold", "smart_casual", "neutral"):    ["dress_shirt",       "knit_sweater",    "slim_trousers",   "loafers",   "light_jacket"],
    ("cold", "smart_casual", "menswear"):   ["dress_shirt",       "knit_sweater",    "slim_trousers",   "loafers",   "light_jacket"],
    ("cold", "smart_casual", "womenswear"): ["blouse",            "knit_sweater",    "slim_trousers",   "ankle_boots","light_jacket"],
    ("cold", "smart_casual", "both"):       ["dress_shirt",       "knit_sweater",    "slim_trousers",   "loafers",   "light_jacket"],

    ("cold", "formal",       "neutral"):    ["dress_shirt",       "blazer",          "dress_trousers",  "oxford_shoes","light_jacket"],
    ("cold", "formal",       "menswear"):   ["dress_shirt",       "blazer",          "dress_trousers",  "oxford_shoes","light_jacket"],
    ("cold", "formal",       "womenswear"): ["blouse",            "blazer",          "tailored_trousers","heels",     "light_jacket"],
    ("cold", "formal",       "both"):       ["dress_shirt",       "blazer",          "dress_trousers",  "oxford_shoes","light_jacket"],
}

# Fallback outfit when a specific key is not in BASE_OUTFITS.
FALLBACK_OUTFIT = {
    "hot":  ["lightweight_tee", "shorts",     "sandals"],
    "warm": ["cotton_shirt",    "chinos",     "clean_sneakers"],
    "mild": ["cotton_shirt",    "chinos",     "clean_sneakers"],
    "cool": ["cotton_shirt",    "light_jacket","slim_trousers",  "loafers"],
    "cold": ["knit_sweater",    "slim_jeans", "boots"],
}


def get_base_outfit(tier: str, profile: dict) -> list[str]:
    style        = profile.get("style_pref",   "smart_casual")
    wardrobe     = profile.get("wardrobe_pref", "neutral")
    lookup_key   = (tier, style, wardrobe)

    items = BASE_OUTFITS.get(lookup_key)

    if items is None:
        # neutral wardrobe as first fallback
        items = BASE_OUTFITS.get((tier, style, "neutral"))

    if items is None:
        # full fallback (not anticipated to reach this in normal operation)
        items = FALLBACK_OUTFIT.get(tier, ["lightweight_tee", "chinos", "clean_sneakers"])

    return list(items)

# Item metadata
ITEM_DISPLAY_NAMES = {
    "lightweight_tee":    "Lightweight tee",
    "fitted_tee":         "Fitted tee",
    "long_sleeve_tee":    "Long-sleeve tee",
    "cotton_top":         "Cotton top",
    "knit_top":           "Knit top",
    "thermal_base":       "Thermal base layer",
    "cotton_shirt":       "Cotton shirt",
    "linen_shirt":        "Linen shirt",
    "dress_shirt":        "Dress shirt",
    "light_dress_shirt":  "Light dress shirt",
    "blouse":             "Blouse",
    "shorts":             "Shorts",
    "chino_shorts":       "Chino shorts",
    "linen_shorts":       "Linen shorts",
    "chinos":             "Chinos",
    "slim_jeans":         "Slim jeans",
    "slim_trousers":      "Slim trousers",
    "dress_trousers":     "Dress trousers",
    "linen_trousers":     "Linen trousers",
    "tailored_trousers":  "Tailored trousers",
    "midi_skirt":         "Midi skirt",
    "sandals":            "Sandals",
    "loafers":            "Loafers",
    "clean_sneakers":     "Clean sneakers",
    "trainers":           "Trainers",
    "oxford_shoes":       "Oxford shoes",
    "heels":              "Heels",
    "ankle_boots":        "Ankle boots",
    "boots":              "Boots",
    "light_overshirt":    "Light overshirt",
    "cardigan":           "Cardigan",
    "knit_sweater":       "Knit sweater",
    "blazer":             "Blazer",
    "light_jacket":       "Light jacket",
    # Weather modifiers
    "compact_umbrella":   "Compact umbrella",
    "sunglasses":         "Sunglasses",
    "sunscreen":          "Sunscreen SPF50",
    # Context modifiers
    "lip_balm":           "SPF lip balm",
    "moisturiser":        "Moisturiser",
    # Backpacking substitutions
    "merino_tee":         "Merino wool tee",
    "merino_long_sleeve": "Merino long-sleeve",
    "quick_dry_shorts":   "Quick-dry shorts",
    "quick_dry_trousers": "Quick-dry trousers",
}

# Category assignment for each item_key.
ITEM_CATEGORIES = {
    "lightweight_tee":    "tops",
    "fitted_tee":         "tops",
    "long_sleeve_tee":    "tops",
    "cotton_top":         "tops",
    "knit_top":           "tops",
    "thermal_base":       "tops",
    "cotton_shirt":       "tops",
    "linen_shirt":        "tops",
    "dress_shirt":        "tops",
    "light_dress_shirt":  "tops",
    "blouse":             "tops",
    "merino_tee":         "tops",
    "merino_long_sleeve": "tops",
    "shorts":             "bottoms",
    "chino_shorts":       "bottoms",
    "linen_shorts":       "bottoms",
    "quick_dry_shorts":   "bottoms",
    "chinos":             "bottoms",
    "slim_jeans":         "bottoms",
    "slim_trousers":      "bottoms",
    "dress_trousers":     "bottoms",
    "linen_trousers":     "bottoms",
    "tailored_trousers":  "bottoms",
    "midi_skirt":         "bottoms",
    "quick_dry_trousers": "bottoms",
    "sandals":            "shoes",
    "loafers":            "shoes",
    "clean_sneakers":     "shoes",
    "trainers":           "shoes",
    "oxford_shoes":       "shoes",
    "heels":              "shoes",
    "ankle_boots":        "shoes",
    "boots":              "shoes",
    "light_overshirt":    "layers",
    "cardigan":           "layers",
    "knit_sweater":       "layers",
    "blazer":             "layers",
    "light_jacket":       "layers",
    "compact_umbrella":   "extras",
    "sunglasses":         "extras",
    "sunscreen":          "extras",
    "lip_balm":           "extras",
    "moisturiser":        "extras",
}

# Tables icon class for each item_key.
ITEM_ICONS = {
    "lightweight_tee":    "ti-shirt",
    "fitted_tee":         "ti-shirt",
    "long_sleeve_tee":    "ti-shirt",
    "cotton_top":         "ti-shirt",
    "knit_top":           "ti-shirt",
    "thermal_base":       "ti-shirt-sport",
    "cotton_shirt":       "ti-shirt",
    "linen_shirt":        "ti-shirt",
    "dress_shirt":        "ti-shirt",
    "light_dress_shirt":  "ti-shirt",
    "blouse":             "ti-shirt",
    "merino_tee":         "ti-shirt",
    "merino_long_sleeve": "ti-shirt",
    "shorts":             "ti-layout-bottombar",
    "chino_shorts":       "ti-layout-bottombar",
    "linen_shorts":       "ti-layout-bottombar",
    "quick_dry_shorts":   "ti-layout-bottombar",
    "chinos":             "ti-layout-bottombar",
    "slim_jeans":         "ti-layout-bottombar",
    "slim_trousers":      "ti-layout-bottombar",
    "dress_trousers":     "ti-layout-bottombar",
    "linen_trousers":     "ti-layout-bottombar",
    "tailored_trousers":  "ti-layout-bottombar",
    "midi_skirt":         "ti-layout-bottombar",
    "quick_dry_trousers": "ti-layout-bottombar",
    "sandals":            "ti-shoe",
    "loafers":            "ti-shoe",
    "clean_sneakers":     "ti-shoe",
    "trainers":           "ti-shoe",
    "oxford_shoes":       "ti-shoe",
    "heels":              "ti-shoe",
    "ankle_boots":        "ti-shoe",
    "boots":              "ti-shoe",
    "light_overshirt":    "ti-shirt-sport",
    "cardigan":           "ti-shirt-sport",
    "knit_sweater":       "ti-shirt-sport",
    "blazer":             "ti-shirt-sport",
    "light_jacket":       "ti-jacket",
    "compact_umbrella":   "ti-umbrella",
    "sunglasses":         "ti-sunglasses",
    "sunscreen":          "ti-droplet",
    "lip_balm":           "ti-droplet",
    "moisturiser":        "ti-droplet",
}

# Backpacking substitutions.
BACKPACKING_SUBS = {
    "lightweight_tee":   "merino_tee",
    "fitted_tee":        "merino_tee",
    "cotton_shirt":      "merino_tee",
    "linen_shirt":       "merino_tee",
    "long_sleeve_tee":   "merino_long_sleeve",
    "shorts":            "quick_dry_shorts",
    "chino_shorts":      "quick_dry_shorts",
    "chinos":            "quick_dry_trousers",
    "slim_trousers":     "quick_dry_trousers",
    "linen_trousers":    "quick_dry_trousers",
}


def build_item_dict(
        item_key: str,
        advisor_quantity: int = 1,
        note: str = "",
        must: bool = True,
) -> dict:
    return {
        "item_key":         item_key,
        "item_name":        ITEM_DISPLAY_NAMES.get(item_key, item_key.replace("_", " ").title()),
        "category":         ITEM_CATEGORIES.get(item_key, "extras"),
        "icon":             ITEM_ICONS.get(item_key, "ti-shirt"),
        "advisor_quantity": advisor_quantity,
        "user_quantity":    None,
        "is_checked":       False,
        "is_custom":        False,
        "must":             must,
        "note":             note,
    }

# Layer 3 - Weather modifiers

def apply_weather_modifiers(
        items: list[str],
        signal: dict,
        profile: dict,
) -> tuple[list[str], list[str]]:
    notes = []
    items = list(items)

    # Rain modifier
    if signal.get("rain_prob", 0) > 0.5:
        if "compact_umbrella" not in items:
            items.append("compact_umbrella")
        notes.append(
            f"Rain likely ({int(signal['rain_prob'] * 100)}%) "
            "- pack a compact umbrella before you leave"
        )

    # Wind modifier
    if signal.get("wind_kph", 0) > 25:
        notes.append(
            f"Windy today ({signal['wind_kph']:.0f} km/h) "
            "- consider a windproof outer layer"
        )

    # UV modifier
    if signal.get("uv_index", 0) >= 6:
        if "sunglasses" not in items:
            items.append("sunglasses")
        if "sunscreen" not in items:
            items.append("sunscreen")
        notes.append(
            f"UV index {signal['uv_index']:.0f} "
            "- sunglasses and SPF50 recommended"
        )

    # Evening temperature drop modifier which adds a jacket note if the user is open to layering and there is no jacket already in the outfit.
    evening_drop = signal.get("evening_drop_c", 0)
    has_jacket = any(k in items for k in ("light_jacket", "blazer", "knit_sweater"))

    if (
            evening_drop > 6
            and profile.get("layering_pref") == "yes"
            and not has_jacket
    ):
        items.append("light_jacket")
        notes.append(
            f"Temperature drops {evening_drop:.0f}C by evening "
            "- a light jacket covers you"
        )

    # Humidity modifier - no extra item, just a fabric note
    if signal.get("humidity_pct", 0) > 75:
        notes.append(
            "High humidity today "
            "- favour linen and breathable fabrics"
        )

    return items, notes

# Layer 4 - Context modifiers

def apply_context_modifiers(
        items: list[str],
        context_flags: dict,
        notes: list[str],
) -> tuple[list[str], list[str]]:
    items = list(items)

    # Conservative dress flag removes items that expose skin regardless of weather. takes priority over all weather-driven suggestions.
    if context_flags.get("conservative"):
        removed = {"shorts", "chino_shorts", "linen_shorts", "quick_dry_shorts",
                   "sandals", "sleeveless_top", "midi_skirt"}
        before = len(items)
        items = [i for i in items if i not in removed]
        if len(items) < before:
            notes.append(
                "Conservative dress norms at this destination "
                "- covered legs and shoulders advised"
            )
        # Ensure covered alternatives are present
        if not any(i in items for i in ("chinos", "slim_trousers", "dress_trousers",
                                        "linen_trousers", "tailored_trousers",
                                        "quick_dry_trousers", "slim_jeans")):
            items.append("chinos")

    # High altitude flag which adds protective items for stronger UV and drier air above 2500m.
    if context_flags.get("high_altitude"):
        if "lip_balm" not in items:
            items.append("lip_balm")
        if "moisturiser" not in items:
            items.append("moisturiser")
        if "sunscreen" not in items:
            items.append("sunscreen")
        if "sunglasses" not in items:
            items.append("sunglasses")
        notes.append(
            "High altitude - UV is stronger and air is drier. "
            "SPF lip balm and moisturiser are essential"
        )

    return items, notes

# Layer 5 - Trip-mode modifier

def apply_trip_mode(
        items: list[str],
        trip_mode: str,
        laundry_access: str,
        duration_days: int,
        notes: list[str],
) -> tuple[list[str], list[str]]:
    items = list(items)

    if trip_mode == "backpacking":
        # Substitute standard items for quick-dry / ultralight equivalents
        items = [BACKPACKING_SUBS.get(k, k) for k in items]
        # Remove duplicates that can arise from multiple substitutions
        seen = set()
        items = [x for x in items if not (x in seen or seen.add(x))]
        notes.append(
            "Backpacking mode - quick-dry fabrics recommended. "
            "Merino wool items can be worn multiple days without washing"
        )

    elif trip_mode == "carry_on":
        # Rough item count check - carry-on weight concern a realistic carry-on limit is ~7kg / ~10-12 garment items
        if len(items) > 12:
            notes.append(
                f"Carry-on mode: {len(items)} items listed. "
                "Consider removing optional items to stay within 7kg limit"
            )

    return items, notes

# Quantity scaling

# Laundry access multiplier applied to top and bottom quantities. 'daily':  wash every day, only need 2 of each,  'some':   wash mid-trip, need enough for half the trip 'none':   no laundry, need enough for the full duration
LAUNDRY_MULTIPLIERS = {
    "daily": 0.3,
    "some":  0.5,
    "none":  1.0,
}

# Maximum quantities per category regardless of duration.
MAX_QUANTITIES = {
    "tops":    5,
    "bottoms": 4,
    "layers":  2,
    "shoes":   2,
    "extras":  1,
    "activity":1,
}


def scale_quantity(
        item_key: str,
        base_quantity: int,
        duration_days: int,
        laundry_access: str,
        trip_mode: str,
) -> int:

    import math

    category = ITEM_CATEGORIES.get(item_key, "extras")

    # Single-use items (shoes, extras, layers) stay at quantity 1 unless duration is very long
    if category in ("shoes", "extras", "activity"):
        return base_quantity

    if category == "layers":
        # Layers are not quantity-scaled - 1 jacket is always 1 jacket
        return base_quantity

    # Tops and bottoms scale with duration and laundry
    multiplier = LAUNDRY_MULTIPLIERS.get(laundry_access, 0.5)

    # Backpacking: merino items wear multiple days, so lower multiplier
    if trip_mode == "backpacking" and item_key in ("merino_tee", "merino_long_sleeve"):
        multiplier = multiplier * 0.6

    raw = duration_days * multiplier
    quantity = max(int(math.ceil(raw)), base_quantity)
    max_qty   = MAX_QUANTITIES.get(category, 2)

    return min(quantity, max_qty)

# Conflict resolution

def resolve_conflicts(
        items: list[str],
        context_flags: dict,
        notes: list[str],
) -> tuple[list[str], list[str]]:

    # Deduplicate preserving insertion order
    seen = set()
    deduped = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)

    return deduped, notes



# Public API - daily outfit

def get_outfit(signal: dict, profile: Optional[dict] = None) -> dict:
    if profile is None:
        profile = DEFAULT_PROFILE

    # Layer 1 - temperature tier
    tier = get_temp_tier(signal["temp_c"], profile.get("temp_sensitivity", "neutral"))

    # Layer 2 - base outfit
    item_keys = get_base_outfit(tier, profile)

    # Layer 3 - weather modifiers
    item_keys, notes = apply_weather_modifiers(item_keys, signal, profile)

    # Layer 4 - context modifiers (daily outfit: no context flags)
    item_keys, notes = apply_context_modifiers(item_keys, {}, notes)

    # Layer 5 - trip mode (daily outfit: always regular)
    item_keys, notes = apply_trip_mode(item_keys, "regular", "some", 1, notes)

    # Conflict resolution
    item_keys, notes = resolve_conflicts(item_keys, {}, notes)

    # Build item dicts
    items = [build_item_dict(key) for key in item_keys]

    # Outfit key for static hero image. Format: "{tier}_{style_pref}" -> maps to static/img/outfits/{key}.jpg
    style      = profile.get("style_pref", "smart_casual")
    outfit_key = f"{tier}_{style}"

    # Rainy day override - use the rainy hero image regardless of tier
    if signal.get("rain_prob", 0) > 0.5:
        outfit_key = f"rainy_{style}"

    return {
        "tier":       tier,
        "items":      items,
        "notes":      notes,
        "outfit_key": outfit_key,
        "condition":  signal.get("condition", "partly_cloudy"),
        "emoji":      signal.get("condition_emoji", "🌡"),
        "temp_c":     signal.get("temp_c", 0),
        "feels_like": signal.get("feels_like_c", 0),
        "rain_prob":  signal.get("rain_prob", 0),
        "is_rainy":   signal.get("is_rainy_day", False),
    }

# Public API - trip packing list

def build_packing_list(
        legs: list[dict],
        profile: Optional[dict],
        trip_config: dict,
) -> list[dict]:
    if profile is None:
        profile = DEFAULT_PROFILE

    trip_mode      = trip_config.get("trip_mode",      "regular")
    laundry_access = trip_config.get("laundry_access", "some")
    activities     = trip_config.get("activities",     [])

    # merged: item_key -> {item_dict, dest_legs: set of leg IDs}
    merged: dict[str, dict] = {}

    for leg in legs:
        forecast       = leg.get("forecast", [])
        context_flags  = leg.get("context_flags", {})
        leg_id         = leg.get("id")
        duration_days  = leg.get("duration_days", 1)

        if not forecast:
            continue

        # Get the dominant signal for this leg
        from app.core.weather import get_dominant_signal
        dominant = get_dominant_signal(forecast)

        # Layer 1 - temperature tier
        tier = get_temp_tier(dominant["temp_c"], profile.get("temp_sensitivity", "neutral"))

        # Layer 2 - base outfit
        item_keys = get_base_outfit(tier, profile)

        # Layer 3 - weather modifiers
        item_keys, _ = apply_weather_modifiers(item_keys, dominant, profile)

        # Layer 4 - context modifiers
        item_keys, _ = apply_context_modifiers(item_keys, context_flags, [])

        # Layer 5 - trip-mode modifier
        item_keys, _ = apply_trip_mode(
            item_keys, trip_mode, laundry_access, duration_days, []
        )

        # Conflict resolution
        item_keys, _ = resolve_conflicts(item_keys, context_flags, [])

        # Add activity gear for this leg
        activity_items = get_activity_items(activities, dominant)
        activity_keys  = [i["key"] for i in activity_items]

        # Merge into the combined dict
        for item_key in item_keys + activity_keys:
            if item_key in merged:
                # Item already exists from a previous leg - just add this leg's ID
                merged[item_key]["dest_legs"].add(leg_id)
            else:
                # New item - build the full dict
                qty = scale_quantity(
                    item_key, 1, duration_days, laundry_access, trip_mode
                )
                item = build_item_dict(item_key, advisor_quantity=qty)
                item["dest_legs"] = {leg_id}

                # Attach activity metadata if this is an activity item
                for act_item in activity_items:
                    if act_item["key"] == item_key:
                        item["category"] = act_item.get("cat", "activity")
                        item["must"]     = act_item.get("must", True)
                        break

                merged[item_key] = item

    # Convert dest_legs sets to sorted lists for JSON serialisation
    result = []
    for item in merged.values():
        item["dest_legs"] = sorted(item["dest_legs"])
        result.append(item)

    # Assign packing sequence zones
    result = sequence.assign_sequence(result, trip_config.get("bag_type", "carry_on"), legs)

    return result