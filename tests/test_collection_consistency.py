"""Collection subject/scope consistency tests.

Verifies that moving an existing Memory into a Collection requires a matching
subject/scope, that a rejected move changes nothing, that every section in a
Collection shares the Collection's subject/scope, and that a Collection with
existing sections cannot have its subject/scope changed.
"""
import os

os.environ.setdefault("SAMJON_PORTAL_USERNAME", "portal-admin")
os.environ.setdefault("SAMJON_PORTAL_PASSWORD", "portal-secret")
os.environ.setdefault("SAMJON_PORTAL_ALLOWED_ORIGINS", "http://localhost:8100,http://127.0.0.1:8100")

import pytest

from samjon_memory.core.service import CoreService
from samjon_memory.core.main import app
from samjon_memory.errors import ValidationError


@pytest.fixture
def client(temp_db):
    from fastapi.testclient import TestClient
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    return c


def _make_collection(service):
    return service.create_collection({
        "subject": "garden", "title": "Garden Guide", "scope": "home", "source": "t",
    })


def test_move_existing_with_matching_subject_scope_succeeds(service):
    coll = _make_collection(service)
    standalone = service.create_memory({"subject": "garden", "scope": "home", "raw_content": "c", "source": "t"})
    result = service.add_memory_to_collection(coll["collection_id"], standalone["memory_id"], 1)
    assert result["added"] is True
    moved = service.get_memory(standalone["memory_id"])
    assert moved["collection_id"] == coll["collection_id"]
    assert moved["subject"] == "garden"  # unchanged


def test_move_rejects_mismatched_subject(service):
    coll = _make_collection(service)
    standalone = service.create_memory({"subject": "other-subject", "scope": "home", "raw_content": "c", "source": "t"})
    with pytest.raises(ValidationError):
        service.add_memory_to_collection(coll["collection_id"], standalone["memory_id"], 1)


def test_move_rejects_mismatched_scope(service):
    coll = _make_collection(service)
    standalone = service.create_memory({"subject": "garden", "scope": "work", "raw_content": "c", "source": "t"})
    with pytest.raises(ValidationError):
        service.add_memory_to_collection(coll["collection_id"], standalone["memory_id"], 1)


def test_rejected_move_changes_nothing(service):
    coll = _make_collection(service)
    standalone = service.create_memory({"subject": "other-subject", "scope": "home", "raw_content": "c", "source": "t"})
    version_before = standalone["version"]
    coll_version_before = coll["version"]
    with pytest.raises(ValidationError):
        service.add_memory_to_collection(coll["collection_id"], standalone["memory_id"], 5)
    got = service.get_memory(standalone["memory_id"])
    assert got["collection_id"] is None  # still standalone
    assert got["sequence_number"] is None
    assert got["version"] == version_before
    assert service.get_collection(coll["collection_id"])["version"] == coll_version_before
    # Ordering unchanged: no section added.
    assert len(service.get_collection_memories(coll["collection_id"])) == 0


def test_collection_sections_match_subject_scope(service):
    coll = _make_collection(service)
    service.add_section_to_collection(coll["collection_id"], {"title": "A", "raw_content": "a"})
    moved = service.create_memory({"subject": "garden", "scope": "home", "raw_content": "c", "source": "t"})
    service.add_memory_to_collection(coll["collection_id"], moved["memory_id"], 2)
    for mem in service.get_collection_memories(coll["collection_id"]):
        assert mem["subject"] == "garden"
        assert mem["scope"] == "home"


def test_update_collection_subject_rejected_when_sections_exist(service):
    coll = _make_collection(service)
    service.add_section_to_collection(coll["collection_id"], {"title": "A", "raw_content": "a"})
    with pytest.raises(ValidationError):
        service.update_collection(coll["collection_id"], {"subject": "new-subject"})


def test_update_collection_scope_rejected_when_sections_exist(service):
    coll = _make_collection(service)
    service.add_section_to_collection(coll["collection_id"], {"title": "A", "raw_content": "a"})
    with pytest.raises(ValidationError):
        service.update_collection(coll["collection_id"], {"scope": "work"})


def test_update_collection_title_allowed_when_sections_exist(service):
    coll = _make_collection(service)
    service.add_section_to_collection(coll["collection_id"], {"title": "A", "raw_content": "a"})
    updated = service.update_collection(coll["collection_id"], {"title": "Renamed"})
    assert updated["title"] == "Renamed"
    assert updated["collection_id"] == coll["collection_id"]