"""Portal functional tests."""
import os
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


def _make_sections(svc, coll, labels):
    """Create Collection sections that inherit subject/scope, with distinct titles."""
    mems = []
    for i, label in enumerate(labels, start=1):
        mem = svc.create_memory({
            "subject": coll["subject"], "scope": coll["scope"],
            "title": label, "raw_content": label.lower(), "source": "test",
        })
        svc.add_memory_to_collection(coll["collection_id"], mem["memory_id"], i)
        mems.append(svc.get_memory(mem["memory_id"]))
    return mems


# ---- Memory list ----

def test_memory_list_empty(client):
    resp = client.get("/portal/memories")
    assert resp.status_code == 200
    assert "Memories" in resp.text


def test_memory_list_shows_created(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    svc.create_memory({"subject": "listed memory", "raw_content": "content", "source": "test"})
    resp = client.get("/portal/memories")
    assert resp.status_code == 200
    assert "listed memory" in resp.text


# ---- Memory detail ----

def test_memory_detail(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "detail test", "raw_content": "content", "source": "test"})
    resp = client.get(f"/portal/memories/{mem['memory_id']}")
    assert resp.status_code == 200
    assert "detail test" in resp.text


def test_memory_detail_not_found(client):
    resp = client.get("/portal/memories/nonexistent")
    assert resp.status_code == 404


# ---- Memory create ----

def test_memory_create_form(client):
    resp = client.get("/portal/memories/create")
    assert resp.status_code == 200
    assert "Create Memory" in resp.text


