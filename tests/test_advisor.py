import pytest
from unittest.mock import patch

from app.core.advisor import (
    get_temp_tier,
    get_base_outfit,
    apply_weather_modifiers,
    apply_context_modifiers,
    apply_trip_mode,
    resolve_conflicts,
    scale_quantity,
    build_item_dict,
    get_outfit,
    build_packing_list,
    DEFAULT_PROFILE,
    BASE_OUTFITS,
    ITEM_CATEGORIES,
    ITEM_DISPLAY_NAMES,
    BACKPACKING_SUBS,
)

# Fixtures

@pytest.fixture
def clear_signal():
    # Clear sunny day - 26C, no rain, high UV.
    return {
        "date":           "2026-07-14",
        "temp_c":          26.0,
        "temp_min_c":      16.0,
        "feels_like_c":    25.0,
        "rain_prob":        0.05,
        "wind_kph":        10.0,
        "uv_index":         8.0,
        "humidity_pct":    45,
        "condition":       "clear",
        "condition_emoji": "☀️",
        "evening_drop_c":  10.0,
        "is_rainy_day":    False,
        "is_high_uv":      True,
        "is_windy":        False,
        "is_humid":        False,
        "altitude_m":      1661,
        "is_high_altitude":False,
    }


@pytest.fixture
def rainy_signal():
    # Rainy overcast day - 19C, 80% rain, low UV.
    return {
        "date":           "2026-07-15",
        "temp_c":          19.0,
        "temp_min_c":      13.0,
        "feels_like_c":    17.0,
        "rain_prob":        0.8,
        "wind_kph":        22.0,
        "uv_index":         2.0,
        "humidity_pct":    82,
        "condition":       "moderate_rain",
        "condition_emoji": "🌧",
        "evening_drop_c":   6.0,
        "is_rainy_day":    True,
        "is_high_uv":      False,
        "is_windy":        False,
        "is_humid":        True,
        "altitude_m":      1661,
        "is_high_altitude":False,
    }


@pytest.fixture
def hot_humid_signal():
    # Hot humid coastal day - 32C, Mombasa-style.
    return {
        "date":           "2026-07-16",
        "temp_c":          32.0,
        "temp_min_c":      24.0,
        "feels_like_c":    36.0,
        "rain_prob":        0.2,
        "wind_kph":         8.0,
        "uv_index":        10.0,
        "humidity_pct":    88,
        "condition":       "partly_cloudy",
        "condition_emoji": "⛅",
        "evening_drop_c":   8.0,
        "is_rainy_day":    False,
        "is_high_uv":      True,
        "is_windy":        False,
        "is_humid":        True,
        "altitude_m":       17,
        "is_high_altitude":False,
    }


@pytest.fixture
def cold_signal():
    # Cold evening - 8C, Kampala highlands style.
    return {
        "date":           "2026-07-17",
        "temp_c":           8.0,
        "temp_min_c":       5.0,
        "feels_like_c":     6.0,
        "rain_prob":        0.3,
        "wind_kph":        15.0,
        "uv_index":         3.0,
        "humidity_pct":    65,
        "condition":       "overcast",
        "condition_emoji": "☁️",
        "evening_drop_c":   3.0,
        "is_rainy_day":    False,
        "is_high_uv":      False,
        "is_windy":        False,
        "is_humid":        False,
        "altitude_m":     1200,
        "is_high_altitude":False,
    }


@pytest.fixture
def neutral_profile():
    return {
        "temp_sensitivity":   "neutral",
        "wardrobe_pref":      "neutral",
        "style_pref":         "smart_casual",
        "layering_pref":      "minimal",
        "default_trip_mode":  "regular",
        "default_activities": [],
    }


@pytest.fixture
def warm_profile():
    return {
        "temp_sensitivity":   "warm",
        "wardrobe_pref":      "neutral",
        "style_pref":         "casual",
        "layering_pref":      "minimal",
        "default_trip_mode":  "regular",
        "default_activities": [],
    }


@pytest.fixture
def cold_profile():
    return {
        "temp_sensitivity":   "cold",
        "wardrobe_pref":      "neutral",
        "style_pref":         "smart_casual",
        "layering_pref":      "yes",
        "default_trip_mode":  "regular",
        "default_activities": [],
    }


