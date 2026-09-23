"""Media backup, restore, and integrity for Samjon Memory Media Foundation.

A media backup copies the original + thumbnail files and a manifest of metadata
(including checksums) into a backup directory. Only relative paths are stored.
Binary content never touches SQLite, logs, or audit records.
"""

import json
import os

from samjon_memory.errors import ValidationError
from samjon_memory.media.images import inspect_image, sha256_bytes

MANIFEST_NAME = "media_manifest.json"


def _safe_relative(relative_path):
    if not relative_path or os.path.isabs(relative_path) or ".." in relative_path:
        raise ValidationError("Invalid relative path in backup")
    return relative_path.replace("\\", "/")


def create_backup(manager, backup_root):
    """Copy media originals + thumbnails and write a checksummed manifest."""
    os.makedirs(os.path.join(backup_root, "media", "originals"), exist_ok=True)
    os.makedirs(os.path.join(backup_root, "media", "thumbnails"), exist_ok=True)
    manifest = []
    stored_files = 0
    for row in manager.repo.all_rows():
        if row.get("lifecycle_status") == "purged":
            continue
        entry = {
            "media_id": row["media_id"],
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "relative_path": _safe_relative(row["relative_path"]),
            "thumbnail_path": _safe_relative(row["thumbnail_path"]),
            "mime_type": row["mime_type"],
            "file_size": row["file_size"],
            "width": row["width"],
            "height": row["height"],
            "alt_text": row.get("alt_text"),
            "caption": row.get("caption"),
            "display_order": row.get("display_order"),
            "is_cover": row.get("is_cover"),
            "lifecycle_status": row.get("lifecycle_status"),
            "checksum": row["checksum"],
        }
        src_orig = manager.store.original_abspath(row["relative_path"])
        src_thumb = manager.store.thumbnail_abspath(row["thumbnail_path"])
        if os.path.exists(src_orig):
            _copy(src_orig, os.path.join(backup_root, "media", _safe_relative(row["relative_path"])))
            stored_files += 1
        if os.path.exists(src_thumb):
            _copy(src_thumb, os.path.join(backup_root, "media", _safe_relative(row["thumbnail_path"])))
        manifest.append(entry)
    with open(os.path.join(backup_root, "media", MANIFEST_NAME), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    return {"entries": len(manifest), "files": stored_files}


def _copy(src, dst):
    d = os.path.dirname(dst)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = dst + ".baktmp"
    with open(src, "rb") as fin, open(tmp, "wb") as fout:
        fout.write(fin.read())
        fout.flush()
        os.fsync(fout.fileno())
    os.replace(tmp, dst)


def _load_manifest(backup_root):
    path = os.path.join(backup_root, "media", MANIFEST_NAME)
    if not os.path.exists(path):
        raise ValidationError("Backup manifest missing")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def check_backup(backup_root):
    """Validate a media backup: missing/orphaned files, checksum, content."""
    issues = []
    media_root = os.path.join(backup_root, "media")
    entries = _load_manifest(backup_root)
    known_ids = set()
    for entry in entries:
        known_ids.add(entry["media_id"])
        rel = _safe_relative(entry["relative_path"])
        orig = os.path.join(media_root, rel)
        if not os.path.exists(orig):
            issues.append(f"missing_file:{entry['media_id']}")
            continue
        data = open(orig, "rb").read()
        if sha256_bytes(data) != entry.get("checksum"):
            issues.append(f"checksum_mismatch:{entry['media_id']}")
        if len(data) != entry.get("file_size"):
            issues.append(f"size_mismatch:{entry['media_id']}")
        try:
            detected, _w, _h = inspect_image(data)
            if detected != entry.get("mime_type"):
                issues.append(f"mime_mismatch:{entry['media_id']}")
        except ValidationError:
            issues.append(f"invalid_content:{entry['media_id']}")
        if entry.get("thumbnail_path"):
            thumb = os.path.join(media_root, _safe_relative(entry["thumbnail_path"]))
            if not os.path.exists(thumb):
                issues.append(f"missing_thumbnail:{entry['media_id']}")
    # Orphaned files present in backup but absent from the manifest.
    for sub in ("originals", "thumbnails"):
        d = os.path.join(media_root, sub)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            mid = f.rsplit(".", 1)[0]
            if mid not in known_ids:
                issues.append(f"orphaned_file:{sub}/{f}")
    return {"healthy": len(issues) == 0, "issues": issues, "entries": len(entries)}


def restore_backup(manager, backup_root):
    """Copy originals/thumbnails from a backup into the live store.

    Only restores rows that already exist in Core metadata (no new metadata is
    created) and only when the live file is missing - so restore is idempotent
    and never duplicates files.
    """
    entries = _load_manifest(backup_root)
    media_root = os.path.join(backup_root, "media")
    restored = 0
    for entry in entries:
        existing = manager.repo.get(entry["media_id"])
        if not existing:
            continue
        rel = _safe_relative(entry["relative_path"])
        if not manager.store.file_exists(rel):
            _copy(os.path.join(media_root, rel), manager.store.original_abspath(rel))
            restored += 1
        if entry.get("thumbnail_path"):
            trel = _safe_relative(entry["thumbnail_path"])
            if not manager.store.file_exists(trel):
                _copy(os.path.join(media_root, trel), manager.store.thumbnail_abspath(trel))
    return {"restored": restored}