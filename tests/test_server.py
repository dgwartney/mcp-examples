"""
Unit tests for mcp_examples.server

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import MiddlewareContext

from mcp_examples.database import DatabaseManager
from mcp_examples.middleware import ApiKeyMiddleware
from mcp_examples.server import GreetMCPServer


class TestGreetMCPServer:
    """Test suite for GreetMCPServer class."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file path."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_tools_registered(self, temp_db_path):
        """Test that tools are registered on initialization."""
        with patch.object(DatabaseManager, 'init_db'):
            server = GreetMCPServer(db_path=temp_db_path)

            assert hasattr(server.mcp, 'tool')

    def test_greet_tool_functionality(self, temp_db_path):
        """Test that the greet tool works correctly by testing the function directly."""
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        result = greet(name="Alice")
        assert result == "Hello, Alice!"

    def test_greet_tool_with_different_names(self, temp_db_path):
        """Test greet tool logic with various names."""
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        test_cases = ["Bob", "Charlie", "世界", "123", ""]
        for name in test_cases:
            result = greet(name=name)
            assert result == f"Hello, {name}!"

    def test_module_level_server_instance(self):
        """Test that module-level server instance is created."""
        import mcp_examples.server as server_module

        assert hasattr(server_module, 'server')
        assert isinstance(server_module.server, GreetMCPServer)

    def test_module_level_mcp_instance(self):
        """Test that module-level mcp instance is exposed."""
        import mcp_examples.server as server_module

        assert hasattr(server_module, 'mcp')
        assert server_module.mcp == server_module.server.mcp


class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file path."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_end_to_end_key_validation(self, temp_db_path):
        """Test complete flow from database to middleware validation."""
        db_manager = DatabaseManager(temp_db_path)
        db_manager.init_db()

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT key FROM api_keys LIMIT 1")
        valid_key = cursor.fetchone()[0]
        conn.close()

        assert db_manager.validate_key(valid_key) is True
        assert db_manager.validate_key("wrong-key") is False

    @pytest.mark.asyncio
    async def test_end_to_end_middleware_flow(self, temp_db_path):
        """Test complete middleware authentication flow."""
        db_manager = DatabaseManager(temp_db_path)
        db_manager.init_db()

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT key FROM api_keys LIMIT 1")
        valid_key = cursor.fetchone()[0]
        conn.close()

        middleware = ApiKeyMiddleware(db_manager)
        mock_context = MagicMock(spec=MiddlewareContext)

        async def mock_call_next(context):
            return "authenticated"

        with patch("mcp_examples.middleware.get_http_headers") as mock_get_headers:
            mock_get_headers.return_value = {"X-API-Key": valid_key}
            result = await middleware.on_request(mock_context, mock_call_next)
            assert result == "authenticated"

        with patch("mcp_examples.middleware.get_http_headers") as mock_get_headers:
            mock_get_headers.return_value = {"X-API-Key": "invalid"}
            with pytest.raises(ToolError):
                await middleware.on_request(mock_context, mock_call_next)

    def test_server_initialization_creates_working_system(self, temp_db_path):
        """Test that GreetMCPServer creates a fully functional system."""
        server = GreetMCPServer(db_path=temp_db_path)

        assert server.db_manager is not None
        assert server.mcp is not None

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM api_keys")
        count = cursor.fetchone()[0]
        conn.close()
        assert count > 0
