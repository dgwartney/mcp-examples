"""
Unit tests for mcp_server_kit._template

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import asyncio
import os
import tempfile

import pytest
from fastmcp import Client

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

    def test_resources_and_template_registered(self, temp_db_path):
        server = TemplateMCPServer(db_path=temp_db_path)

        async def _check():
            async with Client(server.mcp) as client:
                resources = {str(r.uri) for r in await client.list_resources()}
                templates = {t.uriTemplate for t in await client.list_resource_templates()}
                assert resources == {"example://info"}
                assert templates == {"example://echo/{text}"}

        asyncio.run(_check())

    def test_example_resources_read(self, temp_db_path):
        server = TemplateMCPServer(db_path=temp_db_path)

        async def _check():
            async with Client(server.mcp) as client:
                info = await client.read_resource("example://info")
                assert info[0].text == "Example resource — replace with your own data"
                echoed = await client.read_resource("example://echo/hello")
                assert echoed[0].text == "You said: hello"

        asyncio.run(_check())

    def test_example_prompt_renders(self, temp_db_path):
        server = TemplateMCPServer(db_path=temp_db_path)

        async def _check():
            async with Client(server.mcp) as client:
                assert {p.name for p in await client.list_prompts()} == {"example_prompt"}
                prompt = await client.get_prompt("example_prompt", {"topic": "MCP"})
                assert prompt.messages[0].content.text == "Write a short explanation of MCP."

        asyncio.run(_check())
