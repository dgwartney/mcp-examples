"""
REST API for the mock "Acme Support" retail backend.

A small Starlette app (no MCP) that exposes orders, returns and tickets as
plain JSON over HTTP, for Artemis HTTP-tool labs. Mounted by
``combined.py`` at ``/acme/api`` (ahead of the Acme MCP server mounted at
``/acme``), so routes are served under ``/acme/api/...``.

All routes except ``GET /health`` require an ``X-API-Key`` header that
matches a key in the shared API-key database (same keys as the MCP servers).

Reliability-lab simulations (see ``acme_database.SIMULATED_*``):
    ACM-1099  responds after ~8 seconds (exceeds a short tool timeout)
    ACM-1098  always returns HTTP 503 (backend "down")
    ACM-1097  returns HTTP 503 twice, then succeeds (retry demo); the
              failure counter resets 60 seconds after the first failure

Author:
    David Gwartney <david.gwartney@gmail.com>

Environment Variables:
    MCP_DB_PATH:  Path to the shared API-key SQLite database.
    ACME_DB_PATH: Path to the Acme SQLite database (default: acme.db in cwd).
"""

import asyncio
import os
import time
from typing import Optional

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from mcp_server_kit.acme_database import (
    SIMULATED_DOWN_ORDER,
    SIMULATED_FLAKY_ORDER,
    SIMULATED_SLOW_ORDER,
    AcmeDatabaseManager,
)
from mcp_server_kit.database import DatabaseManager
from mcp_server_kit.middleware import ApiKeyMiddleware

SLOW_RESPONSE_SECONDS = 8.0
FLAKY_FAILURES_BEFORE_SUCCESS = 2
FLAKY_RESET_SECONDS = 60.0


class _HealthExemptApiKeyMiddleware(ApiKeyMiddleware):
    """``ApiKeyMiddleware`` that lets ``/health`` through unauthenticated."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.endswith("/health"):
            return await call_next(request)
        return await super().dispatch(request, call_next)


class _FlakyCounter:
    """Per-process failure counter for the retry-demo order."""

    def __init__(self):
        self.failures = 0
        self.first_failure_at: Optional[float] = None

    def should_fail(self) -> bool:
        now = time.monotonic()
        if self.first_failure_at is not None and now - self.first_failure_at > FLAKY_RESET_SECONDS:
            self.failures, self.first_failure_at = 0, None
        if self.failures < FLAKY_FAILURES_BEFORE_SUCCESS:
            if self.first_failure_at is None:
                self.first_failure_at = now
            self.failures += 1
            return True
        self.failures, self.first_failure_at = 0, None
        return False


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def build_acme_app(
    acme_db_path: Optional[str] = None,
    key_db_path: Optional[str] = None,
    slow_seconds: float = SLOW_RESPONSE_SECONDS,
) -> Starlette:
    """
    Build the Acme REST Starlette app.

    Args:
        acme_db_path: Acme database path (defaults to ``ACME_DB_PATH`` env or ``acme.db``).
        key_db_path: API-key database path (defaults to ``MCP_DB_PATH`` env or ``api_keys.db``).
        slow_seconds: Delay used by the slow-order simulation (tests shorten it).

    Returns:
        A Starlette app; mount it at ``/acme/api``.
    """
    acme_db = AcmeDatabaseManager(
        acme_db_path or os.environ.get("ACME_DB_PATH", os.path.join(os.getcwd(), "acme.db"))
    )
    acme_db.init_db()
    key_db = DatabaseManager(
        key_db_path or os.environ.get("MCP_DB_PATH", os.path.join(os.getcwd(), "api_keys.db"))
    )
    key_db.init_db()
    flaky = _FlakyCounter()

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "acme"})

    async def get_order(request: Request) -> JSONResponse:
        order_id = request.path_params["order_id"].strip().upper()
        if order_id == SIMULATED_SLOW_ORDER:
            await asyncio.sleep(slow_seconds)
            return _error(404, "order_not_found", f"No order found with ID {order_id}.")
        if order_id == SIMULATED_DOWN_ORDER:
            return _error(503, "service_unavailable", "The order system is temporarily unavailable.")
        if order_id == SIMULATED_FLAKY_ORDER:
            if flaky.should_fail():
                return _error(503, "service_unavailable", "The order system is temporarily unavailable.")
            order = acme_db.get_order("ACM-1002")
            order["order_id"] = SIMULATED_FLAKY_ORDER
            return JSONResponse(order)
        order = acme_db.get_order(order_id)
        if order is None:
            return _error(404, "order_not_found", f"No order found with ID {order_id}.")
        return JSONResponse(order)

    async def list_orders(request: Request) -> JSONResponse:
        email = request.query_params.get("email", "").strip()
        if not email:
            return _error(400, "missing_email", "Provide the customer's email as ?email=...")
        orders = acme_db.list_orders_by_email(email)
        return JSONResponse({"customer_email": email, "count": len(orders), "orders": orders})

    async def _json_body(request: Request) -> Optional[dict]:
        try:
            body = await request.json()
        except ValueError:
            return None
        return body if isinstance(body, dict) else None

    async def create_return(request: Request) -> JSONResponse:
        body = await _json_body(request)
        if body is None or not body.get("order_id") or not body.get("reason"):
            return _error(400, "invalid_request", "JSON body needs 'order_id' and 'reason'.")
        result = acme_db.create_return(str(body["order_id"]), str(body["reason"]))
        if not result["ok"]:
            status = 404 if result["error"] == "order_not_found" else 409
            return _error(status, result["error"], result["message"])
        return JSONResponse(result["return"], status_code=201)

    async def get_return(request: Request) -> JSONResponse:
        ret = acme_db.get_return(request.path_params["return_id"])
        if ret is None:
            return _error(404, "return_not_found", "No return found with that ID.")
        return JSONResponse(ret)

    async def create_ticket(request: Request) -> JSONResponse:
        body = await _json_body(request)
        required = ("customer_email", "subject", "description")
        if body is None or any(not body.get(k) for k in required):
            return _error(400, "invalid_request",
                          "JSON body needs 'customer_email', 'subject' and 'description'.")
        ticket = acme_db.create_ticket(
            str(body["customer_email"]), str(body["subject"]),
            str(body["description"]), str(body.get("priority", "normal")),
        )
        return JSONResponse(ticket, status_code=201)

    async def get_ticket(request: Request) -> JSONResponse:
        ticket = acme_db.get_ticket(request.path_params["ticket_id"])
        if ticket is None:
            return _error(404, "ticket_not_found", "No ticket found with that ID.")
        return JSONResponse(ticket)

    routes = [
        Route("/health", health, methods=["GET"]),
        Route("/orders", list_orders, methods=["GET"]),
        Route("/orders/{order_id}", get_order, methods=["GET"]),
        Route("/returns", create_return, methods=["POST"]),
        Route("/returns/{return_id}", get_return, methods=["GET"]),
        Route("/tickets", create_ticket, methods=["POST"]),
        Route("/tickets/{ticket_id}", get_ticket, methods=["GET"]),
    ]
    middleware = [Middleware(_HealthExemptApiKeyMiddleware, db_manager=key_db)]
    app = Starlette(routes=routes, middleware=middleware)
    app.state.acme_db = acme_db
    return app
