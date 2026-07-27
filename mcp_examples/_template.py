"""
Minimal starter template for a new MCP server.

Copy this file, rename the class and the module, and replace `example_tool`
with your own tool(s). This is the smallest possible AuthenticatedMCPServer
subclass — no external API calls, no SQLite domain tables beyond the
built-in API-key auth store.

See docs/extending.md for the full checklist of what else to update when
adding a new server (combined.py's SERVER_REGISTRY, docs/servers.md, tests).

Author: <your name>

Example:
    Run directly (stdio transport):
        $ uv run -m mcp_examples._template
    Run as HTTP:
        $ uv run -m mcp_examples._template --transport streamable-http --port 8010
"""

from mcp_examples.base import AuthenticatedMCPServer


class TemplateMCPServer(AuthenticatedMCPServer):
    """Bare-bones example server with a single placeholder tool."""

    def _register_tools(self) -> None:
        @self.mcp.tool(description="Example tool — replace with your own logic")
        def example_tool(text: str) -> str:
            """Echo the input back, prefixed with 'You said: '."""
            return f"You said: {text}"


# Module-level instances (required by FastMCP CLI and combined.py mounting)
server = TemplateMCPServer()
mcp = server.mcp

# Add more tools here using the bare @mcp.tool() decorator, e.g.:
#
#     @mcp.tool()
#     def reverse(text: str) -> str:
#         """Return the input string reversed."""
#         return text[::-1]

if __name__ == "__main__":
    server.main()
