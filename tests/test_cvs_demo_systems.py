"""
Tests for the CVS Phase 2 demo systems MCP server and its database:
identity (EMPLID + DOB, SMS one-time code), timecard and pay, absence and
time off, HR cases, SMS, call checkpoints and the demo reset.

The fixed values come from the Phase 2 build brief (Jeff M., EMPLID 2217203).

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastmcp import Client

from mcp_server_kit import cvs_demo_database as demo
from mcp_server_kit.cvs_demo_database import (CvsDemoDatabase, handoff_text, open_database, parse_dob,
                                              spoken_digits)
from mcp_server_kit.cvs_demo_systems import (CvsDemoDeskMCPServer, CvsDemoSystemsMCPServer, StaticKeyValidator,
                                             twilio_sender)

JEFF = "2217203"
DOB = "1991-03-14"
AS_OF = "2026-10-27"  # a Tuesday, the Session 1 demo day


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("CVS_DEMO_AS_OF", AS_OF)
    monkeypatch.delenv("CVS_HR_DEMO_SMS_TO", raising=False)
    monkeypatch.delenv("CVS_DEMO_REHEARSAL_OTP", raising=False)


class FakeSender:
    def __init__(self, result=None):
        self.sent, self.result = [], result or {"sid": "SM1"}

    def __call__(self, to, body):
        self.sent.append((to, body))
        return self.result


@pytest.fixture
def sender():
    return FakeSender()


@pytest.fixture
def server(tmp_path, sender):
    return CvsDemoSystemsMCPServer(db_path=str(tmp_path / "keys.db"),
                                   cvs_demo_db_path=str(tmp_path / "demo.db"), sender=sender)


@pytest.fixture
def db(server):
    return server.demo_db


async def call(server, tool, **args):
    async with Client(server.mcp) as client:
        result = await client.call_tool(tool, args)
    return json.loads(result.content[0].text)


def verify(db, emplid=JEFF):
    return db.verify_emplid_dob(emplid, DOB)


# ---------------------------------------------------------------------------
# Tool surface
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lists_every_brief_tool(server):
    async with Client(server.mcp) as client:
        names = {t.name for t in await client.list_tools()}
    assert names == {
        "verify_emplid_dob", "send_otp", "verify_otp", "get_timecard", "get_pay_results",
        "resolve_short_pay", "get_absence_balances", "list_absence_types", "submit_time_off",
        "get_open_cases", "create_case", "update_case", "send_sms", "save_call_context",
        "get_call_context", "reset_demo",
    }


# ---------------------------------------------------------------------------
# Scenario 1 over MCP, end to end
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_1_end_to_end(server, db):
    v = await call(server, "verify_emplid_dob", emplid="2 2 1 7 2 0 3", dob="03141991", entry="keypad")
    assert v["verified"] is True and v["emplid_display"] == "ending 7203"
    assert v["colleague_name"] == "Jeff M." and v["auth_method"].endswith("(keypad)")

    tc = await call(server, "get_timecard", emplid=JEFF)
    assert tc["unapproved_hours"] == 22.0 and tc["approver"] == "Roberta L."
    assert tc["approval_status"] == "not_approved" and "Every other timecard" in tc["team_approval"]
    assert tc["period_end_display"] == "Saturday, October 3rd"

    pay = await call(server, "get_pay_results", emplid=JEFF)
    assert pay["checks"][0]["pay_date"] == "2026-10-09" and pay["checks"][0]["short_hours"] == 22.0
    assert pay["next_regular_check"] == "2026-10-23" and pay["off_cycle_available"] is True

    cases = await call(server, "get_open_cases", emplid=JEFF)
    assert cases["case_ids"] == ["HRC0098561"]
    assert cases["cases"][0]["opened_on"] == "2026-10-25" and cases["cases"][0]["opened_weekday"] == "Sunday"
    assert (cases["primary_case_id"], cases["primary_case_weekday"], cases["primary_case_topic"]) == (
        "HRC0098561", "Sunday", "dental enrollment question")

    pay_case = await call(server, "create_case", emplid=JEFF, team="Payroll",
                          summary="22 h unapproved for period ending 2026-10-03; EMPLID 2217203")
    cr_case = await call(server, "create_case", emplid=JEFF, team="colleague relations",
                         summary="Concern that leader withheld approval after a prior report", restricted=False)
    assert pay_case["case_id"] == "HRC0098562" and pay_case["restricted"] is False
    assert cr_case["case_id"] == "HRC0098563" and cr_case["restricted"] is True
    assert cr_case["case_id_spoken"].startswith("H R C zero zero nine")
    assert cr_case["case_id_spoken_es"].startswith("hache erre ce cero cero nueve, ocho cinco seis")

    listed = await call(server, "get_open_cases", emplid=JEFF)
    assert listed["count"] == 3
    restricted = [c for c in listed["cases"] if c["restricted"]][0]
    assert restricted["summary"] == "Confidential Colleague Relations case"

    stored = db.list_audit_events()
    assert stored[0]["tool"] == "get_open_cases" and len(stored) == 7
    verify_row = [e for e in stored if e["tool"] == "verify_emplid_dob"][0]
    assert verify_row["args"]["dob"] == "***"


@pytest.mark.asyncio
async def test_null_optional_strings_are_accepted(server):
    """Artemis sends null for an unset session variable (caller_ani in a text test)."""
    assert (await call(server, "get_call_context", ani=None, emplid=None, exclude_context_id=None)) == {"found": False}
    r = await call(server, "save_call_context", ani=None, summary="pay short", context_id=None)
    assert r["error"] == "no_key"
    assert (await call(server, "send_otp", emplid=JEFF, ani=None))["sent"] is True


@pytest.mark.asyncio
async def test_data_tools_refuse_before_verification(server):
    for tool, args in [("get_timecard", {}), ("get_pay_results", {}), ("get_absence_balances", {}),
                       ("get_open_cases", {}), ("resolve_short_pay", {"option": "next_check"}),
                       ("submit_time_off", {"absence_type": "pto", "start_date": "2026-11-02", "days": 1}),
                       ("create_case", {"team": "Payroll", "summary": "x"}), ("send_sms", {"message": "hi"})]:
        r = await call(server, tool, emplid=JEFF, **args)
        assert r["error"] == "not_verified", tool


def test_verification_expires(db, monkeypatch):
    verify(db)
    assert db.is_verified(JEFF)
    later = datetime.now(timezone.utc) + timedelta(minutes=demo.VERIFICATION_TTL_MINUTES + 1)
    monkeypatch.setattr(demo, "_utcnow", lambda: later)
    assert not db.is_verified(JEFF)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

class TestVerifyEmplidDob:

    @pytest.mark.parametrize("dob", ["1991-03-14", "03/14/1991", "March 14th 1991", "Mar 14, 1991",
                                     "zero three one four one nine nine one", "19910314"])
    def test_accepts_date_formats(self, db, dob):
        assert db.verify_emplid_dob(JEFF, dob)["verified"] is True

    def test_partial_emplid_is_not_an_attempt(self, db):
        r = db.verify_emplid_dob("2217", DOB)
        assert r["outcome"] == "partial" and r["heard_digits"] == 4 and "attempts" not in r

    def test_wrong_dob_offers_otp(self, db):
        r = db.verify_emplid_dob(JEFF, "1990-01-01")
        assert r["outcome"] == "no_match" and r["otp_available"] is True and r["mobile_last4"] == "4417"
        assert r["escalate"] is False

    def test_bad_date(self, db):
        r = db.verify_emplid_dob(JEFF, "sometime in spring")
        assert r["outcome"] == "bad_date" and r["otp_available"] is True

    def test_unknown_emplid_escalates_on_second_attempt(self, db):
        first = db.verify_emplid_dob("1111111", DOB, attempt=1)
        second = db.verify_emplid_dob("1111111", DOB, attempt=2)
        assert first["otp_available"] is False and first["escalate"] is False
        assert second["escalate"] is True and "mobile_last4" not in second


def test_parse_dob_rejects_non_dates():
    assert parse_dob("13/45/1991") is None
    assert parse_dob("12345") is None
    assert parse_dob("") is None


class TestOtp:

    @pytest.mark.asyncio
    async def test_keypad_fails_then_sms_code(self, server, db, sender):
        bad = await call(server, "verify_emplid_dob", emplid=JEFF, dob="01011990", entry="keypad")
        assert bad["otp_available"] is True
        sent = await call(server, "send_otp", emplid=JEFF)
        assert sent == {"sent": True, "mobile_last4": "4417", "expires_in_seconds": 300,
                        "emplid_last4": "7203", "delivery": "rehearsal"}
        assert sender.sent == []
        ok = await call(server, "verify_otp", code="one three five seven nine zero", emplid=JEFF)
        assert ok["verified"] is True and ok["auth_method"] == "SMS one-time code"
        again = await call(server, "verify_otp", code="135790", emplid=JEFF)
        assert again["error"] == "no_code"
        logged = [e for e in db.list_audit_events() if e["tool"] == "verify_otp"][0]
        assert logged["args"]["code"] == "***"

    def test_real_sms_when_enabled(self, db, sender, monkeypatch):
        monkeypatch.setenv("CVS_HR_DEMO_SMS_TO", "(312) 555-0199")
        db.reset(sms_enabled=True)
        r = db.send_otp(JEFF, sender=sender)
        assert r["delivery"] == "sms" and sender.sent[0][0] == "+13125550199"
        code = sender.sent[0][1].split("code is ")[1][:6]
        assert db.verify_otp(code, JEFF)["verified"] is True

    def test_sms_enabled_without_sender_or_with_failure(self, db, monkeypatch):
        monkeypatch.setenv("CVS_HR_DEMO_SMS_TO", "+13125550199")
        db.reset(sms_enabled=True)
        assert db.send_otp(JEFF)["error"] == "sms_unavailable"
        failed = db.send_otp(JEFF, sender=FakeSender({"error": "twilio_http_500"}))
        assert failed["error"] == "sms_failed" and failed["detail"] == "twilio_http_500"

    def test_wrong_code_three_tries_then_locked(self, db):
        db.send_otp(JEFF)
        tries = [db.verify_otp("000000", JEFF) for _ in range(3)]
        assert [t["tries_left"] for t in tries] == [2, 1, 0] and tries[-1]["escalate"] is True
        assert db.verify_otp("135790", JEFF)["error"] == "locked"

    def test_code_expires(self, db, monkeypatch):
        db.send_otp(JEFF)
        later = datetime.now(timezone.utc) + timedelta(seconds=demo.OTP_TTL_SECONDS + 5)
        monkeypatch.setattr(demo, "_utcnow", lambda: later)
        r = db.verify_otp("135790", JEFF)
        assert r["error"] == "expired" and r["can_resend"] is True

    def test_rehearsal_code_override(self, db, monkeypatch):
        monkeypatch.setenv("CVS_DEMO_REHEARSAL_OTP", "246810")
        db.send_otp(JEFF)
        assert db.verify_otp("246810", JEFF)["verified"] is True

    def test_unknown_caller(self, db):
        assert db.send_otp("1111111")["error"] == "unknown_caller"
        assert db.send_otp(ani="+13125550000")["error"] == "unknown_caller"
        assert db.verify_otp("135790", "1111111")["error"] == "no_code"


# ---------------------------------------------------------------------------
# Dropped call: checkpoint and recall
# ---------------------------------------------------------------------------

class TestDroppedCall:

    ANI = "+1 (312) 555-0142"

    @pytest.mark.asyncio
    async def test_same_number_callback(self, server, db, monkeypatch):
        monkeypatch.setenv("CVS_DEMO_ANI_ALIASES", self.ANI)
        # First call: one sentence, a checkpoint by ANI, then the drop before verification.
        first = await call(server, "save_call_context", ani=self.ANI, summary="Says the October paycheck was short",
                           intents="pay_issue")
        assert first["keyed_on"] == ["emplid", "ani"] and len(first["context_id"]) >= 16

        # Callback: the new call's own checkpoint is skipped; the ANI gives only enough to greet.
        own = await call(server, "save_call_context", ani=self.ANI, summary="I got cut off")
        ctx = await call(server, "get_call_context", ani="3125550142", exclude_context_id=own["context_id"])
        assert ctx["found"] is True and "context_id" not in ctx
        assert (ctx["first_name"], ctx["mobile_last4"]) == ("Jeff", "4417")
        assert ctx["verified_required"] is True and "summary" not in ctx and "emplid_last4" not in ctx
        assert (await call(server, "send_otp", ani=self.ANI))["mobile_last4"] == "4417"
        ok = await call(server, "verify_otp", code="135790", ani=self.ANI)
        assert ok["verified"] is True and ok["emplid"] == JEFF

        full = await call(server, "get_call_context", emplid=JEFF, ani=self.ANI,
                          exclude_context_id=own["context_id"])
        assert full["summary"] == "Says the October paycheck was short" and full["intents"] == ["pay_issue"]
        assert full["summary_verified"] is False and full["emplid_last4"] == "7203"

    def test_different_number_callback_uses_emplid(self, db):
        verify(db)
        first = db.save_call_context(emplid=JEFF, ani="+13125550142", summary="pay short",
                                     open_case_ids="HRC0098561", pay_case_id="HRC0098562")
        own = db.save_call_context(ani="+13125550999", summary="calling back")
        assert db.get_call_context(ani="+13125550999", exclude_context_id=own["context_id"]) == {"found": False}
        ctx = db.get_call_context(emplid=JEFF, ani="+13125550999", exclude_context_id=own["context_id"])
        assert ctx["summary"] == "pay short" and ctx["summary_verified"] is True
        assert ctx["open_case_ids"] == ["HRC0098561"] and ctx["pay_case_id"] == "HRC0098562"

    def test_fresh_call_does_not_recall_itself(self, db):
        own = db.save_call_context(ani="+13125550142", summary="first ever call")
        verify(db)
        db.save_call_context(emplid=JEFF, ani="+13125550142", context_id=own["context_id"])
        assert db.get_call_context(emplid=JEFF, ani="+13125550142",
                                   exclude_context_id=own["context_id"]) == {"found": False}

    def test_later_saves_update_the_same_checkpoint(self, db):
        verify(db)
        first = db.save_call_context(emplid=JEFF, summary="first", intents=["pay_issue"], absence_request="3 days PTO")
        again = db.save_call_context(emplid=JEFF, cr_case_id="HRC0098563", context_id=first["context_id"])
        assert again["context_id"] == first["context_id"]
        ctx = db.get_call_context(emplid=JEFF)
        assert ctx["summary"] == "first" and ctx["intents"] == ["pay_issue"] and ctx["summary_verified"] is True
        assert ctx["cr_case_id"] == "HRC0098563" and ctx["absence_request"] == "3 days PTO"
        db.save_call_context(context_id=first["context_id"], summary="")
        assert db.get_call_context(emplid=JEFF)["summary"] == "first"

    def test_other_colleagues_checkpoint_is_not_returned(self, db):
        """An ANI-matched checkpoint tied to another EMPLID never reaches this colleague."""
        with db._conn() as conn:
            conn.execute("INSERT INTO colleagues VALUES ('3300001', 'Ana', 'Ana P.', '1990-01-01', '+15550100001', "
                         "'Tech', '6218', 'Roberta L.', 'Dana K.')")
        db.verify_emplid_dob("3300001", "1990-01-01")
        db.save_call_context(emplid="3300001", ani="+13125550142", summary="Ana's private matter")
        verify(db)
        assert db.get_call_context(emplid=JEFF, ani="+13125550142") == {"found": False}

    def test_context_token_cannot_move_to_another_colleague(self, db):
        with db._conn() as conn:
            conn.execute("INSERT INTO colleagues VALUES ('3300001', 'Ana', 'Ana P.', '1990-01-01', '+15550100001', "
                         "'Tech', '6218', 'Roberta L.', 'Dana K.')")
        db.verify_emplid_dob("3300001", "1990-01-01")
        ana = db.save_call_context(emplid="3300001", summary="Ana")
        verify(db)
        r = db.save_call_context(emplid=JEFF, summary="Jeff", context_id=ana["context_id"])
        assert r["error"] == "context_mismatch"
        assert db.save_call_context(emplid=JEFF, context_id="not-a-token")["context_id"] != "not-a-token"

    def test_recall_window(self, db, monkeypatch):
        db.save_call_context(ani="+13125550142", summary="x")
        later = datetime.now(timezone.utc) + timedelta(minutes=demo.RECALL_WINDOW_MINUTES + 1)
        monkeypatch.setattr(demo, "_utcnow", lambda: later)
        assert db.get_call_context(ani="+13125550142") == {"found": False}

    def test_refusals(self, db):
        assert db.save_call_context()["error"] == "no_key"
        assert db.save_call_context(emplid=JEFF)["error"] == "not_verified"
        assert db.get_call_context(emplid=JEFF)["error"] == "not_verified"
        assert db.get_call_context() == {"found": False}

    def test_drop_before_verification_known_number(self, db, monkeypatch):
        monkeypatch.setenv("CVS_DEMO_ANI_ALIASES", "+1 312 555 0177, +13125550188")
        assert db.get_call_context(ani="(312) 555-0177") == {"found": False}
        db.save_call_context(ani="(312) 555-0177", summary="October paycheck short", intents="pay_issue")
        ctx = db.get_call_context(ani="+13125550177")
        assert (ctx["first_name"], ctx["mobile_last4"]) == ("Jeff", "4417")
        assert db.send_otp(ani="+13125550177")["mobile_last4"] == "4417"
        assert db.verify_otp("135790", ani="+13125550177")["emplid"] == JEFF
        assert db.get_call_context(emplid=JEFF)["summary"] == "October paycheck short"

    def test_mobile_on_file_identifies_without_context(self, db):
        assert db.send_otp(ani="555-010-4417")["emplid_last4"] == "7203"
        assert db.get_call_context(ani="+15550104417") == {"found": False}

    def test_unknown_number_context(self, db):
        db.save_call_context(ani="+13125550142", summary="x")
        ctx = db.get_call_context(ani="+13125550142")
        assert ctx["found"] is True and ctx["first_name"] == "" and ctx["mobile_last4"] == ""

    def test_old_file_gets_the_new_column(self, tmp_path):
        import sqlite3
        path = str(tmp_path / "old.db")
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE call_context (id INTEGER PRIMARY KEY AUTOINCREMENT, emplid TEXT, ani TEXT, "
                     "summary TEXT, intents TEXT, open_case_ids TEXT, pay_case_id TEXT, cr_case_id TEXT, "
                     "absence_request TEXT, updated_at TEXT)")
        conn.commit()
        conn.close()
        assert open_database(path).save_call_context(ani="+13125550142", summary="x")["saved"] is True


# ---------------------------------------------------------------------------
# Pay resolution
# ---------------------------------------------------------------------------

class TestPay:

    def test_next_check_resolution_is_idempotent(self, db):
        verify(db)
        first = db.resolve_short_pay(JEFF, "next check")
        second = db.resolve_short_pay(JEFF, "off_cycle")
        assert first["pay_date"] == "2026-10-23" and first["pay_outcome"] == "next_check"
        assert second["reference"] == first["reference"] and second["pay_outcome"] == "next_check"
        assert "approved and will be paid on your next regular check" in first["display"]
        tc = db.get_timecard(JEFF)
        assert tc["approval_status"] == "approved_after_cutoff" and tc["unapproved_hours"] == 0.0
        assert db.get_pay_results(JEFF)["off_cycle_available"] is False

    def test_off_cycle(self, db):
        verify(db)
        r = db.resolve_short_pay(JEFF, "off-cycle")
        assert r["pay_date"] == "2026-10-30" and "off-cycle payment" in r["display"]

    def test_bad_option_and_other_period(self, db):
        verify(db)
        assert db.resolve_short_pay(JEFF, "cash")["error"] == "bad_option"
        assert db.get_timecard(JEFF, "2026-09-19")["error"] == "no_timecard"
        assert db.get_timecard(JEFF, "2026-10-03")["unapproved_hours"] == 22.0


# ---------------------------------------------------------------------------
# Scenario 2: absence and time off
# ---------------------------------------------------------------------------

class TestAbsence:

    def test_balances_in_days_and_hours(self, db):
        verify(db)
        b = db.get_absence_balances(JEFF)
        assert [(x["type"], x["hours"], x["days"]) for x in b["balances"]] == [
            ("pto", 24.0, 3.0), ("sick", 16.0, 2.0), ("floating_holiday", 8.0, 1.0)]
        assert b["balances"][0]["display"] == "PTO: twenty-four hours, which is three days" or \
            b["balances"][0]["display"].startswith("PTO:")
        assert b["next_monday"] == "2026-11-02" and b["accrual_hours_per_period"] == 6.15

    def test_list_absence_types_has_six_with_rules(self, db):
        types = db.list_absence_types()["types"]
        assert [t["type"] for t in types] == ["pto", "sick", "floating_holiday", "bereavement",
                                              "jury_duty", "leave_of_absence"]
        assert all(t["rule"] for t in types)

    def test_scenario_2_wrong_type_then_too_much_then_adjust(self, db):
        verify(db)
        wrong = db.submit_time_off(JEFF, "leave of absence", "2026-11-02", days=3, reason="moving apartments")
        assert wrong["error"] == "WRONG_TYPE" and wrong["suggested_types"] == ["pto", "floating_holiday"]

        too_much = db.submit_time_off(JEFF, "PTO", "2026-11-02", days=5)
        assert too_much["error"] == "INSUFFICIENT_BALANCE"
        assert too_much["display"] == "You have three days of PTO. Five would put you two days over."
        assert (too_much["available_days"], too_much["over_by_days"]) == (3.0, 2.0)

        pto = db.submit_time_off(JEFF, "pto", "2026-11-02", days=3)
        fh = db.submit_time_off(JEFF, "floating holiday", "2026-11-05", hours=8)
        assert pto["confirmation"] == "410221" and pto["confirmation_spoken"] == "four one zero, two two one"
        assert pto["dates_display"] == "Monday the 2nd, Tuesday the 3rd and Wednesday the 4th"
        assert pto["remaining_days"] == 0.0 and fh["remaining_hours"] == 0.0
        assert db.get_absence_balances(JEFF)["balances"][0]["hours"] == 0.0

    def test_validate_only_checks_without_submitting(self, db):
        verify(db)
        assert db.submit_time_off(JEFF, "pto", "2026-11-02", days=5, validate_only=True)["error"] == "INSUFFICIENT_BALANCE"
        ok = db.submit_time_off(JEFF, "pto", "2026-11-02", days=3, validate_only="true")
        assert ok["valid"] is True and ok["remaining_days_after"] == 0.0 and "confirmation" not in ok
        jury = db.submit_time_off(JEFF, "jury_duty", "2026-11-02", days=1, validate_only=True)
        assert jury["valid"] is True and "remaining_days_after" not in jury
        assert db.get_absence_balances(JEFF)["balances"][0]["hours"] == 24.0
        assert db.status()["counts"]["time_off"] == 0

    def test_weekend_start_rolls_to_workdays(self, db):
        verify(db)
        r = db.submit_time_off(JEFF, "sick", "2026-10-31", days=2)
        assert (r["start_date"], r["end_date"]) == ("2026-11-02", "2026-11-03")

    def test_non_balance_types(self, db):
        verify(db)
        assert db.submit_time_off(JEFF, "jury duty", "2026-11-02", days=5)["submitted"] is True
        assert "remaining_hours" not in db.submit_time_off(JEFF, "bereavement", "2026-11-09", days=3)
        assert db.submit_time_off(JEFF, "bereavement", "2026-11-09", days=4)["error"] == "WRONG_AMOUNT"

    @pytest.mark.parametrize("kind,start,days,hours,code", [
        ("vacation days", "2026-11-02", 1, 0, "UNKNOWN_TYPE"),
        ("pto", "next week", 1, 0, "BAD_DATE"),
        ("pto", "2026-11-02", 0, 0, "BAD_AMOUNT"),
        ("floating_holiday", "2026-11-02", 2, 0, "WRONG_AMOUNT"),
    ])
    def test_validation_errors(self, db, kind, start, days, hours, code):
        verify(db)
        assert db.submit_time_off(JEFF, kind, start, days=days, hours=hours)["error"] == code


# ---------------------------------------------------------------------------
# Cases and SMS
# ---------------------------------------------------------------------------

class TestCases:

    def test_create_validation(self, db):
        verify(db)
        assert db.create_case(JEFF, "Facilities", "x")["error"] == "bad_team"
        assert db.create_case(JEFF, "Payroll", "  ")["error"] == "missing_summary"
        masked = db.create_case(JEFF, "Benefits", "Call back at 312-555-0142", restricted="yes")
        assert masked["restricted"] is True
        with db._conn() as conn:
            stored = conn.execute("SELECT summary FROM cases WHERE case_id=?", (masked["case_id"],)).fetchone()
        assert "0142" in stored["summary"] and "312-555" not in stored["summary"]

    def test_create_is_idempotent_per_team_per_day(self, db):
        verify(db)
        first = db.create_case(JEFF, "Payroll", "22 h unapproved")
        again = db.create_case(JEFF, "payroll", "22 h unapproved, second try")
        assert first["created"] is True and again["created"] is False and again["existing"] is True
        assert again["case_id"] == first["case_id"]
        other = db.create_case(JEFF, "Colleague Relations", "reported the leader")
        assert other["created"] is True and other["case_id"] != first["case_id"]
        db.update_case(first["case_id"], state="resolved")
        assert db.create_case(JEFF, "Payroll", "new issue")["created"] is True

    @pytest.mark.asyncio
    async def test_update_case(self, server, db):
        verify(db)
        r = await call(server, "update_case", case_id="98561", note="Colleague asked for status", state="awaiting_info")
        assert r["updated"] is True and r["state"] == "awaiting_info" and r["notes"] == 1
        assert db.update_case("HRC0098561", state="resolved")["state"] == "resolved"
        assert db.get_open_cases(JEFF)["count"] == 0
        assert db.update_case("HRC0000001", note="x")["error"] == "no_case"
        assert db.update_case("HRC0098561", state="banana")["error"] == "bad_state"

    def test_update_case_needs_verification(self, db):
        assert db.update_case("HRC0098561", note="x")["error"] == "not_verified"

    @pytest.mark.asyncio
    async def test_send_sms_suppressed_when_off(self, server, db, sender):
        verify(db)
        r = await call(server, "send_sms", emplid=JEFF, message="Your case is HRC0098562")
        assert r["sent"] is False and r["suppressed"] is True and sender.sent == []
        assert db.send_sms(JEFF, "   ")["error"] == "empty_message"

    def test_send_sms_when_on(self, db, sender, monkeypatch):
        monkeypatch.setenv("CVS_HR_DEMO_SMS_TO", "+13125550199")
        db.reset(sms_enabled=True)
        verify(db)
        assert db.send_sms(JEFF, "Case HRC0098562", sender=sender)["sent"] is True
        assert db.send_sms(JEFF, "x")["error"] == "sms_unavailable"
        assert db.send_sms(JEFF, "x", sender=FakeSender({"error": "boom"}))["error"] == "sms_failed"


# ---------------------------------------------------------------------------
# Reset and seed
# ---------------------------------------------------------------------------

class TestReset:

    @pytest.mark.asyncio
    async def test_reset_restores_jeff_and_dates_the_case(self, server, db, monkeypatch):
        verify(db)
        db.create_case(JEFF, "Payroll", "x")
        db.submit_time_off(JEFF, "pto", "2026-11-02", days=1)
        status = await call(server, "reset_demo", status_only=True)
        seeded = len(demo.COLLEAGUES)  # one open benefits case per seeded colleague
        assert status["counts"]["cases"] == seeded + 1 and status["sms_enabled"] is False

        monkeypatch.setenv("CVS_DEMO_AS_OF", "2026-10-28")
        r = await call(server, "reset_demo")
        assert r["counts"] == {"cases": seeded, "time_off": 0, "pay_resolutions": 0, "verifications": 0,
                               "call_context": 0}
        assert r["benefits_case_opened"] == "2026-10-26" and r["benefits_case_weekday"] == "Monday"
        assert not db.is_verified(JEFF)
        verify(db)
        assert db.get_absence_balances(JEFF)["balances"][0]["hours"] == 24.0
        assert db.create_case(JEFF, "Payroll", "x")["case_id"] == "HRC0098562"

    def test_reset_keeps_or_sets_the_sms_switch(self, db, monkeypatch):
        monkeypatch.setenv("CVS_HR_DEMO_SMS_TO", "+13125550199")
        assert db.reset(sms_enabled=True)["sms_enabled"] is True
        status = db.reset()
        assert status["sms_enabled"] is True and status["sms_to_set"] is True

    def test_seed_is_not_rewritten_on_reopen(self, tmp_path, monkeypatch):
        path = str(tmp_path / "d.db")
        first = open_database(path)
        first.verify_emplid_dob(JEFF, DOB)
        first.create_case(JEFF, "Payroll", "x")
        monkeypatch.setenv("CVS_DEMO_AS_OF", "2026-11-30")
        again = open_database(path)
        assert again.status()["counts"]["cases"] == len(demo.COLLEAGUES) + 1
        assert again.status()["benefits_case_opened"] == "2026-10-25"

    def test_default_path_and_as_of(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CVS_DEMO_DB_PATH", str(tmp_path / "env.db"))
        assert demo.default_db_path() == str(tmp_path / "env.db")
        monkeypatch.delenv("CVS_DEMO_AS_OF")
        assert demo.as_of_date() == datetime.now(demo.DEMO_TZ).date()
        assert CvsDemoDatabase().db_path == "cvs_demo.db"


# ---------------------------------------------------------------------------
# Extra testers on their own phones
# ---------------------------------------------------------------------------

class TestTesters:

    DAVE = demo.TESTERS[0]

    def test_every_tester_is_seeded_with_their_own_case(self, db):
        verify(db)
        assert db.get_open_cases(JEFF)["case_ids"] == [demo.BENEFITS_CASE]
        for t in demo.TESTERS:
            assert db.verify_emplid_dob(t["emplid"], t["dob"])["verified"] is True
            assert db.get_open_cases(t["emplid"])["case_ids"] == [t["benefits_case"]]
            assert db.get_absence_balances(t["emplid"])["balances"][0]["hours"] == 24.0

    def test_ids_numbers_cases_and_managers_are_distinct(self):
        managers = [c["manager"] for c in demo.COLLEAGUES]
        assert len(set(managers)) == len(managers)
        emplids = [c["emplid"] for c in demo.COLLEAGUES]
        cases = [c["benefits_case"] for c in demo.COLLEAGUES]
        mobiles = [c["mobile"] for c in demo.COLLEAGUES]
        assert len(set(emplids)) == len(emplids) and all(len(e) == 7 for e in emplids)
        assert len(set(cases)) == len(cases) and len(set(mobiles)) == len(mobiles)
        # Seeded cases sit below the running sequence, so new cases never collide with them.
        assert all(int(c[3:]) < demo.FIRST_CASE_SEQ for c in cases)

    def test_tester_is_recognised_by_their_own_number(self, db):
        r = db.send_otp(ani=self.DAVE["mobile"])
        assert r["sent"] is True and r["mobile_last4"] == self.DAVE["mobile"][-4:]
        assert r["emplid_last4"] == self.DAVE["emplid"][-4:]

    @pytest.mark.asyncio
    async def test_tester_callback_greets_the_tester_not_jeff(self, server):
        await call(server, "save_call_context", ani=self.DAVE["mobile"], summary="Says the paycheck was short")
        own = await call(server, "save_call_context", ani=self.DAVE["mobile"], summary="I got cut off")
        ctx = await call(server, "get_call_context", ani=self.DAVE["mobile"], exclude_context_id=own["context_id"])
        assert ctx["found"] is True and ctx["first_name"] == "Dave"

    def test_a_tester_case_does_not_touch_jeff(self, db):
        db.verify_emplid_dob(self.DAVE["emplid"], self.DAVE["dob"])
        verify(db)
        db.create_case(self.DAVE["emplid"], "Payroll", "Timecard not approved")
        assert db.get_open_cases(JEFF)["case_ids"] == [demo.BENEFITS_CASE]
        assert db.get_open_cases(self.DAVE["emplid"])["count"] == 2


def test_spoken_helpers():
    assert spoken_digits("HRC0098562") == "zero zero nine, eight five six, two"
    assert demo.days_text(1) == "one day" and demo.days_text(2.5) == "2.5 days"
    assert demo.normalize_type("Floating-Holiday") == "floating_holiday"
    assert demo.normalize_team("the colleague relations team") == "Colleague Relations"


# ---------------------------------------------------------------------------
# Twilio sender
# ---------------------------------------------------------------------------

class TestTwilioSender:

    def _client(self, handler):
        return httpx.Client(transport=httpx.MockTransport(handler))

    def test_not_configured(self, monkeypatch):
        for var in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_MESSAGING_SERVICE_SID"):
            monkeypatch.delenv(var, raising=False)
        assert twilio_sender("+1", "x") == {"error": "twilio_not_configured"}

    @pytest.fixture
    def creds(self, monkeypatch):
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC1")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
        monkeypatch.setenv("TWILIO_MESSAGING_SERVICE_SID", "MG1")

    def test_success(self, creds):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["body"] = request.content.decode()
            return httpx.Response(201, json={"sid": "SM9"})

        assert twilio_sender("+13125550199", "hi", client=self._client(handler)) == {"sid": "SM9"}
        assert seen["url"].endswith("/Accounts/AC1/Messages.json") and "MessagingServiceSid=MG1" in seen["body"]

    def test_http_error(self, creds):
        client = self._client(lambda r: httpx.Response(400, json={"message": "bad"}))
        assert twilio_sender("+1", "x", client=client) == {"error": "twilio_http_400"}

    def test_request_error(self, creds):
        def boom(request):
            raise httpx.ConnectError("down")
        assert twilio_sender("+1", "x", client=self._client(boom))["error"].startswith("request_failed")

    def test_owns_its_client(self, creds, monkeypatch):
        made = []
        real = httpx.Client

        def factory(**kw):
            c = real(transport=httpx.MockTransport(lambda r: httpx.Response(201, json={"sid": "SM2"})))
            made.append(c)
            return c

        monkeypatch.setattr(httpx, "Client", factory)
        assert twilio_sender("+1", "x") == {"sid": "SM2"} and made[0].is_closed


# ---------------------------------------------------------------------------
# Hand-off context for the transfer target (Sam, Colleague Relations)
# ---------------------------------------------------------------------------

class Clock:
    """A controllable ``_utcnow`` so window and newest-wins checks are exact."""

    def __init__(self, monkeypatch):
        self.now = datetime(2026, 10, 27, 17, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(demo, "_utcnow", lambda: self.now)

    def advance(self, minutes=0, seconds=0):
        self.now += timedelta(minutes=minutes, seconds=seconds)


@pytest.fixture
def clock(monkeypatch):
    return Clock(monkeypatch)


@pytest.fixture
def desk(tmp_path, server, monkeypatch):
    monkeypatch.delenv("CVS_DEMO_DESK_API_KEY", raising=False)
    return CvsDemoDeskMCPServer(db_path=str(tmp_path / "keys.db"), cvs_demo_db_path=str(tmp_path / "demo.db"))


CR_SUMMARY = ("Colleague says Roberta L. approves timecards and everyone else on the team was approved, "
              "and that they raised concerns with Dana K. a few weeks ago.")


def peek(db, **kw):
    """Look without consuming (tests only; the MCP tool always consumes)."""
    return db.get_latest_handoff(consume=False, **kw)


def jeff_escalation(db, clock):
    """Savvy's Scenario 1 call: payroll case, next-check fix, then the confidential CR case."""
    verify(db)
    db.save_call_context(emplid=JEFF, ani="+15550104417", summary="Short check for the last pay period",
                         intents="pay_issue")
    pay = db.create_case(JEFF, "Payroll", "22 hours not approved before payroll closed")
    db.resolve_short_pay(JEFF, "next_check")
    clock.advance(minutes=2)
    cr = db.create_case(JEFF, "Colleague Relations", CR_SUMMARY + " Second sentence with more detail.",
                        restricted=True)
    clock.advance(minutes=3)
    return pay, cr


