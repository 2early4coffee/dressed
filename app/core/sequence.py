# Zone definitions

ZONES: dict[str, list[tuple[str, str]]] = {

    "backpack": [
        ("hip_belt",    "Hip belt pockets -- snacks, sunscreen, lip balm. Accessible mid-hike without stopping."),
        ("top_lid",     "Top lid -- rain cover, docs, emergency items. Fast access without opening the main compartment."),
        ("upper_main",  "Upper main -- tonight's camp items: sleep layer, headlamp. First out at camp."),
        ("mid_main",    "Mid main -- clothing for remaining days."),
        ("lower_main",  "Lower main -- heaviest items closest to your back: sleeping bag, shoes, food. Keeps weight centred."),
        ("back_panel",  "Back panel / hidden pocket -- passport, cash, valuables against your back."),
    ],

    "carry_on_business": [
        ("personal_item", "Personal item (under seat) -- laptop, charger, docs, day-1 outfit. Never goes in the overhead."),
        ("top",           "Top of suitcase -- toiletries clear bag. Security access without unpacking everything."),
        ("middle",        "Middle -- main clothing."),
        ("bottom",        "Bottom -- shoes and heavier items."),
    ],

    "carry_on_multi_city": [
        ("top",    "Top -- leg 1 packing cube. First destination, first out."),
        ("middle", "Middle -- leg 2 packing cube."),
        ("bottom", "Bottom -- leg 3+ packing cube. Last destination, packed deepest."),
    ],

    "carry_on_leisure": [
        ("top",    "Top -- day-1 outfit and toiletries. Accessible right after check-in."),
        ("middle", "Middle -- main clothing."),
        ("bottom", "Bottom -- shoes and heavier items."),
    ],

    "checked": [
        ("cubes", "No strict zone order needed -- use packing cubes sorted by type or by day."),
    ],
}

# Category - zone assignment per bag type.

CATEGORY_ZONE_MAP: dict[str, dict[str, str]] = {

    "backpack": {
        "extras":   "hip_belt",     # sunscreen, lip balm, snacks - hip belt
        "layers":   "upper_main",   # jacket, sweater - upper main (camp)
        "tops":     "mid_main",
        "bottoms":  "mid_main",
        "shoes":    "lower_main",   # shoes are heavy - pack low
        "activity": "mid_main",
    },

    "carry_on_business": {
        "extras":   "personal_item",  # charger, docs - personal item / under seat
        "tops":     "middle",
        "bottoms":  "middle",
        "layers":   "middle",
        "shoes":    "bottom",
        "activity": "middle",
    },

    "carry_on_multi_city": {
        # Zone assigned by dest_leg order, not category. Handled separately in assign_sequence()
        "tops":     "top",
        "bottoms":  "top",
        "layers":   "middle",
        "shoes":    "bottom",
        "extras":   "top",
        "activity": "top",
    },

    "carry_on_leisure": {
        "extras":   "top",
        "layers":   "middle",
        "tops":     "middle",
        "bottoms":  "middle",
        "shoes":    "bottom",
        "activity": "middle",
    },

    "checked": {
        "tops":     "cubes",
        "bottoms":  "cubes",
        "layers":   "cubes",
        "shoes":    "cubes",
        "extras":   "cubes",
        "activity": "cubes",
    },
}

# Special overrides - regardless of category, these items always go in a specific zone for practical reasons.
ITEM_ZONE_OVERRIDES: dict[str, dict[str, str]] = {
    "carry_on_business": {
        "compact_umbrella": "personal_item",  # quick access on arrival
        "sunglasses":       "personal_item",  # worn during travel day
        "lip_balm":         "personal_item",
        "first_aid":        "personal_item",
    },
    "backpack": {
        "compact_umbrella": "top_lid",    # accessible when it starts raining
        "sunscreen":        "hip_belt",   # applied without stopping
        "lip_balm":         "hip_belt",
        "sunglasses":       "hip_belt",
        "first_aid":        "top_lid",
        "headlamp":         "top_lid",    # critical safety item - always accessible
    },
}

