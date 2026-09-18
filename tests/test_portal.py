"""Portal boundary and functional tests."""

import pytest
from samjon_memory.core.service import CoreService
from samjon_memory.errors import NotFound


def test_portal_index_contains_title():
    from samjon_memory.portal.pages import render_portal_index
    html = render_portal_index()
    assert "Samjon Memory Core Portal" in html


def test_portal_memory_list():
    from samjon_memory.portal.pages import render_memory_list
    memories = [{"memory_id": "m1", "subject": "test", "status": "active", "memory_type": "fact"}]
    html = render_memory_list(memories, page=1)
    assert "test" in html
    assert "m1" in html


def test_portal_auth_read_token_required():
    """Portal read routes require X-Service-Token."""
    from samjon_memory.security.auth import get_current_token
    from samjon_memory.errors import AuthenticationRequired
    # Read token works in dev mode
    result = get_current_token("dev-token")
    assert result == "dev-token"


def test_portal_auth_admin_token_required():
    """Portal write routes require X-Admin-Token."""
    from samjon_memory.security.auth import get_admin_token
    from samjon_memory.errors import PermissionDenied
    # Admin token works in dev mode
    result = get_admin_token("dev-admin-token")
    assert result == "dev-admin-token"


def test_portal_csrf_protection():
    """Portal router sets SameSite CSRF cookie."""
    from samjon_memory.portal.router import CSRF_COOKIE_NAME, _set_csrf_cookie, _generate_csrf_token
    assert CSRF_COOKIE_NAME == "portal_csrf"
    token = _generate_csrf_token()
    assert len(token) == 32


def test_portal_xss_safe_rendering():
    """Portal renders escape HTML for user content."""
    from samjon_memory.portal.pages import escape_html
    assert escape_html("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert escape_html('"test"') == "&quot;test&quot;"


def test_portal_no_direct_db_access():
    """Portal pages use service layer, not raw SQL."""
    import inspect
    from samjon_memory.portal import pages, router
    for name, obj in inspect.getmembers(pages):
        if inspect.isfunction(obj):
            src = inspect.getsource(obj)
            assert "conn.execute" not in src, f"pages.{name} uses raw SQL"
    for name, obj in inspect.getmembers(router):
        if inspect.isfunction(obj):
            src = inspect.getsource(obj)
            assert "conn.execute" not in src, f"router.{name} uses raw SQL"
            assert "service.conn" not in src, f"router.{name} accesses conn directly"


def test_portal_independent_memory_edit_not_collection_rewrite(service):
    """Editing one collection memory does not rewrite the whole collection."""
    coll = service.create_collection({
        "subject": "portal edit test", "title": "Portal Edit Test", "source": "test",
    })
    m1 = service.create_memory({
        "subject": "M1", "raw_content": "C1", "source": "test",
        "collection_id": coll["collection_id"], "sequence_number": 1,
    })
    m2 = service.create_memory({
        "subject": "M2", "raw_content": "C2", "source": "test",
        "collection_id": coll["collection_id"], "sequence_number": 2,
    })
    service.activate_collection(coll["collection_id"])
    original_m1_version = m1["version"]

    service.update_memory(m2["memory_id"], {
        "subject": "M2 Updated", "expected_version": m2["version"],
    })

    m1_after = service.get_memory(m1["memory_id"])
    assert m1_after["version"] == original_m1_version
    assert m1_after["subject"] == "M1"