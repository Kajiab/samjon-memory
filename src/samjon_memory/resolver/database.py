"""SQLite connection and pragmas for Samjon Memory Resolver V1."""

import sqlite3
from typing import Optional

from samjon_memory.errors import ResolverDatabaseUnavailable
from samjon_memory.resolver.config import load_config
from samjon_memory.resolver.constants import RESOLVER_SQLITE_PRAGMAS


def get_connection(database_path: Optional[str] = None) -> sqlite3.Connection:
    """Open a Resolver SQLite connection with Resolver pragmas."""
    path = database_path or load_config().database_path
    try:
        conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        for pragma in RESOLVER_SQLITE_PRAGMAS:
            conn.execute(pragma)
        return conn
    except sqlite3.Error as e:
        raise ResolverDatabaseUnavailable(
            f"Cannot connect to Resolver database: {e}"
        ) from e


def execute_script(conn: sqlite3.Connection, sql: str) -> None:
    """Execute a SQL script safely against the Resolver database."""
    try:
        conn.executescript(sql)
        conn.commit()
    except sqlite3.Error as e:
        raise ResolverDatabaseUnavailable(
            f"Resolver database script error: {e}"
        ) from e


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Return True if a Resolver table exists."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def fts5_available(conn: sqlite3.Connection) -> bool:
    """Return True when the SQLite build supports FTS5."""
    try:
        options = [r[0] for r in conn.execute("PRAGMA compile_options").fetchall()]
        if "ENABLE_FTS5" in options:
            return True
    except sqlite3.Error:
        pass
    probe = "_samjon_fts5_probe"
    try:
        conn.execute(f"CREATE VIRTUAL TABLE {probe} USING fts5(x)")
        return True
    except sqlite3.Error:
        return False
    finally:
        try:
            conn.execute(f"DROP TABLE IF EXISTS {probe}")
        except sqlite3.Error:
            pass


def ensure_fts5(conn: sqlite3.Connection) -> None:
    """Fail fast when FTS5 is required but unavailable."""
    if not fts5_available(conn):
        raise ResolverDatabaseUnavailable(
            "FTS5 is required but unavailable in this SQLite build"
        )