class TestHandoff:

    DAVE, MIKE = demo.TESTERS

    @pytest.mark.asyncio
    async def test_tool_takes_no_arguments(self, desk):
        async with Client(desk.mcp) as client:
            (tool,) = await client.list_tools()
        assert tool.inputSchema.get("properties", {}) == {} and not tool.inputSchema.get("required")
        with pytest.raises(Exception):
            await call(desk, "get_latest_handoff", within_minutes=100000)

    @pytest.mark.asyncio
    async def test_tool_lives_only_on_the_desk_server(self, server, desk):
        async with Client(desk.mcp) as client:
            assert {t.name for t in await client.list_tools()} == {"get_latest_handoff"}
        async with Client(server.mcp) as client:
            assert "get_latest_handoff" not in {t.name for t in await client.list_tools()}

    @pytest.mark.asyncio
    async def test_jeff_escalation_over_mcp_is_returned_once(self, desk, db, clock):
        pay, cr = jeff_escalation(db, clock)
        before = db.status()["counts"]
        r = await call(desk, "get_latest_handoff")
        assert r["found"] is True and r["reason"] == "colleague_relations" and r["within_minutes"] == 10
        assert (r["first_name"], r["colleague_name"], r["emplid_last4"]) == ("Jeff", "Jeff M.", "7203")
        assert r["pay_case_id"] == pay["case_id"] and r["cr_case_id"] == cr["case_id"]
        assert r["pay_case_spoken"] == pay["case_id_spoken"] == "H R C zero zero nine, eight five six, two"
        assert r["cr_case_spoken"] == cr["case_id_spoken"]
        assert r["pay_outcome"] == "next_check"
        assert r["pay_outcome_display"] == ("The 22 hours will be paid on your next regular check on "
                                            "Friday, October 23rd.")
        assert r["call_reason"] == "Short check for the last pay period"
        assert r["concern_summary"] == CR_SUMMARY and r["minutes_ago"] == 3  # first sentence only
        assert r["display"] == (
            "Jeff, you just spoke with Savvy about your short check for the period ending October 3rd. "
            f"Payroll case {pay['case_id_spoken']} is open, and your confidential Colleague Relations case "
            f"{cr['case_id_spoken']} is open. The 22 hours will be paid on your next regular check on "
            "Friday, October 23rd. The case notes say: " + CR_SUMMARY.rstrip(".") + ".")
        # Consumed: a second read in the window finds nothing; nothing else changed.
        assert (await call(desk, "get_latest_handoff"))["found"] is False
        assert db.status()["counts"] == before
        assert [e["tool"] for e in db.list_audit_events(2)] == ["get_latest_handoff"] * 2

    def test_a_newer_escalation_after_consumption_is_returned(self, db, clock):
        verify(db)
        db.create_case(JEFF, "Payroll", "short check")
        assert db.get_latest_handoff()["reason"] == "payroll"
        assert db.get_latest_handoff()["found"] is False
        clock.advance(minutes=1)
        cr = db.create_case(JEFF, "Colleague Relations", CR_SUMMARY)
        assert db.get_latest_handoff()["cr_case_id"] == cr["case_id"]
        assert db.get_latest_handoff()["found"] is False

    def test_not_found(self, db, clock):
        r = db.get_latest_handoff()
        assert r == {"found": False, "within_minutes": 10, "display": "I don't see a recent hand-off."}

    def test_other_team_cases_are_never_a_handoff(self, db, clock):
        verify(db)
        db.create_case(JEFF, "Benefits", "Dental question")
        assert db.get_latest_handoff()["found"] is False

    def test_window_boundary(self, db, clock):
        verify(db)
        db.create_case(JEFF, "Payroll", "short check")
        clock.advance(minutes=10)
        r = peek(db)
        assert r["found"] is True and r["minutes_ago"] == 10  # exactly 10 minutes: still in
        clock.advance(seconds=1)
        assert peek(db)["found"] is False
        # The window can be narrowed (tests) but never widened.
        for wide in (30, 10 ** 9, float("inf"), "bad", None, "9" * 400):
            r = peek(db, within_minutes=wide)
            assert r["found"] is False and r["within_minutes"] == 10, wide
        assert peek(db, within_minutes=0)["within_minutes"] == 1
        assert peek(db, within_minutes=-5)["within_minutes"] == 1

    def test_only_a_recently_verified_colleague_qualifies(self, db, clock):
        verify(db)
        clock.advance(minutes=11)  # still verified for Savvy (2 hours), but not within the 10-minute window
        db.create_case(JEFF, "Colleague Relations", CR_SUMMARY)
        db.save_call_context(emplid=JEFF, summary="pay short")
        assert peek(db)["found"] is False
        assert peek(db, within_minutes=15)["found"] is False  # can't widen past 10
        verify(db)  # re-verified now
        assert peek(db)["found"] is True

    def test_unverified_checkpoint_is_never_a_handoff(self, db, clock):
        db.save_call_context(ani=demo.JEFF["mobile"], summary="Says the paycheck was short")  # linked by ANI only
        db.save_call_context(ani="+15550109999", summary="Hung up before giving an ID")
        assert db.get_latest_handoff()["found"] is False

    def test_cr_case_preferred_over_payroll(self, db, clock):
        verify(db)
        cr = db.create_case(JEFF, "Colleague Relations", CR_SUMMARY)
        clock.advance(minutes=1)
        pay = db.create_case(JEFF, "Payroll", "short check")  # newer, but the CR case still sets the reason
        r = db.get_latest_handoff()
        assert r["reason"] == "colleague_relations" and r["cr_case_id"] == cr["case_id"]
        assert r["pay_case_id"] == pay["case_id"] and r["minutes_ago"] == 0

    def test_cr_only(self, db, clock):
        verify(db)
        cr = db.create_case(JEFF, "Colleague Relations", CR_SUMMARY)
        r = db.get_latest_handoff()
        assert r["reason"] == "colleague_relations" and r["pay_case_id"] == r["pay_case_spoken"] == ""
        assert f"Your confidential Colleague Relations case {cr['case_id_spoken']} is open." in r["display"]
        assert r["pay_outcome"] == r["pay_outcome_display"] == "" and r["call_reason"] == ""

    def test_payroll_only(self, db, clock):
        verify(db)
        pay = db.create_case(JEFF, "Payroll", "22 hours not approved")
        db.resolve_short_pay(JEFF, "off_cycle")
        r = db.get_latest_handoff()
        assert r["reason"] == "payroll" and r["cr_case_id"] == r["cr_case_spoken"] == ""
        assert r["concern_summary"] == "" and r["pay_outcome"] == "off_cycle"
        assert r["display"].startswith("Jeff, you just spoke with Savvy about your short check")
        assert f"Payroll case {pay['case_id_spoken']} is open." in r["display"]
        assert "as an off-cycle payment" in r["display"] and "Colleague Relations" not in r["display"]

    def test_call_context_only_fallback(self, db, clock):
        verify(db)
        db.save_call_context(emplid=JEFF, summary="Asked how to request time off.")
        r = db.get_latest_handoff()
        assert r["found"] is True and r["reason"] == "other" and r["first_name"] == "Jeff"
        assert r["call_reason"] == "Asked how to request time off."
        assert r["pay_case_id"] == r["cr_case_id"] == ""
        assert r["display"] == ("Jeff, you just spoke with Savvy. The note from that call says: "
                                "Asked how to request time off.")
        assert db.get_latest_handoff()["found"] is False

    def test_old_call_context_is_ignored(self, db, clock):
        verify(db)
        db.save_call_context(emplid=JEFF, summary="pay short")
        clock.advance(minutes=11)
        assert db.get_latest_handoff()["found"] is False

    def test_no_pii_in_any_field(self, db, clock):
        verify(db)
        db.save_call_context(emplid=JEFF, ani="+15550104417",
                             summary="Jeff 2217203, born 03/14/1991, can be reached at 555-010-4417")
        db.create_case(JEFF, "Payroll", "EMPLID 2217203 short check")
        db.create_case(JEFF, "Colleague Relations",
                       "Born March 14, 1991, call back at +1 555 010 4417 about Dana K. " + "x" * 300)
        r = db.get_latest_handoff()
        flat = json.dumps(r)
        for leak in (JEFF, "5550104417", "010-4417", "010 4417", "1991", "03/14", "March 14"):
            assert leak not in flat, leak
        assert r["emplid_last4"] == "7203" and "emplid" not in r
        assert not any("mobile" in k or "phone" in k or "dob" in k for k in r)
        assert len(r["concern_summary"]) <= demo.HANDOFF_TEXT_MAX and len(r["call_reason"]) <= demo.HANDOFF_TEXT_MAX

    def test_newest_colleague_wins(self, db, clock):
        verify(db)
        db.verify_emplid_dob(self.DAVE["emplid"], self.DAVE["dob"])
        db.verify_emplid_dob(self.MIKE["emplid"], self.MIKE["dob"])
        db.create_case(JEFF, "Colleague Relations", CR_SUMMARY)
        clock.advance(minutes=1)
        db.create_case(self.DAVE["emplid"], "Payroll", "short check")
        clock.advance(minutes=1)
        r = db.get_latest_handoff()
        assert (r["first_name"], r["reason"]) == ("Dave", "payroll")
        assert r["emplid_last4"] == self.DAVE["emplid"][-4:] and r["cr_case_id"] == ""
        # Dave's call context and Jeff's pay resolution never leak into Mike's hand-off.
        db.save_call_context(emplid=self.DAVE["emplid"], summary="Dave's pay question")
        db.resolve_short_pay(JEFF, "next_check")
        clock.advance(minutes=1)
        mike_cr = db.create_case(self.MIKE["emplid"], "Colleague Relations", "Mike reported his leader")
        r = db.get_latest_handoff()
        assert (r["first_name"], r["reason"], r["cr_case_id"]) == ("Mike", "colleague_relations", mike_cr["case_id"])
        assert r["call_reason"] == "" and r["pay_outcome"] == "" and r["pay_case_id"] == ""
        clock.advance(minutes=1)
        db.create_case(JEFF, "Payroll", "short check")
        assert db.get_latest_handoff()["first_name"] == "Jeff"

    @pytest.mark.asyncio
    async def test_reset_demo_clears_it(self, server, desk, db, clock):
        jeff_escalation(db, clock)
        assert (await call(desk, "get_latest_handoff"))["found"] is True
        with db._conn() as conn:
            assert conn.execute("SELECT COUNT(*) FROM handoffs_consumed").fetchone()[0] == 1
        await call(server, "reset_demo")
        with db._conn() as conn:
            assert conn.execute("SELECT COUNT(*) FROM handoffs_consumed").fetchone()[0] == 0
        assert (await call(desk, "get_latest_handoff"))["found"] is False

    def test_existing_file_gains_created_at(self, tmp_path):
        path = str(tmp_path / "old.db")
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE cases (case_id TEXT PRIMARY KEY, emplid TEXT, team TEXT, case_type TEXT, "
                     "summary TEXT, restricted INTEGER, state TEXT, opened_on TEXT, notes TEXT)")
        conn.commit()
        conn.close()
        db = open_database(path)
        with db._conn() as c:
            assert "created_at" in {r["name"] for r in c.execute("PRAGMA table_info(cases)")}
        assert db.get_latest_handoff()["found"] is False


