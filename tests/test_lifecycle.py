"""Acceptance tests for Forget / Restore / Purge / Audit retention.

Written per the spec (docs/design/forget-restore-purge.md) and gated on the
feature being implemented (review approval). Until then the module is skipped
so the rest of the suite stays green.

To run once implemented:
    python -m pytest tests/test_lifecycle.py -v
"""
import os

os.environ.setdefault("SAMJON_PORTAL_USERNAME", "portal-admin")
os.environ.setdefault("SAMJON_PORTAL_PASSWORD", "portal-secret")
os.environ.setdefault("SAMJON_PORTAL_ALLOWED_ORIGINS", "http://localhost:8100,http://127.0.0.1:8100")

import pytest

from samjon_memory.core.service import CoreService
from samjon_memory.core.main import app
from samjon_memory.errors import ValidationError, PermissionDenied

_IMPLEMENTED = (hasattr(CoreService, "restore_memory")
                and hasattr(CoreService, "purge_memory")
                and hasattr(CoreService, "audit_summary"))

pytestmark = pytest.mark.skipif(
    not _IMPLEMENTED,
    reason="Forget/Restore/Purge pending review + implementation",
)


@pytest.fixture
def client(temp_db):
    from fastapi.testclient import TestClient
    from samjon_memory.core.main import app
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    return c


@pytest.fixture
def config():
    from samjon_memory.config import config
    return config


def _purge_eligible(service, memory_id, days=40):
    # Backdate forgotten_at so the purge-age guard passes.
    service.conn.execute(
        "UPDATE memory SET forgotten_at = datetime('now', ?) WHERE memory_id=?",
        (f"-{days} days", memory_id),
    )
    service.conn.commit()


def _make_forgotten_memory(service, subject="gone", raw="secret content"):
    mem = service.create_memory({"subject": subject, "raw_content": raw, "source": "t"})
    service.forget_memory(mem["memory_id"])
    return service.get_memory(mem["memory_id"])


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

def test_restore_memory_returns_to_draft(service):
    mem = _make_forgotten_memory(service)
    restored = service.restore_memory(mem["memory_id"])
    assert restored["status"] == "draft"
    assert restored["version"] == mem["version"] + 1
    assert restored.get("forgotten_at") is None or restored.get("forgotten_at") == ""
    assert [r["action"] for r in service.get_audit_records(entity_id=mem["memory_id"])] \
        .count("memory_restore") == 1


def test_restore_collection_returns_to_draft(service):
    coll = service.create_collection({"subject": "c", "title": "C", "source": "t"})
    service.forget_collection(coll["collection_id"])
    forgotten = service.get_collection(coll["collection_id"])
    restored = service.restore_collection(coll["collection_id"])
    assert restored["status"] == "draft"
    assert restored["version"] == forgotten["version"] + 1
    assert [r["action"] for r in service.get_audit_records(entity_id=coll["collection_id"])] \
        .count("collection_restore") == 1


@pytest.mark.parametrize("status", ["draft", "active", "superseded"])
def test_restore_rejects_non_forgotten(service, status):
    mem = service.create_memory({"subject": "s", "raw_content": "c", "source": "t"})
    if status == "active":
        service.activate_memory(mem["memory_id"])
    elif status == "superseded":
        repl = service.create_memory({"subject": "r", "raw_content": "c", "source": "t"})
        service.supersede_memory(mem["memory_id"], repl["memory_id"])
    with pytest.raises(ValidationError):
        service.restore_memory(mem["memory_id"])


def test_restore_section_bumps_collection_version(service):
    coll = service.create_collection({"subject": "c", "title": "C", "source": "t"})
    section = service.create_memory({"subject": "sec", "raw_content": "c", "source": "t"})
    service.add_memory_to_collection(coll["collection_id"], section["memory_id"], 1)
    service.forget_memory(section["memory_id"])
    coll_before = service.get_collection(coll["collection_id"])["version"]
    service.restore_memory(section["memory_id"])
    assert service.get_collection(coll["collection_id"])["version"] == coll_before + 1


