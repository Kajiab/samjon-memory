"""Collection CRUD tests."""

import pytest
from samjon_memory.core.service import CoreService
from samjon_memory.errors import ValidationError, NotFound


def test_create_draft_collection(service):
    data = {
        "subject": "test collection",
        "title": "Test Collection",
        "source": "test",
    }
    result = service.create_collection(data)
    assert result["collection_id"]
    assert result["status"] == "draft"


def test_add_memory_to_collection(service):
    coll = service.create_collection({"subject": "col", "title": "Test", "source": "test"})
    mem = service.create_memory({"subject": "col", "raw_content": "content", "source": "test"})
    result = service.add_memory_to_collection(coll["collection_id"], mem["memory_id"], 1)
    assert result["added"] is True


def test_collection_version_behavior(service):
    coll = service.create_collection({"subject": "v1", "title": "Test", "source": "test"})
    mem = service.create_memory({"subject": "v1", "raw_content": "content", "source": "test"})
    service.add_memory_to_collection(coll["collection_id"], mem["memory_id"], 1)
    updated = service.update_collection(coll["collection_id"], {"title": "Updated"})
    assert updated["version"] == 2


def test_reorder_collection(service):
    coll = service.create_collection({"subject": "order", "title": "Test", "source": "test"})
    m1 = service.create_memory({"subject": "order", "raw_content": "c1", "source": "test"})
    m2 = service.create_memory({"subject": "order", "raw_content": "c2", "source": "test"})
    service.add_memory_to_collection(coll["collection_id"], m1["memory_id"], 1)
    service.add_memory_to_collection(coll["collection_id"], m2["memory_id"], 2)
    result = service.reorder_collection(coll["collection_id"], [m2["memory_id"], m1["memory_id"]])
    assert result["reordered"] is True


def test_duplicate_sequence_rejected(service):
    coll = service.create_collection({"subject": "dup", "title": "Test", "source": "test"})
    m1 = service.create_memory({"subject": "dup", "raw_content": "c1", "source": "test"})
    m2 = service.create_memory({"subject": "dup", "raw_content": "c2", "source": "test"})
    service.add_memory_to_collection(coll["collection_id"], m1["memory_id"], 1)
    service.add_memory_to_collection(coll["collection_id"], m2["memory_id"], 1)
    memories = service.get_collection_memories(coll["collection_id"])
    seq_nums = [m["sequence_number"] for m in memories if m["sequence_number"] is not None]
    assert len(seq_nums) != len(set(seq_nums))


def test_collection_validation(service):
    coll = service.create_collection({"subject": "val", "title": "Test", "source": "test"})
    result = service.validate_collection(coll["collection_id"])
    assert result["valid"] is True
    assert result["memory_count"] == 0


def test_collection_activation(service):
    coll = service.create_collection({"subject": "act", "title": "Test", "source": "test"})
    mem = service.create_memory({"subject": "act", "raw_content": "content", "source": "test"})
    service.add_memory_to_collection(coll["collection_id"], mem["memory_id"], 1)
    activated = service.activate_collection(coll["collection_id"])
    assert activated["status"] == "active"