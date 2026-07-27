"""
Integration tests for scripts/new_server.py.

Runs the scaffold script against a temporary copy of the repository's
mcp_examples/ and tests/ directories so the real repo is never touched.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "new_server.py"


@pytest.fixture
def scaffold_env(tmp_path, monkeypatch):
    """Copy mcp_examples/, tests/, and scripts/ into a temp repo root."""
    for name in ("mcp_examples", "tests", "scripts"):
        shutil.copytree(REPO_ROOT / name, tmp_path / name)
    return tmp_path


def _run_scaffold(repo_root: Path, name: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "new_server.py"), name],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )


class TestNewServerScript:

    def test_creates_module_and_test_files(self, scaffold_env):
        result = _run_scaffold(scaffold_env, "Inventory")
        assert result.returncode == 0, result.stderr
        assert (scaffold_env / "mcp_examples" / "inventory.py").exists()
        assert (scaffold_env / "tests" / "test_inventory.py").exists()

    def test_generated_module_imports_cleanly(self, scaffold_env):
        _run_scaffold(scaffold_env, "Inventory")
        # Import in a fresh subprocess (cwd = the temp copy) so the module's
        # top-level `server = InventoryMCPServer()` writes its SQLite db
        # inside the temp dir, never the real repo or the test runner's cwd.
        check = subprocess.run(
            [
                sys.executable, "-c",
                "from mcp_examples.inventory import InventoryMCPServer, server, mcp; "
                "assert isinstance(server, InventoryMCPServer); "
                "assert mcp is server.mcp",
            ],
            cwd=scaffold_env,
            capture_output=True,
            text=True,
        )
        assert check.returncode == 0, check.stderr

    def test_combined_py_registry_updated(self, scaffold_env):
        _run_scaffold(scaffold_env, "Inventory")
        content = (scaffold_env / "mcp_examples" / "combined.py").read_text()
        assert "from mcp_examples.inventory import InventoryMCPServer" in content
        assert '("inventory", InventoryMCPServer)' in content

    def test_init_py_registry_updated(self, scaffold_env):
        _run_scaffold(scaffold_env, "Inventory")
        content = (scaffold_env / "mcp_examples" / "__init__.py").read_text()
        assert '"InventoryMCPServer",' in content
        assert '"InventoryMCPServer": "mcp_examples.inventory",' in content

    def test_refuses_to_overwrite_existing_module(self, scaffold_env):
        _run_scaffold(scaffold_env, "Inventory")
        result = _run_scaffold(scaffold_env, "Inventory")
        assert result.returncode != 0
        assert "already exists" in result.stderr

    def test_rejects_lowercase_name(self, scaffold_env):
        result = _run_scaffold(scaffold_env, "inventory")
        assert result.returncode != 0

    def test_rejects_missing_argument(self, scaffold_env):
        result = subprocess.run(
            [sys.executable, str(scaffold_env / "scripts" / "new_server.py")],
            cwd=scaffold_env,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_multi_word_name_converted_to_snake_case(self, scaffold_env):
        result = _run_scaffold(scaffold_env, "OrderTracking")
        assert result.returncode == 0, result.stderr
        assert (scaffold_env / "mcp_examples" / "order_tracking.py").exists()
        assert (scaffold_env / "tests" / "test_order_tracking.py").exists()
        content = (scaffold_env / "mcp_examples" / "order_tracking.py").read_text()
        assert "class OrderTrackingMCPServer" in content
