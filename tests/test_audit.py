"""Audit record tests."""

import pytest
from samjon_memory.core.service import CoreService


def test_audit_records_on_create(service):
    created = service.create_memory({"subject": "audit test", "raw_content": "content", "source": "test"})
    audits = service.conn.execute("SELECT * FROM audit_log WHERE entity_id=? AND action=?", (created["memory_id"], "memory_create")).fetchall()
    assert len(audits) == 1
    assert audits[0]["entity_type"] == "memory"
    assert audits[0]["action"] == "memory_create"