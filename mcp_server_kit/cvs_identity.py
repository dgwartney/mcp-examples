"""
Mock CVS identity service (MCP prefix ``cvs_identity``).

Verifies a caller by 7-digit colleague ID or 10-digit mobile on file and
issues the ``verification_id`` that every other CVS HR system requires (it
is also the key of the per-call sandbox). Thin adapter over
``cvs_hr_database.CvsHrDatabase``; every call writes one ``audit_events``
row tagged ``cvs_identity``.

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    $ uv run -m mcp_server_kit.cvs_identity --transport streamable-http --port 8012
"""

from typing import Optional

from mcp_server_kit.base import AuthenticatedMCPServer, lazy_module_instances
from mcp_server_kit.cvs_hr_database import open_database

SYSTEM = "cvs_identity"


class CvsIdentityMCPServer(AuthenticatedMCPServer):
    """MCP server for caller verification: verify_colleague, revoke_verification."""

    def __init__(self, db_path: Optional[str] = None, cvs_hr_db_path: Optional[str] = None):
        """
        Args:
            db_path: API-key database path (see ``AuthenticatedMCPServer``).
            cvs_hr_db_path: CVS HR database path (default: ``CVS_HR_DB_PATH``
                env var, else ``cvs_hr.db`` in the cwd).
        """
        self.hr_db = open_database(cvs_hr_db_path)
        super().__init__(name="CvsIdentityMCP", db_path=db_path)

    def _register_tools(self) -> None:
        hr_db = self.hr_db

        @self.mcp.tool(description=(
            "Verify the caller before any personal HR data, using the 7-digit colleague ID "
            "or the 10-digit mobile number on file; pass attempt=1, then 2 on the retry."))
        def verify_colleague(colleague_id: str = "", mobile: str = "", attempt: int = 1) -> dict:
            """
            Returns:
                verified, verification_id, colleague_id, display_name, first_name,
                method, sms_to, sms_suppressed, attempts, escalate (true after the
                2nd failed attempt), masked_input; on failure also reason.
                outcome is verified | no_match | partial | no_number. partial and
                no_number (the caller is still finding the number) are not counted
                as attempts and never escalate; partial also gives heard_display.
            """
            args = dict(colleague_id=colleague_id, mobile=mobile, attempt=attempt)
            return hr_db.audited(SYSTEM, "verify_colleague", args,
                                 lambda: hr_db.verify_colleague(colleague_id, mobile, attempt))

        @self.mcp.tool(description=(
            "Revoke the current verification when the caller says the matched record is "
            "not them, so nothing more about that record can be read."))
        def revoke_verification(verification_id: str) -> dict:
            """
            Returns:
                revoked, already_revoked, status ("revoked"), verification_id.
            """
            args = dict(verification_id=verification_id)
            return hr_db.audited(SYSTEM, "revoke_verification", args,
                                 lambda: hr_db.revoke_verification(verification_id))


__getattr__ = lazy_module_instances(CvsIdentityMCPServer)

if __name__ == "__main__":
    CvsIdentityMCPServer().main()
