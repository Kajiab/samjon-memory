"""Dashboard Overview metrics and filtered-list link tests.

Verifies CoreService.dashboard_stats counts, that each metric card links to a
filtered list matching the card, and that the scope/status filters actually
return the right rows.
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


def _seed(service):
    """Create a representative mix of standalone + collection data."""
    # Standalone: one draft, one active, one forgotten, one superseded.
    s_draft = service.create_memory({"subject": "s_draft", "raw_content": "c", "source": "t"})
    s_active = service.create_memory({"subject": "s_active", "raw_content": "c", "source": "t"})
    service.activate_memory(s_active["memory_id"])
    s_forgot = service.create_memory({"subject": "s_forgot", "raw_content": "c", "source": "t"})
    service.forget_memory(s_forgot["memory_id"])
    s_super = service.create_memory({"subject": "s_super", "raw_content": "c", "source": "t"})
    repl = service.create_memory({"subject": "repl", "raw_content": "c", "source": "t"})
    service.supersede_memory(s_super["memory_id"], repl["memory_id"])


# ---------------------------------------------------------------------------
# CoreService.dashboard_stats counts
# ---------------------------------------------------------------------------

def test_dashboard_stats_counts(service):
    _seed(service)
    draft_coll = service.create_collection({"subject": "cd", "title": "CD", "source": "t"})
    active_coll = service.create_collection({"subject": "ca", "title": "CA", "source": "t"})
    sec_draft = service.create_memory({"subject": "sec_draft", "raw_content": "c", "source": "t"})
    sec_active = service.create_memory({"subject": "sec_active", "raw_content": "c", "source": "t"})
    service.add_memory_to_collection(draft_coll["collection_id"], sec_draft["memory_id"], 1)
    service.add_memory_to_collection(active_coll["collection_id"], sec_active["memory_id"], 1)
    service.activate_collection(active_coll["collection_id"])
    service.activate_memory(sec_active["memory_id"])

    stats = service.dashboard_stats()

    # Standalone: draft(2: s_draft + repl) + active(1) + forgotten(1) + superseded(1) = 5
    assert stats["standalone_total"] == 5
    assert stats["standalone_draft"] == 2
    assert stats["standalone_active"] == 1
    assert stats["standalone_superseded"] == 1
    assert stats["standalone_forgotten"] == 1
    # Collections: 2 collections, one draft, one active.
    assert stats["collections_total"] == 2
    assert stats["collections_draft"] == 1
    assert stats["collections_active"] == 1
    # Collection sections: the two memories attached to collections.
    assert stats["collection_sections_total"] == 2
    # Total facts = standalone(5) + sections(2) = 7
    assert stats["total_facts"] == 7
    # Active knowledge = active standalone(1) + active section in active collection(1) = 2
    assert stats["active_knowledge"] == 2


def test_dashboard_stats_invalid_collections(service):
    service.create_collection({"subject": "g", "title": "Good", "source": "t"})
    service.create_collection({"subject": "b", "title": "Bad", "source": "t", "expected_item_count": 3})
    stats = service.dashboard_stats()
    assert stats["invalid_collections"] == 1


# ---------------------------------------------------------------------------
# Portal metric links and filtered lists
# ---------------------------------------------------------------------------

def test_dashboard_metric_links(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    _seed(svc)
    body = client.get("/portal/").text
    assert 'href="/portal/memories?scope=standalone"' in body
    assert 'href="/portal/memories?scope=standalone&amp;status=draft"' in body
    assert 'href="/portal/memories?scope=standalone&amp;status=active"' in body
    assert 'href="/portal/memories?scope=standalone&amp;status=superseded"' in body
    assert 'href="/portal/memories?scope=standalone&amp;status=forgotten"' in body
    assert 'href="/portal/collections"' in body
    assert 'href="/portal/collections?status=draft"' in body
    assert 'href="/portal/collections?status=active"' in body
    assert 'href="/portal/memories?scope=collection"' in body
    assert 'href="/portal/collections?invalid=1"' in body
    assert 'href="/portal/memories?scope=active_knowledge"' in body
    assert 'href="/portal/memories"' in body  # Total Facts
    # Tooltips / descriptors present to clarify no double counting.
    assert "Standalone memories + collection sections" in body
    assert "Active standalone memories" in body


def test_memory_list_scope_standalone(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    svc.create_memory({"subject": "stand-alone-name", "raw_content": "c", "source": "t"})
    coll = svc.create_collection({"subject": "col", "title": "Col", "source": "t"})
    section = svc.create_memory({"subject": "section-name", "raw_content": "c", "source": "t"})
    svc.add_memory_to_collection(coll["collection_id"], section["memory_id"], 1)

    body = client.get("/portal/memories?scope=standalone").text
    assert "stand-alone-name" in body
    assert "section-name" not in body

    body2 = client.get("/portal/memories?scope=collection").text
    assert "section-name" in body2
    assert "stand-alone-name" not in body2


def test_memory_list_status_scope_combined(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    draft = svc.create_memory({"subject": "draft-mem", "raw_content": "c", "source": "t"})
    active = svc.create_memory({"subject": "active-mem", "raw_content": "c", "source": "t"})
    svc.activate_memory(active["memory_id"])
    body = client.get("/portal/memories?scope=standalone&status=active").text
    assert "active-mem" in body
    assert "draft-mem" not in body


def test_memory_list_active_knowledge(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    standalone = svc.create_memory({"subject": "know-stand", "raw_content": "c", "source": "t"})
    svc.activate_memory(standalone["memory_id"])
    coll = svc.create_collection({"subject": "col", "title": "Col", "source": "t"})
    section = svc.create_memory({"subject": "know-draft-section", "raw_content": "c", "source": "t"})
    svc.add_memory_to_collection(coll["collection_id"], section["memory_id"], 1)
    # section stays draft -> excluded from active knowledge
    body = client.get("/portal/memories?scope=active_knowledge").text
    assert "know-stand" in body
    assert "know-draft-section" not in body


def test_collections_invalid_filter(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    svc.create_collection({"subject": "good", "title": "Good Title", "source": "t"})
    svc.create_collection({"subject": "bad", "title": "Bad Title", "source": "t", "expected_item_count": 3})
    body = client.get("/portal/collections?invalid=1").text
    assert "Bad Title" in body
    assert "Good Title" not in body
    assert "Showing collections that fail validation" in body


def test_collections_status_filter(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    svc.create_collection({"subject": "d", "title": "Draft Coll", "source": "t"})
    active = svc.create_collection({"subject": "a", "title": "Active Coll", "source": "t"})
    svc.activate_collection(active["collection_id"])
    body = client.get("/portal/collections?status=active").text
    assert "Active Coll" in body
    assert "Draft Coll" not in body