import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import date

from app.core.weather import (
    fetch_forecast,
    get_dominant_signal,
    forecast_date_range,
    signals_from_cache,
    is_high_altitude,
    WeatherFetchError,
    WMO_MAP,
    CONDITION_EMOJI,
)

@pytest.fixture
def mock_open_meteo_response():
    return {
        "latitude":  -1.28,
        "longitude":  36.82,
        "elevation":  1661.0,
        "timezone":  "Africa/Nairobi",
        "daily": {
            "time": [
                "2026-07-14",
                "2026-07-15",
                "2026-07-16",
                "2026-07-17",
                "2026-07-18",
            ],
            "temperature_2m_max":            [23.1, 19.4, 26.3, 21.0, 25.5],
            "temperature_2m_min":            [12.5, 13.1, 14.2, 11.8, 13.0],
            "apparent_temperature_max":      [22.0, 17.8, 25.5, 19.5, 24.1],
            "precipitation_probability_max": [20,   80,   10,   60,   5   ],
            "windspeed_10m_max":             [14.2, 22.5, 8.0,  18.3, 10.1],
            "uv_index_max":                  [5.2,  2.1,  7.8,  4.0,  6.5 ],
            "weathercode":                   [2,    63,   0,    61,   1   ],
            "sunrise": [
                "2026-07-14T06:31",
                "2026-07-15T06:31",
                "2026-07-16T06:32",
                "2026-07-17T06:32",
                "2026-07-18T06:32",
            ],
            "sunset": [
                "2026-07-14T18:38",
                "2026-07-15T18:38",
                "2026-07-16T18:38",
                "2026-07-17T18:38",
                "2026-07-18T18:38",
            ],
        },
        "hourly": {
            "relativehumidity_2m": (
                    [58] * 24 +
                    [82] * 24 +
                    [45] * 24 +
                    [70] * 24 +
                    [50] * 24
            ),
        },
    }


@pytest.fixture
def mock_response_obj(mock_open_meteo_response):
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = mock_open_meteo_response
    mock.raise_for_status.return_value = None
    return mock


@pytest.fixture
def nairobi_signals(mock_open_meteo_response, mock_response_obj):
    with patch("app.core.weather.requests.get", return_value=mock_response_obj):
        return fetch_forecast(
            lat=-1.28,
            lng=36.82,
            start_date=date(2026, 7, 14),
            end_date=date(2026, 7, 18),
        )
