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


def test_v110_backfills_forgotten_at_from_audit(temp_db):
    """Backfill forgotten_at from reliable audit evidence only."""
    conn = sqlite3.connect(temp_db)
    # Simulate a pre-1.1.0 database.
    run_migrations(conn, target_version="1.0.0")
    conn.execute(
        "INSERT INTO memory (memory_id, subject, raw_content, source, status, version, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
        ("mem-with-evidence", "s1", "c", "t", "forgotten", 2, "2026-01-01T00:00:00.000000Z", "2026-01-02T00:00:00.000000Z"),
    )
    conn.execute(
        "INSERT INTO memory (memory_id, subject, raw_content, source, status, version, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
        ("mem-no-evidence", "s2", "c", "t", "forgotten", 2, "2026-01-01T00:00:00.000000Z", "2026-01-02T00:00:00.000000Z"),
    )
    conn.execute(
        "INSERT INTO audit_log (audit_id, entity_type, entity_id, action, actor, source, version, created_at) VALUES (?,?,?,?,?,?,?,?)",
        ("aud-1", "memory", "mem-with-evidence", "memory_forget", "system", "t", 2, "2026-01-02T12:00:00.000000Z"),
    )
    conn.commit()
    run_migrations(conn)  # -> 1.1.0 applies backfill
    row = conn.execute("SELECT forgotten_at FROM memory WHERE memory_id='mem-with-evidence'").fetchone()
    assert row[0] == "2026-01-02T12:00:00.000000Z"
    row2 = conn.execute("SELECT forgotten_at FROM memory WHERE memory_id='mem-no-evidence'").fetchone()
    assert row2[0] is None
    conn.close()