@pytest.fixture
def womenswear_profile():
    return {
        "temp_sensitivity":   "neutral",
        "wardrobe_pref":      "womenswear",
        "style_pref":         "smart_casual",
        "layering_pref":      "minimal",
        "default_trip_mode":  "regular",
        "default_activities": [],
    }


@pytest.fixture
def layering_profile():
    # Profile that is open to layering - evening drop triggers jacket.
    return {
        "temp_sensitivity":   "neutral",
        "wardrobe_pref":      "neutral",
        "style_pref":         "casual",
        "layering_pref":      "yes",
        "default_trip_mode":  "regular",
        "default_activities": [],
    }

# Layer 1 - Temperature tier

class TestGetTempTier:

    def test_hot_neutral(self):
        assert get_temp_tier(32, "neutral") == "hot"

    def test_warm_neutral(self):
        assert get_temp_tier(24, "neutral") == "warm"

    def test_mild_neutral(self):
        assert get_temp_tier(18, "neutral") == "mild"

    def test_cool_neutral(self):
        assert get_temp_tier(12, "neutral") == "cool"

    def test_cold_neutral(self):
        assert get_temp_tier(7, "neutral") == "cold"

    def test_exactly_at_hot_threshold(self):
        assert get_temp_tier(28, "neutral") == "hot"

    def test_exactly_at_warm_threshold(self):
        assert get_temp_tier(22, "neutral") == "warm"

    def test_exactly_at_mild_threshold(self):
        assert get_temp_tier(16, "neutral") == "mild"

    def test_exactly_at_cool_threshold(self):
        assert get_temp_tier(10, "neutral") == "cool"

    def test_warm_sensitivity_shifts_tier_down(self):
        # 23C with warm sensitivity > adjusted 21C > "warm" not "warm"
        # 23C neutral > "warm", 23C warm_user > 23-2=21 > still "warm"
        # Use a border case: 24C with warm > 22C > "warm"
        assert get_temp_tier(24, "warm") == "warm"

    def test_warm_sensitivity_at_border(self):
        # 24C neutral > "warm". 24C warm_user > 22C > "warm" (at boundary)
        # 23C warm_user > 21C > "mild"
        assert get_temp_tier(23, "warm") == "mild"

    def test_cold_sensitivity_shifts_tier_up(self):
        # 21C cold_user > 23C > "warm"
        assert get_temp_tier(21, "cold") == "warm"

    def test_cold_sensitivity_at_border(self):
        # 20C neutral > "mild". 20C cold_user > 22C > "warm"
        assert get_temp_tier(20, "cold") == "warm"

    def test_very_hot(self):
        assert get_temp_tier(40, "neutral") == "hot"

    def test_freezing(self):
        assert get_temp_tier(-5, "neutral") == "cold"

    def test_unknown_sensitivity_defaults_to_neutral(self):
        # Unknown sensitivity should not crash - offset defaults to 0
        assert get_temp_tier(24, "unknown") == "warm"

    @pytest.mark.parametrize("temp,sensitivity,expected", [
        (32, "neutral", "hot"),
        (32, "warm",    "hot"),
        (32, "cold",    "hot"),
        (28, "warm",    "warm"),   # 28-2=26 > "warm"
        (28, "cold",    "hot"),    # 28+2=30 > "hot"
        (16, "neutral", "mild"),
        (16, "warm",    "cool"),   # 16-2=14 > "cool"
        (16, "cold",    "mild"),   # 16+2=18 > "mild"
        (10, "warm",    "cold"),   # 10-2=8 > "cold"
    ])
    def test_parametrized_tiers(self, temp, sensitivity, expected):
        assert get_temp_tier(temp, sensitivity) == expected


# Layer 2 - Base outfit matrix

