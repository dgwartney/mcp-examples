"""
Unit tests for mcp_server_kit.pto

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import os
import tempfile

import pytest
from fastmcp.exceptions import ToolError

from mcp_server_kit.database import DatabaseManager
from mcp_server_kit.pto import PtoMCPServer
from mcp_server_kit.pto_database import PtoDatabaseManager


def _tool_fn(server, name):
    """Extract the raw callable from a registered FastMCP tool."""
    return server.mcp._tool_manager._tools[name].fn


@pytest.fixture
def temp_db_path():
    """Create a temporary database file path for API keys."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def temp_pto_db_path():
    """Create a temporary database file path for PTO records."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def server(temp_db_path, temp_pto_db_path):
    """Create a PtoMCPServer instance with temp databases."""
    return PtoMCPServer(db_path=temp_db_path, pto_db_path=temp_pto_db_path)


class TestPtoMCPServer:
    """Test suite for PtoMCPServer class."""

    def test_four_tools_registered(self, server):
        assert len(server.mcp._tool_manager._tools) == 4

    def test_tool_names(self, server):
        tool_names = set(server.mcp._tool_manager._tools)
        assert tool_names == {
            "get_balance",
            "get_balance_by_email",
            "request_pto",
            "list_requests",
        }

    def test_server_has_pto_db(self, server):
        assert isinstance(server.pto_db, PtoDatabaseManager)

    def test_db_manager_created(self, server):
        assert isinstance(server.db_manager, DatabaseManager)

    def test_module_level_server_instance(self):
        import mcp_server_kit.pto as pto_module
        assert isinstance(pto_module.server, PtoMCPServer)

    def test_module_level_mcp_instance(self):
        import mcp_server_kit.pto as pto_module
        assert pto_module.mcp is pto_module.server.mcp


class TestPtoMCPServerToolFunctions:
    """Tests that invoke the registered tool closures directly."""

    def test_get_balance_returns_seed_employee(self, server):
        result = _tool_fn(server, "get_balance")(employee_id="E1001")
        assert result["full_name"] == "Asha Rao"
        assert result["location"] == "India"
        assert result["pto_balance_days"] == 18.0

    def test_get_balance_unknown_employee_raises(self, server):
        with pytest.raises(ToolError, match="No employee found"):
            _tool_fn(server, "get_balance")(employee_id="does-not-exist")

    def test_get_balance_by_email(self, server):
        result = _tool_fn(server, "get_balance_by_email")(
            email="jordan.blake@example.com"
        )
        assert result["employee_id"] == "E2001"
        assert result["location"] == "USA"

    def test_get_balance_by_email_unknown_raises(self, server):
        with pytest.raises(ToolError, match="No employee found"):
            _tool_fn(server, "get_balance_by_email")(email="nobody@example.com")

    def test_request_pto_approved_deducts_balance(self, server):
        result = _tool_fn(server, "request_pto")(
            employee_id="E1001",
            start_date="2026-08-01",
            end_date="2026-08-03",
            days=3,
        )
        assert result["status"] == "approved"
        assert result["remaining_balance_days"] == 15.0

        balance = _tool_fn(server, "get_balance")(employee_id="E1001")
        assert balance["pto_balance_days"] == 15.0

    def test_request_pto_denied_insufficient_balance(self, server):
        result = _tool_fn(server, "request_pto")(
            employee_id="E2001",
            start_date="2026-09-01",
            end_date="2026-09-20",
            days=100,
        )
        assert result["status"] == "denied_insufficient_balance"
        assert result["remaining_balance_days"] == 9.0

    def test_request_pto_unknown_employee_raises(self, server):
        with pytest.raises(ToolError, match="No employee found"):
            _tool_fn(server, "request_pto")(
                employee_id="does-not-exist",
                start_date="2026-08-01",
                end_date="2026-08-02",
                days=1,
            )

    def test_list_requests_returns_filed_requests(self, server):
        _tool_fn(server, "request_pto")(
            employee_id="E1002",
            start_date="2026-10-01",
            end_date="2026-10-02",
            days=2,
        )
        results = _tool_fn(server, "list_requests")(employee_id="E1002")
        assert len(results) == 1
        assert results[0]["EmployeeId"] == "E1002"
