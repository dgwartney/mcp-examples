"""
API key authentication middleware for FastMCP.

Uses Starlette's BaseHTTPMiddleware to intercept requests at the HTTP level,
returning a proper 401 status code for invalid or missing API keys.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_examples.database import DatabaseManager


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware for validating API keys on incoming requests.

    Extracts the X-API-Key header from HTTP requests and validates it
    against the database. Header matching is case-insensitive per RFC 7230.
    Requests with invalid or missing API keys receive an HTTP 401 response.

    Attributes:
        db_manager (DatabaseManager): Database manager instance for key validation.
    """

    def __init__(self, app, db_manager: DatabaseManager):
        """
        Initialize the ApiKeyMiddleware.

        Args:
            app: The ASGI application to wrap.
            db_manager (DatabaseManager): Database manager for API key validation.
        """
        super().__init__(app)
        self.db_manager = db_manager

    async def dispatch(self, request: Request, call_next):
        """
        Process incoming requests and validate API keys.

        Extracts the X-API-Key header (case-insensitive) from the request,
        validates it against the database, and either continues processing
        or returns a 401 Unauthorized response.

        Args:
            request (Request): The incoming HTTP request.
            call_next: Callable to invoke the next middleware or route handler.

        Returns:
            Response: The response from the next handler if authenticated,
                or a 401 JSON error response if not.
        """
        # HTTP headers are case-insensitive per RFC 7230
        # Starlette headers are already case-insensitive
        api_key = request.headers.get("x-api-key")

        if not self.db_manager.validate_key(api_key):
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized: Invalid or missing API Key"},
            )

        return await call_next(request)
