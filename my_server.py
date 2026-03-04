"""
Thin wrapper for backward compatibility.

Delegates to mcp_examples.server so that `fastmcp run my_server.py`
and `uv run my_server.py` continue to work.
"""

from mcp_examples.server import MCPServer, server, mcp  # noqa: F401

if __name__ == "__main__":
    server.run()
