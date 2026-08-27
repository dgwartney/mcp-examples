"""
FastMCP Server with OpenWeatherMap weather tools.

Demonstrates how to build an MCP server by subclassing
``AuthenticatedMCPServer`` and registering tools that query OpenWeatherMap's
free-tier APIs: Current Weather Data, 5 Day / 3 Hour Forecast, and Air
Pollution.

To use this server you need a free OpenWeatherMap API key:
    1. Sign up at https://openweathermap.org/api
    2. Export the key before starting the server:
           export OPENWEATHER_API_KEY=<your_key>

All three tools work on OpenWeatherMap's free tier — no subscription or
credit card required.

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    Run the server directly (stdio transport):
        $ OPENWEATHER_API_KEY=<key> uv run -m mcp_server_kit.weather

    Run as HTTP server:
        $ OPENWEATHER_API_KEY=<key> uv run -m mcp_server_kit.weather --transport streamable-http --port 8001

    Run with custom database path:
        $ MCP_DB_PATH=/var/data/keys.db OPENWEATHER_API_KEY=<key> uv run -m mcp_server_kit.weather
"""

import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastmcp.exceptions import ToolError

from mcp_server_kit.base import AuthenticatedMCPServer, lazy_module_instances

_BASE_URL = "https://api.openweathermap.org"
_GEO_URL = "https://api.openweathermap.org"
_USER_AGENT = "mcp-weather-example/1.0"

_AQI_LABELS = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}

_VALID_UNITS = {"metric", "imperial", "standard"}


