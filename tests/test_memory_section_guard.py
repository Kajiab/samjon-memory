"""Memory section subject/scope consistency tests (Bug 2).

Verifies that a standalone Memory may change its subject/scope, but a
Collection section cannot (subject/scope always match the Collection), that a
rejected update changes nothing, and that the Portal edit form and the REST
PATCH cannot bypass the CoreService guard.
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


def _add_section(service, coll_id, title="A"):
    return service.add_section_to_collection(coll_id, {"title": title, "raw_content": "c"})


def test_standalone_memory_can_change_subject_scope(service):
    mem = service.create_memory({"subject": "old", "scope": "household", "raw_content": "c", "source": "t"})
    updated = service.update_memory(mem["memory_id"], {"subject": "new", "scope": "work"})
    assert updated["subject"] == "new"
    assert updated["scope"] == "work"


def test_section_change_subject_rejected(service):
    coll = _make_collection(service)
    section = _add_section(service, coll["collection_id"])
    with pytest.raises(ValidationError):
        service.update_memory(section["memory_id"], {"subject": "other"})


def test_section_change_scope_rejected(service):
    coll = _make_collection(service)
    section = _add_section(service, coll["collection_id"])
    with pytest.raises(ValidationError):
        service.update_memory(section["memory_id"], {"scope": "work"})


def test_section_same_value_allowed(service):
    coll = _make_collection(service)
    section = _add_section(service, coll["collection_id"])
    updated = service.update_memory(section["memory_id"], {"subject": "garden", "scope": "home"})
    assert updated["subject"] == "garden"
    assert updated["scope"] == "home"


def test_rejected_section_update_changes_nothing(service):
    coll = _make_collection(service)
    section = _add_section(service, coll["collection_id"])
    v_before = section["version"]
    with pytest.raises(ValidationError):
        service.update_memory(section["memory_id"], {"subject": "other", "raw_content": "x"})
    got = service.get_memory(section["memory_id"])
    assert got["version"] == v_before
    assert got["subject"] == "garden"
    assert got["raw_content"] == "c"
    # No memory_update audit was written for the rejected update.
    assert [r["action"] for r in service.get_audit_records(entity_id=section["memory_id"])] \
        .count("memory_update") == 0


def test_section_edit_allows_other_fields_and_keeps_subject(service):
    # Resolver projection stays consistent: subject/scope remain Collection-aligned.
    coll = _make_collection(service)
    section = _add_section(service, coll["collection_id"])
    service.update_memory(section["memory_id"], {
        "title": "Renamed", "memory_type": "note", "raw_content": "new",
        "structured_value_json": '{"k":1}',
    })
    got = service.get_memory(section["memory_id"])
    assert got["subject"] == "garden"
    assert got["scope"] == "home"
    assert got["title"] == "Renamed"
    assert got["raw_content"] == "new"


def test_portal_section_edit_has_no_editable_subject_scope(client, temp_db):
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = _make_collection(svc)
    section = _add_section(svc, coll["collection_id"])
    body = client.get(f"/portal/memories/{section['memory_id']}/edit").text
    assert 'name="subject"' not in body
    assert 'name="scope"' not in body
    assert "Inherited from the Collection" in body
    assert "garden" in body


def test_portal_standalone_edit_keeps_editable_subject_scope(client, temp_db):
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "stand", "raw_content": "c", "source": "t"})
    body = client.get(f"/portal/memories/{mem['memory_id']}/edit").text
    assert 'name="subject"' in body
    assert 'name="scope"' in body


def test_rest_patch_cannot_change_section_subject(client, temp_db, monkeypatch):
    import samjon_memory.api.memories as memories_api
    real = memories_api.CoreService
    monkeypatch.setattr(memories_api, "CoreService", lambda: real(database_path=temp_db))
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = _make_collection(svc)
    section = _add_section(svc, coll["collection_id"])
    resp_raised = False
    try:
        client.patch(
            f"/api/v1/core/memories/{section['memory_id']}",
            json={"subject": "other"},
        )
    except ValidationError:
        resp_raised = True
    assert resp_raised is True  # REST PATCH cannot bypass the CoreService guard
    assert svc.get_memory(section["memory_id"])["subject"] == "garden"