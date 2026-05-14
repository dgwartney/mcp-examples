"""
FastMCP Server with OpenWeatherMap weather tools.

Demonstrates how to build an MCP server by subclassing
``AuthenticatedMCPServer`` and registering tools that query the
OpenWeatherMap One Call API 3.0.

To use this server you need an OpenWeatherMap API key subscribed to the
"One Call by Call" plan (2,000 free calls/day, credit card required):
    1. Sign up at https://openweathermap.org/api
    2. Subscribe to "One Call API 3.0" at https://openweathermap.org/price
    3. Export the key before starting the server:
           export OPENWEATHER_API_KEY=<your_key>

Air quality uses the free Air Pollution API (no subscription needed).

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    Run the server directly (stdio transport):
        $ OPENWEATHER_API_KEY=<key> uv run -m mcp_examples.weather

    Run as HTTP server:
        $ OPENWEATHER_API_KEY=<key> uv run -m mcp_examples.weather --transport streamable-http --port 8001

    Run with custom database path:
        $ MCP_DB_PATH=/var/data/keys.db OPENWEATHER_API_KEY=<key> uv run -m mcp_examples.weather
"""

import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastmcp.exceptions import ToolError

from mcp_examples.base import AuthenticatedMCPServer

_BASE_URL = "https://api.openweathermap.org"
_GEO_URL = "http://api.openweathermap.org"
_USER_AGENT = "mcp-weather-example/1.0"

_AQI_LABELS = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}

_VALID_UNITS = {"metric", "imperial", "standard"}


