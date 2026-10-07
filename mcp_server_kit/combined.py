"""
Combined MCP server — mounts all registered servers at separate URL paths.

To add a new server: append one entry to SERVER_REGISTRY.

Endpoints (when running on port 8000):
    /greet/mcp      → Greet server
    /contacts/mcp   → Contact server
    /wikipedia/mcp  → Wikipedia server
    /weather/mcp    → Weather server
    /messaging/mcp  → Messaging server (Twilio SMS + SendGrid email)
    /pto/mcp        → PTO server
    /onboarding/mcp → Onboarding server
    /acme/mcp       → Acme Support server (orders, returns, tickets)
    /acme/api/...   → Acme Support REST API (same data; see acme_api.py)
    /cvs_identity/mcp    → CVS identity service (caller verification)
    /workday_hcm/mcp     → Workday HCM mock (worker, PTO, read-only payroll rule)
    /time_attendance/mcp → Time and attendance mock (timecards, corrections)
    /servicenow_hrsd/mcp → ServiceNow HRSD mock (HR cases)
    /cvs_hr/api/...      → CVS HR admin REST (reset, audit_events, systems, settings)

Run locally:
    OPENWEATHER_API_KEY=<key> uv run -m mcp_server_kit.combined --port 8000

Deploy to Fly.io:
    fly secrets set OPENWEATHER_API_KEY=<key>
    fly secrets set TWILIO_ACCOUNT_SID=<sid>
    fly secrets set TWILIO_AUTH_TOKEN=<token>
    fly secrets set TWILIO_MESSAGING_SERVICE_SID=<mg_sid>
    fly secrets set SENDGRID_API_KEY=<sg_key>
    fly secrets set SENDGRID_FROM_EMAIL=<verified_sender>
    fly deploy
"""

import argparse
from contextlib import AsyncExitStack, asynccontextmanager

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount

from mcp_server_kit.acme import AcmeMCPServer
from mcp_server_kit.acme_api import build_acme_app
from mcp_server_kit.contacts import ContactMCPServer
from mcp_server_kit.cvs_hr_api import build_cvs_hr_app
from mcp_server_kit.cvs_identity import CvsIdentityMCPServer
from mcp_server_kit.onboarding import OnboardingMCPServer
from mcp_server_kit.pto import PtoMCPServer
from mcp_server_kit.server import GreetMCPServer
from mcp_server_kit.servicenow_hrsd import ServicenowHrsdMCPServer
from mcp_server_kit.messaging import MessagingMCPServer
from mcp_server_kit.time_attendance import TimeAttendanceMCPServer
from mcp_server_kit.weather import WeatherMCPServer
from mcp_server_kit.wikipedia import WikipediaMCPServer
from mcp_server_kit.workday_hcm import WorkdayHcmMCPServer

# Central registry: (url_prefix, ServerClass)
# To add a new server: append one entry here, then redeploy.
SERVER_REGISTRY: list[tuple[str, type]] = [
    ("greet", GreetMCPServer),
    ("contacts", ContactMCPServer),
    ("wikipedia", WikipediaMCPServer),
    ("weather", WeatherMCPServer),
    ("messaging", MessagingMCPServer),
    ("pto", PtoMCPServer),
    ("onboarding", OnboardingMCPServer),
    ("acme", AcmeMCPServer),
    ("cvs_identity", CvsIdentityMCPServer),
    ("workday_hcm", WorkdayHcmMCPServer),
    ("time_attendance", TimeAttendanceMCPServer),
    ("servicenow_hrsd", ServicenowHrsdMCPServer),
]

# Plain (non-MCP) REST apps: (mount_path, zero-arg app factory). Mounted
# BEFORE the MCP servers so a more specific path like "/acme/api" wins over
# the "/acme" MCP mount (Starlette uses the first matching Mount).
REST_REGISTRY: list[tuple[str, object]] = [
    ("/acme/api", build_acme_app),
    ("/cvs_hr/api", build_cvs_hr_app),
]


def _build() -> tuple[list, list, list]:
    routes, sub_apps, servers = [], [], []
    for prefix, ServerClass in SERVER_REGISTRY:
        srv = ServerClass()
        sub_app = srv.mcp.http_app(
            path="/mcp",
            middleware=srv._http_middleware,
            transport="streamable-http",
        )
        routes.append(Mount(f"/{prefix}", app=sub_app))
        sub_apps.append(sub_app)
        servers.append(srv)
    return routes, sub_apps, servers


def build_app() -> Starlette:
    """Construct the combined Starlette app, mounting every registered server.

    Building the app instantiates every server in ``SERVER_REGISTRY`` (which
    opens/creates their SQLite databases), so this is done lazily rather than
    at import time — see the module-level ``__getattr__`` below.
    """
    routes, sub_apps, servers = _build()
    rest_routes = [Mount(path, app=factory()) for path, factory in REST_REGISTRY]
    routes = rest_routes + routes

    @asynccontextmanager
    async def _lifespan(parent_app):
        # Starlette's Mount does not propagate sub-app lifespans automatically;
        # compose them here so each server's background workers start and stop
        # correctly.
        try:
            async with AsyncExitStack() as stack:
                for sub_app in sub_apps:
                    await stack.enter_async_context(sub_app.lifespan(sub_app))
                yield
        finally:
            for srv in servers:
                srv.close()

    return Starlette(lifespan=_lifespan, routes=routes)


_app_cache: dict[str, Starlette] = {}


def __getattr__(name: str) -> Starlette:
    """Lazily build the ASGI ``app`` on first access (PEP 562).

    Deployment targets reference ``mcp_server_kit.combined:app``; uvicorn's
    string import triggers this and builds the app at server startup, so a
    plain ``import mcp_server_kit.combined`` performs no database I/O.
    """
    if name == "app":
        if "app" not in _app_cache:
            _app_cache["app"] = build_app()
        return _app_cache["app"]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Combined MCP Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("mcp_server_kit.combined:app", host=args.host, port=args.port)
