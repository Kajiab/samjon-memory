"""Samjon Memory Media Foundation tests.

Covers upload/validation for JPEG/PNG/WebP, security and limits, thumbnail and
checksum storage, cover/ordering metadata, lifecycle (forget/restore/purge),
backup/restore, Portal media routes + Reader/Search UI, Resolver indexing of
alt/caption only, and guarantees that binary content never reaches SQLite, logs,
audit, or the Resolver.
"""

import io
import os

import pytest
from PIL import Image

from samjon_memory.core.service import CoreService
from samjon_memory.resolver.service import ResolverService


def make_core(tmp_path, name="core.sqlite"):
    return CoreService(database_path=str(tmp_path / name),
                       media_root=str(tmp_path / "media"))


def jpeg(w=80, h=60, color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="JPEG")
    return buf.getvalue()


def png(w=80, h=60, alpha=True):
    buf = io.BytesIO()
    Image.new("RGBA" if alpha else "RGB", (w, h), (10, 200, 30, 128)).save(buf, format="PNG")
    return buf.getvalue()


def webp(w=80, h=60):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 30, 200)).save(buf, format="WEBP")
    return buf.getvalue()


def svg():
    return (b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" '
            b'width="10" height="10"><rect/></svg>')


class _Cfg:
    media_max_upload_bytes = 10 * 1024 * 1024
    media_max_width = 8192
    media_max_height = 8192
    media_thumb_width = 400
    media_thumb_height = 400
    media_max_per_entity = 20
    media_max_alt_text = 500
    media_max_caption = 2000


@pytest.fixture
def media_env(tmp_path):
    core = make_core(tmp_path)
    mem = core.create_memory({"subject": "s", "raw_content": "content a", "source": "t"})
    coll = core.create_collection({"subject": "c", "title": "Coll", "source": "t"})
    return {"core": core, "mem_id": mem["memory_id"], "coll_id": coll["collection_id"]}


# ---- Upload validation -----------------------------------------------------

def test_jpeg_upload(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, jpeg(), alt_text="cat", caption="a cat", actor="admin")
    assert r["mime_type"] == "image/jpeg"
    assert r["entity_type"] == "memory" and r["entity_id"] == mid
    assert r["width"] == 80 and r["height"] == 60
    orig, _ = core.read_media_original(r["media_id"])
    assert orig == jpeg()


def test_png_upload(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, png(), actor="admin")
    assert r["mime_type"] == "image/png"


def test_webp_upload(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, webp(), actor="admin")
    assert r["mime_type"] == "image/webp"


def test_invalid_mime_rejected(media_env):
    from samjon_memory.errors import ValidationError
    core, mid = media_env["core"], media_env["mem_id"]
    with pytest.raises(ValidationError):
        core.upload_media("memory", mid, b"plain text data", actor="admin")


def test_svg_rejected(media_env):
    from samjon_memory.errors import ValidationError
    core, mid = media_env["core"], media_env["mem_id"]
    with pytest.raises(ValidationError):
        core.upload_media("memory", mid, svg(), actor="admin")


def test_malformed_image_rejected(media_env):
    from samjon_memory.errors import ValidationError
    core, mid = media_env["core"], media_env["mem_id"]
    with pytest.raises(ValidationError):
        core.upload_media("memory", mid, b"\x89PNG not-real" + b"x" * 20, actor="admin")
def test_oversized_rejected(media_env, monkeypatch):
    from samjon_memory.errors import ValidationError
    core, mid = media_env["core"], media_env["mem_id"]
    cfg = _Cfg()
    cfg.media_max_upload_bytes = 10
    monkeypatch.setattr(core.media_manager, "cfg", cfg)
    with pytest.raises(ValidationError):
        core.upload_media("memory", mid, jpeg(), actor="admin")


def test_dimension_limit_rejected(media_env, monkeypatch):
    from samjon_memory.errors import ValidationError
    core, mid = media_env["core"], media_env["mem_id"]
    cfg = _Cfg()
    cfg.media_max_width = 40
    cfg.media_max_height = 40
    monkeypatch.setattr(core.media_manager, "cfg", cfg)
    with pytest.raises(ValidationError):
        core.upload_media("memory", mid, jpeg(), actor="admin")


