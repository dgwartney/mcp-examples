"""
Unit tests for mcp_server_kit._template

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import os
import tempfile

import pytest

from mcp_server_kit.database import DatabaseManager
from mcp_server_kit._template import TemplateMCPServer


def _tool_fn(server, name):
    """Extract the raw callable from a registered FastMCP tool."""
    return server.mcp._tool_manager._tools[name].fn


@pytest.fixture
def temp_db_path():
    """Create a temporary database file path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


class TestTemplateMCPServer:
    """Test suite for TemplateMCPServer class."""

    def test_server_name(self, temp_db_path):
        server = TemplateMCPServer(db_path=temp_db_path)
        assert server.mcp.name == "MyMCP"

    def test_one_tool_registered(self, temp_db_path):
        server = TemplateMCPServer(db_path=temp_db_path)
        assert len(server.mcp._tool_manager._tools) == 1

    def test_tool_names(self, temp_db_path):
        server = TemplateMCPServer(db_path=temp_db_path)
        assert set(server.mcp._tool_manager._tools) == {"example_tool"}

    def test_db_manager_created(self, temp_db_path):
        server = TemplateMCPServer(db_path=temp_db_path)
        assert isinstance(server.db_manager, DatabaseManager)

    def test_example_tool_functionality(self, temp_db_path):
        server = TemplateMCPServer(db_path=temp_db_path)
        result = _tool_fn(server, "example_tool")(text="hello")
        assert result == "You said: hello"

    def test_module_level_server_instance(self):
        import mcp_server_kit._template as template_module
        assert isinstance(template_module.server, TemplateMCPServer)

    def test_module_level_mcp_instance(self):
        import mcp_server_kit._template as template_module
        assert template_module.mcp is template_module.server.mcp
