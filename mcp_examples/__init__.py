"""
MCP Examples package.

Re-exports all public classes for convenient access.
Uses lazy imports to avoid ``RuntimeWarning`` when running submodules
directly with ``python -m mcp_examples.<module>``.
"""

import importlib as _importlib

__all__ = [
    "AuthenticatedMCPServer",
    "ContactDatabaseManager",
    "ContactMCPServer",
    "DatabaseManager",
    "ApiKeyMiddleware",
    "GreetMCPServer",
    "MCPClient",
    "MCPClientApp",
]

_LAZY_IMPORTS: dict[str, str] = {
    "AuthenticatedMCPServer": "mcp_examples.base",
    "ContactDatabaseManager": "mcp_examples.contact_database",
    "ContactMCPServer": "mcp_examples.contacts",
    "DatabaseManager": "mcp_examples.database",
    "ApiKeyMiddleware": "mcp_examples.middleware",
    "GreetMCPServer": "mcp_examples.server",
    "MCPClient": "mcp_examples.client",
    "MCPClientApp": "mcp_examples.cli",
}


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module = _importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
