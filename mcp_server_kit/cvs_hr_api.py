"""
Admin REST API for the mock CVS HR systems (mounted at ``/cvs_hr/api``).

Not an agent tool: the agents cannot reset or reconfigure the demo. Every
route except ``GET /health`` requires the shared ``X-API-Key``.

Routes:
    GET  /health                               no key; status + as-of date
    POST /reset                                clear sandboxes/cases/audit, re-seed
    GET  /audit_events?system=&verification_id=&limit=
    GET  /systems?verification_id=             "what changed" (latest sandbox if omitted)
    GET  /settings                             {"sms_enabled": bool}
    POST /settings  {"sms_enabled": bool}      the SMS switch (persisted in the DB)

Author:
    David Gwartney <david.gwartney@gmail.com>

Environment Variables:
    MCP_DB_PATH:    Shared API-key SQLite database.
    CVS_HR_DB_PATH: CVS HR SQLite database (default: cvs_hr.db in the cwd).
"""

import os
from typing import Optional

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from mcp_server_kit.acme_api import _HealthExemptApiKeyMiddleware
from mcp_server_kit.cvs_hr_database import SYSTEMS, open_database
from mcp_server_kit.database import DatabaseManager


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def build_cvs_hr_app(cvs_hr_db_path: Optional[str] = None,
                     key_db_path: Optional[str] = None) -> Starlette:
    """
    Build the CVS HR admin Starlette app; mount it at ``/cvs_hr/api``.

    Args:
        cvs_hr_db_path: CVS HR database path (defaults to ``CVS_HR_DB_PATH``).
        key_db_path: API-key database path (defaults to ``MCP_DB_PATH`` or ``api_keys.db``).
    """
    hr_db = open_database(cvs_hr_db_path)
    key_db = DatabaseManager(
        key_db_path or os.environ.get("MCP_DB_PATH", os.path.join(os.getcwd(), "api_keys.db"))
    )
    key_db.init_db()

    async def health(request: Request) -> JSONResponse:
        cal = hr_db.calendar()
        return JSONResponse({"status": "ok", "service": "cvs_hr",
                             "as_of": cal.as_of.isoformat(),
                             "period_end": cal.period_end.isoformat()})

    async def reset(request: Request) -> JSONResponse:
        return JSONResponse(hr_db.reset())

    async def audit_events(request: Request) -> JSONResponse:
        system = request.query_params.get("system", "").strip()
        if system and system not in SYSTEMS:
            return _error(400, "invalid_system", f"system must be one of {list(SYSTEMS)}.")
        vid = request.query_params.get("verification_id", "").strip()
        try:
            limit = int(request.query_params.get("limit", "500"))
        except ValueError:
            return _error(400, "invalid_limit", "limit must be an integer.")
        hr_db.ensure_current()
        events = hr_db.list_audit_events(system, vid, limit)
        return JSONResponse({"count": len(events), "events": events})

    async def systems(request: Request) -> JSONResponse:
        hr_db.ensure_current()
        vid = request.query_params.get("verification_id", "").strip()
        view = hr_db.systems_view(vid)
        if vid and view["verification"] is None:
            return _error(404, "verification_not_found", "No verification with that ID.")
        return JSONResponse(view)

    async def get_settings(request: Request) -> JSONResponse:
        return JSONResponse(hr_db.get_settings())

    async def post_settings(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except ValueError:
            body = None
        if not isinstance(body, dict) or not isinstance(body.get("sms_enabled"), bool):
            return _error(400, "invalid_request", 'JSON body needs {"sms_enabled": true|false}.')
        return JSONResponse(hr_db.update_settings(body["sms_enabled"]))

    routes = [
        Route("/health", health, methods=["GET"]),
        Route("/reset", reset, methods=["POST"]),
        Route("/audit_events", audit_events, methods=["GET"]),
        Route("/systems", systems, methods=["GET"]),
        Route("/settings", get_settings, methods=["GET"]),
        Route("/settings", post_settings, methods=["POST"]),
    ]
    middleware = [Middleware(_HealthExemptApiKeyMiddleware, db_manager=key_db)]
    app = Starlette(routes=routes, middleware=middleware)
    app.state.hr_db = hr_db
    return app
