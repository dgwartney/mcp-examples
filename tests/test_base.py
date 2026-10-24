"""
Unit tests for mcp_server_kit.base

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import asyncio
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from mcp_server_kit.base import AuthenticatedMCPServer
from mcp_server_kit.database import DatabaseManager
from mcp_server_kit.middleware import ApiKeyMiddleware


class StubMCPServer(AuthenticatedMCPServer):
    """Minimal concrete subclass for testing the abstract base class."""

    def _register_tools(self):
        pass


class StubMCPServerWithHttp(AuthenticatedMCPServer):
    """Subclass with an ``_http`` attribute, like messaging/weather/wikipedia."""

    def __init__(self, *args, **kwargs):
        self._http = MagicMock()
        super().__init__(*args, **kwargs)

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

    def test_close_is_noop_without_http_attribute(self, temp_db_path):
        """Test that close() does nothing when the subclass has no _http."""
        with patch.object(DatabaseManager, 'init_db'):
            server = StubMCPServer(db_path=temp_db_path)
            server.close()  # must not raise

    def test_close_closes_http_attribute(self, temp_db_path):
        """Test that close() closes self._http when a subclass sets one."""
        with patch.object(DatabaseManager, 'init_db'):
            server = StubMCPServerWithHttp(db_path=temp_db_path)
            server.close()
            server._http.close.assert_called_once()

    def test_run_method_exists(self, temp_db_path):
        """Test that run method exists and is callable."""
        with patch.object(DatabaseManager, 'init_db'):
            server = StubMCPServer(db_path=temp_db_path)

            assert hasattr(server, 'run')
            assert callable(server.run)

    def test_run_stdio_does_not_add_middleware(self, temp_db_path):
        """Test that stdio transport does not inject HTTP middleware."""
        with patch.object(DatabaseManager, 'init_db'):
            server = StubMCPServer(db_path=temp_db_path)
            with patch.object(server.mcp, 'run') as mock_run:
                server.run()
                kwargs = mock_run.call_args[1] if mock_run.call_args else {}
                assert "middleware" not in kwargs

    def test_run_http_transport_adds_middleware(self, temp_db_path):
        """Test that streamable-http transport injects API key middleware."""
        with patch.object(DatabaseManager, 'init_db'):
            server = StubMCPServer(db_path=temp_db_path)
            with patch.object(server.mcp, 'run') as mock_run:
                server.run(transport="streamable-http", host="127.0.0.1", port=8000)
                kwargs = mock_run.call_args[1]
                assert "middleware" in kwargs
                assert len(kwargs["middleware"]) == 1
                assert kwargs["middleware"][0].cls is ApiKeyMiddleware

    def test_run_sse_transport_adds_middleware(self, temp_db_path):
        """Test that sse transport also injects middleware."""
        with patch.object(DatabaseManager, 'init_db'):
            server = StubMCPServer(db_path=temp_db_path)
            with patch.object(server.mcp, 'run') as mock_run:
                server.run(transport="sse")
                kwargs = mock_run.call_args[1]
                assert "middleware" in kwargs

    def test_main_stdio_calls_run_with_no_args(self, temp_db_path):
        """Test that main() with --transport stdio calls run() with no args."""
        with patch.object(DatabaseManager, 'init_db'):
            server = StubMCPServer(db_path=temp_db_path)
            with patch.object(server, 'run') as mock_run, \
                 patch('sys.argv', ['prog']):
                server.main()
                mock_run.assert_called_once_with()

    def test_main_http_transport_passes_args(self, temp_db_path):
        """Test that main() with streamable-http passes transport/host/port."""
        with patch.object(DatabaseManager, 'init_db'):
            server = StubMCPServer(db_path=temp_db_path)
            with patch.object(server, 'run') as mock_run, \
                 patch('sys.argv', ['prog', '--transport', 'streamable-http',
                                    '--port', '9000', '--host', '0.0.0.0']):
                server.main()
                mock_run.assert_called_once_with(
                    transport='streamable-http', host='0.0.0.0', port=9000
                )


class StubMCPServerAllPrimitives(AuthenticatedMCPServer):
    """Subclass that registers a tool, a resource, a resource template and a prompt."""

    def __init__(self, *args, **kwargs):
        self.hook_calls = []
        super().__init__(*args, **kwargs)

    def _register_tools(self):
        self.hook_calls.append("tools")

        @self.mcp.tool
        def ping() -> str:
            return "pong"

    def _register_resources(self):
        self.hook_calls.append("resources")

        @self.mcp.resource("stub://info")
        def info() -> str:
            return "stub info"

        @self.mcp.resource("stub://echo/{text}")
        def echo(text: str) -> str:
            return text

    def _register_prompts(self):
        self.hook_calls.append("prompts")

        @self.mcp.prompt
        def ask(topic: str) -> str:
            return f"Tell me about {topic}."


def _list_primitives(mcp):
    """Return (tools, resources, templates, prompts) names via the public client."""
    from fastmcp import Client

    async def _list():
        async with Client(mcp) as client:
            return (
                {t.name for t in await client.list_tools()},
                {str(r.uri) for r in await client.list_resources()},
                {t.uriTemplate for t in await client.list_resource_templates()},
                {p.name for p in await client.list_prompts()},
            )

    return asyncio.run(_list())


class TestResourceAndPromptHooks:
    """The optional _register_resources() / _register_prompts() hooks."""

    def test_hooks_default_to_registering_nothing(self, tmp_path):
        server = StubMCPServer(db_path=str(tmp_path / "keys.db"))
        _tools, resources, templates, prompts = _list_primitives(server.mcp)
        assert (resources, templates, prompts) == (set(), set(), set())

    def test_hooks_run_once_in_order(self, tmp_path):
        server = StubMCPServerAllPrimitives(db_path=str(tmp_path / "keys.db"))
        assert server.hook_calls == ["tools", "resources", "prompts"]

    def test_all_primitives_are_served(self, tmp_path):
        server = StubMCPServerAllPrimitives(db_path=str(tmp_path / "keys.db"))
        tools, resources, templates, prompts = _list_primitives(server.mcp)
        assert tools == {"ping"}
        assert resources == {"stub://info"}
        assert templates == {"stub://echo/{text}"}
        assert prompts == {"ask"}

    def test_resource_template_and_prompt_render(self, tmp_path):
        from fastmcp import Client

        server = StubMCPServerAllPrimitives(db_path=str(tmp_path / "keys.db"))

        async def _check():
            async with Client(server.mcp) as client:
                echoed = await client.read_resource("stub://echo/hello")
                assert echoed[0].text == "hello"
                prompt = await client.get_prompt("ask", {"topic": "MCP"})
                assert prompt.messages[0].content.text == "Tell me about MCP."

        asyncio.run(_check())
