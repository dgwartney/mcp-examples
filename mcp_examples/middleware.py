"""
API key authentication middleware for FastMCP.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_http_headers
from fastmcp.exceptions import ToolError

from mcp_examples.database import DatabaseManager


class ApiKeyMiddleware(Middleware):
    """
    Middleware for validating API keys on incoming requests.

    This middleware extracts the X-API-Key header from HTTP requests and
    validates it against the database. Header matching is case-insensitive
    per RFC 7230. Requests with invalid or missing API keys are rejected.

    Attributes:
        db_manager (DatabaseManager): Database manager instance for key validation.
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the ApiKeyMiddleware.

        Args:
            db_manager (DatabaseManager): Database manager for API key validation.
        """
        self.db_manager = db_manager

    async def on_request(self, context: MiddlewareContext, call_next):
        """
        Process incoming requests and validate API keys.

        Extracts the X-API-Key header (case-insensitive) from the request,
        validates it against the database, and either continues processing
        or raises an error for invalid keys.

        Args:
            context (MiddlewareContext): The request context.
            call_next: Callable to invoke the next middleware or tool handler.

        Returns:
            The result from call_next if authentication succeeds.

        Raises:
            ToolError: If the API key is invalid or missing.
        """
        headers = get_http_headers()

        # HTTP headers are case-insensitive per RFC 7230
        # Create a case-insensitive lookup
        headers_lower = {k.lower(): v for k, v in headers.items()}
        api_key = headers_lower.get("x-api-key")

        if not self.db_manager.validate_key(api_key):
            raise ToolError("Unauthorized: Invalid or missing API Key")

        return await call_next(context)
