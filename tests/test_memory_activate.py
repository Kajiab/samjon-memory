"""Standalone Memory activation tests.

Covers the CoreService activate_memory operation, Portal UI button visibility,
Portal auth/Origin guards, and REST route registration (OpenAPI).
"""
import os

os.environ.setdefault("SAMJON_PORTAL_USERNAME", "portal-admin")
os.environ.setdefault("SAMJON_PORTAL_PASSWORD", "portal-secret")
os.environ.setdefault("SAMJON_PORTAL_ALLOWED_ORIGINS", "http://localhost:8100,http://127.0.0.1:8100")

import pytest
from fastapi.testclient import TestClient

from samjon_memory.core.main import app
from samjon_memory.errors import ValidationError, VersionConflict


@pytest.fixture
def client(temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    return c


# ---------------------------------------------------------------------------
# CoreService behavior
# ---------------------------------------------------------------------------

def test_activate_draft_succeeds(service):
    mem = service.create_memory({"subject": "act", "raw_content": "c", "source": "t"})
    assert mem["status"] == "draft"
    result = service.activate_memory(mem["memory_id"])
    assert result["status"] == "active"


def test_activate_increments_version(service):
    mem = service.create_memory({"subject": "v", "raw_content": "c", "source": "t"})
    service.activate_memory(mem["memory_id"])
    activated = service.get_memory(mem["memory_id"])
    assert activated["version"] == mem["version"] + 1
    assert activated["status"] == "active"


def test_activate_creates_audit(service):
    mem = service.create_memory({"subject": "aud", "raw_content": "c", "source": "t"})
    service.activate_memory(mem["memory_id"])
    records = service.get_audit_records(entity_id=mem["memory_id"], action="memory_activate")
    assert len(records) == 1
    assert records[0]["action"] == "memory_activate"
    assert records[0]["entity_type"] == "memory"


def test_activate_stale_expected_version_conflict(service):
    mem = service.create_memory({"subject": "stale", "raw_content": "c", "source": "t"})
    with pytest.raises(VersionConflict) as e:
        service.activate_memory(mem["memory_id"], expected_version=999)
    assert e.value.status_code == 409


def test_activate_active_is_idempotent(service):
    mem = service.create_memory({"subject": "idem", "raw_content": "c", "source": "t"})
    first = service.activate_memory(mem["memory_id"])
    second = service.activate_memory(mem["memory_id"])
    assert first["status"] == "active"
    assert second["version"] == first["version"]


def test_activate_superseded_rejected(service):
    mem = service.create_memory({"subject": "sup", "raw_content": "c", "source": "t"})
    repl = service.create_memory({"subject": "new", "raw_content": "c", "source": "t"})
    service.supersede_memory(mem["memory_id"], repl["memory_id"])
    with pytest.raises(ValidationError):
        service.activate_memory(mem["memory_id"])


def test_activate_forgotten_rejected(service):
    mem = service.create_memory({"subject": "for", "raw_content": "c", "source": "t"})
    service.forget_memory(mem["memory_id"])
    with pytest.raises(ValidationError):
        service.activate_memory(mem["memory_id"])


# ---------------------------------------------------------------------------
# REST route registration (OpenAPI)
# ---------------------------------------------------------------------------

def test_activate_route_registered_in_openapi():
    paths = app.openapi()["paths"]
    assert "/api/v1/core/memories/{memory_id}/activate" in paths
    assert "post" in paths["/api/v1/core/memories/{memory_id}/activate"]


# ---------------------------------------------------------------------------
# Portal UI
# ---------------------------------------------------------------------------

def test_draft_memory_shows_activate(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "d", "raw_content": "c", "source": "t"})
    body = client.get(f"/portal/memories/{mem['memory_id']}").text
    assert f'action="/portal/memories/{mem["memory_id"]}/activate"' in body
    assert 'name="expected_version"' in body
    assert ">Activate</button>" in body
    # Viewing the page is a no-op: no version bump, no activate audit record.
    still = svc.get_memory(mem["memory_id"])
    assert still["version"] == 1
    assert svc.get_audit_records(entity_id=mem["memory_id"], action="memory_activate") == []


def test_active_memory_hides_activate(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "a", "raw_content": "c", "source": "t"})
    svc.activate_memory(mem["memory_id"])
    body = client.get(f"/portal/memories/{mem['memory_id']}").text
    assert f'action="/portal/memories/{mem["memory_id"]}/activate"' not in body


def test_superseded_and_forgotten_hide_activate(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "sup", "raw_content": "c", "source": "t"})
    repl = svc.create_memory({"subject": "new", "raw_content": "c", "source": "t"})
    svc.supersede_memory(mem["memory_id"], repl["memory_id"])
    assert f'action="/portal/memories/{mem["memory_id"]}/activate"' not in client.get(
        f"/portal/memories/{mem['memory_id']}"
    ).text
    forgotten = svc.create_memory({"subject": "for", "raw_content": "c", "source": "t"})
    svc.forget_memory(forgotten["memory_id"])
    assert f'action="/portal/memories/{forgotten["memory_id"]}/activate"' not in client.get(
        f"/portal/memories/{forgotten['memory_id']}"
    ).text


def test_portal_activate_success_messages(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "p", "raw_content": "c", "source": "t"})
    resp = client.post(
        f"/portal/memories/{mem['memory_id']}/activate",
        headers={"Origin": "http://localhost:8100"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert svc.get_memory(mem["memory_id"])["status"] == "active"
    assert svc.get_memory(mem["memory_id"])["version"] == mem["version"] + 1
    assert len(svc.get_audit_records(entity_id=mem["memory_id"], action="memory_activate")) == 1
    detail = client.get(f"/portal/memories/{mem['memory_id']}?message=memory_activated")
    assert "Memory activated" in detail.text


def test_activate_requires_credentials():
    c = TestClient(app)
    resp = c.post("/portal/memories/mem-nonexistent/activate")
    assert resp.status_code == 401


def test_activate_rejects_unapproved_origin(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "w", "raw_content": "c", "source": "t"})
    resp = client.post(
        f"/portal/memories/{mem['memory_id']}/activate",
        headers={"Origin": "http://evil.example"},
        follow_redirects=False,
    )
    assert resp.status_code == 403
    assert svc.get_memory(mem["memory_id"])["status"] == "draft"