class WeatherMCPServer(AuthenticatedMCPServer):
    """
    MCP server with OpenWeatherMap weather tools.

    Exposes three tools backed by the OpenWeatherMap API:
    - get_current_weather: current conditions via One Call API 3.0
    - get_forecast: up to 8-day daily forecast via One Call API 3.0
    - get_air_quality: current AQI and pollutant levels via Air Pollution API

    Requires the ``OPENWEATHER_API_KEY`` environment variable to be set.
    get_current_weather and get_forecast require a One Call API 3.0 subscription
    (2,000 free calls/day). get_air_quality uses the free Air Pollution API.
    """

    def __init__(self, db_path: Optional[str] = None, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("OPENWEATHER_API_KEY", "")
        self._http = httpx.Client(
            headers={"User-Agent": _USER_AGENT},
            timeout=10.0,
            follow_redirects=True,
        )
        super().__init__(name="WeatherMCP", db_path=db_path)

    def _register_tools(self) -> None:
        """Register OpenWeatherMap MCP tools."""

        @self.mcp.tool(
            description=(
                "Get the current weather conditions for a city or location using "
                "One Call API 3.0. Returns temperature, humidity, wind, UV index, "
                "visibility, and a short description. "
                "units: 'metric' (Celsius), 'imperial' (Fahrenheit), 'standard' (Kelvin)."
            )
        )
        def get_current_weather(location: str, units: str = "metric") -> dict:
            """
            Retrieve current weather conditions for a location.

            Geocodes the location, then calls the One Call API 3.0 for current
            conditions. Today's min/max temperatures come from the daily forecast
            included in the same response.

            Args:
                location: City name, optionally with country code
                          (e.g. 'London', 'Paris,FR', 'New York,US').
                units: Unit system — 'metric' (°C, m/s), 'imperial' (°F, mph),
                       or 'standard' (K, m/s). Defaults to 'metric'.

            Returns:
                Dict with keys: location, country, temperature, feels_like,
                temp_min, temp_max, humidity, pressure, wind_speed,
                wind_direction, description, visibility, uvi, sunrise, sunset.

            Raises:
                ToolError: If the API key is missing, the location is not found,
                           or the request fails.
            """
            self._check_api_key()
            if units not in _VALID_UNITS:
                raise ToolError(
                    f"Invalid units '{units}'. Must be one of: metric, imperial, standard."
                )
            lat, lon, name, country = self._geocode(location)
            try:
                resp = self._http.get(
                    f"{_BASE_URL}/data/3.0/onecall",
                    params={
                        "lat": lat,
                        "lon": lon,
                        "exclude": "minutely,hourly,alerts",
                        "units": units,
                        "appid": self._api_key,
                    },
                )
                if resp.status_code == 401:
                    raise ToolError(
                        "Invalid or missing OpenWeatherMap API key. "
                        "Set the OPENWEATHER_API_KEY environment variable."
                    )
                resp.raise_for_status()
            except ToolError:
                raise
            except httpx.HTTPStatusError as exc:
                raise ToolError(
                    f"Weather request failed: HTTP {exc.response.status_code}"
                ) from exc
            except httpx.RequestError as exc:
                raise ToolError(f"Weather request error: {exc}") from exc

            d = resp.json()
            current = d.get("current", {})
            daily = d.get("daily", [])
            today_temp = (daily[0].get("temp") or {}) if daily else {}
            weather_list = current.get("weather", [{}])
            return {
                "location": name,
                "country": country,
                "temperature": current.get("temp"),
                "feels_like": current.get("feels_like"),
                "temp_min": today_temp.get("min"),
                "temp_max": today_temp.get("max"),
                "humidity": current.get("humidity"),
                "pressure": current.get("pressure"),
                "wind_speed": current.get("wind_speed"),
                "wind_direction": current.get("wind_deg"),
                "description": weather_list[0].get("description", "") if weather_list else "",
                "visibility": current.get("visibility"),
                "uvi": current.get("uvi"),
                "sunrise": _fmt_utc(current.get("sunrise")),
                "sunset": _fmt_utc(current.get("sunset")),
            }

        @self.mcp.tool(
            description=(
                "Get a multi-day weather forecast for a city or location using "
                "One Call API 3.0. Returns daily summaries with min/max temperature, "
                "description, humidity, wind, and a plain-English summary. "
                "units: 'metric' (Celsius), 'imperial' (Fahrenheit), 'standard' (Kelvin)."
            )
        )
        def get_forecast(location: str, days: int = 7, units: str = "metric") -> list[dict]:
            """
            Retrieve a multi-day weather forecast for a location.

            Uses the One Call API 3.0 daily forecast, which provides up to 8 days
            (today + 7). Each entry is a true daily aggregate, not an interval average.

            Args:
                location: City name, optionally with country code
                          (e.g. 'London', 'Tokyo,JP').
                days: Number of days to return (1–8, default 7).
                units: Unit system — 'metric', 'imperial', or 'standard'.
                       Defaults to 'metric'.

            Returns:
                List of dicts with keys: date, temp_min, temp_max, description,
                humidity, wind_speed, summary.

            Raises:
                ToolError: If the API key is missing, the location is not found,
                           or the request fails.
            """
            self._check_api_key()
            if units not in _VALID_UNITS:
                raise ToolError(
                    f"Invalid units '{units}'. Must be one of: metric, imperial, standard."
                )
            days = max(1, min(days, 8))
            lat, lon, _name, _country = self._geocode(location)
            try:
                resp = self._http.get(
                    f"{_BASE_URL}/data/3.0/onecall",
                    params={
                        "lat": lat,
                        "lon": lon,
                        "exclude": "current,minutely,hourly,alerts",
                        "units": units,
                        "appid": self._api_key,
                    },
                )
                if resp.status_code == 401:
                    raise ToolError(
                        "Invalid or missing OpenWeatherMap API key. "
                        "Set the OPENWEATHER_API_KEY environment variable."
                    )
                resp.raise_for_status()
            except ToolError:
                raise
            except httpx.HTTPStatusError as exc:
                raise ToolError(
                    f"Forecast request failed: HTTP {exc.response.status_code}"
                ) from exc
            except httpx.RequestError as exc:
                raise ToolError(f"Forecast request error: {exc}") from exc

            daily = resp.json().get("daily", [])[:days]
            return [
                {
                    "date": _fmt_date(d.get("dt")),
                    "temp_min": (d.get("temp") or {}).get("min"),
                    "temp_max": (d.get("temp") or {}).get("max"),
                    "description": (d.get("weather") or [{}])[0].get("description", ""),
                    "humidity": d.get("humidity"),
                    "wind_speed": d.get("wind_speed"),
                    "summary": d.get("summary", ""),
                }
                for d in daily
            ]

        @self.mcp.tool(
            description=(
                "Get the current air quality index (AQI) and key pollutant levels "
                "for a city or location. AQI scale: 1=Good, 2=Fair, 3=Moderate, "
                "4=Poor, 5=Very Poor. Uses the free Air Pollution API."
            )
        )
        def get_air_quality(location: str) -> dict:
            """
            Retrieve current air quality for a location.

            Geocodes the location to coordinates, then fetches air quality data
            from the OpenWeatherMap Air Pollution API (free, no subscription needed).

            Args:
                location: City name, optionally with country code
                          (e.g. 'Beijing', 'Los Angeles,US').

            Returns:
                Dict with keys: location, aqi (1–5), aqi_label, co, no2,
                o3, pm2_5, pm10.

            Raises:
                ToolError: If the API key is missing, the location cannot be
                           geocoded, or any request fails.
            """
            self._check_api_key()
            lat, lon, name, country = self._geocode(location)
            resolved_name = f"{name}, {country}" if country else name

            try:
                resp = self._http.get(
                    f"{_BASE_URL}/data/2.5/air_pollution",
                    params={"lat": lat, "lon": lon, "appid": self._api_key},
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ToolError(
                    f"Air quality request failed: HTTP {exc.response.status_code}"
                ) from exc
            except httpx.RequestError as exc:
                raise ToolError(f"Air quality request error: {exc}") from exc

            items = resp.json().get("list", [{}])
            entry = items[0] if items else {}
            aqi = (entry.get("main") or {}).get("aqi", 0)
            components = entry.get("components", {})
            return {
                "location": resolved_name,
                "aqi": aqi,
                "aqi_label": _AQI_LABELS.get(aqi, "Unknown"),
                "co": components.get("co"),
                "no2": components.get("no2"),
                "o3": components.get("o3"),
                "pm2_5": components.get("pm2_5"),
                "pm10": components.get("pm10"),
            }

    def _check_api_key(self) -> None:
        if not self._api_key:
            raise ToolError(
                "OpenWeatherMap API key is not configured. "
                "Sign up at https://openweathermap.org/api and subscribe to "
                "One Call API 3.0, then set the OPENWEATHER_API_KEY environment variable."
            )

    def _geocode(self, location: str) -> tuple[float, float, str, str]:
        """Return (lat, lon, city_name, country) for a location string."""
        try:
            resp = self._http.get(
                f"{_GEO_URL}/geo/1.0/direct",
                params={"q": location, "limit": 1, "appid": self._api_key},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ToolError(
                f"Geocoding failed: HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise ToolError(f"Geocoding request error: {exc}") from exc

        results = resp.json()
        if not results:
            raise ToolError(f"Location not found: '{location}'")
        r = results[0]
        return r["lat"], r["lon"], r.get("name", location), r.get("country", "")


def _fmt_utc(ts: Optional[int]) -> str:
    """Convert a Unix timestamp to an ISO-8601 UTC string, or '' if None."""
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt_date(ts: Optional[int]) -> str:
    """Convert a Unix timestamp to a YYYY-MM-DD date string, or '' if None."""
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


# Module-level instances
server = WeatherMCPServer()
mcp = server.mcp  # FastMCP CLI expects a module-level 'mcp' object

if __name__ == "__main__":
    server.main()