class TestGetBaseOutfit:

    def test_returns_list(self, neutral_profile):
        result = get_base_outfit("hot", neutral_profile)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_hot_smart_casual_neutral(self, neutral_profile):
        result = get_base_outfit("hot", neutral_profile)
        assert "linen_shirt" in result
        assert "chinos" in result
        assert "clean_sneakers" in result

    def test_hot_casual_womenswear(self, womenswear_profile):
        womenswear_profile["style_pref"] = "casual"
        result = get_base_outfit("hot", womenswear_profile)
        # Womenswear casual hot should not include chinos
        assert "chinos" not in result

    def test_cold_smart_casual_includes_layer(self, neutral_profile):
        result = get_base_outfit("cold", neutral_profile)
        # Cold weather should include a warm layer
        has_layer = any(k in result for k in ("knit_sweater", "light_jacket", "blazer"))
        assert has_layer

    def test_all_items_have_display_names(self, neutral_profile):
        #Every item key in the matrix must have a display name.
        for key in get_base_outfit("hot", neutral_profile):
            assert key in ITEM_DISPLAY_NAMES or key in ITEM_CATEGORIES, \
                f"Item key '{key}' has no display name or category"

    def test_all_tiers_return_non_empty(self, neutral_profile):
        for tier in ("hot", "warm", "mild", "cool", "cold"):
            result = get_base_outfit(tier, neutral_profile)
            assert len(result) > 0, f"Empty outfit for tier '{tier}'"

    def test_fallback_for_unknown_combination(self):
        #Unknown combination should not raise - returns a fallback.
        profile = {**DEFAULT_PROFILE, "style_pref": "unknown", "wardrobe_pref": "unknown"}
        result = get_base_outfit("hot", profile)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_returns_copy_not_original(self, neutral_profile):
        #Modifying the returned list should not affect BASE_OUTFITS.
        result = get_base_outfit("hot", neutral_profile)
        original_len = len(result)
        result.append("extra_item")
        result2 = get_base_outfit("hot", neutral_profile)
        assert len(result2) == original_len


# Layer 3 - Weather modifiers

class TestApplyWeatherModifiers:

    def test_rain_adds_umbrella(self, rainy_signal, neutral_profile):
        items, notes = apply_weather_modifiers([], rainy_signal, neutral_profile)
        assert "compact_umbrella" in items

    def test_rain_adds_note(self, rainy_signal, neutral_profile):
        _, notes = apply_weather_modifiers([], rainy_signal, neutral_profile)
        assert any("rain" in n.lower() or "umbrella" in n.lower() for n in notes)

    def test_no_rain_no_umbrella(self, clear_signal, neutral_profile):
        items, _ = apply_weather_modifiers([], clear_signal, neutral_profile)
        assert "compact_umbrella" not in items

    def test_rain_not_duplicated(self, rainy_signal, neutral_profile):
        #If umbrella already in list, should not be added twice.
        items, _ = apply_weather_modifiers(
            ["compact_umbrella"], rainy_signal, neutral_profile
        )
        assert items.count("compact_umbrella") == 1

    def test_high_uv_adds_sunglasses(self, clear_signal, neutral_profile):
        items, _ = apply_weather_modifiers([], clear_signal, neutral_profile)
        assert "sunglasses" in items

    def test_high_uv_adds_sunscreen(self, clear_signal, neutral_profile):
        items, _ = apply_weather_modifiers([], clear_signal, neutral_profile)
        assert "sunscreen" in items

    def test_high_uv_adds_note(self, clear_signal, neutral_profile):
        _, notes = apply_weather_modifiers([], clear_signal, neutral_profile)
        assert any("uv" in n.lower() or "spf" in n.lower() for n in notes)

    def test_low_uv_no_sunglasses(self, cold_signal, neutral_profile):
        items, _ = apply_weather_modifiers([], cold_signal, neutral_profile)
        assert "sunglasses" not in items

    def test_evening_drop_with_layering_adds_jacket(self, clear_signal, layering_profile):
        # clear_signal has evening_drop_c = 10 > 6, layering_pref = "yes"
        items, _ = apply_weather_modifiers([], clear_signal, layering_profile)
        assert "light_jacket" in items

    def test_evening_drop_minimal_layering_no_jacket(self, clear_signal, neutral_profile):
        # neutral_profile has layering_pref = "minimal" - no jacket from drop
        items, _ = apply_weather_modifiers([], clear_signal, neutral_profile)
        # Jacket should NOT be added when layering_pref is minimal
        assert "light_jacket" not in items

    def test_no_duplicate_jacket_if_already_present(self, clear_signal, layering_profile):
        items, _ = apply_weather_modifiers(
            ["light_jacket"], clear_signal, layering_profile
        )
        assert items.count("light_jacket") == 1

    def test_high_humidity_adds_note(self, hot_humid_signal, neutral_profile):
        _, notes = apply_weather_modifiers([], hot_humid_signal, neutral_profile)
        assert any("humid" in n.lower() or "linen" in n.lower() or "breathable" in n.lower()
                   for n in notes)

    def test_does_not_mutate_input_list(self, rainy_signal, neutral_profile):
        original = ["fitted_tee", "chinos"]
        apply_weather_modifiers(original, rainy_signal, neutral_profile)
        assert original == ["fitted_tee", "chinos"]

    def test_windy_day_adds_note(self, neutral_profile):
        windy_signal = {
            "rain_prob": 0.1, "wind_kph": 35.0, "uv_index": 4.0,
            "humidity_pct": 50, "evening_drop_c": 3.0,
        }
        _, notes = apply_weather_modifiers([], windy_signal, neutral_profile)
        assert any("wind" in n.lower() for n in notes)

