"""User-facing Resolver Search Portal tests.

Exercises GET/POST /portal/search through the real routes against a temp Core
+ Resolver with a built projection, asserting grouping, cards, technical
details, no-results, and the stale warning.
"""
import os

os.environ.setdefault("SAMJON_PORTAL_USERNAME", "portal-admin")
os.environ.setdefault("SAMJON_PORTAL_PASSWORD", "portal-secret")
os.environ.setdefault("SAMJON_PORTAL_ALLOWED_ORIGINS", "http://localhost:8100,http://127.0.0.1:8100")

import pytest
from fastapi.testclient import TestClient

from samjon_memory.core.main import app
from samjon_memory.core.service import CoreService
from samjon_memory.resolver.service import ResolverService


@pytest.fixture
def search_context(temp_db, tmp_path):
    core = CoreService(database_path=temp_db)
    app.state.service = core
    coll = core.create_collection({
        "subject": "plants", "title": "Garden Catalog", "scope": "home",
        "source": "t", "summary": "Everything about garden plants.",
    })
    s1 = core.add_section_to_collection(
        coll["collection_id"], {"title": "Watering", "raw_content": "Water plants twice a week.", "sequence_number": 1})
    s2 = core.add_section_to_collection(
        coll["collection_id"], {"title": "Soil", "raw_content": "Use well-draining soil.", "sequence_number": 2})
    core.activate_collection(coll["collection_id"])
    mem = core.create_memory({"subject": "rose", "title": "Roses", "raw_content": "Roses need sunlight.", "source": "t"})
    core.activate_memory(mem["memory_id"])
    rsvc = ResolverService(database_path=str(tmp_path / "resolver.sqlite"))
    app.state.resolver_service = rsvc
    rsvc.full_rebuild(core)
    return {"core": core, "coll_id": coll["collection_id"],
            "s1": s1["memory_id"], "mem_id": mem["memory_id"]}


@pytest.fixture
def search_client(search_context):
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    return c


def test_search_requires_auth():
    c = TestClient(app)
    assert c.get("/portal/search").status_code == 401


def test_search_page_renders_box_and_nav(search_client):
    body = search_client.get("/portal/search").text
    assert "ค้นหาในคลังความรู้" in body
    assert 'name="q"' in body
    assert "Library" in body
    assert "Status" in body
    assert "Memories" in body
    assert "Resolver Debug" in body


def test_search_returns_grouped_results(search_client, search_context):
    resp = search_client.post(
        "/portal/search", data={"q": "plants", "target": "auto"},
        headers={"Origin": "http://localhost:8100"},
    )
    assert resp.status_code == 200
    body = resp.text
    assert "ค้นหาในคลังความรู้" in body
    assert "ชุดความรู้" in body                    # Library-oriented Collection label group
    assert "บทภายในชุด" in body                    # Library-oriented Section label group
    assert "Garden Catalog" in body               # collection title (also parent label on sections)
    assert "Watering" in body                     # a section title
    assert "Garden Catalog › Watering" in body    # section shows collection / chapter
    assert 'class="lib-card"' in body
    assert '<details class="technical result-action technical-action">' in body  # technical details still in <details>
    assert "รายละเอียดทางเทคนิค" in body
    assert "เปิดชุดความรู้" in body                 # Collection button
    assert f'href="/portal/library/memories/{search_context["s1"]}"' in body
    assert f'href="/portal/library/collections/{search_context["coll_id"]}"' in body
    assert "อ่านบทนี้" in body                     # Section primary button
    assert "เปิดทั้งชุด" in body                    # Section secondary button


def test_search_memory_card_library_labels(search_client, search_context):
    """A Memory result renders the Library 'บันทึกความรู้' label + 'อ่านบันทึก' button."""
    body = search_client.post(
        "/portal/search", data={"q": "roses"},
        headers={"Origin": "http://localhost:8100"},
    ).text
    assert "บันทึกความรู้" in body                 # Memory label group / kind badge
    assert "อ่านบันทึก" in body                    # Memory primary button
    assert 'class="lib-card"' in body
    assert f'href="/portal/library/memories/{search_context["mem_id"]}"' in body


def test_search_technical_details_fields(search_client, search_context):
    body = search_client.post(
        "/portal/search", data={"q": "plants"},
        headers={"Origin": "http://localhost:8100"},
    ).text
    assert "รายละเอียดทางเทคนิค" in body
    assert "Score" in body
    assert "Freshness" in body
    assert "Checksum" in body


def test_search_no_results_message(search_client):
    body = search_client.post(
        "/portal/search", data={"q": "zzzznomatch"},
        headers={"Origin": "http://localhost:8100"},
    ).text
    assert "ไม่พบผลลัพธ์สำหรับ" in body


def test_search_stale_warning(search_client, search_context):
    core = search_context["core"]
    # Bump a projected entity's version so the projection becomes stale.
    core.update_collection(search_context["coll_id"], {"summary": "Updated summary text."})
    body = search_client.post(
        "/portal/search", data={"q": "plants"},
        headers={"Origin": "http://localhost:8100"},
    ).text
    assert "ล้าสมัย" in body  # human stale notice