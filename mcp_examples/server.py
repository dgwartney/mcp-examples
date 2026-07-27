"""
FastMCP Server with a greet tool.

Demonstrates how to build an MCP server by subclassing
``AuthenticatedMCPServer`` and registering tools in ``_register_tools()``.

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    Run the server directly (stdio transport):
        $ uv run -m mcp_examples.server

    Run as HTTP server:
        $ uv run -m mcp_examples.server --transport streamable-http --port 8000

    Run with custom database path:
        $ MCP_DB_PATH=/var/data/keys.db uv run -m mcp_examples.server
"""

from mcp_examples.base import AuthenticatedMCPServer


class GreetMCPServer(AuthenticatedMCPServer):
    """
    MCP server with a greet tool.

    Demonstrates ``AuthenticatedMCPServer`` usage by registering a single
    greeting tool.
    """

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


# Backward-compatible alias
MCPServer = GreetMCPServer

# Module-level instances
server = GreetMCPServer()
mcp = server.mcp  # FastMCP CLI expects a module-level 'mcp' object

# Add your own tools here using the bare @mcp.tool() decorator, e.g.:
#
#     @mcp.tool()
#     def reverse(text: str) -> str:
#         """Return the input string reversed."""
#         return text[::-1]

if __name__ == "__main__":
    server.main()
