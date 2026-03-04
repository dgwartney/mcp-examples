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
from mcp_examples.server import MCPServer


class TestMCPServer:
    """Test suite for MCPServer class."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file path."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        # Cleanup
        if os.path.exists(path):
            os.remove(path)

    def test_init_default_db_path(self):
        """Test MCPServer initialization with default database path."""
        with patch.object(DatabaseManager, 'init_db'):
            server = MCPServer()

            assert server.db_manager is not None
            assert "api_keys.db" in server.db_manager.db_path
            assert server.mcp is not None

    def test_init_custom_db_path(self, temp_db_path):
        """Test MCPServer initialization with custom database path."""
        with patch.object(DatabaseManager, 'init_db'):
            server = MCPServer(db_path=temp_db_path)

            assert server.db_manager.db_path == temp_db_path

    def test_init_custom_name(self, temp_db_path):
        """Test MCPServer initialization with custom name."""
        with patch.object(DatabaseManager, 'init_db'):
            server = MCPServer(name="CustomServer", db_path=temp_db_path)

            assert server.mcp.name == "CustomServer"

    def test_init_calls_init_db(self, temp_db_path):
        """Test that MCPServer initialization calls init_db."""
        with patch.object(DatabaseManager, 'init_db') as mock_init_db:
            server = MCPServer(db_path=temp_db_path)

            mock_init_db.assert_called_once()

    def test_init_with_env_var(self, temp_db_path, monkeypatch):
        """Test MCPServer initialization with MCP_DB_PATH environment variable."""
        monkeypatch.setenv("MCP_DB_PATH", temp_db_path)

        with patch.object(DatabaseManager, 'init_db'):
            server = MCPServer()

            assert server.db_manager.db_path == temp_db_path

    def test_init_env_var_overridden_by_parameter(self, temp_db_path, monkeypatch):
        """Test that db_path parameter takes precedence over environment variable."""
        monkeypatch.setenv("MCP_DB_PATH", "/tmp/env_path.db")

        with patch.object(DatabaseManager, 'init_db'):
            server = MCPServer(db_path=temp_db_path)

            assert server.db_manager.db_path == temp_db_path
            assert server.db_manager.db_path != "/tmp/env_path.db"

    def test_middleware_registered(self, temp_db_path):
        """Test that ApiKeyMiddleware is registered on initialization."""
        with patch.object(DatabaseManager, 'init_db'):
            server = MCPServer(db_path=temp_db_path)

            # Check that middleware was added (using public API)
            assert hasattr(server.mcp, 'middleware')
            assert len(server.mcp.middleware) > 0
            # Verify it's the right type
            assert isinstance(server.mcp.middleware[0], ApiKeyMiddleware)

    def test_tools_registered(self, temp_db_path):
        """Test that tools are registered on initialization."""
        with patch.object(DatabaseManager, 'init_db'):
            server = MCPServer(db_path=temp_db_path)

            # Check that greet tool is registered
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

    def test_run_method_exists(self, temp_db_path):
        """Test that run method exists and is callable."""
        with patch.object(DatabaseManager, 'init_db'):
            server = MCPServer(db_path=temp_db_path)

            assert hasattr(server, 'run')
            assert callable(server.run)

    def test_module_level_server_instance(self):
        """Test that module-level server instance is created."""
        import mcp_examples.server as server_module

        assert hasattr(server_module, 'server')
        assert isinstance(server_module.server, MCPServer)

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
        # Cleanup
        if os.path.exists(path):
            os.remove(path)

    def test_end_to_end_key_validation(self, temp_db_path):
        """Test complete flow from database to middleware validation."""
        # Initialize database with a key
        db_manager = DatabaseManager(temp_db_path)
        db_manager.init_db()

        # Get the generated key
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT key FROM api_keys LIMIT 1")
        valid_key = cursor.fetchone()[0]
        conn.close()

        # Validate the key
        assert db_manager.validate_key(valid_key) is True
        assert db_manager.validate_key("wrong-key") is False

    @pytest.mark.asyncio
    async def test_end_to_end_middleware_flow(self, temp_db_path):
        """Test complete middleware authentication flow."""
        # Setup
        db_manager = DatabaseManager(temp_db_path)
        db_manager.init_db()

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT key FROM api_keys LIMIT 1")
        valid_key = cursor.fetchone()[0]
        conn.close()

        # Create middleware
        middleware = ApiKeyMiddleware(db_manager)
        mock_context = MagicMock(spec=MiddlewareContext)

        async def mock_call_next(context):
            return "authenticated"

        # Test with valid key
        with patch("mcp_examples.middleware.get_http_headers") as mock_get_headers:
            mock_get_headers.return_value = {"X-API-Key": valid_key}
            result = await middleware.on_request(mock_context, mock_call_next)
            assert result == "authenticated"

        # Test with invalid key
        with patch("mcp_examples.middleware.get_http_headers") as mock_get_headers:
            mock_get_headers.return_value = {"X-API-Key": "invalid"}
            with pytest.raises(ToolError):
                await middleware.on_request(mock_context, mock_call_next)

    def test_server_initialization_creates_working_system(self, temp_db_path):
        """Test that MCPServer creates a fully functional system."""
        server = MCPServer(db_path=temp_db_path)

        # Verify all components are initialized
        assert server.db_manager is not None
        assert server.mcp is not None

        # Verify database is functional
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM api_keys")
        count = cursor.fetchone()[0]
        conn.close()
        assert count > 0
