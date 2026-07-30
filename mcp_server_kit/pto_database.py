"""
Database management for mock employee PTO (paid time off) records.

Provides a SQLite-backed store of employee PTO balances (seeded with a
small India/USA workforce) plus a PTO request log, modeled on the same
shape as ``contact_database.py``.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import sqlite3
from typing import Optional


_EMPLOYEE_COLUMNS = [
    "EmployeeId", "FullName", "Email", "Location", "Manager",
    "PtoBalanceDays", "AccrualRatePerMonth",
]

_SEED_EMPLOYEES = [
    {
        "EmployeeId": "E1001", "FullName": "Asha Rao",
        "Email": "asha.rao@example.com", "Location": "India",
        "Manager": "Priya Nair", "PtoBalanceDays": 18.0,
        "AccrualRatePerMonth": 1.5,
    },
    {
        "EmployeeId": "E1002", "FullName": "Rohit Sharma",
        "Email": "rohit.sharma@example.com", "Location": "India",
        "Manager": "Priya Nair", "PtoBalanceDays": 12.5,
        "AccrualRatePerMonth": 1.5,
    },
    {
        "EmployeeId": "E1003", "FullName": "Priya Nair",
        "Email": "priya.nair@example.com", "Location": "India",
        "Manager": "Deepak Menon", "PtoBalanceDays": 22.0,
        "AccrualRatePerMonth": 1.5,
    },
    {
        "EmployeeId": "E2001", "FullName": "Jordan Blake",
        "Email": "jordan.blake@example.com", "Location": "USA",
        "Manager": "Casey Morgan", "PtoBalanceDays": 9.0,
        "AccrualRatePerMonth": 1.25,
    },
    {
        "EmployeeId": "E2002", "FullName": "Taylor Reed",
        "Email": "taylor.reed@example.com", "Location": "USA",
        "Manager": "Casey Morgan", "PtoBalanceDays": 15.0,
        "AccrualRatePerMonth": 1.25,
    },
    {
        "EmployeeId": "E2003", "FullName": "Casey Morgan",
        "Email": "casey.morgan@example.com", "Location": "USA",
        "Manager": "Jamie Ellis", "PtoBalanceDays": 20.0,
        "AccrualRatePerMonth": 1.25,
    },
]


class PtoDatabaseManager:
    """
    Manages SQLite database operations for mock employee PTO records.

    Attributes:
        db_path (str): Path to the SQLite database file.
    """

    def __init__(self, db_path: str = "pto.db"):
        """
        Initialize the PtoDatabaseManager.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path

    def init_db(self) -> None:
        """
        Initialize the PTO database and seed data if empty.

        Creates the ``employees`` and ``pto_requests`` tables if they do
        not exist, then calls ``seed_employees()`` to populate sample data
        when the ``employees`` table is empty.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            columns_sql = ", ".join(f"{col} TEXT" for col in _EMPLOYEE_COLUMNS)
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS employees "
                f"(rowid INTEGER PRIMARY KEY AUTOINCREMENT, {columns_sql})"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS pto_requests ("
                "RequestId INTEGER PRIMARY KEY AUTOINCREMENT, "
                "EmployeeId TEXT, StartDate TEXT, EndDate TEXT, "
                "Days REAL, Status TEXT, CreatedAt TEXT)"
            )
            conn.commit()
            self.seed_employees(conn)
        finally:
            conn.close()

    def seed_employees(self, conn: Optional[sqlite3.Connection] = None) -> None:
        """
        Seed the employees table with sample data if it is empty.

        Args:
            conn: Optional existing database connection. If ``None``,
                  a new connection is opened and closed automatically.
        """
        close = False
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            close = True
        try:
            row = conn.execute("SELECT COUNT(*) FROM employees").fetchone()
            if row[0] == 0:
                placeholders = ", ".join("?" for _ in _EMPLOYEE_COLUMNS)
                col_names = ", ".join(_EMPLOYEE_COLUMNS)
                for employee in _SEED_EMPLOYEES:
                    values = [employee[col] for col in _EMPLOYEE_COLUMNS]
                    conn.execute(
                        f"INSERT INTO employees ({col_names}) VALUES ({placeholders})",
                        values,
                    )
                conn.commit()
        finally:
            if close:
                conn.close()

    def _rows_to_dicts(self, cursor: sqlite3.Cursor) -> list[dict]:
        """Convert cursor results to a list of dicts."""
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _row_to_balance_dict(self, row: dict) -> dict:
        """Coerce the numeric PTO fields from TEXT storage back to floats."""
        return {
            "employee_id": row["EmployeeId"],
            "full_name": row["FullName"],
            "email": row["Email"],
            "location": row["Location"],
            "manager": row["Manager"],
            "pto_balance_days": float(row["PtoBalanceDays"]),
            "accrual_rate_per_month": float(row["AccrualRatePerMonth"]),
        }

    def get_balance(self, employee_id: str) -> Optional[dict]:
        """
        Look up an employee's PTO balance by employee ID.

        Args:
            employee_id: Employee ID to search for (exact match).

        Returns:
            A balance dict, or ``None`` if no matching employee is found.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM employees WHERE EmployeeId = ?",
                (employee_id,),
            )
            results = self._rows_to_dicts(cursor)
            if not results:
                return None
            return self._row_to_balance_dict(results[0])
        finally:
            conn.close()

    def get_balance_by_email(self, email: str) -> Optional[dict]:
        """
        Look up an employee's PTO balance by email (case-insensitive exact match).

        Args:
            email: Employee email address to search for.

        Returns:
            A balance dict, or ``None`` if no matching employee is found.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM employees WHERE Email = ? COLLATE NOCASE",
                (email,),
            )
            results = self._rows_to_dicts(cursor)
            if not results:
                return None
            return self._row_to_balance_dict(results[0])
        finally:
            conn.close()

    def request_pto(
        self, employee_id: str, start_date: str, end_date: str, days: float
    ) -> dict:
        """
        File a PTO request for an employee, auto-approving if balance allows.

        If the employee has sufficient balance, the requested days are
        deducted immediately and the request is recorded as ``approved``.
        Otherwise the request is recorded as ``denied_insufficient_balance``
        and no balance is deducted.

        Args:
            employee_id: Employee ID filing the request.
            start_date: Requested start date (ISO ``YYYY-MM-DD``).
            end_date: Requested end date (ISO ``YYYY-MM-DD``).
            days: Number of PTO days requested.

        Returns:
            Dict with keys: request_id, employee_id, start_date, end_date,
            days, status, remaining_balance_days.

        Raises:
            ValueError: If no employee matches ``employee_id``.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT rowid, PtoBalanceDays FROM employees WHERE EmployeeId = ?",
                (employee_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError(f"No employee found with EmployeeId '{employee_id}'")

            rowid, current_balance = row[0], float(row[1])
            if days <= current_balance:
                status = "approved"
                new_balance = current_balance - days
                conn.execute(
                    "UPDATE employees SET PtoBalanceDays = ? WHERE rowid = ?",
                    (new_balance, rowid),
                )
            else:
                status = "denied_insufficient_balance"
                new_balance = current_balance

            cursor = conn.execute(
                "INSERT INTO pto_requests "
                "(EmployeeId, StartDate, EndDate, Days, Status, CreatedAt) "
                "VALUES (?, ?, ?, ?, ?, datetime('now'))",
                (employee_id, start_date, end_date, days, status),
            )
            conn.commit()
            return {
                "request_id": cursor.lastrowid,
                "employee_id": employee_id,
                "start_date": start_date,
                "end_date": end_date,
                "days": days,
                "status": status,
                "remaining_balance_days": new_balance,
            }
        finally:
            conn.close()

    def list_requests(self, employee_id: str) -> list[dict]:
        """
        List all PTO requests filed by an employee, most recent first.

        Args:
            employee_id: Employee ID to list requests for.

        Returns:
            List of request dicts.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM pto_requests WHERE EmployeeId = ? "
                "ORDER BY RequestId DESC",
                (employee_id,),
            )
            return self._rows_to_dicts(cursor)
        finally:
            conn.close()
