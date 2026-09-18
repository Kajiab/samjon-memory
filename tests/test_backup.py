"""Backup and restore tests."""

import os
import sqlite3
import tempfile
import pytest
from samjon_memory.core.database import get_connection
from samjon_memory.core.migration import ensure_schema
from samjon_memory.core.service import CoreService


def test_backup_manifest(temp_db):
    svc = CoreService(database_path=temp_db)
    svc.create_memory({"subject": "backup test", "raw_content": "content", "source": "test"})
    conn = get_connection(temp_db)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "memory" in tables
    assert "memory_collection" in tables
    assert "audit_log" in tables
    assert "schema_metadata" in tables
    conn.close()


def test_isolated_restore(temp_db):
    svc = CoreService(database_path=temp_db)
    svc.create_memory({"subject": "restore test", "raw_content": "content", "source": "test"})
    mem_id = svc.create_memory({"subject": "second", "raw_content": "content2", "source": "test"})["memory_id"]
    conn = get_connection(temp_db)
    count = conn.execute("SELECT COUNT(*) as c FROM memory WHERE status='draft'").fetchone()["c"]
    assert count == 2
    conn.close()