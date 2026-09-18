"""Memory CRUD tests."""

import pytest
from samjon_memory.core.service import CoreService
from samjon_memory.errors import NotFound, VersionConflict


def test_create_standalone_memory(service):
    data = {
        "subject": "test memory",
        "raw_content": "This is a test memory.",
        "source": "test",
    }
    result = service.create_memory(data)
    assert result["memory_id"]
    assert result["subject"] == "test memory"
    assert result["status"] == "draft"


def test_get_memory(service):
    created = service.create_memory({"subject": "find me", "raw_content": "content", "source": "test"})
    result = service.get_memory(created["memory_id"])
    assert result["subject"] == "find me"


def test_update_memory(service):
    created = service.create_memory({"subject": "original", "raw_content": "content", "source": "test"})
    updated = service.update_memory(created["memory_id"], {"subject": "updated", "expected_version": 1})
    assert updated["subject"] == "updated"
    assert updated["version"] == 2


def test_version_conflict(service):
    created = service.create_memory({"subject": "v1", "raw_content": "content", "source": "test"})
    service.update_memory(created["memory_id"], {"subject": "v2", "expected_version": 1})
    with pytest.raises(ValueError, match="VERSION_CONFLICT"):
        service.update_memory(created["memory_id"], {"subject": "v3", "expected_version": 1})


def test_supersede_memory(service):
    created = service.create_memory({"subject": "old", "raw_content": "content", "source": "test"})
    replacement = service.create_memory({"subject": "new", "raw_content": "replacement", "source": "test"})
    result = service.supersede_memory(created["memory_id"], replacement["memory_id"])
    assert result["status"] == "superseded"


def test_forget_memory(service):
    created = service.create_memory({"subject": "forget me", "raw_content": "content", "source": "test"})
    result = service.forget_memory(created["memory_id"])
    assert result["forgotten"] is True
    forgotten = service.get_memory(created["memory_id"])
    assert forgotten["status"] == "forgotten"


def test_content_limit(service):
    with pytest.raises(Exception):
        service.create_memory({"subject": "too long", "raw_content": "x" * 16385, "source": "test"})
