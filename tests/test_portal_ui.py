"""Focused Portal UI behavior tests (server-rendered markup).

These assert the user-friendly behaviors shipped in the Portal rewrite:
the dashboard, empty states, status badges, the Collection Editor progress
and assembled preview, disabled-until-valid Activate, destructive-action
confirmation, and no-side-effect Cancel links.
"""
import os

os.environ.setdefault("SAMJON_PORTAL_USERNAME", "portal-admin")
os.environ.setdefault("SAMJON_PORTAL_PASSWORD", "portal-secret")
os.environ.setdefault("SAMJON_PORTAL_ALLOWED_ORIGINS", "http://localhost:8100,http://127.0.0.1:8100")

import pytest
from fastapi.testclient import TestClient

from samjon_memory.core.main import app


@pytest.fixture
def client(temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    return c


# ---- Dashboard ----

def test_dashboard_requires_auth():
    c = TestClient(app)
    assert c.get("/portal/").status_code == 401


def test_dashboard_shows_quick_actions(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    svc.create_memory({"subject": "a", "raw_content": "c", "source": "t"})
    svc.create_collection({"subject": "col", "title": "Col", "source": "t"})
    resp = client.get("/portal/")
    assert resp.status_code == 200
    assert "Overview" in resp.text
    assert "Standalone Memories" in resp.text
    assert "Total Facts" in resp.text
    assert "Collections" in resp.text
    assert "Create Memory" in resp.text
    assert "Create Collection" in resp.text


# ---- Memory list ----

def test_memory_list_empty_state(client):
    resp = client.get("/portal/memories")
    assert resp.status_code == 200
    assert "No memories found yet" in resp.text


def test_memory_list_shows_status_badge(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    svc.create_memory({"subject": "badged", "raw_content": "c", "source": "t"})
    resp = client.get("/portal/memories")
    assert 'class="badge ' in resp.text


# ---- Collection Editor ----

def test_collection_detail_progress_and_preview(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({
        "subject": "prog", "title": "Prog", "source": "t", "expected_item_count": 2,
    })
    m1 = svc.create_memory({"subject": "Part 1", "raw_content": "hello world", "source": "t"})
    m2 = svc.create_memory({"subject": "Part 2", "raw_content": "goodbye world", "source": "t"})
    svc.add_memory_to_collection(coll["collection_id"], m1["memory_id"], 1)
    svc.add_memory_to_collection(coll["collection_id"], m2["memory_id"], 2)
    resp = client.get(f"/portal/collections/{coll['collection_id']}")
    assert resp.status_code == 200
    assert "Assembled preview" in resp.text
    assert "hello world" in resp.text
    assert "Expected Sections: 2" in resp.text
    assert "Current Sections: 2" in resp.text
    assert "Ready to activate" in resp.text
    assert 'class="progress-bar"' in resp.text


def test_collection_add_section_and_activate_disabled(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({
        "subject": "add", "title": "Add", "source": "t", "expected_item_count": 1,
    })
    resp = client.get(f"/portal/collections/{coll['collection_id']}")
    assert resp.status_code == 200
    assert "Add Section" in resp.text
    assert '<button type="submit" disabled>Activate</button>' in resp.text
    assert "Not ready to activate" in resp.text


def test_activate_enabled_when_valid(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({
        "subject": "ok", "title": "Ok", "source": "t", "expected_item_count": 1,
    })
    mem = svc.create_memory({"subject": "sec", "raw_content": "c", "source": "t"})
    svc.add_memory_to_collection(coll["collection_id"], mem["memory_id"], 1)
    resp = client.get(f"/portal/collections/{coll['collection_id']}")
    assert '<button type="submit" disabled>Activate</button>' not in resp.text


# ---- Confirmation & Cancel ----

def test_destructive_actions_have_confirmation(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "del", "raw_content": "c", "source": "t"})
    resp = client.get(f"/portal/memories/{mem['memory_id']}")
    assert resp.status_code == 200
    assert "onsubmit=\"return confirm(" in resp.text


def test_create_memory_cancel_is_navigation_link(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    before = len(svc.memories.list(limit=100))
    body = client.get("/portal/memories/create").text
    assert 'href="/portal/memories">Cancel</a>' in body
    assert len(svc.memories.list(limit=100)) == before


def test_memory_edit_carry_expected_version(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "v", "raw_content": "x", "source": "t"})
    body = client.get(f"/portal/memories/{mem['memory_id']}/edit").text
    assert f'name="expected_version" value="{mem["version"]}"' in body