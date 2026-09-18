"""Migration tests."""

import sqlite3
import pytest
from samjon_memory.core.migration import run_migrations, ensure_schema, get_schema_version
from samjon_memory.constants import CORE_SCHEMA_VERSION


def test_initial_migration(temp_db):
    conn = sqlite3.connect(temp_db)
    applied = run_migrations(conn)
    assert "1.0.0" in applied
    assert get_schema_version(conn) == CORE_SCHEMA_VERSION
    conn.close()


def test_migration_idempotent(temp_db):
    conn = sqlite3.connect(temp_db)
    ensure_schema(conn)
    applied = run_migrations(conn)
    assert applied == []
    conn.close()


def test_core_schema_version(temp_db):
    conn = sqlite3.connect(temp_db)
    ensure_schema(conn)
    version = get_schema_version(conn)
    assert version == CORE_SCHEMA_VERSION
    conn.close()


def test_no_resolver_tables(temp_db):
    conn = sqlite3.connect(temp_db)
    ensure_schema(conn)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "samjon_resolver" not in tables
    for t in tables:
        assert "resolver" not in t.lower()
    conn.close()