"""
Mock data store for the CVS Phase 2 demo systems (MCP prefix ``cvs_demo_systems``).

One SQLite file (``CVS_DEMO_DB_PATH``) answers for both Workday and
ServiceNow in CVS's two Phase 2 scenarios, seeded with one colleague, Jeff M.
It is separate from Savvy's ``cvs_hr.db`` so the Phase 1 demo data is never
touched.

Unlike ``cvs_hr_database`` the seed never rolls forward on its own: the
dates are the ones in the build brief (period ending 2026-10-03, short check
2026-10-09, next check 2026-10-23). Only the open benefits case is relative:
:meth:`CvsDemoDatabase.reset` dates it two days before "today" so the agent
can say which weekday it was opened.

Every personal-data method requires a verification of the EMPLID (by EMPLID
plus date of birth, or by the SMS one-time code) made in the last
``VERIFICATION_TTL_MINUTES``; otherwise it returns ``error="not_verified"``.
Refusals are dicts with an ``error`` key and a ``display`` line the agent can
speak, never exceptions.

Author:
    David Gwartney <david.gwartney@gmail.com>

Environment Variables:
    CVS_DEMO_DB_PATH:       SQLite file (default: cvs_demo.db in the cwd).
    CVS_DEMO_AS_OF:         Optional ISO date overriding "today" (tests).
    CVS_HR_DEMO_SMS_TO:     Demo handset that receives every SMS (shared with Savvy).
    CVS_DEMO_REHEARSAL_OTP: Code used while SMS is off (default 135790).
    CVS_DEMO_ANI_ALIASES:   Comma-separated caller numbers that identify Jeff, besides his
                            mobile on file (the role-player's phone on demo day).
"""

import hashlib
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterator, Optional
from zoneinfo import ZoneInfo

from mcp_server_kit import cvs_hr_rules as rules
from mcp_server_kit.cvs_hr_database import coerce_bool, coerce_list, normalize_e164
from mcp_server_kit.spoken_dates import parse_spoken_date

SYSTEM = "cvs_demo_systems"
DEMO_TZ = ZoneInfo("America/Los_Angeles")
AS_OF_ENV = "CVS_DEMO_AS_OF"
SMS_TO_ENV = "CVS_HR_DEMO_SMS_TO"
REHEARSAL_OTP_ENV = "CVS_DEMO_REHEARSAL_OTP"
ANI_ALIASES_ENV = "CVS_DEMO_ANI_ALIASES"
DEFAULT_REHEARSAL_OTP = "135790"
HOURS_PER_DAY = 8.0
OTP_TTL_SECONDS = 300
OTP_MAX_TRIES = 3
VERIFICATION_TTL_MINUTES = 120
RECALL_WINDOW_MINUTES = 30
FIRST_CASE_SEQ = 98562
FIRST_TIME_OFF_SEQ = 410221

JEFF = {
    "emplid": "2217203", "first_name": "Jeff", "display_name": "Jeff M.", "dob": "1991-03-14",
    "mobile": "+15550104417", "job_title": "Pharmacy Technician", "store": "6218",
    "manager": "Roberta L.", "second_level_leader": "Dana K.",
}
PERIOD = {"start": date(2026, 9, 20), "end": date(2026, 10, 3)}
UNAPPROVED_HOURS = 22.0
SHORT_CHECK = date(2026, 10, 9)
NEXT_CHECK = date(2026, 10, 23)
LEAVE = (date(2026, 10, 5), date(2026, 10, 16))
BENEFITS_CASE = "HRC0098561"
BALANCES = {"pto": 24.0, "sick": 16.0, "floating_holiday": 8.0}
ACCRUAL_PER_PERIOD = 6.15

ABSENCE_TYPES = [
    {"type": "pto", "name": "PTO", "uses_balance": True,
     "rule": "Paid time off for vacations, personal errands and short personal absences such as a move."},
    {"type": "sick", "name": "Sick time", "uses_balance": True,
     "rule": "Your own illness, or caring for a sick family member; not for planned personal time."},
    {"type": "floating_holiday", "name": "Floating holiday", "uses_balance": True,
     "rule": "One 8-hour day a year that you choose, taken as a whole day."},
    {"type": "bereavement", "name": "Bereavement", "uses_balance": False,
     "rule": "Up to 3 paid days after the death of a family member."},
    {"type": "jury_duty", "name": "Jury duty", "uses_balance": False,
     "rule": "Paid time to serve on a jury, with a copy of the summons."},
    {"type": "leave_of_absence", "name": "Leave of absence", "uses_balance": False,
     "rule": ("A serious health condition, caring for a family member, parental or military leave, "
              "usually more than 3 workdays; requested through the Leave of Absence team, not as time off.")},
]
_TYPES = {t["type"]: t for t in ABSENCE_TYPES}
_TYPE_ALIASES = {
    "paid time off": "pto", "vacation": "pto", "personal": "pto", "sick time": "sick",
    "floating": "floating_holiday", "floating holiday": "floating_holiday", "holiday": "floating_holiday",
    "loa": "leave_of_absence", "leave": "leave_of_absence", "leave of absence": "leave_of_absence",
    "jury": "jury_duty", "jury duty": "jury_duty", "bereavement leave": "bereavement",
}
MAX_BEREAVEMENT_DAYS = 3

