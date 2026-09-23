"""Independent collection-memory editing regression test.

Proves that editing one collection section does not rewrite the whole
collection, unchanged sections retain IDs/versions/content, and that a
collection section's subject/scope always match its Collection (activation
activates draft sections and bumps their version).
"""

import pytest
from samjon_memory.core.service import CoreService
from samjon_memory.errors import VersionConflict


def test_independent_collection_memory_edit(service):
    """Edit one section in a collection; the collection and other sections are unchanged."""
    coll = service.create_collection({
        "subject": "independent edit test", "title": "Independent Edit Test", "source": "test",
    })
    collection_id = coll["collection_id"]

    # Add three sections; each inherits the Collection subject with a distinct title.
    m1 = service.create_memory({
        "subject": "independent edit test", "title": "Memory One",
        "raw_content": "Content One", "source": "test",
        "collection_id": collection_id, "sequence_number": 1,
    })
    m2 = service.create_memory({
        "subject": "independent edit test", "title": "Memory Two",
        "raw_content": "Content Two", "source": "test",
        "collection_id": collection_id, "sequence_number": 2,
    })
    m3 = service.create_memory({
        "subject": "independent edit test", "title": "Memory Three",
        "raw_content": "Content Three", "source": "test",
        "collection_id": collection_id, "sequence_number": 3,
    })

    m1_id, m1_content = m1["memory_id"], m1["raw_content"]
    m3_id, m3_content = m3["memory_id"], m3["raw_content"]

    # Activate the collection; all draft sections become active (version+1).
    activated = service.activate_collection(collection_id)
    assert activated["status"] == "active"
    post = {m["memory_id"]: m for m in service.get_collection_memories(collection_id)}
    assert all(m["status"] == "active" for m in post.values())
    coll_version_before = activated["version"]
    m1_ver = post[m1_id]["version"]
    m2_ver = post[m2["memory_id"]]["version"]
    m3_ver = post[m3_id]["version"]

    # Update ONLY the middle section (title/raw_content), keeping subject.
    updated_m2 = service.update_memory(m2["memory_id"], {
        "title": "Memory Two Updated",
        "raw_content": "Content Two Updated",
        "expected_version": m2_ver,
    })
    assert updated_m2["subject"] == "independent edit test"
    assert updated_m2["title"] == "Memory Two Updated"
    assert updated_m2["raw_content"] == "Content Two Updated"
    assert updated_m2["version"] == m2_ver + 1

    # Unchanged sections retain IDs, versions, and content.
    unchanged_m1 = service.get_memory(m1_id)
    unchanged_m3 = service.get_memory(m3_id)
    assert unchanged_m1["memory_id"] == m1_id
    assert unchanged_m1["version"] == m1_ver
    assert unchanged_m1["raw_content"] == m1_content
    assert unchanged_m3["memory_id"] == m3_id
    assert unchanged_m3["version"] == m3_ver
    assert unchanged_m3["raw_content"] == m3_content

    # Collection version does NOT change from a section edit.
    assert service.get_collection(collection_id)["version"] == coll_version_before

    # Sequence order preserved.
    memories = service.get_collection_memories(collection_id)
    seq_nums = sorted([m["sequence_number"] for m in memories if m["sequence_number"] is not None])
    assert seq_nums == [1, 2, 3]

    # Audit record identifies the changed section.
    audits = service.conn.execute(
        "SELECT * FROM audit_log WHERE entity_id=? AND action=?",
        (m2["memory_id"], "memory_update"),
    ).fetchall()
    assert len(audits) == 1


def test_collection_memory_edit_conflict(service):
    """Updating a collection section with a stale expected_version is a conflict."""
    coll = service.create_collection({
        "subject": "conflict test", "title": "Conflict Test", "source": "test",
    })
    m1 = service.create_memory({
        "subject": "conflict test", "title": "M1", "raw_content": "C1", "source": "test",
        "collection_id": coll["collection_id"], "sequence_number": 1,
    })
    m2 = service.create_memory({
        "subject": "conflict test", "title": "M2", "raw_content": "C2", "source": "test",
        "collection_id": coll["collection_id"], "sequence_number": 2,
    })
    service.activate_collection(coll["collection_id"])
    # m2 is now at version 2 after activation; expected_version=3 is stale.
    with pytest.raises(ValueError, match="VERSION_CONFLICT"):
        service.update_memory(m2["memory_id"], {"title": "M2 Wrong", "expected_version": 3})

    # m1 is completely unaffected.
    m1_after = service.get_memory(m1["memory_id"])
    assert m1_after["subject"] == "conflict test"
    assert m1_after["raw_content"] == "C1"
    assert m1_after["version"] == 2  # bumped to active by activation