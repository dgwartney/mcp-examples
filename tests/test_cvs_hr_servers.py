"""
Tests for the four CVS HR mock MCP servers and their shared database:
cvs_identity, workday_hcm, time_attendance, servicenow_hrsd.

Covers every field the Savvy turn script reads, at the demo as-of date
(2026-10-08) and at the recording's (2026-09-01), plus the recovery rows,
verification locks, the single unverified case, sandbox isolation, the SMS
switch, and one audit row per call.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import json

import pytest
import pytest_asyncio
from fastmcp import Client

from mcp_server_kit.cvs_hr_database import (
    CvsHrDatabase, coerce_bool, coerce_list, normalize_e164, open_database,
)
from mcp_server_kit.cvs_identity import CvsIdentityMCPServer
from mcp_server_kit.servicenow_hrsd import ServicenowHrsdMCPServer
from mcp_server_kit.time_attendance import TimeAttendanceMCPServer
from mcp_server_kit.workday_hcm import WorkdayHcmMCPServer

DANIEL = "7742318"
DEMO = {
    "as_of": "2026-10-08", "period_end": "2026-10-03",
    "period_end_display_en": "Saturday, October 3rd",
    "period_end_display_es": "sábado 3 de octubre",
    "deduction_dates": ["2026-09-28", "2026-09-30", "2026-10-01"],
    "deduction_days_display_en": "Monday the 28th, Wednesday the 30th and Thursday, October 1st",
    "deduction_days_display_es": "lunes 28, miércoles 30 de septiembre y jueves 1 de octubre",
    "pay_date": "2026-10-16", "pay_date_display_en": "Friday, October 16th",
    "pay_date_display_es": "viernes 16 de octubre",
    "projected": ["2026-10-16", "2026-10-30", "2026-11-13"],
    "target_label_en": "mid-November", "target_label_es": "mediados de noviembre",
    "prior_period_end": "2026-09-26",
}
RECORDING = {
    "as_of": "2026-09-01", "period_end": "2026-08-29",
    "period_end_display_en": "Saturday, August 29th",
    "period_end_display_es": "sábado 29 de agosto",
    "deduction_dates": ["2026-08-24", "2026-08-26", "2026-08-27"],
    "deduction_days_display_en": "Monday the 24th, Wednesday the 26th and Thursday the 27th",
    "deduction_days_display_es": "lunes 24, miércoles 26 y jueves 27 de agosto",
    "pay_date": "2026-09-11", "pay_date_display_en": "Friday, September 11th",
    "pay_date_display_es": "viernes 11 de septiembre",
    "projected": ["2026-09-11", "2026-09-25", "2026-10-09"],
    "target_label_en": "mid-October", "target_label_es": "mediados de octubre",
    "prior_period_end": "2026-08-22",
}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("CVS_HR_AS_OF", DEMO["as_of"])
    monkeypatch.delenv("CVS_HR_DEMO_SMS_TO", raising=False)


@pytest.fixture
def paths(tmp_path):
    return {"db_path": str(tmp_path / "keys.db"), "cvs_hr_db_path": str(tmp_path / "cvs_hr.db")}


@pytest.fixture
def hr(paths):
    return open_database(paths["cvs_hr_db_path"])


class Systems:
    """All four servers over one database, called the way Artemis calls them."""

    def __init__(self, paths):
        self.servers = {
            "cvs_identity": CvsIdentityMCPServer(**paths),
            "workday_hcm": WorkdayHcmMCPServer(**paths),
            "time_attendance": TimeAttendanceMCPServer(**paths),
            "servicenow_hrsd": ServicenowHrsdMCPServer(**paths),
        }
        self.db = CvsHrDatabase(paths["cvs_hr_db_path"])

    async def call(self, system: str, tool: str, **args) -> dict:
        async with Client(self.servers[system].mcp) as client:
            result = await client.call_tool(tool, args)
        return json.loads(result.content[0].text)

    async def verify(self, colleague_id=DANIEL, mobile="", attempt=1) -> dict:
        return await self.call("cvs_identity", "verify_colleague",
                               colleague_id=colleague_id, mobile=mobile, attempt=attempt)


@pytest.fixture
def systems(paths):
    return Systems(paths)


def correction_args(vid, cal=DEMO, **overrides):
    args = dict(worker_id=DANIEL, period_end=cal["period_end"], dates=cal["deduction_dates"],
                remove_auto_deduct="meal",
                audit_note="No break taken per punches; colleague confirmed",
                consent=True, verification_id=vid)
    args.update(overrides)
    return args


# ---------------------------------------------------------------------------
# The golden turn script, at both as-of dates
# ---------------------------------------------------------------------------

class TestGoldenTurnScript:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cal", [DEMO, RECORDING], ids=["demo-2026-10-08", "recording-2026-09-01"])
    async def test_every_turn_script_field(self, systems, monkeypatch, cal):
        monkeypatch.setenv("CVS_HR_AS_OF", cal["as_of"])
        systems.db.reset()

        # Turn 3 ① verify_colleague
        v = await systems.verify("774-2318")
        assert v["verified"] is True and v["display_name"] == "Daniel R."
        assert v["verification_id"].startswith("ver_") and "sms_to" in v
        vid = v["verification_id"]

        # Turn 3 ② get_worker
        w = await systems.call("workday_hcm", "get_worker", worker_id=DANIEL, verification_id=vid)
        assert w["first_name"] == "Daniel" and w["job_title"] == "Pharmacy Technician"
        assert w["location"]["store"] == "6218" and w["location"]["city"] == "Phoenix"
        assert w["base_rate_usd"] == 18.50 and w["ot_rate_usd"] == 27.75

        # Turn 3 ③ get_timecard (default: latest closed period)
        tc = await systems.call("time_attendance", "get_timecard", worker_id=DANIEL, verification_id=vid)
        for key in ("period_end", "period_end_display_en", "period_end_display_es", "deduction_dates",
                    "deduction_days_display_en", "deduction_days_display_es"):
            assert tc[key] == cal[key], key
        assert tc["break_punched"] is False and tc["hours_short"] == 1.5
        assert tc["week_hours_worked"] == 43.0 and tc["overtime"] is True
        assert tc["amount_usd"] == 41.63
        assert tc["amount_display_en"] == "$41.63"
        assert tc["amount_display_es"] == "41 dólares con 63 centavos"
        flagged = [d for d in tc["days"] if d["auto_deduct"]]
        assert [d["date"] for d in flagged] == cal["deduction_dates"]
        assert all(d["auto_deduct"] == {"type": "meal", "minutes": 30} and not d["break_punched"]
                   for d in flagged)
        assert all(d["punches"] for d in tc["days"])

        # Turn 4 ④ submit_timecard_correction, ⑤ evaluate_pay_correction
        c = await systems.call("time_attendance", "submit_timecard_correction", **correction_args(vid, cal))
        assert c["status"] == "applied" and c["correction_id"].startswith("TC-")
        assert c["hours"] == 1.5 and c["amount_usd"] == 41.63
        p = await systems.call("workday_hcm", "evaluate_pay_correction",
                               worker_id=DANIEL, hours=1.5, verification_id=vid)
        assert p["pay_date"] == cal["pay_date"]
        assert p["pay_date_display_en"] == cal["pay_date_display_en"]
        assert p["pay_date_display_es"] == cal["pay_date_display_es"]
        assert p["off_cycle"] is False and p["off_cycle_threshold_hours"] == 4
        assert p["rule_id"] == "PAY-CORRECTIONS v2.4"
        assert p["read_only"] is True and p["payroll_written"] is False
        assert p["correction_id"] == c["correction_id"]  # cross-system consistency

        # Turn 5 ⑥ get_time_off_balance
        b = await systems.call("workday_hcm", "get_time_off_balance", worker_id=DANIEL, verification_id=vid)
        assert (b["plan"], b["balance_hours"], b["balance_days"]) == ("PTO", 62.5, 7.8)

        # Turn 6 ⑦ project_time_off
        pr = await systems.call("workday_hcm", "project_time_off",
                                worker_id=DANIEL, target_hours=80, verification_id=vid)
        assert pr["accrual_per_period_hours"] == 6.15 and pr["hours_needed"] == 17.5
        assert pr["periods_needed"] == 3 and pr["already_enough"] is False
        assert pr["target_pay_date"] == cal["projected"][2]
        assert pr["projected_pay_dates"] == cal["projected"]
        assert pr["target_label"] == cal["target_label_en"] == pr["target_label_en"]
        assert pr["target_label_es"] == cal["target_label_es"]

        # Turn 10 ⑨ create_hr_case
        case = await systems.call(
            "servicenow_hrsd", "create_hr_case", subject_person=DANIEL,
            hr_service="Timecard correction", contact_type="phone",
            short_description="Timecard corrected; PTO and parental-leave questions answered",
            description="recap", related_records=[c["correction_id"]], state="resolved",
            resolved_by="Savvy", verification_id=vid)
        assert case["number"] == "HR-2026-0917" and case["state"] == "resolved"
        assert case["sys_id"] and case["related_records"] == [c["correction_id"]]
        assert case["related_records_detail"][0]["status"] == "applied"

        # Replay assertion: exactly one audit row per call, tagged with its system, in order.
        events = systems.db.list_audit_events()
        assert [(e["system"], e["tool"]) for e in events] == [
            ("cvs_identity", "verify_colleague"), ("workday_hcm", "get_worker"),
            ("time_attendance", "get_timecard"), ("time_attendance", "submit_timecard_correction"),
            ("workday_hcm", "evaluate_pay_correction"), ("workday_hcm", "get_time_off_balance"),
            ("workday_hcm", "project_time_off"), ("servicenow_hrsd", "create_hr_case")]
        assert events[0]["args"] == {"colleague_id": "774-2318", "mobile": "", "attempt": 1}
        assert all(e["verification_id"] == vid for e in events)

    @pytest.mark.asyncio
    async def test_mobile_instead_of_id(self, systems):
        v = await systems.verify(colleague_id="", mobile="602-555-0148")
        assert v["verified"] is True and v["colleague_id"] == DANIEL and v["method"] == "mobile"

    @pytest.mark.asyncio
    async def test_case_numbers_are_sequential_and_reset(self, systems):
        vid = (await systems.verify())["verification_id"]
        numbers = [(await systems.call("servicenow_hrsd", "create_hr_case", hr_service="Callback request",
                                       verification_id=vid))["number"] for _ in range(2)]
        assert numbers == ["HR-2026-0917", "HR-2026-0918"]
        systems.db.reset()
        vid = (await systems.verify())["verification_id"]
        again = await systems.call("servicenow_hrsd", "create_hr_case", hr_service="General inquiry",
                                   verification_id=vid)
        assert again["number"] == "HR-2026-0917"


# ---------------------------------------------------------------------------
# Verification: attempts, escalation, locks, revocation
# ---------------------------------------------------------------------------

LOCKED_CALLS = [
    ("workday_hcm", "get_worker", {"worker_id": DANIEL}),
    ("workday_hcm", "get_time_off_balance", {"worker_id": DANIEL}),
    ("workday_hcm", "project_time_off", {"worker_id": DANIEL, "target_hours": 80}),
    ("workday_hcm", "evaluate_pay_correction", {"worker_id": DANIEL, "hours": 1.5}),
    ("time_attendance", "get_timecard", {"worker_id": DANIEL}),
    ("time_attendance", "submit_timecard_correction",
     {"worker_id": DANIEL, "period_end": DEMO["period_end"], "consent": True}),
    ("time_attendance", "cancel_timecard_correction", {"correction_id": "TC-000001"}),
    ("servicenow_hrsd", "create_hr_case", {"subject_person": DANIEL, "hr_service": "Timecard correction"}),
    ("servicenow_hrsd", "create_hr_case", {"hr_service": "General inquiry"}),
    ("servicenow_hrsd", "create_hr_case", {"hr_service": "Callback request"}),
    ("servicenow_hrsd", "add_work_note", {"number": "HR-2026-0788", "note": "x"}),
    ("servicenow_hrsd", "get_hr_cases", {"subject_person": DANIEL}),
]


class TestVerification:

    @pytest.mark.asyncio
    async def test_kevin_two_misses_escalate(self, systems):
        first = await systems.verify("332-9081", attempt=1)
        assert first["verified"] is False and first["escalate"] is False
        assert first["attempts"] == 1 and first["reason"] == "no_match"
        assert first["verification_id"] == "" and first["masked_input"] == "*****81"
        second = await systems.verify("3329019", attempt=2)
        assert (second["verified"], second["attempts"], second["escalate"]) == (False, 2, True)
        assert "after 2 attempts" in second["message"]

    @pytest.mark.asyncio
    async def test_partial_number_is_read_back_not_counted(self, systems):
        r = await systems.verify("774-231", attempt=2)
        assert r["verified"] is False and (r["outcome"], r["reason"]) == ("partial", "partial")
        assert r["counted"] is False and r["escalate"] is False
        assert r["heard_display"] == "774-231"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("said", [
        "Hold on while I find my identification 7 digits",
        "let me grab my badge",
        "uh, give me 10 seconds",
        "Un momento, déjeme buscar mi número",
        "",
    ])
    async def test_stalling_is_no_number_and_never_escalates(self, systems, said):
        r = await systems.verify(said, attempt=2)
        assert (r["verified"], r["outcome"], r["counted"]) == (False, "no_number", False)
        assert (r["escalate"], r["escalate_display"], r["heard_display"]) == (False, "no", "")

    @pytest.mark.asyncio
    async def test_spoken_start_of_id_is_partial(self, systems):
        r = await systems.verify("uh, seven seven four")
        assert (r["outcome"], r["heard_display"]) == ("partial", "774")

    @pytest.mark.asyncio
    async def test_outcomes_on_match_and_miss(self, systems):
        assert (await systems.verify())["outcome"] == "verified"
        miss = await systems.verify("3329081")
        assert (miss["outcome"], miss["counted"]) == ("no_match", True)

    @pytest.mark.asyncio
    async def test_attempt_is_coerced(self, hr):
        assert hr.verify_colleague("1", "", "abc")["attempts"] == 1
        assert hr.verify_colleague("1", "", 0)["attempts"] == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize("system, tool, args", LOCKED_CALLS)
    async def test_every_tool_refuses_when_unverified(self, systems, system, tool, args):
        r = await systems.call(system, tool, verification_id="", **args)
        assert r["error"] == "not_verified"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("system, tool, args", LOCKED_CALLS)
    async def test_every_tool_refuses_after_revoke(self, systems, system, tool, args):
        vid = (await systems.verify())["verification_id"]
        rv = await systems.call("cvs_identity", "revoke_verification", verification_id=vid)
        assert rv["revoked"] is True and rv["status"] == "revoked"
        r = await systems.call(system, tool, verification_id=vid, **args)
        assert r["error"] == "not_verified"

    @pytest.mark.asyncio
    async def test_verification_does_not_cover_another_worker(self, systems):
        vid = (await systems.verify())["verification_id"]
        r = await systems.call("workday_hcm", "get_worker", worker_id="5530912", verification_id=vid)
        assert r["error"] == "not_verified"
        r = await systems.call("servicenow_hrsd", "create_hr_case", subject_person="5530912",
                               hr_service="General inquiry", verification_id=vid)
        assert r["error"] == "not_verified"

    @pytest.mark.asyncio
    async def test_revoke_is_idempotent_and_unknown_is_refused(self, systems):
        vid = (await systems.verify())["verification_id"]
        await systems.call("cvs_identity", "revoke_verification", verification_id=vid)
        again = await systems.call("cvs_identity", "revoke_verification", verification_id=vid)
        assert again["already_revoked"] is True
        unknown = await systems.call("cvs_identity", "revoke_verification", verification_id="ver_nope")
        assert unknown["error"] == "not_verified"

    @pytest.mark.asyncio
    async def test_wrong_person_then_reverify(self, systems):
        # Transposed digits match Elena Ruiz, not Daniel.
        elena = await systems.verify("774-2381")
        assert elena["verified"] is True and elena["display_name"] == "Elena R."
        await systems.call("cvs_identity", "revoke_verification", verification_id=elena["verification_id"])
        blocked = await systems.call("workday_hcm", "get_worker", worker_id="7742381",
                                     verification_id=elena["verification_id"])
        assert blocked["error"] == "not_verified"
        daniel = await systems.verify("774-2318", attempt=1)
        assert daniel["first_name"] == "Daniel"
        tools = [e["tool"] for e in systems.db.list_audit_events("cvs_identity")]
        assert tools == ["verify_colleague", "revoke_verification", "verify_colleague"]


class TestUnverifiedIdentityCase:

    @pytest.mark.asyncio
    async def test_identity_verification_case_allowed_and_masked(self, systems):
        r = await systems.call(
            "servicenow_hrsd", "create_hr_case", hr_service="Identity verification",
            contact_type="phone", state="new", assignment_group="Colleague Service",
            short_description="Could not verify identity after 2 attempts",
            description="Tried IDs 332-9081 and 3329019; wants pay help",
            related_records=["TC-000001"])
        assert r["number"] == "HR-2026-0917" and r["verified"] is False
        assert r["subject_person"] == "" and r["state"] == "new"
        assert r["assignment_group"] == "Colleague Service" and r["related_records"] == []
        assert "332" not in r["description"] and "*****81" in r["description"]
        assert "*****19" in r["description"]

    @pytest.mark.asyncio
    async def test_identity_case_with_subject_person_refused(self, systems):
        r = await systems.call("servicenow_hrsd", "create_hr_case", hr_service="Identity verification",
                               subject_person="3329018")
        assert r["error"] == "not_verified"

    @pytest.mark.asyncio
    async def test_unverified_state_forced_new(self, systems):
        r = await systems.call("servicenow_hrsd", "create_hr_case", hr_service="identity verification",
                               state="resolved")
        assert r["state"] == "new" and r["hr_service"] == "Identity verification"


# ---------------------------------------------------------------------------
# Recovering from wrong information
# ---------------------------------------------------------------------------

class TestRecovery:

    @pytest_asyncio.fixture
    async def vid(self, systems):
        return (await systems.verify())["verification_id"]

    @pytest.mark.asyncio
    async def test_prior_week_is_clean(self, systems, vid):
        tc = await systems.call("time_attendance", "get_timecard", worker_id=DANIEL,
                                period_end=DEMO["prior_period_end"], verification_id=vid)
        assert tc["discrepancy"] is False and tc["hours_short"] == 0
        assert tc["amount_usd"] == 0 and tc["deduction_dates"] == []
        assert tc["is_latest_closed_period"] is False and tc["break_punched"] is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize("period_end, error", [
        ("2026-10-10", "period_not_closed"), ("2026-10-02", "invalid_period_end"),
        ("Oct 3", "invalid_period_end"), ("2026-09-19", "period_not_available")])
    async def test_bad_period_end(self, systems, vid, period_end, error):
        tc = await systems.call("time_attendance", "get_timecard", worker_id=DANIEL,
                                period_end=period_end, verification_id=vid)
        assert tc["error"] == error

    @pytest.mark.asyncio
    async def test_disputed_day_partial_correction(self, systems, vid):
        c = await systems.call("time_attendance", "submit_timecard_correction",
                               **correction_args(vid, dates=["2026-09-28", "2026-10-01"]))
        assert c["hours"] == 1.0 and c["amount_usd"] == 27.75
        assert c["amount_display_en"] == "$27.75"
        assert c["amount_display_es"] == "27 dólares con 75 centavos"
        assert c["dates_display_en"] == "Monday the 28th and Thursday, October 1st"
        assert c["remaining_hours_short"] == 0.5
        p = await systems.call("workday_hcm", "evaluate_pay_correction", worker_id=DANIEL,
                               hours=1.0, verification_id=vid)
        assert p["amount_usd"] == 27.75 and p["off_cycle"] is False

    @pytest.mark.asyncio
    async def test_exclude_dates_variant(self, systems, vid):
        c = await systems.call("time_attendance", "submit_timecard_correction",
                               **correction_args(vid, dates=None, exclude_dates=["2026-09-30"]))
        assert c["dates"] == ["2026-09-28", "2026-10-01"] and c["hours"] == 1.0

    @pytest.mark.asyncio
    async def test_list_args_as_strings(self, systems, vid):
        c = await systems.call("time_attendance", "submit_timecard_correction",
                               **correction_args(vid, dates='["2026-09-28","2026-09-30"]',
                                                 exclude_dates="2026-09-30"))
        assert c["dates"] == ["2026-09-28"] and c["hours"] == 0.5

    @pytest.mark.asyncio
    async def test_change_of_mind_cancel_restores_timecard(self, systems, vid):
        before = await systems.call("time_attendance", "get_timecard", worker_id=DANIEL, verification_id=vid)
        c = await systems.call("time_attendance", "submit_timecard_correction", **correction_args(vid))
        mid = await systems.call("time_attendance", "get_timecard", worker_id=DANIEL, verification_id=vid)
        assert mid["hours_short"] == 0 and mid["corrected_dates"] == DEMO["deduction_dates"]
        assert all(d["auto_deduct"] is None for d in mid["days"])
        x = await systems.call("time_attendance", "cancel_timecard_correction",
                               verification_id=vid, correction_id=c["correction_id"])
        assert x["status"] == "reversed" and x["restored_hours_short"] == 1.5
        after = await systems.call("time_attendance", "get_timecard", worker_id=DANIEL, verification_id=vid)
        strip = lambda t: {k: v for k, v in t.items() if k != "corrections"}  # noqa: E731
        assert strip(after) == strip(before)
        assert after["corrections"][0]["status"] == "reversed"
        rows = systems.db.list_audit_events("time_attendance")
        submit = [r for r in rows if r["tool"] == "submit_timecard_correction"][0]
        assert submit["status"] == "reversed"
        again = await systems.call("time_attendance", "cancel_timecard_correction",
                                   verification_id=vid, correction_id=c["correction_id"])
        assert again["error"] == "already_reversed"
        p = await systems.call("workday_hcm", "evaluate_pay_correction", worker_id=DANIEL,
                               hours=1.5, verification_id=vid)
        assert p["correction_id"] == ""

    @pytest.mark.asyncio
    async def test_cancel_unknown_correction(self, systems, vid):
        r = await systems.call("time_attendance", "cancel_timecard_correction",
                               verification_id=vid, correction_id="TC-999999")
        assert r["error"] == "correction_not_found"

    @pytest.mark.asyncio
    async def test_consent_required(self, systems, vid):
        r = await systems.call("time_attendance", "submit_timecard_correction",
                               **correction_args(vid, consent=False))
        assert r["error"] == "consent_required"
        assert systems.db.timecard_view(DANIEL, __import__("datetime").date(2026, 10, 3), vid)["hours_short"] == 1.5

    @pytest.mark.asyncio
    async def test_correction_validation(self, systems, vid):
        bad_type = await systems.call("time_attendance", "submit_timecard_correction",
                                      **correction_args(vid, remove_auto_deduct="rest"))
        assert bad_type["error"] == "invalid_deduction_type"
        bad_date = await systems.call("time_attendance", "submit_timecard_correction",
                                      **correction_args(vid, dates=["2026-09-29"]))
        assert bad_date["error"] == "invalid_dates"
        none_left = await systems.call("time_attendance", "submit_timecard_correction",
                                       **correction_args(vid, exclude_dates=DEMO["deduction_dates"]))
        assert none_left["error"] == "no_dates"
        bad_period = await systems.call("time_attendance", "submit_timecard_correction",
                                        **correction_args(vid, period_end="2026-10-10"))
        assert bad_period["error"] == "period_not_closed"
        await systems.call("time_attendance", "submit_timecard_correction", **correction_args(vid))
        dup = await systems.call("time_attendance", "submit_timecard_correction", **correction_args(vid))
        assert dup["error"] == "already_corrected"

    @pytest.mark.asyncio
    async def test_different_pto_targets(self, systems, vid):
        two_weeks = await systems.call("workday_hcm", "project_time_off", worker_id=DANIEL,
                                       target_hours=80, verification_id=vid)
        forty = await systems.call("workday_hcm", "project_time_off", worker_id=DANIEL,
                                   target_hours=40, verification_id=vid)
        assert two_weeks["periods_needed"] == 3
        assert forty["already_enough"] is True and forty["hours_needed"] == 0
        assert forty["target_pay_date"] == "" and forty["target_label_es"] == "ahora"
        bad = await systems.call("workday_hcm", "project_time_off", worker_id=DANIEL,
                                 target_hours=0, verification_id=vid)
        assert bad["error"] == "invalid_target"

    @pytest.mark.asyncio
    async def test_evaluate_rejects_bad_hours(self, systems, vid):
        r = await systems.call("workday_hcm", "evaluate_pay_correction", worker_id=DANIEL,
                               hours=0, verification_id=vid)
        assert r["error"] == "invalid_hours"


class TestDisplayFields:
    """String display fields the ABL templates read, at as-of 2026-10-08."""

    @pytest.mark.asyncio
    async def test_display_strings(self, systems):
        v = await systems.verify("seven seven four two three one eight")
        assert (v["verified"], v["verified_display"], v["escalate_display"]) == (True, "yes", "no")
        vid = v["verification_id"]
        w = await systems.call("workday_hcm", "get_worker", worker_id=DANIEL, verification_id=vid)
        assert (w["store_number"], w["store_city"], w["verified_display"]) == ("6218", "Phoenix", "yes")
        tc = await systems.call("time_attendance", "get_timecard", worker_id=DANIEL, verification_id=vid)
        assert tc["hours_short_display_en"] == "an hour and a half"
        assert tc["hours_short_display_es"] == "una hora y media"
        b = await systems.call("workday_hcm", "get_time_off_balance", worker_id=DANIEL, verification_id=vid)
        assert (b["balance_hours_display"], b["balance_days_display"], b["accrual_display"]) == \
            ("62.5", "7.8", "6.15")
        p = await systems.call("workday_hcm", "project_time_off", worker_id=DANIEL,
                               target_hours=80, verification_id=vid)
        assert (p["hours_needed_display_en"], p["hours_needed_display_es"]) == \
            ("17 and a half", "diecisiete y media")
        assert (p["periods_needed_display_en"], p["periods_needed_display_es"]) == ("three", "tres")
        assert p["target_hours_display"] == "80"
        e = await systems.call("workday_hcm", "evaluate_pay_correction", worker_id=DANIEL,
                               hours=1.5, verification_id=vid)
        assert e["off_cycle_display"] == "no"
        for result in (v, w, b, p, e):
            for key, value in result.items():
                if key.endswith(("_display", "_display_en", "_display_es")):
                    assert isinstance(value, str), key

    @pytest.mark.asyncio
    async def test_failed_verify_displays(self, systems):
        v = await systems.verify("3329019", attempt=2)
        assert (v["verified_display"], v["escalate_display"]) == ("no", "yes")

    @pytest.mark.asyncio
    async def test_marcus_off_cycle_display(self, systems):
        vid = (await systems.verify("8104467"))["verification_id"]
        e = await systems.call("workday_hcm", "evaluate_pay_correction", worker_id="8104467",
                               hours=5, verification_id=vid)
        assert e["off_cycle_display"] == "yes"

    @pytest.mark.asyncio
    async def test_dates_omitted_defaults_to_all_deduction_dates(self, systems):
        vid = (await systems.verify())["verification_id"]
        c = await systems.call("time_attendance", "submit_timecard_correction", worker_id=DANIEL,
                               period_end=DEMO["period_end"], consent=True, verification_id=vid)
        assert c["dates"] == DEMO["deduction_dates"] and c["hours"] == 1.5
        assert (c["hours_display_en"], c["hours_display_es"]) == ("an hour and a half", "una hora y media")


class TestSmsBody:

    async def _golden(self, systems, *, pto=True, projection=True, correct=True):
        vid = (await systems.verify())["verification_id"]
        cid = ""
        if correct:
            cid = (await systems.call("time_attendance", "submit_timecard_correction",
                                      **correction_args(vid)))["correction_id"]
        if pto:
            await systems.call("workday_hcm", "get_time_off_balance", worker_id=DANIEL, verification_id=vid)
        if projection:
            await systems.call("workday_hcm", "project_time_off", worker_id=DANIEL,
                               target_hours=80, verification_id=vid)
        return vid, cid

    @pytest.mark.asyncio
    async def test_english_golden(self, systems):
        vid, cid = await self._golden(systems)
        case = await systems.call("servicenow_hrsd", "create_hr_case", subject_person=DANIEL,
                                  hr_service="Timecard correction", related_records=[cid],
                                  state="resolved", leave_discussed="yes", verification_id=vid)
        assert case["sms_body"] == (
            "CVS Health Colleague Service — case HR-2026-0917. "
            "Timecard corrected: 1.5 h, $41.63 on your Friday, October 16th paycheck. "
            "PTO balance: 62.5 h (7.8 days). ~80 h by mid-November. "
            "Parental leave: up to 4 weeks at 100% base pay (Leave of Absence Guide).")
        assert len(case["sms_body"]) <= 320 and case["language"] == "en"
        assert DANIEL not in case["sms_body"] and "Reyes" not in case["sms_body"]
        assert case["description"].startswith("Timecard corrected: 1.5 h, $41.63")

    @pytest.mark.asyncio
    async def test_spanish_golden(self, systems):
        vid, _ = await self._golden(systems)
        case = await systems.call("servicenow_hrsd", "create_hr_case", hr_service="Timecard correction",
                                  leave_discussed="yes", language="es", description="given",
                                  verification_id=vid)
        assert case["sms_body"] == (
            "CVS Health Colleague Service — caso HR-2026-0917. "
            "Tarjeta de tiempo corregida: 1.5 h, $41.63 en su cheque del viernes 16 de octubre. "
            "Saldo de PTO: 62.5 h (7.8 días). ~80 h para mediados de noviembre. "
            "Licencia parental: hasta 4 semanas al 100% del salario base (Guía de Licencias).")
        assert len(case["sms_body"]) <= 320 and case["description"] == "given"

    @pytest.mark.asyncio
    async def test_only_what_happened(self, systems):
        vid, _ = await self._golden(systems, pto=False, projection=False, correct=False)
        case = await systems.call("servicenow_hrsd", "create_hr_case", hr_service="General inquiry",
                                  verification_id=vid)
        assert case["sms_body"] == "CVS Health Colleague Service — case HR-2026-0917."
        assert case["description"] == "Colleague call handled by Savvy."

    @pytest.mark.asyncio
    async def test_cancelled_correction_and_failed_reads_are_left_out(self, systems):
        vid, cid = await self._golden(systems, pto=False, projection=False)
        await systems.call("time_attendance", "cancel_timecard_correction", verification_id=vid,
                           correction_id=cid)
        await systems.call("workday_hcm", "project_time_off", worker_id=DANIEL, target_hours=0,
                           verification_id=vid)
        case = await systems.call("servicenow_hrsd", "create_hr_case", hr_service="Timecard correction",
                                  verification_id=vid)
        assert case["sms_body"] == "CVS Health Colleague Service — case HR-2026-0917."

    @pytest.mark.asyncio
    async def test_off_cycle_and_already_enough(self, systems):
        vid = (await systems.verify("8104467"))["verification_id"]
        await systems.call("time_attendance", "submit_timecard_correction", worker_id="8104467",
                           period_end=DEMO["period_end"], consent=True, verification_id=vid)
        await systems.call("workday_hcm", "project_time_off", worker_id="8104467",
                           target_hours=8, verification_id=vid)
        en = await systems.call("servicenow_hrsd", "create_hr_case", hr_service="Timecard correction",
                                verification_id=vid)
        assert "paid off-cycle on Tuesday, October 13th" in en["sms_body"] and "~" not in en["sms_body"]
        es = await systems.call("servicenow_hrsd", "create_hr_case", hr_service="Timecard correction",
                                language="es", verification_id=vid)
        assert "pago fuera de ciclo el martes 13 de octubre" in es["sms_body"]

    def test_sms_body_is_trimmed_to_320(self):
        from mcp_server_kit.cvs_hr_database import build_sms_body
        facts = {"correction": None, "balance": None, "projection": None, "leave": True}
        long_number = "HR-" + "9" * 250
        body = build_sms_body(long_number, facts, "en")
        assert "Parental leave" not in body

    @pytest.mark.asyncio
    async def test_identity_case_has_header_only(self, systems):
        r = await systems.call("servicenow_hrsd", "create_hr_case", hr_service="Identity verification",
                               leave_discussed="yes")
        assert r["sms_body"] == "CVS Health Colleague Service — case HR-2026-0917."
        assert r["description"] == "Colleague call handled by Savvy."


class TestOtherColleagues:

    @pytest.mark.asyncio
    async def test_marcus_off_cycle(self, systems):
        vid = (await systems.verify("8104467"))["verification_id"]
        tc = await systems.call("time_attendance", "get_timecard", worker_id="8104467", verification_id=vid)
        assert tc["hours_short"] == 5.0 and tc["week_hours_worked"] == 52.5
        assert tc["amount_usd"] == 165.00 and tc["amount_display_es"] == "165 dólares"
        c = await systems.call("time_attendance", "submit_timecard_correction", worker_id="8104467",
                               period_end=DEMO["period_end"], consent=True, verification_id=vid)
        assert c["hours"] == 5.0 and len(c["dates"]) == 5
        p = await systems.call("workday_hcm", "evaluate_pay_correction", worker_id="8104467",
                               hours=5.0, verification_id=vid)
        assert p["off_cycle"] is True and p["pay_date"] == "2026-10-13"

    @pytest.mark.asyncio
    async def test_priya_already_has_enough(self, systems):
        vid = (await systems.verify("6610425"))["verification_id"]
        p = await systems.call("workday_hcm", "project_time_off", worker_id="6610425",
                               target_hours=80, verification_id=vid)
        assert p["already_enough"] is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cid, first, lang", [
        ("5530912", "Ana", "es"), ("3329018", "Kevin", "en"), ("9017734", "Jordan", "en"),
        ("7742381", "Elena", "en")])
    async def test_seeded_colleagues_have_clean_timecards(self, systems, cid, first, lang):
        v = await systems.verify(cid)
        w = await systems.call("workday_hcm", "get_worker", worker_id=cid,
                               verification_id=v["verification_id"])
        assert w["first_name"] == first and w["preferred_language"] == lang
        tc = await systems.call("time_attendance", "get_timecard", worker_id=cid,
                                verification_id=v["verification_id"])
        assert tc["discrepancy"] is False and tc["week_hours_worked"] == 40.0


# ---------------------------------------------------------------------------
# The colleague profile returned at authentication
# ---------------------------------------------------------------------------

class TestColleagueProfile:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cal", [DEMO, RECORDING], ids=["demo-2026-10-08", "recording-2026-09-01"])
    async def test_daniel_profile_matches_the_lookup_tools(self, systems, monkeypatch, cal):
        monkeypatch.setenv("CVS_HR_AS_OF", cal["as_of"])
        systems.db.reset()
        v = await systems.verify("774-2318")
        assert v["profile_loaded"] == "yes"
        assert (v["job_title"], v["store_number"], v["store_city"]) == (
            "Pharmacy Technician", "6218", "Phoenix")
        assert (v["base_rate_usd"], v["ot_rate_usd"]) == (18.50, 27.75)
        assert v["period_end"] == cal["period_end"]
        assert v["period_end_display_en"] == cal["period_end_display_en"]
        assert v["period_end_display_es"] == cal["period_end_display_es"]
        assert v["deduction_days_display_en"] == cal["deduction_days_display_en"]
        assert v["deduction_days_display_es"] == cal["deduction_days_display_es"]
        assert v["timecard_discrepancy"] == "yes" and v["hours_short"] == 1.5
        assert v["amount_display_en"] == "$41.63"
        assert (v["pto_balance_hours"], v["pto_balance_days"], v["accrual_hours"]) == (
            "62.5", "7.8", "6.15")
        assert v["p80_target_hours_display"] == "80"
        assert v["p80_periods_needed_display_en"] == "three"
        assert v["p80_target_label_en"] == cal["target_label_en"]
        assert v["p80_target_label_es"] == cal["target_label_es"]
        assert v["p40_target_label_en"] == "now" and v["p40_target_label_es"] == "ahora"
        assert v["p120_target_hours_display"] == "120"
        assert v["open_case_count"] == 0 and v["open_case_numbers"] == ""

        # The profile is the same data the lookup tools return.
        vid = v["verification_id"]
        tc = await systems.call("time_attendance", "get_timecard", worker_id=DANIEL,
                                verification_id=vid)
        p = await systems.call("workday_hcm", "project_time_off", worker_id=DANIEL,
                               target_hours=80, verification_id=vid)
        assert v["hours_short_display_en"] == tc["hours_short_display_en"]
        assert v["amount_display_es"] == tc["amount_display_es"]
        assert v["p80_hours_needed_display_en"] == p["hours_needed_display_en"]
        assert v["p80_hours_needed_display_es"] == p["hours_needed_display_es"]

    @pytest.mark.asyncio
    async def test_profile_costs_one_audit_row(self, systems):
        systems.db.reset()
        await systems.verify(DANIEL)
        events = systems.db.list_audit_events()
        assert [e["tool"] for e in events] == ["verify_colleague"]
        assert events[0]["result"]["job_title"] == "Pharmacy Technician"

    @pytest.mark.asyncio
    async def test_clean_timecard_profile(self, systems):
        v = await systems.verify("5530912")
        assert v["timecard_discrepancy"] == "no" and v["hours_short"] == 0

    @pytest.mark.asyncio
    async def test_open_cases_are_listed(self, systems, hr):
        first = hr.verify_colleague(DANIEL)
        case = hr.create_hr_case(first["verification_id"], subject_person=DANIEL,
                                 hr_service="Callback request", state="new")
        profile = hr.colleague_profile(first["verification_id"], DANIEL)
        assert profile["open_case_count"] == 1
        assert profile["open_case_numbers"] == case["number"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("said, attempt", [("3329019", 1), ("774-231", 1), ("", 1)])
    async def test_no_profile_without_a_match(self, systems, said, attempt):
        r = await systems.verify(said, attempt=attempt)
        assert r["verified"] is False
        assert "profile_loaded" not in r and "job_title" not in r and "amount_display_en" not in r


# ---------------------------------------------------------------------------
# Sandboxes, ServiceNow, SMS switch, seeding
# ---------------------------------------------------------------------------

class TestSandboxIsolation:

    @pytest.mark.asyncio
    async def test_two_calls_do_not_see_each_other(self, systems):
        a = (await systems.verify())["verification_id"]
        b = (await systems.verify())["verification_id"]
        assert a != b
        c = await systems.call("time_attendance", "submit_timecard_correction", **correction_args(a))
        tc_b = await systems.call("time_attendance", "get_timecard", worker_id=DANIEL, verification_id=b)
        assert tc_b["hours_short"] == 1.5 and tc_b["corrections"] == []
        # b can correct independently, and cannot cancel a's correction.
        assert (await systems.call("time_attendance", "submit_timecard_correction",
                                   **correction_args(b)))["status"] == "applied"
        x = await systems.call("time_attendance", "cancel_timecard_correction",
                               verification_id=b, correction_id=c["correction_id"])
        assert x["error"] == "correction_not_found"
        case_a = await systems.call("servicenow_hrsd", "create_hr_case", hr_service="Timecard correction",
                                    verification_id=a)
        cases_b = await systems.call("servicenow_hrsd", "get_hr_cases", subject_person=DANIEL,
                                     verification_id=b)
        assert case_a["number"] not in [k["number"] for k in cases_b["cases"]]
        note = await systems.call("servicenow_hrsd", "add_work_note", number=case_a["number"],
                                  note="x", verification_id=b)
        assert note["error"] == "case_not_found"


class TestServiceNow:

    @pytest_asyncio.fixture
    async def vid(self, systems):
        return (await systems.verify())["verification_id"]

    @pytest.mark.asyncio
    async def test_cases_and_work_notes(self, systems, vid):
        case = await systems.call("servicenow_hrsd", "create_hr_case", hr_service="Callback request",
                                  related_records="TC-424242", verification_id=vid)
        assert case["state"] == "new" and case["assignment_group"] == "Colleague Service"
        assert case["subject_person"] == DANIEL and case["resolved_at"] == ""
        assert case["related_records_detail"] == [{"id": "TC-424242", "table": "unknown",
                                                   "status": "not_found"}]
        n = await systems.call("servicenow_hrsd", "add_work_note", number=case["number"].lower(),
                               note="Caller prefers mornings", verification_id=vid)
        assert n["work_notes_count"] == 1 and n["last_note"] == "Caller prefers mornings"
        seeded = await systems.call("servicenow_hrsd", "add_work_note", number="HR-2026-0788",
                                    note="seen", verification_id=vid)
        assert seeded["work_notes_count"] == 1
        empty = await systems.call("servicenow_hrsd", "add_work_note", number=case["number"],
                                   note=" ", verification_id=vid)
        assert empty["error"] == "invalid_note"
        all_cases = await systems.call("servicenow_hrsd", "get_hr_cases", subject_person=DANIEL,
                                       verification_id=vid)
        assert all_cases["count"] == 2
        open_cases = await systems.call("servicenow_hrsd", "get_hr_cases", subject_person=DANIEL,
                                        state="open", verification_id=vid)
        assert [c["number"] for c in open_cases["cases"]] == [case["number"]]
        closed = await systems.call("servicenow_hrsd", "get_hr_cases", subject_person=DANIEL,
                                    state="closed_complete", verification_id=vid)
        assert [c["number"] for c in closed["cases"]] == ["HR-2026-0788"]

    @pytest.mark.asyncio
    async def test_validation(self, systems, vid):
        r = await systems.call("servicenow_hrsd", "create_hr_case", hr_service="", verification_id=vid)
        assert r["error"] == "invalid_hr_service"
        r = await systems.call("servicenow_hrsd", "create_hr_case", hr_service="General inquiry",
                               state="bogus", verification_id=vid)
        assert r["error"] == "invalid_state"


class TestSmsSwitch:

    @pytest.mark.asyncio
    async def test_disabled_by_default(self, systems, monkeypatch):
        monkeypatch.setenv("CVS_HR_DEMO_SMS_TO", "555-010-0000")
        v = await systems.verify()
        assert v["sms_to"] == "" and v["sms_suppressed"] is True
        assert v["sms_suppressed_reason"] == "disabled"

    @pytest.mark.asyncio
    async def test_enabled_returns_env_number_masked_in_audit(self, systems, monkeypatch):
        monkeypatch.setenv("CVS_HR_DEMO_SMS_TO", "555-010-0000")
        systems.db.update_settings(True)
        v = await systems.verify()
        assert v["sms_to"] == "+15550100000" and v["sms_suppressed"] is False
        logged = systems.db.list_audit_events("cvs_identity")[-1]["result"]
        assert logged["sms_to"] == "*********00"

    @pytest.mark.asyncio
    async def test_enabled_without_number(self, systems):
        systems.db.update_settings(True)
        v = await systems.verify()
        assert v["sms_to"] == "" and v["sms_suppressed_reason"] == "no_number"

    def test_settings_survive_reset(self, hr):
        hr.update_settings(True)
        hr.reset()
        assert hr.get_settings() == {"sms_enabled": True}


class TestSeedingAndHelpers:

    def test_reseeds_when_period_changes(self, hr, monkeypatch):
        vid = hr.verify_colleague(DANIEL)["verification_id"]
        assert hr.get_timecard(vid, DANIEL)["period_end"] == "2026-10-03"
        monkeypatch.setenv("CVS_HR_AS_OF", "2026-10-12")
        hr.ensure_current()
        tc = hr.get_timecard(vid, DANIEL)
        assert tc["period_end"] == "2026-10-10" and tc["hours_short"] == 1.5

    def test_init_is_idempotent(self, paths):
        a = open_database(paths["cvs_hr_db_path"])
        vid = a.verify_colleague(DANIEL)["verification_id"]
        b = open_database(paths["cvs_hr_db_path"])
        assert b.check_verification(vid)[0] is not None

    def test_non_numeric_hours_and_targets_are_rejected(self, hr):
        vid = hr.verify_colleague(DANIEL)["verification_id"]
        assert hr.project_time_off(vid, DANIEL, "ten days")["error"] == "invalid_target"
        assert hr.evaluate_pay_correction(vid, DANIEL, None)["error"] == "invalid_hours"

    def test_reset_payload(self, hr):
        r = hr.reset()
        assert r == {"status": "reset", "as_of": "2026-10-08", "period_end": "2026-10-03",
                     "next_case_number": "HR-2026-0917"}

    def test_audit_filters(self, hr):
        hr.audited("cvs_identity", "verify_colleague", {"colleague_id": DANIEL},
                   lambda: hr.verify_colleague(DANIEL))
        hr.audited("workday_hcm", "get_worker", {"worker_id": DANIEL, "verification_id": ""},
                   lambda: hr.get_worker("", DANIEL))
        assert len(hr.list_audit_events()) == 2
        assert hr.list_audit_events("workday_hcm")[0]["status"] == "error"
        assert hr.list_audit_events(limit=1)[0]["tool"] == "verify_colleague"

    def test_default_db_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CVS_HR_DB_PATH", str(tmp_path / "env.db"))
        db = open_database()
        assert db.db_path == str(tmp_path / "env.db")

    def test_db_errors_roll_back(self, hr):
        with pytest.raises(Exception):
            with hr._conn() as conn:
                conn.execute("INSERT INTO meta VALUES ('x', '1')")
                conn.execute("SELECT * FROM no_such_table")
        with hr._conn() as conn:
            assert conn.execute("SELECT * FROM meta WHERE key='x'").fetchone() is None

    @pytest.mark.parametrize("value, expected", [
        (None, []), (["a", " ", "b"], ["a", "b"]), ("", []), ('["a","b"]', ["a", "b"]),
        ("a, b", ["a", "b"]), ("[a, 'b']", ["a", "b"]), ("[not json", ["not json"])])
    def test_coerce_list(self, value, expected):
        assert coerce_list(value) == expected

    def test_coerce_bool(self):
        assert coerce_bool(True) and coerce_bool("yes") and not coerce_bool("no")

    @pytest.mark.parametrize("raw, expected", [
        ("", ""), ("+1 555 010 0000", "+15550100000"), ("5550100000", "+15550100000"),
        ("15550100000", "+15550100000"), ("12345", "12345")])
    def test_normalize_e164(self, raw, expected):
        assert normalize_e164(raw) == expected


class TestServerTools:

    @pytest.mark.asyncio
    async def test_tool_names(self, systems):
        expected = {
            "cvs_identity": {"verify_colleague", "revoke_verification"},
            "workday_hcm": {"get_worker", "get_time_off_balance", "project_time_off",
                            "evaluate_pay_correction"},
            "time_attendance": {"get_timecard", "submit_timecard_correction",
                                "cancel_timecard_correction"},
            "servicenow_hrsd": {"create_hr_case", "add_work_note", "get_hr_cases"},
        }
        for system, names in expected.items():
            async with Client(systems.servers[system].mcp) as client:
                assert {t.name for t in await client.list_tools()} == names

    def test_lazy_module_instances(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        import mcp_server_kit.cvs_identity as m1
        import mcp_server_kit.servicenow_hrsd as m4
        import mcp_server_kit.time_attendance as m3
        import mcp_server_kit.workday_hcm as m2
        for module in (m1, m2, m3, m4):
            assert module.server.mcp is module.mcp