# ---------------------------------------------------------------------------
# Purge
# ---------------------------------------------------------------------------

def test_purge_rejects_non_forgotten(service):
    mem = service.create_memory({"subject": "s", "raw_content": "c", "source": "t"})
    with pytest.raises(ValidationError):
        service.purge_memory(mem["memory_id"], confirmation="PURGE", actor="admin")


def test_purge_rejects_too_fresh(service):
    mem = _make_forgotten_memory(service)  # forgotten just now
    with pytest.raises(ValidationError):
        service.purge_memory(mem["memory_id"], confirmation="PURGE", actor="admin")


def test_purge_rejects_wrong_confirmation(service):
    mem = _make_forgotten_memory(service)
    _purge_eligible(service, mem["memory_id"])
    with pytest.raises(ValidationError):
        service.purge_memory(mem["memory_id"], confirmation="forget", actor="admin")


def test_purge_rejects_non_admin(service):
    mem = _make_forgotten_memory(service)
    _purge_eligible(service, mem["memory_id"])
    with pytest.raises(PermissionDenied):
        service.purge_memory(mem["memory_id"], confirmation="PURGE", actor="reader")


def test_purge_erases_content_keeps_tombstone(service):
    mem = service.create_memory({
        "subject": "gone", "title": "secret-title", "section_path": "a/b",
        "raw_content": "super-secret-value", "structured_value_json": '{"secret": 1}',
        "source": "t",
    })
    service.forget_memory(mem["memory_id"])
    mem = service.get_memory(mem["memory_id"])
    _purge_eligible(service, mem["memory_id"])
    service.purge_memory(mem["memory_id"], confirmation="PURGE", actor="admin")
    purged = service.get_memory(mem["memory_id"])
    assert purged["raw_content"] == ""
    assert purged["structured_value_json"] is None
    assert purged["title"] is None
    assert purged["section_path"] is None
    assert purged["purged_at"] is not None
    assert purged["memory_id"] == mem["memory_id"]
    assert purged["content_checksum"] == mem["content_checksum"]
    assert purged["version"] == mem["version"] + 1
    # Lifecycle audit kept (no deleted content in it).
    assert [r["action"] for r in service.get_audit_records(entity_id=mem["memory_id"])] \
        .count("memory_purge") == 1
    assert "super-secret-value" not in str(service.get_audit_records(entity_id=mem["memory_id"]))
    # Tombstone archived.
    row = service.conn.execute(
        "SELECT * FROM lifecycle_tombstone WHERE entity_id=? AND entity_type='memory'",
        (mem["memory_id"],),
    ).fetchone()
    assert row is not None
    assert row["content_checksum"] == mem["content_checksum"]


def test_purged_cannot_be_edited_activated_or_reused(service):
    mem = service.create_memory({"subject": "gone", "title": "t", "raw_content": "c", "source": "t"})
    service.forget_memory(mem["memory_id"])
    _purge_eligible(service, mem["memory_id"])
    service.purge_memory(mem["memory_id"], confirmation="PURGE", actor="admin")
    with pytest.raises(Exception):
        service.update_memory(mem["memory_id"], {"subject": "x"})
    with pytest.raises(Exception):
        service.activate_memory(mem["memory_id"])
    with pytest.raises(Exception):
        service.forget_memory(mem["memory_id"])
    with pytest.raises(ValidationError):
        service.restore_memory(mem["memory_id"])


