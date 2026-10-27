"""
Mock CVS demo systems for Phase 2 (MCP prefix ``cvs_demo_systems``).

One server answers for Workday and ServiceNow in CVS's two Phase 2 demo
scenarios: identity (EMPLID + date of birth, SMS one-time code), timecard and
pay results, absence balances and time off, HR cases, SMS, and the call
checkpoint that lets a dropped call resume. Thin adapter over
``cvs_demo_database.CvsDemoDatabase``; every call writes one audit row.

``reset_demo`` is exposed for operators (``agents/cvs-phase2/scripts/demo-reset.sh``)
and is never bound to an agent.

A second server, :class:`CvsDemoDeskMCPServer` (MCP prefix ``cvs_demo_desk``),
carries only ``get_latest_handoff`` for the transfer target (Sam, Colleague
Relations), on its own path and optionally its own API key. That lookup is a
demo shortcut: in production the context travels with the call, in the SIP
header / UUI or through the CCaaS API keyed to that call.

Author:
    David Gwartney <david.gwartney@gmail.com>

Environment Variables:
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_MESSAGING_SERVICE_SID:
        Real SMS delivery when the demo's SMS switch is on (see ``reset_demo``).
    CVS_DEMO_DESK_API_KEY:
        Optional. When set, ``/cvs_demo_desk/mcp`` accepts only this key; when
        unset it accepts the shared keys in ``MCP_DB_PATH`` like every other server.

Example:
    $ uv run -m mcp_server_kit.cvs_demo_systems --transport streamable-http --port 8017
"""

import os
import secrets
from typing import Optional

import httpx
from starlette.middleware import Middleware as StarletteMiddleware

from mcp_server_kit.base import AuthenticatedMCPServer, lazy_module_instances
from mcp_server_kit.cvs_demo_database import HANDOFF_WINDOW_MINUTES, open_database
from mcp_server_kit.middleware import ApiKeyMiddleware

DESK_API_KEY_ENV = "CVS_DEMO_DESK_API_KEY"

_TWILIO_BASE = "https://api.twilio.com/2010-04-01"


