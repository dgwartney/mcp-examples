"""
Unit tests for mcp_server_kit.database

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import os
import sqlite3
import tempfile

import pytest

from mcp_server_kit.database import DatabaseManager


class TestDatabaseManager:
    """Test suite for DatabaseManager class."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file path."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        # Cleanup
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def db_manager(self, temp_db_path):
        """Create a DatabaseManager instance with temporary database."""
        return DatabaseManager(temp_db_path)

    def test_init(self, temp_db_path):
        """Test DatabaseManager initialization."""
        db_manager = DatabaseManager(temp_db_path)
        assert db_manager.db_path == temp_db_path

    def test_init_db_creates_table(self, db_manager, temp_db_path):
        """Test that init_db creates the api_keys table."""
        db_manager.init_db()

        # Verify table exists
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='api_keys'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "api_keys"

    def test_init_db_creates_default_key(self, db_manager, temp_db_path, caplog):
        """Test that init_db creates a default API key on first run."""
        with caplog.at_level("INFO", logger="mcp_server_kit.database"):
            returned_key = db_manager.init_db()

        # Verify key was generated
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM api_keys")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1

        # init_db returns the generated key and logs it (not printed to stdout)
        assert returned_key is not None
        assert "Generated default API key:" in caplog.text
        assert returned_key in caplog.text

    def test_init_db_does_not_duplicate_key(self, db_manager, temp_db_path):
        """Test that init_db doesn't create duplicate keys on subsequent runs."""
        db_manager.init_db()
        db_manager.init_db()  # Run again

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM api_keys")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1  # Still only one key

    def test_validate_key_valid(self, db_manager, temp_db_path):
        """Test validate_key returns True for valid keys."""
        # Insert a test key
        conn = sqlite3.connect(temp_db_path)
        test_key = "test-key-123"
        conn.execute("CREATE TABLE IF NOT EXISTS api_keys (id INTEGER PRIMARY KEY, key TEXT UNIQUE NOT NULL)")
        conn.execute("INSERT INTO api_keys (key) VALUES (?)", (test_key,))
        conn.commit()
        conn.close()

        assert db_manager.validate_key(test_key) is True

    def test_validate_key_invalid(self, db_manager, temp_db_path):
        """Test validate_key returns False for invalid keys."""
        db_manager.init_db()
        assert db_manager.validate_key("invalid-key") is False

    def test_validate_key_none(self, db_manager, temp_db_path):
        """Test validate_key returns False for None."""
        db_manager.init_db()
        assert db_manager.validate_key(None) is False

    def test_validate_key_empty_string(self, db_manager, temp_db_path):
        """Test validate_key returns False for empty string."""
        db_manager.init_db()
        assert db_manager.validate_key("") is False

    def test_database_path_customization(self):
        """Test that custom database paths are respected."""
        custom_path = "/tmp/custom_test.db"
        db_manager = DatabaseManager(custom_path)
        assert db_manager.db_path == custom_path
