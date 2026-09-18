"""Independent collection-memory editing regression test.

Proves that editing one memory inside a collection does not rewrite
the whole collection, and that unchanged memories retain their IDs,
versions, and content.
"""

import pytest
from samjon_memory.core.service import CoreService
from samjon_memory.errors import VersionConflict


def test_independent_collection_memory_edit(service):
    """Edit one middle memory in a collection; others are unchanged."""
    # 1. Create a draft collection
    coll = service.create_collection({
        "subject": "independent edit test",
        "title": "Independent Edit Test",
        "source": "test",
    })
    collection_id = coll["collection_id"]

    # 2. Add three ordered memories
    m1 = service.create_memory({
        "subject": "Memory One", "raw_content": "Content One", "source": "test",
        "collection_id": collection_id, "sequence_number": 1,
    })
    m2 = service.create_memory({
        "subject": "Memory Two", "raw_content": "Content Two", "source": "test",
        "collection_id": collection_id, "sequence_number": 2,
    })
    m3 = service.create_memory({
        "subject": "Memory Three", "raw_content": "Content Three", "source": "test",
        "collection_id": collection_id, "sequence_number": 3,
    })

    # Record original state
    m1_id, m1_ver, m1_content = m1["memory_id"], m1["version"], m1["raw_content"]
    m2_id, m2_ver, m2_content = m2["memory_id"], m2["version"], m2["raw_content"]
    m3_id, m3_ver, m3_content = m3["memory_id"], m3["version"], m3["raw_content"]

    # 3. Activate the collection
    activated = service.activate_collection(collection_id)
    assert activated["status"] == "active"
    coll_version_before = activated["version"]

    # 4. Update ONLY the middle memory using expected_version
    updated_m2 = service.update_memory(m2_id, {
        "subject": "Memory Two Updated",
        "raw_content": "Content Two Updated",
        "expected_version": m2_ver,
    })

    # 5. Middle memory content and version changed
    assert updated_m2["subject"] == "Memory Two Updated"
    assert updated_m2["raw_content"] == "Content Two Updated"
    assert updated_m2["version"] == m2_ver + 1

    # 6. Unchanged memories retain IDs, versions, and content
    unchanged_m1 = service.get_memory(m1_id)
    unchanged_m3 = service.get_memory(m3_id)
    assert unchanged_m1["memory_id"] == m1_id
    assert unchanged_m1["version"] == m1_ver
    assert unchanged_m1["raw_content"] == m1_content
    assert unchanged_m3["memory_id"] == m3_id
    assert unchanged_m3["version"] == m3_ver
    assert unchanged_m3["raw_content"] == m3_content

    # 7. Collection version does NOT change from memory edit (only structural changes increment it)
    coll_after = service.get_collection(collection_id)
    assert coll_after["version"] == coll_version_before

    # 8. Sequence order is preserved (all three sequence numbers present)
    memories = service.get_collection_memories(collection_id)
    seq_nums = sorted([m["sequence_number"] for m in memories if m["memory_id"] in (m1_id, m2_id, m3_id)])
    assert seq_nums == [1, 2, 3]

    # 9. Audit record identifies the changed memory
    audits = service.conn.execute(
        "SELECT * FROM audit_log WHERE entity_id=? AND action=?",
        (m2_id, "memory_update"),
    ).fetchall()
    assert len(audits) == 1


def test_collection_memory_edit_conflict(service):
    """Updating a collection memory with wrong expected_version raises ValueError."""
    coll = service.create_collection({
        "subject": "conflict test", "title": "Conflict Test", "source": "test",
    })
    m1 = service.create_memory({
        "subject": "M1", "raw_content": "C1", "source": "test",
        "collection_id": coll["collection_id"], "sequence_number": 1,
    })
    m2 = service.create_memory({
        "subject": "M2", "raw_content": "C2", "source": "test",
        "collection_id": coll["collection_id"], "sequence_number": 2,
    })
    service.activate_collection(coll["collection_id"])

    # m2 is at version 1; try updating with expected_version=2 (wrong)
    with pytest.raises(ValueError, match="VERSION_CONFLICT"):
        service.update_memory(m2["memory_id"], {
            "subject": "M2 Wrong", "expected_version": 2,
        })

    # m1 should be completely unaffected
    m1_after = service.get_memory(m1["memory_id"])
    assert m1_after["subject"] == "M1"
    assert m1_after["raw_content"] == "C1"
    assert m1_after["version"] == 1