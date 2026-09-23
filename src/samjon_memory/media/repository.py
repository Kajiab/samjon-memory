"""Media metadata repository (SQLite metadata only - no binaries)."""
from samjon_memory.constants import MEDIA_LIFECYCLE_ACTIVE
from samjon_memory.shared.helpers import utc_now


class MediaRepo:
    def __init__(self, conn):
        self.conn = conn

    def create(self, data: dict) -> dict:
        self.conn.execute(
            """INSERT INTO media (media_id, entity_type, entity_id, relative_path,
               thumbnail_path, mime_type, file_size, width, height, alt_text,
               caption, display_order, is_cover, checksum, lifecycle_status,
               created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["media_id"], data["entity_type"], data["entity_id"],
             data["relative_path"], data.get("thumbnail_path"),
             data["mime_type"], data["file_size"], data["width"], data["height"],
             data.get("alt_text"), data.get("caption"),
             data.get("display_order", 0), 1 if data.get("is_cover") else 0,
             data["checksum"], data.get("lifecycle_status", MEDIA_LIFECYCLE_ACTIVE),
             utc_now(), utc_now()),
        )
        self.conn.commit()
        return self.get(data["media_id"])

    def get(self, media_id: str):
        row = self.conn.execute(
            "SELECT * FROM media WHERE media_id=?", (media_id,)).fetchone()
        return dict(row) if row else None

    def list_by_entity(self, entity_type, entity_id, lifecycle=None):
        query = ("SELECT * FROM media WHERE entity_type=? AND entity_id=? AND "
                 "lifecycle_status != 'purged'")
        params = [entity_type, entity_id]
        if lifecycle:
            query += " AND lifecycle_status=?"
            params.append(lifecycle)
        query += " ORDER BY display_order ASC, created_at ASC"
        return [dict(r) for r in self.conn.execute(query, params).fetchall()]

    def list_active_by_entity(self, entity_type, entity_id):
        return self.list_by_entity(entity_type, entity_id,
                                   lifecycle=MEDIA_LIFECYCLE_ACTIVE)

    def count_active(self, entity_type, entity_id) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM media WHERE entity_type=? AND entity_id=? "
            "AND lifecycle_status='active'", (entity_type, entity_id)).fetchone()
        return row["n"]

    def get_cover(self, entity_type, entity_id):
        row = self.conn.execute(
            "SELECT * FROM media WHERE entity_type=? AND entity_id=? "
            "AND is_cover=1 AND lifecycle_status='active' LIMIT 1",
            (entity_type, entity_id)).fetchone()
        return dict(row) if row else None

    def _clear_cover(self, entity_type, entity_id, exclude_id=None):
        if exclude_id:
            self.conn.execute(
                "UPDATE media SET is_cover=0, updated_at=? WHERE entity_type=? "
                "AND entity_id=? AND media_id != ?",
                (utc_now(), entity_type, entity_id, exclude_id))
        else:
            self.conn.execute(
                "UPDATE media SET is_cover=0, updated_at=? WHERE entity_type=? "
                "AND entity_id=?", (utc_now(), entity_type, entity_id))

    def set_cover(self, media_id: str):
        media = self.get(media_id)
        if not media:
            return None
        self._clear_cover(media["entity_type"], media["entity_id"],
                          exclude_id=media_id)
        self.conn.execute(
            "UPDATE media SET is_cover=1, updated_at=? WHERE media_id=?",
            (utc_now(), media_id))
        self.conn.commit()
    def update_metadata(self, media_id, alt_text=None, caption=None) -> dict:
        fields = []
        params = []
        if alt_text is not None:
            fields.append("alt_text=?")
            params.append(alt_text or None)
        if caption is not None:
            fields.append("caption=?")
            params.append(caption or None)
        if not fields:
            return self.get(media_id)
        fields.append("updated_at=?")
        params.append(utc_now())
        params.append(media_id)
        self.conn.execute(f"UPDATE media SET {', '.join(fields)} WHERE media_id=?",
                          params)
        self.conn.commit()
        return self.get(media_id)

    def set_display_order(self, media_id, display_order) -> dict:
        self.conn.execute(
            "UPDATE media SET display_order=?, updated_at=? WHERE media_id=?",
            (display_order, utc_now(), media_id))
        self.conn.commit()
        return self.get(media_id)

    def refresh_files(self, media_id, checksum, file_size, relative_path,
                      thumbnail_path, mime_type, width, height) -> dict:
        self.conn.execute(
            "UPDATE media SET checksum=?, file_size=?, relative_path=?, "
            "thumbnail_path=?, mime_type=?, width=?, height=?, updated_at=? "
            "WHERE media_id=?",
            (checksum, file_size, relative_path, thumbnail_path, mime_type,
             width, height, utc_now(), media_id))
        self.conn.commit()
        return self.get(media_id)

    def set_lifecycle(self, media_id, lifecycle) -> dict:
        self.conn.execute(
            "UPDATE media SET lifecycle_status=?, updated_at=? WHERE media_id=?",
            (lifecycle, utc_now(), media_id))
        if lifecycle != "active":
            self.conn.execute(
                "UPDATE media SET is_cover=0, updated_at=? WHERE media_id=?",
                (utc_now(), media_id))
        self.conn.commit()
        return self.get(media_id)

    def delete(self, media_id) -> None:
        self.conn.execute("DELETE FROM media WHERE media_id=?", (media_id,))
        self.conn.commit()

    def all_rows(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM media ORDER BY entity_type, entity_id, display_order").fetchall()]
        return self.get(media_id)