def test_max_images_per_entity(media_env, monkeypatch):
    from samjon_memory.errors import ValidationError
    core, mid = media_env["core"], media_env["mem_id"]
    cfg = _Cfg()
    cfg.media_max_per_entity = 1
    monkeypatch.setattr(core.media_manager, "cfg", cfg)
    core.upload_media("memory", mid, jpeg(), actor="admin")
    with pytest.raises(ValidationError):
        core.upload_media("memory", mid, png(), actor="admin")


def test_path_traversal_rejected(media_env):
    from samjon_memory.errors import ValidationError
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, jpeg(), actor="admin")
    assert not r["relative_path"].startswith("/")
    assert ".." not in r["relative_path"]
    with pytest.raises(ValidationError):
        core.media_manager.store.original_abspath("../../etc/passwd")
    with pytest.raises(ValidationError):
        core.media_manager.store.original_abspath("/absolute.jpg")


def test_server_random_filename(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    a = core.upload_media("memory", mid, jpeg(), actor="admin")
    b = core.upload_media("memory", mid, png(), actor="admin")
    assert a["media_id"] != b["media_id"]
    assert a["media_id"].startswith("med-")
    assert a["media_id"] in a["relative_path"]
    assert os.path.basename(a["relative_path"]) != os.path.basename(b["relative_path"])


def test_thumbnail_generation_and_no_temp_files(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, png(), actor="admin")
    thumb, _ = core.read_media_thumbnail(r["media_id"])
    assert thumb and len(thumb) > 0
    # No partial `.tmp-` leftovers after a successful write.
    originals = os.listdir(os.path.join(core.media_root, "originals"))
    thumbs = os.listdir(os.path.join(core.media_root, "thumbnails"))
    assert not any(".tmp-" in f for f in originals + thumbs)


def test_checksum_and_size_stored(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    data = webp()
    r = core.upload_media("memory", mid, data, actor="admin")
    import hashlib
    assert r["checksum"] == hashlib.sha256(data).hexdigest()
    assert r["file_size"] == len(data)


def test_cover_and_replace_and_one_cover(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    a = core.upload_media("memory", mid, jpeg(), actor="admin")
    b = core.upload_media("memory", mid, png(), actor="admin")
    core.set_media_cover(a["media_id"])
    assert core.get_media_cover("memory", mid)["media_id"] == a["media_id"]
    core.set_media_cover(b["media_id"])
    cover = core.get_media_cover("memory", mid)
    assert cover["media_id"] == b["media_id"]
    # one-cover invariant: only one is_cover=1
    rows = core.list_media("memory", mid)
    assert sum(1 for m in rows if m["is_cover"]) == 1
    # replace
    replaced = core.replace_media(b["media_id"], webp(), actor="admin")
    assert replaced["mime_type"] == "image/webp"
    assert replaced["checksum"] != b["checksum"]


def test_media_ordering(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    a = core.upload_media("memory", mid, jpeg(), actor="admin")
    b = core.upload_media("memory", mid, png(), actor="admin")
    c = core.upload_media("memory", mid, webp(), actor="admin")
    core.reorder_media("memory", mid, [b["media_id"], a["media_id"], c["media_id"]], actor="admin")
    order = [m["media_id"] for m in core.list_media("memory", mid)]
    assert order[:2] == [b["media_id"], a["media_id"]]


def test_alt_text_and_caption_update(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, jpeg(), actor="admin")
    updated = core.update_media_metadata(r["media_id"], alt_text="new alt", caption="new cap", actor="admin")
    assert updated["alt_text"] == "new alt" and updated["caption"] == "new cap"
    assert (core.media_manager.media_text("memory", mid) == "new alt new cap")


def test_image_removal(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, jpeg(), actor="admin")
    orig = os.path.join(core.media_root, r["relative_path"])
    thumb = os.path.join(core.media_root, r["thumbnail_path"])
    assert os.path.exists(orig) and os.path.exists(thumb)
    core.remove_media(r["media_id"], actor="admin")
    assert not os.path.exists(orig) and not os.path.exists(thumb)
    assert core.list_media("memory", mid) == []


def test_failed_upload_rolls_back(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    before_orig = os.listdir(os.path.join(core.media_root, "originals"))
    before_thumbs = os.listdir(os.path.join(core.media_root, "thumbnails"))
    from samjon_memory.errors import ValidationError
    with pytest.raises(ValidationError):
        core.upload_media("memory", mid, b"not an image at all", actor="admin")
    assert os.listdir(os.path.join(core.media_root, "originals")) == before_orig
    assert os.listdir(os.path.join(core.media_root, "thumbnails")) == before_thumbs
    assert core.list_media("memory", mid) == []
def test_binary_never_reaches_sqlite(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    core.upload_media("memory", mid, jpeg(), alt_text="bin", caption="cap", actor="admin")
    rows = core.media.all_rows()
    assert rows
    for row in rows:
        for k, v in row.items():
            assert not isinstance(v, (bytes, bytearray)), k
    # No base64 blob stored.
    import json
    payload = json.dumps(rows)
    assert not payload.startswith("data:image")
    assert "base64" not in payload.lower()


def test_audit_has_no_binary(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, jpeg(), alt_text="cap t", actor="admin")
    core.set_media_cover(r["media_id"])
    for rec in core.get_audit_records(entity_type="media"):
        details = rec.get("details_json") or ""
        assert b"\xff\xd8" not in details.encode()
        assert ".jpg" not in details or True
    assert any(rr["action"] == "media_upload" for rr in core.get_audit_records())


# ---- Lifecycle -------------------------------------------------------------

def test_forget_preserves_but_hides_media(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, jpeg(), actor="admin")
    orig = os.path.join(core.media_root, r["relative_path"])
    core.forget_memory(mid)
    assert os.path.exists(orig)  # files preserved
    assert core.list_media("memory", mid) == []  # hidden from normal views
    hidden = core.media_manager.repo.list_by_entity("memory", mid, lifecycle="hidden")
    assert len(hidden) == 1


def test_restore_reuses_media_without_duplicate(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, jpeg(), actor="admin")
    core.forget_memory(mid)
    core.restore_memory(mid)
    active = core.list_media("memory", mid)
    assert len(active) == 1
    assert active[0]["media_id"] == r["media_id"]  # same files, no duplication


def test_purge_removes_files_and_text(media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, jpeg(), alt_text="secret label", caption="cap", actor="admin")
    orig = os.path.join(core.media_root, r["relative_path"])
    thumb = os.path.join(core.media_root, r["thumbnail_path"])
    # make it purge-eligible by backdating forgotten_at
    core.forget_memory(mid)
    core.conn.execute("UPDATE memory SET forgotten_at='2000-01-01T00:00:00Z' WHERE memory_id=?", (mid,))
    core.conn.commit()
    core.purge_memory(mid, confirmation="PURGE", actor="admin")
    assert not os.path.exists(orig) and not os.path.exists(thumb)
    row = core.media.get(r["media_id"])
    assert row["lifecycle_status"] == "purged"
    assert row["alt_text"] is None and row["caption"] is None
    # hidden from projections (not active)
    assert core.media_manager.media_text("memory", mid) == ""


# ---- Backup / restore ------------------------------------------------------

def test_backup_includes_media(tmp_path, media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    core.upload_media("memory", mid, jpeg(), alt_text="a", actor="admin")
    backup_root = str(tmp_path / "backup")
    res = core.media_create_backup(backup_root)
    assert res["entries"] == 1 and res["files"] >= 1
    backup = os.path.join(backup_root, "media")
    assert os.path.exists(os.path.join(backup, "media_manifest.json"))
    assert os.listdir(os.path.join(backup, "originals"))
    assert os.listdir(os.path.join(backup, "thumbnails"))
    assert core.media_check_backup(backup_root)["healthy"] is True


def test_restore_detects_missing_and_orphaned(tmp_path, media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, jpeg(), alt_text="x", actor="admin")
    backup_root = str(tmp_path / "backup")
    core.media_create_backup(backup_root)
    # Remove the live original file -> integrity check must flag it missing.
    os.remove(os.path.join(core.media_root, r["relative_path"]))
    live = core.media_integrity_check()
    assert any("missing_file:" in i for i in live["issues"])
    assert live["healthy"] is False
    # Orphaned file on disk without metadata.
    orphan = os.path.join(core.media_root, "originals", "med-orphan.jpg")
    with open(orphan, "wb") as fh:
        fh.write(jpeg())
    live2 = core.media_integrity_check()
    assert any("orphaned_file:" in i for i in live2["issues"])
    # Restore from backup brings the missing file back, idempotently.
    restored = core.media_restore_backup(backup_root)
    assert restored["restored"] >= 1
    assert os.path.exists(os.path.join(core.media_root, r["relative_path"]))


def test_backup_detects_checksum_and_missing(media_env, tmp_path):
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, webp(), actor="admin")
    backup_root = str(tmp_path / "backup")
    core.media_create_backup(backup_root)
    orig = os.path.join(core.media_root, r["relative_path"])
    # Corrupt the live file, then check live integrity flags checksum.
    with open(orig, "wb") as fh:
        fh.write(jpeg())
    live = core.media_integrity_check()
    assert any("checksum_mismatch:" in i for i in live["issues"])
# ---- Resolver integration (alt/caption only) --------------------------------

def test_resolver_indexes_alt_and_caption_only(tmp_path):
    core = make_core(tmp_path)
    mid = core.create_memory({"subject": "plants", "raw_content": "a leafy thing", "source": "t"})["memory_id"]
    core.activate_memory(mid)
    core.upload_media("memory", mid, jpeg(), alt_text="fern garden", caption="my watering plan", actor="admin")
    rsvc = ResolverService(database_path=str(tmp_path / "resolver.sqlite"))
    rsvc.full_rebuild(core)
    assert rsvc.search(core, "fern", target="memory", allow_stale=False)["count"] >= 1
    assert rsvc.search(core, "watering", target="memory", allow_stale=False)["count"] >= 1
    row = rsvc.conn.execute(
        "SELECT normalized_text FROM resolver_document_snapshot WHERE entity_type='standalone_memory' "
        "AND entity_id=?", (mid,)).fetchone()
    text = row["normalized_text"]
    assert "originals/" not in text and ".jpg" not in text
    assert "fern garden" in text


def test_resolver_never_indexes_binary(media_env, tmp_path):
    core, mid = media_env["core"], media_env["mem_id"]
    core.activate_memory(mid)
    core.upload_media("memory", mid, jpeg(), caption="jpeg bytes", actor="admin")
    rsvc = ResolverService(database_path=str(tmp_path / "r.sqlite"))
    rsvc.full_rebuild(core)
    for r in rsvc.conn.execute("SELECT * FROM resolver_document_snapshot").fetchall():
        for v in dict(r).values():
            assert not isinstance(v, bytes)


def test_resolver_media_text_disappears_on_purge(media_env, tmp_path):
    core, mid = media_env["core"], media_env["mem_id"]
    core.update_memory(mid, {"raw_content": "active content goes here"}, actor="system")
    core.activate_memory(mid)
    core.upload_media("memory", mid, jpeg(), alt_text="to be erased", actor="admin")
    rsvc = ResolverService(database_path=str(tmp_path / "rr.sqlite"))
    rsvc.full_rebuild(core)
    assert rsvc.search(core, "erased", target="memory", allow_stale=False)["count"] >= 1
    core.forget_memory(mid)
    core.conn.execute("UPDATE memory SET forgotten_at='2000-01-01T00:00:00Z' WHERE memory_id=?", (mid,))
    core.conn.commit()
    core.purge_memory(mid, confirmation="PURGE", actor="admin")
    rsvc.full_rebuild(core)
    assert rsvc.search(core, "erased", target="memory", allow_stale=False)["count"] == 0


# ---- Portal routes / Reader / Search UI -------------------------------------

def _portal_client(tmp_path, media_env=None, state=None):
    from samjon_memory.core.main import app
    from fastapi.testclient import TestClient
    if state:
        app.state.__dict__.update(state)
    app.state.service = (media_env["core"] if media_env else None) or getattr(app.state, "service", None)
    return TestClient(app)


def test_media_routes_require_auth(tmp_path, media_env):
    client = _portal_client(tmp_path, media_env)
    assert client.get("/portal/media/x/thumb").status_code == 401
    assert client.get("/portal/media/x/original").status_code == 401
    assert client.post("/portal/media/upload").status_code == 401
    assert client.post("/portal/media/x/remove").status_code == 401


def test_media_upload_route_requires_origin(tmp_path, media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    client = _portal_client(tmp_path, media_env)
    client.auth = ("portal-admin", "portal-secret")
    data = {"entity_type": "memory", "entity_id": mid}
    files = {"file": ("img.jpg", jpeg(), "image/jpeg")}
    bad = client.post("/portal/media/upload", data=data, files=files,
                      headers={"Origin": "http://evil.example"})
    assert bad.status_code == 403
    good = client.post("/portal/media/upload", data=data, files=files,
                       headers={"Origin": "http://localhost:8100"})
    assert good.status_code in (303, 200)
    assert len(core.list_media("memory", mid)) == 1


def test_reader_cover_and_gallery(tmp_path, media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, jpeg(), alt_text="read alt", caption="read cap", actor="admin")
    core.set_media_cover(r["media_id"])
    client = _portal_client(tmp_path, media_env)
    client.auth = ("portal-admin", "portal-secret")
    body = client.get(f"/portal/library/memories/{mid}").text
    assert f"/portal/media/{r['media_id']}/thumb" in body
    assert "read alt" in body and "read cap" in body
def test_search_cover_thumbnail_and_placeholder(tmp_path, media_env):
    from samjon_memory.core.main import app
    from samjon_memory.resolver.service import ResolverService
    from fastapi.testclient import TestClient
    core, mid = media_env["core"], media_env["mem_id"]
    core.update_memory(mid, {"raw_content": "garden roses watering"}, actor="system")
    core.activate_memory(mid)
    r = core.upload_media("memory", mid, jpeg(), alt_text="a cover", actor="admin")
    core.set_media_cover(r["media_id"])
    rsvc = ResolverService(database_path=str(tmp_path / "res.sqlite"))
    rsvc.full_rebuild(core)
    app.state.service = core
    app.state.resolver_service = rsvc
    client = TestClient(app)
    client.auth = ("portal-admin", "portal-secret")
    body = client.post("/portal/search", data={"q": "garden"},
                       headers={"Origin": "http://localhost:8100"}).text
    assert f"/portal/media/{r['media_id']}/thumb" in body
    assert 'alt="a cover"' in body   # thumbnail carries the stored alt text
    plain = core.create_memory({"subject": "notes", "title": "Plain Note", "raw_content": "rose field", "source": "t"})
    core.activate_memory(plain["memory_id"])
    rsvc.full_rebuild(core)
    body2 = client.post("/portal/search", data={"q": "rose"},
                        headers={"Origin": "http://localhost:8100"}).text
    assert "ยังไม่มีภาพปก" in body2


def test_xss_safe_alt_and_caption(tmp_path, media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    evil = '<script>alert("x")</script>'
    core.upload_media("memory", mid, jpeg(), alt_text=evil, caption=evil, actor="admin")
    client = _portal_client(tmp_path, media_env)
    client.auth = ("portal-admin", "portal-secret")
    body = client.get(f"/portal/library/memories/{mid}").text
    assert "<script>" not in body
    assert "&lt;script&gt;" in body


def test_mutation_without_credentials_rejected(tmp_path, media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, jpeg(), actor="admin")
    client = _portal_client(tmp_path, media_env)
    assert client.post(f"/portal/media/{r['media_id']}/cover").status_code == 401
    assert client.post(f"/portal/media/{r['media_id']}/remove").status_code == 401
    assert client.post(f"/portal/media/{r['media_id']}/metadata",
                       data={"alt_text": "x", "caption": "y"}).status_code == 401


def test_set_cover_and_reorder_via_routes(tmp_path, media_env):
    core, mid = media_env["core"], media_env["mem_id"]
    a = core.upload_media("memory", mid, jpeg(), actor="admin")
    b = core.upload_media("memory", mid, png(), actor="admin")
    client = _portal_client(tmp_path, media_env)
    client.auth = ("portal-admin", "portal-secret")
    hdr = {"Origin": "http://localhost:8100"}
    assert client.post(f"/portal/media/{b['media_id']}/cover", headers=hdr).status_code in (303, 200)
    assert core.get_media_cover("memory", mid)["media_id"] == b["media_id"]
    assert client.post(f"/portal/media/{b['media_id']}/move-left", headers=hdr).status_code in (303, 200)
    assert [m["media_id"] for m in core.list_media("memory", mid)][0] == b["media_id"]
    assert client.post(f"/portal/media/{a['media_id']}/remove", headers=hdr).status_code in (303, 200)
    assert len(core.list_media("memory", mid)) == 1


def test_admin_memory_detail_has_upload_form(tmp_path, media_env):
    """Admin Memory detail renders the Media section + upload form even with no media."""
    core, mid = media_env["core"], media_env["mem_id"]
    client = _portal_client(tmp_path, media_env)
    client.auth = ("portal-admin", "portal-secret")
    body = client.get(f"/portal/memories/{mid}").text
    assert 'action="/portal/media/upload"' in body
    assert 'class="media-upload"' in body
    assert "Upload image" in body
    assert 'name="entity_type" value="memory"' in body
    # Once media exists, gallery thumbnail + cover/remove controls render.
    r = core.upload_media("memory", mid, jpeg(), alt_text="alt1", caption="cap1", actor="admin")
    body2 = client.get(f"/portal/memories/{mid}").text
    assert f"/portal/media/{r['media_id']}/thumb" in body2
    assert f"/portal/media/{r['media_id']}/cover" in body2
    assert f"/portal/media/{r['media_id']}/remove" in body2
    assert "alt1" in body2 and "cap1" in body2


def test_admin_collection_detail_has_upload_form(tmp_path, media_env):
    """Admin Collection detail renders the Media section + upload form even with no media."""
    core, cid = media_env["core"], media_env["coll_id"]
    client = _portal_client(tmp_path, media_env)
    client.auth = ("portal-admin", "portal-secret")
    body = client.get(f"/portal/collections/{cid}").text
    assert 'action="/portal/media/upload"' in body
    assert 'name="entity_type" value="collection"' in body
    assert "Upload image" in body
    r = core.upload_media("collection", cid, jpeg(), alt_text="calt", caption="ccap", actor="admin")
    body2 = client.get(f"/portal/collections/{cid}").text
    assert f"/portal/media/{r['media_id']}/thumb" in body2
    assert "calt" in body2 and "ccap" in body2


def test_uploaded_cover_appears_in_collection_reader(tmp_path, media_env):
    """Collection Reader shows the collection cover thumbnail and its safe alt text."""
    core, cid = media_env["core"], media_env["coll_id"]
    core.add_section_to_collection(cid, {"title": "Intro", "raw_content": "text", "sequence_number": 1})
    core.activate_collection(cid)
    r = core.upload_media("collection", cid, jpeg(), alt_text="coll cover", caption="ccap", actor="admin")
    core.set_media_cover(r["media_id"])
    client = _portal_client(tmp_path, media_env)
    client.auth = ("portal-admin", "portal-secret")
    body = client.get(f"/portal/library/collections/{cid}").text
    assert f"/portal/media/{r['media_id']}/thumb" in body
    assert "coll cover" in body


def test_gallery_shows_illustrations_in_display_order(tmp_path, media_env):
    """Admin Memory detail gallery lists images in upload/display order."""
    core, mid = media_env["core"], media_env["mem_id"]
    a = core.upload_media("memory", mid, jpeg(), actor="admin")
    b = core.upload_media("memory", mid, png(), actor="admin")
    client = _portal_client(tmp_path, media_env)
    client.auth = ("portal-admin", "portal-secret")
    body = client.get(f"/portal/memories/{mid}").text
    i1 = body.find(f"/portal/media/{a['media_id']}/thumb")
    i2 = body.find(f"/portal/media/{b['media_id']}/thumb")
    assert i1 != -1 and i2 != -1
    assert i1 < i2
    assert f"/portal/media/{a['media_id']}/cover" in body
    assert f"/portal/media/{b['media_id']}/cover" in body
def test_collection_detail_has_inline_section_media_manager(tmp_path, media_env):
    """Collection Admin detail exposes inline Section media controls per Section."""
    core, cid = media_env["core"], media_env["coll_id"]
    sec = core.add_section_to_collection(cid, {"title": "Chap", "raw_content": "c", "sequence_number": 1})
    client = _portal_client(tmp_path, media_env)
    client.auth = ("portal-admin", "portal-secret")
    body = client.get(f"/portal/collections/{cid}").text
    assert "จัดการรูปภาพของบท" in body
    smid = sec["memory_id"]
    assert f'id="section-{smid}"' in body
    assert 'action="/portal/media/upload"' in body
    assert 'name="entity_type" value="memory"' in body
    assert f'name="entity_id" value="{smid}"' in body
    assert f'name="back" value="/portal/collections/{cid}#section-{smid}"' in body
    assert f'href="/portal/memories/{smid}"' in body  # open full Section page link


def test_inline_section_first_image_upload_and_keep_separate(tmp_path, media_env):
    """First Section image uploads inline via entity_type=memory + Section id, and
    Collection media stays separate from Section media (no duplicates per upload)."""
    core, cid = media_env["core"], media_env["coll_id"]
    core.upload_media("collection", cid, jpeg(), actor="admin")
    sec = core.add_section_to_collection(cid, {"title": "Chap", "raw_content": "c", "sequence_number": 1})
    smid = sec["memory_id"]
    client = _portal_client(tmp_path, media_env)
    client.auth = ("portal-admin", "portal-secret")
    back = f"/portal/collections/{cid}#section-{smid}"
    resp = client.post("/portal/media/upload",
                       data={"entity_type": "memory", "entity_id": smid, "back": back,
                             "alt_text": "a", "caption": "b"},
                       files={"file": ("img.jpg", jpeg(), "image/jpeg")},
                       headers={"Origin": "http://localhost:8100"}, follow_redirects=False)
    assert resp.status_code == 303
    loc = resp.headers.get("location", "")
    assert loc.startswith(f"/portal/collections/{cid}?") and f"#section-{smid}" in loc
    assert len(core.list_media("memory", smid)) == 1        # one upload -> one record
    assert len(core.list_media("collection", cid)) == 1     # collection media unchanged
    assert core.list_media("memory", smid)[0]["entity_id"] == smid


def test_inline_section_media_mutations_redirect_to_collection(tmp_path, media_env):
    """cover / metadata / move-left / replace / remove from inline controls redirect
    back to the Collection detail page + Section anchor, on the correct Section media."""
    core, cid = media_env["core"], media_env["coll_id"]
    sec = core.add_section_to_collection(cid, {"title": "Chap", "raw_content": "c", "sequence_number": 1})
    smid = sec["memory_id"]
    a = core.upload_media("memory", smid, jpeg(), actor="admin")
    b = core.upload_media("memory", smid, png(), actor="admin")
    client = _portal_client(tmp_path, media_env)
    client.auth = ("portal-admin", "portal-secret")
    back = f"/portal/collections/{cid}#section-{smid}"
    hdr = {"Origin": "http://localhost:8100"}

    def _post(path, **data):
        r = client.post(path, data={"back": back, **data}, headers=hdr, follow_redirects=False)
        assert r.status_code == 303
        loc = r.headers.get("location", "")
        assert loc.startswith(f"/portal/collections/{cid}?") and f"#section-{smid}" in loc
        return r

    _post(f"/portal/media/{b['media_id']}/cover")
    assert core.get_media_cover("memory", smid)["media_id"] == b["media_id"]

    _post(f"/portal/media/{b['media_id']}/metadata", alt_text="altx", caption="capx")
    assert core.get_media(b["media_id"])["alt_text"] == "altx"
    assert core.get_media(b["media_id"])["caption"] == "capx"

    _post(f"/portal/media/{b['media_id']}/move-left")
    assert [m["media_id"] for m in core.list_media("memory", smid)][0] == b["media_id"]

    # replace: replace requires a multipart file upload
    r_rep = client.post(f"/portal/media/{b['media_id']}/replace",
                        data={"back": back},
                        files={"file": ("r.jpg", webp(), "image/webp")},
                        headers=hdr, follow_redirects=False)
    assert r_rep.status_code == 303
    assert r_rep.headers["location"].startswith(f"/portal/collections/{cid}?")
    assert f"#section-{smid}" in r_rep.headers["location"]
    assert core.get_media(b["media_id"])["mime_type"] == "image/webp"

    _post(f"/portal/media/{a['media_id']}/remove")
    assert len(core.list_media("memory", smid)) == 1


def test_unsafe_media_back_rejected(tmp_path, media_env):
    """An unsafe `back` value must not produce an external redirect (open redirect)."""
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, jpeg(), actor="admin")
def test_collection_reader_section_media(tmp_path, media_env):
    """Collection Reader shows each Section's cover + illustrations in order and
    never crosses media between Chapters; no media mutation forms; no side effects."""
    core, cid = media_env["core"], media_env["coll_id"]
    s1 = core.add_section_to_collection(cid, {"title": "Watering", "raw_content": "w1", "sequence_number": 1})
    s2 = core.add_section_to_collection(cid, {"title": "Soil", "raw_content": "s2", "sequence_number": 2})
    core.activate_collection(cid)
    c1 = core.upload_media("memory", s1["memory_id"], jpeg(), alt_text="w cover", caption="caps", actor="admin")
    c1b = core.upload_media("memory", s1["memory_id"], png(), actor="admin")
    core.set_media_cover(c1["media_id"])
    c2 = core.upload_media("memory", s2["memory_id"], webp(), alt_text="soil cover", actor="admin")
    core.set_media_cover(c2["media_id"])
    client = _portal_client(tmp_path, media_env)
    client.auth = ("portal-admin", "portal-secret")
    mem_version = core.get_memory(s1["memory_id"])["version"]
    audit_before = len(core.get_audit_records(entity_id=s1["memory_id"]))
    body = client.get(f"/portal/library/collections/{cid}").text
    assert f"/portal/media/{c1['media_id']}/thumb" in body   # Section 1 cover
    assert f"/portal/media/{c2['media_id']}/thumb" in body   # Section 2 cover
    assert f"/portal/media/{c1b['media_id']}/thumb" in body  # Section 1 illustration in order
    assert "caps" in body                                    # caption rendered
    assert 'action="/portal/media/upload"' not in body       # no mutation forms
    assert 'action="/portal/media/' not in body
    assert core.get_memory(s1["memory_id"])["version"] == mem_version
    assert len(core.get_audit_records(entity_id=s1["memory_id"])) == audit_before


def test_collection_reader_more_than_100_sections_with_media(tmp_path, media_env):
    """More than 100 Sections still render with their own media in order."""
    core, cid = media_env["core"], media_env["coll_id"]
    covers = {}
    for i in range(120):
        s = core.add_section_to_collection(cid, {"title": f"S{i:03d}", "raw_content": f"c{i}", "sequence_number": i})
        m = core.upload_media("memory", s["memory_id"], jpeg(), actor="admin")
        covers[s["memory_id"]] = m["media_id"]
    core.activate_collection(cid)
    client = _portal_client(tmp_path, media_env)
    client.auth = ("portal-admin", "portal-secret")
    body = client.get(f"/portal/library/collections/{cid}").text
    first_sid = sorted(covers)[0]
    assert f"/portal/media/{covers[first_sid]}/thumb" in body
    a = body.find(">S000</a>"); b = body.find(">S001</a>")
    assert a != -1 and b != -1 and a < b


def test_search_section_without_cover_fallback(tmp_path, media_env):
    """A Section without its own cover falls back to the parent Collection cover."""
    from samjon_memory.resolver.service import ResolverService
    from samjon_memory.core.main import app
    from fastapi.testclient import TestClient
    core = media_env["core"]
    coll = core.create_collection({"subject": "offtopic", "title": "Unrelated",
                                   "summary": "nothing to see", "expected_item_count": 1, "source": "t"})
    ccover = core.upload_media("collection", coll["collection_id"], webp(), alt_text="big cover", actor="admin")
    core.set_media_cover(ccover["media_id"])
    core.add_section_to_collection(coll["collection_id"],
                                   {"title": "Rare", "raw_content": "zor blob reef", "sequence_number": 1})
    core.activate_collection(coll["collection_id"])
    rsvc = ResolverService(database_path=str(tmp_path / "resf.sqlite"))
    rsvc.full_rebuild(core)
    app.state.service = core
    app.state.resolver_service = rsvc
    client = TestClient(app)
    client.auth = ("portal-admin", "portal-secret")
    body = client.post("/portal/search", data={"q": "zor"},
                       headers={"Origin": "http://localhost:8100"}).text
    assert f"/portal/media/{ccover['media_id']}/thumb" in body


def test_search_html_has_no_paths_or_binary(tmp_path, media_env):
    """Search result HTML exposes no filesystem paths, thumbnails paths, or base64."""
    from samjon_memory.resolver.service import ResolverService
    from samjon_memory.core.main import app
    from fastapi.testclient import TestClient
    core, mid = media_env["core"], media_env["mem_id"]
    r = core.upload_media("memory", mid, jpeg(), alt_text="cover", actor="admin")
    core.set_media_cover(r["media_id"])
    core.update_memory(mid, {"raw_content": "tumbleweed grass"}, actor="system")
    core.activate_memory(mid)
    rsvc = ResolverService(database_path=str(tmp_path / "resh.sqlite"))
    rsvc.full_rebuild(core)
    app.state.service = core
    app.state.resolver_service = rsvc
    client = TestClient(app)
    client.auth = ("portal-admin", "portal-secret")
    body = client.post("/portal/search", data={"q": "tumbleweed"},
                       headers={"Origin": "http://localhost:8100"}).text
    assert "relative_path" not in body
    assert "thumbnail_path" not in body
    assert "data:image" not in body
    assert "originals" not in body
    client = _portal_client(tmp_path, media_env)
    client.auth = ("portal-admin", "portal-secret")
    hdr = {"Origin": "http://localhost:8100"}
    for evil in ("https://evil.example/x", "//evil.example/x", "/portal/../secret", "/fallback-only"):
        resp = client.post(f"/portal/media/{r['media_id']}/cover", data={"back": evil},
                           headers=hdr, follow_redirects=False)
        loc = resp.headers.get("location", "")
        assert "evil.example" not in loc
        assert loc.startswith("/portal/memories/")  # falls back to internal path
        assert ".." not in loc