def twilio_sender(to: str, body: str, client: Optional[httpx.Client] = None) -> dict:
    """Send one SMS through the Twilio Messaging Service; returns ``{"sid"}`` or ``{"error"}``."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    service = os.environ.get("TWILIO_MESSAGING_SERVICE_SID", "")
    if not (sid and token and service):
        return {"error": "twilio_not_configured"}
    http = client or httpx.Client(timeout=10.0)
    try:
        resp = http.post(f"{_TWILIO_BASE}/Accounts/{sid}/Messages.json", auth=(sid, token),
                         data={"MessagingServiceSid": service, "To": to, "Body": body})
    except httpx.RequestError as exc:
        return {"error": f"request_failed: {exc}"}
    finally:
        if client is None:
            http.close()
    if not resp.is_success:
        return {"error": f"twilio_http_{resp.status_code}"}
    return {"sid": resp.json().get("sid", "")}


class CvsDemoSystemsMCPServer(AuthenticatedMCPServer):
    """MCP server for the CVS Phase 2 demo (Workday + ServiceNow mock)."""

    def __init__(self, db_path: Optional[str] = None, cvs_demo_db_path: Optional[str] = None,
                 sender=twilio_sender):
        """
        Args:
            db_path: API-key database path (see ``AuthenticatedMCPServer``).
            cvs_demo_db_path: demo database path (default: ``CVS_DEMO_DB_PATH``
                env var, else ``cvs_demo.db`` in the cwd).
            sender: ``(to, body) -> dict`` used for real SMS (tests pass a fake).
        """
        self.demo_db = open_database(cvs_demo_db_path)
        self.sender = sender
        super().__init__(name="CvsDemoSystemsMCP", db_path=db_path)

    def _register_tools(self) -> None:
        db = self.demo_db
        server = self

        def run(tool: str, args: dict, fn):
            return db.audited(tool, args, fn)

        @self.mcp.tool(description=(
            "Verify the caller with the 7-digit EMPLID and date of birth (any format, or keypad MMDDYYYY). "
            "entry is 'keypad' or 'voice'; pass attempt=1, then 2 on the retry. On a failed attempt, "
            "otp_available says a one-time code can be texted instead."))
        def verify_emplid_dob(emplid: str, dob: str, attempt: int = 1, entry: str = "voice") -> dict:
            """
            Returns:
                verified, outcome (verified | partial | bad_date | no_match), emplid,
                emplid_last4, emplid_display ("ending 7203"), first_name, colleague_name,
                auth_method, mobile_last4; on failure attempts, otp_available, escalate, display.
            """
            args = dict(emplid=emplid, dob="***", attempt=attempt, entry=entry)
            return run("verify_emplid_dob", args, lambda: db.verify_emplid_dob(emplid, dob, attempt, entry))

        @self.mcp.tool(description=(
            "Text a six-digit one-time code to the colleague's mobile on file. Give the EMPLID, or the "
            "caller's phone number (ani) on a callback before the EMPLID is known."))
        def send_otp(emplid: Optional[str] = "", ani: Optional[str] = "") -> dict:
            """
            Returns:
                sent, mobile_last4, emplid_last4, expires_in_seconds, delivery (sms | rehearsal);
                or error + display.
            """
            return run("send_otp", dict(emplid=emplid, ani=ani),
                       lambda: db.send_otp(emplid, ani, sender=server.sender))

        @self.mcp.tool(description=(
            "Check the six-digit code the caller reads back. Codes expire after 5 minutes and allow 3 tries. "
            "Give the same emplid or ani used for send_otp."))
        def verify_otp(code: str, emplid: Optional[str] = "", ani: Optional[str] = "") -> dict:
            """
            Returns:
                verified, outcome, emplid, emplid_last4, first_name, colleague_name, auth_method;
                on failure tries_left, escalate, display; or error (expired | locked | no_code).
            """
            return run("verify_otp", dict(code=code, emplid=emplid, ani=ani),
                       lambda: db.verify_otp(code, emplid, ani))

        @self.mcp.tool(description="Get the verified colleague's timecard for the period (default: ending 2026-10-03).")
        def get_timecard(emplid: str, period_end: Optional[str] = "") -> dict:
            """
            Returns:
                period_end, period_end_display, hours_recorded, approved_hours, unapproved_hours,
                approval_status, approver, team_approval, leave_display, display.
            """
            return run("get_timecard", dict(emplid=emplid, period_end=period_end),
                       lambda: db.get_timecard(emplid, period_end))

        @self.mcp.tool(description="Get the verified colleague's recent pay results, including a short check and why.")
        def get_pay_results(emplid: str) -> dict:
            """
            Returns:
                checks[], short_check_display, next_regular_check_display, off_cycle_available,
                off_cycle_pay_date_display, resolution, display.
            """
            return run("get_pay_results", dict(emplid=emplid), lambda: db.get_pay_results(emplid))

        @self.mcp.tool(description=(
            "Pay the unapproved hours from the short check: option 'next_check' or 'off_cycle'. "
            "Only after the colleague chose the option."))
        def resolve_short_pay(emplid: str, option: str) -> dict:
            """
            Returns:
                resolved, pay_outcome, reference, reference_spoken, pay_date_display, hours, display.
            """
            return run("resolve_short_pay", dict(emplid=emplid, option=option),
                       lambda: db.resolve_short_pay(emplid, option))

        @self.mcp.tool(description="Get the verified colleague's absence balances (PTO, sick, floating holiday).")
        def get_absence_balances(emplid: str) -> dict:
            """
            Returns:
                balances[] (type, name, hours, days, display), accrual_hours_per_period,
                as_of, next_monday, display.
            """
            return run("get_absence_balances", dict(emplid=emplid), lambda: db.get_absence_balances(emplid))

        @self.mcp.tool(description="List the absence types, each with its one-line rule.")
        def list_absence_types() -> dict:
            """
            Returns:
                types[] (type, name, uses_balance, rule), hours_per_day.
            """
            return run("list_absence_types", {}, db.list_absence_types)

        @self.mcp.tool(description=(
            "Submit time off after the colleague confirmed it. absence_type: pto, sick, floating_holiday, "
            "bereavement or jury_duty; start_date ISO (YYYY-MM-DD); days or hours. Errors: WRONG_TYPE, "
            "INSUFFICIENT_BALANCE (with the numbers), WRONG_AMOUNT, BAD_DATE. validate_only=true runs the same "
            "checks without submitting (use it before asking the colleague to confirm)."))
        def submit_time_off(emplid: str, absence_type: str, start_date: str, days: float = 0,
                            hours: float = 0, reason: Optional[str] = "", validate_only: bool = False) -> dict:
            """
            Returns:
                submitted, confirmation, confirmation_spoken, type_name, days, dates_display,
                remaining_days, display; or error + display + the numbers.
            """
            args = dict(emplid=emplid, absence_type=absence_type, start_date=start_date, days=days,
                        hours=hours, reason=reason, validate_only=validate_only)
            return run("submit_time_off", args, lambda: db.submit_time_off(
                emplid, absence_type, start_date, days, hours, reason, validate_only))

        @self.mcp.tool(description="List the verified colleague's open HR cases (ServiceNow).")
        def get_open_cases(emplid: str) -> dict:
            """
            Returns:
                count, case_ids, cases[] (case_id, case_last4, team, summary, restricted,
                opened_weekday, opened_display).
            """
            return run("get_open_cases", dict(emplid=emplid), lambda: db.get_open_cases(emplid))

        @self.mcp.tool(description=(
            "Open an HR case. team: Payroll, Colleague Relations, Benefits, Leave of Absence, Time and "
            "Attendance or HR Service Center. restricted=true for a confidential case (Colleague Relations "
            "is always restricted)."))
        def create_case(emplid: str, team: str, summary: str, restricted: bool = False,
                        case_type: Optional[str] = "") -> dict:
            """
            Returns:
                created, case_id, case_id_spoken, case_last4, team, restricted, state, opened_display.
            """
            args = dict(emplid=emplid, team=team, summary=summary, restricted=restricted, case_type=case_type)
            return run("create_case", args, lambda: db.create_case(emplid, team, summary, restricted, case_type))

        @self.mcp.tool(description="Add a note to an HR case and optionally change its state.")
        def update_case(case_id: str, note: Optional[str] = "", state: Optional[str] = "") -> dict:
            """
            Returns:
                updated, notes (count), case_id, state.
            """
            return run("update_case", dict(case_id=case_id, note=note, state=state),
                       lambda: db.update_case(case_id, note, state))

        @self.mcp.tool(description="Text the verified colleague's mobile on file (for example a case number).")
        def send_sms(emplid: str, message: str) -> dict:
            """
            Returns:
                sent, suppressed, mobile_last4, body.
            """
            return run("send_sms", dict(emplid=emplid, message=message),
                       lambda: db.send_sms(emplid, message, sender=server.sender))

        @self.mcp.tool(description=(
            "Checkpoint the call so a dropped call can resume: a one-line summary, the intents and any case "
            "IDs. Key on the caller's number (ani) and, once verified, the EMPLID. The first save returns "
            "context_id; pass it on every later save in the same call."))
        def save_call_context(emplid: Optional[str] = "", ani: Optional[str] = "", summary: Optional[str] = "", intents: Optional[str] = "",
                              open_case_ids: Optional[str] = "", pay_case_id: Optional[str] = "", cr_case_id: Optional[str] = "",
                              absence_request: Optional[str] = "", context_id: Optional[str] = "") -> dict:
            """
            Returns:
                saved, context_id, keyed_on.
            """
            args = dict(emplid=emplid, ani=ani, summary=summary, intents=intents, open_case_ids=open_case_ids,
                        pay_case_id=pay_case_id, cr_case_id=cr_case_id, absence_request=absence_request,
                        context_id=context_id)
            return run("save_call_context", args, lambda: db.save_call_context(**args))

        @self.mcp.tool(description=(
            "Look for an earlier call from this caller in the last 30 minutes (pass this call's own "
            "context_id as exclude_context_id). With only ani it returns first_name and mobile_last4 (enough "
            "to greet and send a code); with a verified emplid it also returns the summary, intents and cases."))
        def get_call_context(ani: Optional[str] = "", emplid: Optional[str] = "", exclude_context_id: Optional[str] = "") -> dict:
            """
            Returns:
                found, context_id, minutes_ago, verified_required, first_name, mobile_last4, emplid_last4;
                for a verified emplid also summary, has_summary, intents, open_case_ids, pay_case_id, cr_case_id.
            """
            args = dict(ani=ani, emplid=emplid, exclude_context_id=exclude_context_id)
            return run("get_call_context", args, lambda: db.get_call_context(ani, emplid, exclude_context_id))

        @self.mcp.tool(description=(
            "Admin only, never for callers: re-seed the demo data (status_only=true just reports). "
            "sms_enabled turns real SMS delivery on or off."))
        def reset_demo(status_only: bool = False, sms_enabled: Optional[bool] = None) -> dict:
            """
            Returns:
                seeded_on, as_of, sms_enabled, sms_to_set, benefits_case_opened,
                benefits_case_weekday, counts.
            """
            if status_only:
                return db.status()
            return run("reset_demo", dict(sms_enabled=sms_enabled), lambda: db.reset(sms_enabled))


class StaticKeyValidator:
    """Accepts exactly one API key (constant-time compare); same interface as ``DatabaseManager``."""

    def __init__(self, key: str):
        self._key = key.encode("utf-8")

    def validate_key(self, api_key: Optional[str]) -> bool:
        return api_key is not None and secrets.compare_digest(api_key.encode("utf-8"), self._key)


class CvsDemoDeskMCPServer(AuthenticatedMCPServer):
    """
    MCP server for the transfer target's desk (MCP prefix ``cvs_demo_desk``): only
    ``get_latest_handoff``, over the same demo database as ``cvs_demo_systems``.

    It lives on its own path so the hand-off lookup is not reachable with the key
    Savvy's tools use. With ``CVS_DEMO_DESK_API_KEY`` set it accepts only that key;
    unset, it falls back to the shared keys (``MCP_DB_PATH``).
    """

    def __init__(self, db_path: Optional[str] = None, cvs_demo_db_path: Optional[str] = None,
                 desk_api_key: Optional[str] = None):
        """
        Args:
            db_path: shared API-key database path (see ``AuthenticatedMCPServer``).
            cvs_demo_db_path: demo database path (default: ``CVS_DEMO_DB_PATH``).
            desk_api_key: the only key accepted (default: ``CVS_DEMO_DESK_API_KEY``;
                empty means the shared keys).
        """
        self.demo_db = open_database(cvs_demo_db_path)
        super().__init__(name="CvsDemoDeskMCP", db_path=db_path)
        key = (desk_api_key if desk_api_key is not None else os.environ.get(DESK_API_KEY_ENV, "")).strip()
        self.own_key = bool(key)
        if key:
            self._http_middleware = [StarletteMiddleware(ApiKeyMiddleware, db_manager=StaticKeyValidator(key))]

    def _register_tools(self) -> None:
        db = self.demo_db

        @self.mcp.tool(description=(
            "For the agent that takes a transferred call: the context of the most recent escalation from a "
            "colleague verified in the last within_minutes (default 10), with no input needed. Returned once: "
            "a second call gets found=false. Gives the colleague's first name, the reason "
            "(colleague_relations | payroll | other), the open Payroll and confidential Colleague Relations "
            "case numbers (spoken), the pay outcome, a one-sentence concern summary and a display line to "
            "open the call."))
        def get_latest_handoff(within_minutes: int = HANDOFF_WINDOW_MINUTES) -> dict:
            """
            Demo shortcut: the demo transfer carries no EMPLID, so the most recent escalation in the
            single demo tenant wins. In production the context travels with the call (SIP header /
            UUI, or the CCaaS API keyed to the call). Never returns the full EMPLID, a phone number
            or the date of birth; it marks the hand-off consumed and otherwise changes nothing.

            Returns:
                found, reason, first_name, colleague_name, emplid_last4, call_reason, pay_case_id,
                pay_case_spoken, pay_outcome, pay_outcome_display, cr_case_id, cr_case_spoken,
                concern_summary, minutes_ago, within_minutes, display.
            """
            return db.audited("get_latest_handoff", dict(within_minutes=within_minutes),
                              lambda: db.get_latest_handoff(within_minutes))


__getattr__ = lazy_module_instances(CvsDemoSystemsMCPServer)

if __name__ == "__main__":
    CvsDemoSystemsMCPServer().main()
