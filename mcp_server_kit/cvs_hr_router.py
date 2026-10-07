"""
Deterministic reply router for the CVS HR voice agent (MCP prefix ``cvs_hr_router``).

One tool, ``interpret_reply``, turns the caller's free-text reply into flat,
rule-based decisions (next intent, consent, PTO target, languages) so the
Artemis specialists never have to classify free text themselves. Pure
rules from ``cvs_hr_router_rules``: no verification and no data writes,
apart from one ``audit_events`` row tagged ``cvs_hr_router`` per call.

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    $ uv run -m mcp_server_kit.cvs_hr_router --transport streamable-http --port 8016
"""

from typing import Optional

from mcp_server_kit.base import AuthenticatedMCPServer, lazy_module_instances
from mcp_server_kit.cvs_hr_database import open_database
from mcp_server_kit.cvs_hr_router_rules import interpret_reply as _interpret

SYSTEM = "cvs_hr_router"


class CvsHrRouterMCPServer(AuthenticatedMCPServer):
    """MCP server exposing ``interpret_reply``."""

    def __init__(self, db_path: Optional[str] = None, cvs_hr_db_path: Optional[str] = None):
        """
        Args:
            db_path: API-key database path (see ``AuthenticatedMCPServer``).
            cvs_hr_db_path: CVS HR database path, used only for the audit row
                (default: ``CVS_HR_DB_PATH``).
        """
        self.hr_db = open_database(cvs_hr_db_path)
        super().__init__(name="CvsHrRouterMCP", db_path=db_path)

    def _register_tools(self) -> None:
        hr_db = self.hr_db

        @self.mcp.tool(description=(
            "Interpret the caller's latest reply with fixed rules: next intent, consent "
            "yes/no/unclear, PTO target hours, recap language and language requests."))
        def interpret_reply(text: str, expecting: str = "") -> dict:
            """
            Args:
                text: The caller's words, verbatim.
                expecting: Optional hint: ``consent``, ``pto_target`` or ``next``.

            Returns:
                intent (pay|pto|leave|recap|language|close|other|none),
                pending_intent, intents, consent (yes|no|unclear), target_hours,
                recap_language (es|en|""), wants_spanish, language_name,
                wants_human, expecting.
            """
            args = dict(text=text, expecting=expecting)
            return hr_db.audited(SYSTEM, "interpret_reply", args,
                                 lambda: _interpret(text, expecting).to_dict())


__getattr__ = lazy_module_instances(CvsHrRouterMCPServer)

if __name__ == "__main__":
    CvsHrRouterMCPServer().main()
