"""Regression: Portal Add Section -> Activate leaves every Section active.

Exercises the exact runtime path the browser uses (Portal routes -> CoreService)
and reads the result back from a separate CoreService instance so the assertion
reflects committed database state, not in-process cache.
"""
import os
import re

os.environ.setdefault("SAMJON_PORTAL_USERNAME", "portal-admin")
os.environ.setdefault("SAMJON_PORTAL_PASSWORD", "portal-secret")
os.environ.setdefault("SAMJON_PORTAL_ALLOWED_ORIGINS", "http://localhost:8100,http://127.0.0.1:8100")

import pytest
from fastapi.testclient import TestClient

from samjon_memory.core.main import app
from samjon_memory.core.service import CoreService


@pytest.fixture
def client(temp_db):
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    return c


def _sid(location):
    m = re.search(r"/portal/collections/([^/?]+)", location)
    assert m, location
    return m.group(1)


def _create_through_portal(client, subject="garden", expected=2):
    resp = client.post("/portal/collections", data={
        "subject": subject, "title": "Garden Guide", "scope": "home",
        "source": "test", "expected_item_count": str(expected),
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    return _sid(resp.headers.get("location", ""))


def _add_section_through_portal(client, cid, title, seq):
    resp = client.post(f"/portal/collections/{cid}/memories", data={
        "title": title, "raw_content": title, "sequence_number": str(seq),
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303


def test_portal_add_and_activate_leaves_all_sections_active(client, temp_db):
    # 1. Create Collection through Portal
    cid = _create_through_portal(client)
    # 2. Add Sections through Portal
    _add_section_through_portal(client, cid, "Watering", 1)
    _add_section_through_portal(client, cid, "Soil", 2)
    # 3. Activate through Portal
    resp = client.post(
        f"/portal/collections/{cid}/activate",
        headers={"Origin": "http://localhost:8100"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    # 4. Read from a fresh CoreService instance (fresh connection, committed DB).
    fresh = CoreService(database_path=temp_db)
    coll = fresh.get_collection(cid)
    assert coll["status"] == "active"
    sections = fresh.get_collection_memories(cid, limit=100)
    assert len(sections) == 2
    assert all(s["status"] == "active" for s in sections), \
        [f'{s["title"]}:{s["status"]}' for s in sections]


def test_activate_more_sections_than_default_list_limit(client, temp_db):
    # > DEFAULT_PAGE_SIZE (20): activation must process every section, not one page.
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({
        "subject": "big", "title": "Big", "scope": "home",
        "source": "test", "expected_item_count": 25,
    })
    for i in range(25):
        svc.add_section_to_collection(
            coll["collection_id"], {"title": f"S{i}", "raw_content": "c", "sequence_number": i + 1})
    resp = client.post(
        f"/portal/collections/{coll['collection_id']}/activate",
        headers={"Origin": "http://localhost:8100"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    fresh = CoreService(database_path=temp_db)
    sections = fresh.get_collection_memories(coll["collection_id"], limit=100)
    assert len(sections) == 25
    assert all(s["status"] == "active" for s in sections), \
        [f'{s["title"]}:{s["status"]}' for s in sections]