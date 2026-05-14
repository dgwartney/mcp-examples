"""
Unit tests for mcp_examples.weather

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import os
import tempfile
from unittest.mock import MagicMock

import httpx
import pytest
from fastmcp.exceptions import ToolError

from mcp_examples.database import DatabaseManager
from mcp_examples.weather import WeatherMCPServer, _fmt_date, _fmt_utc


def _tool_fn(server, name):
    """Extract the raw callable from a registered FastMCP tool."""
    return server.mcp._tool_manager._tools[name].fn


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def server(tmp_path):
    db = str(tmp_path / "keys.db")
    s = WeatherMCPServer(db_path=db, api_key="test-key-123")
    s._http = MagicMock()
    return s


@pytest.fixture
def server_no_key(tmp_path):
    db = str(tmp_path / "keys.db")
    s = WeatherMCPServer(db_path=db, api_key="")
    s._http = MagicMock()
    return s


def _resp(data, status=200):
    """Build a mock httpx response."""
    r = MagicMock()
    r.status_code = status
    r.json.return_value = data
    r.raise_for_status.return_value = None
    return r


def _http_error(status):
    """Build a mock HTTPStatusError with the given status code."""
    mock_response = MagicMock()
    mock_response.status_code = status
    return httpx.HTTPStatusError("error", request=MagicMock(), response=mock_response)


_GEO_LONDON = [{"name": "London", "country": "GB", "lat": 51.51, "lon": -0.13}]
_GEO_ROME = [{"name": "Rome", "country": "IT", "lat": 41.9, "lon": 12.5}]
_GEO_BEIJING = [{"name": "Beijing", "country": "CN", "lat": 39.9, "lon": 116.4}]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestFmtUtc:

    def test_none_returns_empty_string(self):
        assert _fmt_utc(None) == ""

    def test_known_timestamp(self):
        assert _fmt_utc(0) == "1970-01-01T00:00:00Z"

    def test_returns_iso_format(self):
        result = _fmt_utc(1700000000)
        assert result.endswith("Z")
        assert "T" in result


class TestFmtDate:

    def test_none_returns_empty_string(self):
        assert _fmt_date(None) == ""

    def test_known_timestamp(self):
        assert _fmt_date(0) == "1970-01-01"

    def test_returns_date_only(self):
        result = _fmt_date(1700000000)
        assert len(result) == 10
        assert result.count("-") == 2


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestWeatherMCPServerInit:

    def test_server_name(self, temp_db_path):
        s = WeatherMCPServer(db_path=temp_db_path, api_key="k")
        assert s.mcp.name == "WeatherMCP"

    def test_three_tools_registered(self, temp_db_path):
        s = WeatherMCPServer(db_path=temp_db_path, api_key="k")
        assert len(s.mcp._tool_manager._tools) == 3

    def test_tool_names(self, temp_db_path):
        s = WeatherMCPServer(db_path=temp_db_path, api_key="k")
        assert set(s.mcp._tool_manager._tools) == {
            "get_current_weather",
            "get_forecast",
            "get_air_quality",
        }

    def test_db_manager_created(self, temp_db_path):
        s = WeatherMCPServer(db_path=temp_db_path, api_key="k")
        assert isinstance(s.db_manager, DatabaseManager)

    def test_api_key_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENWEATHER_API_KEY", "env-key")
        s = WeatherMCPServer(db_path=str(tmp_path / "k.db"))
        assert s._api_key == "env-key"

    def test_api_key_param_overrides_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENWEATHER_API_KEY", "env-key")
        s = WeatherMCPServer(db_path=str(tmp_path / "k.db"), api_key="param-key")
        assert s._api_key == "param-key"

    def test_module_level_server_instance(self):
        import mcp_examples.weather as m
        assert isinstance(m.server, WeatherMCPServer)

    def test_module_level_mcp_instance(self):
        import mcp_examples.weather as m
        assert m.mcp is m.server.mcp


# ---------------------------------------------------------------------------
# get_current_weather — One Call API 3.0
# ---------------------------------------------------------------------------

_ONE_CALL_CURRENT = {
    "lat": 51.51,
    "lon": -0.13,
    "timezone": "Europe/London",
    "current": {
        "dt": 1700000000,
        "sunrise": 1700000000,
        "sunset": 1700040000,
        "temp": 10.5,
        "feels_like": 8.0,
        "pressure": 1013,
        "humidity": 80,
        "visibility": 10000,
        "wind_speed": 5.5,
        "wind_deg": 270,
        "uvi": 0.5,
        "weather": [{"description": "overcast clouds"}],
    },
    "daily": [{
        "dt": 1700000000,
        "temp": {"day": 10.5, "min": 9.0, "max": 12.0},
        "weather": [{"description": "overcast clouds"}],
    }],
}


class TestGetCurrentWeather:

    def _setup(self, server, geo=None, weather=None):
        geo_resp = _resp(geo if geo is not None else _GEO_LONDON)
        wx_resp = _resp(weather if weather is not None else _ONE_CALL_CURRENT)
        server._http.get.side_effect = [geo_resp, wx_resp]

    def test_returns_all_fields(self, server):
        self._setup(server)
        result = _tool_fn(server, "get_current_weather")(location="London")
        assert result["location"] == "London"
        assert result["country"] == "GB"
        assert result["temperature"] == 10.5
        assert result["feels_like"] == 8.0
        assert result["temp_min"] == 9.0
        assert result["temp_max"] == 12.0
        assert result["humidity"] == 80
        assert result["pressure"] == 1013
        assert result["wind_speed"] == 5.5
        assert result["wind_direction"] == 270
        assert result["description"] == "overcast clouds"
        assert result["visibility"] == 10000
        assert result["uvi"] == 0.5
        assert result["sunrise"].endswith("Z")
        assert result["sunset"].endswith("Z")

    def test_uses_one_call_3_endpoint(self, server):
        self._setup(server)
        _tool_fn(server, "get_current_weather")(location="London")
        url = server._http.get.call_args_list[1][0][0]
        assert "/data/3.0/onecall" in url

    def test_geocode_lat_lon_passed_to_onecall(self, server):
        self._setup(server)
        _tool_fn(server, "get_current_weather")(location="London")
        params = server._http.get.call_args_list[1][1]["params"]
        assert params["lat"] == 51.51
        assert params["lon"] == -0.13

    def test_minutely_hourly_alerts_excluded(self, server):
        self._setup(server)
        _tool_fn(server, "get_current_weather")(location="London")
        params = server._http.get.call_args_list[1][1]["params"]
        assert "minutely" in params["exclude"]
        assert "hourly" in params["exclude"]
        assert "alerts" in params["exclude"]

    def test_units_forwarded_to_onecall(self, server):
        self._setup(server)
        _tool_fn(server, "get_current_weather")(location="London", units="imperial")
        params = server._http.get.call_args_list[1][1]["params"]
        assert params["units"] == "imperial"

    def test_default_units_is_metric(self, server):
        self._setup(server)
        _tool_fn(server, "get_current_weather")(location="London")
        params = server._http.get.call_args_list[1][1]["params"]
        assert params["units"] == "metric"

    def test_invalid_units_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="Invalid units"):
            _tool_fn(server, "get_current_weather")(location="London", units="celsius")

    def test_location_not_found_via_geocode(self, server):
        server._http.get.return_value = _resp([])
        with pytest.raises(ToolError, match="Location not found"):
            _tool_fn(server, "get_current_weather")(location="Neverland")

    def test_401_on_onecall_raises_api_key_error(self, server):
        geo = _resp(_GEO_LONDON)
        wx = _resp({}, status=401)
        server._http.get.side_effect = [geo, wx]
        with pytest.raises(ToolError, match="API key"):
            _tool_fn(server, "get_current_weather")(location="London")

    def test_http_status_error_raises_tool_error(self, server):
        geo = _resp(_GEO_LONDON)
        wx = _resp({}, status=503)
        wx.raise_for_status.side_effect = _http_error(503)
        server._http.get.side_effect = [geo, wx]
        with pytest.raises(ToolError, match="HTTP 503"):
            _tool_fn(server, "get_current_weather")(location="London")

    def test_request_error_raises_tool_error(self, server):
        geo = _resp(_GEO_LONDON)
        server._http.get.side_effect = [geo, httpx.RequestError("timeout")]
        with pytest.raises(ToolError, match="request error"):
            _tool_fn(server, "get_current_weather")(location="London")

    def test_missing_api_key_raises_tool_error(self, server_no_key):
        with pytest.raises(ToolError, match="API key"):
            _tool_fn(server_no_key, "get_current_weather")(location="London")

    def test_empty_weather_list_handled(self, server):
        data = {**_ONE_CALL_CURRENT, "current": {**_ONE_CALL_CURRENT["current"], "weather": []}}
        self._setup(server, weather=data)
        result = _tool_fn(server, "get_current_weather")(location="London")
        assert result["description"] == ""

    def test_empty_daily_gives_none_min_max(self, server):
        data = {**_ONE_CALL_CURRENT, "daily": []}
        self._setup(server, weather=data)
        result = _tool_fn(server, "get_current_weather")(location="London")
        assert result["temp_min"] is None
        assert result["temp_max"] is None


# ---------------------------------------------------------------------------
# get_forecast — One Call API 3.0
# ---------------------------------------------------------------------------

_ONE_CALL_DAILY = {
    "lat": 41.9,
    "lon": 12.5,
    "daily": [
        {
            "dt": 1717200000,
            "temp": {"min": 18.0, "max": 24.0},
            "humidity": 55,
            "wind_speed": 4.0,
            "weather": [{"description": "sunny"}],
            "summary": "Sunny throughout the day",
        },
        {
            "dt": 1717286400,
            "temp": {"min": 15.0, "max": 21.0},
            "humidity": 70,
            "wind_speed": 6.0,
            "weather": [{"description": "light rain"}],
            "summary": "Rain expected in the afternoon",
        },
    ],
}


class TestGetForecast:

    def _setup(self, server, geo=None, forecast=None):
        geo_resp = _resp(geo if geo is not None else _GEO_ROME)
        fc_resp = _resp(forecast if forecast is not None else _ONE_CALL_DAILY)
        server._http.get.side_effect = [geo_resp, fc_resp]

    def test_returns_daily_entries(self, server):
        self._setup(server)
        result = _tool_fn(server, "get_forecast")(location="Rome")
        assert len(result) == 2

    def test_fields_present(self, server):
        self._setup(server)
        result = _tool_fn(server, "get_forecast")(location="Rome")
        day = result[0]
        assert day["date"] == "2024-06-01"
        assert day["temp_min"] == 18.0
        assert day["temp_max"] == 24.0
        assert day["description"] == "sunny"
        assert day["humidity"] == 55
        assert day["wind_speed"] == 4.0
        assert day["summary"] == "Sunny throughout the day"

    def test_uses_one_call_3_endpoint(self, server):
        self._setup(server)
        _tool_fn(server, "get_forecast")(location="Rome")
        url = server._http.get.call_args_list[1][0][0]
        assert "/data/3.0/onecall" in url

    def test_current_minutely_hourly_alerts_excluded(self, server):
        self._setup(server)
        _tool_fn(server, "get_forecast")(location="Rome")
        params = server._http.get.call_args_list[1][1]["params"]
        for part in ("current", "minutely", "hourly", "alerts"):
            assert part in params["exclude"]

    def test_geocode_lat_lon_passed_to_onecall(self, server):
        self._setup(server)
        _tool_fn(server, "get_forecast")(location="Rome")
        params = server._http.get.call_args_list[1][1]["params"]
        assert params["lat"] == 41.9
        assert params["lon"] == 12.5

    def test_days_clamped_to_minimum_1(self, server):
        many = {**_ONE_CALL_DAILY, "daily": _ONE_CALL_DAILY["daily"] * 4}
        self._setup(server, forecast=many)
        result = _tool_fn(server, "get_forecast")(location="Rome", days=0)
        assert len(result) == 1

    def test_days_clamped_to_maximum_8(self, server):
        eight_days = {**_ONE_CALL_DAILY, "daily": _ONE_CALL_DAILY["daily"] * 5}
        self._setup(server, forecast=eight_days)
        result = _tool_fn(server, "get_forecast")(location="Rome", days=20)
        assert len(result) == 8

    def test_default_days_is_7(self, server):
        seven_days = {**_ONE_CALL_DAILY, "daily": _ONE_CALL_DAILY["daily"] * 4}
        self._setup(server, forecast=seven_days)
        result = _tool_fn(server, "get_forecast")(location="Rome")
        assert len(result) == 7

    def test_units_forwarded(self, server):
        self._setup(server)
        _tool_fn(server, "get_forecast")(location="Rome", units="imperial")
        params = server._http.get.call_args_list[1][1]["params"]
        assert params["units"] == "imperial"

    def test_invalid_units_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="Invalid units"):
            _tool_fn(server, "get_forecast")(location="Rome", units="badval")

    def test_location_not_found_via_geocode(self, server):
        server._http.get.return_value = _resp([])
        with pytest.raises(ToolError, match="Location not found"):
            _tool_fn(server, "get_forecast")(location="Nowhere")

    def test_401_on_onecall_raises_api_key_error(self, server):
        geo = _resp(_GEO_ROME)
        fc = _resp({}, status=401)
        server._http.get.side_effect = [geo, fc]
        with pytest.raises(ToolError, match="API key"):
            _tool_fn(server, "get_forecast")(location="Rome")

    def test_http_status_error(self, server):
        geo = _resp(_GEO_ROME)
        fc = _resp({}, status=500)
        fc.raise_for_status.side_effect = _http_error(500)
        server._http.get.side_effect = [geo, fc]
        with pytest.raises(ToolError, match="HTTP 500"):
            _tool_fn(server, "get_forecast")(location="Rome")

    def test_request_error(self, server):
        geo = _resp(_GEO_ROME)
        server._http.get.side_effect = [geo, httpx.RequestError("connection refused")]
        with pytest.raises(ToolError, match="request error"):
            _tool_fn(server, "get_forecast")(location="Rome")

    def test_missing_api_key_raises_tool_error(self, server_no_key):
        with pytest.raises(ToolError, match="API key"):
            _tool_fn(server_no_key, "get_forecast")(location="Rome")


# ---------------------------------------------------------------------------
# get_air_quality — Air Pollution API (free, unchanged)
# ---------------------------------------------------------------------------

_AQ_RESPONSE = {
    "list": [{
        "main": {"aqi": 3},
        "components": {
            "co": 500.1, "no2": 25.3, "o3": 40.0, "pm2_5": 35.2, "pm10": 60.0,
        },
    }]
}


class TestGetAirQuality:

    def _setup_http(self, server, geo_resp=None, aq_resp=None):
        geo = _resp(geo_resp if geo_resp is not None else _GEO_BEIJING)
        aq = _resp(aq_resp if aq_resp is not None else _AQ_RESPONSE)
        server._http.get.side_effect = [geo, aq]

    def test_returns_all_fields(self, server):
        self._setup_http(server)
        result = _tool_fn(server, "get_air_quality")(location="Beijing")
        assert result["location"] == "Beijing, CN"
        assert result["aqi"] == 3
        assert result["aqi_label"] == "Moderate"
        assert result["co"] == 500.1
        assert result["no2"] == 25.3
        assert result["o3"] == 40.0
        assert result["pm2_5"] == 35.2
        assert result["pm10"] == 60.0

    def test_aqi_label_good(self, server):
        aq = {"list": [{"main": {"aqi": 1}, "components": {}}]}
        self._setup_http(server, aq_resp=aq)
        result = _tool_fn(server, "get_air_quality")(location="Rural")
        assert result["aqi_label"] == "Good"

    def test_aqi_label_very_poor(self, server):
        aq = {"list": [{"main": {"aqi": 5}, "components": {}}]}
        self._setup_http(server, aq_resp=aq)
        result = _tool_fn(server, "get_air_quality")(location="Smoggy")
        assert result["aqi_label"] == "Very Poor"

    def test_geocode_uses_lat_lon_for_aq_call(self, server):
        self._setup_http(server)
        _tool_fn(server, "get_air_quality")(location="Beijing")
        aq_call_params = server._http.get.call_args_list[1][1]["params"]
        assert aq_call_params["lat"] == 39.9
        assert aq_call_params["lon"] == 116.4

    def test_geocode_empty_result_raises_tool_error(self, server):
        server._http.get.return_value = _resp([])
        with pytest.raises(ToolError, match="Location not found"):
            _tool_fn(server, "get_air_quality")(location="Atlantis")

    def test_geocode_http_error_raises_tool_error(self, server):
        mock_resp = _resp([], status=500)
        mock_resp.raise_for_status.side_effect = _http_error(500)
        server._http.get.return_value = mock_resp
        with pytest.raises(ToolError, match="HTTP 500"):
            _tool_fn(server, "get_air_quality")(location="City")

    def test_geocode_request_error_raises_tool_error(self, server):
        server._http.get.side_effect = httpx.RequestError("timeout")
        with pytest.raises(ToolError, match="request error"):
            _tool_fn(server, "get_air_quality")(location="City")

    def test_aq_http_error_raises_tool_error(self, server):
        geo = _resp(_GEO_BEIJING)
        aq = _resp({}, status=503)
        aq.raise_for_status.side_effect = _http_error(503)
        server._http.get.side_effect = [geo, aq]
        with pytest.raises(ToolError, match="HTTP 503"):
            _tool_fn(server, "get_air_quality")(location="Beijing")

    def test_aq_request_error_raises_tool_error(self, server):
        geo = _resp(_GEO_BEIJING)
        server._http.get.side_effect = [geo, httpx.RequestError("network error")]
        with pytest.raises(ToolError, match="request error"):
            _tool_fn(server, "get_air_quality")(location="Beijing")

    def test_missing_api_key_raises_tool_error(self, server_no_key):
        with pytest.raises(ToolError, match="API key"):
            _tool_fn(server_no_key, "get_air_quality")(location="Beijing")

    def test_location_without_country_code(self, server):
        geo = _resp([{"name": "Springfield", "lat": 37.2, "lon": -93.3}])
        aq = _resp(_AQ_RESPONSE)
        server._http.get.side_effect = [geo, aq]
        result = _tool_fn(server, "get_air_quality")(location="Springfield")
        assert result["location"] == "Springfield"
