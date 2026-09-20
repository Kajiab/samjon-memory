"""Core Portal Administration page tests.

Covers the /portal/admin page (auth, sections, nav), purge-eligibility
readiness, and navigation. The page reads only through CoreService.admin_stats.
"""
import os

os.environ.setdefault("SAMJON_PORTAL_USERNAME", "portal-admin")
os.environ.setdefault("SAMJON_PORTAL_PASSWORD", "portal-secret")
os.environ.setdefault("SAMJON_PORTAL_ALLOWED_ORIGINS", "http://localhost:8100,http://127.0.0.1:8100")

import pytest
from fastapi.testclient import TestClient

from samjon_memory.core.main import app
from samjon_memory.constants import CORE_SCHEMA_VERSION


@pytest.fixture
def client(temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    return c


def _forgotten_memory(svc, subject="gone", raw="c"):
    mem = svc.create_memory({"subject": subject, "raw_content": raw, "source": "t"})
    svc.forget_memory(mem["memory_id"])
    return svc.get_memory(mem["memory_id"])


def _backdate_memory(svc, memory_id, days=40):
    svc.conn.execute(
        "UPDATE memory SET forgotten_at = datetime('now', ?) WHERE memory_id=?",
        (f"-{days} days", memory_id),
    )
    svc.conn.commit()


# ---- Auth ----

def test_admin_requires_auth():
    c = TestClient(app)
    assert c.get("/portal/admin").status_code == 401


# ---- Page rendering + navigation ----

def test_admin_page_renders_sections(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    _forgotten_memory(svc)
    resp = client.get("/portal/admin")
    assert resp.status_code == 200
    body = resp.text
    assert "Administration" in body
    assert "Core schema version" in body
    assert CORE_SCHEMA_VERSION in body
    assert "Database status" in body
    assert "Forgotten memories" in body
    assert "Forgotten collections" in body
    assert "Ready to purge" in body
    assert "Pending retention" in body
    assert "Purged memories and collections" in body
    assert "Tombstones" in body
    assert "Audit rows" in body


def test_admin_navigation_present_everywhere(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    memories = client.get("/portal/memories").text
    assert 'href="/portal/admin"' in memories
    assert "Administration" in memories
    admin = client.get("/portal/admin").text
    assert 'href="/portal/admin"' in admin
    assert 'href="/portal/admin"' in client.get("/portal/").text


# ---- Forgotten items + purge eligibility ----

def test_admin_lists_forgotten_memories_and_collections(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = _forgotten_memory(svc, subject="gone-mem")
    coll = svc.create_collection({"subject": "col", "title": "Gone Coll", "source": "t"})
    svc.forget_collection(coll["collection_id"])
    body = client.get("/portal/admin").text
    assert "gone-mem" in body
    assert "Gone Coll" in body
    assert f'action="/portal/memories/{mem["memory_id"]}/restore"' in body
    assert f'action="/portal/collections/{coll["collection_id"]}/restore"' in body


def test_purge_disabled_until_retention(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    _forgotten_memory(svc)  # fresh -> not eligible
    body = client.get("/portal/admin").text
    assert "Pending" in body
    assert "disabled>Purge</button>" in body        # not yet eligible
    assert 'name="confirmation"' not in body         # no enabled purge form


def test_purge_enabled_when_retention_met(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = _forgotten_memory(svc)
    _backdate_memory(svc, mem["memory_id"])
    body = client.get("/portal/admin").text
    assert "Ready" in body
    assert 'name="confirmation"' in body             # type PURGE input present
    assert 'name="expected_version"' in body
    assert 'disabled>Purge</button>' not in body


def test_admin_stats_purge_eligibility(service):
    mem = _forgotten_memory(service)
    stats = service.admin_stats()
    row = next(r for r in stats["forgotten_memories"] if r["entity_id"] == mem["memory_id"])
    assert row["purge_eligible"] is False
    assert row["days_remaining"] >= 1
    _backdate_memory(service, mem["memory_id"])
    stats2 = service.admin_stats()
    row2 = next(r for r in stats2["forgotten_memories"] if r["entity_id"] == mem["memory_id"])
    assert row2["purge_eligible"] is True


def test_admin_shows_purged_and_tombstones(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = _forgotten_memory(svc)
    _backdate_memory(svc, mem["memory_id"])
    svc.purge_memory(mem["memory_id"], confirmation="PURGE", actor="admin")
    body = client.get("/portal/admin").text
    assert "Purged memories and collections" in body
    assert mem["subject"] in body  # purged row title retained
    stats = svc.admin_stats()
    assert stats["tombstone_count"] >= 1


def test_admin_page_view_creates_no_audit(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = _forgotten_memory(svc)
    audit_count = svc.admin_stats()["audit_count"]
    client.get("/portal/admin")
    client.get(f"/portal/memories/{mem['memory_id']}")  # page view
    assert svc.admin_stats()["audit_count"] == audit_count