class TestFetchForecast:

    def test_returns_list(self, nairobi_signals):
        assert isinstance(nairobi_signals, list)

    def test_correct_number_of_days(self, nairobi_signals):
        assert len(nairobi_signals) == 5

    def test_signal_has_all_required_keys(self, nairobi_signals):
        required_keys = [
            "date", "temp_c", "temp_min_c", "feels_like_c",
            "rain_prob", "is_rainy_day", "wind_kph", "uv_index",
            "humidity_pct", "condition", "condition_emoji", "wmo_code",
            "evening_drop_c", "is_high_uv", "is_windy", "is_humid",
            "sunrise", "sunset", "altitude_m", "is_high_altitude",
        ]
        for signal in nairobi_signals:
            for key in required_keys:
                assert key in signal, f"Missing key '{key}' in signal for {signal['date']}"

    def test_dates_are_correct(self, nairobi_signals):
        expected = [
            "2026-07-14", "2026-07-15", "2026-07-16",
            "2026-07-17", "2026-07-18",
        ]
        actual = [s["date"] for s in nairobi_signals]
        assert actual == expected

    def test_temperature_values(self, nairobi_signals):
        assert nairobi_signals[0]["temp_c"]     == 23.1
        assert nairobi_signals[0]["temp_min_c"] == 12.5
        assert nairobi_signals[0]["feels_like_c"] == 22.0

    def test_rain_prob_scaled_to_0_1(self, nairobi_signals):
        assert nairobi_signals[0]["rain_prob"] == 0.2
        assert nairobi_signals[1]["rain_prob"] == 0.8

    def test_is_rainy_day_threshold(self, nairobi_signals):
        assert nairobi_signals[0]["is_rainy_day"] is False
        assert nairobi_signals[1]["is_rainy_day"] is True
        assert nairobi_signals[3]["is_rainy_day"] is True

    def test_wmo_code_mapped_to_condition(self, nairobi_signals):
        assert nairobi_signals[0]["condition"] == "partly_cloudy"
        assert nairobi_signals[1]["condition"] == "moderate_rain"
        assert nairobi_signals[2]["condition"] == "clear"

    def test_condition_has_emoji(self, nairobi_signals):
        for signal in nairobi_signals:
            assert signal["condition_emoji"] != ""
            assert isinstance(signal["condition_emoji"], str)

    def test_evening_drop_computed(self, nairobi_signals):
        assert nairobi_signals[0]["evening_drop_c"] == round(23.1 - 12.5, 1)

    def test_is_high_uv_threshold(self, nairobi_signals):
        assert nairobi_signals[0]["is_high_uv"] is False
        assert nairobi_signals[2]["is_high_uv"] is True
        assert nairobi_signals[4]["is_high_uv"] is True

    def test_is_windy_threshold(self, nairobi_signals):
        assert nairobi_signals[0]["is_windy"] is False
        assert nairobi_signals[1]["is_windy"] is False

    def test_humidity_averaged_from_hourly(self, nairobi_signals):
        assert nairobi_signals[0]["humidity_pct"] == 58
        assert nairobi_signals[1]["humidity_pct"] == 82

    def test_is_humid_threshold(self, nairobi_signals):
        assert nairobi_signals[1]["is_humid"] is True
        assert nairobi_signals[0]["is_humid"] is False

    def test_altitude_set_from_elevation(self, nairobi_signals):
        for signal in nairobi_signals:
            assert signal["altitude_m"] == 1661

    def test_is_high_altitude_nairobi(self, nairobi_signals):
        for signal in nairobi_signals:
            assert signal["is_high_altitude"] is False

    def test_sunrise_sunset_present(self, nairobi_signals):
        assert nairobi_signals[0]["sunrise"] == "2026-07-14T06:31"
        assert nairobi_signals[0]["sunset"]  == "2026-07-14T18:38"

