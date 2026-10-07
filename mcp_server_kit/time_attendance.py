"""
Mock time and attendance system (MCP prefix ``time_attendance``).

Reads a closed week's timecard (punches, auto meal deductions, hours short,
overtime price) and writes timecard corrections, which are reversible within
the call. Corrections need ``consent=true`` and an active verification; they
live in that verification's sandbox. Every call writes one ``audit_events``
row tagged ``time_attendance``.

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    $ uv run -m mcp_server_kit.time_attendance --transport streamable-http --port 8014
"""

from typing import Optional, Union

from mcp_server_kit.base import AuthenticatedMCPServer, lazy_module_instances
from mcp_server_kit.cvs_hr_database import open_database

SYSTEM = "time_attendance"


class TimeAttendanceMCPServer(AuthenticatedMCPServer):
    """MCP server for timecards and timecard corrections."""

    def __init__(self, db_path: Optional[str] = None, cvs_hr_db_path: Optional[str] = None):
        """
        Args:
            db_path: API-key database path (see ``AuthenticatedMCPServer``).
            cvs_hr_db_path: CVS HR database path (default: ``CVS_HR_DB_PATH``).
        """
        self.hr_db = open_database(cvs_hr_db_path)
        super().__init__(name="TimeAttendanceMCP", db_path=db_path)

    def _register_tools(self) -> None:
        hr_db = self.hr_db

        @self.mcp.tool(description=(
            "Get the verified colleague's timecard for a closed week (default: the latest "
            "closed week ending Saturday), including any meal deductions taken without a break."))
        def get_timecard(worker_id: str, period_end: str = "", verification_id: str = "") -> dict:
            """
            Returns:
                period_start, period_end, period_end_display_en/_es, days[] (date,
                punches, hours_worked, auto_deduct {type, minutes}, break_punched,
                corrected), deduction_dates, deduction_days_display_en/_es,
                break_punched, discrepancy, hours_short, week_hours_worked,
                paid_hours, overtime, base_rate_usd, ot_rate_usd, amount_usd,
                amount_display_en/_es, corrections.
            """
            args = dict(worker_id=worker_id, period_end=period_end, verification_id=verification_id)
            return hr_db.audited(SYSTEM, "get_timecard", args,
                                 lambda: hr_db.get_timecard(verification_id, worker_id, period_end))

        @self.mcp.tool(description=(
            "Remove wrongly auto-deducted meal breaks from the timecard after the colleague "
            "says yes (consent=true); list the dates, or exclude any the colleague disputes."))
        def submit_timecard_correction(
            worker_id: str,
            period_end: str,
            dates: Union[list[str], str, None] = None,
            remove_auto_deduct: str = "meal",
            audit_note: str = "",
            consent: bool = False,
            exclude_dates: Union[list[str], str, None] = None,
            verification_id: str = "",
        ) -> dict:
            """
            Returns:
                correction_id, status ("applied"), dates, dates_display_en/_es,
                hours, overtime, amount_usd, amount_display_en/_es,
                remaining_hours_short.
            """
            args = dict(worker_id=worker_id, period_end=period_end, dates=dates,
                        remove_auto_deduct=remove_auto_deduct, audit_note=audit_note,
                        consent=consent, exclude_dates=exclude_dates,
                        verification_id=verification_id)
            return hr_db.audited(SYSTEM, "submit_timecard_correction", args,
                                 lambda: hr_db.submit_timecard_correction(
                                     verification_id, worker_id, period_end, dates,
                                     remove_auto_deduct, audit_note, consent, exclude_dates))

        @self.mcp.tool(description=(
            "Reverse a timecard correction made earlier in this call when the colleague "
            "changes their mind."))
        def cancel_timecard_correction(verification_id: str, correction_id: str) -> dict:
            """
            Returns:
                correction_id, status ("reversed"), dates, hours,
                restored_hours_short, amount_usd.
            """
            args = dict(verification_id=verification_id, correction_id=correction_id)
            return hr_db.audited(SYSTEM, "cancel_timecard_correction", args,
                                 lambda: hr_db.cancel_timecard_correction(verification_id, correction_id))


__getattr__ = lazy_module_instances(TimeAttendanceMCPServer)

if __name__ == "__main__":
    TimeAttendanceMCPServer().main()
