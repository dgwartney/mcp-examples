"""
Minimal starter template for a new MCP server.

Copy this file, rename the class and the module, and replace the examples
with your own: `example_tool` (a tool), `example://info` (a resource),
`example://echo/{text}` (a resource template) and `example_prompt` (a prompt).
Delete `_register_resources()` or `_register_prompts()` if you don't need
them. This is the smallest possible AuthenticatedMCPServer subclass — no
external API calls, no SQLite domain tables beyond the built-in API-key auth
store.

See docs/extending.md for the full checklist of what else to update when
adding a new server (combined.py's SERVER_REGISTRY, docs/servers.md, tests).

Author: <your name>

Example:
    Run directly (stdio transport):
        $ uv run -m mcp_server_kit._template
    Run as HTTP:
        $ uv run -m mcp_server_kit._template --transport streamable-http --port 8010
"""

from mcp_server_kit.base import AuthenticatedMCPServer, lazy_module_instances


class TemplateMCPServer(AuthenticatedMCPServer):
    """Bare-bones example server with one of each MCP primitive."""

    def _register_tools(self) -> None:
        @self.mcp.tool(description="Example tool — replace with your own logic")
        def example_tool(text: str) -> str:
            """Echo the input back, prefixed with 'You said: '."""
            return f"You said: {text}"

    def _register_resources(self) -> None:
        @self.mcp.resource(
            "example://info", description="Example resource — replace with your own data"
        )
        def example_info() -> str:
            """Return fixed text. A resource is read-only data the client can fetch."""
            return "Example resource — replace with your own data"

        @self.mcp.resource(
            "example://echo/{text}", description="Example resource template"
        )
        def example_echo(text: str) -> str:
            """Return the {text} part of the URI. A template serves a family of URIs."""
            return f"You said: {text}"

    def _register_prompts(self) -> None:
        @self.mcp.prompt(description="Example prompt — replace with your own template")
        def example_prompt(topic: str) -> str:
            """Return a reusable prompt that the client fills in and sends to a model."""
            return f"Write a short explanation of {topic}."


# Lazy module-level ``server`` / ``mcp`` — built on first attribute access, not
# on import, so ``import mcp_server_kit._template`` performs no database I/O.
# The FastMCP CLI and combined.py mounting still find ``server``/``mcp`` here.
#
# Add more tools inside ``_register_tools()`` above, e.g.:
#
#     @self.mcp.tool(description="Reverse a string")
#     def reverse(text: str) -> str:
#         """Return the input string reversed."""
#         return text[::-1]
__getattr__ = lazy_module_instances(TemplateMCPServer)

if __name__ == "__main__":
    TemplateMCPServer().main()
