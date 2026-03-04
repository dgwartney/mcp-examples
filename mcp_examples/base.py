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
from typing import Optional

from fastmcp import FastMCP

from mcp_examples.database import DatabaseManager
from mcp_examples.middleware import ApiKeyMiddleware


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
        self.mcp.add_middleware(ApiKeyMiddleware(self.db_manager))
        self._register_tools()

    @abstractmethod
    def _register_tools(self) -> None:
        """Subclasses must implement this to register their MCP tools."""
        ...

    def run(self, **kwargs) -> None:
        """
        Run the MCP server.

        Starts the FastMCP server using the configured transport.
        Blocks until the server is shut down.

        Args:
            **kwargs: Passed to ``FastMCP.run()`` (e.g. ``transport``,
                ``host``, ``port``).
        """
        self.mcp.run(**kwargs)

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
