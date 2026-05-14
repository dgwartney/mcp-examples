"""
Combined MCP server — mounts all registered servers at separate URL paths.

To add a new server: append one entry to SERVER_REGISTRY.

Endpoints (when running on port 8000):
    /greet/mcp      → Greet server
    /contacts/mcp   → Contact server
    /wikipedia/mcp  → Wikipedia server

Run locally:
    uv run -m mcp_examples.combined --port 8000

Deploy to Fly.io:
    fly deploy
"""

import argparse
from contextlib import AsyncExitStack, asynccontextmanager

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount

from mcp_examples.contacts import ContactMCPServer
from mcp_examples.server import GreetMCPServer
from mcp_examples.wikipedia import WikipediaMCPServer

# Central registry: (url_prefix, ServerClass)
# To add a new server: append one entry here, then redeploy.
SERVER_REGISTRY: list[tuple[str, type]] = [
    ("greet", GreetMCPServer),
    ("contacts", ContactMCPServer),
    ("wikipedia", WikipediaMCPServer),
]


def _build() -> tuple[list, list]:
    routes, sub_apps = [], []
    for prefix, ServerClass in SERVER_REGISTRY:
        srv = ServerClass()
        sub_app = srv.mcp.http_app(
            path="/mcp",
            middleware=srv._http_middleware,
            transport="streamable-http",
        )
        routes.append(Mount(f"/{prefix}", app=sub_app))
        sub_apps.append(sub_app)
    return routes, sub_apps


_routes, _sub_apps = _build()


@asynccontextmanager
async def _lifespan(parent_app):
    # Starlette's Mount does not propagate sub-app lifespans automatically;
    # compose them here so each server's background workers start and stop correctly.
    async with AsyncExitStack() as stack:
        for sub_app in _sub_apps:
            await stack.enter_async_context(sub_app.lifespan(sub_app))
        yield


app = Starlette(lifespan=_lifespan, routes=_routes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Combined MCP Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("mcp_examples.combined:app", host=args.host, port=args.port)
