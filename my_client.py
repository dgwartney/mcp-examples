"""
Thin wrapper for backward compatibility.

Delegates to mcp_examples so that `uv run my_client.py` continues to work.
"""

from mcp_examples.client import MCPClient  # noqa: F401
from mcp_examples.cli import MCPClientApp  # noqa: F401

if __name__ == "__main__":
    app = MCPClientApp()
    app.run()
