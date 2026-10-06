"""
Unit tests for the Acme Support backend: database, REST API, MCP server.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

from datetime import date

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from starlette.testclient import TestClient

from mcp_server_kit.acme import AcmeMCPServer
from mcp_server_kit.acme_api import build_acme_app
from mcp_server_kit.acme_database import AcmeDatabaseManager
from mcp_server_kit.database import DatabaseManager

TODAY = date(2026, 10, 12)


@pytest.fixture
def acme_db(tmp_path):
    db = AcmeDatabaseManager(str(tmp_path / "acme.db"))
    db.init_db()
    return db


@pytest.fixture
def api(tmp_path):
    key_db_path = str(tmp_path / "keys.db")
    key = DatabaseManager(key_db_path).init_db()
    app = build_acme_app(str(tmp_path / "acme.db"), key_db_path, slow_seconds=0.01)
    client = TestClient(app)
    client.headers["X-API-Key"] = key
    return client


class TestAcmeDatabase:

    def test_seeds_six_orders_once(self, acme_db):
        acme_db.seed_orders()
        assert len(acme_db.list_orders_by_email("maria.lopez@example.com")) == 2
        assert len(acme_db.list_orders_by_email("james.chen@example.com")) == 2
        assert len(acme_db.list_orders_by_email("aisha.patel@example.com")) == 2

    def test_get_order_is_case_insensitive(self, acme_db):
        assert acme_db.get_order("acm-1002")["status"] == "shipped"

    def test_get_order_missing_returns_none(self, acme_db):
        assert acme_db.get_order("ACM-0000") is None

    def test_delivered_inside_window_is_eligible(self, acme_db):
        order = acme_db.get_order("ACM-1004", today=TODAY)
        assert order["return_eligible"] is True
        assert order["return_deadline"] == "2026-10-25"

    def test_delivered_outside_window_is_not_eligible(self, acme_db):
        order = acme_db.get_order("ACM-1005", today=TODAY)
        assert order["return_eligible"] is False
        assert order["return_deadline"] == "2026-09-01"

    def test_undelivered_is_not_eligible(self, acme_db):
        order = acme_db.get_order("ACM-1002", today=TODAY)
        assert order["return_eligible"] is False
        assert order["return_deadline"] is None

    def test_create_return_success(self, acme_db):
        result = acme_db.create_return("ACM-1004", "Dead pixels", today=TODAY)
        assert result["ok"] is True
        assert result["return"]["return_id"] == "RET-1"
        assert acme_db.get_return("ret-1")["reason"] == "Dead pixels"

    def test_create_return_rejects_window_closed(self, acme_db):
        result = acme_db.create_return("ACM-1005", "Too big", today=TODAY)
        assert result == {"ok": False, "error": "not_eligible",
                          "message": "The return window for order ACM-1005 closed on 2026-09-01."}

    def test_create_return_rejects_missing_order(self, acme_db):
        assert acme_db.create_return("ACM-0000", "x", today=TODAY)["error"] == "order_not_found"

    def test_ticket_round_trip(self, acme_db):
        t = acme_db.create_ticket("a@example.com", "Help", "Box damaged", "urgent")
        assert t["ticket_id"] == "TKT-1"
        assert acme_db.get_ticket("TKT-1")["priority"] == "urgent"

    def test_ticket_invalid_priority_defaults_to_normal(self, acme_db):
        assert acme_db.create_ticket("a@example.com", "s", "d", "panic")["priority"] == "normal"

    def test_malformed_ids_return_none(self, acme_db):
        assert acme_db.get_return("RET-abc") is None
        assert acme_db.get_ticket("nope") is None


class TestAcmeRestApi:

    def test_health_needs_no_key(self, api):
        del api.headers["X-API-Key"]
        resp = api.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "service": "acme"}

    def test_missing_key_is_401(self, api):
        del api.headers["X-API-Key"]
        assert api.get("/orders/ACM-1002").status_code == 401

    def test_get_order(self, api):
        resp = api.get("/orders/ACM-1002")
        assert resp.status_code == 200
        assert resp.json()["carrier"] == "UPS"

    def test_get_order_404(self, api):
        resp = api.get("/orders/ACM-0000")
        assert resp.status_code == 404
        assert resp.json()["error"] == "order_not_found"

    def test_list_orders_requires_email(self, api):
        assert api.get("/orders").status_code == 400

    def test_list_orders_by_email(self, api):
        body = api.get("/orders", params={"email": "JAMES.CHEN@example.com"}).json()
        assert body["count"] == 2

    def test_create_return_validation(self, api):
        assert api.post("/returns", json={"order_id": "ACM-1004"}).status_code == 400
        assert api.post("/returns", content=b"not json").status_code == 400

    def test_create_return_not_eligible_is_409(self, api):
        resp = api.post("/returns", json={"order_id": "ACM-1002", "reason": "x"})
        assert resp.status_code == 409

    def test_create_return_missing_order_is_404(self, api):
        resp = api.post("/returns", json={"order_id": "ACM-0000", "reason": "x"})
        assert resp.status_code == 404

    def test_ticket_round_trip(self, api):
        resp = api.post("/tickets", json={"customer_email": "a@example.com",
                                          "subject": "Help", "description": "Late"})
        assert resp.status_code == 201
        tid = resp.json()["ticket_id"]
        assert api.get(f"/tickets/{tid}").json()["subject"] == "Help"
        assert api.get("/tickets/TKT-999").status_code == 404

    def test_get_return_404(self, api):
        assert api.get("/returns/RET-999").status_code == 404

    def test_simulated_down_order_is_503(self, api):
        assert api.get("/orders/ACM-1098").status_code == 503

    def test_simulated_slow_order_eventually_404s(self, api):
        assert api.get("/orders/ACM-1099").status_code == 404

    def test_simulated_flaky_order_fails_twice_then_succeeds(self, api):
        codes = [api.get("/orders/ACM-1097").status_code for _ in range(3)]
        assert codes == [503, 503, 200]
        assert api.get("/orders/ACM-1097").status_code == 503  # cycle restarts


class TestAcmeMCPServer:

    @pytest.fixture
    def server(self, tmp_path):
        return AcmeMCPServer(db_path=str(tmp_path / "keys.db"),
                             acme_db_path=str(tmp_path / "acme.db"))

    @pytest.mark.asyncio
    async def test_lists_six_tools(self, server):
        async with Client(server.mcp) as client:
            names = {t.name for t in await client.list_tools()}
        assert names == {"get_order", "list_orders", "create_return",
                         "get_return", "create_ticket", "get_ticket"}

    @pytest.mark.asyncio
    async def test_get_order(self, server):
        async with Client(server.mcp) as client:
            result = await client.call_tool("get_order", {"order_id": "ACM-1003"})
        assert result.data["status"] == "out_for_delivery"

    @pytest.mark.asyncio
    async def test_get_order_missing_raises(self, server):
        async with Client(server.mcp) as client:
            with pytest.raises(ToolError):
                await client.call_tool("get_order", {"order_id": "ACM-0000"})

    @pytest.mark.asyncio
    async def test_create_return_not_eligible_raises(self, server):
        async with Client(server.mcp) as client:
            with pytest.raises(ToolError, match="only delivered orders"):
                await client.call_tool("create_return", {"order_id": "ACM-1001", "reason": "x"})

    @pytest.mark.asyncio
    async def test_ticket_round_trip(self, server):
        async with Client(server.mcp) as client:
            t = await client.call_tool("create_ticket", {"customer_email": "a@example.com",
                                                         "subject": "s", "description": "d"})
            got = await client.call_tool("get_ticket", {"ticket_id": t.data["ticket_id"]})
        assert got.data["status"] == "open"
