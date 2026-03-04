"""
Database management for API key storage and validation.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import secrets
import sqlite3
from typing import Optional


class DatabaseManager:
    """
    Manages SQLite database operations for API key storage and validation.

    This class handles database initialization, API key generation, and
    validation against stored keys. Keys are stored securely using
    parameterized queries to prevent SQL injection.

    Attributes:
        db_path (str): Path to the SQLite database file.
    """

    def __init__(self, db_path: str):
        """
        Initialize the DatabaseManager.

        Args:
            db_path (str): Absolute path to the SQLite database file.
        """
        self.db_path = db_path

    def init_db(self) -> None:
        """
        Initialize the database schema and create a default API key.

        Creates the api_keys table if it doesn't exist. If the table is empty,
        generates a cryptographically secure random API key using secrets.token_urlsafe()
        and inserts it as the default key. The generated key is printed to stdout
        on first run.

        The table schema:
            - id: INTEGER PRIMARY KEY AUTOINCREMENT
            - key: TEXT UNIQUE NOT NULL

        Raises:
            sqlite3.Error: If database operations fail.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS api_keys "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE NOT NULL)"
            )
            row = conn.execute("SELECT COUNT(*) FROM api_keys").fetchone()
            if row[0] == 0:
                default_key = secrets.token_urlsafe(32)
                conn.execute("INSERT INTO api_keys (key) VALUES (?)", (default_key,))
                print(f"Generated default API key: {default_key}")
            conn.commit()
        finally:
            conn.close()

    def validate_key(self, api_key: Optional[str]) -> bool:
        """
        Validate an API key against the database.

        Args:
            api_key (Optional[str]): The API key to validate. Can be None.

        Returns:
            bool: True if the key exists in the database, False otherwise.

        Raises:
            sqlite3.Error: If database query fails.
        """
        if api_key is None:
            return False

        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM api_keys WHERE key = ?", (api_key,)
            ).fetchone()
        finally:
            conn.close()
        return row is not None