def test_handoff_text():
    assert handoff_text("Talked to Dana K. last week. Then more.") == "Talked to Dana K. last week."
    assert handoff_text("  no   end punctuation ") == "no end punctuation"
    assert handoff_text("Call 312-555-0142.") == "Call a number."
    assert handoff_text("22 hours, the 14th of March.") == "a number hours, the a date."
    assert handoff_text("Cases HRC0098563 and hrc0098562 are open.") == "Cases HRC0098563 and HRC0098562 are open."
    cut = handoff_text("word " * 100)
    assert len(cut) <= demo.HANDOFF_TEXT_MAX and cut.endswith("word.")
    assert handoff_text("") == ""


@pytest.mark.parametrize("dob", [
    "14 March 1991", "March 14th, 1991", "March 14 1991", "Mar. 14, 1991", "14th of March 1991",
    "3.14.1991", "03/14/1991", "3-14-91", "1991-03-14", "1991", "03141991", "19910314", "3 14 1991",
])
def test_handoff_text_never_leaks_a_date_of_birth(dob):
    out = handoff_text(f"Colleague (born {dob}) says HRC0098563 is about Dana K. and 2217203.")
    assert not any(c.isdigit() for c in out.replace("HRC0098563", "")), out
    assert "March" not in out and "Mar." not in out and "HRC0098563" in out


