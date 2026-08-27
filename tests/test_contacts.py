"""
Unit tests for mcp_server_kit.contacts

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import os
import tempfile
from unittest.mock import patch

import pytest
from fastmcp.exceptions import ToolError

from mcp_server_kit.contact_database import ContactDatabaseManager
from mcp_server_kit.database import DatabaseManager
from mcp_server_kit.contacts import ContactMCPServer


class TestContactMCPServer:
    """Test suite for ContactMCPServer class."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file path for API keys."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def temp_contact_db_path(self):
        """Create a temporary database file path for contacts."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def server(self, temp_db_path, temp_contact_db_path):
        """Create a ContactMCPServer instance with temp databases."""
        return ContactMCPServer(
            db_path=temp_db_path,
            contact_db_path=temp_contact_db_path,
        )

    def test_four_tools_registered(self, server):
        """Test that exactly 4 tools are registered."""
        tools = server.mcp._tool_manager._tools
        assert len(tools) == 4

    def test_tool_names(self, server):
        """Test that the expected tool names are registered."""
        tool_names = set(server.mcp._tool_manager._tools.keys())
        expected = {
            "search_by_last_name",
            "search_by_email",
            "search_by_account_id",
            "authenticate",
        }
        assert tool_names == expected

    def test_server_has_contact_db(self, server):
        """Test that the server has a contact database manager."""
        assert isinstance(server.contact_db, ContactDatabaseManager)

    def test_server_has_api_key_db(self, server):
        """Test that the server has an API key database manager."""
        assert isinstance(server.db_manager, DatabaseManager)

    def test_module_level_server_instance(self):
        """Test that module-level server instance is created."""
        import mcp_server_kit.contacts as contacts_module

        assert hasattr(contacts_module, "server")
        assert isinstance(contacts_module.server, ContactMCPServer)

    def test_module_level_mcp_instance(self):
        """Test that module-level mcp instance is exposed."""
        import mcp_server_kit.contacts as contacts_module

        assert hasattr(contacts_module, "mcp")
        assert contacts_module.mcp == contacts_module.server.mcp


class TestContactMCPServerIntegration:
    """Integration tests for ContactMCPServer tools."""

    @pytest.fixture
    def temp_db_path(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def temp_contact_db_path(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def server(self, temp_db_path, temp_contact_db_path):
        return ContactMCPServer(
            db_path=temp_db_path,
            contact_db_path=temp_contact_db_path,
        )

    def test_search_by_last_name_delegates(self, server):
        """Test that the tool delegates to ContactDatabaseManager."""
        results = server.contact_db.search_by_last_name("web")
        assert len(results) == 2

    def test_search_by_email_delegates(self, server):
        """Test that the tool delegates to ContactDatabaseManager."""
        results = server.contact_db.search_by_email("daniel.reyes@meridiancorp.com")
        assert len(results) == 1
        assert results[0]["FirstName"] == "Daniel"

    def test_search_by_account_id_delegates(self, server):
        """Test that the tool delegates to ContactDatabaseManager."""
        results = server.contact_db.search_by_account_id("MC-001")
        assert len(results) == 4

    def test_authenticate_delegates_success(self, server):
        """Test that authenticate delegates correctly for valid credentials."""
        result = server.contact_db.authenticate("james.whitfield@meridiancorp.com", "password123")
        assert result is not None
        assert result["FirstName"] == "James"
        assert "Password" not in result

    def test_authenticate_delegates_failure(self, server):
        """Test that authenticate returns None for invalid credentials."""
        result = server.contact_db.authenticate("james.whitfield@meridiancorp.com", "wrong")
        assert result is None


class TestContactMCPServerToolFunctions:
    """Tests that invoke the registered tool closures directly."""

    @pytest.fixture
    def temp_db_path(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def temp_contact_db_path(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def server(self, temp_db_path, temp_contact_db_path):
        return ContactMCPServer(
            db_path=temp_db_path,
            contact_db_path=temp_contact_db_path,
        )

    def _tool(self, server, name):
        return server.mcp._tool_manager._tools[name].fn

    def test_search_by_last_name_tool_returns_results(self, server):
        """Invoke the search_by_last_name tool closure directly."""
        results = self._tool(server, "search_by_last_name")(last_name="web")
        assert len(results) == 2
        assert all("web" in r["LastName"].lower() for r in results)

    def test_search_by_email_tool_returns_result(self, server):
        """Invoke the search_by_email tool closure directly."""
        results = self._tool(server, "search_by_email")(email="daniel.reyes@meridiancorp.com")
        assert len(results) == 1
        assert results[0]["FirstName"] == "Daniel"

    def test_search_by_account_id_tool_returns_results(self, server):
        """Invoke the search_by_account_id tool closure directly."""
        results = self._tool(server, "search_by_account_id")(account_id="MC-001")
        assert len(results) == 4

    def test_authenticate_tool_success(self, server):
        """Invoke the authenticate tool closure with valid credentials."""
        result = self._tool(server, "authenticate")(
            email="james.whitfield@meridiancorp.com", password="password123"
        )
        assert result["FirstName"] == "James"
        assert "Password" not in result

    def test_authenticate_tool_failure_raises_tool_error(self, server):
        """Invoke the authenticate tool closure with bad credentials."""
        with pytest.raises(ToolError, match="Authentication failed"):
            self._tool(server, "authenticate")(
                email="james.whitfield@meridiancorp.com", password="wrongpassword"
            )

    def test_search_by_last_name_empty_raises_tool_error(self, server):
        """An empty last_name would otherwise wildcard-match every contact."""
        with pytest.raises(ToolError, match="last_name must not be empty"):
            self._tool(server, "search_by_last_name")(last_name="")

    def test_search_by_email_empty_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="email must not be empty"):
            self._tool(server, "search_by_email")(email="")

    def test_search_by_account_id_empty_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="account_id must not be empty"):
            self._tool(server, "search_by_account_id")(account_id="")