def test_memory_create_submission(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    resp = client.post("/portal/memories", data={
        "subject": "created via portal", "raw_content": "content", "source": "test",
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    memories = svc.memories.list(limit=100)
    assert any(m["subject"] == "created via portal" for m in memories)


# ---- Memory edit ----

def test_memory_edit_form(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "edit me", "raw_content": "old content", "source": "test"})
    resp = client.get(f"/portal/memories/{mem['memory_id']}/edit")
    assert resp.status_code == 200
    assert "edit me" in resp.text


def test_memory_edit_submission(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "edit target", "raw_content": "old", "source": "test"})
    resp = client.post(f"/portal/memories/{mem['memory_id']}", data={
        "subject": "edited", "raw_content": "new content", "source": "test",
        "expected_version": mem["version"],
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    updated = svc.get_memory(mem["memory_id"])
    assert updated["subject"] == "edited"


# ---- Memory supersede ----

def test_memory_supersede(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    old = svc.create_memory({"subject": "old memory", "raw_content": "old", "source": "test"})
    new = svc.create_memory({"subject": "new memory", "raw_content": "new", "source": "test"})
    resp = client.post(f"/portal/memories/{old['memory_id']}/supersede", data={
        "replacement_memory_id": new["memory_id"],
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    updated = svc.get_memory(old["memory_id"])
    assert updated["status"] == "superseded"


# ---- Memory forget ----

def test_memory_forget(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "to forget", "raw_content": "content", "source": "test"})
    resp = client.post(f"/portal/memories/{mem['memory_id']}/forget", headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    assert svc.get_memory(mem["memory_id"])["status"] == "forgotten"


# ---- Collection list ----

def test_collection_list_empty(client):
    resp = client.get("/portal/collections")
    assert resp.status_code == 200
    assert "Collections" in resp.text


# ---- Collection create ----

def test_collection_create_form(client):
    resp = client.get("/portal/collections/create")
    assert resp.status_code == 200
    assert "Create Collection" in resp.text


def test_collection_create_submission(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    resp = client.post("/portal/collections", data={
        "subject": "test collection", "title": "Test Collection", "source": "test",
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    collections = svc.collections.list(limit=100)
    assert any(c["subject"] == "test collection" for c in collections)


# ---- Collection detail ----

def test_collection_detail(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "detail test", "title": "Detail", "source": "test"})
    resp = client.get(f"/portal/collections/{coll['collection_id']}")
    assert resp.status_code == 200
    assert "Detail" in resp.text


# ---- Collection edit ----

def test_collection_edit_form(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "edit test", "title": "Edit Me", "source": "test"})
    resp = client.get(f"/portal/collections/{coll['collection_id']}/edit")
    assert resp.status_code == 200
    assert "Edit Me" in resp.text


def test_collection_edit_submission(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "edit target", "title": "Edit Target", "source": "test"})
    resp = client.post(f"/portal/collections/{coll['collection_id']}", data={
        "subject": "edited", "title": "Edited", "source": "test",
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    updated = svc.get_collection(coll["collection_id"])
    assert updated["subject"] == "edited"


# ---- Collection memory operations ----

def test_collection_add_section_no_memory_id(client, temp_db):
    """Adding a Section does not require a Memory ID."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "section test", "title": "Section Test", "source": "test", "expected_item_count": 3})
    resp = client.post(f"/portal/collections/{coll['collection_id']}/memories", data={
        "title": "new section", "memory_type": "fact", "raw_content": "content",
        "language": "en", "sequence_number": 1,
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303


def test_section_server_generated_id(client, temp_db):
    """Backend generates the Memory ID when adding a Section."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "id test", "title": "ID Test", "source": "test", "expected_item_count": 3})
    before = set(m["memory_id"] for m in svc.get_collection_memories(coll["collection_id"]))
    resp = client.post(f"/portal/collections/{coll['collection_id']}/memories", data={
        "title": "auto id", "memory_type": "fact", "raw_content": "content",
        "language": "en", "sequence_number": 1,
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    after = set(m["memory_id"] for m in svc.get_collection_memories(coll["collection_id"]))
    new_ids = after - before
    assert len(new_ids) == 1
    new_id = new_ids.pop()
    assert new_id.startswith("mem-")


def test_section_appears_after_creation(client, temp_db):
    """New Section appears in the Collection detail page."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "appear test", "title": "Appear", "source": "test", "expected_item_count": 3})
    resp = client.post(f"/portal/collections/{coll['collection_id']}/memories", data={
        "title": "visible section", "memory_type": "fact", "raw_content": "content",
        "language": "en", "sequence_number": 1,
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    detail = client.get(f"/portal/collections/{coll['collection_id']}")
    assert detail.status_code == 200
    assert "visible section" in detail.text


def test_section_count_changes_from_0_to_1(client, temp_db):
    """Adding a Section increments the count from 0 to 1."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "count test", "title": "Count", "source": "test", "expected_item_count": 3})
    assert len(svc.get_collection_memories(coll["collection_id"])) == 0
    resp = client.post(f"/portal/collections/{coll['collection_id']}/memories", data={
        "title": "counted", "memory_type": "fact", "raw_content": "content",
        "language": "en", "sequence_number": 1,
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    assert len(svc.get_collection_memories(coll["collection_id"])) == 1


def test_activate_disabled_when_invalid(client, temp_db):
    """Activate button is disabled when validation fails."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "disable test", "title": "Disable", "source": "test", "expected_item_count": 3})
    resp = client.get(f"/portal/collections/{coll['collection_id']}")
    assert resp.status_code == 200
    assert "Not ready to activate" in resp.text
    assert '<button type="submit" disabled>Activate</button>' in resp.text


def test_activate_enabled_after_three_valid_sections(client, temp_db):
    """Activate button is enabled after adding three valid Sections."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "enable test", "title": "Enable", "source": "test", "expected_item_count": 3})
    _make_sections(svc, coll, ["sec 0", "sec 1", "sec 2"])
    resp = client.get(f"/portal/collections/{coll['collection_id']}")
    assert resp.status_code == 200
    assert "Ready to activate" in resp.text
    assert '<button type="submit" disabled>Activate</button>' not in resp.text


def test_collection_reorder(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "reorder test", "title": "Reorder", "source": "test"})
    m1, m2 = _make_sections(svc, coll, ["a", "b"])
    resp = client.post(f"/portal/collections/{coll['collection_id']}/order", data={
        "ordered_memory_ids": f"{m2['memory_id']},{m1['memory_id']}",
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303


# ---- Collection activate ----

def test_collection_activate(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "act test", "title": "Activate", "source": "test"})
    (mem,) = _make_sections(svc, coll, ["sec"])
    resp = client.post(f"/portal/collections/{coll['collection_id']}/activate", headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    updated = svc.get_collection(coll["collection_id"])
    assert updated["status"] == "active"


# ---- Audit log ----

def test_audit_log(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    svc.create_memory({"subject": "audited", "raw_content": "content", "source": "test"})
    resp = client.get("/portal/audit")
    assert resp.status_code == 200
    assert "Audit Log" in resp.text
    assert "memory_create" in resp.text


# ---- Version conflict ----

def test_edit_version_conflict_shown(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "conflict", "raw_content": "content", "source": "test"})
    svc.update_memory(mem["memory_id"], {"subject": "changed", "expected_version": 1})
    resp = client.post(f"/portal/memories/{mem['memory_id']}", data={
        "subject": "conflict", "raw_content": "content", "source": "test",
        "expected_version": 1,
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 409


# ---- Cancel behavior ----

def test_cancel_create_memory_link(client, temp_db):
    """Cancel link on create form sends no mutation."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    before = len(svc.memories.list(limit=100))
    resp = client.get("/portal/memories?message=cancelled")
    assert resp.status_code == 200
    after = len(svc.memories.list(limit=100))
    assert after == before


# ---- Collection move up/down ----

def test_move_up_down_disabled_at_boundaries(client, temp_db):
    """Up disabled on first section, Down disabled on last section."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "boundary test", "title": "Boundary", "source": "test", "expected_item_count": 3})
    m1, m2, m3 = _make_sections(svc, coll, ["A", "B", "C"])
    resp = client.get(f"/portal/collections/{coll['collection_id']}")
    assert resp.status_code == 200
    assert f'action="/portal/collections/{coll["collection_id"]}/memories/{m1["memory_id"]}/move-up"' in resp.text
    assert f'action="/portal/collections/{coll["collection_id"]}/memories/{m3["memory_id"]}/move-down"' in resp.text


def test_down_of_a_reorders_b_a_c(client, temp_db):
    """Down on first section results in B, A, C."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "down-a test", "title": "Down A", "source": "test", "expected_item_count": 3})
    m1, m2, m3 = _make_sections(svc, coll, ["A", "B", "C"])
    resp = client.post(f"/portal/collections/{coll['collection_id']}/memories/{m1['memory_id']}/move-down", headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    memories = svc.get_collection_memories(coll["collection_id"])
    titles = [m["title"] for m in sorted(memories, key=lambda m: m.get("sequence_number", 0))]
    assert titles == ["B", "A", "C"]


def test_up_of_c_reorders_a_c_b(client, temp_db):
    """Up on last section results in A, C, B."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "up-c test", "title": "Up C", "source": "test", "expected_item_count": 3})
    m1, m2, m3 = _make_sections(svc, coll, ["A", "B", "C"])
    resp = client.post(f"/portal/collections/{coll['collection_id']}/memories/{m3['memory_id']}/move-up", headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    memories = svc.get_collection_memories(coll["collection_id"])
    titles = [m["title"] for m in sorted(memories, key=lambda m: m.get("sequence_number", 0))]
    assert titles == ["A", "C", "B"]


def test_up_of_b_reorders_b_a_c(client, temp_db):
    """Up on middle section B results in B, A, C."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "up-b test", "title": "Up B", "source": "test", "expected_item_count": 3})
    m1, m2, m3 = _make_sections(svc, coll, ["A", "B", "C"])
    resp = client.post(f"/portal/collections/{coll['collection_id']}/memories/{m2['memory_id']}/move-up", headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    memories = svc.get_collection_memories(coll["collection_id"])
    titles = [m["title"] for m in sorted(memories, key=lambda m: m.get("sequence_number", 0))]
    assert titles == ["B", "A", "C"]


def test_down_of_b_reorders_a_c_b(client, temp_db):
    """Down on middle section B results in A, C, B."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "down-b test", "title": "Down B", "source": "test", "expected_item_count": 3})
    m1, m2, m3 = _make_sections(svc, coll, ["A", "B", "C"])
    resp = client.post(f"/portal/collections/{coll['collection_id']}/memories/{m2['memory_id']}/move-down", headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    memories = svc.get_collection_memories(coll["collection_id"])
    titles = [m["title"] for m in sorted(memories, key=lambda m: m.get("sequence_number", 0))]
    assert titles == ["A", "C", "B"]


def test_boundary_move_does_not_corrupt_order(client, temp_db):
    """Pressing Up on first or Down on last does not change order."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "boundary-corrupt test", "title": "Boundary", "source": "test", "expected_item_count": 3})
    m1, m2, m3 = _make_sections(svc, coll, ["A", "B", "C"])
    client.post(f"/portal/collections/{coll['collection_id']}/memories/{m1['memory_id']}/move-up", headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    memories = svc.get_collection_memories(coll["collection_id"])
    titles = [m["title"] for m in sorted(memories, key=lambda m: m.get("sequence_number", 0))]
    assert titles == ["A", "B", "C"]
    client.post(f"/portal/collections/{coll['collection_id']}/memories/{m3['memory_id']}/move-down", headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    memories = svc.get_collection_memories(coll["collection_id"])
    titles = [m["title"] for m in sorted(memories, key=lambda m: m.get("sequence_number", 0))]
    assert titles == ["A", "B", "C"]


def test_move_preserves_other_sections(client, temp_db):
    """IDs, content, and versions of unchanged sections remain correct after move."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "preserve test", "title": "Preserve", "source": "test", "expected_item_count": 3})
    m1, m2, m3 = _make_sections(svc, coll, ["A", "B", "C"])
    v1_before = svc.get_memory(m1["memory_id"])["version"]
    v3_before = svc.get_memory(m3["memory_id"])["version"]
    client.post(f"/portal/collections/{coll['collection_id']}/memories/{m2['memory_id']}/move-up", headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert svc.get_memory(m1["memory_id"])["title"] == "A"
    assert svc.get_memory(m1["memory_id"])["raw_content"] == "a"
    assert svc.get_memory(m1["memory_id"])["version"] == v1_before
    assert svc.get_memory(m3["memory_id"])["title"] == "C"
    assert svc.get_memory(m3["memory_id"])["raw_content"] == "c"
    assert svc.get_memory(m3["memory_id"])["version"] == v3_before


def test_collection_version_increments_on_reorder(client, temp_db):
    """Collection version increments when reordering sections."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "version-test", "title": "Version Test", "source": "test", "expected_item_count": 2})
    m1, m2 = _make_sections(svc, coll, ["A", "B"])
    v_before = svc.get_collection(coll["collection_id"])["version"]
    client.post(f"/portal/collections/{coll['collection_id']}/memories/{m1['memory_id']}/move-down", headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    v_after = svc.get_collection(coll["collection_id"])["version"]
    assert v_after == v_before + 1


# ---- Independent Collection Memory editing ----

def test_independent_collection_memory_edit(client, temp_db):
    """Editing one Collection Memory does not rewrite the Collection."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "indep test", "title": "Indep", "source": "test"})
    (mem,) = _make_sections(svc, coll, ["indep section"])
    svc.update_memory(mem["memory_id"], {"title": "indep section edited", "expected_version": 1}, actor="portal")
    updated_mem = svc.get_memory(mem["memory_id"])
    assert updated_mem["title"] == "indep section edited"
    updated_coll = svc.get_collection(coll["collection_id"])
    assert updated_coll["status"] == "draft"