# Layer 4 - Context modifiers

class TestApplyContextModifiers:

    def test_conservative_removes_shorts(self):
        items = ["fitted_tee", "shorts", "clean_sneakers"]
        result, _ = apply_context_modifiers(items, {"conservative": True}, [])
        assert "shorts" not in result

    def test_conservative_removes_sandals(self):
        items = ["linen_shirt", "chinos", "sandals"]
        result, _ = apply_context_modifiers(items, {"conservative": True}, [])
        assert "sandals" not in result

    def test_conservative_adds_note(self):
        items = ["fitted_tee", "shorts"]
        _, notes = apply_context_modifiers(items, {"conservative": True}, [])
        assert any("conservative" in n.lower() or "covered" in n.lower() for n in notes)

    def test_conservative_adds_trousers_if_none(self):
        #If conservative removes all bottoms, chinos should be added.
        items = ["fitted_tee", "shorts"]
        result, _ = apply_context_modifiers(items, {"conservative": True}, [])
        has_trousers = any(k in result for k in (
            "chinos", "slim_trousers", "dress_trousers", "linen_trousers",
            "tailored_trousers", "quick_dry_trousers", "slim_jeans"
        ))
        assert has_trousers

    def test_conservative_keeps_covered_items(self):
        items = ["linen_shirt", "chinos", "loafers"]
        result, _ = apply_context_modifiers(items, {"conservative": True}, [])
        assert "chinos" in result
        assert "linen_shirt" in result
        assert "loafers" in result

    def test_non_conservative_no_changes(self):
        items = ["fitted_tee", "shorts", "sandals"]
        result, notes = apply_context_modifiers(items, {"conservative": False}, [])
        assert result == items
        assert notes == []

    def test_high_altitude_adds_lip_balm(self):
        items = ["fitted_tee", "chinos"]
        result, _ = apply_context_modifiers(items, {"high_altitude": True}, [])
        assert "lip_balm" in result

    def test_high_altitude_adds_moisturiser(self):
        items = ["fitted_tee", "chinos"]
        result, _ = apply_context_modifiers(items, {"high_altitude": True}, [])
        assert "moisturiser" in result

    def test_high_altitude_adds_sunscreen(self):
        items = ["fitted_tee", "chinos"]
        result, _ = apply_context_modifiers(items, {"high_altitude": True}, [])
        assert "sunscreen" in result

    def test_high_altitude_adds_note(self):
        items = ["fitted_tee"]
        _, notes = apply_context_modifiers(items, {"high_altitude": True}, [])
        assert any("altitude" in n.lower() for n in notes)

    def test_high_altitude_no_duplicates(self):
        items = ["fitted_tee", "sunscreen", "lip_balm"]
        result, _ = apply_context_modifiers(items, {"high_altitude": True}, [])
        assert result.count("sunscreen") == 1
        assert result.count("lip_balm") == 1

    def test_empty_flags_no_changes(self):
        items = ["fitted_tee", "shorts"]
        result, notes = apply_context_modifiers(items, {}, [])
        assert result == items
        assert notes == []

    def test_does_not_mutate_input(self):
        original = ["fitted_tee", "shorts", "sandals"]
        apply_context_modifiers(original, {"conservative": True}, [])
        assert original == ["fitted_tee", "shorts", "sandals"]

