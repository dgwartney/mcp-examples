"""
Mock Workday HCM (MCP prefix ``workday_hcm``).

Worker profile, PTO balance and projection, and a read-only payroll rule
check. Payroll is never written: ``evaluate_pay_correction`` only says where
a correction will land. Every tool needs an active ``verification_id`` for
the same worker, and writes one ``audit_events`` row tagged ``workday_hcm``.

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    $ uv run -m mcp_server_kit.workday_hcm --transport streamable-http --port 8013
"""

from typing import Optional

from mcp_server_kit.base import AuthenticatedMCPServer, lazy_module_instances
from mcp_server_kit.cvs_hr_database import open_database

SYSTEM = "workday_hcm"


class WorkdayHcmMCPServer(AuthenticatedMCPServer):
    """MCP server for Workday worker, time-off and payroll-rule reads."""

    def __init__(self, db_path: Optional[str] = None, cvs_hr_db_path: Optional[str] = None):
        """
        Args:
            db_path: API-key database path (see ``AuthenticatedMCPServer``).
            cvs_hr_db_path: CVS HR database path (default: ``CVS_HR_DB_PATH``).
        """
        self.hr_db = open_database(cvs_hr_db_path)
        super().__init__(name="WorkdayHcmMCP", db_path=db_path)

    def _register_tools(self) -> None:
        hr_db = self.hr_db

        @self.mcp.tool(description=(
            "Get the verified colleague's worker profile: name, job title, store, "
            "base and overtime pay rates."))
        def get_worker(worker_id: str, verification_id: str = "") -> dict:
            """
            Returns:
                worker_id, first_name, last_name, display_name, job_title,
                location {store, city, state}, base_rate_usd, ot_rate_usd,
                employment_type, scheduled_weekly_hours, hire_date,
                preferred_language, worker_status.
            """
            args = dict(worker_id=worker_id, verification_id=verification_id)
            return hr_db.audited(SYSTEM, "get_worker", args,
                                 lambda: hr_db.get_worker(verification_id, worker_id))

        @self.mcp.tool(description="Get the verified colleague's current PTO balance in hours and days.")
        def get_time_off_balance(worker_id: str, verification_id: str = "") -> dict:
            """
            Returns:
                worker_id, plan ("PTO"), balance_hours, balance_days,
                accrual_per_period_hours, as_of_period_end.
            """
            args = dict(worker_id=worker_id, verification_id=verification_id)
            return hr_db.audited(SYSTEM, "get_time_off_balance", args,
                                 lambda: hr_db.get_time_off_balance(verification_id, worker_id))

        @self.mcp.tool(description=(
            "Project when the verified colleague's PTO balance reaches target_hours "
            "(convert days to hours at 8 hours per day)."))
        def project_time_off(worker_id: str, target_hours: float, verification_id: str = "") -> dict:
            """
            Returns:
                balance_hours, target_hours, accrual_per_period_hours, hours_needed,
                periods_needed, already_enough, target_pay_date,
                target_pay_date_display_en/_es, target_label (=target_label_en),
                target_label_en, target_label_es, projected_pay_dates.
            """
            args = dict(worker_id=worker_id, target_hours=target_hours,
                        verification_id=verification_id)
            return hr_db.audited(SYSTEM, "project_time_off", args,
                                 lambda: hr_db.project_time_off(verification_id, worker_id, target_hours))

        @self.mcp.tool(description=(
            "Check, read-only, which paycheck a timecard correction of the given hours "
            "lands on and whether it is off-cycle; never writes to payroll."))
        def evaluate_pay_correction(worker_id: str, hours: float, verification_id: str = "") -> dict:
            """
            Returns:
                hours, amount_usd, amount_display_en/_es, overtime, pay_date,
                pay_date_display_en/_es, off_cycle, off_cycle_threshold_hours,
                rule_id, read_only, payroll_written, correction_id.
            """
            args = dict(worker_id=worker_id, hours=hours, verification_id=verification_id)
            return hr_db.audited(SYSTEM, "evaluate_pay_correction", args,
                                 lambda: hr_db.evaluate_pay_correction(verification_id, worker_id, hours))


__getattr__ = lazy_module_instances(WorkdayHcmMCPServer)

if __name__ == "__main__":
    WorkdayHcmMCPServer().main()
