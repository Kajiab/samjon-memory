"""Foundation tests for the Jinja2 Core Portal templates.

Covers: template path resolution independent of CWD, default autoescape, the
no-``|safe`` policy, single-navbar/single-H1 on migrated pages, and controlled
behavior when a template is missing. Semantic assertions -- no full-page
whitespace snapshots.
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


# ---- Template path resolution ----------------------------------------------

def test_template_dir_resolved_from_module():
    """Templates directory is module-relative, never cwd-dependent."""
    from samjon_memory.portal import templating
    assert templating.TEMPLATES_DIR.name == "templates"
    assert templating.TEMPLATES_DIR.is_absolute()
    assert (templating.TEMPLATES_DIR / "base.html").is_file()


def test_render_works_with_any_cwd(tmp_path, monkeypatch):
    """Rendering succeeds when launched from an unrelated working directory."""
    from samjon_memory.portal import templating
    monkeypatch.chdir(tmp_path)
    html = templating.render(
        "library/home.html", active="library",
        hero={"title": "Search the knowledge library", "hint": "h",
              "target": "t", "q": ""},
        categories=[], discover=[], recent=[])
    assert "Browse by Subject" in html


# ---- Autoescape -------------------------------------------------------------

def test_autoescape_search_query(client):
    """User-supplied query is autoescaped on the migrated search page."""
    body = client.post("/portal/search", data={"q": '<script>alert(1)</script>"'},
                       headers={"Origin": "http://localhost:8100"}).text
    assert "&lt;script&gt;" in body
    assert "<script>alert(1)</script>" not in body


def test_autoescape_rendered_value(tmp_path):
    """A user-controlled title is escaped when rendered through a template."""
    from samjon_memory.portal import templating, viewmodels
    card = viewmodels.result_card_vm(
        {"memory_id": "m1", "title": '<b>T</b>&"', "subject": "rose", "excerpt": ""}, "memory")
    html = templating.render_partial("components/result_card.html", card=card)
    assert "&lt;b&gt;" in html
    assert "<b>T</b>" not in html


# ---- No |safe on user content ----------------------------------------------

def test_no_safe_filter_on_user_content():
    """No template wraps user-controlled values with ``|safe``."""
    from samjon_memory.portal import templating
    offenders = []
    for path in templating.TEMPLATES_DIR.rglob("*.html"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "|safe" in line:
                offenders.append((str(path.relative_to(templating.TEMPLATES_DIR)), i))
    assert offenders == []


# ---- Layout invariants ------------------------------------------------------

def test_home_single_navbar_and_single_h1(client, temp_db):
    body = client.get("/portal/").text
    assert body.count('class="navbar"') == 1
    assert body.count("aria-label=\"Primary\"") == 1
    assert body.count("<h1") == 1
    assert body.count('<nav class="navbar"') == 1


# ---- Template-not-found behavior -------------------------------------------

def test_missing_template_returns_controlled_document():
    from samjon_memory.portal import templating
    html = templating.render("does-not-exist.html", active="library")
    assert "Portal temporarily unavailable" in html
    assert "Traceback" not in html
    assert "portal/templates" not in html


# ---- Template validity ------------------------------------------------------

def test_all_templates_compile():
    from samjon_memory.portal import templating
    assert templating.validate_templates() == []