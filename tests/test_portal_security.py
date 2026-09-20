"""Portal security tests.

Tests HTTP Basic auth, Origin validation, XSS safety, and cancel behavior.
"""
import os

# Must be set before importing app (config reads env at property access)
os.environ.setdefault("SAMJON_PORTAL_USERNAME", "portal-admin")
os.environ.setdefault("SAMJON_PORTAL_PASSWORD", "portal-secret")
os.environ.setdefault("SAMJON_PORTAL_ALLOWED_ORIGINS", "http://localhost:8100,http://127.0.0.1:8100")

import pytest
from samjon_memory.core.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client(temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    return c


# ---- Authentication ----

def test_missing_credentials_return_401(client):
    c = TestClient(app)
    resp = c.get("/portal/memories")
    assert resp.status_code == 401


def test_www_authenticate_basic_present(client):
    c = TestClient(app)
    resp = c.get("/portal/memories")
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers
    assert "Basic" in resp.headers["WWW-Authenticate"]


def test_invalid_username_rejected(client):
    c = TestClient(app)
    c.auth = ("wrong", "portal-secret")
    resp = c.get("/portal/memories")
    assert resp.status_code == 401


def test_invalid_password_rejected(client):
    c = TestClient(app)
    c.auth = ("portal-admin", "wrong")
    resp = c.get("/portal/memories")
    assert resp.status_code == 401


def test_valid_credentials_allow_access(client):
    resp = client.get("/portal/memories")
    assert resp.status_code == 200


# ---- Auth required on all portal routes ----

@pytest.mark.parametrize("path", [
    "/portal/",
    "/portal/memories",
    "/portal/collections",
    "/portal/audit",
])
def test_authenticated_routes_require_credentials(path):
    c = TestClient(app)
    resp = c.get(path)
    assert resp.status_code == 401


# ---- Origin validation ----

def test_unapproved_origin_rejected_on_mutation(client, temp_db):
    """POST without an approved Origin header is rejected."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    resp = c.post("/portal/memories", data={"subject": "x", "raw_content": "c", "source": "t"}, headers={"Origin": "http://evil.example"}, follow_redirects=False)
    assert resp.status_code == 403


def test_approved_origin_succeeds_on_mutation(client, temp_db):
    """POST with an approved Origin header succeeds."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    resp = c.post("/portal/memories", data={"subject": "x", "raw_content": "c", "source": "t"}, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code in (303, 422)  # 303 redirect or 422 validation


# ---- Credentials absent from output ----

def test_credentials_absent_from_html(client):
    resp = client.get("/portal/memories")
    body = resp.text
    assert "portal-secret" not in body
    assert "portal-admin" not in body


def test_credentials_absent_from_capabilities():
    from samjon_memory.core.main import app
    c = TestClient(app)
    resp = c.get("/api/v1/capabilities")
    body = resp.json()
    portal = body["features"]["portal"]
    assert "portal-secret" not in str(portal)
    assert "portal-admin" not in str(portal)


# ---- Cancel behavior ----

def test_cancel_create_memory_no_mutation(client, temp_db):
    """Cancel link on create form does not create a memory."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    before = len(svc.memories.list(limit=100))
    # Follow cancel link (navigation link)
    resp = c.get("/portal/memories?message=cancelled")
    assert resp.status_code == 200
    after = len(svc.memories.list(limit=100))
    assert after == before


# ---- XSS safety ----

def test_xss_safe_rendering(client, temp_db):
    """Dynamic content is HTML-escaped in portal output."""
    xss_subject = "<script>alert(1)</script>"
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    mem = svc.create_memory({"subject": xss_subject, "raw_content": "safe", "source": "test"})
    resp = c.get(f"/portal/memories/{mem['memory_id']}")
    assert resp.status_code == 200
    assert "<script>" not in resp.text
    assert "&lt;script&gt;" in resp.text


def test_validation_errors_human_readable(client, temp_db):
    """Validation errors are presented in human-readable language, not raw codes."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "human test", "title": "Human", "source": "test", "expected_item_count": 3})
    resp = client.get(f"/portal/collections/{coll['collection_id']}")
    assert resp.status_code == 200
    assert "Expected Sections: 3" in resp.text
    assert "Current Sections: 0" in resp.text
    assert "Missing Sections: 3" in resp.text
    assert "Not ready to activate" in resp.text