def test_purge_erases_related_manual_metadata(service):
    mem = service.create_memory({"subject": "the-subject", "raw_content": "c", "source": "t"})
    subject = mem["subject"]
    service.conn.execute(
        "INSERT INTO durable_alias (alias_id, subject, alias, language, source) VALUES (?,?,?,?,?)",
        ("alias-1", subject, "the-alias", "en", "t"))
    service.conn.execute(
        "INSERT INTO durable_user_tag (tag_id, subject, tag, language, source) VALUES (?,?,?,?,?)",
        ("tag-1", subject, "mytag", "en", "t"))
    service.conn.execute(
        "INSERT INTO manual_override (override_id, subject, scope, key, value_json, source) VALUES (?,?,?,?,?,?)",
        ("ovr-1", subject, "household", "answer", '{"x":1}', "t"))
    service.conn.commit()
    service.forget_memory(mem["memory_id"])
    mem = service.get_memory(mem["memory_id"])
    _purge_eligible(service, mem["memory_id"])
    service.purge_memory(mem["memory_id"], confirmation="PURGE", actor="admin")
    assert service.conn.execute("SELECT COUNT(*) AS n FROM durable_alias WHERE subject=?", (subject,)).fetchone()["n"] == 0
    assert service.conn.execute("SELECT COUNT(*) AS n FROM durable_user_tag WHERE subject=?", (subject,)).fetchone()["n"] == 0
    assert service.conn.execute("SELECT COUNT(*) AS n FROM manual_override WHERE subject=?", (subject,)).fetchone()["n"] == 0
    # Related rows tombstoned with identity only (no content).
    kinds = {r["entity_type"] for r in service.conn.execute(
        "SELECT DISTINCT entity_type FROM lifecycle_tombstone WHERE entity_type IN ('durable_alias','durable_user_tag','manual_override')").fetchall()}
    assert kinds == {"durable_alias", "durable_user_tag", "manual_override"}


def _purge_eligible_collection(service, collection_id, days=40):
    service.conn.execute(
        "UPDATE memory_collection SET forgotten_at = datetime('now', ?) WHERE collection_id=?",
        (f"-{days} days", collection_id),
    )
    service.conn.commit()


def test_purge_collection_erases_content(service):
    coll = service.create_collection({
        "subject": "col", "title": "Secret Title", "summary": "secret summary",
        "source_reference": "ref-1", "source": "t",
    })
    service.forget_collection(coll["collection_id"])
    coll = service.get_collection(coll["collection_id"])
    _purge_eligible_collection(service, coll["collection_id"])
    service.purge_collection(coll["collection_id"], confirmation="PURGE", actor="admin")
    purged = service.get_collection(coll["collection_id"])
    assert purged["title"] == ""
    assert purged["summary"] is None
    assert purged["source_reference"] is None
    assert purged["collection_id"] == coll["collection_id"]
    assert purged["version"] == coll["version"] + 1
    # Sections keep their FK to the (still-present) purged collection row.
    assert service.conn.execute("SELECT COUNT(*) AS n FROM memory_collection WHERE collection_id=?", (coll["collection_id"],)).fetchone()["n"] == 1


def test_restore_rejects_purged(service):
    mem = _make_forgotten_memory(service)
    _purge_eligible(service, mem["memory_id"])
    service.purge_memory(mem["memory_id"], confirmation="PURGE", actor="admin")
    with pytest.raises(ValidationError):
        service.restore_memory(mem["memory_id"])


def test_purge_section_bumps_collection_version(service):
    coll = service.create_collection({"subject": "c", "title": "C", "source": "t"})
    section = service.create_memory({"subject": "sec", "raw_content": "c", "source": "t"})
    service.add_memory_to_collection(coll["collection_id"], section["memory_id"], 1)
    service.forget_memory(section["memory_id"])
    _purge_eligible(service, section["memory_id"])
    coll_before = service.get_collection(coll["collection_id"])["version"]
    service.purge_memory(section["memory_id"], confirmation="PURGE", actor="admin")
    assert service.get_collection(coll["collection_id"])["version"] == coll_before + 1
    # Referential integrity intact.
    assert service.get_collection(coll["collection_id"])["collection_id"] == coll["collection_id"]


# ---------------------------------------------------------------------------
# Config, audit retention, pagination
# ---------------------------------------------------------------------------

def test_automatic_purge_off_by_default(config):
    assert getattr(config, "automatic_purge_enabled", False) is False
    from samjon_memory.core.main import app
    assert "/api/v1/core/purge" not in app.openapi()["paths"]


