"""Add Section subject/scope inheritance tests.

Verifies that a new Collection section inherits subject/scope from the
Collection, uses title only as the section name, rejects client subject/scope
that disagree, and that moving an existing standalone Memory into a Collection
keeps its own subject.
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


# ---- CoreService behavior ----

def test_section_inherits_subject_from_collection(service):
    coll = _make_collection(service)
    section = service.add_section_to_collection(
        coll["collection_id"], {"title": "Watering", "raw_content": "c"})
    got = service.get_memory(section["memory_id"])
    assert got["subject"] == "garden"
    assert got["collection_id"] == coll["collection_id"]


def test_section_inherits_scope_from_collection(service):
    coll = _make_collection(service)
    section = service.add_section_to_collection(
        coll["collection_id"], {"title": "Watering", "raw_content": "c"})
    assert service.get_memory(section["memory_id"])["scope"] == "home"


def test_section_title_used_as_title_not_subject(service):
    coll = _make_collection(service)
    section = service.add_section_to_collection(
        coll["collection_id"], {"title": "Watering Schedule", "raw_content": "c"})
    got = service.get_memory(section["memory_id"])
    assert got["subject"] == "garden"           # not the title
    assert got["title"] == "Watering Schedule"  # title is the section name


def test_section_rejects_mismatched_subject(service):
    coll = _make_collection(service)
    with pytest.raises(ValidationError):
        service.add_section_to_collection(
            coll["collection_id"], {"title": "x", "raw_content": "c", "subject": "kitchen"})


def test_section_rejects_mismatched_scope(service):
    coll = _make_collection(service)
    with pytest.raises(ValidationError):
        service.add_section_to_collection(
            coll["collection_id"], {"title": "x", "raw_content": "c", "scope": "work"})


def test_section_accepts_matching_subject_scope(service):
    coll = _make_collection(service)
    section = service.add_section_to_collection(
        coll["collection_id"], {"title": "x", "raw_content": "c", "subject": "garden", "scope": "home"})
    got = service.get_memory(section["memory_id"])
    assert got["subject"] == "garden"
    assert got["scope"] == "home"


def test_multiple_sections_share_collection_subject(service):
    coll = _make_collection(service)
    s1 = service.add_section_to_collection(coll["collection_id"], {"title": "A", "raw_content": "a", "sequence_number": 1})
    s2 = service.add_section_to_collection(coll["collection_id"], {"title": "B", "raw_content": "b", "sequence_number": 2})
    m1 = service.get_memory(s1["memory_id"])
    m2 = service.get_memory(s2["memory_id"])
    assert m1["subject"] == "garden"
    assert m2["subject"] == "garden"


def test_resolver_eligible_subject_uses_collection_subject(service):
    # Resolver is not implemented; eligibility is evidenced by the projected
    # subject value that Resolver would inherit for a Collection section.
    coll = _make_collection(service)
    section = service.add_section_to_collection(coll["collection_id"], {"title": "Watering", "raw_content": "c"})
    got = service.get_memory(section["memory_id"])
    assert got["subject"] == coll["subject"]
    assert got["subject"] != "Watering"


def test_move_existing_memory_keeps_subject(service):
    coll = _make_collection(service)
    standalone = service.create_memory({"subject": "garden", "scope": "home", "raw_content": "c", "source": "t"})
    service.add_memory_to_collection(coll["collection_id"], standalone["memory_id"], 1)
    moved = service.get_memory(standalone["memory_id"])
    assert moved["subject"] == "garden"  # subject unchanged
    assert moved["collection_id"] == coll["collection_id"]


# ---- Portal ----

def test_add_section_form_has_no_subject_or_scope_fields(client, temp_db):
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = _make_collection(svc)
    body = client.get(f"/portal/collections/{coll['collection_id']}").text
    form = body.split('action="/portal/collections/{cid}/memories"'.replace("{cid}", coll["collection_id"]))[1].split("</form>")[0]
    assert 'name="subject"' not in form
    assert 'name="scope"' not in form
    assert 'name="title"' in form


def test_portal_add_section_inherits_subject_and_scope(client, temp_db):
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = _make_collection(svc)
    resp = client.post(
        f"/portal/collections/{coll['collection_id']}/memories",
        data={"title": "Watering", "raw_content": "water daily",
              "sequence_number": "1"},
        headers={"Origin": "http://localhost:8100"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    (section,) = svc.get_collection_memories(coll["collection_id"])
    assert section["subject"] == "garden"
    assert section["scope"] == "home"
    assert section["title"] == "Watering"
    assert section["collection_id"] == coll["collection_id"]