# Layer 5 - Trip-mode modifier

class TestApplyTripMode:

    def test_backpacking_substitutes_linen_for_merino(self):
        items = ["linen_shirt", "chinos"]
        result, _ = apply_trip_mode(items, "backpacking", "some", 5, [])
        assert "merino_tee" in result
        assert "linen_shirt" not in result

    def test_backpacking_substitutes_shorts_for_quickdry(self):
        items = ["fitted_tee", "shorts"]
        result, _ = apply_trip_mode(items, "backpacking", "some", 5, [])
        assert "quick_dry_shorts" in result
        assert "shorts" not in result

    def test_backpacking_no_duplicates_after_substitution(self):
        items = ["fitted_tee", "lightweight_tee"]  # both map to merino_tee
        result, _ = apply_trip_mode(items, "backpacking", "some", 5, [])
        assert result.count("merino_tee") == 1

    def test_backpacking_adds_note(self):
        items = ["fitted_tee"]
        _, notes = apply_trip_mode(items, "backpacking", "some", 5, [])
        assert any("backpack" in n.lower() or "quick-dry" in n.lower()
                   or "merino" in n.lower() for n in notes)

    def test_regular_mode_no_changes(self):
        items = ["fitted_tee", "chinos", "clean_sneakers"]
        result, notes = apply_trip_mode(items, "regular", "some", 5, [])
        assert result == items
        assert notes == []

    def test_carry_on_large_list_adds_note(self):
        items = ["item"] * 15   # 15 items > 12 threshold
        _, notes = apply_trip_mode(items, "carry_on", "some", 5, [])
        assert any("carry-on" in n.lower() or "7kg" in n.lower() for n in notes)

    def test_carry_on_small_list_no_note(self):
        items = ["fitted_tee", "chinos", "loafers"]
        _, notes = apply_trip_mode(items, "carry_on", "some", 5, [])
        assert not any("carry-on" in n.lower() for n in notes)

    def test_does_not_mutate_input(self):
        original = ["linen_shirt", "chinos"]
        apply_trip_mode(original, "backpacking", "some", 5, [])
        assert original == ["linen_shirt", "chinos"]

# Scale quantity

class TestScaleQuantity:

    def test_shoes_always_quantity_1(self):
        assert scale_quantity("clean_sneakers", 1, 7, "some", "regular") == 1

    def test_extras_always_quantity_1(self):
        assert scale_quantity("compact_umbrella", 1, 7, "none", "regular") == 1

    def test_layers_always_quantity_1(self):
        assert scale_quantity("light_jacket", 1, 7, "none", "regular") == 1

    def test_tops_scale_with_duration_no_laundry(self):
        qty = scale_quantity("fitted_tee", 1, 7, "none", "regular")
        # 7 * 1.0 = 7 > capped at 5
        assert qty == 5

    def test_tops_scale_with_laundry_some(self):
        qty = scale_quantity("fitted_tee", 1, 7, "some", "regular")
        # 7 * 0.5 = 3.5 > ceil = 4
        assert qty == 4

    def test_tops_daily_laundry_minimum(self):
        qty = scale_quantity("fitted_tee", 1, 7, "daily", "regular")
        # 7 * 0.3 = 2.1 > ceil = 3, min 1
        assert qty >= 1
        assert qty <= 3

    def test_minimum_quantity_is_1(self):
        qty = scale_quantity("fitted_tee", 1, 1, "daily", "regular")
        assert qty >= 1

    def test_backpacking_merino_lower_quantity(self):
        regular_qty = scale_quantity("fitted_tee", 1, 7, "some", "regular")
        merino_qty  = scale_quantity("merino_tee",  1, 7, "some", "backpacking")
        assert merino_qty <= regular_qty

# Conflict resolution

class TestResolveConflicts:

    def test_deduplicates_items(self):
        items = ["fitted_tee", "chinos", "fitted_tee", "loafers"]
        result, _ = resolve_conflicts(items, {}, [])
        assert result.count("fitted_tee") == 1

    def test_preserves_order(self):
        items = ["chinos", "fitted_tee", "loafers"]
        result, _ = resolve_conflicts(items, {}, [])
        assert result == ["chinos", "fitted_tee", "loafers"]

    def test_empty_list(self):
        result, _ = resolve_conflicts([], {}, [])
        assert result == []

    def test_no_duplicates_unchanged(self):
        items = ["fitted_tee", "chinos", "loafers"]
        result, _ = resolve_conflicts(items, {}, [])
        assert result == items