class TestDeskKey:

    def _validator(self, srv):
        return srv._http_middleware[0].kwargs["db_manager"]

    def test_shared_keys_by_default(self, desk):
        assert desk.own_key is False and self._validator(desk) is desk.db_manager

    def test_own_key_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CVS_DEMO_DESK_API_KEY", " desk-secret ")
        srv = CvsDemoDeskMCPServer(db_path=str(tmp_path / "k.db"), cvs_demo_db_path=str(tmp_path / "d.db"))
        check = self._validator(srv)
        assert srv.own_key is True and isinstance(check, StaticKeyValidator)
        assert check.validate_key("desk-secret") is True
        assert check.validate_key("other") is False and check.validate_key(None) is False

    def test_explicit_key_overrides_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CVS_DEMO_DESK_API_KEY", "from-env")
        srv = CvsDemoDeskMCPServer(db_path=str(tmp_path / "k.db"), cvs_demo_db_path=str(tmp_path / "d.db"),
                                   desk_api_key="")
        assert srv.own_key is False

    def test_http_rejects_the_shared_key_when_own_key_set(self, tmp_path):
        from starlette.testclient import TestClient
        srv = CvsDemoDeskMCPServer(db_path=str(tmp_path / "k.db"), cvs_demo_db_path=str(tmp_path / "d.db"),
                                   desk_api_key="desk-secret")
        shared = sqlite3.connect(str(tmp_path / "k.db")).execute("SELECT key FROM api_keys").fetchone()[0]
        app = srv.mcp.http_app(path="/mcp", middleware=srv._http_middleware, transport="streamable-http")
        with TestClient(app) as client:
            assert client.post("/mcp", headers={"X-API-Key": shared}, json={}).status_code == 401
            assert client.post("/mcp", headers={"X-API-Key": "desk-secret"}, json={}).status_code != 401
