"""
FastMCP Server for the mock "Acme Support" retail backend.

Exposes the same orders/returns/tickets data as ``acme_api.py`` (REST), but
as MCP tools, so Artemis labs can compare an HTTP tool and an MCP tool that
reach the same backend. Both share one SQLite database (``ACME_DB_PATH``).

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    Run the server directly (stdio transport):
        $ uv run -m mcp_server_kit.acme

    Run as HTTP server:
        $ uv run -m mcp_server_kit.acme --transport streamable-http --port 8011
"""

import os
from typing import Optional

from fastmcp.exceptions import ToolError

from mcp_server_kit.acme_database import AcmeDatabaseManager
from mcp_server_kit.base import AuthenticatedMCPServer, lazy_module_instances


class AcmeMCPServer(AuthenticatedMCPServer):
    """
    MCP server with mock Acme retail tools: order lookup, returns, tickets.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        acme_db_path: Optional[str] = None,
    ):
        """
        Initialize the Acme MCP server.

        Args:
            db_path: Path to the API key database. Passed to
                ``AuthenticatedMCPServer``.
            acme_db_path: Path to the Acme SQLite database. If None, checks
                the ACME_DB_PATH environment variable. Defaults to acme.db
                in the current working directory.
        """
        if acme_db_path is None:
            acme_db_path = os.environ.get(
                "ACME_DB_PATH",
                os.path.join(os.getcwd(), "acme.db")
            )
        self.acme_db = AcmeDatabaseManager(acme_db_path)
        self.acme_db.init_db()
        super().__init__(name="AcmeMCP", db_path=db_path)

    def _register_tools(self) -> None:
        """Register Acme retail MCP tools."""
        acme_db = self.acme_db

        @self.mcp.tool(description="Get the status and details of an Acme order by order ID (e.g. ACM-1002)")
        def get_order(order_id: str) -> dict:
            """
            Look up one order by ID.

            Args:
                order_id: Order ID such as ``ACM-1002``.

            Returns:
                Order dict: order_id, customer_name, customer_email, status,
                order_date, carrier, tracking_number, estimated_delivery,
                delivered_date, items, total, return_eligible, return_deadline.

            Raises:
                ToolError: If no order matches order_id.
            """
            result = acme_db.get_order(order_id)
            if result is None:
                raise ToolError(f"No order found with ID '{order_id}'")
            return result

        @self.mcp.tool(description="List all Acme orders for a customer email address, newest first")
        def list_orders(email: str) -> list[dict]:
            """
            List every order for a customer email.

            Args:
                email: Customer email address.

            Returns:
                List of order dicts (possibly empty).
            """
            return acme_db.list_orders_by_email(email)

        @self.mcp.tool(
            description=(
                "Open a return for a delivered Acme order that is still inside "
                "its return window. Fails if the order is missing or not eligible."
            )
        )
        def create_return(order_id: str, reason: str) -> dict:
            """
            Open a return for an order.

            Args:
                order_id: Order to return.
                reason: Customer's reason for the return.

            Returns:
                Return dict: return_id, order_id, reason, status, created_at.

            Raises:
                ToolError: If the order is missing or not eligible.
            """
            result = acme_db.create_return(order_id, reason)
            if not result["ok"]:
                raise ToolError(result["message"])
            return result["return"]

        @self.mcp.tool(description="Get an Acme return by return ID (e.g. RET-1)")
        def get_return(return_id: str) -> dict:
            """
            Look up a return by ID.

            Raises:
                ToolError: If no return matches return_id.
            """
            result = acme_db.get_return(return_id)
            if result is None:
                raise ToolError(f"No return found with ID '{return_id}'")
            return result

        @self.mcp.tool(
            description=(
                "Open an Acme support ticket for a human agent to follow up. "
                "priority is one of low, normal, high, urgent."
            )
        )
        def create_ticket(
            customer_email: str, subject: str, description: str, priority: str = "normal"
        ) -> dict:
            """
            Open a support ticket.

            Returns:
                Ticket dict: ticket_id, customer_email, subject, description,
                priority, status, created_at.
            """
            return acme_db.create_ticket(customer_email, subject, description, priority)

        @self.mcp.tool(description="Get an Acme support ticket by ticket ID (e.g. TKT-1)")
        def get_ticket(ticket_id: str) -> dict:
            """
            Look up a ticket by ID.

            Raises:
                ToolError: If no ticket matches ticket_id.
            """
            result = acme_db.get_ticket(ticket_id)
            if result is None:
                raise ToolError(f"No ticket found with ID '{ticket_id}'")
            return result


# Lazy module-level ``server`` / ``mcp`` — built on first attribute access, not
# on import, so ``import mcp_server_kit.acme`` performs no database I/O.
__getattr__ = lazy_module_instances(AcmeMCPServer)

if __name__ == "__main__":
    AcmeMCPServer().main()
