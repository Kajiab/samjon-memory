"""Regression: adding a Section to an Active Collection reopens it (draft).

Adding a new Section to an Active Collection must revert the Collection to
draft (version+1, audit) so that a later Activate re-validates and activates
the new Section. Covers the CoreService, Portal, and REST entry points.
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
        "subject": "garden", "title": "G", "scope": "home", "source": "t",
    })


def test_add_section_to_active_collection_reopens_to_draft(service):
    coll = _make_collection(service)
    service.add_section_to_collection(coll["collection_id"], {"title": "A", "raw_content": "a"})
    service.activate_collection(coll["collection_id"])
    active_version = service.get_collection(coll["collection_id"])["version"]
    section = service.add_section_to_collection(coll["collection_id"], {"title": "B", "raw_content": "b"})
    coll_after = service.get_collection(coll["collection_id"])
    assert coll_after["status"] == "draft"                      # reopened
    assert coll_after["version"] == active_version + 1           # version bumped once
    assert service.get_memory(section["memory_id"])["status"] == "draft"  # new section draft
    assert len(service.get_audit_records(entity_id=coll["collection_id"], action="collection_reopened")) == 1


def test_portal_add_section_reopens_active_collection(client, temp_db):
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = _make_collection(svc)
    svc.add_section_to_collection(coll["collection_id"], {"title": "A", "raw_content": "a"})
    svc.activate_collection(coll["collection_id"])
    resp = client.post(
        f"/portal/collections/{coll['collection_id']}/memories",
        data={"title": "B", "raw_content": "b"},
        headers={"Origin": "http://localhost:8100"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert svc.get_collection(coll["collection_id"])["status"] == "draft"


def test_rest_add_section_reopens_active_collection(client, temp_db, monkeypatch):
    import samjon_memory.api.collections as coll_api
    real = coll_api.CoreService
    monkeypatch.setattr(coll_api, "CoreService", lambda: real(database_path=temp_db))
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = _make_collection(svc)
    svc.add_section_to_collection(coll["collection_id"], {"title": "A", "raw_content": "a"})
    svc.activate_collection(coll["collection_id"])
    resp = client.post(
        f"/api/v1/core/collections/{coll['collection_id']}/memories",
        json={"title": "B", "raw_content": "b"},
    )
    assert resp.status_code == 200
    assert svc.get_collection(coll["collection_id"])["status"] == "draft"
    section_b = [s for s in svc.get_collection_memories(coll["collection_id"]) if s["title"] == "B"][0]
    assert section_b["status"] == "draft"


def test_reactivate_activates_collection_and_new_section_active_not_bumped(service):
    coll = _make_collection(service)
    s1 = service.add_section_to_collection(coll["collection_id"], {"title": "A", "raw_content": "a"})
    service.add_section_to_collection(coll["collection_id"], {"title": "B", "raw_content": "b"})
    service.activate_collection(coll["collection_id"])
    v1_after_first = service.get_memory(s1["memory_id"])["version"]  # active
    s3 = service.add_section_to_collection(coll["collection_id"], {"title": "C", "raw_content": "c"})  # reopens
    service.activate_collection(coll["collection_id"])  # reactivate
    coll = service.get_collection(coll["collection_id"])
    assert coll["status"] == "active"
    assert service.get_memory(s1["memory_id"])["version"] == v1_after_first  # existing active: no bump
    assert service.get_memory(s3["memory_id"])["status"] == "active"         # new section activated
    assert service.get_memory(s3["memory_id"])["version"] == 2               # create(1) + activate
    assert all(m["status"] == "active" for m in service.get_collection_memories(coll["collection_id"]))


def test_reactivation_idempotent_when_no_change(service):
    coll = _make_collection(service)
    service.add_section_to_collection(coll["collection_id"], {"title": "A", "raw_content": "a"})
    service.activate_collection(coll["collection_id"])
    v_coll = service.get_collection(coll["collection_id"])["version"]
    audits_before = len(service.get_audit_records(entity_id=coll["collection_id"], action="collection_activate"))
    result = service.activate_collection(coll["collection_id"])
    assert result["status"] == "active"
    assert service.get_collection(coll["collection_id"])["version"] == v_coll  # no version bump
    assert len(service.get_audit_records(entity_id=coll["collection_id"], action="collection_activate")) == audits_before


def test_reactivation_failure_rolls_back_collection_and_sections(service):
    coll = _make_collection(service)
    s1 = service.add_section_to_collection(coll["collection_id"], {"title": "A", "raw_content": "a"})
    s2 = service.add_section_to_collection(coll["collection_id"], {"title": "B", "raw_content": "b"})
    service.activate_collection(coll["collection_id"])
    v_s1 = service.get_memory(s1["memory_id"])["version"]
    s3 = service.add_section_to_collection(coll["collection_id"], {"title": "C", "raw_content": "c"})  # reopen
    coll_v_before = service.get_collection(coll["collection_id"])["version"]
    service.forget_memory(s3["memory_id"])  # invalid section -> activation rejected
    with pytest.raises(ValidationError):
        service.activate_collection(coll["collection_id"])
    assert service.get_collection(coll["collection_id"])["status"] == "draft"
    assert service.get_collection(coll["collection_id"])["version"] == coll_v_before
    assert service.get_memory(s1["memory_id"])["status"] == "active"
    assert service.get_memory(s1["memory_id"])["version"] == v_s1
    assert service.get_memory(s2["memory_id"])["status"] == "active"


def test_portal_shows_reopen_message(client, temp_db):
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = _make_collection(svc)
    svc.add_section_to_collection(coll["collection_id"], {"title": "A", "raw_content": "a"})
    svc.activate_collection(coll["collection_id"])
    svc.add_section_to_collection(coll["collection_id"], {"title": "B", "raw_content": "b"})  # reopens
    body = client.get(f"/portal/collections/{coll['collection_id']}").text
    assert "reopened for editing" in body
    assert "Activate to republish" in body