"""Idempotency tests."""

import pytest
from samjon_memory.core.service import CoreService
from samjon_memory.errors import IdempotencyConflict


def test_idempotent_create(service):
    data = {"subject": "idempotent", "raw_content": "content", "source": "test"}
    r1 = service.create_memory(data)
    r2 = service.create_memory(data)
    assert r1["memory_id"] != r2["memory_id"]


def test_idempotency_conflict(service):
    data1 = {"subject": "first", "raw_content": "content1", "source": "test"}
    data2 = {"subject": "second", "raw_content": "content2", "source": "test"}
    key = "test-key-123"
    r1 = service.create_memory(data1, idempotency_key=key)
    with pytest.raises(IdempotencyConflict):
        service.create_memory(data2, idempotency_key=key)