class TestFetchForecastErrors:

    def test_raises_on_timeout(self):
        import requests as req
        with patch(
                "app.core.weather.requests.get",
                side_effect=req.exceptions.Timeout,
        ):
            with pytest.raises(WeatherFetchError, match="timed out"):
                fetch_forecast(
                    lat=-1.28, lng=36.82,
                    start_date=date(2026, 7, 14),
                    end_date=date(2026, 7, 14),
                )

    def test_raises_on_connection_error(self):
        import requests as req
        with patch(
                "app.core.weather.requests.get",
                side_effect=req.exceptions.ConnectionError,
        ):
            with pytest.raises(WeatherFetchError, match="connect"):
                fetch_forecast(
                    lat=-1.28, lng=36.82,
                    start_date=date(2026, 7, 14),
                    end_date=date(2026, 7, 14),
                )

    def test_raises_on_http_error(self):
        import requests as req
        mock = MagicMock()
        mock.status_code = 429
        mock.raise_for_status.side_effect = req.exceptions.HTTPError("429")
        with patch("app.core.weather.requests.get", return_value=mock):
            with pytest.raises(WeatherFetchError, match="HTTP 429"):
                fetch_forecast(
                    lat=-1.28, lng=36.82,
                    start_date=date(2026, 7, 14),
                    end_date=date(2026, 7, 14),
                )

    def test_raises_on_missing_daily_key(self):
        mock = MagicMock()
        mock.status_code = 200
        mock.raise_for_status.return_value = None
        # Response with 'daily' key missing entirely
        mock.json.return_value = {"latitude": -1.28, "longitude": 36.82}
        with patch("app.core.weather.requests.get", return_value=mock):
            with pytest.raises(WeatherFetchError, match="missing 'daily'"):
                fetch_forecast(
                    lat=-1.28, lng=36.82,
                    start_date=date(2026, 7, 14),
                    end_date=date(2026, 7, 14),
                )

    def test_raises_on_missing_temperature_key(self):
        mock = MagicMock()
        mock.status_code = 200
        mock.raise_for_status.return_value = None
        # 'daily' exists but missing temperature_2m_max
        mock.json.return_value = {
            "elevation": 0,
            "daily": {
                "time": ["2026-07-14"],
                # temperature_2m_max intentionally missing
                "temperature_2m_min":            [12.0],
                "apparent_temperature_max":      [20.0],
                "precipitation_probability_max": [10],
                "windspeed_10m_max":             [10.0],
                "uv_index_max":                  [5.0],
                "weathercode":                   [2],
            },
            "hourly": {"relativehumidity_2m": [60] * 24},
        }
        with patch("app.core.weather.requests.get", return_value=mock):
            with pytest.raises(WeatherFetchError, match="temperature_2m_max"):
                fetch_forecast(
                    lat=-1.28, lng=36.82,
                    start_date=date(2026, 7, 14),
                    end_date=date(2026, 7, 14),
                )

    def test_handles_none_values_gracefully(self):
        mock = MagicMock()
        mock.status_code = 200
        mock.raise_for_status.return_value = None
        mock.json.return_value = {
            "elevation": 0,
            "daily": {
                "time":                          ["2026-07-14"],
                "temperature_2m_max":            [None],
                "temperature_2m_min":            [None],
                "apparent_temperature_max":      [None],
                "precipitation_probability_max": [None],
                "windspeed_10m_max":             [None],
                "uv_index_max":                  [None],
                "weathercode":                   [None],
            },
            "hourly": {"relativehumidity_2m": []},
        }
        with patch("app.core.weather.requests.get", return_value=mock):
            signals = fetch_forecast(
                lat=-1.28, lng=36.82,
                start_date=date(2026, 7, 14),
                end_date=date(2026, 7, 14),
            )
        assert len(signals) == 1
        assert signals[0]["temp_c"] == 22.0
        assert signals[0]["rain_prob"] == 0.0
        assert signals[0]["condition"] == "clear"

    def test_raises_on_non_json_response(self):
        mock = MagicMock()
        mock.status_code = 200
        mock.raise_for_status.return_value = None
        mock.json.side_effect = ValueError("No JSON")
        with patch("app.core.weather.requests.get", return_value=mock):
            with pytest.raises(WeatherFetchError, match="non-JSON"):
                fetch_forecast(
                    lat=-1.28, lng=36.82,
                    start_date=date(2026, 7, 14),
                    end_date=date(2026, 7, 14),
                )

class TestGetDominantSignal:

    def test_raises_on_empty_list(self):
        with pytest.raises(ValueError, match="empty"):
            get_dominant_signal([])

    def test_single_signal_returns_itself(self, nairobi_signals):
        single = nairobi_signals[:1]
        dominant = get_dominant_signal(single)
        assert dominant["temp_c"] == single[0]["temp_c"]

    def test_temp_c_is_average_of_maxes(self, nairobi_signals):
        expected_avg = round((23.1 + 19.4 + 26.3 + 21.0 + 25.5) / 5, 1)
        dominant = get_dominant_signal(nairobi_signals)
        assert dominant["temp_c"] == expected_avg

    def test_temp_min_is_minimum_of_mins(self, nairobi_signals):
        dominant = get_dominant_signal(nairobi_signals)
        assert dominant["temp_min_c"] == 11.8

    def test_rain_prob_is_maximum(self, nairobi_signals):
        dominant = get_dominant_signal(nairobi_signals)
        assert dominant["rain_prob"] == 0.8

    def test_uv_index_is_maximum(self, nairobi_signals):
        dominant = get_dominant_signal(nairobi_signals)
        assert dominant["uv_index"] == 7.8

    def test_condition_is_most_frequent(self, nairobi_signals):
        dominant = get_dominant_signal(nairobi_signals)
        assert dominant["condition"] in list(WMO_MAP.values())

    def test_is_rainy_day_reflects_max_rain_prob(self, nairobi_signals):
        dominant = get_dominant_signal(nairobi_signals)
        assert dominant["is_rainy_day"] is True

    def test_dominant_flag_is_set(self, nairobi_signals):
        dominant = get_dominant_signal(nairobi_signals)
        assert dominant["is_dominant"] is True

    def test_date_is_first_day(self, nairobi_signals):
        dominant = get_dominant_signal(nairobi_signals)
        assert dominant["date"] == nairobi_signals[0]["date"]

