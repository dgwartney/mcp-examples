"""
Shared mock data store for the four CVS Health HR systems of record.

One SQLite file (``CVS_HR_DB_PATH``) holds the schema and seed for:

    cvs_identity     identity_colleagues, verifications
    workday_hcm      workday_workers, workday_time_off   (read-only: no payroll writes)
    time_attendance  ta_timecard_days, ta_corrections
    servicenow_hrsd  sn_hr_cases

plus ``audit_events`` (one row per MCP tool call, tagged with its system),
``meta`` (counters, seeded period) and ``settings`` (the SMS switch).

Per-call sandbox (H3): ``verify_colleague`` creates a ``verification_id``.
Every mutable record (corrections, cases, revocation) is keyed by it, and
reads overlay that sandbox on the seed, so concurrent eval calls never see
each other's writes. Every tool except ``verify_colleague`` and the single
unverified ``create_hr_case(hr_service="Identity verification")`` refuses
with ``error="not_verified"`` unless the verification is active and covers
the worker asked about.

Dates are relative to the as-of date (see ``cvs_hr_rules.as_of_date``). When
the last closed period changes (a Saturday rolls over, or ``CVS_HR_AS_OF``
changes), the seed tables are rebuilt for the new period automatically;
sandboxes and audit rows are only cleared by :meth:`CvsHrDatabase.reset`.

Author:
    David Gwartney <david.gwartney@gmail.com>

Environment Variables:
    CVS_HR_DB_PATH:     SQLite file (default: cvs_hr.db in the cwd).
    CVS_HR_AS_OF:       Optional ISO date overriding "today".
    CVS_HR_DEMO_SMS_TO: Demo handset number returned as ``sms_to`` (never
                        hard-coded; empty when unset).
"""

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterator, Optional

from mcp_server_kit import cvs_hr_rules as rules

SMS_TO_ENV = "CVS_HR_DEMO_SMS_TO"
FIRST_CASE_SEQ = 917
MAX_VERIFY_ATTEMPTS = 2
SYSTEMS = ("cvs_identity", "workday_hcm", "time_attendance", "servicenow_hrsd", "cvs_hr_router")
CASE_STATES = {
    "new", "ready", "work_in_progress", "awaiting_info", "resolved",
    "closed_complete", "closed_incomplete", "cancelled",
}
_CLOSED_STATES = {"resolved", "closed_complete", "closed_incomplete", "cancelled"}
IDENTITY_VERIFICATION_SERVICE = "Identity verification"

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

# Day templates: (days after the period's Sunday, punch segments,
# auto-deducted meal minutes, break punched?)
_SPLIT_8H = (("07:00", "11:00"), ("11:30", "15:30"))
_CLEAN_WEEK = [(d, _SPLIT_8H, 0, True) for d in (1, 2, 3, 4, 5)]  # Mon-Fri, 40.0 h
_DANIEL_WEEK = [  # 43.0 h worked; 30-min meal auto-deducted Mon/Wed/Thu with no break punched
    (1, (("07:00", "16:00"),), 30, False),
    (2, _SPLIT_8H, 0, True),
    (3, (("07:00", "16:00"),), 30, False),
    (4, (("07:00", "16:00"),), 30, False),
    (5, _SPLIT_8H, 0, True),
]
_MARCUS_WEEK = [  # 52.5 h worked; 60-min meal auto-deducted on five 10.5 h shifts -> 5.0 h short
    (d, (("06:00", "16:30"),), 60, False) for d in (1, 2, 3, 4, 5)
]

_COLLEAGUES = [
    {"id": "7742318", "first": "Daniel", "last": "Reyes", "display": "Daniel R.",
     "mobile": "6025550148", "title": "Pharmacy Technician", "store": "6218",
     "city": "Phoenix", "state": "AZ", "rate": "18.50", "lang": "en",
     "hire": "2019-05-13", "pto": 62.5, "accrual": 6.15, "week": _DANIEL_WEEK},
    {"id": "5530912", "first": "Ana", "last": "Ortiz", "display": "Ana O.",
     "mobile": "6025550172", "title": "Retail Associate", "store": "2290",
     "city": "Mesa", "state": "AZ", "rate": "16.00", "lang": "es",
     "hire": "2021-08-02", "pto": 40.0, "accrual": 4.62, "week": _CLEAN_WEEK},
    {"id": "8104467", "first": "Marcus", "last": "Lee", "display": "Marcus L.",
     "mobile": "6025550126", "title": "Shift Supervisor", "store": "6218",
     "city": "Phoenix", "state": "AZ", "rate": "22.00", "lang": "en",
     "hire": "2017-02-20", "pto": 24.0, "accrual": 6.15, "week": _MARCUS_WEEK},
    {"id": "3329018", "first": "Kevin", "last": "Park", "display": "Kevin P.",
     "mobile": "6025550193", "title": "Shift Supervisor", "store": "5107",
     "city": "Scottsdale", "state": "AZ", "rate": "17.00", "lang": "en",
     "hire": "2022-11-07", "pto": 30.0, "accrual": 4.62, "week": _CLEAN_WEEK},
    {"id": "9017734", "first": "Jordan", "last": "Hayes", "display": "Jordan H.",
     "mobile": "6025550111", "title": "Pharmacy Technician", "store": "3384",
     "city": "Tempe", "state": "AZ", "rate": "19.00", "lang": "en",
     "hire": "2020-06-15", "pto": 51.0, "accrual": 6.15, "week": _CLEAN_WEEK},
    {"id": "6610425", "first": "Priya", "last": "Shah", "display": "Priya S.",
     "mobile": "6025550164", "title": "Beauty Consultant", "store": "2290",
     "city": "Mesa", "state": "AZ", "rate": "16.50", "lang": "en",
     "hire": "2018-09-24", "pto": 88.5, "accrual": 6.15, "week": _CLEAN_WEEK},
    {"id": "7742381", "first": "Elena", "last": "Ruiz", "display": "Elena R.",
     "mobile": "5205550187", "title": "Lead Pharmacy Technician", "store": "4471",
     "city": "Tucson", "state": "AZ", "rate": "20.00", "lang": "en",
     "hire": "2016-04-11", "pto": 70.0, "accrual": 6.15, "week": _CLEAN_WEEK},
]