# build_item_dict

class TestBuildItemDict:

    def test_returns_dict(self):
        result = build_item_dict("fitted_tee")
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        result = build_item_dict("fitted_tee")
        for key in ("item_key", "item_name", "category", "icon",
                    "advisor_quantity", "user_quantity", "is_checked", "is_custom", "note"):
            assert key in result

    def test_item_name_from_display_names(self):
        result = build_item_dict("fitted_tee")
        assert result["item_name"] == "Fitted tee"

    def test_category_assigned_correctly(self):
        assert build_item_dict("fitted_tee")["category"]     == "tops"
        assert build_item_dict("chinos")["category"]          == "bottoms"
        assert build_item_dict("light_jacket")["category"]    == "layers"
        assert build_item_dict("loafers")["category"]         == "shoes"
        assert build_item_dict("sunglasses")["category"]      == "extras"

    def test_default_quantity_is_1(self):
        result = build_item_dict("fitted_tee")
        assert result["advisor_quantity"] == 1

    def test_custom_quantity(self):
        result = build_item_dict("fitted_tee", advisor_quantity=3)
        assert result["advisor_quantity"] == 3

    def test_user_quantity_is_none(self):
        result = build_item_dict("fitted_tee")
        assert result["user_quantity"] is None

    def test_is_checked_false(self):
        result = build_item_dict("fitted_tee")
        assert result["is_checked"] is False

    def test_is_custom_false(self):
        result = build_item_dict("fitted_tee")
        assert result["is_custom"] is False

    def test_unknown_key_uses_slug_as_name(self):
        result = build_item_dict("some_unknown_item")
        assert result["item_name"] == "Some Unknown Item"


# get_outfit -- combined entry point
class TestGetOutfit:

    def test_returns_dict(self, clear_signal, neutral_profile):
        result = get_outfit(clear_signal, neutral_profile)
        assert isinstance(result, dict)

    def test_has_required_keys(self, clear_signal, neutral_profile):
        result = get_outfit(clear_signal, neutral_profile)
        for key in ("tier", "items", "notes", "outfit_key", "condition",
                    "emoji", "temp_c", "rain_prob"):
            assert key in result

    def test_items_is_list_of_dicts(self, clear_signal, neutral_profile):
        result = get_outfit(clear_signal, neutral_profile)
        assert isinstance(result["items"], list)
        assert len(result["items"]) > 0
        for item in result["items"]:
            assert isinstance(item, dict)
            assert "item_key" in item

    def test_tier_correct_for_clear_signal(self, clear_signal, neutral_profile):
        # 26C neutral > "warm"
        result = get_outfit(clear_signal, neutral_profile)
        assert result["tier"] == "warm"

    def test_outfit_key_format(self, clear_signal, neutral_profile):
        result = get_outfit(clear_signal, neutral_profile)
        # outfit_key will be "tier_style"
        assert "_" in result["outfit_key"]

    def test_rainy_day_uses_rainy_outfit_key(self, rainy_signal, neutral_profile):
        result = get_outfit(rainy_signal, neutral_profile)
        assert "rainy" in result["outfit_key"]

    def test_uses_default_profile_if_none(self, clear_signal):
        result = get_outfit(clear_signal, None)
        assert result is not None
        assert len(result["items"]) > 0

    def test_warm_sensitivity_changes_tier(self, neutral_profile):
        # 23C with warm sensitivity > tier should be "mild" not "warm"
        signal = {"temp_c": 23.0, "temp_min_c": 15.0, "feels_like_c": 22.0,
                  "rain_prob": 0.1, "wind_kph": 10.0, "uv_index": 4.0,
                  "humidity_pct": 50, "evening_drop_c": 8.0,
                  "condition": "partly_cloudy", "condition_emoji": "⛅",
                  "is_rainy_day": False, "is_high_uv": False, "is_windy": False,
                  "is_humid": False, "altitude_m": 0, "is_high_altitude": False}
        warm_p = {**neutral_profile, "temp_sensitivity": "warm"}
        result = get_outfit(signal, warm_p)
        assert result["tier"] == "mild"

    def test_cold_sensitivity_changes_tier(self, neutral_profile):
        # 20C cold sensitivity > 22C > "warm"
        signal = {"temp_c": 20.0, "temp_min_c": 14.0, "feels_like_c": 19.0,
                  "rain_prob": 0.1, "wind_kph": 10.0, "uv_index": 4.0,
                  "humidity_pct": 55, "evening_drop_c": 6.0,
                  "condition": "partly_cloudy", "condition_emoji": "⛅",
                  "is_rainy_day": False, "is_high_uv": False, "is_windy": False,
                  "is_humid": False, "altitude_m": 0, "is_high_altitude": False}
        cold_p = {**neutral_profile, "temp_sensitivity": "cold"}
        result = get_outfit(signal, cold_p)
        assert result["tier"] == "warm"

    def test_rain_note_present_on_rainy_day(self, rainy_signal, neutral_profile):
        result = get_outfit(rainy_signal, neutral_profile)
        assert any("rain" in n.lower() for n in result["notes"])

    def test_uv_note_on_sunny_day(self, clear_signal, neutral_profile):
        result = get_outfit(clear_signal, neutral_profile)
        assert any("uv" in n.lower() or "spf" in n.lower() for n in result["notes"])

    def test_temp_c_in_result(self, clear_signal, neutral_profile):
        result = get_outfit(clear_signal, neutral_profile)
        assert result["temp_c"] == 26.0

    def test_all_items_have_category(self, clear_signal, neutral_profile):
        result = get_outfit(clear_signal, neutral_profile)
        for item in result["items"]:
            assert item["category"] in ("tops", "bottoms", "layers", "shoes", "extras", "activity")

    def test_womenswear_profile(self, hot_humid_signal, womenswear_profile):
        result = get_outfit(hot_humid_signal, womenswear_profile)
        # Womenswear hot smart_casual should include blouse
        item_keys = [i["item_key"] for i in result["items"]]
        assert "blouse" in item_keys or "cotton_top" in item_keys

