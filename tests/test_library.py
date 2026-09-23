"""Library Reader + unified navigation + search-safety UI tests.

Covers: Portal Create Memory title persistence, unified navigation on every
page, read-only Readers (Memory + Collection ordering), search results opening
the Reader, search safety (inactive/forgotten/purged removed), Collection with
>100 sections, and Administration resolver rebuild guidance + guards.
"""
import os

os.environ.setdefault("SAMJON_PORTAL_USERNAME", "portal-admin")
os.environ.setdefault("SAMJON_PORTAL_PASSWORD", "portal-secret")
os.environ.setdefault("SAMJON_PORTAL_ALLOWED_ORIGINS", "http://localhost:8100,http://127.0.0.1:8100")

import pytest
import io
import time
from PIL import Image
from fastapi.testclient import TestClient

from samjon_memory.core.main import app
from samjon_memory.core.service import CoreService
from samjon_memory.resolver.service import ResolverService


@pytest.fixture
def client(temp_db):
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    return c


@pytest.fixture
def search_env(temp_db, tmp_path):
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
    return {"core": core, "resolver": rsvc, "coll_id": coll["collection_id"],
            "s1": s1["memory_id"], "s2": s2["memory_id"], "mem_id": mem["memory_id"]}


@pytest.fixture
def search_client(search_env):
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    return c


def _post(client, path, data, **kw):
    kw.setdefault("headers", {"Origin": "http://localhost:8100"})
    kw.setdefault("follow_redirects", False)
    return client.post(path, data=data, **kw)


# ---- Unified navigation ----------------------------------------------------

def test_unified_nav_new_links_on_every_page(client):
    for path in ("/portal/", "/portal/memories", "/portal/collections", "/portal/status", "/portal/audit", "/portal/admin", "/portal/search"):
        body = client.get(path).text
        assert 'href="/portal/memories"' in body, path
        assert 'href="/portal/status"' in body, path
        assert 'href="/portal/resolver/"' in body, path  # admin debug link everywhere
        assert body.count('class="navbar"') == 1, path   # one unified navbar  # admin debug link everywhere


def test_unified_nav_single_navbar(client):
    body = client.get("/portal/search").text
    assert body.count('class="navbar"') == 1  # no duplicate navbar


# ---- Memory Create title ---------------------------------------------------

def test_portal_memory_create_saves_title(client, temp_db):
    resp = _post(client, "/portal/memories", {
        "subject": "topic", "title": "The Big Title", "raw_content": "content", "source": "t",
    })
    assert resp.status_code == 303
    memories = app.state.service.query_memories(subject="topic")
    assert memories and memories[0]["title"] == "The Big Title"
    detail = client.get(f"/portal/memories/{memories[0]['memory_id']}").text
    assert "The Big Title" in detail


# ---- Memory Reader ----------------------------------------------------------

def test_memory_reader_read_only(client, temp_db):
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "note", "title": "A Note", "raw_content": "secret reading", "source": "t"})
    svc.activate_memory(mem["memory_id"])
    version_before = svc.get_memory(mem["memory_id"])["version"]
    audit_before = len(svc.get_audit_records(entity_id=mem["memory_id"]))
    body = client.get(f"/portal/library/memories/{mem['memory_id']}").text
    assert body.count('class="navbar"') == 1
    assert "A Note" in body
    assert "secret reading" in body
    assert "<form" not in body                     # no mutation form
    assert f'href="/portal/memories/{mem["memory_id"]}/edit"' in body  # small admin edit
    assert "Back to results" in body
    assert svc.get_memory(mem["memory_id"])["version"] == version_before  # no version change
    assert len(svc.get_audit_records(entity_id=mem["memory_id"])) == audit_before  # no audit


# ---- Collection Reader ------------------------------------------------------

