"""
Tool-call logging middleware for FastMCP.

Logs the tool name (and, on failure, the error) for every ``tools/call``
request so deployed servers show which MCP tool actually ran instead of
just the wrapping HTTP request line.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import logging

from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from mcp.types import CallToolRequestParams
from fastmcp.tools.tool import ToolResult

logger = logging.getLogger("mcp_server_kit.tool_calls")


def configure_logging() -> None:
    """Configure the root logger so INFO-level app logs reach stdout.

    ``uvicorn.run()`` only configures its own ``uvicorn*`` loggers and
    leaves the root logger untouched, so without this, records logged
    through plain ``logging.getLogger(__name__)`` calls (like the ones in
    :class:`ToolCallLoggingMiddleware`) fall through to the logging
    module's silent "handler of last resort" (WARNING+ only) and never
    reach ``fly logs``. Safe to call multiple times — ``basicConfig`` is a
    no-op once the root logger already has a handler.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


class ToolCallLoggingMiddleware(Middleware):
    """Logs each MCP tool invocation: tool name, argument names, and outcome.

    Argument *values* are never logged — many tools (e.g. messaging) take
    phone numbers, email addresses, message bodies, or API credentials as
    arguments, and logs are not an appropriate place for that data. Only
    the argument *keys* are logged, which is enough to see which fields a
    caller populated without exposing their contents.
    """

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        tool_name = context.message.name
        argument_names = sorted((context.message.arguments or {}).keys())

        logger.info("tool_call start name=%s argument_names=%s", tool_name, argument_names)
        try:
            result = await call_next(context)
        except Exception:
            logger.exception("tool_call failed name=%s", tool_name)
            raise

        logger.info("tool_call done name=%s", tool_name)
        return result