# build_packing_list - integration test

class TestBuildPackingList:

    def _make_leg(self, leg_id, city, signals, context_flags=None, duration=3):
        return {
            "id":            leg_id,
            "leg_order":     leg_id,
            "city":          city,
            "duration_days": duration,
            "forecast":      signals,
            "context_flags": context_flags or {},
        }

    def test_single_leg_returns_list(self, clear_signal, neutral_profile):
        legs = [self._make_leg(1, "Nairobi", [clear_signal])]
        config = {
            "trip_mode": "regular", "bag_type": "carry_on",
            "activities": [], "laundry_access": "some",
            "travelling_with": "solo", "purpose": "leisure",
        }
        result = build_packing_list(legs, neutral_profile, config)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_all_items_have_required_keys(self, clear_signal, neutral_profile):
        legs = [self._make_leg(1, "Nairobi", [clear_signal])]
        config = {
            "trip_mode": "regular", "bag_type": "carry_on",
            "activities": [], "laundry_access": "some",
            "travelling_with": "solo", "purpose": "leisure",
        }
        result = build_packing_list(legs, neutral_profile, config)
        for item in result:
            assert "item_key"         in item
            assert "item_name"        in item
            assert "category"         in item
            assert "advisor_quantity" in item
            assert "dest_legs"        in item
            assert "sort_order"       in item

    def test_multi_leg_merges_common_items(self, clear_signal, cold_signal, neutral_profile):
        #Items needed in multiple legs should appear once with multiple dest_legs.
        legs = [
            self._make_leg(1, "Mombasa", [clear_signal]),
            self._make_leg(2, "Kampala", [cold_signal]),
        ]
        config = {
            "trip_mode": "regular", "bag_type": "carry_on",
            "activities": [], "laundry_access": "some",
            "travelling_with": "solo", "purpose": "leisure",
        }
        result = build_packing_list(legs, neutral_profile, config)

        # No item_key should appear more than once
        keys = [item["item_key"] for item in result]
        assert len(keys) == len(set(keys)), "Duplicate item keys found in merged list"

    def test_multi_leg_dest_legs_tagged(self, clear_signal, neutral_profile):
        #An item needed in both legs should have both leg IDs in dest_legs.
        legs = [
            self._make_leg(1, "Nairobi", [clear_signal]),
            self._make_leg(2, "Mombasa", [clear_signal]),
        ]
        config = {
            "trip_mode": "regular", "bag_type": "carry_on",
            "activities": [], "laundry_access": "some",
            "travelling_with": "solo", "purpose": "leisure",
        }
        result = build_packing_list(legs, neutral_profile, config)

        # Check that at least one item has both leg IDs
        multi_leg_items = [i for i in result if len(i["dest_legs"]) > 1]
        assert len(multi_leg_items) > 0, "Expected some items to span multiple legs"

    def test_conservative_leg_removes_shorts(self, hot_humid_signal, neutral_profile):
        #Conservative context flag should remove shorts from that leg.
        legs = [self._make_leg(1, "Mombasa", [hot_humid_signal],
                               context_flags={"conservative": True})]
        config = {
            "trip_mode": "regular", "bag_type": "carry_on",
            "activities": [], "laundry_access": "some",
            "travelling_with": "solo", "purpose": "leisure",
        }
        result = build_packing_list(legs, neutral_profile, config)
        keys = [item["item_key"] for item in result]
        assert "shorts" not in keys
        assert "linen_shorts" not in keys
        assert "chino_shorts" not in keys

    def test_backpacking_mode_uses_merino(self, clear_signal, neutral_profile):
        legs = [self._make_leg(1, "Nairobi", [clear_signal])]
        config = {
            "trip_mode": "backpacking", "bag_type": "backpack",
            "activities": [], "laundry_access": "none",
            "travelling_with": "solo", "purpose": "leisure",
        }
        result = build_packing_list(legs, neutral_profile, config)
        keys = [item["item_key"] for item in result]
        # Backpacking substitutions should apply
        assert "linen_shirt" not in keys or "merino_tee" in keys

    def test_activity_items_included(self, clear_signal, neutral_profile):
        legs = [self._make_leg(1, "Mombasa", [clear_signal])]
        config = {
            "trip_mode": "regular", "bag_type": "carry_on",
            "activities": ["cycling"], "laundry_access": "some",
            "travelling_with": "solo", "purpose": "leisure",
        }
        result = build_packing_list(legs, neutral_profile, config)
        keys = [item["item_key"] for item in result]
        assert "helmet" in keys
        assert "cycling_jersey" in keys

    def test_empty_legs_returns_empty_list(self, neutral_profile):
        config = {
            "trip_mode": "regular", "bag_type": "carry_on",
            "activities": [], "laundry_access": "some",
            "travelling_with": "solo", "purpose": "leisure",
        }
        result = build_packing_list([], neutral_profile, config)
        assert result == []

    def test_leg_with_empty_forecast_skipped(self, neutral_profile):
        #Legs with no forecast data should be skipped gracefully.
        legs = [{"id": 1, "leg_order": 1, "city": "Unknown",
                 "duration_days": 3, "forecast": [], "context_flags": {}}]
        config = {
            "trip_mode": "regular", "bag_type": "carry_on",
            "activities": [], "laundry_access": "some",
            "travelling_with": "solo", "purpose": "leisure",
        }
        result = build_packing_list(legs, neutral_profile, config)
        assert result == []

    def test_uses_default_profile_if_none(self, clear_signal):
        legs = [self._make_leg(1, "Nairobi", [clear_signal])]
        config = {
            "trip_mode": "regular", "bag_type": "carry_on",
            "activities": [], "laundry_access": "some",
            "travelling_with": "solo", "purpose": "leisure",
        }
        result = build_packing_list(legs, None, config)
        assert len(result) > 0

    def test_items_sorted_by_sort_order(self, clear_signal, neutral_profile):
        legs = [self._make_leg(1, "Nairobi", [clear_signal])]
        config = {
            "trip_mode": "regular", "bag_type": "carry_on",
            "activities": [], "laundry_access": "some",
            "travelling_with": "solo", "purpose": "leisure",
        }
        result = build_packing_list(legs, neutral_profile, config)
        sort_orders = [item["sort_order"] for item in result]
        assert sort_orders == sorted(sort_orders)