class TestIsHighAltitude:

    def test_nairobi_not_high_altitude(self):
        assert is_high_altitude(1661) is False

    def test_addis_ababa_not_quite(self):
        assert is_high_altitude(2355) is False

    def test_exactly_at_threshold(self):
        assert is_high_altitude(2500) is True

    def test_above_threshold(self):
        assert is_high_altitude(5364) is True

    def test_sea_level(self):
        assert is_high_altitude(0) is False

    def test_mombasa_coastal(self):
        assert is_high_altitude(17) is False

class TestForecastDateRange:

    def test_single_day(self):
        result = forecast_date_range(date(2026, 7, 14), date(2026, 7, 14))
        assert result == "2026-07-14:2026-07-14"

    def test_multi_day_range(self):
        result = forecast_date_range(date(2026, 7, 10), date(2026, 7, 22))
        assert result == "2026-07-10:2026-07-22"

    def test_format_is_consistent(self):
        result = forecast_date_range(date(2026, 1, 5), date(2026, 1, 9))
        assert result == "2026-01-05:2026-01-09"

class TestSignalsFromCache:

    def test_roundtrip_from_cache(self, mock_open_meteo_response):
        original = signals_from_cache(mock_open_meteo_response)
        assert len(original) == 5
        assert original[0]["date"] == "2026-07-14"
        assert original[1]["condition"] == "moderate_rain"

class TestWMOMapping:

    def test_all_wmo_codes_have_condition(self):
        for code, condition in WMO_MAP.items():
            assert isinstance(condition, str)
            assert len(condition) > 0, f"WMO code {code} has empty condition"

    def test_all_conditions_have_emoji(self):
        conditions_in_map = set(WMO_MAP.values())
        for condition in conditions_in_map:
            assert condition in CONDITION_EMOJI, (
                f"Condition '{condition}' from WMO_MAP has no emoji in CONDITION_EMOJI"
            )

    def test_unknown_wmo_code_returns_default(self, nairobi_signals, mock_response_obj):
        mock_response_obj.json.return_value["daily"]["weathercode"][0] = 999
        with patch("app.core.weather.requests.get", return_value=mock_response_obj):
            signals = fetch_forecast(
                lat=-1.28, lng=36.82,
                start_date=date(2026, 7, 14),
                end_date=date(2026, 7, 18),
            )
        assert signals[0]["condition"] == "partly_cloudy"

class TestMultipleCities:

    @pytest.mark.parametrize("lat,lng,label", [
        (-1.28,  36.82, "Nairobi"),
        (-4.05,  39.67, "Mombasa"),
        (0.32,   32.58, "Kampala"),
        (25.20,  55.27, "Dubai"),
        (40.71, -74.01, "New York"),
        (-33.87, 151.21, "Sydney"),
    ])
    def test_fetch_succeeds_for_major_cities(
            self, lat, lng, label, mock_response_obj
    ):
        with patch("app.core.weather.requests.get", return_value=mock_response_obj):
            signals = fetch_forecast(
                lat=lat, lng=lng,
                start_date=date(2026, 7, 14),
                end_date=date(2026, 7, 18),
            )
        assert len(signals) == 5, f"Expected 5 signals for {label}"
        assert all("temp_c" in s for s in signals)