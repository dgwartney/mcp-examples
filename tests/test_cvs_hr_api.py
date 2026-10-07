"""
Tests for the CVS HR admin REST API (mcp_server_kit.cvs_hr_api).

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import pytest
from starlette.testclient import TestClient

from mcp_server_kit.cvs_hr_api import build_cvs_hr_app
from mcp_server_kit.database import DatabaseManager

DANIEL = "7742318"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("CVS_HR_AS_OF", "2026-10-08")
    monkeypatch.delenv("CVS_HR_DEMO_SMS_TO", raising=False)


@pytest.fixture
def api(tmp_path):
    key_db_path = str(tmp_path / "keys.db")
    key = DatabaseManager(key_db_path).init_db()
    app = build_cvs_hr_app(str(tmp_path / "cvs_hr.db"), key_db_path)
    client = TestClient(app)
    client.headers["X-API-Key"] = key
    client.hr_db = app.state.hr_db
    return client


def golden_call(hr_db) -> str:
    """Run the backend side of Daniel's golden call; returns the verification_id."""
    v = hr_db.audited("cvs_identity", "verify_colleague", {"colleague_id": DANIEL},
                      lambda: hr_db.verify_colleague(DANIEL))
    vid = v["verification_id"]
    hr_db.audited("workday_hcm", "get_worker", {"worker_id": DANIEL, "verification_id": vid},
                  lambda: hr_db.get_worker(vid, DANIEL))
    c = hr_db.audited("time_attendance", "submit_timecard_correction", {"verification_id": vid},
                      lambda: hr_db.submit_timecard_correction(vid, DANIEL, "2026-10-03", consent=True))
    hr_db.audited("servicenow_hrsd", "create_hr_case", {"verification_id": vid},
                  lambda: hr_db.create_hr_case(vid, DANIEL, "Timecard correction",
                                               related_records=[c["correction_id"]], state="resolved"))
    return vid


class TestAuth:

    def test_health_needs_no_key(self, api):
        del api.headers["X-API-Key"]
        resp = api.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "service": "cvs_hr", "as_of": "2026-10-08",
                               "period_end": "2026-10-03"}

    @pytest.mark.parametrize("method, path", [
        ("post", "/reset"), ("get", "/audit_events"), ("get", "/systems"),
        ("get", "/settings"), ("post", "/settings")])
    def test_everything_else_is_401_without_key(self, api, method, path):
        del api.headers["X-API-Key"]
        assert getattr(api, method)(path).status_code == 401

    def test_wrong_key_is_401(self, api):
        api.headers["X-API-Key"] = "wrong"
        assert api.post("/reset").status_code == 401


class TestReset:

    def test_reset_clears_everything_and_restarts_case_numbers(self, api):
        golden_call(api.hr_db)
        resp = api.post("/reset")
        assert resp.status_code == 200
        assert resp.json()["next_case_number"] == "HR-2026-0917"
        assert api.get("/audit_events").json() == {"count": 0, "events": []}
        assert api.get("/systems").json()["verification"] is None


class TestAuditEvents:

    def test_filters(self, api):
        vid = golden_call(api.hr_db)
        golden_call(api.hr_db)
        assert api.get("/audit_events").json()["count"] == 8
        body = api.get("/audit_events", params={"system": "time_attendance"}).json()
        assert body["count"] == 2 and {e["system"] for e in body["events"]} == {"time_attendance"}
        mine = api.get("/audit_events", params={"verification_id": vid}).json()
        assert [e["tool"] for e in mine["events"]] == [
            "verify_colleague", "get_worker", "submit_timecard_correction", "create_hr_case"]
        assert api.get("/audit_events", params={"limit": 1}).json()["count"] == 1

    def test_bad_params(self, api):
        assert api.get("/audit_events", params={"system": "payroll"}).status_code == 400
        assert api.get("/audit_events", params={"limit": "x"}).status_code == 400


class TestSystems:

    def test_empty(self, api):
        body = api.get("/systems").json()
        assert body["verification"] is None and body["unverified_cases"] == []
        assert body["as_of"] == "2026-10-08"

    def test_what_changed_latest_and_by_id(self, api):
        first = golden_call(api.hr_db)
        second = api.hr_db.verify_colleague("5530912")["verification_id"]
        latest = api.get("/systems").json()
        assert latest["verification"]["verification_id"] == second
        assert latest["servicenow_hrsd"]["cases"] == []
        body = api.get("/systems", params={"verification_id": first}).json()
        tc = body["time_attendance"]["timecard"]
        assert tc["hours_short"] == 0 and tc["corrected_dates"] == [
            "2026-09-28", "2026-09-30", "2026-10-01"]
        assert body["time_attendance"]["corrections"][0]["status"] == "applied"
        assert body["workday_hcm"]["payroll_written"] is False
        assert [r["tool"] for r in body["workday_hcm"]["reads"]] == ["get_worker"]
        case = body["servicenow_hrsd"]["cases"][0]
        assert case["number"] == "HR-2026-0917" and case["state"] == "resolved"

    def test_unverified_cases_listed(self, api):
        api.hr_db.create_hr_case("", "", "Identity verification", description="tried 3329081")
        body = api.get("/systems").json()
        assert body["unverified_cases"][0]["description"] == "tried *****81"

    def test_unknown_verification_404(self, api):
        assert api.get("/systems", params={"verification_id": "ver_nope"}).status_code == 404


class TestSettings:

    def test_default_off_then_toggle(self, api):
        assert api.get("/settings").json() == {"sms_enabled": False}
        assert api.post("/settings", json={"sms_enabled": True}).json() == {"sms_enabled": True}
        assert api.get("/settings").json() == {"sms_enabled": True}
        assert api.hr_db.verify_colleague(DANIEL)["sms_suppressed_reason"] == "no_number"
        api.post("/settings", json={"sms_enabled": False})
        v = api.hr_db.verify_colleague(DANIEL)
        assert v["sms_to"] == "" and v["sms_suppressed"] is True

    @pytest.mark.parametrize("payload", [{"sms_enabled": "yes"}, {}, [True]])
    def test_validation(self, api, payload):
        assert api.post("/settings", json=payload).status_code == 400

    def test_not_json(self, api):
        assert api.post("/settings", content=b"nope").status_code == 400
