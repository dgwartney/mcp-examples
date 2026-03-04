"""
Unit tests for mcp_examples.contact_database

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import os
import tempfile

import pytest

from mcp_examples.contact_database import ContactDatabaseManager


class TestContactDatabaseManager:
    """Test suite for ContactDatabaseManager class."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file path."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def db(self, temp_db_path):
        """Create an initialized ContactDatabaseManager."""
        db = ContactDatabaseManager(temp_db_path)
        db.init_db()
        return db

    def test_init_db_creates_table_and_seeds(self, db, temp_db_path):
        """Test that init_db creates the contacts table and seeds 20 rows."""
        import sqlite3
        conn = sqlite3.connect(temp_db_path)
        count = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        conn.close()
        assert count == 20

    def test_seed_contacts_does_not_duplicate(self, db, temp_db_path):
        """Test that calling seed_contacts again does not insert duplicates."""
        import sqlite3
        db.seed_contacts()
        conn = sqlite3.connect(temp_db_path)
        count = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        conn.close()
        assert count == 20

    def test_search_by_last_name_partial_match(self, db):
        """Test partial match returns Bugs Bunny and Lola Bunny."""
        results = db.search_by_last_name("bunny")
        assert len(results) == 2
        first_names = {r["FirstName"] for r in results}
        assert first_names == {"Bugs", "Lola"}

    def test_search_by_last_name_case_insensitive(self, db):
        """Test that last name search is case-insensitive."""
        results_lower = db.search_by_last_name("duck")
        results_upper = db.search_by_last_name("DUCK")
        assert len(results_lower) == 1
        assert len(results_upper) == 1
        assert results_lower[0]["FirstName"] == "Daffy"

    def test_search_by_last_name_no_results(self, db):
        """Test that a non-matching last name returns empty list."""
        results = db.search_by_last_name("nonexistent")
        assert results == []

    def test_search_by_email_exact_match(self, db):
        """Test exact email match."""
        results = db.search_by_email("bugs.bunny@acme.com")
        assert len(results) == 1
        assert results[0]["FirstName"] == "Bugs"

    def test_search_by_email_case_insensitive(self, db):
        """Test that email search is case-insensitive."""
        results = db.search_by_email("BUGS.BUNNY@ACME.COM")
        assert len(results) == 1
        assert results[0]["FirstName"] == "Bugs"

    def test_search_by_email_no_results(self, db):
        """Test that a non-matching email returns empty list."""
        results = db.search_by_email("nobody@nowhere.com")
        assert results == []

    def test_search_by_account_id_exact_match(self, db):
        """Test exact account ID match returns 4 ACME contacts."""
        results = db.search_by_account_id("0011A00001xAC001")
        assert len(results) == 4
        account_names = {r["AccountName"] for r in results}
        assert account_names == {"ACME Corporation"}

    def test_search_by_account_id_no_results(self, db):
        """Test that a non-matching account ID returns empty list."""
        results = db.search_by_account_id("INVALID_ID")
        assert results == []

    def test_password_field_present_and_nonempty(self, db):
        """Test that the Password field is present and non-empty in search results."""
        results = db.search_by_last_name("bunny")
        for contact in results:
            assert "Password" in contact
            assert contact["Password"]

    def test_authenticate_valid_credentials(self, db):
        """Test successful authentication returns contact without password."""
        result = db.authenticate("bugs.bunny@acme.com", "bugs2022!")
        assert result is not None
        assert result["FirstName"] == "Bugs"
        assert "Password" not in result

    def test_authenticate_invalid_password(self, db):
        """Test authentication with wrong password returns None."""
        result = db.authenticate("bugs.bunny@acme.com", "wrongpassword")
        assert result is None

    def test_authenticate_unknown_email(self, db):
        """Test authentication with unknown email returns None."""
        result = db.authenticate("unknown@example.com", "password")
        assert result is None

    def test_authenticate_case_insensitive_email(self, db):
        """Test that authenticate is case-insensitive for email."""
        result = db.authenticate("BUGS.BUNNY@ACME.COM", "bugs2022!")
        assert result is not None
        assert result["FirstName"] == "Bugs"
