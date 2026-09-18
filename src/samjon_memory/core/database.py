"""SQLite database connection and pragmas for Samjon Memory Core."""

import sqlite3
from typing import Optional

from samjon_memory.config import config
from samjon_memory.constants import SQLITE_PRAGMAS
from samjon_memory.errors import CoreDatabaseUnavailable


def get_connection(database_path: Optional[str] = None) -> sqlite3.Connection:
    """Get a SQLite connection with Core pragmas configured."""
    path = database_path or config.database_path
    try:
        conn = sqlite3.connect(path, timeout=10)
        conn.row_factory = sqlite3.Row
        for pragma in SQLITE_PRAGMAS:
            conn.execute(pragma)
        return conn
    except sqlite3.Error as e:
        raise CoreDatabaseUnavailable(f"Cannot connect to Core database: {e}") from e


def execute_script(conn: sqlite3.Connection, sql: str) -> None:
    """Execute a SQL script safely."""
    try:
        conn.executescript(sql)
        conn.commit()
    except sqlite3.Error as e:
        raise CoreDatabaseUnavailable(f"Database script error: {e}") from e


def execute_query(conn: sqlite3.Connection, query: str, params: tuple = ()):
    """Execute a query and return cursor."""
    try:
        return conn.execute(query, params)
    except sqlite3.Error as e:
        raise CoreDatabaseUnavailable(f"Database query error: {e}") from e


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check if a table exists in the database."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()
    return row is not None


def get_schema_version(conn: sqlite3.Connection) -> str:
    """Get the current schema version from metadata."""
    row = conn.execute(
        "SELECT value FROM schema_metadata WHERE key=?", ("core_schema_version",)
    ).fetchone()
    if row is None:
        return "0.0.0"
    try:
        return row["value"]
    except (TypeError, IndexError):
        return row[0] if row else "0.0.0"