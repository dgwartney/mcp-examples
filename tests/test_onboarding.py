"""
Unit tests for mcp_server_kit.onboarding

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import os
import tempfile

import pytest
from fastmcp.exceptions import ToolError

from mcp_server_kit.database import DatabaseManager
from mcp_server_kit.onboarding import OnboardingMCPServer
from mcp_server_kit.onboarding_database import OnboardingDatabaseManager


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
def temp_onboarding_db_path():
    """Create a temporary database file path for onboarding cases."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def server(temp_db_path, temp_onboarding_db_path):
    """Create an OnboardingMCPServer instance with temp databases."""
    return OnboardingMCPServer(
        db_path=temp_db_path, onboarding_db_path=temp_onboarding_db_path
    )


class TestOnboardingMCPServer:
    """Test suite for OnboardingMCPServer class."""

    def test_four_tools_registered(self, server):
        assert len(server.mcp._tool_manager._tools) == 4

    def test_tool_names(self, server):
        tool_names = set(server.mcp._tool_manager._tools)
        assert tool_names == {
            "create_case",
            "get_case",
            "update_case_status",
            "list_cases",
        }

    def test_server_has_onboarding_db(self, server):
        assert isinstance(server.onboarding_db, OnboardingDatabaseManager)

    def test_db_manager_created(self, server):
        assert isinstance(server.db_manager, DatabaseManager)

    def test_module_level_server_instance(self):
        import mcp_server_kit.onboarding as onboarding_module
        assert isinstance(onboarding_module.server, OnboardingMCPServer)

    def test_module_level_mcp_instance(self):
        import mcp_server_kit.onboarding as onboarding_module
        assert onboarding_module.mcp is onboarding_module.server.mcp


class TestOnboardingMCPServerToolFunctions:
    """Tests that invoke the registered tool closures directly."""

    def test_create_case_returns_submitted_case(self, server):
        result = _tool_fn(server, "create_case")(
            employee_name="Meera Iyer",
            employee_email="meera.iyer@example.com",
            location="India",
            manager_name="Priya Nair",
            start_date="2026-09-01",
        )
        assert result["Status"] == "submitted"
        assert result["EmployeeName"] == "Meera Iyer"
        assert result["CaseId"] is not None

    def test_get_case_returns_created_case(self, server):
        created = _tool_fn(server, "create_case")(
            employee_name="Sam Carter",
            employee_email="sam.carter@example.com",
            location="USA",
            manager_name="Casey Morgan",
            start_date="2026-09-15",
        )
        fetched = _tool_fn(server, "get_case")(case_id=created["CaseId"])
        assert fetched["EmployeeEmail"] == "sam.carter@example.com"

    def test_get_case_unknown_raises(self, server):
        with pytest.raises(ToolError, match="No onboarding case found"):
            _tool_fn(server, "get_case")(case_id=999999)

    def test_update_case_status_valid(self, server):
        created = _tool_fn(server, "create_case")(
            employee_name="Vikram Singh",
            employee_email="vikram.singh@example.com",
            location="India",
            manager_name="Priya Nair",
            start_date="2026-09-20",
        )
        updated = _tool_fn(server, "update_case_status")(
            case_id=created["CaseId"], status="it_provisioning", notes="Laptop ordered"
        )
        assert updated["Status"] == "it_provisioning"
        assert updated["Notes"] == "Laptop ordered"

    def test_update_case_status_invalid_raises(self, server):
        created = _tool_fn(server, "create_case")(
            employee_name="Dana White",
            employee_email="dana.white@example.com",
            location="USA",
            manager_name="Casey Morgan",
            start_date="2026-09-22",
        )
        with pytest.raises(ToolError, match="Invalid status"):
            _tool_fn(server, "update_case_status")(
                case_id=created["CaseId"], status="not_a_real_status"
            )

    def test_update_case_status_unknown_case_raises(self, server):
        with pytest.raises(ToolError, match="No onboarding case found"):
            _tool_fn(server, "update_case_status")(case_id=999999, status="completed")

    def test_list_cases_filters_by_status(self, server):
        _tool_fn(server, "create_case")(
            employee_name="Anita Desai",
            employee_email="anita.desai@example.com",
            location="India",
            manager_name="Priya Nair",
            start_date="2026-10-01",
        )
        second = _tool_fn(server, "create_case")(
            employee_name="Chris Nolan",
            employee_email="chris.nolan@example.com",
            location="USA",
            manager_name="Casey Morgan",
            start_date="2026-10-02",
        )
        _tool_fn(server, "update_case_status")(
            case_id=second["CaseId"], status="completed"
        )

        submitted = _tool_fn(server, "list_cases")(status="submitted")
        completed = _tool_fn(server, "list_cases")(status="completed")
        all_cases = _tool_fn(server, "list_cases")()

        assert len(submitted) == 1
        assert len(completed) == 1
        assert len(all_cases) == 2
