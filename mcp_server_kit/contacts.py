"""
FastMCP Server with mock customer contact profile tools.

Demonstrates how to build an MCP server by subclassing
``AuthenticatedMCPServer`` and registering tools that query a
Salesforce-style contact database seeded with fictional customer contacts.

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    Run the server directly (stdio transport):
        $ uv run -m mcp_server_kit.contacts

    Run as HTTP server:
        $ uv run -m mcp_server_kit.contacts --transport streamable-http --port 8000
"""

import os
from typing import Optional

from fastmcp.exceptions import ToolError

from mcp_server_kit.base import AuthenticatedMCPServer, lazy_module_instances
from mcp_server_kit.contact_database import ContactDatabaseManager


class ContactMCPServer(AuthenticatedMCPServer):
    """
    MCP server with mock customer contact profile tools.

    Provides tools to search and authenticate against a SQLite database
    of Salesforce-style contact records.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        contact_db_path: Optional[str] = None,
    ):
        """
        Initialize the contact MCP server.

        Args:
            db_path: Path to the API key database. Passed to
                ``AuthenticatedMCPServer``.
            contact_db_path: Path to the contacts SQLite database.
                If None, checks CONTACTS_DB_PATH environment variable.
                Defaults to contacts.db in the current working directory.
        """
        if contact_db_path is None:
            contact_db_path = os.environ.get(
                "CONTACTS_DB_PATH",
                os.path.join(os.getcwd(), "contacts.db")
            )
        self.contact_db = ContactDatabaseManager(contact_db_path)
        self.contact_db.init_db()
        super().__init__(name="ContactMCP", db_path=db_path)

    def _register_tools(self) -> None:
        """Register contact-related MCP tools."""
        contact_db = self.contact_db

        @self.mcp.tool(description="Search contacts by last name (case-insensitive partial match)")
        def search_by_last_name(last_name: str) -> list[dict]:
            """
            Search contacts by last name.

            Args:
                last_name: Partial or full last name to search for.

            Returns:
                List of matching contact records.

            Raises:
                ToolError: If ``last_name`` is empty (an empty ``LIKE``
                           pattern would otherwise match every contact).
            """
            if not last_name.strip():
                raise ToolError("last_name must not be empty.")
            return contact_db.search_by_last_name(last_name)

        @self.mcp.tool(description="Search contacts by email address (case-insensitive exact match)")
        def search_by_email(email: str) -> list[dict]:
            """
            Search contacts by email address.

            Args:
                email: Email address to search for.

            Returns:
                List of matching contact records.

            Raises:
                ToolError: If ``email`` is empty.
            """
            if not email.strip():
                raise ToolError("email must not be empty.")
            return contact_db.search_by_email(email)

        @self.mcp.tool(description="Search contacts by account ID (exact match)")
        def search_by_account_id(account_id: str) -> list[dict]:
            """
            Search contacts by account ID.

            Args:
                account_id: Account ID to search for.

            Returns:
                List of matching contact records.

            Raises:
                ToolError: If ``account_id`` is empty.
            """
            if not account_id.strip():
                raise ToolError("account_id must not be empty.")
            return contact_db.search_by_account_id(account_id)

        @self.mcp.tool(description="Authenticate a contact by email and password")
        def authenticate(email: str, password: str) -> dict:
            """
            Authenticate a contact by email and password.

            Args:
                email: Contact email address.
                password: Contact password.

            Returns:
                Contact profile dict (without password) on success.

            Raises:
                ToolError: If authentication fails.
            """
            result = contact_db.authenticate(email, password)
            if result is None:
                raise ToolError("Authentication failed: invalid email or password")
            return result


# Lazy module-level ``server`` / ``mcp`` — built on first attribute access, not
# on import, so ``import mcp_server_kit.contacts`` performs no database I/O.
__getattr__ = lazy_module_instances(ContactMCPServer)

if __name__ == "__main__":
    ContactMCPServer().main()
