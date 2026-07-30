"""
FastMCP Server with mock employee onboarding case tools.

Demonstrates how to build an MCP server by subclassing
``AuthenticatedMCPServer`` and registering tools that create and track
new-hire onboarding cases (India/USA) in a SQLite-backed case log.

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    Run the server directly (stdio transport):
        $ uv run -m mcp_server_kit.onboarding

    Run as HTTP server:
        $ uv run -m mcp_server_kit.onboarding --transport streamable-http --port 8010
"""

import os
from typing import Optional

from fastmcp.exceptions import ToolError

from mcp_server_kit.base import AuthenticatedMCPServer, lazy_module_instances
from mcp_server_kit.onboarding_database import OnboardingDatabaseManager


class OnboardingMCPServer(AuthenticatedMCPServer):
    """
    MCP server with mock employee onboarding case tools.

    Provides tools to create, look up, update, and list onboarding cases
    against a SQLite database of case records.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        onboarding_db_path: Optional[str] = None,
    ):
        """
        Initialize the onboarding MCP server.

        Args:
            db_path: Path to the API key database. Passed to
                ``AuthenticatedMCPServer``.
            onboarding_db_path: Path to the onboarding SQLite database. If
                None, checks the ONBOARDING_DB_PATH environment variable.
                Defaults to onboarding.db in the current working directory.
        """
        if onboarding_db_path is None:
            onboarding_db_path = os.environ.get(
                "ONBOARDING_DB_PATH",
                os.path.join(os.getcwd(), "onboarding.db")
            )
        self.onboarding_db = OnboardingDatabaseManager(onboarding_db_path)
        self.onboarding_db.init_db()
        super().__init__(name="OnboardingMCP", db_path=db_path)

    def _register_tools(self) -> None:
        """Register onboarding-related MCP tools."""
        onboarding_db = self.onboarding_db

        @self.mcp.tool(
            description=(
                "Create a new employee onboarding case. Returns the new "
                "case with a case_id and status 'submitted'. "
                "start_date is an ISO date (YYYY-MM-DD)."
            )
        )
        def create_case(
            employee_name: str,
            employee_email: str,
            location: str,
            manager_name: str,
            start_date: str,
        ) -> dict:
            """
            Create a new onboarding case.

            Args:
                employee_name: Full name of the new hire.
                employee_email: Email address of the new hire.
                location: Work location, e.g. "India" or "USA".
                manager_name: Full name of the new hire's manager.
                start_date: Employment start date (ISO YYYY-MM-DD).

            Returns:
                The newly created case dict.
            """
            return onboarding_db.create_case(
                employee_name, employee_email, location, manager_name, start_date
            )

        @self.mcp.tool(description="Get an onboarding case by case ID")
        def get_case(case_id: int) -> dict:
            """
            Look up an onboarding case by case ID.

            Args:
                case_id: Case ID to search for.

            Returns:
                Case dict.

            Raises:
                ToolError: If no case matches case_id.
            """
            result = onboarding_db.get_case(case_id)
            if result is None:
                raise ToolError(f"No onboarding case found with case_id '{case_id}'")
            return result

        @self.mcp.tool(
            description=(
                "Update an onboarding case's status. status must be one of: "
                "submitted, it_provisioning, manager_review, completed, "
                "cancelled. notes is optional free-text appended to the case."
            )
        )
        def update_case_status(
            case_id: int, status: str, notes: Optional[str] = None
        ) -> dict:
            """
            Update an onboarding case's status.

            Args:
                case_id: Case ID to update.
                status: New status.
                notes: Optional note text for this status change.

            Returns:
                The updated case dict.

            Raises:
                ToolError: If case_id doesn't exist or status is invalid.
            """
            try:
                return onboarding_db.update_case_status(case_id, status, notes)
            except ValueError as exc:
                raise ToolError(str(exc)) from exc

        @self.mcp.tool(
            description=(
                "List onboarding cases, optionally filtered by status "
                "(submitted, it_provisioning, manager_review, completed, "
                "cancelled). Omit status to list all cases."
            )
        )
        def list_cases(status: Optional[str] = None) -> list[dict]:
            """
            List onboarding cases, optionally filtered by status.

            Args:
                status: Optional status to filter by.

            Returns:
                List of case dicts, most recently created first.
            """
            return onboarding_db.list_cases_by_status(status)


# Lazy module-level ``server`` / ``mcp`` — built on first attribute access, not
# on import, so ``import mcp_server_kit.onboarding`` performs no database I/O.
__getattr__ = lazy_module_instances(OnboardingMCPServer)

if __name__ == "__main__":
    OnboardingMCPServer().main()
