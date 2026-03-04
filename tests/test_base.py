"""
Unit tests for mcp_examples.base

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import os
import tempfile
from unittest.mock import patch

import pytest

from mcp_examples.base import AuthenticatedMCPServer
from mcp_examples.database import DatabaseManager
from mcp_examples.middleware import ApiKeyMiddleware


class StubMCPServer(AuthenticatedMCPServer):
    """Minimal concrete subclass for testing the abstract base class."""

    def _register_tools(self):
        pass


class TestAuthenticatedMCPServer:
    """Test suite for AuthenticatedMCPServer abstract base class."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file path."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_cannot_instantiate_abstract_class(self):
        """Test that AuthenticatedMCPServer cannot be instantiated directly."""
        with patch.object(DatabaseManager, 'init_db'):
            with pytest.raises(TypeError):
                AuthenticatedMCPServer()

    def test_init_default_db_path(self):
        """Test initialization with default database path."""
        with patch.object(DatabaseManager, 'init_db'):
            server = StubMCPServer()

            assert server.db_manager is not None
            assert "api_keys.db" in server.db_manager.db_path
            assert server.mcp is not None

    def test_init_custom_db_path(self, temp_db_path):
        """Test initialization with custom database path."""
        with patch.object(DatabaseManager, 'init_db'):
            server = StubMCPServer(db_path=temp_db_path)

            assert server.db_manager.db_path == temp_db_path

    def test_init_custom_name(self, temp_db_path):
        """Test initialization with custom name."""
        with patch.object(DatabaseManager, 'init_db'):
            server = StubMCPServer(name="CustomServer", db_path=temp_db_path)

            assert server.mcp.name == "CustomServer"

    def test_init_calls_init_db(self, temp_db_path):
        """Test that initialization calls init_db."""
        with patch.object(DatabaseManager, 'init_db') as mock_init_db:
            StubMCPServer(db_path=temp_db_path)

            mock_init_db.assert_called_once()

    def test_init_with_env_var(self, temp_db_path, monkeypatch):
        """Test initialization with MCP_DB_PATH environment variable."""
        monkeypatch.setenv("MCP_DB_PATH", temp_db_path)

        with patch.object(DatabaseManager, 'init_db'):
            server = StubMCPServer()

            assert server.db_manager.db_path == temp_db_path

    def test_init_env_var_overridden_by_parameter(self, temp_db_path, monkeypatch):
        """Test that db_path parameter takes precedence over environment variable."""
        monkeypatch.setenv("MCP_DB_PATH", "/tmp/env_path.db")

        with patch.object(DatabaseManager, 'init_db'):
            server = StubMCPServer(db_path=temp_db_path)

            assert server.db_manager.db_path == temp_db_path
            assert server.db_manager.db_path != "/tmp/env_path.db"

    def test_middleware_registered(self, temp_db_path):
        """Test that HTTP middleware is registered on initialization."""
        with patch.object(DatabaseManager, 'init_db'):
            server = StubMCPServer(db_path=temp_db_path)

            assert hasattr(server, '_http_middleware')
            assert len(server._http_middleware) > 0
            assert server._http_middleware[0].cls is ApiKeyMiddleware

    def test_run_method_exists(self, temp_db_path):
        """Test that run method exists and is callable."""
        with patch.object(DatabaseManager, 'init_db'):
            server = StubMCPServer(db_path=temp_db_path)

            assert hasattr(server, 'run')
            assert callable(server.run)
