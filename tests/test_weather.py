"""
Unit tests for mcp_server_kit.weather

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import os
import tempfile
from unittest.mock import MagicMock

import httpx
import pytest
from fastmcp.exceptions import ToolError

from mcp_server_kit.database import DatabaseManager
from mcp_server_kit.weather import WeatherMCPServer, _fmt_date, _fmt_utc


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

    def test_close_closes_http_client(self, server):
        server.close()
        server._http.close.assert_called_once()

    def test_api_key_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENWEATHER_API_KEY", "env-key")
        s = WeatherMCPServer(db_path=str(tmp_path / "k.db"))
        assert s._api_key == "env-key"

    def test_api_key_param_overrides_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENWEATHER_API_KEY", "env-key")
        s = WeatherMCPServer(db_path=str(tmp_path / "k.db"), api_key="param-key")
        assert s._api_key == "param-key"

    def test_module_level_server_instance(self):
        import mcp_server_kit.weather as m
        assert isinstance(m.server, WeatherMCPServer)

    def test_module_level_mcp_instance(self):
        import mcp_server_kit.weather as m
        assert m.mcp is m.server.mcp


# ---------------------------------------------------------------------------
# get_current_weather — Current Weather Data API (free tier)
# ---------------------------------------------------------------------------

_CURRENT_WEATHER_2_5 = {
    "main": {
        "temp": 10.5, "feels_like": 8.0, "temp_min": 9.0, "temp_max": 12.0,
        "pressure": 1013, "humidity": 80,
    },
    "visibility": 10000,
    "wind": {"speed": 5.5, "deg": 270},
    "weather": [{"description": "overcast clouds"}],
    "sys": {"sunrise": 1700000000, "sunset": 1700040000, "country": "GB"},
    "name": "London",
}


class TestGetCurrentWeather:

    def _setup(self, server, geo=None, weather=None):
        geo_resp = _resp(geo if geo is not None else _GEO_LONDON)
        wx_resp = _resp(weather if weather is not None else _CURRENT_WEATHER_2_5)
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
        assert "uvi" not in result
        assert result["sunrise"].endswith("Z")
        assert result["sunset"].endswith("Z")

    def test_uses_2_5_weather_endpoint(self, server):
        self._setup(server)
        _tool_fn(server, "get_current_weather")(location="London")
        url = server._http.get.call_args_list[1][0][0]
        assert "/data/2.5/weather" in url

    def test_geocode_lat_lon_passed_to_weather_call(self, server):
        self._setup(server)
        _tool_fn(server, "get_current_weather")(location="London")
        params = server._http.get.call_args_list[1][1]["params"]
        assert params["lat"] == 51.51
        assert params["lon"] == -0.13

    def test_geocode_call_uses_https(self, server):
        self._setup(server)
        _tool_fn(server, "get_current_weather")(location="London")
        geocode_url = server._http.get.call_args_list[0][0][0]
        assert geocode_url.startswith("https://"), (
            "Geocoding must use HTTPS so the API key is not sent in "
            "plaintext over the network."
        )

    def test_units_forwarded(self, server):
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

    def test_401_on_weather_call_raises_api_key_error(self, server):
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
        data = {**_CURRENT_WEATHER_2_5, "weather": []}
        self._setup(server, weather=data)
        result = _tool_fn(server, "get_current_weather")(location="London")
        assert result["description"] == ""

    def test_missing_main_block_gives_none_fields(self, server):
        data = {**_CURRENT_WEATHER_2_5, "main": {}}
        self._setup(server, weather=data)
        result = _tool_fn(server, "get_current_weather")(location="London")
        assert result["temperature"] is None
        assert result["temp_min"] is None
        assert result["temp_max"] is None


# ---------------------------------------------------------------------------
# get_forecast — 5 Day / 3 Hour Forecast API (free tier)
# ---------------------------------------------------------------------------

def _day(dt, temp_min, temp_max, description, humidity, wind_speed):
    return {
        "dt": dt,
        "main": {"temp_min": temp_min, "temp_max": temp_max, "humidity": humidity},
        "weather": [{"description": description}],
        "wind": {"speed": wind_speed},
    }


# Day 1 (2024-06-01, base dt=1717200000): entries at 00:00, 12:00 (midday), 21:00
# Day 2 (2024-06-02, base dt=1717286400): entries at 00:00, 12:00 (midday), 21:00
_FORECAST_2_5 = {
    "list": [
        _day(1717200000, 14, 16, "clear sky", 60, 2.0),
        _day(1717243200, 20, 24, "sunny", 50, 4.0),
        _day(1717275600, 15, 18, "clear sky", 62, 2.5),
        _day(1717286400, 12, 15, "light rain", 75, 5.0),
        _day(1717329600, 15, 21, "light rain", 70, 6.0),
        _day(1717362000, 13, 17, "overcast clouds", 78, 4.5),
    ]
}


def _make_multi_day_forecast(n_days, start_dt=1717200000):
    """Build a forecast fixture with one midday entry per day, for clamp tests."""
    entries = []
    for i in range(n_days):
        dt = start_dt + i * 86400 + 12 * 3600
        entries.append(_day(dt, 10 + i, 15 + i, "clear sky", 50, 3.0))
    return {"list": entries}


class TestGetForecast:

    def _setup(self, server, geo=None, forecast=None):
        geo_resp = _resp(geo if geo is not None else _GEO_ROME)
        fc_resp = _resp(forecast if forecast is not None else _FORECAST_2_5)
        server._http.get.side_effect = [geo_resp, fc_resp]

    def test_returns_daily_entries(self, server):
        self._setup(server)
        result = _tool_fn(server, "get_forecast")(location="Rome")
        assert len(result) == 2

    def test_first_day_aggregation(self, server):
        self._setup(server)
        result = _tool_fn(server, "get_forecast")(location="Rome")
        day = result[0]
        assert day["date"] == "2024-06-01"
        assert day["temp_min"] == 14
        assert day["temp_max"] == 24
        assert day["description"] == "sunny"
        assert day["humidity"] == 50
        assert day["wind_speed"] == 4.0

    def test_second_day_aggregation(self, server):
        self._setup(server)
        result = _tool_fn(server, "get_forecast")(location="Rome")
        day = result[1]
        assert day["date"] == "2024-06-02"
        assert day["temp_min"] == 12
        assert day["temp_max"] == 21
        assert day["description"] == "light rain"
        assert day["humidity"] == 70
        assert day["wind_speed"] == 6.0

    def test_uses_2_5_forecast_endpoint(self, server):
        self._setup(server)
        _tool_fn(server, "get_forecast")(location="Rome")
        url = server._http.get.call_args_list[1][0][0]
        assert "/data/2.5/forecast" in url

    def test_geocode_lat_lon_passed_to_forecast_call(self, server):
        self._setup(server)
        _tool_fn(server, "get_forecast")(location="Rome")
        params = server._http.get.call_args_list[1][1]["params"]
        assert params["lat"] == 41.9
        assert params["lon"] == 12.5

    def test_days_clamped_to_minimum_1(self, server):
        self._setup(server)
        result = _tool_fn(server, "get_forecast")(location="Rome", days=0)
        assert len(result) == 1

    def test_days_clamped_to_maximum_5(self, server):
        forecast = _make_multi_day_forecast(7)
        self._setup(server, forecast=forecast)
        result = _tool_fn(server, "get_forecast")(location="Rome", days=20)
        assert len(result) == 5

    def test_default_days_is_5(self, server):
        forecast = _make_multi_day_forecast(7)
        self._setup(server, forecast=forecast)
        result = _tool_fn(server, "get_forecast")(location="Rome")
        assert len(result) == 5

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

    def test_401_on_forecast_raises_api_key_error(self, server):
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

    def test_empty_list_returns_empty(self, server):
        self._setup(server, forecast={"list": []})
        result = _tool_fn(server, "get_forecast")(location="Rome")
        assert result == []

    def test_entry_missing_dt_is_skipped(self, server):
        malformed = {"list": [{"main": {}, "weather": [{}], "wind": {}}, *_FORECAST_2_5["list"]]}
        self._setup(server, forecast=malformed)
        result = _tool_fn(server, "get_forecast")(location="Rome")
        assert len(result) == 2


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