def test_purge_min_age_default(config):
    assert getattr(config, "purge_min_age_days", 30) == 30


def test_audit_summary_counts(service):
    _make_forgotten_memory(service)
    summary = service.audit_summary()
    actions = {row["action"]: row["count"] for row in summary}
    assert actions.get("memory_forget", 0) >= 1
    assert "memory_create" in actions


def test_audit_pagination(service):
    for i in range(5):
        service.create_memory({"subject": f"m{i}", "raw_content": "c", "source": "t"})
    page1 = service.get_audit_records(limit=3, offset=0)
    page2 = service.get_audit_records(limit=3, offset=3)
    assert len(page1) == 3
    assert page1[0]["audit_id"] != page2[0]["audit_id"]


def test_audit_details_sanitized(service):
    mem = service.create_memory({"subject": "sec", "raw_content": "secret-content", "source": "t"})
    records = service.get_audit_records(entity_id=mem["memory_id"])
    assert all("secret-content" not in (r["details_json"] or "") for r in records)
    assert all("password" not in (r["details_json"] or "").lower() for r in records)


def test_get_page_view_creates_no_audit(client, temp_db):
    from samjon_memory.core.main import app
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "view", "raw_content": "c", "source": "t"})
    before = len(svc.get_audit_records(entity_id=mem["memory_id"]))
    client.get(f"/portal/memories/{mem['memory_id']}")  # page view
    client.get(f"/portal/memories/{mem['memory_id']}?message=cancelled")  # cancel nav
    assert len(svc.get_audit_records(entity_id=mem["memory_id"])) == before


def test_audit_since_until_filters(service):
    service.create_memory({"subject": "a", "raw_content": "c", "source": "t"})
    early = service.get_audit_records(action="memory_create", since="2000-01-01T00:00:00.000000Z")
    assert len(early) >= 1
    late = service.get_audit_records(action="memory_create", since="2999-01-01T00:00:00.000000Z")
    assert late == []
    summary_by_action = {r["action"]: r["count"] for r in service.audit_summary(action="memory_create")}
    assert summary_by_action["memory_create"] == len(service.get_audit_records(action="memory_create"))


# ---------------------------------------------------------------------------
# REST routes + Portal
# ---------------------------------------------------------------------------

def test_lifecycle_routes_registered():
    from samjon_memory.core.main import app
    paths = app.openapi()["paths"]
    assert "/api/v1/core/memories/{memory_id}/restore" in paths
    assert "/api/v1/core/collections/{collection_id}/restore" in paths
    assert "/api/v1/core/memories/{memory_id}/purge" in paths
    assert "/api/v1/core/collections/{collection_id}/purge" in paths
    assert "/api/v1/core/audit/stats" in paths


def test_forgotten_memory_portal_shows_restore_and_purge(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = _make_forgotten_memory(svc)
    body = client.get(f"/portal/memories/{mem['memory_id']}").text
    assert f"action=\"/portal/memories/{mem['memory_id']}/restore\"" in body
    assert f"action=\"/portal/memories/{mem['memory_id']}/purge\"" in body


def test_active_memory_portal_hides_restore(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "a", "raw_content": "c", "source": "t"})
    svc.activate_memory(mem["memory_id"])
    body = client.get(f"/portal/memories/{mem['memory_id']}").text
    assert f"action=\"/portal/memories/{mem['memory_id']}/restore\"" not in body
    assert f"action=\"/portal/memories/{mem['memory_id']}/purge\"" not in body


def test_portal_purge_requires_confirmation_word(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = _make_forgotten_memory(svc)
    _purge_eligible(svc, mem["memory_id"])
    resp = client.post(
        f"/portal/memories/{mem['memory_id']}/purge",
        data={"confirmation": "nope", "expected_version": str(mem["version"])},
        headers={"Origin": "http://localhost:8100"},
        follow_redirects=False,
    )
    assert resp.status_code != 303 or svc.get_memory(mem["memory_id"])["raw_content"] != ""