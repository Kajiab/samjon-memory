"""Portal vocabulary word bank tests (Portal-only feature).

Covers the file-backed store (defaults, add/remove, dedupe, caps, corrupt-file
fallback), the /portal/vocabulary admin page (auth, Origin validation, add,
remove), and the datalist suggestions + auto-collect behavior on the Memory /
Collection create, edit, and Add-Section forms.
"""
import os

os.environ.setdefault("SAMJON_PORTAL_USERNAME", "portal-admin")
os.environ.setdefault("SAMJON_PORTAL_PASSWORD", "portal-secret")
os.environ.setdefault("SAMJON_PORTAL_ALLOWED_ORIGINS", "http://localhost:8100,http://127.0.0.1:8100")

import pytest
from fastapi.testclient import TestClient

from samjon_memory.core.main import app
from samjon_memory.portal import vocabulary


@pytest.fixture
def client(temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    c = TestClient(app)
    c.auth = ("portal-admin", "portal-secret")
    return c


def _save(overrides=None):
    """Persist a vocabulary state seeded from the defaults plus overrides."""
    from samjon_memory.portal.vocabulary import empty_vocabulary
    vocab = empty_vocabulary()
    for key, words in (overrides or {}).items():
        vocab[key] = words
    vocabulary.save_vocabulary(vocab)
    return vocab


# ---- Store: defaults & corruption -------------------------------------------

def test_defaults_when_no_file():
    vocab = vocabulary.load_vocabulary()
    assert set(vocab) == set(vocabulary.VOCAB_LISTS)
    assert "person" in vocab["subject"]
    assert "pet" in vocab["subject"]
    assert "fact" in vocab["memory_type"]
    assert "guide" in vocab["collection_type"]
    assert "household" in vocab["scope"]


def test_corrupt_file_returns_seeded_defaults(tmp_path, monkeypatch):
    store = tmp_path / "portal_vocabulary.json"
    store.write_text("{ not json", encoding="utf-8")
    monkeypatch.setenv("SAMJON_PORTAL_VOCABULARY_PATH", str(store))
    vocab = vocabulary.load_vocabulary()
    assert vocab["subject"] == vocabulary.DEFAULT_VOCABULARY["subject"]


# ---- Store: normalize / add / remove / caps ----------------------------------

def test_normalize_words_splits_commas_and_newlines():
    raw = "person, plant\npet\r\n person"
    assert vocabulary.normalize_words(raw) == ["person", "plant", "pet"]


def test_add_words_dedupes_and_counts():
    vocab = vocabulary.empty_vocabulary()
    added = vocabulary.add_words(vocab, "subject", ["person", "Place", "place", " food "])
    assert added == 2
    assert vocab["subject"] == vocabulary.DEFAULT_VOCABULARY["subject"] + ["Place", "food"]


def test_add_words_accepts_raw_string():
    vocab = vocabulary.empty_vocabulary()
    added = vocabulary.add_words(vocab, "scope", "personal, garden\nwork")
    assert added == 2  # 'personal' is already seeded
    assert "garden" in vocab["scope"]
    assert "work" in vocab["scope"]


def test_add_words_rejects_unknown_list():
    vocab = vocabulary.empty_vocabulary()
    assert vocabulary.add_words(vocab, "bogus", ["x"]) == 0


def test_add_words_enforces_per_list_cap():
    vocab = {key: [] for key in vocabulary.VOCAB_LISTS}
    added = vocabulary.add_words(
        vocab, "scope", [f"word-{i}" for i in range(vocabulary.MAX_WORDS_PER_LIST + 5)])
    assert added == vocabulary.MAX_WORDS_PER_LIST
    assert len(vocab["scope"]) == vocabulary.MAX_WORDS_PER_LIST


def test_remove_word_case_insensitive():
    vocab = vocabulary.empty_vocabulary()
    assert vocabulary.remove_word(vocab, "subject", "PERSON") is True
    assert "person" not in vocab["subject"]
    assert vocabulary.remove_word(vocab, "subject", "missing") is False


def test_collect_writes_only_new_words():
    vocabulary.collect(subject="recipe", memory_type="schedule", scope="personal")
    vocab = vocabulary.load_vocabulary()
    assert "recipe" in vocab["subject"]
    assert "schedule" in vocab["memory_type"]
    # 'personal' already in the seeded scope list -> no duplicate
    assert vocab["scope"].count("personal") == 1


# ---- Admin page: auth and content -------------------------------------------

def test_vocabulary_page_requires_auth():
    c = TestClient(app)
    assert c.get("/portal/vocabulary").status_code == 401


def test_vocabulary_page_lists_sections_and_counts(client):
    _save()
    resp = client.get("/portal/vocabulary")
    assert resp.status_code == 200
    for label in ("Subject", "Memory Type", "Collection Type", "Scope"):
        assert label in resp.text
    assert "/portal/vocabulary/subject/remove" in resp.text
    assert 'name="list" value="memory_type"' in resp.text
    assert "person" in resp.text
    assert "fact" in resp.text
    assert '<a class="btn btn-ghost" href="/portal/status">Back to Status</a>' in resp.text


def test_vocabulary_page_has_no_credentials(client):
    _save()
    resp = client.get("/portal/vocabulary")
    assert "portal-admin" not in resp.text
    assert "portal-secret" not in resp.text


def test_vocabulary_add_origin_validation(client):
    _save()
    resp = client.post("/portal/vocabulary/add",
                       data={"list": "subject", "words": "garden"},
                       headers={"Origin": "http://evil.example"},
                       follow_redirects=False)
    assert resp.status_code == 403


def test_vocabulary_add_saves_words(client):
    _save()
    resp = client.post("/portal/vocabulary/add",
                       data={"list": "memory_type", "words": "recipe, checklist"},
                       headers={"Origin": "http://localhost:8100"},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert "message=words_added" in resp.headers["location"]
    types = vocabulary.load_vocabulary()["memory_type"]
    assert "recipe" in types and "checklist" in types


def test_vocabulary_add_duplicates_are_noops(client):
    _save()
    resp = client.post("/portal/vocabulary/add",
                       data={"list": "subject", "words": "person"},
                       headers={"Origin": "http://localhost:8100"},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert "message=no_words_added" in resp.headers["location"]


def test_vocabulary_add_unknown_list_is_error(client):
    resp = client.post("/portal/vocabulary/add",
                       data={"list": "bogus", "words": "x"},
                       headers={"Origin": "http://localhost:8100"},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert "message=error:" in resp.headers["location"]


def test_vocabulary_remove_word(client):
    _save({"subject": ["person", "recipe"]})
    resp = client.post("/portal/vocabulary/subject/remove",
                       data={"word": "PERSON"},
                       headers={"Origin": "http://localhost:8100"},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert "message=word_removed" in resp.headers["location"]
    assert vocabulary.load_vocabulary()["subject"] == ["recipe"]


# ---- Form suggestions ---------------------------------------------------------

def test_memory_create_form_has_datalists(client):
    _save()
    body = client.get("/portal/memories/create").text
    assert 'list="subject-vocab"' in body
    assert '<datalist id="subject-vocab">' in body
    assert '<option value="person"></option>' in body
    assert '<datalist id="memory_type-vocab">' in body
    assert '<datalist id="scope-vocab">' in body


def test_collection_create_form_has_datalists(client):
    _save()
    body = client.get("/portal/collections/create").text
    assert '<datalist id="subject-vocab">' in body
    assert '<datalist id="collection_type-vocab">' in body
    assert '<datalist id="scope-vocab">' in body


def test_edit_forms_include_current_value_in_suggestions(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "person:jeab", "raw_content": "x", "source": "t"})
    body = client.get(f"/portal/memories/{mem['memory_id']}/edit").text
    assert '<option value="person:jeab"></option>' in body
    assert '<option value="person"></option>' in body  # collected suggestions follow


def test_section_edit_form_type_datalist_only(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "plants:garden", "title": "Garden", "source": "t"})
    mem = svc.create_memory({"subject": "plants:garden", "raw_content": "x", "source": "t"})
    svc.add_memory_to_collection(coll["collection_id"], mem["memory_id"], 1)
    body = client.get(f"/portal/memories/{mem['memory_id']}/edit").text
    assert '<datalist id="memory_type-vocab">' in body
    assert 'name="subject"' not in body
    assert 'name="scope"' not in body


def test_add_section_form_type_datalist_and_no_subject_scope(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "plants:garden", "title": "Garden", "source": "t"})
    body = client.get(f"/portal/collections/{coll['collection_id']}").text
    form = body.split(f'action="/portal/collections/{coll["collection_id"]}/memories"')[1].split("</form>")[0]
    assert '<datalist id="memory_type-vocab">' in form
    assert 'name="subject"' not in form
    assert 'name="scope"' not in form


# ---- Auto-collect on successful Portal mutations -----------------------------

def test_create_memory_collects_new_words(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    client.post("/portal/memories", data={
        "subject": "device:water-pump", "memory_type": "schedule",
        "scope": "property", "raw_content": "c", "source": "portal",
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    vocab = vocabulary.load_vocabulary()
    assert "device:water-pump" in vocab["subject"]
    assert "schedule" in vocab["memory_type"]
    assert "property" in vocab["scope"]


def test_create_collection_collects_new_words(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    client.post("/portal/collections", data={
        "subject": "inventory:spares", "collection_type": "checklist",
        "scope": "household", "title": "Spares", "source": "portal",
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    vocab = vocabulary.load_vocabulary()
    assert "inventory:spares" in vocab["subject"]
    assert "checklist" in vocab["collection_type"]


def test_edit_memory_collects_new_subject(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    mem = svc.create_memory({"subject": "old", "raw_content": "x", "source": "t"})
    client.post(f"/portal/memories/{mem['memory_id']}", data={
        "subject": "topic:recipes", "raw_content": "x", "source": "t",
        "expected_version": str(mem["version"]),
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert "topic:recipes" in vocabulary.load_vocabulary()["subject"]


def test_add_section_collects_type_only(client, temp_db):
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    coll = svc.create_collection({"subject": "plant:monstera", "title": "Monstera", "source": "t"})
    client.post(f"/portal/collections/{coll['collection_id']}/memories", data={
        "title": "Watering", "memory_type": "care_instruction", "raw_content": "daily",
    }, headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    vocab = vocabulary.load_vocabulary()
    assert "care_instruction" in vocab["memory_type"]
    # add-section must not invent subject/scope words
    assert "Watering" not in vocab["subject"]
    assert "daily" not in vocab["scope"]


def test_rejected_request_does_not_collect(client, temp_db):
    """A request rejected before the mutation must not write vocabulary."""
    from samjon_memory.core.service import CoreService
    svc = CoreService(database_path=temp_db)
    app.state.service = svc
    resp = client.post("/portal/memories", data={
        "subject": "never-saved-subject", "raw_content": "c", "source": "t",
    }, headers={"Origin": "http://evil.example"}, follow_redirects=False)
    assert resp.status_code == 403
    assert "never-saved-subject" not in vocabulary.load_vocabulary()["subject"]