TEAMS = {
    "payroll": "Payroll", "colleague relations": "Colleague Relations", "benefits": "Benefits",
    "leave": "Leave of Absence", "leave of absence": "Leave of Absence",
    "time and attendance": "Time and Attendance", "hr service center": "HR Service Center",
}
RESTRICTED_TEAMS = {"Colleague Relations"}
CASE_STATES = {"new", "work_in_progress", "awaiting_info", "resolved", "closed"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS colleagues (
    emplid TEXT PRIMARY KEY, first_name TEXT, display_name TEXT, dob TEXT, mobile TEXT,
    job_title TEXT, store TEXT, manager TEXT, second_level_leader TEXT);
CREATE TABLE IF NOT EXISTS balances (emplid TEXT, type TEXT, hours REAL, PRIMARY KEY (emplid, type));
CREATE TABLE IF NOT EXISTS time_off (
    confirmation TEXT PRIMARY KEY, emplid TEXT, type TEXT, start_date TEXT, end_date TEXT,
    hours REAL, created_at TEXT);
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY, emplid TEXT, team TEXT, case_type TEXT, summary TEXT,
    restricted INTEGER, state TEXT, opened_on TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS pay_resolutions (
    reference TEXT PRIMARY KEY, emplid TEXT, option TEXT, pay_date TEXT, hours REAL, created_at TEXT);
CREATE TABLE IF NOT EXISTS verifications (emplid TEXT PRIMARY KEY, method TEXT, verified_at TEXT);
CREATE TABLE IF NOT EXISTS otps (emplid TEXT PRIMARY KEY, code_hash TEXT, expires_at TEXT, tries INTEGER);
CREATE TABLE IF NOT EXISTS call_context (
    id INTEGER PRIMARY KEY AUTOINCREMENT, emplid TEXT, ani TEXT, summary TEXT, intents TEXT,
    open_case_ids TEXT, pay_case_id TEXT, cr_case_id TEXT, absence_request TEXT, updated_at TEXT,
    summary_verified INTEGER DEFAULT 0, token TEXT);
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tool TEXT, args TEXT, result TEXT, at TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""
_DATA_TABLES = ("colleagues", "balances", "time_off", "cases", "pay_resolutions", "verifications",
                "otps", "call_context", "audit_events", "meta")


# ---------------------------------------------------------------------------
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _err(code: str, display: str, **extra) -> dict:
    return {"error": code, "display": display, **extra}


def as_of_date() -> date:
    """``CVS_DEMO_AS_OF`` when set, else today in Pacific time (the demo's time zone)."""
    override = os.environ.get(AS_OF_ENV, "").strip()
    if override:
        return date.fromisoformat(override)
    return datetime.now(DEMO_TZ).date()


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _last4(value: str) -> str:
    return rules.digits_only(value)[-4:]


def spoken_digits(value: str) -> str:
    """``'410221' -> 'four one zero, two two one'``: digits in groups of three, for TTS read-back."""
    words = [rules.number_word_en(int(c)) for c in rules.digits_only(value)]
    return ", ".join(" ".join(words[i:i + 3]) for i in range(0, len(words), 3))


def days_text(days: float) -> str:
    """``3 -> 'three days'``, ``1 -> 'one day'``, ``2.5 -> '2.5 days'``."""
    if float(days).is_integer():
        n = int(days)
        return f"{rules.number_word_en(n)} day{'s' if n != 1 else ''}"
    return f"{rules.number_display(days)} days"


def parse_dob(value: Any) -> Optional[date]:
    """
    Accept the ways a caller gives a date of birth: ``1991-03-14``,
    ``03/14/1991``, ``March 14 1991``, keypad ``03141991`` (MMDDYYYY), the
    spoken digits of any of those, or spoken English or Spanish
    (``catorce de marzo de 1991``, see :mod:`spoken_dates`). Returns None when
    it isn't a date.
    """
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    plain = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%B %d %Y", "%B %d, %Y", "%b %d %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(plain, fmt).date()
        except ValueError:
            continue
    d = rules.digits_only(text)
    if len(d) == 8:
        for fmt in ("%m%d%Y", "%Y%m%d"):
            try:
                return datetime.strptime(d, fmt).date()
            except ValueError:
                continue
    return parse_spoken_date(text)


def workdays_from(start: date, count: int) -> list[date]:
    """``count`` consecutive Monday-Friday dates starting at ``start`` (moved to Monday if a weekend)."""
    out, day = [], start
    while len(out) < count:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def normalize_type(value: str) -> str:
    key = str(value or "").strip().lower().replace("-", " ")
    if key.replace(" ", "_") in _TYPES:
        return key.replace(" ", "_")
    return _TYPE_ALIASES.get(key, "")


def normalize_team(value: str) -> str:
    key = str(value or "").strip().lower()
    for alias, team in TEAMS.items():
        if alias in key:
            return team
    return ""


class CvsDemoDatabase:
    """SQLite-backed mock of Workday and ServiceNow for the CVS Phase 2 demo."""

    def __init__(self, db_path: str = "cvs_demo.db"):
        self.db_path = db_path

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        """Create the tables and seed them once; an existing seed is never rewritten."""
        with self._conn() as conn:
            conn.executescript(_SCHEMA)
            columns = {r["name"] for r in conn.execute("PRAGMA table_info(call_context)")}
            if "summary_verified" not in columns:  # files created before 2026-10-26
                conn.execute("ALTER TABLE call_context ADD COLUMN summary_verified INTEGER DEFAULT 0")
            if "token" not in columns:
                conn.execute("ALTER TABLE call_context ADD COLUMN token TEXT")
            if conn.execute("SELECT 1 FROM colleagues").fetchone() is None:
                self._seed(conn)

    def reset(self, sms_enabled: Optional[bool] = None) -> dict:
        """Wipe every table and re-seed; the SMS switch keeps its value unless given."""
        keep = self.sms_enabled() if sms_enabled is None else bool(sms_enabled)
        with self._conn() as conn:
            for table in _DATA_TABLES:
                conn.execute(f"DELETE FROM {table}")
            conn.execute("DELETE FROM sqlite_sequence")
            self._seed(conn)
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('sms_enabled', ?)", ("true" if keep else "false",))
        return self.status()

    def _seed(self, conn: sqlite3.Connection) -> None:
        conn.execute("INSERT INTO colleagues VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     tuple(JEFF[k] for k in ("emplid", "first_name", "display_name", "dob", "mobile",
                                             "job_title", "store", "manager", "second_level_leader")))
        for kind, hours in BALANCES.items():
            conn.execute("INSERT INTO balances VALUES (?, ?, ?)", (JEFF["emplid"], kind, hours))
        opened = as_of_date() - timedelta(days=2)
        conn.execute("INSERT INTO cases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (BENEFITS_CASE, JEFF["emplid"], "Benefits", "benefits_question",
                      "Dental enrollment question", 0, "work_in_progress", opened.isoformat(), "[]"))
        for key, value in (("case_seq", FIRST_CASE_SEQ), ("time_off_seq", FIRST_TIME_OFF_SEQ),
                           ("seeded_on", as_of_date().isoformat())):
            conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, str(value)))
        if conn.execute("SELECT 1 FROM meta WHERE key='sms_enabled'").fetchone() is None:
            conn.execute("INSERT INTO meta VALUES ('sms_enabled', 'false')")

    def _meta(self, conn: sqlite3.Connection, key: str) -> Optional[str]:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def _next(self, conn: sqlite3.Connection, key: str) -> int:
        value = int(self._meta(conn, key))
        conn.execute("UPDATE meta SET value=? WHERE key=?", (str(value + 1), key))
        return value

    def sms_enabled(self) -> bool:
        with self._conn() as conn:
            return self._meta(conn, "sms_enabled") == "true"

    def status(self) -> dict:
        with self._conn() as conn:
            counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in ("cases", "time_off", "pay_resolutions", "verifications", "call_context")}
            case = conn.execute("SELECT opened_on FROM cases WHERE case_id=?", (BENEFITS_CASE,)).fetchone()
            seeded_on = self._meta(conn, "seeded_on")
            sms = self._meta(conn, "sms_enabled") == "true"
        opened = date.fromisoformat(case["opened_on"]) if case else None
        return {"seeded_on": seeded_on, "as_of": as_of_date().isoformat(), "sms_enabled": sms,
                "sms_to_set": bool(os.environ.get(SMS_TO_ENV, "").strip()),
                "benefits_case": BENEFITS_CASE,
                "benefits_case_opened": opened.isoformat() if opened else None,
                "benefits_case_weekday": rules.date_display_en(opened).split(",")[0] if opened else None,
                "counts": counts}

    def audited(self, tool: str, args: dict, fn: Callable[[], dict]) -> dict:
        """Run one tool body and write one ``audit_events`` row; OTP codes are never logged."""
        result = fn()
        logged_args = {k: ("***" if k == "code" else v) for k, v in args.items()}
        with self._conn() as conn:
            conn.execute("INSERT INTO audit_events (tool, args, result, at, status) VALUES (?, ?, ?, ?, ?)",
                         (tool, json.dumps(logged_args, default=str), json.dumps(result, default=str),
                          _iso(_utcnow()), "error" if "error" in result else "ok"))
        return result

    def list_audit_events(self, limit: int = 200) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT ?",
                                (max(1, min(int(limit), 2000)),)).fetchall()
        return [{"tool": r["tool"], "args": json.loads(r["args"]), "result": json.loads(r["result"]),
                 "at": r["at"], "status": r["status"]} for r in rows]

    # ---------------------------------------------------------------- identity

    def _colleague(self, conn: sqlite3.Connection, emplid: str) -> Optional[sqlite3.Row]:
        return conn.execute("SELECT * FROM colleagues WHERE emplid=?", (emplid,)).fetchone()

    def _colleague_by_ani(self, conn: sqlite3.Connection, ani: str) -> Optional[sqlite3.Row]:
        """The colleague whose mobile on file is this number, or Jeff when it's a configured alias."""
        number = normalize_e164(ani)
        if not number:
            return None
        row = conn.execute("SELECT * FROM colleagues WHERE mobile=?", (number,)).fetchone()
        if row is not None:
            return row
        aliases = {normalize_e164(a) for a in os.environ.get(ANI_ALIASES_ENV, "").split(",") if a.strip()}
        return self._colleague(conn, JEFF["emplid"]) if number in aliases else None

    def _identity(self, row: sqlite3.Row, method: str) -> dict:
        return {"verified": True, "emplid": row["emplid"], "emplid_last4": row["emplid"][-4:],
                "emplid_display": f"ending {row['emplid'][-4:]}", "first_name": row["first_name"],
                "colleague_name": row["display_name"], "auth_method": method,
                "mobile_last4": _last4(row["mobile"])}

    def _mark_verified(self, conn: sqlite3.Connection, emplid: str, method: str) -> None:
        conn.execute("INSERT OR REPLACE INTO verifications VALUES (?, ?, ?)", (emplid, method, _iso(_utcnow())))

    def is_verified(self, emplid: str) -> bool:
        with self._conn() as conn:
            row = conn.execute("SELECT verified_at FROM verifications WHERE emplid=?",
                               (rules.digits_only(emplid),)).fetchone()
        if row is None:
            return False
        age = _utcnow() - datetime.fromisoformat(row["verified_at"])
        return age <= timedelta(minutes=VERIFICATION_TTL_MINUTES)

    def _require(self, emplid: str) -> tuple[str, Optional[dict]]:
        digits = rules.digits_only(emplid)
        if not self.is_verified(digits):
            return digits, _err("not_verified", "I need to verify you before I can look at that.")
        return digits, None

    def verify_emplid_dob(self, emplid: str, dob: str, attempt: int = 1, entry: str = "voice") -> dict:
        """
        Check the EMPLID and date of birth. A partial EMPLID (fewer than 7
        digits) isn't a failed attempt. After a failed attempt the one-time
        code is offered when the EMPLID belongs to a colleague.
        """
        digits = rules.digits_only(emplid)
        if len(digits) < 7:
            return {"verified": False, "outcome": "partial", "heard_digits": len(digits),
                    "display": "I didn't get all seven digits of your employee ID."}
        born = parse_dob(dob)
        method = "EMPLID and date of birth (keypad)" if entry == "keypad" else "EMPLID and date of birth"
        with self._conn() as conn:
            row = self._colleague(conn, digits)
            if row is not None and born is not None and row["dob"] == born.isoformat():
                self._mark_verified(conn, digits, method)
                return {**self._identity(row, method), "outcome": "verified"}
        attempt = max(1, int(attempt or 1))
        result = {"verified": False, "outcome": "no_match", "attempts": attempt,
                  "otp_available": row is not None, "escalate": row is None and attempt >= 2,
                  "display": "That didn't match our records."}
        if row is not None:
            result["mobile_last4"] = _last4(row["mobile"])
        if born is None:
            result["outcome"] = "bad_date"
            result["display"] = "I didn't catch a full date of birth."
        return result

    def _resolve_caller(self, conn: sqlite3.Connection, emplid: str, ani: str) -> Optional[sqlite3.Row]:
        digits = rules.digits_only(emplid)
        if digits:
            return self._colleague(conn, digits)
        ctx = self._recent_context(conn, ani=normalize_e164(ani))
        if ctx is not None and ctx["emplid"]:
            return self._colleague(conn, ctx["emplid"])
        return self._colleague_by_ani(conn, ani)

    def _sms_target(self) -> str:
        return normalize_e164(os.environ.get(SMS_TO_ENV, "")) if self.sms_enabled() else ""

    def send_otp(self, emplid: str = "", ani: str = "", sender: Optional[Callable[[str, str], dict]] = None) -> dict:
        """
        Send a six-digit code to the mobile on file (the demo handset). With
        SMS off the rehearsal code is used and nothing is sent.
        """
        with self._conn() as conn:
            row = self._resolve_caller(conn, emplid, ani)
            if row is None:
                return _err("unknown_caller", "I couldn't find a mobile number to send a code to.")
            target = self._sms_target()
            code = (f"{secrets.randbelow(10 ** 6):06d}" if target
                    else os.environ.get(REHEARSAL_OTP_ENV, DEFAULT_REHEARSAL_OTP))
            expires = _utcnow() + timedelta(seconds=OTP_TTL_SECONDS)
            conn.execute("INSERT OR REPLACE INTO otps VALUES (?, ?, ?, 0)",
                         (row["emplid"], _hash(code), _iso(expires)))
        result = {"sent": True, "mobile_last4": _last4(row["mobile"]), "expires_in_seconds": OTP_TTL_SECONDS,
                  "emplid_last4": row["emplid"][-4:], "delivery": "sms" if target else "rehearsal"}
        if target:
            if sender is None:
                return _err("sms_unavailable", "I'm not able to send a text right now.")
            sent = sender(target, f"Your CVS Health verification code is {code}. It expires in 5 minutes.")
            if "error" in sent:
                return _err("sms_failed", "I couldn't send the code just now.", detail=sent["error"])
        return result

    def verify_otp(self, code: str, emplid: str = "", ani: str = "") -> dict:
        """Check the code: 5-minute expiry, 3 tries; a match verifies the colleague."""
        with self._conn() as conn:
            row = self._resolve_caller(conn, emplid, ani)
            otp = conn.execute("SELECT * FROM otps WHERE emplid=?", (row["emplid"],)).fetchone() if row else None
            if otp is None:
                return _err("no_code", "I haven't sent you a code yet.")
            if _utcnow() > datetime.fromisoformat(otp["expires_at"]):
                return _err("expired", "That code has expired. I can send a new one.", can_resend=True)
            if otp["tries"] >= OTP_MAX_TRIES:
                return _err("locked", "That's too many tries for this code.", escalate=True)
            if _hash(rules.digits_only(code)) != otp["code_hash"]:
                tries = otp["tries"] + 1
                conn.execute("UPDATE otps SET tries=? WHERE emplid=?", (tries, row["emplid"]))
                left = OTP_MAX_TRIES - tries
                return {"verified": False, "outcome": "no_match", "tries_left": left, "escalate": left == 0,
                        "display": "That code didn't match."}
            conn.execute("DELETE FROM otps WHERE emplid=?", (row["emplid"],))
            method = "SMS one-time code"
            self._mark_verified(conn, row["emplid"], method)
            return {**self._identity(row, method), "outcome": "verified"}

    # -------------------------------------------------------------- pay / time

    def get_timecard(self, emplid: str, period_end: str = "") -> dict:
        digits, refused = self._require(emplid)
        if refused:
            return refused
        if period_end and parse_dob(period_end) != PERIOD["end"]:
            return _err("no_timecard", "I only have the timecard for the period ending October 3rd.",
                        available_period_end=PERIOD["end"].isoformat())
        with self._conn() as conn:
            row = self._colleague(conn, digits)
            resolved = conn.execute("SELECT * FROM pay_resolutions WHERE emplid=?", (digits,)).fetchone()
        status = "approved_after_cutoff" if resolved else "not_approved"
        return {
            "emplid_last4": digits[-4:], "period_start": PERIOD["start"].isoformat(),
            "period_end": PERIOD["end"].isoformat(),
            "period_end_display": rules.date_display_en(PERIOD["end"]),
            "hours_recorded": UNAPPROVED_HOURS, "approved_hours": UNAPPROVED_HOURS if resolved else 0.0,
            "unapproved_hours": 0.0 if resolved else UNAPPROVED_HOURS, "approval_status": status,
            "approver": row["manager"], "second_level_leader": row["second_level_leader"],
            "team_approval": "Every other timecard on the team was approved for this period.",
            "leave_start": LEAVE[0].isoformat(), "leave_end": LEAVE[1].isoformat(),
            "leave_display": f"{rules.date_display_en(LEAVE[0])} to {rules.date_display_en(LEAVE[1])}",
            "display": (f"{rules.hours_display_en(UNAPPROVED_HOURS)} for the period ending "
                        f"{rules.date_display_en(PERIOD['end'])} "
                        + ("have since been approved." if resolved
                           else f"were not approved by {row['manager']} before payroll closed.")),
        }

    def get_pay_results(self, emplid: str) -> dict:
        digits, refused = self._require(emplid)
        if refused:
            return refused
        off_cycle = rules.add_business_days(as_of_date(), 3)
        with self._conn() as conn:
            resolved = conn.execute("SELECT * FROM pay_resolutions WHERE emplid=?", (digits,)).fetchone()
        return {
            "emplid_last4": digits[-4:],
            "checks": [{"pay_date": SHORT_CHECK.isoformat(), "type": "regular", "short": True,
                        "short_hours": UNAPPROVED_HOURS, "period_end": PERIOD["end"].isoformat(),
                        "reason": "timecard hours not approved before payroll closed"}],
            "short_check_display": rules.date_display_en(SHORT_CHECK),
            "next_regular_check": NEXT_CHECK.isoformat(),
            "next_regular_check_display": rules.date_display_en(NEXT_CHECK),
            "off_cycle_available": resolved is None, "off_cycle_pay_date": off_cycle.isoformat(),
            "off_cycle_pay_date_display": rules.date_display_en(off_cycle),
            "resolution": dict(resolved) if resolved else None,
            "display": (f"Your {rules.date_display_en(SHORT_CHECK)} check was short "
                        f"{rules.hours_display_en(UNAPPROVED_HOURS)} because those hours weren't approved "
                        f"before payroll closed."),
        }

    def resolve_short_pay(self, emplid: str, option: str) -> dict:
        """
        Pay the 22 hours: ``next_check`` (on 2026-10-23) or ``off_cycle``
        (three business days out). Idempotent: a second call returns the
        first resolution.
        """
        digits, refused = self._require(emplid)
        if refused:
            return refused
        option = str(option or "").strip().lower().replace("-", "_").replace(" ", "_")
        if option not in ("next_check", "off_cycle"):
            return _err("bad_option", "Should I put the hours on your next check or request an off-cycle payment?",
                        options=["next_check", "off_cycle"])
        with self._conn() as conn:
            existing = conn.execute("SELECT * FROM pay_resolutions WHERE emplid=?", (digits,)).fetchone()
            if existing is None:
                pay_date = NEXT_CHECK if option == "next_check" else rules.add_business_days(as_of_date(), 3)
                reference = f"PAY{self._next(conn, 'time_off_seq')}"
                conn.execute("INSERT INTO pay_resolutions VALUES (?, ?, ?, ?, ?, ?)",
                             (reference, digits, option, pay_date.isoformat(), UNAPPROVED_HOURS, _iso(_utcnow())))
                existing = conn.execute("SELECT * FROM pay_resolutions WHERE emplid=?", (digits,)).fetchone()
        pay_date = date.fromisoformat(existing["pay_date"])
        how = "on your next regular check" if existing["option"] == "next_check" else "as an off-cycle payment"
        return {"resolved": True, "pay_outcome": existing["option"], "reference": existing["reference"],
                "reference_spoken": spoken_digits(existing["reference"]), "pay_date": pay_date.isoformat(),
                "pay_date_display": rules.date_display_en(pay_date), "hours": existing["hours"],
                "display": (f"The {rules.hours_display_en(existing['hours'])} are approved and will be paid "
                            f"{how} on {rules.date_display_en(pay_date)}.")}

    # ----------------------------------------------------------------- absence

    def get_absence_balances(self, emplid: str) -> dict:
        digits, refused = self._require(emplid)
        if refused:
            return refused
        with self._conn() as conn:
            rows = {r["type"]: r["hours"] for r in
                    conn.execute("SELECT type, hours FROM balances WHERE emplid=?", (digits,))}
        today = as_of_date()
        next_monday = today + timedelta(days=(7 - today.weekday()) or 7)
        balances = []
        for kind in ("pto", "sick", "floating_holiday"):
            hours = rows.get(kind, 0.0)
            balances.append({"type": kind, "name": _TYPES[kind]["name"], "hours": hours,
                             "days": hours / HOURS_PER_DAY,
                             "display": f"{_TYPES[kind]['name']}: {rules.hours_display_en(hours)}, "
                                        f"which is {days_text(hours / HOURS_PER_DAY)}"})
        return {"emplid_last4": digits[-4:], "balances": balances, "accrual_hours_per_period": ACCRUAL_PER_PERIOD,
                "hours_per_day": HOURS_PER_DAY, "as_of": today.isoformat(), "next_monday": next_monday.isoformat(),
                "display": "; ".join(b["display"] for b in balances) + "."}

    def list_absence_types(self) -> dict:
        return {"types": ABSENCE_TYPES, "hours_per_day": HOURS_PER_DAY}

    def submit_time_off(self, emplid: str, absence_type: str, start_date: str, days: float = 0,
                        hours: float = 0, reason: str = "", validate_only: Any = False) -> dict:
        """
        Submit time off after the deterministic checks: the type must fit
        (a leave of absence isn't filed here), and ``requested_hours <=
        available_hours`` for a balance type. Errors carry ``WRONG_TYPE`` or
        ``INSUFFICIENT_BALANCE`` plus the numbers to explain the gap.
        ``validate_only`` runs every check and returns ``valid`` without submitting.
        """
        digits, refused = self._require(emplid)
        if refused:
            return refused
        kind = normalize_type(absence_type)
        if not kind:
            return _err("UNKNOWN_TYPE", "I'm not sure which kind of time off that is.",
                        types=[t["type"] for t in ABSENCE_TYPES])
        if kind == "leave_of_absence":
            return _err("WRONG_TYPE", ("A leave of absence is for a serious health condition, caring for family, "
                                       "or parental or military leave. For a few days for something personal, "
                                       "like a move, you can use PTO or your floating holiday."),
                        suggested_types=["pto", "floating_holiday"], rule=_TYPES[kind]["rule"])
        start = parse_dob(start_date)
        if start is None:
            return _err("BAD_DATE", "What day would you like the time off to start?")
        requested = float(hours or 0) or float(days or 0) * HOURS_PER_DAY
        if requested <= 0:
            return _err("BAD_AMOUNT", "How many days would you like?")
        req_days = requested / HOURS_PER_DAY
        if kind == "floating_holiday" and requested != HOURS_PER_DAY:
            return _err("WRONG_AMOUNT", "A floating holiday is taken as one whole day.", requested_days=req_days)
        if kind == "bereavement" and req_days > MAX_BEREAVEMENT_DAYS:
            return _err("WRONG_AMOUNT", "Bereavement covers up to three days.", requested_days=req_days)
        with self._conn() as conn:
            if _TYPES[kind]["uses_balance"]:
                available = conn.execute("SELECT hours FROM balances WHERE emplid=? AND type=?",
                                         (digits, kind)).fetchone()["hours"]
                if requested > available:  # the deterministic check the brief requires
                    avail_days = available / HOURS_PER_DAY
                    over = req_days - avail_days
                    return _err("INSUFFICIENT_BALANCE",
                                (f"You have {days_text(avail_days)} of {_TYPES[kind]['name']}. "
                                 f"{days_text(req_days).split(' ')[0].capitalize()} would put you "
                                 f"{days_text(over)} over."),
                                type=kind, requested_hours=requested, available_hours=available,
                                requested_days=req_days, available_days=avail_days, over_by_days=over)
                remaining = available - requested
            else:
                remaining = None
            dates = workdays_from(start, max(1, int(-(-req_days // 1))))
            if coerce_bool(validate_only):
                result = {"valid": True, "type": kind, "type_name": _TYPES[kind]["name"], "hours": requested,
                          "days": req_days, "start_date": dates[0].isoformat(), "end_date": dates[-1].isoformat(),
                          "dates_display": rules.days_display_en(dates),
                          "display": (f"{days_text(req_days).capitalize()} of {_TYPES[kind]['name']}, "
                                      f"{rules.days_display_en(dates)}.")}
                if remaining is not None:
                    result["remaining_days_after"] = remaining / HOURS_PER_DAY
                return result
            if remaining is not None:
                conn.execute("UPDATE balances SET hours=hours-? WHERE emplid=? AND type=?", (requested, digits, kind))
            confirmation = str(self._next(conn, "time_off_seq"))
            conn.execute("INSERT INTO time_off VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (confirmation, digits, kind, dates[0].isoformat(), dates[-1].isoformat(), requested,
                          _iso(_utcnow())))
        result = {"submitted": True, "confirmation": confirmation, "confirmation_spoken": spoken_digits(confirmation),
                  "type": kind, "type_name": _TYPES[kind]["name"], "hours": requested, "days": req_days,
                  "start_date": dates[0].isoformat(), "end_date": dates[-1].isoformat(),
                  "dates_display": rules.days_display_en(dates),
                  "display": (f"{days_text(req_days).capitalize()} of {_TYPES[kind]['name']}, "
                              f"{rules.days_display_en(dates)}. Confirmation number "
                              f"{spoken_digits(confirmation)}.")}
        if remaining is not None:
            result["remaining_hours"] = remaining
            result["remaining_days"] = remaining / HOURS_PER_DAY
        return result

    # ------------------------------------------------------------------- cases

    def _case_dict(self, r: sqlite3.Row) -> dict:
        opened = date.fromisoformat(r["opened_on"])
        restricted = bool(r["restricted"])
        return {"case_id": r["case_id"], "case_id_spoken": f"H R C {spoken_digits(r['case_id'])}",
                "case_last4": r["case_id"][-4:], "team": r["team"], "case_type": r["case_type"],
                "summary": "Confidential Colleague Relations case" if restricted else r["summary"],
                "restricted": restricted, "state": r["state"], "opened_on": r["opened_on"],
                "opened_weekday": rules.date_display_en(opened).split(",")[0],
                "opened_display": rules.date_display_en(opened)}

    def get_open_cases(self, emplid: str) -> dict:
        digits, refused = self._require(emplid)
        if refused:
            return refused
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM cases WHERE emplid=? AND state NOT IN ('resolved', 'closed') "
                                "ORDER BY case_id", (digits,)).fetchall()
        cases = [self._case_dict(r) for r in rows]
        result = {"emplid_last4": digits[-4:], "count": len(cases), "cases": cases,
                  "case_ids": [c["case_id"] for c in cases]}
        # The oldest open case, flattened so a FLOW can read it without array indexing.
        if cases:
            first = cases[0]
            result.update({"primary_case_id": first["case_id"], "primary_case_weekday": first["opened_weekday"],
                           "primary_case_team": first["team"],
                           "primary_case_topic": first["summary"][:1].lower() + first["summary"][1:]})
        return result

    def create_case(self, emplid: str, team: str, summary: str, restricted: Any = False,
                    case_type: str = "") -> dict:
        """Open a ServiceNow HR case; Colleague Relations cases are always restricted."""
        digits, refused = self._require(emplid)
        if refused:
            return refused
        team_name = normalize_team(team)
        if not team_name:
            return _err("bad_team", "Which team should handle this?", teams=sorted(set(TEAMS.values())))
        if not str(summary or "").strip():
            return _err("missing_summary", "I need a short description for the case.")
        restricted = coerce_bool(restricted) or team_name in RESTRICTED_TEAMS
        with self._conn() as conn:
            case_id = f"HRC{self._next(conn, 'case_seq'):07d}"
            conn.execute("INSERT INTO cases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (case_id, digits, team_name, case_type or team_name.lower().replace(" ", "_"),
                          rules.mask_digit_runs(str(summary).strip(), keep=4), int(restricted), "new",
                          as_of_date().isoformat(), "[]"))
            row = conn.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        return {"created": True, **self._case_dict(row)}

    def update_case(self, case_id: str, note: str = "", state: str = "") -> dict:
        number = str(case_id or "").strip().upper()
        if number.isdigit():
            number = f"HRC{int(number):07d}"
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM cases WHERE case_id=?", (number,)).fetchone()
            if row is None:
                return _err("no_case", "I couldn't find that case number.")
            if not self.is_verified(row["emplid"]):
                return _err("not_verified", "I need to verify you before I can update that case.")
            state = str(state or "").strip().lower()
            if state and state not in CASE_STATES:
                return _err("bad_state", "That isn't a case state I can set.", states=sorted(CASE_STATES))
            notes = json.loads(row["notes"])
            if note:
                notes.append({"at": _iso(_utcnow()), "note": rules.mask_digit_runs(note, keep=4)})
            conn.execute("UPDATE cases SET notes=?, state=? WHERE case_id=?",
                         (json.dumps(notes), state or row["state"], number))
            row = conn.execute("SELECT * FROM cases WHERE case_id=?", (number,)).fetchone()
        return {"updated": True, "notes": len(notes), **self._case_dict(row)}

    def send_sms(self, emplid: str, message: str, sender: Optional[Callable[[str, str], dict]] = None) -> dict:
        """Text the colleague's mobile on file (the demo handset when SMS is on)."""
        digits, refused = self._require(emplid)
        if refused:
            return refused
        body = rules.mask_digit_runs(str(message or "").strip(), keep=4)[:320]
        if not body:
            return _err("empty_message", "There's nothing to send.")
        with self._conn() as conn:
            mobile = self._colleague(conn, digits)["mobile"]
        target = self._sms_target()
        if not target:
            return {"sent": False, "suppressed": True, "mobile_last4": _last4(mobile), "body": body}
        if sender is None:
            return _err("sms_unavailable", "I'm not able to send a text right now.")
        sent = sender(target, body)
        if "error" in sent:
            return _err("sms_failed", "I couldn't send the text just now.", detail=sent["error"])
        return {"sent": True, "suppressed": False, "mobile_last4": _last4(mobile), "body": body}

    # ------------------------------------------------------------ call context

    def _recent_context(self, conn: sqlite3.Connection, emplid: str = "", ani: str = "",
                        exclude_token: str = "") -> Optional[sqlite3.Row]:
        """
        Most recent checkpoint in the recall window matching the EMPLID or the
        ANI, skipping this call's own (``exclude_token``). With an EMPLID, an
        ANI match counts only when that checkpoint isn't tied to another colleague.
        """
        since = _iso(_utcnow() - timedelta(minutes=RECALL_WINDOW_MINUTES))
        keys, params = [], []
        if emplid:
            keys.append("emplid=?")
            params.append(emplid)
        if ani:
            keys.append("(ani=? AND (emplid='' OR emplid=?))" if emplid else "ani=?")
            params.extend([ani, emplid] if emplid else [ani])
        if not keys:
            return None
        return conn.execute(f"SELECT * FROM call_context WHERE ({' OR '.join(keys)}) AND updated_at>=? "
                            "AND COALESCE(token, '')!=? ORDER BY updated_at DESC, id DESC LIMIT 1",
                            (*params, since, exclude_token or "-")).fetchone()

    def save_call_context(self, emplid: str = "", ani: str = "", summary: str = "", intents: Any = None,
                          open_case_ids: Any = None, pay_case_id: str = "", cr_case_id: str = "",
                          absence_request: str = "", context_id: Any = "") -> dict:
        """
        Checkpoint the call so a dropped call can resume. The first save of a
        call creates a checkpoint and returns its ``context_id``; later saves
        pass it back and update that checkpoint (empty fields keep their saved
        value). Keyed on the caller's number (ANI) and, once verified, the
        EMPLID; an ANI that identifies a colleague links the EMPLID straight away.
        """
        digits = rules.digits_only(emplid)
        number = normalize_e164(ani)
        if not digits and not number and not str(context_id or "").strip():  # nothing to key on
            return _err("no_key", "Nothing to key the call on yet.")
        if digits and not self.is_verified(digits):
            return _err("not_verified", "Context is saved by EMPLID only after verification.")
        fields = {"summary": str(summary or "").strip(), "intents": json.dumps(coerce_list(intents)),
                  "open_case_ids": json.dumps(coerce_list(open_case_ids)), "pay_case_id": pay_case_id or "",
                  "cr_case_id": cr_case_id or "", "absence_request": str(absence_request or "").strip()}
        empty = {"intents": "[]", "open_case_ids": "[]"}
        token = str(context_id or "").strip()
        with self._conn() as conn:
            known = self._colleague_by_ani(conn, number) if number and not digits else None
            linked = digits or (known["emplid"] if known else "")
            row = conn.execute("SELECT * FROM call_context WHERE token=?", (token,)).fetchone() if token else None
            if row is not None and linked and row["emplid"] and row["emplid"] != linked:
                return _err("context_mismatch", "That checkpoint belongs to another caller.")
            now = _iso(_utcnow())
            if row is None:
                token = secrets.token_urlsafe(12)
                conn.execute("INSERT INTO call_context (emplid, ani, summary, intents, open_case_ids, pay_case_id, "
                             "cr_case_id, absence_request, updated_at, summary_verified, token) "
                             "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (linked, number, *fields.values(), now, int(bool(digits and fields["summary"])), token))
            else:
                merged = {k: (v if v and v != empty.get(k) else row[k]) for k, v in fields.items()}
                summary_verified = int(bool(digits and fields["summary"])) or (
                    row["summary_verified"] if not fields["summary"] else 0)
                conn.execute("UPDATE call_context SET emplid=?, ani=?, summary=?, intents=?, open_case_ids=?, "
                             "pay_case_id=?, cr_case_id=?, absence_request=?, updated_at=?, summary_verified=? "
                             "WHERE id=?",
                             (linked or row["emplid"], number or row["ani"], *merged.values(), now,
                              summary_verified, row["id"]))
        return {"saved": True, "context_id": token,
                "keyed_on": [k for k, v in (("emplid", linked), ("ani", number)) if v]}

    def get_call_context(self, ani: str = "", emplid: str = "", exclude_context_id: Any = "") -> dict:
        """
        Look for an earlier call from this caller in the last 30 minutes,
        skipping this call's own checkpoint (``exclude_context_id``). Before
        verification (ANI only) it returns just enough to greet and send the
        code: first name and mobile last 4. The summary, intents and cases come
        back only for a verified EMPLID (matched on the EMPLID or the ANI).
        """
        digits = rules.digits_only(emplid)
        number = normalize_e164(ani)
        with self._conn() as conn:
            if digits and not self.is_verified(digits):
                return _err("not_verified", "I need to verify you before I can look at that.")
            row = self._recent_context(conn, emplid=digits, ani=number,
                                       exclude_token=str(exclude_context_id or "").strip())
            colleague = None
            if row is not None:
                colleague = (self._colleague(conn, row["emplid"]) if row["emplid"]
                             else self._colleague_by_ani(conn, number))
        if row is None:
            return {"found": False}
        minutes = int((_utcnow() - datetime.fromisoformat(row["updated_at"])).total_seconds() // 60)
        result = {"found": True, "minutes_ago": minutes,
                  "verified_required": not digits,
                  "first_name": colleague["first_name"] if colleague else "",
                  "mobile_last4": _last4(colleague["mobile"]) if colleague else ""}
        if digits:
            result.update({"summary": row["summary"], "intents": json.loads(row["intents"]),
                           "open_case_ids": json.loads(row["open_case_ids"]), "pay_case_id": row["pay_case_id"],
                           "cr_case_id": row["cr_case_id"], "absence_request": row["absence_request"],
                           "has_summary": bool(row["summary"]),
                           "summary_verified": bool(row["summary_verified"]),
                           "emplid_last4": row["emplid"][-4:] if row["emplid"] else ""})
        return result


def default_db_path() -> str:
    """``CVS_DEMO_DB_PATH`` or ``cvs_demo.db`` in the current working directory."""
    return os.environ.get("CVS_DEMO_DB_PATH", os.path.join(os.getcwd(), "cvs_demo.db"))


def open_database(path: Optional[str] = None) -> CvsDemoDatabase:
    """Construct and initialise a :class:`CvsDemoDatabase`."""
    db = CvsDemoDatabase(path or default_db_path())
    db.init_db()
    return db
