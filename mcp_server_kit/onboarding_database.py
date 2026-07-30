"""
Database management for mock employee onboarding cases.

Provides a SQLite-backed case log for new-hire onboarding (India/USA),
modeled on the same shape as ``contact_database.py``/``pto_database.py``.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import sqlite3
from typing import Optional

_VALID_STATUSES = {
    "submitted", "it_provisioning", "manager_review", "completed", "cancelled",
}


class OnboardingDatabaseManager:
    """
    Manages SQLite database operations for mock onboarding cases.

    Attributes:
        db_path (str): Path to the SQLite database file.
    """

    def __init__(self, db_path: str = "onboarding.db"):
        """
        Initialize the OnboardingDatabaseManager.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path

    def init_db(self) -> None:
        """
        Initialize the onboarding_cases table if it does not already exist.

        No seed data is inserted — cases are created at runtime via
        ``create_case``, since a new-hire case log is meaningfully empty
        until someone actually onboards.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS onboarding_cases ("
                "CaseId INTEGER PRIMARY KEY AUTOINCREMENT, "
                "EmployeeName TEXT, EmployeeEmail TEXT, Location TEXT, "
                "ManagerName TEXT, StartDate TEXT, Status TEXT, "
                "Notes TEXT, CreatedAt TEXT, UpdatedAt TEXT)"
            )
            conn.commit()
        finally:
            conn.close()

    def _rows_to_dicts(self, cursor: sqlite3.Cursor) -> list[dict]:
        """Convert cursor results to a list of dicts."""
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def create_case(
        self,
        employee_name: str,
        employee_email: str,
        location: str,
        manager_name: str,
        start_date: str,
    ) -> dict:
        """
        Create a new onboarding case in the ``submitted`` status.

        Args:
            employee_name: Full name of the new hire.
            employee_email: Email address of the new hire.
            location: Work location, e.g. "India" or "USA".
            manager_name: Full name of the new hire's manager.
            start_date: Employment start date (ISO YYYY-MM-DD).

        Returns:
            The newly created case dict.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "INSERT INTO onboarding_cases "
                "(EmployeeName, EmployeeEmail, Location, ManagerName, "
                "StartDate, Status, Notes, CreatedAt, UpdatedAt) "
                "VALUES (?, ?, ?, ?, ?, 'submitted', '', datetime('now'), datetime('now'))",
                (employee_name, employee_email, location, manager_name, start_date),
            )
            conn.commit()
            return self.get_case(cursor.lastrowid)
        finally:
            conn.close()

    def get_case(self, case_id: int) -> Optional[dict]:
        """
        Look up an onboarding case by case ID.

        Args:
            case_id: Case ID to search for.

        Returns:
            Case dict, or ``None`` if no matching case is found.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM onboarding_cases WHERE CaseId = ?",
                (case_id,),
            )
            results = self._rows_to_dicts(cursor)
            return results[0] if results else None
        finally:
            conn.close()

    def update_case_status(
        self, case_id: int, status: str, notes: Optional[str] = None
    ) -> dict:
        """
        Update an onboarding case's status (and optionally append notes).

        Args:
            case_id: Case ID to update.
            status: New status. Must be one of: submitted, it_provisioning,
                manager_review, completed, cancelled.
            notes: Optional note text to record with this status change.

        Returns:
            The updated case dict.

        Raises:
            ValueError: If case_id doesn't exist or status is invalid.
        """
        if status not in _VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: "
                f"{', '.join(sorted(_VALID_STATUSES))}"
            )
        conn = sqlite3.connect(self.db_path)
        try:
            existing = conn.execute(
                "SELECT CaseId FROM onboarding_cases WHERE CaseId = ?",
                (case_id,),
            ).fetchone()
            if existing is None:
                raise ValueError(f"No onboarding case found with case_id '{case_id}'")

            if notes:
                conn.execute(
                    "UPDATE onboarding_cases SET Status = ?, Notes = ?, "
                    "UpdatedAt = datetime('now') WHERE CaseId = ?",
                    (status, notes, case_id),
                )
            else:
                conn.execute(
                    "UPDATE onboarding_cases SET Status = ?, "
                    "UpdatedAt = datetime('now') WHERE CaseId = ?",
                    (status, case_id),
                )
            conn.commit()
            return self.get_case(case_id)
        finally:
            conn.close()

    def list_cases_by_status(self, status: Optional[str] = None) -> list[dict]:
        """
        List onboarding cases, optionally filtered by status.

        Args:
            status: Optional status to filter by. If None, all cases are
                returned.

        Returns:
            List of case dicts, most recently created first.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            if status:
                cursor = conn.execute(
                    "SELECT * FROM onboarding_cases WHERE Status = ? "
                    "ORDER BY CaseId DESC",
                    (status,),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM onboarding_cases ORDER BY CaseId DESC"
                )
            return self._rows_to_dicts(cursor)
        finally:
            conn.close()
