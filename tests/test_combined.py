"""
Unit tests for mcp_examples.combined

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

from unittest.mock import MagicMock

import pytest
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

import mcp_examples.combined as combined


class FakeServer:
    """Stand-in for an AuthenticatedMCPServer subclass, avoiding real DB/tool setup."""

    def __init__(self):
        self._http_middleware = ["mw"]
        self.mcp = MagicMock()
        self.mcp.http_app.return_value = MagicMock()


class TestServerRegistry:

    def test_registry_has_five_entries(self):
        assert len(combined.SERVER_REGISTRY) == 5

    def test_registry_prefixes(self):
        prefixes = [prefix for prefix, _ in combined.SERVER_REGISTRY]
        assert prefixes == ["greet", "contacts", "wikipedia", "weather", "twilio"]


class TestBuild:

    def test_build_creates_one_route_per_registry_entry(self, monkeypatch):
        monkeypatch.setattr(
            combined,
            "SERVER_REGISTRY",
            [("one", FakeServer), ("two", FakeServer)],
        )
        routes, sub_apps = combined._build()
        assert len(routes) == 2
        assert len(sub_apps) == 2

    def test_build_mounts_at_registry_prefix(self, monkeypatch):
        monkeypatch.setattr(combined, "SERVER_REGISTRY", [("foo", FakeServer)])
        routes, _ = combined._build()
        assert isinstance(routes[0], Mount)
        assert routes[0].path == "/foo"

    def test_build_passes_server_middleware_to_http_app(self, monkeypatch):
        monkeypatch.setattr(combined, "SERVER_REGISTRY", [("foo", FakeServer)])
        instances = []

        class TrackedFakeServer(FakeServer):
            def __init__(self):
                super().__init__()
                instances.append(self)

        monkeypatch.setattr(combined, "SERVER_REGISTRY", [("foo", TrackedFakeServer)])
        combined._build()
        srv = instances[0]
        srv.mcp.http_app.assert_called_once_with(
            path="/mcp",
            middleware=srv._http_middleware,
            transport="streamable-http",
        )

    def test_build_real_registry_produces_five_routes(self):
        routes, sub_apps = combined._build()
        assert len(routes) == 5
        assert len(sub_apps) == 5
        assert [r.path for r in routes] == [
            "/greet",
            "/contacts",
            "/wikipedia",
            "/weather",
            "/twilio",
        ]


class TestApp:

    def test_app_is_starlette_instance(self):
        assert isinstance(combined.app, Starlette)

    def test_app_has_route_for_each_registered_server(self):
        mounted_paths = {r.path for r in combined.app.routes}
        assert mounted_paths == {
            "/greet",
            "/contacts",
            "/wikipedia",
            "/weather",
            "/twilio",
        }

    def test_unmounted_path_returns_404(self):
        with TestClient(combined.app) as client:
            resp = client.get("/does-not-exist")
            assert resp.status_code == 404


class TestLifespan:

    @pytest.mark.asyncio
    async def test_lifespan_enters_and_exits_all_sub_app_lifespans(self):
        sub_app_1, sub_app_2 = MagicMock(), MagicMock()
        for sub_app in (sub_app_1, sub_app_2):
            sub_app.lifespan.return_value.__aenter__.return_value = None
            sub_app.lifespan.return_value.__aexit__.return_value = None

        original_sub_apps = combined._sub_apps
        combined._sub_apps = [sub_app_1, sub_app_2]
        try:
            async with combined._lifespan(MagicMock()):
                pass
        finally:
            combined._sub_apps = original_sub_apps

        for sub_app in (sub_app_1, sub_app_2):
            sub_app.lifespan.assert_called_once_with(sub_app)
            sub_app.lifespan.return_value.__aenter__.assert_awaited_once()
            sub_app.lifespan.return_value.__aexit__.assert_awaited_once()