def test_collection_reader_orders_sections_asc(client, temp_db):
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "g", "title": "Guide", "scope": "home", "source": "t"})
    for title, seq in (("Three", 3), ("One", 1), ("Two", 2)):
        svc.add_section_to_collection(coll["collection_id"], {"title": title, "raw_content": title, "sequence_number": seq})
    svc.activate_collection(coll["collection_id"])
    body = client.get(f"/portal/library/collections/{coll['collection_id']}").text
    o1, o2, o3 = body.find(">One</a>"), body.find(">Two</a>"), body.find(">Three</a>")
    assert o1 != -1 and o2 != -1 and o3 != -1
    assert o1 < o2 < o3
    assert "Chapters" in body


# ---- Search safety + Reader links ------------------------------------------

def test_search_opens_reader_not_admin_detail(search_client, search_env):
    body = search_client.post("/portal/search", data={"q": "plants", "target": "auto"},
                              headers={"Origin": "http://localhost:8100"}).text
    assert f'href="/portal/library/collections/{search_env["coll_id"]}"' in body     # collection -> reader
    assert f'href="/portal/library/memories/{search_env["s1"]}"' in body             # section -> reader
    assert "อ่านบทนี้" in body
    assert "เปิดทั้งชุด" in body


def test_search_hides_forgotten_after_stale(search_client, search_env):
    core = search_env["core"]
    core.forget_memory(search_env["s1"])          # not rebuilt -> projection still has it
    body = search_client.post("/portal/search", data={"q": "plants"},
                              headers={"Origin": "http://localhost:8100"}).text
    assert "Watering" not in body                  # forgotten section removed
    assert "Soil" in body                          # active sibling still shown


def test_search_hides_purged_after_stale(search_client, search_env):
    core = search_env["core"]
    core.forget_memory(search_env["mem_id"])
    core.conn.execute("UPDATE memory SET forgotten_at = datetime('now','-40 days') WHERE memory_id=?", (search_env["mem_id"],))
    core.conn.commit()
    core.purge_memory(search_env["mem_id"], confirmation="PURGE", actor="admin")
    body = search_client.post("/portal/search", data={"q": "rose"},
                              headers={"Origin": "http://localhost:8100"}).text
    assert "Roses" not in body


def test_search_hides_section_of_inactive_collection(search_client, search_env):
    core = search_env["core"]
    core.forget_collection(search_env["coll_id"])   # parent becomes inactive (not active)
    body = search_client.post("/portal/search", data={"q": "plants"},
                              headers={"Origin": "http://localhost:8100"}).text
    assert "Watering" not in body
    assert "Soil" not in body


# ---- Administration resolver rebuild ---------------------------------------

def test_admin_resolver_controls_rendered(search_client):
    body = search_client.get("/portal/admin").text
    assert "Search index (Resolver)" in body
    assert "Guidance" in body
    assert "Full Rebuild" in body
    assert "Selective Rebuild" in body


def test_admin_rebuild_guards_argument_origin(search_client):
    resp = search_client.post("/portal/admin/resolver/rebuild",
                              data={"confirmation": "REBUILD"},
                              headers={"Origin": "http://evil.example"},
                              follow_redirects=False)
    assert resp.status_code == 403


def test_admin_rebuild_requires_confirmation(search_client):
    resp = _post(search_client, "/portal/admin/resolver/rebuild", {"confirmation": "nope"})
    assert resp.status_code == 303
    assert "message=error" in resp.headers.get("location", "")
    assert "REBUILD" in resp.headers.get("location", "")


def test_admin_full_rebuild_confirms_and_runs(search_client, search_env):
    resp = _post(search_client, "/portal/admin/resolver/rebuild", {"confirmation": "REBUILD"})
    assert resp.status_code == 303
    assert "resolver_rebuilt" in resp.headers.get("location", "")


# ---- Collection >100 sections ----------------------------------------------

