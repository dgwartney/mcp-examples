"""
Mock ServiceNow HR Service Delivery (MCP prefix ``servicenow_hrsd``).

HR cases shaped like ``sn_hr_core_case``. Cases need an active
verification, with one exception (H4): an unverified caller who failed
identity checks may get ``hr_service="Identity verification"`` with no
``subject_person``; its text is stored with digits masked. Case numbers
start at HR-<year>-0917 after a reset. Every call writes one
``audit_events`` row tagged ``servicenow_hrsd``.

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    $ uv run -m mcp_server_kit.servicenow_hrsd --transport streamable-http --port 8015
"""

from typing import Optional, Union

from mcp_server_kit.base import AuthenticatedMCPServer, lazy_module_instances
from mcp_server_kit.cvs_hr_database import open_database

SYSTEM = "servicenow_hrsd"


class ServicenowHrsdMCPServer(AuthenticatedMCPServer):
    """MCP server for HR cases: create_hr_case, add_work_note, get_hr_cases."""

    def __init__(self, db_path: Optional[str] = None, cvs_hr_db_path: Optional[str] = None):
        """
        Args:
            db_path: API-key database path (see ``AuthenticatedMCPServer``).
            cvs_hr_db_path: CVS HR database path (default: ``CVS_HR_DB_PATH``).
        """
        self.hr_db = open_database(cvs_hr_db_path)
        super().__init__(name="ServicenowHrsdMCP", db_path=db_path)

    def _register_tools(self) -> None:
        hr_db = self.hr_db

        @self.mcp.tool(description=(
            "Open an HR case recording the call and get back the recap sms_body (or, for a "
            "caller who could not be verified, an 'Identity verification' case with no "
            "subject_person)."))
        def create_hr_case(
            subject_person: str = "",
            hr_service: str = "",
            contact_type: str = "phone",
            short_description: str = "",
            description: str = "",
            related_records: Union[list[str], str, None] = None,
            state: str = "new",
            resolved_by: str = "",
            assignment_group: str = "",
            verification_id: str = "",
            leave_discussed: str = "no",
            language: str = "en",
        ) -> dict:
            """
            Returns:
                number (e.g. HR-2026-0917), sys_id, state, hr_service,
                subject_person, related_records, related_records_detail,
                assignment_group, resolved_by, opened_at, resolved_at, verified,
                sms_body (recap text for the SMS, in ``language``: en|es, built
                from what happened in this call; leave line only when
                leave_discussed="yes"), language.
            """
            args = dict(subject_person=subject_person, hr_service=hr_service,
                        contact_type=contact_type, short_description=short_description,
                        description=description, related_records=related_records, state=state,
                        resolved_by=resolved_by, assignment_group=assignment_group,
                        verification_id=verification_id, leave_discussed=leave_discussed,
                        language=language)
            return hr_db.audited(SYSTEM, "create_hr_case", args,
                                 lambda: hr_db.create_hr_case(
                                     verification_id, subject_person, hr_service, contact_type,
                                     short_description, description, related_records, state,
                                     resolved_by, assignment_group, leave_discussed, language))

        @self.mcp.tool(description="Add a work note to one of the verified colleague's HR cases.")
        def add_work_note(number: str, note: str, verification_id: str = "") -> dict:
            """
            Returns:
                number, sys_id, work_notes_count, last_note, updated_at.
            """
            args = dict(number=number, note=note, verification_id=verification_id)
            return hr_db.audited(SYSTEM, "add_work_note", args,
                                 lambda: hr_db.add_work_note(verification_id, number, note))

        @self.mcp.tool(description=(
            "List the verified colleague's HR cases, e.g. to answer 'do I have a case open?' "
            "(state='open' for open cases only)."))
        def get_hr_cases(subject_person: str, state: str = "", verification_id: str = "") -> dict:
            """
            Returns:
                subject_person, count, cases[].
            """
            args = dict(subject_person=subject_person, state=state, verification_id=verification_id)
            return hr_db.audited(SYSTEM, "get_hr_cases", args,
                                 lambda: hr_db.get_hr_cases(verification_id, subject_person, state))


__getattr__ = lazy_module_instances(ServicenowHrsdMCPServer)

if __name__ == "__main__":
    ServicenowHrsdMCPServer().main()
