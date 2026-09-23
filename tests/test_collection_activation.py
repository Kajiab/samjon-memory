"""Collection activation lifecycle tests.

Verifies that activation validates sections first, activates all draft
sections (+1 version) and rolls back on failure, leaves active sections
untouched, bumps the Collection version once, and rejects collections that
contain forgotten / superseded / purged sections.
"""
import os

os.environ.setdefault("SAMJON_PORTAL_USERNAME", "portal-admin")
os.environ.setdefault("SAMJON_PORTAL_PASSWORD", "portal-secret")
os.environ.setdefault("SAMJON_PORTAL_ALLOWED_ORIGINS", "http://localhost:8100,http://127.0.0.1:8100")

import pytest

from samjon_memory.core.service import CoreService
from samjon_memory.errors import ValidationError


@pytest.fixture
def client(temp_db):
    from fastapi.testclient import TestClient
    from samjon_memory.core.main import app
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    return c


def _make_collection(service, expected_count=None):
    return service.create_collection({
        "subject": "garden", "title": "Garden Guide", "scope": "home",
        "source": "t", "expected_item_count": expected_count,
    })


def _add_section(service, coll_id, title, seq=None):
    data = {"title": title, "raw_content": title.lower()}
    if seq is not None:
        data["sequence_number"] = seq
    return service.add_section_to_collection(coll_id, data)


def test_activate_makes_all_draft_sections_active(service):
    coll = _make_collection(service, expected_count=2)
    s1 = _add_section(service, coll["collection_id"], "A", 1)
    s2 = _add_section(service, coll["collection_id"], "B", 2)
    activated = service.activate_collection(coll["collection_id"])
    assert activated["status"] == "active"
    assert service.get_memory(s1["memory_id"])["status"] == "active"
    assert service.get_memory(s2["memory_id"])["status"] == "active"
    assert service.get_memory(s1["memory_id"])["version"] == 2  # +1 from activation
    assert service.get_memory(s2["memory_id"])["version"] == 2


def test_activation_bumps_draft_but_not_active_sections(service):
    coll = _make_collection(service)
    s1 = _add_section(service, coll["collection_id"], "A", 1)
    s2 = _add_section(service, coll["collection_id"], "B", 2)
    # s1 is already active before collection activation.
    service.activate_memory(s1["memory_id"])
    v1_before = service.get_memory(s1["memory_id"])["version"]  # 2 (create 1 + activate 1)
    v2_before = service.get_memory(s2["memory_id"])["version"]  # 1
    coll_v_before = service.get_collection(coll["collection_id"])["version"]  # 1
    service.activate_collection(coll["collection_id"])
    assert service.get_memory(s1["memory_id"])["version"] == v1_before  # active unchanged
    assert service.get_memory(s2["memory_id"])["version"] == v2_before + 1  # draft bumped
    assert service.get_collection(coll["collection_id"])["version"] == coll_v_before + 1  # single bump
    # No draft sections remain in the active collection.
    assert all(m["status"] == "active" for m in service.get_collection_memories(coll["collection_id"]))


def test_activate_accepts_mixed_active_and_draft(service):
    coll = _make_collection(service)
    s1 = _add_section(service, coll["collection_id"], "A", 1)
    s2 = _add_section(service, coll["collection_id"], "B", 2)
    service.activate_memory(s1["memory_id"])
    service.activate_collection(coll["collection_id"])
    assert service.get_collection(coll["collection_id"])["status"] == "active"
    assert all(m["status"] == "active" for m in service.get_collection_memories(coll["collection_id"]))


def test_activate_rejects_forgotten_section(service):
    coll = _make_collection(service)
    s1 = _add_section(service, coll["collection_id"], "A", 1)
    s2 = _add_section(service, coll["collection_id"], "B", 2)
    service.forget_memory(s2["memory_id"])
    with pytest.raises(ValidationError):
        service.activate_collection(coll["collection_id"])
    assert service.get_collection(coll["collection_id"])["status"] == "draft"


def test_activate_rejects_superseded_section(service):
    coll = _make_collection(service)
    s1 = _add_section(service, coll["collection_id"], "A", 1)
    s2 = _add_section(service, coll["collection_id"], "B", 2)
    repl = service.create_memory({"subject": "garden", "raw_content": "r", "source": "t"})
    service.supersede_memory(s2["memory_id"], repl["memory_id"])
    with pytest.raises(ValidationError):
        service.activate_collection(coll["collection_id"])


def test_activate_rejects_purged_section(service):
    coll = _make_collection(service)
    s1 = _add_section(service, coll["collection_id"], "A", 1)
    s2 = _add_section(service, coll["collection_id"], "B", 2)
    service.forget_memory(s2["memory_id"])
    service.conn.execute(
        "UPDATE memory SET forgotten_at = datetime('now','-40 days') WHERE memory_id=?",
        (s2["memory_id"],),
    )
    service.conn.commit()
    service.purge_memory(s2["memory_id"], confirmation="PURGE", actor="admin")
    with pytest.raises(ValidationError):
        service.activate_collection(coll["collection_id"])


def test_rejected_activation_changes_nothing(service):
    """A failed activation leaves the Collection and all sections unchanged."""
    coll = _make_collection(service)
    s1 = _add_section(service, coll["collection_id"], "A", 1)
    s2 = _add_section(service, coll["collection_id"], "B", 2)
    service.forget_memory(s2["memory_id"])
    v1_before = service.get_memory(s1["memory_id"])["version"]
    v2_before = service.get_memory(s2["memory_id"])["version"]
    coll_v_before = service.get_collection(coll["collection_id"])["version"]
    with pytest.raises(ValidationError):
        service.activate_collection(coll["collection_id"])
    assert service.get_collection(coll["collection_id"])["status"] == "draft"
    assert service.get_collection(coll["collection_id"])["version"] == coll_v_before
    assert service.get_memory(s1["memory_id"])["status"] == "draft"
    assert service.get_memory(s1["memory_id"])["version"] == v1_before
    assert service.get_memory(s2["memory_id"])["version"] == v2_before