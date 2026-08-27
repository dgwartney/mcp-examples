"""
Abstract base class for authenticated MCP servers.

Provides API key authentication infrastructure so that subclasses only need
to implement ``_register_tools()`` to add their own MCP tools.

Author:
    David Gwartney <david.gwartney@gmail.com>

Environment Variables:
    MCP_DB_PATH: Optional path to SQLite database file.
                 Defaults to api_keys.db in the current working directory if not set.
"""

import argparse
import os
from abc import ABC, abstractmethod
from typing import Callable, Optional

from fastmcp import FastMCP
from starlette.middleware import Middleware as StarletteMiddleware

from mcp_server_kit.database import DatabaseManager
from mcp_server_kit.middleware import ApiKeyMiddleware


class AuthenticatedMCPServer(ABC):
    """
    Abstract base class for MCP servers with API key authentication.

    Handles database initialization, middleware registration, and delegates
    tool registration to subclasses via the ``_register_tools()`` hook.

    Attributes:
        db_manager (DatabaseManager): Manages API key database operations.
        mcp (FastMCP): The FastMCP server instance.
    """

    def __init__(self, name: str = "MyMCP", db_path: Optional[str] = None):
        """
        Initialize the authenticated MCP server.

        Args:
            name (str, optional): Name of the MCP server. Defaults to "MyMCP".
            db_path (Optional[str], optional): Path to the SQLite database.
                If None, checks MCP_DB_PATH environment variable.
                If not set, defaults to api_keys.db in the current working directory.
                Defaults to None.
        """
        if db_path is None:
            db_path = os.environ.get(
                "MCP_DB_PATH",
                os.path.join(os.getcwd(), "api_keys.db")
            )

        self.db_manager = DatabaseManager(db_path)
        self.db_manager.init_db()

        self.mcp = FastMCP(name)
        self._http_middleware = [
            StarletteMiddleware(ApiKeyMiddleware, db_manager=self.db_manager)
        ]
        self._register_tools()

    @abstractmethod
    def _register_tools(self) -> None:
        """Subclasses must implement this to register their MCP tools."""
        ...

    def close(self) -> None:
        """
        Release any resources held by the server (e.g. HTTP clients).

        Closes ``self._http`` if a subclass set one in ``__init__`` (the
        common case for servers that wrap an external HTTP API); otherwise
        a no-op. Subclasses with other closeable resources, or an HTTP
        client under a different attribute name, should override this.
        ``run()`` calls this automatically on shutdown for a standalone
        server; callers that own multiple server instances directly (e.g.
        ``combined.py``, which never calls ``run()``) must call this
        themselves during shutdown to avoid leaking connection pools.
        """
        http_client = getattr(self, "_http", None)
        if http_client is not None:
            http_client.close()

    def run(self, **kwargs) -> None:
        """
        Run the MCP server.

        Starts the FastMCP server using the configured transport.
        Blocks until the server is shut down.

        For HTTP transports, API key authentication middleware is
        automatically applied, returning HTTP 401 for invalid keys.

        Args:
            **kwargs: Passed to ``FastMCP.run()`` (e.g. ``transport``,
                ``host``, ``port``).
        """
        transport = kwargs.get("transport")
        if transport in ("sse", "streamable-http", "http"):
            kwargs.setdefault("middleware", []).extend(self._http_middleware)
        try:
            self.mcp.run(**kwargs)
        finally:
            self.close()

    def main(self) -> None:
        """
        Parse command-line arguments and run the server.

        Provides ``--transport``, ``--port``, and ``--host`` flags so that
        every subclass gets HTTP transport support without duplicating
        argument parsing logic.
        """
        parser = argparse.ArgumentParser(
            description=f"{self.mcp.name} MCP Server",
        )
        parser.add_argument(
            "--transport",
            choices=["stdio", "sse", "streamable-http"],
            default="stdio",
            help="Transport protocol (default: stdio)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=8000,
            help="Port for HTTP transport (default: 8000)",
        )
        parser.add_argument(
            "--host",
            default="127.0.0.1",
            help="Host for HTTP transport (default: 127.0.0.1)",
        )
        args = parser.parse_args()

        if args.transport == "stdio":
            self.run()
        else:
            self.run(
                transport=args.transport, host=args.host, port=args.port
            )


def lazy_module_instances(
    server_factory: Callable[[], "AuthenticatedMCPServer"],
) -> Callable[[str], object]:
    """Build a module-level ``__getattr__`` that lazily exposes ``server``/``mcp``.

    Server modules historically defined module-level ``server`` and ``mcp``
    objects (the FastMCP CLI and older imports expect a module-level ``mcp``).
    Constructing them at import time, however, instantiates the server —
    which opens/creates the SQLite database and may log a generated key —
    merely because the module was imported. That makes the package unsafe to
    ``import`` as a library.

    This returns a PEP 562 module ``__getattr__`` that constructs the server
    on *first access* of ``server`` or ``mcp`` and caches it, so a plain
    ``import mcp_server_kit.<module>`` performs no database or network I/O.

    Usage in a server module::

        __getattr__ = lazy_module_instances(GreetMCPServer)

    Args:
        server_factory: Zero-argument callable returning a server instance
            (typically the server class itself).

    Returns:
        A ``__getattr__(name)`` function to assign at module scope.
    """
    cache: dict[str, object] = {}

    def __getattr__(name: str) -> object:
        if name in ("server", "mcp"):
            if "server" not in cache:
                srv = server_factory()
                cache["server"] = srv
                cache["mcp"] = srv.mcp
            return cache[name]
        raise AttributeError(f"module has no attribute {name!r}")

    return __getattr__
