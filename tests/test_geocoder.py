import pytest
from unittest.mock import patch, MagicMock

from app.core.geocoder import (
    geocode,
    geocode_multiple,
    build_cache_key,
    extract_country,
    GeocoderError,
    DEFAULT_USER_AGENT,
    COORD_PRECISION,
)

@pytest.fixture
def nairobi_response():

    return [
        {
            "lat": "-1.2834169",
            "lon": "36.8172449",
            "display_name": "Nairobi, Nairobi City County, Kenya",
            "type": "city",
            "importance": 0.8,
        }
    ]


@pytest.fixture
def mombasa_response():
    return [
        {
            "lat": "-4.0534688",
            "lon": "39.6680814",
            "display_name": "Mombasa, Coast, Kenya",
            "type": "city",
            "importance": 0.7,
        }
    ]


@pytest.fixture
def kampala_response():
    return [
        {
            "lat": "0.3155548",
            "lon": "32.5820994",
            "display_name": "Kampala, Uganda",
            "type": "city",
            "importance": 0.75,
        }
    ]


@pytest.fixture
def mock_nominatim(nairobi_response):
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status.return_value = None
    mock.json.return_value = nairobi_response
    return mock


def make_mock(json_data, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.raise_for_status.return_value = None
    mock.json.return_value = json_data
    return mock

# geocode -- happy path

class TestGeocodeHappyPath:

    def test_returns_dict_for_known_city(self, mock_nominatim):
        with patch("app.core.geocoder.requests.get", return_value=mock_nominatim):
            result = geocode("Nairobi", delay=False)
        assert result is not None
        assert isinstance(result, dict)

    def test_result_has_required_keys(self, mock_nominatim):
        with patch("app.core.geocoder.requests.get", return_value=mock_nominatim):
            result = geocode("Nairobi", delay=False)
        assert "lat" in result
        assert "lng" in result
        assert "display_name" in result
        assert "short_name" in result

    def test_coordinates_are_floats(self, mock_nominatim):
        with patch("app.core.geocoder.requests.get", return_value=mock_nominatim):
            result = geocode("Nairobi", delay=False)
        assert isinstance(result["lat"], float)
        assert isinstance(result["lng"], float)

    def test_coordinates_rounded_to_precision(self, mock_nominatim):
        with patch("app.core.geocoder.requests.get", return_value=mock_nominatim):
            result = geocode("Nairobi", delay=False)
        # -1.2834169 rounded to 2dp = -1.28
        assert result["lat"] == -1.28
        # 36.8172449 rounded to 2dp = 36.82
        assert result["lng"] == 36.82

    def test_display_name_preserved(self, mock_nominatim):
        with patch("app.core.geocoder.requests.get", return_value=mock_nominatim):
            result = geocode("Nairobi", delay=False)
        assert result["display_name"] == "Nairobi, Nairobi City County, Kenya"

    def test_short_name_is_first_component(self, mock_nominatim):
        with patch("app.core.geocoder.requests.get", return_value=mock_nominatim):
            result = geocode("Nairobi", delay=False)
        assert result["short_name"] == "Nairobi"

    def test_mombasa_coordinates(self, mombasa_response):
        mock = make_mock(mombasa_response)
        with patch("app.core.geocoder.requests.get", return_value=mock):
            result = geocode("Mombasa", delay=False)
        assert result["lat"] == round(-4.0534688, COORD_PRECISION)
        assert result["lng"] == round(39.6680814, COORD_PRECISION)
        assert result["short_name"] == "Mombasa"

    def test_kampala_coordinates(self, kampala_response):
        mock = make_mock(kampala_response)
        with patch("app.core.geocoder.requests.get", return_value=mock):
            result = geocode("Kampala", delay=False)
        assert result["lat"] == round(0.3155548, COORD_PRECISION)
        assert result["lng"] == round(32.5820994, COORD_PRECISION)
        assert result["short_name"] == "Kampala"

    def test_city_with_country_qualifier(self, nairobi_response):
        """'Nairobi, Kenya' should geocode the same as 'Nairobi'."""
        mock = make_mock(nairobi_response)
        with patch("app.core.geocoder.requests.get", return_value=mock):
            result = geocode("Nairobi, Kenya", delay=False)
        assert result is not None
        assert result["lat"] == -1.28

    def test_strips_whitespace_from_input(self, nairobi_response):
        mock = make_mock(nairobi_response)
        with patch("app.core.geocoder.requests.get", return_value=mock):
            result = geocode("  Nairobi  ", delay=False)
        assert result is not None

    def test_user_agent_sent_in_headers(self, mock_nominatim):
        with patch("app.core.geocoder.requests.get", return_value=mock_nominatim) as mock_get:
            geocode("Nairobi", delay=False)
        call_kwargs = mock_get.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
        assert "User-Agent" in headers
        assert headers["User-Agent"] == DEFAULT_USER_AGENT

    def test_custom_user_agent(self, mock_nominatim):
        custom_agent = "TestApp/1.0 (test@example.com)"
        with patch("app.core.geocoder.requests.get", return_value=mock_nominatim) as mock_get:
            geocode("Nairobi", user_agent=custom_agent, delay=False)
        call_kwargs = mock_get.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
        assert headers["User-Agent"] == custom_agent

    def test_limit_param_is_1(self, mock_nominatim):
        with patch("app.core.geocoder.requests.get", return_value=mock_nominatim) as mock_get:
            geocode("Nairobi", delay=False)
        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params", {})
        assert params.get("limit") == 1

    def test_format_param_is_json(self, mock_nominatim):
        with patch("app.core.geocoder.requests.get", return_value=mock_nominatim) as mock_get:
            geocode("Nairobi", delay=False)
        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params", {})
        assert params.get("format") == "json"

# geocode -- returns None cases
class TestGeocodeReturnsNone:

    def test_returns_none_for_empty_string(self):
        result = geocode("", delay=False)
        assert result is None

    def test_returns_none_for_whitespace_only(self):
        result = geocode("   ", delay=False)
        assert result is None

    def test_returns_none_for_unknown_city(self):
        mock = make_mock([])   # empty list = city not found
        with patch("app.core.geocoder.requests.get", return_value=mock):
            result = geocode("Xyznonexistentcity123", delay=False)
        assert result is None

    def test_returns_none_on_timeout(self):
        import requests as req
        with patch(
                "app.core.geocoder.requests.get",
                side_effect=req.exceptions.Timeout,
        ):
            result = geocode("Nairobi", delay=False)
        assert result is None

    def test_returns_none_on_connection_error(self):
        import requests as req
        with patch(
                "app.core.geocoder.requests.get",
                side_effect=req.exceptions.ConnectionError,
        ):
            result = geocode("Nairobi", delay=False)
        assert result is None

    def test_returns_none_on_http_error(self):
        import requests as req
        mock = MagicMock()
        mock.raise_for_status.side_effect = req.exceptions.HTTPError("429")
        with patch("app.core.geocoder.requests.get", return_value=mock):
            result = geocode("Nairobi", delay=False)
        assert result is None

    def test_returns_none_on_non_json_response(self):
        mock = MagicMock()
        mock.status_code = 200
        mock.raise_for_status.return_value = None
        mock.json.side_effect = ValueError("No JSON")
        with patch("app.core.geocoder.requests.get", return_value=mock):
            result = geocode("Nairobi", delay=False)
        assert result is None

    def test_returns_none_on_non_list_response(self):
        mock = make_mock({"error": "Unable to geocode"})
        with patch("app.core.geocoder.requests.get", return_value=mock):
            result = geocode("Nairobi", delay=False)
        assert result is None

    def test_returns_none_on_missing_lat_key(self):
        mock = make_mock([{"lon": "36.82", "display_name": "Nairobi"}])
        with patch("app.core.geocoder.requests.get", return_value=mock):
            result = geocode("Nairobi", delay=False)
        assert result is None

    def test_returns_none_on_missing_lon_key(self):
        mock = make_mock([{"lat": "-1.28", "display_name": "Nairobi"}])
        with patch("app.core.geocoder.requests.get", return_value=mock):
            result = geocode("Nairobi", delay=False)
        assert result is None

    def test_returns_none_on_non_numeric_coordinates(self):
        mock = make_mock([{
            "lat": "not_a_number",
            "lon": "also_not_a_number",
            "display_name": "Nairobi",
        }])
        with patch("app.core.geocoder.requests.get", return_value=mock):
            result = geocode("Nairobi", delay=False)
        assert result is None

    def test_never_raises_on_unexpected_exception(self):
        with patch(
                "app.core.geocoder.requests.get",
                side_effect=RuntimeError("Unexpected!"),
        ):
            result = geocode("Nairobi", delay=False)
        assert result is None

# geocode_multiple

class TestGeocodeMultiple:

    def test_returns_dict_with_all_cities(
            self, nairobi_response, mombasa_response, kampala_response
    ):
        responses = [nairobi_response, mombasa_response, kampala_response]
        mocks = [make_mock(r) for r in responses]

        with patch("app.core.geocoder.requests.get", side_effect=mocks):
            results = geocode_multiple(
                ["Nairobi", "Mombasa", "Kampala"],
            )

        assert "Nairobi" in results
        assert "Mombasa" in results
        assert "Kampala" in results

    def test_failed_city_maps_to_none(self, nairobi_response):
        responses = [nairobi_response, []]   # second city not found
        mocks = [make_mock(r) for r in responses]

        with patch("app.core.geocoder.requests.get", side_effect=mocks):
            results = geocode_multiple(["Nairobi", "Xyzunknown"])

        assert results["Nairobi"] is not None
        assert results["Xyzunknown"] is None

    def test_all_failed_returns_all_none(self):
        mocks = [make_mock([]), make_mock([])]
        with patch("app.core.geocoder.requests.get", side_effect=mocks):
            results = geocode_multiple(["City1", "City2"])
        assert results["City1"] is None
        assert results["City2"] is None

    def test_empty_list_returns_empty_dict(self):
        results = geocode_multiple([])
        assert results == {}

    def test_single_city_list(self, nairobi_response):
        mock = make_mock(nairobi_response)
        with patch("app.core.geocoder.requests.get", return_value=mock):
            results = geocode_multiple(["Nairobi"])
        assert len(results) == 1
        assert results["Nairobi"] is not None

# build_cache_key

class TestBuildCacheKey:

    def test_lowercases_input(self):
        assert build_cache_key("Nairobi") == "nairobi"
        assert build_cache_key("MOMBASA") == "mombasa"
        assert build_cache_key("Kampala Uganda") == "kampala uganda"

    def test_strips_whitespace(self):
        assert build_cache_key("  Nairobi  ") == "nairobi"
        assert build_cache_key("\tMombasa\n") == "mombasa"

    def test_consistent_for_same_city(self):
        assert build_cache_key("Nairobi") == build_cache_key("nairobi")
        assert build_cache_key("Nairobi") == build_cache_key("  NAIROBI  ")

    def test_different_cities_give_different_keys(self):
        assert build_cache_key("Nairobi") != build_cache_key("Mombasa")

    def test_empty_string(self):
        assert build_cache_key("") == ""

    def test_city_with_country(self):
        key = build_cache_key("Nairobi, Kenya")
        assert key == "nairobi, kenya"

# extract_country

class TestExtractCountry:

    def test_extracts_kenya_from_nairobi(self):
        result = extract_country("Nairobi, Nairobi City County, Kenya")
        assert result == "Kenya"

    def test_extracts_kenya_from_mombasa(self):
        result = extract_country("Mombasa, Coast, Kenya")
        assert result == "Kenya"

    def test_extracts_uganda_from_kampala(self):
        result = extract_country("Kampala, Uganda")
        assert result == "Uganda"

    def test_handles_two_component_name(self):
        result = extract_country("Miami, United States")
        assert result == "United States"

    def test_returns_none_for_empty_string(self):
        result = extract_country("")
        assert result is None

    def test_returns_none_for_none_input(self):
        result = extract_country(None)
        assert result is None

    def test_returns_none_for_single_component(self):
        result = extract_country("Kenya")
        assert result is None

    def test_strips_whitespace_from_country(self):
        result = extract_country("Nairobi,   Kenya  ")
        assert result == "Kenya"

    def test_handles_many_components(self):
        result = extract_country("Westlands, Nairobi, Nairobi City County, Kenya")
        assert result == "Kenya"

# Coordinate precision
class TestCoordinatePrecision:

    @pytest.mark.parametrize("raw_lat,raw_lng,expected_lat,expected_lng", [
        ("-1.2834169",  "36.8172449",  -1.28,  36.82),   # Nairobi
        ("-4.0534688",  "39.6680814",  -4.05,  39.67),   # Mombasa
        ("0.3155548",   "32.5820994",  0.32,   32.58),   # Kampala
        ("25.2048493",  "55.2707828",  25.2,   55.27),   # Dubai
        ("40.7127281",  "-74.0060152", 40.71,  -74.01),  # New York
        ("-33.8698439", "151.2082848", -33.87, 151.21),  # Sydney
        ("51.5073219",  "-0.1276474",  51.51,  -0.13),   # London
    ])
    def test_coordinates_rounded_correctly(
            self, raw_lat, raw_lng, expected_lat, expected_lng
    ):
        mock_response = [{"lat": raw_lat, "lon": raw_lng, "display_name": "Test City"}]
        mock = make_mock(mock_response)
        with patch("app.core.geocoder.requests.get", return_value=mock):
            result = geocode("Test City", delay=False)
        assert result["lat"] == expected_lat
        assert result["lng"] == expected_lng