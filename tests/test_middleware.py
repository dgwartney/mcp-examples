"""
Unit tests for mcp_examples.middleware

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

from unittest.mock import MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import MiddlewareContext

from mcp_examples.database import DatabaseManager
from mcp_examples.middleware import ApiKeyMiddleware


class TestApiKeyMiddleware:
    """Test suite for ApiKeyMiddleware class."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock DatabaseManager."""
        manager = MagicMock(spec=DatabaseManager)
        return manager

    @pytest.fixture
    def middleware(self, mock_db_manager):
        """Create an ApiKeyMiddleware instance with mock database."""
        return ApiKeyMiddleware(mock_db_manager)

    @pytest.fixture
    def mock_context(self):
        """Create a mock MiddlewareContext."""
        return MagicMock(spec=MiddlewareContext)

    @pytest.fixture
    def mock_call_next(self):
        """Create a mock call_next function."""
        async def call_next(context):
            return "success"
        return call_next

    def test_init(self, mock_db_manager):
        """Test ApiKeyMiddleware initialization."""
        middleware = ApiKeyMiddleware(mock_db_manager)
        assert middleware.db_manager == mock_db_manager

    @pytest.mark.asyncio
    async def test_on_request_valid_key(self, middleware, mock_context, mock_call_next, mock_db_manager):
        """Test on_request allows valid API keys."""
        mock_db_manager.validate_key.return_value = True

        with patch("mcp_examples.middleware.get_http_headers") as mock_get_headers:
            mock_get_headers.return_value = {"X-API-Key": "valid-key"}

            result = await middleware.on_request(mock_context, mock_call_next)

            assert result == "success"
            mock_db_manager.validate_key.assert_called_once_with("valid-key")

    @pytest.mark.asyncio
    async def test_on_request_invalid_key(self, middleware, mock_context, mock_call_next, mock_db_manager):
        """Test on_request rejects invalid API keys."""
        mock_db_manager.validate_key.return_value = False

        with patch("mcp_examples.middleware.get_http_headers") as mock_get_headers:
            mock_get_headers.return_value = {"X-API-Key": "invalid-key"}

            with pytest.raises(ToolError, match="Unauthorized: Invalid or missing API Key"):
                await middleware.on_request(mock_context, mock_call_next)

    @pytest.mark.asyncio
    async def test_on_request_missing_key(self, middleware, mock_context, mock_call_next, mock_db_manager):
        """Test on_request rejects requests without API key."""
        mock_db_manager.validate_key.return_value = False

        with patch("mcp_examples.middleware.get_http_headers") as mock_get_headers:
            mock_get_headers.return_value = {}

            with pytest.raises(ToolError, match="Unauthorized: Invalid or missing API Key"):
                await middleware.on_request(mock_context, mock_call_next)

    @pytest.mark.asyncio
    async def test_on_request_case_insensitive_lowercase(self, middleware, mock_context, mock_call_next, mock_db_manager):
        """Test on_request handles lowercase x-api-key header."""
        mock_db_manager.validate_key.return_value = True

        with patch("mcp_examples.middleware.get_http_headers") as mock_get_headers:
            mock_get_headers.return_value = {"x-api-key": "valid-key"}

            result = await middleware.on_request(mock_context, mock_call_next)

            assert result == "success"
            mock_db_manager.validate_key.assert_called_once_with("valid-key")

    @pytest.mark.asyncio
    async def test_on_request_case_insensitive_mixed(self, middleware, mock_context, mock_call_next, mock_db_manager):
        """Test on_request handles mixed case X-Api-Key header."""
        mock_db_manager.validate_key.return_value = True

        with patch("mcp_examples.middleware.get_http_headers") as mock_get_headers:
            mock_get_headers.return_value = {"X-Api-Key": "valid-key"}

            result = await middleware.on_request(mock_context, mock_call_next)

            assert result == "success"
            mock_db_manager.validate_key.assert_called_once_with("valid-key")

    @pytest.mark.asyncio
    async def test_on_request_case_insensitive_uppercase(self, middleware, mock_context, mock_call_next, mock_db_manager):
        """Test on_request handles uppercase X-API-KEY header."""
        mock_db_manager.validate_key.return_value = True

        with patch("mcp_examples.middleware.get_http_headers") as mock_get_headers:
            mock_get_headers.return_value = {"X-API-KEY": "valid-key"}

            result = await middleware.on_request(mock_context, mock_call_next)

            assert result == "success"
            mock_db_manager.validate_key.assert_called_once_with("valid-key")

    @pytest.mark.asyncio
    async def test_on_request_multiple_headers(self, middleware, mock_context, mock_call_next, mock_db_manager):
        """Test on_request extracts API key from multiple headers."""
        mock_db_manager.validate_key.return_value = True

        with patch("mcp_examples.middleware.get_http_headers") as mock_get_headers:
            mock_get_headers.return_value = {
                "Content-Type": "application/json",
                "X-API-Key": "valid-key",
                "User-Agent": "test-client"
            }

            result = await middleware.on_request(mock_context, mock_call_next)

            assert result == "success"
            mock_db_manager.validate_key.assert_called_once_with("valid-key")
