"""MediaManager - orchestrates validation, storage, thumbnails, and metadata.

All media operations run through CoreService (Portal/API never touch the
filesystem or media repositories directly). Binary bytes never enter SQLite,
logs, or audit records.
"""

from samjon_memory.config import config
from samjon_memory.constants import (
    AUDIT_MEDIA_PURGE,
    AUDIT_MEDIA_REMOVE,
    AUDIT_MEDIA_REORDER,
    AUDIT_MEDIA_REPLACE,
    AUDIT_MEDIA_SET_COVER,
    AUDIT_MEDIA_UPDATE,
    AUDIT_MEDIA_UPLOAD,
    MEDIA_ENTITY_TYPES,
    MEDIA_EXTENSIONS,
    MEDIA_LIFECYCLE_ACTIVE,
    MEDIA_LIFECYCLE_HIDDEN,
    MEDIA_LIFECYCLE_PURGED,
)
from samjon_memory.errors import NotFound, ValidationError
from samjon_memory.media.images import build_thumbnail, inspect_image, sha256_bytes
from samjon_memory.shared.helpers import generate_id


class MediaManager:
    def __init__(self, core):
        self.core = core
        self.repo = core.media
        self.store = core.media_store
        self.cfg = config

    # -- helpers -------------------------------------------------------------

    def _validate_entity(self, entity_type, entity_id):
        if entity_type not in MEDIA_ENTITY_TYPES:
            raise ValidationError("entity_type must be 'memory' or 'collection'")
        if not entity_id:
            raise ValidationError("entity_id is required")
        if entity_type == "collection":
            coll = self.core.collections.get(entity_id)
            if not coll:
                raise NotFound("Collection not found")
            if coll.get("purged_at"):
                raise ValidationError("Cannot attach media to a purged collection")
        else:
            mem = self.core.memories.get(entity_id)
            if not mem:
                raise NotFound("Memory not found")
            if mem.get("purged_at"):
                raise ValidationError("Cannot attach media to a purged memory")

    def _validate_text(self, alt_text, caption):
        if alt_text is not None and len(alt_text) > self.cfg.media_max_alt_text:
            raise ValidationError(f"alt_text exceeds {self.cfg.media_max_alt_text} characters")
        if caption is not None and len(caption) > self.cfg.media_max_caption:
            raise ValidationError(f"caption exceeds {self.cfg.media_max_caption} characters")

    def _record_id(self, record):
        return record.get("media_id") if isinstance(record, dict) else record

    # -- upload --------------------------------------------------------------

    def upload(self, entity_type, entity_id, data, alt_text=None, caption=None,
               actor="system"):
        self._validate_entity(entity_type, entity_id)
        self._validate_text(alt_text, caption)
        if not data:
            raise ValidationError("Empty upload")
        if len(data) > self.cfg.media_max_upload_bytes:
            raise ValidationError("Upload exceeds maximum size")
        mime, width, height = inspect_image(data)
        if width > self.cfg.media_max_width or height > self.cfg.media_max_height:
            raise ValidationError("Image exceeds maximum dimensions")
        if self.repo.count_active(entity_type, entity_id) >= self.cfg.media_max_per_entity:
            raise ValidationError("Maximum images per entity reached")

        media_id = generate_id("med-")
        ext = MEDIA_EXTENSIONS[mime]
        orig_rel = self.store.build_original_relative(media_id, ext)
        thumb_rel = self.store.build_thumbnail_relative(media_id, ext)
        thumb_bytes = build_thumbnail(data, mime, self.cfg.media_thumb_width,
                                      self.cfg.media_thumb_height)
        checksum = sha256_bytes(data)
        display_order = self.repo.count_active(entity_type, entity_id)

        # Persist files first; thumbnail must succeed before any DB commit.
        try:
            self.store.write_original(orig_rel, data)
            try:
                self.store.write_thumbnail(thumb_rel, thumb_bytes)
            except Exception:
                self.store.remove_original(orig_rel)
                raise
            record = self.repo.create({
                "media_id": media_id, "entity_type": entity_type,
                "entity_id": entity_id, "relative_path": orig_rel,
                "thumbnail_path": thumb_rel, "mime_type": mime,
                "file_size": len(data), "width": width, "height": height,
                "alt_text": alt_text, "caption": caption,
                "display_order": display_order, "is_cover": False,
                "checksum": checksum,
                "lifecycle_status": MEDIA_LIFECYCLE_ACTIVE,
            })
        except ValidationError:
            self.store.remove_original(orig_rel)
            self.store.remove_thumbnail(thumb_rel)
            raise
        self.core._audit("media", media_id, AUDIT_MEDIA_UPLOAD, actor, "", 1)
        return record

    def list_media(self, entity_type, entity_id, include_hidden=False):
        self._validate_entity(entity_type, entity_id)
        return self.repo.list_active_by_entity(entity_type, entity_id)

    def get_media(self, media_id):
        record = self.repo.get(media_id)
        if not record:
            raise NotFound("Media not found")
        return record

    def get_cover(self, entity_type, entity_id):
        return self.repo.get_cover(entity_type, entity_id)

    def set_cover(self, media_id, actor="system"):
        record = self.repo.get(media_id)
        if not record:
            raise NotFound("Media not found")
        if record["lifecycle_status"] != MEDIA_LIFECYCLE_ACTIVE:
            raise ValidationError("Cannot set a hidden or purged image as cover")
        updated = self.repo.set_cover(media_id)
        self.core._audit("media", media_id, AUDIT_MEDIA_SET_COVER, actor, "", 1)
        return updated

    def update_metadata(self, media_id, alt_text=None, caption=None, actor="system"):
        record = self.repo.get(media_id)
        if not record:
            raise NotFound("Media not found")
        self._validate_text(alt_text, caption)
        updated = self.repo.update_metadata(media_id, alt_text=alt_text, caption=caption)
        self.core._audit("media", media_id, AUDIT_MEDIA_UPDATE, actor, "", 1)
        return updated

    def reorder(self, entity_type, entity_id, ordered_media_ids, actor="system"):
        active = self.repo.list_active_by_entity(entity_type, entity_id)
        active_ids = [m["media_id"] for m in active]
        if sorted(ordered_media_ids) != sorted(active_ids):
            raise ValidationError("Ordered id list must be a permutation of the entity's media")
        for index, media_id in enumerate(ordered_media_ids):
            self.repo.set_display_order(media_id, index)
        self.core._audit("media", entity_id, AUDIT_MEDIA_REORDER, actor, "", 1)
        return self.list_media(entity_type, entity_id)

    def replace(self, media_id, data, actor="system"):
        record = self.repo.get(media_id)
        if not record:
            raise NotFound("Media not found")
        if not data:
            raise ValidationError("Empty upload")
        if len(data) > self.cfg.media_max_upload_bytes:
            raise ValidationError("Upload exceeds maximum size")
        mime, width, height = inspect_image(data)
        if width > self.cfg.media_max_width or height > self.cfg.media_max_height:
            raise ValidationError("Image exceeds maximum dimensions")
        thumb_bytes = build_thumbnail(data, mime, self.cfg.media_thumb_width,
                                      self.cfg.media_thumb_height)
        new_checksum = sha256_bytes(data)
        orig_rel = self.store.build_original_relative(media_id, MEDIA_EXTENSIONS[mime])
        thumb_rel = self.store.build_thumbnail_relative(media_id, MEDIA_EXTENSIONS[mime])
        wrote = []
        try:
            self.store.write_original(orig_rel, data)
            wrote.append(orig_rel)
            self.store.write_thumbnail(thumb_rel, thumb_bytes)
            wrote.append(thumb_rel)
        except Exception:
            for rel in wrote:
                try:
                    self.store.remove_original(rel)
                except Exception:
                    pass
            raise
        updated = self.repo.refresh_files(
            media_id, new_checksum, len(data), orig_rel, thumb_rel, mime,
            width, height)
        self.core._audit("media", media_id, AUDIT_MEDIA_REPLACE, actor, "", 1)
        return updated

    def remove(self, media_id, actor="system"):
        record = self.repo.get(media_id)
        if not record:
            raise NotFound("Media not found")
        self.repo.delete(media_id)
        if record["lifecycle_status"] != MEDIA_LIFECYCLE_PURGED:
            if record.get("relative_path"):
                self.store.remove_original(record["relative_path"])
            if record.get("thumbnail_path"):
                self.store.remove_thumbnail(record["thumbnail_path"])
        self.core._audit("media", media_id, AUDIT_MEDIA_REMOVE, actor, "", 1)
        return {"removed": True, "media_id": media_id}

    def read_original(self, media_id):
        record = self.get_media(media_id)
        data = self.store.read_original(record["relative_path"])
        return data, record

    def read_thumbnail(self, media_id):
        record = self.get_media(media_id)
        data = self.store.read_thumbnail(record["thumbnail_path"])
        return data, record

    # -- lifecycle -----------------------------------------------------------

    def hide_for_entity(self, entity_type, entity_id):
        for m in self.repo.list_active_by_entity(entity_type, entity_id):
            self.repo.set_lifecycle(m["media_id"], MEDIA_LIFECYCLE_HIDDEN)

    def restore_for_entity(self, entity_type, entity_id):
        for m in self.repo.list_by_entity(entity_type, entity_id,
                                          lifecycle=MEDIA_LIFECYCLE_HIDDEN):
            self.repo.set_lifecycle(m["media_id"], MEDIA_LIFECYCLE_ACTIVE)

    def purge_entity(self, entity_type, entity_id, actor="system"):
        for m in self.repo.all_rows():
            if m["entity_type"] == entity_type and m["entity_id"] == entity_id \
                    and m["lifecycle_status"] != MEDIA_LIFECYCLE_PURGED:
                self.repo.update_metadata(m["media_id"], alt_text="", caption="")
                if m.get("relative_path"):
                    self.store.remove_original(m["relative_path"])
                if m.get("thumbnail_path"):
                    self.store.remove_thumbnail(m["thumbnail_path"])
                self.repo.set_lifecycle(m["media_id"], MEDIA_LIFECYCLE_PURGED)
                self.core._audit("media", m["media_id"], AUDIT_MEDIA_PURGE, actor, "", 1)

    def media_text(self, entity_type, entity_id):
        parts = []
        for m in self.repo.list_active_by_entity(entity_type, entity_id):
            if m.get("alt_text"):
                parts.append(m["alt_text"])
            if m.get("caption"):
                parts.append(m["caption"])
        return " ".join(parts)

    def integrity_check(self):
        issues = []
        rows = self.repo.all_rows()
        on_disk = set(self.store.list_original_files())
        thumb_disk = set(self.store.list_thumbnail_files())
        known = set()
        for m in rows:
            known.add(m["media_id"])
            rel = m.get("relative_path")
            if not rel or rel.count("/") != 1 or rel.startswith(("/", "\\")) \
                    or ".." in rel:
                issues.append(f"invalid_path:{m['media_id']}")
                continue
            try:
                self.store.original_abspath(rel)
            except ValidationError:
                issues.append(f"invalid_path:{m['media_id']}")
                continue
            try:
                data = self.store.read_original(rel)
                if sha256_bytes(data) != m["checksum"]:
                    issues.append(f"checksum_mismatch:{m['media_id']}")
                if len(data) != m["file_size"]:
                    issues.append(f"size_mismatch:{m['media_id']}")
                try:
                    detected, _w, _h = inspect_image(data)
                    if detected != m["mime_type"]:
                        issues.append(f"mime_mismatch:{m['media_id']}")
                except ValidationError:
                    issues.append(f"invalid_content:{m['media_id']}")
            except NotFound:
                issues.append(f"missing_file:{m['media_id']}")
            if m.get("thumbnail_path"):
                try:
                    self.store.read_thumbnail(m["thumbnail_path"])
                except NotFound:
                    issues.append(f"missing_thumbnail:{m['media_id']}")
                except ValidationError:
                    issues.append(f"invalid_thumbnail_path:{m['media_id']}")
        for f in on_disk:
            if f.rsplit(".", 1)[0] not in known:
                issues.append(f"orphaned_file:{f}")
        for f in thumb_disk:
            if f.rsplit(".", 1)[0] not in known:
                issues.append(f"orphaned_thumbnail:{f}")
        return {"healthy": len(issues) == 0, "issues": issues, "count": len(rows)}
        return record