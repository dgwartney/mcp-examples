"""
FastMCP Server with SQLite-backed API Key Authentication.

This module implements a Model Context Protocol (MCP) server using the FastMCP
library with middleware-based authentication. API keys are stored and validated
against a SQLite database.

Author:
    David Gwartney <david.gwartney@gmail.com>

Environment Variables:
    MCP_DB_PATH: Optional path to SQLite database file.
                 Defaults to api_keys.db in the current working directory if not set.

Example:
    Run the server directly:
        $ uv run -m mcp_examples.server

    Run via FastMCP CLI:
        $ uv run fastmcp run my_server.py

    Run as HTTP server:
        $ uv run fastmcp run my_server.py --transport http --port 8000

    Run with custom database path:
        $ MCP_DB_PATH=/var/data/keys.db uv run -m mcp_examples.server
"""

import os
from typing import Optional

from fastmcp import FastMCP

from mcp_examples.database import DatabaseManager
from mcp_examples.middleware import ApiKeyMiddleware


class MCPServer:
    """
    FastMCP server with API key authentication.

    Encapsulates the entire MCP server setup including database initialization,
    middleware registration, and tool registration. The server can be run
    via stdio transport (default) or HTTP transport when using the FastMCP CLI.

    Attributes:
        db_manager (DatabaseManager): Manages API key database operations.
        mcp (FastMCP): The FastMCP server instance.
    """

    def __init__(self, name: str = "MyMCP", db_path: Optional[str] = None):
        """
        Initialize the MCP server.

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

    def _register_tools(self) -> None:
        """
        Register MCP tools with the server.

        This method registers all available tools that can be called by clients.
        Currently implements a single 'greet' tool for demonstration purposes.
        """
        @self.mcp.tool(description="A tool that greets a user by name")
        def greet(name: str) -> str:
            """
            Generate a greeting message.

            Args:
                name (str): The name of the person to greet.

            Returns:
                str: A greeting message in the format "Hello, {name}!".
            """
            return f"Hello, {name}!"

    def run(self) -> None:
        """
        Run the MCP server.

        Starts the FastMCP server using the configured transport.
        Blocks until the server is shut down.
        """
        self.mcp.run()


# Module-level instances
server = MCPServer()
mcp = server.mcp  # FastMCP CLI expects a module-level 'mcp' object

if __name__ == "__main__":
    server.run()
