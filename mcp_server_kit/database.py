"""
Database management for API key storage and validation.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import logging
import secrets
import sqlite3
from typing import Optional

_logger = logging.getLogger(__name__)


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

    def init_db(self) -> Optional[str]:
        """
        Initialize the database schema and create a default API key.

        Creates the api_keys table if it doesn't exist. If the table is empty,
        generates a cryptographically secure random API key using
        ``secrets.token_urlsafe()`` and inserts it as the default key. The
        generated key is emitted via the ``logging`` module (logger
        ``mcp_server_kit.database``) at INFO level rather than printed to
        stdout, so importing a server module never leaks a secret.

        The table schema:
            - id: INTEGER PRIMARY KEY AUTOINCREMENT
            - key: TEXT UNIQUE NOT NULL

        Returns:
            Optional[str]: The newly generated default key if the table was
            empty, otherwise ``None``.

        Raises:
            sqlite3.Error: If database operations fail.
        """
        conn = sqlite3.connect(self.db_path)
        generated_key: Optional[str] = None
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS api_keys "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE NOT NULL)"
            )
            row = conn.execute("SELECT COUNT(*) FROM api_keys").fetchone()
            if row[0] == 0:
                generated_key = secrets.token_urlsafe(32)
                conn.execute(
                    "INSERT INTO api_keys (key) VALUES (?)", (generated_key,)
                )
                _logger.info("Generated default API key: %s", generated_key)
            conn.commit()
        finally:
            conn.close()
        return generated_key

    def validate_key(self, api_key: Optional[str]) -> bool:
        """
        Validate an API key against the database.

        Compares against every stored key using ``secrets.compare_digest``
        (constant-time per comparison) rather than a SQL equality lookup, so
        the response time does not leak how much of a guessed key is correct.

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
            rows = conn.execute("SELECT key FROM api_keys").fetchall()
        finally:
            conn.close()
        return any(secrets.compare_digest(api_key, row[0]) for row in rows)