# Historical ServiceNow cases (not tied to any sandbox; visible to the subject).
_SEED_CASES = [
    {"number": "HR-2026-0788", "subject": "7742318", "service": "General inquiry",
     "short": "W-2 mailing address updated in myHR", "state": "closed_complete",
     "opened_days_ago": 41},
    {"number": "HR-2026-0902", "subject": "5530912", "service": "Benefits inquiry",
     "short": "Question about dependent enrollment", "state": "work_in_progress",
     "opened_days_ago": 6},
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS identity_colleagues (
    colleague_id TEXT PRIMARY KEY, mobile TEXT, first_name TEXT,
    display_name TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS verifications (
    verification_id TEXT PRIMARY KEY, colleague_id TEXT, method TEXT,
    status TEXT, created_at TEXT, revoked_at TEXT);
CREATE TABLE IF NOT EXISTS workday_workers (
    worker_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT, display_name TEXT,
    job_title TEXT, store TEXT, city TEXT, state TEXT, base_rate_usd TEXT,
    employment_type TEXT, scheduled_weekly_hours REAL, hire_date TEXT,
    preferred_language TEXT);
CREATE TABLE IF NOT EXISTS workday_time_off (
    worker_id TEXT PRIMARY KEY, plan TEXT, balance_hours REAL,
    accrual_per_period_hours REAL);
CREATE TABLE IF NOT EXISTS ta_timecard_days (
    worker_id TEXT, period_end TEXT, work_date TEXT, segments TEXT,
    auto_deduct_type TEXT, auto_deduct_minutes INTEGER, break_punched INTEGER,
    PRIMARY KEY (worker_id, work_date));
CREATE TABLE IF NOT EXISTS ta_corrections (
    correction_id TEXT PRIMARY KEY, verification_id TEXT, worker_id TEXT,
    period_end TEXT, dates TEXT, remove_auto_deduct TEXT, audit_note TEXT,
    hours REAL, amount_usd REAL, status TEXT, created_at TEXT, reversed_at TEXT);
CREATE TABLE IF NOT EXISTS sn_hr_cases (
    sys_id TEXT PRIMARY KEY, number TEXT UNIQUE, verification_id TEXT,
    seeded INTEGER DEFAULT 0, subject_person TEXT, hr_service TEXT,
    contact_type TEXT, short_description TEXT, description TEXT,
    related_records TEXT, state TEXT, resolved_by TEXT, assignment_group TEXT,
    opened_at TEXT, resolved_at TEXT, work_notes TEXT);
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, system TEXT, tool TEXT, args TEXT,
    result TEXT, at TEXT, verification_id TEXT, status TEXT DEFAULT 'ok');
"""

_SEED_TABLES = ("identity_colleagues", "workday_workers", "workday_time_off", "ta_timecard_days")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _err(code: str, message: str, **extra) -> dict:
    return {"error": code, "message": message, **extra}


def coerce_list(value: Any) -> list[str]:
    """
    Accept a list, a JSON-encoded list, or a comma-separated string (some MCP
    callers, Artemis included, template list arguments as strings).
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
        except ValueError:
            pass
    return [p.strip().strip("\"'") for p in text.strip("[]").split(",") if p.strip().strip("\"'")]


def coerce_bool(value: Any) -> bool:
    """Accept a bool or a string like ``"true"``/``"yes"``; anything else is False."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


def normalize_e164(raw: str) -> str:
    """``'602-555-0148'`` -> ``'+16025550148'``; keeps an existing ``+`` prefix."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw.startswith("+"):
        return "+" + rules.digits_only(raw)
    d = rules.digits_only(raw)
    if len(d) == 10:
        return "+1" + d
    if len(d) == 11 and d.startswith("1"):
        return "+" + d
    return d


class CvsHrDatabase:
    """
    SQLite-backed mock of the CVS HR systems, with per-call sandboxes.

    Public methods return plain dicts shaped like the MCP tool results; a
    refusal is a dict with an ``error`` key (``not_verified``,
    ``consent_required``, ...) rather than an exception, so the agent can
    branch on it and the audit row records it.
    """

    def __init__(self, db_path: str = "cvs_hr.db"):
        self.db_path = db_path

    # ------------------------------------------------------------------ infra

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

    @staticmethod
    def calendar() -> rules.PayCalendar:
        """Pay calendar for the current as-of date."""
        return rules.pay_calendar(rules.as_of_date())

    def init_db(self) -> None:
        """Create tables; seed (or re-seed for a new period) as needed."""
        with self._conn() as conn:
            conn.executescript(_SCHEMA)
            if conn.execute("SELECT value FROM meta WHERE key='case_seq'").fetchone() is None:
                self._reset_counters(conn)
            if conn.execute("SELECT value FROM settings WHERE key='sms_enabled'").fetchone() is None:
                conn.execute("INSERT INTO settings VALUES ('sms_enabled', 'false')")
        self.ensure_current()

    def ensure_current(self) -> None:
        """Re-seed the seed tables if the last closed period has changed."""
        period_end = self.calendar().period_end.isoformat()
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key='seed_period_end'").fetchone()
            if row is None or row["value"] != period_end:
                self._seed(conn)

    def reset(self) -> dict:
        """
        Clear every sandbox, case, correction and audit row, restart the
        counters (next case HR-<year>-0917) and re-seed for the current
        as-of date. Settings (the SMS switch) are kept.
        """
        with self._conn() as conn:
            for table in ("verifications", "ta_corrections", "sn_hr_cases", "audit_events"):
                conn.execute(f"DELETE FROM {table}")
            conn.execute("DELETE FROM sqlite_sequence WHERE name='audit_events'")
            self._reset_counters(conn)
            self._seed(conn)
        cal = self.calendar()
        return {"status": "reset", "as_of": cal.as_of.isoformat(),
                "period_end": cal.period_end.isoformat(),
                "next_case_number": f"HR-{cal.as_of.year}-{FIRST_CASE_SEQ:04d}"}

    @staticmethod
    def _reset_counters(conn: sqlite3.Connection) -> None:
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('case_seq', ?)", (str(FIRST_CASE_SEQ - 1),))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('correction_seq', '0')")

    def _seed(self, conn: sqlite3.Connection) -> None:
        cal = self.calendar()
        for table in _SEED_TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sn_hr_cases WHERE seeded = 1")
        for c in _COLLEAGUES:
            conn.execute("INSERT INTO identity_colleagues VALUES (?, ?, ?, ?, 'active')",
                         (c["id"], c["mobile"], c["first"], c["display"]))
            conn.execute(
                "INSERT INTO workday_workers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'full_time', 40.0, ?, ?)",
                (c["id"], c["first"], c["last"], c["display"], c["title"], c["store"],
                 c["city"], c["state"], c["rate"], c["hire"], c["lang"]))
            conn.execute("INSERT INTO workday_time_off VALUES (?, 'PTO', ?, ?)",
                         (c["id"], c["pto"], c["accrual"]))
            for period_end, week in ((cal.period_end, c["week"]), (cal.prior_period_end, _CLEAN_WEEK)):
                sunday = period_end - timedelta(days=6)
                for offset, segments, deduct, punched in week:
                    conn.execute(
                        "INSERT INTO ta_timecard_days VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (c["id"], period_end.isoformat(),
                         (sunday + timedelta(days=offset)).isoformat(),
                         json.dumps([list(s) for s in segments]),
                         "meal" if deduct else None, deduct, int(punched)))
        for s in _SEED_CASES:
            opened = datetime.combine(cal.as_of - timedelta(days=s["opened_days_ago"]),
                                      datetime.min.time(), timezone.utc).isoformat(timespec="seconds")
            closed = s["state"] in _CLOSED_STATES
            conn.execute(
                "INSERT INTO sn_hr_cases VALUES (?, ?, NULL, 1, ?, ?, 'phone', ?, '', '[]', ?, ?, ?, ?, ?, '[]')",
                (uuid.uuid5(uuid.NAMESPACE_OID, s["number"]).hex, s["number"], s["subject"],
                 s["service"], s["short"], s["state"], "HR Shared Services" if closed else "",
                 "" if closed else "Colleague Service", opened, opened if closed else None))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('seed_period_end', ?)",
                     (cal.period_end.isoformat(),))

    # ---------------------------------------------------------------- settings

    def get_settings(self) -> dict:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='sms_enabled'").fetchone()
        return {"sms_enabled": bool(row) and row["value"] == "true"}

    def update_settings(self, sms_enabled: bool) -> dict:
        with self._conn() as conn:
            conn.execute("INSERT OR REPLACE INTO settings VALUES ('sms_enabled', ?)",
                         ("true" if sms_enabled else "false",))
        return self.get_settings()

    # ------------------------------------------------------------------- audit

    def audited(self, system: str, tool: str, args: dict, fn: Callable[[], dict]) -> dict:
        """Run one tool body and write exactly one ``audit_events`` row for it."""
        self.ensure_current()
        result = fn()
        vid = result.get("verification_id") or args.get("verification_id") or None
        logged = dict(result)
        if logged.get("sms_to"):
            logged["sms_to"] = rules.mask_digits(logged["sms_to"])
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO audit_events (system, tool, args, result, at, verification_id, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (system, tool, json.dumps(args, default=str), json.dumps(logged, default=str),
                 _now(), vid, "error" if "error" in result else "ok"))
        return result

    def list_audit_events(self, system: str = "", verification_id: str = "",
                          limit: int = 500) -> list[dict]:
        sql, params = "SELECT * FROM audit_events WHERE 1=1", []
        if system:
            sql += " AND system = ?"
            params.append(system)
        if verification_id:
            sql += " AND verification_id = ?"
            params.append(verification_id)
        sql += " ORDER BY id LIMIT ?"
        params.append(max(1, min(int(limit), 5000)))
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [{"id": r["id"], "system": r["system"], "tool": r["tool"],
                 "args": json.loads(r["args"]), "result": json.loads(r["result"]),
                 "at": r["at"], "verification_id": r["verification_id"], "status": r["status"]}
                for r in rows]

    # ---------------------------------------------------------------- identity

    def _sms_fields(self) -> dict:
        number = normalize_e164(os.environ.get(SMS_TO_ENV, ""))
        if not self.get_settings()["sms_enabled"]:
            return {"sms_to": "", "sms_suppressed": True, "sms_suppressed_reason": "disabled"}
        if not number:
            return {"sms_to": "", "sms_suppressed": True, "sms_suppressed_reason": "no_number"}
        return {"sms_to": number, "sms_suppressed": False, "sms_suppressed_reason": ""}

    def verify_colleague(self, colleague_id: str = "", mobile: str = "", attempt: int = 1) -> dict:
        """
        Verify a caller by 7-digit colleague ID or 10-digit mobile on file.
        Stateless across attempts (H5): the agent passes ``attempt``; a
        failure with ``attempt >= 2`` returns ``escalate=True``.
        """
        try:
            attempt = max(1, int(attempt))
        except (TypeError, ValueError):
            attempt = 1
        kind, digits = rules.classify_identifier(colleague_id, mobile)
        row = None
        if kind != "invalid":
            column = "colleague_id" if kind == "colleague_id" else "mobile"
            with self._conn() as conn:
                row = conn.execute(
                    f"SELECT * FROM identity_colleagues WHERE {column} = ? AND status = 'active'",
                    (digits,)).fetchone()
        if row is None:
            escalate = attempt >= MAX_VERIFY_ATTEMPTS
            reason = "invalid_format" if kind == "invalid" else "no_match"
            return {"verified": False, "verification_id": "", "attempts": attempt,
                    "max_attempts": MAX_VERIFY_ATTEMPTS, "escalate": escalate,
                    "reason": reason, "method": kind, "masked_input": rules.mask_digits(digits),
                    "message": ("Could not verify identity after "
                                f"{attempt} attempts" if escalate else
                                "No colleague record matches that number.")}
        vid = "ver_" + uuid.uuid4().hex[:16]
        with self._conn() as conn:
            conn.execute("INSERT INTO verifications VALUES (?, ?, ?, 'active', ?, NULL)",
                         (vid, row["colleague_id"], kind, _now()))
        return {"verified": True, "verification_id": vid, "colleague_id": row["colleague_id"],
                "display_name": row["display_name"], "first_name": row["first_name"],
                "method": kind, "attempts": attempt, "max_attempts": MAX_VERIFY_ATTEMPTS,
                "escalate": False, "masked_input": rules.mask_digits(digits),
                **self._sms_fields()}

    def revoke_verification(self, verification_id: str) -> dict:
        """End a verification (wrong person matched). Idempotent."""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM verifications WHERE verification_id = ?",
                               (verification_id or "",)).fetchone()
            if row is None:
                return _err("not_verified", "Unknown verification_id.", revoked=False)
            already = row["status"] == "revoked"
            if not already:
                conn.execute("UPDATE verifications SET status='revoked', revoked_at=? "
                             "WHERE verification_id = ?", (_now(), verification_id))
        return {"revoked": True, "already_revoked": already, "status": "revoked",
                "verification_id": verification_id, "verified": False}

    def check_verification(self, verification_id: str, worker_id: Optional[str] = None):
        """
        Return ``(row, None)`` for an active verification covering
        ``worker_id`` (if given), else ``(None, error_dict)``.
        """
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM verifications WHERE verification_id = ?",
                               (verification_id or "",)).fetchone()
        if row is None or row["status"] != "active":
            why = "revoked" if row is not None else "missing or unknown"
            return None, _err("not_verified",
                              f"Caller is not verified (verification {why}). Verify first.")
        if worker_id is not None and rules.digits_only(worker_id) != row["colleague_id"]:
            return None, _err("not_verified", "This verification does not cover that worker.")
        return row, None

    # ----------------------------------------------------------------- workday

    def _worker(self, worker_id: str) -> Optional[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute("SELECT * FROM workday_workers WHERE worker_id = ?",
                                (rules.digits_only(worker_id),)).fetchone()

    def get_worker(self, verification_id: str, worker_id: str) -> dict:
        v, err = self.check_verification(verification_id, worker_id)
        if err:
            return err
        w = self._worker(worker_id)
        base = rules.money(w["base_rate_usd"])
        return {"worker_id": w["worker_id"], "first_name": w["first_name"],
                "last_name": w["last_name"], "display_name": w["display_name"],
                "job_title": w["job_title"],
                "location": {"store": w["store"], "city": w["city"], "state": w["state"]},
                "base_rate_usd": float(base), "ot_rate_usd": float(rules.ot_rate(base)),
                "employment_type": w["employment_type"],
                "scheduled_weekly_hours": w["scheduled_weekly_hours"],
                "hire_date": w["hire_date"], "preferred_language": w["preferred_language"],
                "worker_status": "active", "verification_id": verification_id}

    def _time_off(self, worker_id: str) -> sqlite3.Row:
        with self._conn() as conn:
            return conn.execute("SELECT * FROM workday_time_off WHERE worker_id = ?",
                                (rules.digits_only(worker_id),)).fetchone()

    def get_time_off_balance(self, verification_id: str, worker_id: str) -> dict:
        v, err = self.check_verification(verification_id, worker_id)
        if err:
            return err
        t = self._time_off(worker_id)
        return {"worker_id": t["worker_id"], "plan": t["plan"],
                "balance_hours": t["balance_hours"],
                "balance_days": rules.hours_to_days(t["balance_hours"]),
                "accrual_per_period_hours": t["accrual_per_period_hours"],
                "as_of_period_end": self.calendar().period_end.isoformat(),
                "verification_id": verification_id}

    def project_time_off(self, verification_id: str, worker_id: str, target_hours) -> dict:
        v, err = self.check_verification(verification_id, worker_id)
        if err:
            return err
        try:
            target = float(target_hours)
        except (TypeError, ValueError):
            target = 0.0
        if target <= 0:
            return _err("invalid_target", "target_hours must be a positive number of hours.")
        t = self._time_off(worker_id)
        cal = self.calendar()
        p = rules.project_time_off(t["balance_hours"], t["accrual_per_period_hours"], target, cal)
        result = {"worker_id": t["worker_id"], "plan": t["plan"],
                  "balance_hours": p.balance_hours, "target_hours": p.target_hours,
                  "accrual_per_period_hours": p.accrual_per_period_hours,
                  "hours_needed": p.hours_needed, "periods_needed": p.periods_needed,
                  "already_enough": p.already_enough,
                  "projected_pay_dates": [cal.pay_date(n).isoformat()
                                          for n in range(1, p.periods_needed + 1)],
                  "verification_id": verification_id}
        if p.already_enough:
            result.update({"target_pay_date": "", "target_pay_date_display_en": "",
                           "target_pay_date_display_es": "", "target_label": "now",
                           "target_label_en": "now", "target_label_es": "ahora"})
        else:
            d = p.target_pay_date
            result.update({"target_pay_date": d.isoformat(),
                           "target_pay_date_display_en": rules.date_display_en(d),
                           "target_pay_date_display_es": rules.date_display_es(d),
                           "target_label": rules.target_label_en(d),
                           "target_label_en": rules.target_label_en(d),
                           "target_label_es": rules.target_label_es(d)})
        return result

    def evaluate_pay_correction(self, verification_id: str, worker_id: str, hours) -> dict:
        """Read-only payroll rule check: where a correction of ``hours`` lands. Never writes."""
        v, err = self.check_verification(verification_id, worker_id)
        if err:
            return err
        try:
            hours = float(hours)
        except (TypeError, ValueError):
            hours = 0.0
        if hours <= 0:
            return _err("invalid_hours", "hours must be a positive number.")
        cal = self.calendar()
        w = self._worker(worker_id)
        days = self._timecard_days(w["worker_id"], cal.period_end)
        week_hours = sum(d.hours_worked for d in days)
        price = rules.price_restored_hours(hours, week_hours, w["base_rate_usd"])
        decision = rules.evaluate_pay_correction(hours, cal)
        latest = self._corrections(verification_id, w["worker_id"], status="applied")
        return {"worker_id": w["worker_id"], "hours": hours, "period_end": cal.period_end.isoformat(),
                "amount_usd": float(price.amount_usd),
                "amount_display_en": rules.amount_display_en(price.amount_usd),
                "amount_display_es": rules.amount_display_es(price.amount_usd),
                "overtime": price.overtime, "pay_date": decision.pay_date.isoformat(),
                "pay_date_display_en": rules.date_display_en(decision.pay_date),
                "pay_date_display_es": rules.date_display_es(decision.pay_date),
                "off_cycle": decision.off_cycle,
                "off_cycle_threshold_hours": decision.off_cycle_threshold_hours,
                "rule_id": decision.rule_id, "read_only": True, "payroll_written": False,
                "correction_id": latest[-1]["correction_id"] if latest else "",
                "verification_id": verification_id}

    # ---------------------------------------------------------- time & attendance

    def _timecard_days(self, worker_id: str, period_end: date) -> list[rules.TimecardDay]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM ta_timecard_days WHERE worker_id = ? AND period_end = ? "
                "ORDER BY work_date", (worker_id, period_end.isoformat())).fetchall()
        return [rules.TimecardDay(date.fromisoformat(r["work_date"]),
                                  tuple(tuple(s) for s in json.loads(r["segments"])),
                                  r["auto_deduct_minutes"] or 0, bool(r["break_punched"]))
                for r in rows]

    def _corrections(self, verification_id: Optional[str], worker_id: str,
                     period_end: Optional[date] = None, status: Optional[str] = None) -> list[dict]:
        sql = "SELECT * FROM ta_corrections WHERE verification_id = ? AND worker_id = ?"
        params: list = [verification_id or "", worker_id]
        if period_end is not None:
            sql += " AND period_end = ?"
            params.append(period_end.isoformat())
        if status:
            sql += " AND status = ?"
            params.append(status)
        with self._conn() as conn:
            rows = conn.execute(sql + " ORDER BY created_at, correction_id", params).fetchall()
        return [self._correction_dict(r) for r in rows]

    @staticmethod
    def _correction_dict(r: sqlite3.Row) -> dict:
        return {"correction_id": r["correction_id"], "worker_id": r["worker_id"],
                "period_end": r["period_end"], "dates": json.loads(r["dates"]),
                "remove_auto_deduct": r["remove_auto_deduct"], "audit_note": r["audit_note"],
                "hours": r["hours"], "amount_usd": r["amount_usd"], "status": r["status"],
                "created_at": r["created_at"], "reversed_at": r["reversed_at"]}

    def _resolve_period(self, period_end: str) -> tuple[Optional[date], Optional[dict]]:
        cal = self.calendar()
        if not (period_end or "").strip():
            return cal.period_end, None
        try:
            d = date.fromisoformat(period_end.strip())
        except ValueError:
            return None, _err("invalid_period_end", "period_end must be an ISO date (YYYY-MM-DD).")
        if d.weekday() != rules.SATURDAY:
            return None, _err("invalid_period_end", "Pay periods end on a Saturday.")
        if d > cal.period_end:
            return None, _err("period_not_closed", "That pay period has not closed yet.",
                              latest_closed_period_end=cal.period_end.isoformat())
        if d < cal.prior_period_end:
            return None, _err("period_not_available",
                              "Only the last two closed pay periods are available.",
                              latest_closed_period_end=cal.period_end.isoformat())
        return d, None

    def timecard_view(self, worker_id: str, period_end: date, verification_id: Optional[str]) -> dict:
        """Timecard for a week with this sandbox's applied corrections overlaid (no lock check)."""
        w = self._worker(worker_id)
        days = self._timecard_days(w["worker_id"], period_end)
        corrections = self._corrections(verification_id, w["worker_id"], period_end)
        corrected = {}
        for c in corrections:
            if c["status"] == "applied":
                for d in c["dates"]:
                    corrected[d] = c["correction_id"]
        open_days = [d for d in days if d.is_discrepancy and d.work_date.isoformat() not in corrected]
        short = rules.hours_short(open_days)
        week_hours = sum(d.hours_worked for d in days)
        price = rules.price_restored_hours(short, week_hours, w["base_rate_usd"])
        deduction_dates = [d.work_date for d in open_days]
        day_dicts, paid = [], 0.0
        for d in days:
            cid = corrected.get(d.work_date.isoformat(), "")
            deduct = 0 if cid else d.auto_deduct_minutes
            paid += d.hours_worked - deduct / 60.0
            day_dicts.append({
                "date": d.work_date.isoformat(), "weekday": d.work_date.strftime("%A"),
                "punches": [{"in": a, "out": b} for a, b in d.segments],
                "hours_worked": d.hours_worked,
                "auto_deduct": {"type": "meal", "minutes": d.auto_deduct_minutes}
                if d.auto_deduct_minutes and not cid else None,
                "break_punched": d.break_punched, "paid_hours": d.hours_worked - deduct / 60.0,
                "corrected": bool(cid), "correction_id": cid})
        cal = self.calendar()
        return {
            "worker_id": w["worker_id"], "period_start": (period_end - timedelta(days=6)).isoformat(),
            "period_end": period_end.isoformat(),
            "period_end_display_en": rules.date_display_en(period_end),
            "period_end_display_es": rules.date_display_es(period_end),
            "is_latest_closed_period": period_end == cal.period_end,
            "days": day_dicts,
            "deduction_dates": [d.isoformat() for d in deduction_dates],
            "deduction_days_display_en": rules.days_display_en(deduction_dates),
            "deduction_days_display_es": rules.days_display_es(deduction_dates),
            "corrected_dates": sorted(corrected),
            "break_punched": not open_days, "discrepancy": bool(open_days),
            "hours_short": short, "week_hours_worked": week_hours, "paid_hours": paid,
            "overtime": price.overtime, "ot_hours": price.ot_hours,
            "base_rate_usd": float(price.base_rate_usd), "ot_rate_usd": float(price.ot_rate_usd),
            "amount_usd": float(price.amount_usd),
            "amount_display_en": rules.amount_display_en(price.amount_usd),
            "amount_display_es": rules.amount_display_es(price.amount_usd),
            "corrections": corrections, "verification_id": verification_id or ""}

    def get_timecard(self, verification_id: str, worker_id: str, period_end: str = "") -> dict:
        v, err = self.check_verification(verification_id, worker_id)
        if err:
            return err
        d, err = self._resolve_period(period_end)
        if err:
            return err
        return self.timecard_view(worker_id, d, verification_id)

    def _next_seq(self, conn: sqlite3.Connection, key: str) -> int:
        conn.execute("UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = ?", (key,))
        return int(conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()["value"])

    def submit_timecard_correction(self, verification_id: str, worker_id: str, period_end: str,
                                   dates: Any = None, remove_auto_deduct: str = "meal",
                                   audit_note: str = "", consent: Any = False,
                                   exclude_dates: Any = None) -> dict:
        """
        Remove wrongly auto-deducted meal breaks for ``dates`` (default: every
        discrepancy day in the period) minus ``exclude_dates``. Requires
        ``consent=True``. Writes only to this verification's sandbox.
        """
        v, err = self.check_verification(verification_id, worker_id)
        if err:
            return err
        if not coerce_bool(consent):
            return _err("consent_required",
                        "The colleague must agree before the timecard is corrected (consent=true).")
        if (remove_auto_deduct or "meal").strip().lower() != "meal":
            return _err("invalid_deduction_type", "Only 'meal' auto-deductions can be removed.")
        pe, err = self._resolve_period(period_end)
        if err:
            return err
        w = self._worker(worker_id)
        view = self.timecard_view(w["worker_id"], pe, verification_id)
        open_dates = set(view["deduction_dates"])
        requested = coerce_list(dates) or sorted(open_dates)
        excluded = set(coerce_list(exclude_dates))
        already = [d for d in requested if d in view["corrected_dates"]]
        if already:
            return _err("already_corrected", "Some of those dates were already corrected on this call.",
                        dates=already)
        invalid = [d for d in requested if d not in open_dates]
        if invalid:
            return _err("invalid_dates",
                        "These dates have no auto-deducted meal break without a punched break.",
                        dates=invalid, deduction_dates=sorted(open_dates))
        chosen = sorted(d for d in requested if d not in excluded)
        if not chosen:
            return _err("no_dates", "No dates left to correct after exclusions.")
        days = self._timecard_days(w["worker_id"], pe)
        chosen_dates = [date.fromisoformat(d) for d in chosen]
        hours = rules.hours_short(days, chosen_dates)
        price = rules.price_restored_hours(hours, sum(d.hours_worked for d in days), w["base_rate_usd"])
        with self._conn() as conn:
            seq = self._next_seq(conn, "correction_seq")
            cid = f"TC-{seq:06d}"
            conn.execute(
                "INSERT INTO ta_corrections VALUES (?, ?, ?, ?, ?, 'meal', ?, ?, ?, 'applied', ?, NULL)",
                (cid, verification_id, w["worker_id"], pe.isoformat(), json.dumps(chosen),
                 audit_note or "", hours, float(price.amount_usd), _now()))
        after = self.timecard_view(w["worker_id"], pe, verification_id)
        return {"correction_id": cid, "status": "applied", "worker_id": w["worker_id"],
                "period_end": pe.isoformat(), "dates": chosen,
                "dates_display_en": rules.days_display_en(chosen_dates),
                "dates_display_es": rules.days_display_es(chosen_dates),
                "excluded_dates": sorted(excluded), "remove_auto_deduct": "meal",
                "audit_note": audit_note or "", "hours": hours, "overtime": price.overtime,
                "amount_usd": float(price.amount_usd),
                "amount_display_en": rules.amount_display_en(price.amount_usd),
                "amount_display_es": rules.amount_display_es(price.amount_usd),
                "remaining_hours_short": after["hours_short"],
                "verification_id": verification_id}

    def cancel_timecard_correction(self, verification_id: str, correction_id: str) -> dict:
        """Reverse a correction made in this call; marks its audit row ``reversed``."""
        v, err = self.check_verification(verification_id)
        if err:
            return err
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM ta_corrections WHERE correction_id = ? "
                               "AND verification_id = ?",
                               ((correction_id or "").strip().upper(), verification_id)).fetchone()
            if row is None:
                return _err("correction_not_found", "No correction with that ID on this call.")
            if row["status"] == "reversed":
                return _err("already_reversed", "That correction was already reversed.",
                            correction_id=row["correction_id"])
            conn.execute("UPDATE ta_corrections SET status='reversed', reversed_at=? "
                         "WHERE correction_id = ?", (_now(), row["correction_id"]))
            conn.execute("UPDATE audit_events SET status='reversed' WHERE tool = "
                         "'submit_timecard_correction' AND verification_id = ? "
                         "AND json_extract(result, '$.correction_id') = ?",
                         (verification_id, row["correction_id"]))
        after = self.timecard_view(row["worker_id"], date.fromisoformat(row["period_end"]),
                                   verification_id)
        return {"correction_id": row["correction_id"], "status": "reversed",
                "worker_id": row["worker_id"], "period_end": row["period_end"],
                "dates": json.loads(row["dates"]), "hours": row["hours"],
                "restored_hours_short": after["hours_short"],
                "amount_usd": after["amount_usd"], "verification_id": verification_id}

    # -------------------------------------------------------------- servicenow

    def _case_dict(self, r: sqlite3.Row, verification_id: Optional[str]) -> dict:
        related = json.loads(r["related_records"] or "[]")
        detail = []
        for rid in related:
            with self._conn() as conn:
                c = conn.execute("SELECT status FROM ta_corrections WHERE correction_id = ? "
                                 "AND verification_id = ?", (rid, verification_id or "")).fetchone()
            detail.append({"id": rid, "table": "time_attendance.correction" if c else "unknown",
                           "status": c["status"] if c else "not_found"})
        return {"number": r["number"], "sys_id": r["sys_id"], "state": r["state"],
                "hr_service": r["hr_service"], "subject_person": r["subject_person"] or "",
                "contact_type": r["contact_type"], "short_description": r["short_description"],
                "description": r["description"], "related_records": related,
                "related_records_detail": detail, "assignment_group": r["assignment_group"],
                "resolved_by": r["resolved_by"], "opened_at": r["opened_at"],
                "resolved_at": r["resolved_at"] or "", "opened_by": "Savvy",
                "work_notes": json.loads(r["work_notes"] or "[]")}

    def create_hr_case(self, verification_id: str = "", subject_person: str = "",
                       hr_service: str = "", contact_type: str = "phone",
                       short_description: str = "", description: str = "",
                       related_records: Any = None, state: str = "new",
                       resolved_by: str = "", assignment_group: str = "") -> dict:
        """
        Open an HR case. The single unverified write allowed (H4) is
        ``hr_service="Identity verification"`` with no ``subject_person``;
        its free text is stored with digits masked.
        """
        hr_service = (hr_service or "").strip()
        if not hr_service:
            return _err("invalid_hr_service", "hr_service is required.")
        state = (state or "new").strip().lower()
        if state not in CASE_STATES:
            return _err("invalid_state", f"state must be one of {sorted(CASE_STATES)}.")
        v, err = self.check_verification(verification_id)
        related = coerce_list(related_records)
        if v is None:
            if hr_service.lower() != IDENTITY_VERIFICATION_SERVICE.lower() or rules.digits_only(subject_person):
                return err
            vid, subject, verified = None, "", False
            hr_service, state, related = IDENTITY_VERIFICATION_SERVICE, "new", []
            short_description = rules.mask_digit_runs(short_description)
            description = rules.mask_digit_runs(description)
        else:
            subject = rules.digits_only(subject_person) or v["colleague_id"]
            if subject != v["colleague_id"]:
                return _err("not_verified", "This verification does not cover that subject_person.")
            vid, verified = verification_id, True
        resolved = state in _CLOSED_STATES
        now = _now()
        with self._conn() as conn:
            seq = self._next_seq(conn, "case_seq")
            number = f"HR-{self.calendar().as_of.year}-{seq:04d}"
            conn.execute(
                "INSERT INTO sn_hr_cases VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]')",
                (uuid.uuid4().hex, number, vid, subject, hr_service, contact_type or "phone",
                 short_description or "", description or "", json.dumps(related), state,
                 (resolved_by or "Savvy") if resolved else "",
                 assignment_group or ("" if resolved else "Colleague Service"),
                 now, now if resolved else None))
            row = conn.execute("SELECT * FROM sn_hr_cases WHERE number = ?", (number,)).fetchone()
        result = self._case_dict(row, vid)
        result.update({"verified": verified, "verification_id": vid or ""})
        return result

    def _visible_case(self, verification_id: str, colleague_id: str, number: str):
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM sn_hr_cases WHERE number = ? AND "
                "(verification_id = ? OR (seeded = 1 AND subject_person = ?))",
                ((number or "").strip().upper(), verification_id, colleague_id)).fetchone()

    def add_work_note(self, verification_id: str, number: str, note: str) -> dict:
        v, err = self.check_verification(verification_id)
        if err:
            return err
        if not (note or "").strip():
            return _err("invalid_note", "note must not be empty.")
        row = self._visible_case(verification_id, v["colleague_id"], number)
        if row is None:
            return _err("case_not_found", "No case with that number for this caller.")
        notes = json.loads(row["work_notes"] or "[]")
        now = _now()
        notes.append({"note": note.strip(), "author": "Savvy", "at": now})
        with self._conn() as conn:
            conn.execute("UPDATE sn_hr_cases SET work_notes = ? WHERE number = ?",
                         (json.dumps(notes), row["number"]))
        return {"number": row["number"], "sys_id": row["sys_id"], "work_notes_count": len(notes),
                "last_note": note.strip(), "updated_at": now, "verification_id": verification_id}

    def get_hr_cases(self, verification_id: str, subject_person: str, state: str = "") -> dict:
        v, err = self.check_verification(verification_id, subject_person)
        if err:
            return err
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM sn_hr_cases WHERE subject_person = ? AND "
                "(verification_id = ? OR seeded = 1) ORDER BY opened_at, number",
                (v["colleague_id"], verification_id)).fetchall()
        cases = [self._case_dict(r, verification_id) for r in rows]
        wanted = (state or "").strip().lower()
        if wanted == "open":
            cases = [c for c in cases if c["state"] not in _CLOSED_STATES]
        elif wanted:
            cases = [c for c in cases if c["state"] == wanted]
        return {"subject_person": v["colleague_id"], "count": len(cases), "cases": cases,
                "verification_id": verification_id}

    # ------------------------------------------------------------- admin views

    def systems_view(self, verification_id: str = "") -> dict:
        """
        "What changed in the systems" for one sandbox (latest if omitted):
        the verification, the timecard with corrections overlaid, the
        corrections, Workday reads, and the ServiceNow cases.
        """
        cal = self.calendar()
        with self._conn() as conn:
            if verification_id:
                v = conn.execute("SELECT * FROM verifications WHERE verification_id = ?",
                                 (verification_id,)).fetchone()
            else:
                v = conn.execute("SELECT * FROM verifications ORDER BY rowid DESC LIMIT 1").fetchone()
            unverified = conn.execute("SELECT * FROM sn_hr_cases WHERE verification_id IS NULL "
                                      "AND seeded = 0 ORDER BY number").fetchall()
        view = {"as_of": cal.as_of.isoformat(), "period_end": cal.period_end.isoformat(),
                "verification": None, "time_attendance": None, "workday_hcm": None,
                "servicenow_hrsd": None,
                "unverified_cases": [self._case_dict(r, None) for r in unverified]}
        if v is None:
            return view
        vid, cid = v["verification_id"], v["colleague_id"]
        view["verification"] = dict(v)
        view["time_attendance"] = {
            "timecard": self.timecard_view(cid, cal.period_end, vid),
            "corrections": self._corrections(vid, cid)}
        view["workday_hcm"] = {"payroll_written": False, "reads": [
            {"tool": e["tool"], "args": e["args"], "result": e["result"], "at": e["at"]}
            for e in self.list_audit_events("workday_hcm", vid)]}
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM sn_hr_cases WHERE verification_id = ? "
                                "ORDER BY number", (vid,)).fetchall()
        view["servicenow_hrsd"] = {"cases": [self._case_dict(r, vid) for r in rows]}
        return view


def default_db_path() -> str:
    """``CVS_HR_DB_PATH`` or ``cvs_hr.db`` in the current working directory."""
    return os.environ.get("CVS_HR_DB_PATH", os.path.join(os.getcwd(), "cvs_hr.db"))


def open_database(path: Optional[str] = None) -> CvsHrDatabase:
    """Construct and initialise a :class:`CvsHrDatabase`."""
    db = CvsHrDatabase(path or default_db_path())
    db.init_db()
    return db
