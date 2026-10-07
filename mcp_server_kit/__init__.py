"""
mcp-server-kit package.

Toolkit for building authenticated MCP servers. Re-exports all public
classes for convenient access. Uses lazy imports to avoid ``RuntimeWarning``
when running submodules directly with ``python -m mcp_server_kit.<module>``.
"""

import importlib as _importlib

__version__ = "0.1.0"

__all__ = [
    "AuthenticatedMCPServer",
    "ContactDatabaseManager",
    "ContactMCPServer",
    "DatabaseManager",
    "ApiKeyMiddleware",
    "GreetMCPServer",
    "MCPClient",
    "MCPClientApp",
    "MessagingMCPServer",
    "WeatherMCPServer",
    "WikipediaMCPServer",
    "PtoMCPServer",
    "AcmeMCPServer",
    "OnboardingMCPServer",
    "CvsHrDatabase",
    "CvsIdentityMCPServer",
    "WorkdayHcmMCPServer",
    "TimeAttendanceMCPServer",
    "ServicenowHrsdMCPServer",
    "CvsHrRouterMCPServer",
]

_LAZY_IMPORTS: dict[str, str] = {
    "AuthenticatedMCPServer": "mcp_server_kit.base",
    "ContactDatabaseManager": "mcp_server_kit.contact_database",
    "ContactMCPServer": "mcp_server_kit.contacts",
    "DatabaseManager": "mcp_server_kit.database",
    "ApiKeyMiddleware": "mcp_server_kit.middleware",
    "GreetMCPServer": "mcp_server_kit.server",
    "MCPClient": "mcp_server_kit.client",
    "MCPClientApp": "mcp_server_kit.cli",
    "MessagingMCPServer": "mcp_server_kit.messaging",
    "WeatherMCPServer": "mcp_server_kit.weather",
    "WikipediaMCPServer": "mcp_server_kit.wikipedia",
    "PtoMCPServer": "mcp_server_kit.pto",
    "AcmeMCPServer": "mcp_server_kit.acme",
    "OnboardingMCPServer": "mcp_server_kit.onboarding",
    "CvsHrDatabase": "mcp_server_kit.cvs_hr_database",
    "CvsIdentityMCPServer": "mcp_server_kit.cvs_identity",
    "WorkdayHcmMCPServer": "mcp_server_kit.workday_hcm",
    "TimeAttendanceMCPServer": "mcp_server_kit.time_attendance",
    "ServicenowHrsdMCPServer": "mcp_server_kit.servicenow_hrsd",
    "CvsHrRouterMCPServer": "mcp_server_kit.cvs_hr_router",
}


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module = _importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