def test_collection_over_100_sections_renders_ordered(client, temp_db):
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "big", "title": "Big", "scope": "home", "source": "t"})
    for i in range(150):
        svc.add_section_to_collection(coll["collection_id"], {"title": f"S{i:03d}", "raw_content": f"content {i}", "sequence_number": i})
    svc.activate_collection(coll["collection_id"])
    body = client.get(f"/portal/library/collections/{coll['collection_id']}").text
    assert "S149" in body
    a = body.find(">S000</a>"); b = body.find(">S001</a>"); c = body.find(">S149</a>")
    assert a != -1 and b != -1 and c != -1
    assert a < b < c  # ordered ASC
    mems = svc.get_collection_memories(coll["collection_id"], limit=200)
    assert len(mems) == 150
    client.post(f"/portal/collections/{coll['collection_id']}/memories/{mems[1]['memory_id']}/move-up",
                headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert len(svc.get_collection_memories_all(coll["collection_id"])) == 150


# ---- Portal IA: Library homepage + subject categories ----------------------

import samjon_memory.portal.pages as _pages


def _jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (8, 6), (200, 30, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def test_portal_home_renders_library(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    body = client.get("/portal/").text
    assert "Search the knowledge library" in body
    assert "Browse by Subject" in body
    assert "Discover" in body
    assert "Recently Updated" in body
    assert 'href="/portal/" aria-current="page"' in body  # Library is active nav
    assert 'class="lib-cat-grid"' in body


def test_portal_status_renders_dashboard(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    svc.create_memory({"subject": "a", "raw_content": "c", "source": "t"})
    body = client.get("/portal/status").text
    assert "System Status" in body
    assert "Standalone Memories" in body
    assert "Total Facts" in body
    assert 'href="/portal/status" aria-current="page"' in body  # Status is active nav


def test_subject_domain_derivation():
    assert _pages.subject_domain("person:jeab") == "person"
    assert _pages.subject_domain("plant:monstera-bedroom") == "plant"
    assert _pages.subject_domain("pet:thai-cat") == "pet"
    assert _pages.subject_domain("device:water-pump-main") == "device"
    assert _pages.subject_domain("plain-subject") == "plain-subject"


def test_category_mapping_combined_and_other():
    music = _pages.category_by_key("music")
    assert _pages.category_matches(music, "music:album-a")
    assert _pages.category_matches(music, "playlist:chill")
    inv = _pages.category_by_key("inventory")
    assert _pages.category_matches(inv, "item:hammer")
    assert _pages.category_matches(inv, "supply:glue")
    other = _pages.category_by_key("other")
    assert _pages.category_matches(other, "alphabet:notes")
    assert not _pages.category_matches(inv, "plant:rose")


def test_library_category_page_active_only(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    m_active = svc.create_memory({"subject": "plant:monstera", "title": "Monstera Active", "raw_content": "c", "source": "t"})
    svc.create_memory({"subject": "plant:kk", "title": "Draft Plant", "raw_content": "d", "source": "t"})
    cv = svc.create_collection({"subject": "plant:guide", "title": "Plant Guide", "source": "t"})
    svc.activate_memory(m_active["memory_id"])
    svc.activate_collection(cv["collection_id"])
    m_forg = svc.create_memory({"subject": "plant:x", "title": "Forgotten Plant", "raw_content": "f", "source": "t"})
    svc.forget_memory(m_forg["memory_id"])
    m_sup = svc.create_memory({"subject": "plant:y", "title": "Superseded Plant", "raw_content": "s", "source": "t"})
    repl = svc.create_memory({"subject": "plant:y", "raw_content": "r", "source": "t"})
    svc.supersede_memory(m_sup["memory_id"], repl["memory_id"])

    home = client.get("/portal/library/subjects/plants").text
    assert "Monstera Active" in home
    assert "Plant Guide" in home
    assert "Draft Plant" not in home
    assert "Forgotten Plant" not in home
    assert "Superseded Plant" not in home
    assert f"/portal/library/memories/{m_active['memory_id']}" in home  # reader link
    homebody = client.get("/portal/").text
    assert "1 ชุด · 1 บันทึก" in homebody  # only active counted


def test_discover_bounded_and_active(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    for i in range(20):
        m = svc.create_memory({"subject": "activity:x", "raw_content": f"c{i}", "source": "t"})
        svc.activate_memory(m["memory_id"])
    disc = svc.library_discover(12)
    assert len(disc) <= 12
    assert all(e["status"] == "active" for e in disc)
    assert all(e["_type"] in ("memory", "collection") for e in disc)
    assert "Discover" in client.get("/portal/").text


def test_recently_updated_ordered_desc(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    m1 = svc.create_memory({"subject": "a", "raw_content": "c1", "source": "t"})
    svc.activate_memory(m1["memory_id"])
    # Cross the OS clock tick so updated_at differ (Windows microsecond granularity).
    time.sleep(0.06)
    m2 = svc.create_memory({"subject": "a", "raw_content": "c2", "source": "t"})
    svc.activate_memory(m2["memory_id"])
    svc.update_memory(m2["memory_id"], {"raw_content": "c2-updated"})  # newest first
    recent = svc.library_recent(500)
    ids = [e["memory_id"] for e in recent
           if e.get("_type") == "memory" and e["memory_id"] in {m1["memory_id"], m2["memory_id"]}]
    assert ids[0] == m2["memory_id"]
    assert ids[1] == m1["memory_id"]
    assert "Recently Updated" in client.get("/portal/").text


def test_library_home_cover_and_placeholder(client, temp_db, tmp_path):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db, media_root=str(tmp_path / "media"))
    app.state.service = svc
    mc = svc.create_memory({"subject": "plant:rose", "title": "Rose", "raw_content": "c", "source": "t"})
    svc.activate_memory(mc["memory_id"])
    cov = svc.upload_media("memory", mc["memory_id"], _jpeg(), alt_text="rose cover", actor="admin")
    svc.set_media_cover(cov["media_id"])
    mp = svc.create_memory({"subject": "plant:tulip", "title": "Tulip", "raw_content": "d", "source": "t"})
    svc.activate_memory(mp["memory_id"])
    body = client.get("/portal/").text
    assert f"/portal/media/{cov['media_id']}/thumb" in body
    assert 'alt="rose cover"' in body
    assert "ยังไม่มีภาพปก" in body
    assert "relative_path" not in body
    assert "data:image" not in body
    assert "portal-secret" not in body


def test_library_pages_no_side_effects(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    m = svc.create_memory({"subject": "plant:x", "raw_content": "c", "source": "t"})
    svc.activate_memory(m["memory_id"])
    v_before = svc.get_memory(m["memory_id"])["version"]
    a_before = len(svc.get_audit_records(entity_id=m["memory_id"]))
    client.get("/portal/")
    client.get("/portal/library/subjects/plants")
    assert svc.get_memory(m["memory_id"])["version"] == v_before
    assert len(svc.get_audit_records(entity_id=m["memory_id"])) == a_before


def test_library_home_xss_escaped(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    m = svc.create_memory({"subject": "plant:x", "title": "<script>alert(1)</script>", "raw_content": "c", "source": "t"})
    svc.activate_memory(m["memory_id"])
    body = client.get("/portal/").text
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body


def test_search_query_param_still_works(client, temp_db, tmp_path):
    from samjon_memory.resolver.service import ResolverService
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    m = svc.create_memory({"subject": "rose", "raw_content": "roses bloom nicely", "source": "t"})
    svc.activate_memory(m["memory_id"])
    rsvc = ResolverService(database_path=str(tmp_path / "r.sqlite"))
    app.state.resolver_service = rsvc
    rsvc.full_rebuild(svc)
    r = client.get("/portal/search", params={"q": "roses"})
    assert r.status_code == 200
    assert "อ่านบันทึก" in r.text
# ---------------------------------------------------------------------------
# Bookstore-presentation coverage (Samjon Library UI redesign)
# ---------------------------------------------------------------------------

def test_home_sections_keep_bookstore_order(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    body = client.get("/portal/").text
    i = body.index
    assert i("Search the knowledge library") < i("Browse by Subject") < i("Discover") < i("Recently Updated")


def test_home_category_cards_english_name_and_thai_hint(client, temp_db):
    from samjon_memory.core.service import CoreService
    import samjon_memory.portal.pages as pages
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    body = client.get("/portal/").text
    assert 'class="lib-cat-grid"' in body
    for cat in pages.SUBJECT_CATEGORIES:
        assert ('<span class="lib-cat-name">%s</span>' % cat["name"]) in body
        assert ('<span class="lib-cat-hint">%s</span>' % cat["hint"]) in body


def test_home_category_card_counts_use_library_labels(client, temp_db):
    from samjon_memory.core.service import CoreService
    import samjon_memory.portal.pages as pages
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "plant:rose", "raw_content": "c", "source": "t"})
    svc.activate_memory(mem["memory_id"])
    body = client.get("/portal/").text
    # Active counts reflected with the shared library label format.
    expected = pages._cat_counts({"collections": 0, "memories": 1})
    assert expected in body


def test_home_category_cover_uses_authenticated_thumb(client, temp_db, tmp_path):
    import io
    from PIL import Image
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db, media_root=str(tmp_path / "media"))
    app.state.service = svc
    m = svc.create_memory({"subject": "plant:rose", "title": "Rose", "raw_content": "c", "source": "t"})
    svc.activate_memory(m["memory_id"])
    buf = io.BytesIO()
    Image.new("RGB", (8, 6), (200, 30, 30)).save(buf, format="JPEG")
    cov = svc.upload_media("memory", m["memory_id"], buf.getvalue(), alt_text="rose cover", actor="admin")
    svc.set_media_cover(cov["media_id"])
    body = client.get("/portal/").text
    assert f"/portal/media/{cov['media_id']}/thumb" in body
    assert 'class="lib-cat-cover-img"' in body
    assert "relative_path" not in body


def test_search_home_and_results_use_reader_routes(client, temp_db, tmp_path):
    from samjon_memory.core.service import CoreService
    from samjon_memory.resolver.service import ResolverService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    c = svc.create_collection({"subject": "plants", "title": "Guide", "source": "t"})
    s = svc.add_section_to_collection(
        c["collection_id"], {"title": "Watering", "raw_content": "water the plants", "sequence_number": 1})
    svc.activate_collection(c["collection_id"])
    rsvc = ResolverService(database_path=str(tmp_path / "r.sqlite"))
    app.state.resolver_service = rsvc
    rsvc.full_rebuild(svc)
    body = client.post(
        "/portal/search", data={"q": "water", "target": "auto"},
        headers={"Origin": "http://localhost:8100"}).text
    assert f'/portal/library/memories/{s["memory_id"]}' in body
    assert f'/portal/library/collections/{c["collection_id"]}' in body
    assert 'class="lib-card"' in body
    assert "<details class=\"technical\">" in body


def test_memory_reader_hero_and_no_mutation(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    m = svc.create_memory({"subject": "note", "title": "A Note", "raw_content": "reading", "source": "t"})
    svc.activate_memory(m["memory_id"])
    body = client.get(f'/portal/library/memories/{m["memory_id"]}').text
    assert 'class="reader-hero"' in body
    assert 'class="reader-meta"' in body
    assert "<form" not in body
    assert f'href="/portal/memories/{m["memory_id"]}/edit"' in body
    assert "Back to results" in body


def test_collection_reader_toc_anchors_and_read_only(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "g", "title": "Guide", "source": "t"})
    for i, t in enumerate(("One", "Two", "Three"), start=1):
        svc.add_section_to_collection(
            coll["collection_id"], {"title": t, "raw_content": t, "sequence_number": i})
    svc.activate_collection(coll["collection_id"])
    body = client.get(f'/portal/library/collections/{coll["collection_id"]}').text
    assert 'class="reader-toc"' in body
    assert "Chapters" in body
    for i in (1, 2, 3):
        assert f'href="#chapter-{i}"' in body
    assert "<details class=\"technical\">" in body
    assert 'action="/portal/media/' not in body


def test_library_pages_no_paths_binary_or_secrets(client, temp_db, tmp_path):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db, media_root=str(tmp_path / "media"))
    app.state.service = svc
    m = svc.create_memory({"subject": "plant:rose", "title": "Rose", "raw_content": "c", "source": "t"})
    svc.activate_memory(m["memory_id"])
    paths = [
        "/portal/",
        "/portal/library/subjects/plants",
        f'/portal/library/memories/{m["memory_id"]}',
    ]
    for p in paths:
        body = client.get(p).text
        for banned in ("relative_path", "thumbnail_path", "data:image",
                       "portal-secret", "portal-admin", "base64"):
            assert banned not in body, (p, banned)