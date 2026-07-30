"""
FastMCP Server with mock employee PTO (paid time off) tools.

Demonstrates how to build an MCP server by subclassing
``AuthenticatedMCPServer`` and registering tools that query and update a
SQLite-backed store of employee PTO balances (India/USA workforce).

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    Run the server directly (stdio transport):
        $ uv run -m mcp_server_kit.pto

    Run as HTTP server:
        $ uv run -m mcp_server_kit.pto --transport streamable-http --port 8010
"""

import os
from typing import Optional

from fastmcp.exceptions import ToolError

from mcp_server_kit.base import AuthenticatedMCPServer, lazy_module_instances
from mcp_server_kit.pto_database import PtoDatabaseManager


class PtoMCPServer(AuthenticatedMCPServer):
    """
    MCP server with mock employee PTO balance/request tools.

    Provides tools to look up PTO balances and file/list PTO requests
    against a SQLite database of employee records.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        pto_db_path: Optional[str] = None,
    ):
        """
        Initialize the PTO MCP server.

        Args:
            db_path: Path to the API key database. Passed to
                ``AuthenticatedMCPServer``.
            pto_db_path: Path to the PTO SQLite database. If None, checks
                the PTO_DB_PATH environment variable. Defaults to pto.db
                in the current working directory.
        """
        if pto_db_path is None:
            pto_db_path = os.environ.get(
                "PTO_DB_PATH",
                os.path.join(os.getcwd(), "pto.db")
            )
        self.pto_db = PtoDatabaseManager(pto_db_path)
        self.pto_db.init_db()
        super().__init__(name="PtoMCP", db_path=db_path)

    def _register_tools(self) -> None:
        """Register PTO-related MCP tools."""
        pto_db = self.pto_db

        @self.mcp.tool(description="Get an employee's PTO balance by employee ID")
        def get_balance(employee_id: str) -> dict:
            """
            Look up an employee's PTO balance by employee ID.

            Args:
                employee_id: Employee ID to search for.

            Returns:
                Balance dict: employee_id, full_name, email, location,
                manager, pto_balance_days, accrual_rate_per_month.

            Raises:
                ToolError: If no employee matches employee_id.
            """
            result = pto_db.get_balance(employee_id)
            if result is None:
                raise ToolError(f"No employee found with employee_id '{employee_id}'")
            return result

        @self.mcp.tool(description="Get an employee's PTO balance by email address")
        def get_balance_by_email(email: str) -> dict:
            """
            Look up an employee's PTO balance by email address.

            Args:
                email: Employee email address to search for.

            Returns:
                Balance dict, same shape as get_balance.

            Raises:
                ToolError: If no employee matches email.
            """
            result = pto_db.get_balance_by_email(email)
            if result is None:
                raise ToolError(f"No employee found with email '{email}'")
            return result

        @self.mcp.tool(
            description=(
                "File a PTO request for an employee. Auto-approves and "
                "deducts the balance if sufficient days are available; "
                "otherwise the request is recorded as denied. "
                "start_date/end_date are ISO dates (YYYY-MM-DD)."
            )
        )
        def request_pto(
            employee_id: str, start_date: str, end_date: str, days: float
        ) -> dict:
            """
            File a PTO request for an employee.

            Args:
                employee_id: Employee ID filing the request.
                start_date: Requested start date (ISO YYYY-MM-DD).
                end_date: Requested end date (ISO YYYY-MM-DD).
                days: Number of PTO days requested.

            Returns:
                Dict with request_id, employee_id, start_date, end_date,
                days, status, remaining_balance_days.

            Raises:
                ToolError: If no employee matches employee_id.
            """
            try:
                return pto_db.request_pto(employee_id, start_date, end_date, days)
            except ValueError as exc:
                raise ToolError(str(exc)) from exc

        @self.mcp.tool(description="List all PTO requests filed by an employee")
        def list_requests(employee_id: str) -> list[dict]:
            """
            List all PTO requests filed by an employee, most recent first.

            Args:
                employee_id: Employee ID to list requests for.

            Returns:
                List of request dicts.
            """
            return pto_db.list_requests(employee_id)


# Lazy module-level ``server`` / ``mcp`` — built on first attribute access, not
# on import, so ``import mcp_server_kit.pto`` performs no database I/O.
__getattr__ = lazy_module_instances(PtoMCPServer)

if __name__ == "__main__":
    PtoMCPServer().main()