# Sort order within each zone - lower number appears first.
ZONE_SORT_ORDER: dict[str, int] = {
    # Backpack zones
    "hip_belt":     0,
    "top_lid":      1,
    "upper_main":   2,
    "mid_main":     3,
    "lower_main":   4,
    "back_panel":   5,
    # Carry-on zones
    "personal_item":0,
    "top":          1,
    "middle":       2,
    "bottom":       3,
    # Checked
    "cubes":        0,
}

# Public API

def assign_sequence(
        items: list[dict],
        bag_type: str,
        legs: list[dict],
) -> list[dict]:
    zone_key    = _resolve_zone_key(bag_type, legs)
    zone_map    = CATEGORY_ZONE_MAP.get(zone_key, CATEGORY_ZONE_MAP["carry_on_leisure"])
    overrides   = ITEM_ZONE_OVERRIDES.get(zone_key, {})

    for item in items:
        item_key = item.get("item_key", "")
        category = item.get("category", "extras")

        # Check for item-specific zone override first
        if item_key in overrides:
            zone = overrides[item_key]
        elif zone_key == "carry_on_multi_city" and item.get("dest_legs"):
            # For multi-city carry-on, zone is determined by earliest leg ie Leg 1 items go on top (pulled out first), last leg items go deepest
            zone = _multi_city_zone(item["dest_legs"], legs)
        else:
            zone = zone_map.get(category, "middle")

        item["zone_label"] = zone
        item["sort_order"] = _compute_sort_order(zone, category, item.get("must", True))

    # Sort the list by sort_order so the packing list renders in logical sequence
    items.sort(key=lambda x: x.get("sort_order", 99))

    return items


def get_zone_description(zone_label: str) -> str:
    for zones in ZONES.values():
        for label, description in zones:
            if label == zone_label:
                return description
    return ""


def get_zone_tip(bag_type: str, legs: list[dict]) -> str:
    zone_key = _resolve_zone_key(bag_type, legs)

    tips = {
        "backpack":           "Pack heaviest items lowest and closest to your spine. Access tonight's items last.",
        "carry_on_business":  "Toiletries and docs stay on top for security. Laptop in your personal item, never in the overhead.",
        "carry_on_multi_city":"Pack one cube per destination. First stop on top -- you will not need the bottom cube until your last leg.",
        "carry_on_leisure":   "Day-1 outfit on top so you can freshen up immediately after check-in.",
        "checked":            "Use packing cubes sorted by type. Shoes in a shoe bag at the bottom -- they are the heaviest items.",
    }

    return tips.get(zone_key, "")

# Private helpers

def _resolve_zone_key(bag_type: str, legs: list[dict]) -> str:
    if bag_type == "backpack":
        return "backpack"

    if bag_type == "checked" or bag_type == "duffel":
        return "checked"

    if bag_type == "carry_on":
        n_legs = len(legs)
        if n_legs > 1:
            return "carry_on_multi_city"
        # Single destination - check purpose
        return "carry_on_leisure"

    # Default - treat anything else as leisure carry-on
    return "carry_on_leisure"


def _multi_city_zone(dest_legs: list[int], all_legs: list[dict]) -> str:
    if not dest_legs or not all_legs:
        return "middle"

    # Find the earliest leg_order among the item's dest_legs
    leg_id_to_order = {leg.get("id"): leg.get("leg_order", 99) for leg in all_legs}
    earliest_order  = min(leg_id_to_order.get(lid, 99) for lid in dest_legs)
    total_legs      = len(all_legs)

    if total_legs <= 1:
        return "top"

    # Divide into thirds: first third > top, last third > bottom, else middle
    position = earliest_order / total_legs
    if position <= 0.33:
        return "top"
    elif position <= 0.66:
        return "middle"
    else:
        return "bottom"


def _compute_sort_order(zone: str, category: str, must: bool) -> int:
    zone_base     = ZONE_SORT_ORDER.get(zone, 5) * 1000
    priority_bump = 0 if must else 500
    category_order = {
        "tops":     0,
        "bottoms":  1,
        "layers":   2,
        "shoes":    3,
        "activity": 4,
        "extras":   5,
    }
    cat_bump = category_order.get(category, 5) * 10

    return zone_base + priority_bump + cat_bump