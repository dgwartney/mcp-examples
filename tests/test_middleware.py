"""
Unit tests for mcp_server_kit.middleware

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

from unittest.mock import MagicMock, AsyncMock

import pytest
from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.middleware import Middleware

from mcp_server_kit.database import DatabaseManager
from mcp_server_kit.middleware import ApiKeyMiddleware


def _make_app(db_manager):
    """Create a minimal Starlette app with ApiKeyMiddleware for testing."""

    async def homepage(request: Request):
        return Response("ok", media_type="text/plain")

    return Starlette(
        routes=[Route("/", homepage)],
        middleware=[Middleware(ApiKeyMiddleware, db_manager=db_manager)],
    )


class TestApiKeyMiddleware:
    """Test suite for ApiKeyMiddleware class."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock DatabaseManager."""
        manager = MagicMock(spec=DatabaseManager)
        return manager

    @pytest.fixture
    def client(self, mock_db_manager):
        """Create a test client with the middleware-protected app."""
        app = _make_app(mock_db_manager)
        return TestClient(app)

    def test_init(self, mock_db_manager):
        """Test ApiKeyMiddleware stores db_manager."""
        app = _make_app(mock_db_manager)
        # Middleware is constructed lazily by Starlette; verify it works
        mock_db_manager.validate_key.return_value = True
        client = TestClient(app)
        resp = client.get("/", headers={"x-api-key": "key"})
        assert resp.status_code == 200

    def test_valid_key(self, client, mock_db_manager):
        """Test middleware allows valid API keys."""
        mock_db_manager.validate_key.return_value = True

        resp = client.get("/", headers={"X-API-Key": "valid-key"})

        assert resp.status_code == 200
        assert resp.text == "ok"
        mock_db_manager.validate_key.assert_called_once_with("valid-key")

    def test_invalid_key(self, client, mock_db_manager):
        """Test middleware rejects invalid API keys with HTTP 401."""
        mock_db_manager.validate_key.return_value = False

        resp = client.get("/", headers={"X-API-Key": "invalid-key"})

        assert resp.status_code == 401
        assert "Unauthorized" in resp.json()["error"]

    def test_missing_key(self, client, mock_db_manager):
        """Test middleware rejects requests without API key with HTTP 401."""
        mock_db_manager.validate_key.return_value = False

        resp = client.get("/")

        assert resp.status_code == 401
        assert "Unauthorized" in resp.json()["error"]

    def test_case_insensitive_lowercase(self, client, mock_db_manager):
        """Test middleware handles lowercase x-api-key header."""
        mock_db_manager.validate_key.return_value = True

        resp = client.get("/", headers={"x-api-key": "valid-key"})

        assert resp.status_code == 200
        mock_db_manager.validate_key.assert_called_once_with("valid-key")

    def test_case_insensitive_mixed(self, client, mock_db_manager):
        """Test middleware handles mixed case X-Api-Key header."""
        mock_db_manager.validate_key.return_value = True

        resp = client.get("/", headers={"X-Api-Key": "valid-key"})

        assert resp.status_code == 200
        mock_db_manager.validate_key.assert_called_once_with("valid-key")

    def test_case_insensitive_uppercase(self, client, mock_db_manager):
        """Test middleware handles uppercase X-API-KEY header."""
        mock_db_manager.validate_key.return_value = True

        resp = client.get("/", headers={"X-API-KEY": "valid-key"})

        assert resp.status_code == 200
        mock_db_manager.validate_key.assert_called_once_with("valid-key")

    def test_multiple_headers(self, client, mock_db_manager):
        """Test middleware extracts API key from multiple headers."""
        mock_db_manager.validate_key.return_value = True

        resp = client.get("/", headers={
            "Content-Type": "application/json",
            "X-API-Key": "valid-key",
            "User-Agent": "test-client",
        })

        assert resp.status_code == 200
        mock_db_manager.validate_key.assert_called_once_with("valid-key")
