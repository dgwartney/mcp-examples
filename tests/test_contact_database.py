"""
Unit tests for mcp_server_kit.contact_database

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import os
import tempfile

import pytest

from mcp_server_kit.contact_database import ContactDatabaseManager


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
        """Test partial match returns Marcus Webb and Eleanor Webster."""
        results = db.search_by_last_name("web")
        assert len(results) == 2
        first_names = {r["FirstName"] for r in results}
        assert first_names == {"Marcus", "Eleanor"}

    def test_search_by_last_name_case_insensitive(self, db):
        """Test that last name search is case-insensitive."""
        results_lower = db.search_by_last_name("chen")
        results_upper = db.search_by_last_name("CHEN")
        assert len(results_lower) == 1
        assert len(results_upper) == 1
        assert results_lower[0]["FirstName"] == "Robert"

    def test_search_by_last_name_no_results(self, db):
        """Test that a non-matching last name returns empty list."""
        results = db.search_by_last_name("nonexistent")
        assert results == []

    def test_search_by_email_exact_match(self, db):
        """Test exact email match."""
        results = db.search_by_email("james.whitfield@meridiancorp.com")
        assert len(results) == 1
        assert results[0]["FirstName"] == "James"

    def test_search_by_email_case_insensitive(self, db):
        """Test that email search is case-insensitive."""
        results = db.search_by_email("JAMES.WHITFIELD@MERIDIANCORP.COM")
        assert len(results) == 1
        assert results[0]["FirstName"] == "James"

    def test_search_by_email_no_results(self, db):
        """Test that a non-matching email returns empty list."""
        results = db.search_by_email("nobody@nowhere.com")
        assert results == []

    def test_search_by_account_id_exact_match(self, db):
        """Test exact account ID match returns 4 Meridian Corporation contacts."""
        results = db.search_by_account_id("MC-001")
        assert len(results) == 4
        account_names = {r["AccountName"] for r in results}
        assert account_names == {"Meridian Corporation"}

    def test_search_by_account_id_no_results(self, db):
        """Test that a non-matching account ID returns empty list."""
        results = db.search_by_account_id("INVALID_ID")
        assert results == []

    def test_search_by_department_partial_match(self, db):
        """Test partial department match returns Marketing contacts."""
        results = db.search_by_department("Marketing")
        assert len(results) == 3
        last_names = {r["LastName"] for r in results}
        assert last_names == {"Reyes", "Moreau", "Dupont"}

    def test_search_by_department_case_insensitive(self, db):
        """Test that department search is case-insensitive."""
        results = db.search_by_department("marketing")
        results_upper = db.search_by_department("MARKETING")
        assert len(results) == 3
        assert len(results_upper) == 3

    def test_search_by_department_no_results(self, db):
        """Test that a non-matching department returns empty list."""
        results = db.search_by_department("Nonexistent")
        assert results == []

    def test_password_field_excluded_from_search_results(self, db):
        """Test that the Password field is never exposed via search results."""
        results = db.search_by_last_name("web")
        assert results
        for contact in results:
            assert "Password" not in contact

    def test_authenticate_valid_credentials(self, db):
        """Test successful authentication returns contact without password."""
        result = db.authenticate("james.whitfield@meridiancorp.com", "password123")
        assert result is not None
        assert result["FirstName"] == "James"
        assert "Password" not in result

    def test_authenticate_invalid_password(self, db):
        """Test authentication with wrong password returns None."""
        result = db.authenticate("james.whitfield@meridiancorp.com", "wrongpassword")
        assert result is None

    def test_authenticate_unknown_email(self, db):
        """Test authentication with unknown email returns None."""
        result = db.authenticate("unknown@example.com", "password")
        assert result is None

    def test_authenticate_case_insensitive_email(self, db):
        """Test that authenticate is case-insensitive for email."""
        result = db.authenticate("JAMES.WHITFIELD@MERIDIANCORP.COM", "password123")
        assert result is not None
        assert result["FirstName"] == "James"

    def test_duplicate_email_rejected_by_unique_constraint(self, db, temp_db_path):
        """Test that inserting a second contact with an existing email fails."""
        import sqlite3

        conn = sqlite3.connect(temp_db_path)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO contacts (Email, FirstName, LastName) "
                    "VALUES (?, ?, ?)",
                    ("james.whitfield@meridiancorp.com", "Duplicate", "Whitfield"),
                )
        finally:
            conn.close()

    def test_duplicate_email_rejected_case_insensitive(self, db, temp_db_path):
        """Test that the email UNIQUE constraint is case-insensitive."""
        import sqlite3

        conn = sqlite3.connect(temp_db_path)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO contacts (Email, FirstName, LastName) "
                    "VALUES (?, ?, ?)",
                    ("JAMES.WHITFIELD@MERIDIANCORP.COM", "Duplicate", "Whitfield"),
                )
        finally:
            conn.close()

    def test_passwords_stored_hashed_not_plaintext(self, db, temp_db_path):
        """Test that the stored Password column never contains the plaintext value."""
        import sqlite3
        conn = sqlite3.connect(temp_db_path)
        stored = conn.execute(
            "SELECT Password FROM contacts WHERE Email = 'james.whitfield@meridiancorp.com'"
        ).fetchone()[0]
        conn.close()
        assert stored != "password123"
        assert stored.count("$") == 2
