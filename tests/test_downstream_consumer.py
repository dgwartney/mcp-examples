"""
Downstream-consumer test (plan E1).

Proves the *published* mcp-server-kit package can be used, from its public API
alone, to build a working authenticated MCP server from scratch — the true
"from scratch" acceptance test. Uses only names a `uv pip install mcp-server-kit`
user would have: ``mcp_server_kit.AuthenticatedMCPServer`` and
``mcp_server_kit.DatabaseManager``.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import subprocess
import sys

import httpx
import pytest
from fastmcp import Client

from mcp_server_kit import AuthenticatedMCPServer, DatabaseManager


class ConsumerServer(AuthenticatedMCPServer):
    """A minimal server a downstream user might write."""

    def _register_tools(self) -> None:
        @self.mcp.tool(description="Add two numbers")
        def add(a: int, b: int) -> int:
            return a + b


@pytest.mark.asyncio
async def test_consumer_tool_is_callable(tmp_path):
    """The public base class registers and runs a tool (in-memory transport)."""
    srv = ConsumerServer(db_path=str(tmp_path / "keys.db"))
    async with Client(srv.mcp) as client:
        tools = {t.name for t in await client.list_tools()}
        assert "add" in tools
        result = await client.call_tool("add", {"a": 2, "b": 3})
        assert result.data == 5


def _build_http_app(srv: AuthenticatedMCPServer):
    return srv.mcp.http_app(
        path="/mcp",
        middleware=srv._http_middleware,
        transport="streamable-http",
    )


@pytest.mark.asyncio
async def test_http_requires_api_key(tmp_path):
    """Requests without a valid X-API-Key are rejected by ApiKeyMiddleware."""
    db_path = str(tmp_path / "keys.db")
    srv = ConsumerServer(db_path=db_path)
    app = _build_http_app(srv)
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await client.post("/mcp", json=body)
            assert resp.status_code == 401


@pytest.mark.asyncio
async def test_http_accepts_valid_api_key(tmp_path):
    """A key seeded via the public DatabaseManager is accepted over HTTP."""
    db_path = str(tmp_path / "keys.db")
    manager = DatabaseManager(db_path)
    generated_key = manager.init_db()
    assert generated_key is not None  # init_db returns the generated key

    srv = ConsumerServer(db_path=db_path)
    app = _build_http_app(srv)
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }
    headers = {
        "X-API-Key": generated_key,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await client.post("/mcp", json=init, headers=headers)
            assert resp.status_code == 200


def test_import_creates_no_db_and_prints_no_secret(tmp_path):
    """Importing the package/submodules in an empty dir writes no db, leaks no key."""
    code = (
        "import mcp_server_kit, mcp_server_kit.contacts, mcp_server_kit.weather, "
        "mcp_server_kit.combined, mcp_server_kit.server; "
        "print('VERSION', mcp_server_kit.__version__)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "VERSION" in result.stdout
    assert "Generated default API key" not in result.stdout
    assert not list(tmp_path.glob("*.db"))