class WeatherMCPServer(AuthenticatedMCPServer):
    """
    MCP server with OpenWeatherMap weather tools.

    Exposes three tools, all backed by OpenWeatherMap's free tier:
    - get_current_weather: current conditions via the Current Weather Data API
    - get_forecast: up to 5-day forecast via the 5 Day / 3 Hour Forecast API
      (3-hour data points aggregated into daily summaries)
    - get_air_quality: current AQI and pollutant levels via the Air Pollution API

    Requires the ``OPENWEATHER_API_KEY`` environment variable to be set.
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
                "the free Current Weather Data API. Returns temperature, humidity, "
                "wind, visibility, and a short description. "
                "location: city name (e.g. 'London'), city+country (e.g. 'Paris,FR'), "
                "or city+state+country for US cities (e.g. 'San Jose,CA,US'). "
                "units: 'metric' (Celsius), 'imperial' (Fahrenheit), 'standard' (Kelvin)."
            )
        )
        def get_current_weather(location: str, units: str = "metric") -> dict:
            """
            Retrieve current weather conditions for a location.

            Geocodes the location, then calls the free Current Weather Data API.

            Args:
                location: City name, optionally with country code
                          (e.g. 'London', 'Paris,FR', 'New York,US').
                units: Unit system — 'metric' (°C, m/s), 'imperial' (°F, mph),
                       or 'standard' (K, m/s). Defaults to 'metric'.

            Returns:
                Dict with keys: location, country, temperature, feels_like,
                temp_min, temp_max, humidity, pressure, wind_speed,
                wind_direction, description, visibility, sunrise, sunset.

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
                    f"{_BASE_URL}/data/2.5/weather",
                    params={
                        "lat": lat,
                        "lon": lon,
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
            main = d.get("main", {})
            wind = d.get("wind", {})
            sys_info = d.get("sys", {})
            weather_list = d.get("weather", [{}])
            return {
                "location": name,
                "country": country,
                "temperature": main.get("temp"),
                "feels_like": main.get("feels_like"),
                "temp_min": main.get("temp_min"),
                "temp_max": main.get("temp_max"),
                "humidity": main.get("humidity"),
                "pressure": main.get("pressure"),
                "wind_speed": wind.get("speed"),
                "wind_direction": wind.get("deg"),
                "description": weather_list[0].get("description", "") if weather_list else "",
                "visibility": d.get("visibility"),
                "sunrise": _fmt_utc(sys_info.get("sunrise")),
                "sunset": _fmt_utc(sys_info.get("sunset")),
            }

        @self.mcp.tool(
            description=(
                "Get a multi-day weather forecast for a city or location using "
                "the free 5 Day / 3 Hour Forecast API. Returns daily summaries "
                "with min/max temperature, description, humidity, and wind, "
                "aggregated from 3-hour interval data. "
                "location: city name (e.g. 'London'), city+country (e.g. 'Tokyo,JP'), "
                "or city+state+country for US cities (e.g. 'San Jose,CA,US'). "
                "days: number of days to return (1–5, default 5). "
                "units: 'metric' (Celsius), 'imperial' (Fahrenheit), 'standard' (Kelvin)."
            )
        )
        def get_forecast(location: str, days: int = 5, units: str = "metric") -> list[dict]:
            """
            Retrieve a multi-day weather forecast for a location.

            Uses the free 5 Day / 3 Hour Forecast API, which returns 3-hour
            interval data points (up to 40, covering 5 days). Entries are grouped
            by UTC calendar date and aggregated into daily summaries: temp_min/max
            are the min/max across that day's data points, and description/humidity/
            wind_speed are taken from the data point closest to midday UTC — a
            simplification, since this endpoint (unlike One Call) has no true
            daily-aggregate field.

            Args:
                location: City name, optionally with country code
                          (e.g. 'London', 'Tokyo,JP').
                days: Number of days to return (1–5, default 5).
                units: Unit system — 'metric', 'imperial', or 'standard'.
                       Defaults to 'metric'.

            Returns:
                List of dicts with keys: date, temp_min, temp_max, description,
                humidity, wind_speed.

            Raises:
                ToolError: If the API key is missing, the location is not found,
                           or the request fails.
            """
            self._check_api_key()
            if units not in _VALID_UNITS:
                raise ToolError(
                    f"Invalid units '{units}'. Must be one of: metric, imperial, standard."
                )
            days = max(1, min(days, 5))
            lat, lon, _name, _country = self._geocode(location)
            try:
                resp = self._http.get(
                    f"{_BASE_URL}/data/2.5/forecast",
                    params={
                        "lat": lat,
                        "lon": lon,
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

            entries = resp.json().get("list", [])
            by_date: dict = {}
            for entry in entries:
                dt = entry.get("dt")
                if dt is None:
                    continue
                date_key = datetime.fromtimestamp(dt, tz=timezone.utc).date()
                by_date.setdefault(date_key, []).append(entry)

            results = []
            for date_key in sorted(by_date)[:days]:
                day_entries = by_date[date_key]
                temp_mins = [
                    (e.get("main") or {}).get("temp_min") for e in day_entries
                    if (e.get("main") or {}).get("temp_min") is not None
                ]
                temp_maxs = [
                    (e.get("main") or {}).get("temp_max") for e in day_entries
                    if (e.get("main") or {}).get("temp_max") is not None
                ]
                midday_entry = min(
                    day_entries,
                    key=lambda e: abs(
                        datetime.fromtimestamp(e["dt"], tz=timezone.utc).hour - 12
                    ),
                )
                weather_list = midday_entry.get("weather") or [{}]
                results.append({
                    "date": _fmt_date(midday_entry.get("dt")),
                    "temp_min": min(temp_mins) if temp_mins else None,
                    "temp_max": max(temp_maxs) if temp_maxs else None,
                    "description": weather_list[0].get("description", "") if weather_list else "",
                    "humidity": (midday_entry.get("main") or {}).get("humidity"),
                    "wind_speed": (midday_entry.get("wind") or {}).get("speed"),
                })
            return results

        @self.mcp.tool(
            description=(
                "Get the current air quality index (AQI) and key pollutant levels "
                "for a city or location. AQI scale: 1=Good, 2=Fair, 3=Moderate, "
                "4=Poor, 5=Very Poor. Uses the free Air Pollution API. "
                "location: city name (e.g. 'Beijing'), city+country (e.g. 'London,GB'), "
                "or city+state+country for US cities (e.g. 'Los Angeles,CA,US')."
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

    def close(self) -> None:
        """Close the underlying ``httpx.Client``."""
        self._http.close()

    def _check_api_key(self) -> None:
        if not self._api_key:
            raise ToolError(
                "OpenWeatherMap API key is not configured. "
                "Sign up at https://openweathermap.org/api, then set the "
                "OPENWEATHER_API_KEY environment variable."
            )

    def _geocode(self, location: str) -> tuple[float, float, str, str]:
        """Return (lat, lon, city_name, country) for a location string."""
        # Normalize spaces around commas: "San Jose, CA" → "San Jose,CA"
        location = ",".join(part.strip() for part in location.split(","))
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


# Lazy module-level ``server`` / ``mcp`` — built on first attribute access, not
# on import, so ``import mcp_server_kit.weather`` performs no database I/O.
__getattr__ = lazy_module_instances(WeatherMCPServer)

if __name__ == "__main__":
    WeatherMCPServer().main()
