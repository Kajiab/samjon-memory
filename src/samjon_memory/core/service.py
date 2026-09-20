"""Business logic layer for Samjon Memory Core."""

from samjon_memory.core.database import get_connection
from samjon_memory.core.migration import ensure_schema
from samjon_memory.core.repositories import CollectionRepo, MemoryRepo
from samjon_memory.shared.helpers import generate_id, utc_now
from samjon_memory.shared.checksum import content_checksum
from samjon_memory.config import config
from samjon_memory.errors import PermissionDenied, NotFound, VersionConflict, ValidationError
from samjon_memory.constants import CORE_SCHEMA_VERSION, LIFECYCLE_PURGE_MIN_AGE_DAYS


class CoreService:
    def __init__(self, database_path=None):
        self.conn = get_connection(database_path)
        ensure_schema(self.conn)
        self.collections = CollectionRepo(self.conn)
        self.memories = MemoryRepo(self.conn)

    def health(self):
        try:
            self.conn.execute("SELECT 1")
            return {"status": "ok", "service": "samjon-memory-core", "version": "1.0.0", "core_schema_version": CORE_SCHEMA_VERSION}
        except Exception as e:
            return {"status": "degraded", "error": str(e)}

    def create_memory(self, data, actor="system", idempotency_key=None):
        data = dict(data)
        mid = data.get("memory_id") or generate_id("mem-")
        data["memory_id"] = mid
        data["content_checksum"] = content_checksum(data["raw_content"])
        if idempotency_key:
            existing = self.conn.execute("SELECT * FROM idempotency_record WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if existing:
                if existing["request_hash"] != str(hash(str(data))):
                    from samjon_memory.errors import IdempotencyConflict
                    raise IdempotencyConflict()
                return self.memories.get(existing["resulting_entity_id"])
        resp = self.memories.create(data)
        self._audit("memory", mid, "memory_create", actor, data.get("source", ""), 1)
        if idempotency_key:
            self.conn.execute("INSERT OR REPLACE INTO idempotency_record (idempotency_key, request_hash, operation, resulting_entity_type, resulting_entity_id, created_at) VALUES (?,?,?,?,?,?)", (idempotency_key, str(hash(str(data))), "create_memory", "memory", mid, utc_now()))
            self.conn.commit()
        return resp

    def get_memory(self, memory_id):
        result = self.memories.get(memory_id)
        if not result:
            raise NotFound(f"Memory not found: {memory_id}")
        return result

    def update_memory(self, memory_id, data, actor="system"):
        existing = self.memories.get(memory_id)
        if not existing:
            raise NotFound(f"Memory not found: {memory_id}")
        if existing.get("purged_at"):
            raise ValidationError("Cannot edit a purged memory")
        expected = data.pop("expected_version", None)
        result = self.memories.update(memory_id, data, expected)
        self._audit("memory", memory_id, "memory_update", actor, existing.get("source", ""), result["version"])
        return result

    def query_memories(self, **filters):
        return self.memories.list(**filters)

    def supersede_memory(self, memory_id, replacement_id, actor="system"):
        existing = self.memories.get(memory_id)
        if not existing:
            raise NotFound(f"Memory not found: {memory_id}")
        if existing.get("purged_at"):
            raise ValidationError("Cannot supersede a purged memory")
        self.conn.execute("UPDATE memory SET status='superseded', version=version+1, updated_at=? WHERE memory_id=?", (utc_now(), memory_id))
        self.conn.execute("UPDATE memory SET supersedes_memory_id=? WHERE memory_id=?", (memory_id, replacement_id))
        self.conn.commit()
        self._audit("memory", memory_id, "memory_supersede", actor, existing.get("source", ""), existing["version"] + 1)
        return self.memories.get(memory_id)

    def forget_memory(self, memory_id, actor="system"):
        existing = self.memories.get(memory_id)
        if not existing:
            raise NotFound(f"Memory not found: {memory_id}")
        if existing.get("purged_at"):
            raise ValidationError("Cannot forget a purged memory")
        now = utc_now()
        self.conn.execute("UPDATE memory SET status='forgotten', forgotten_at=?, version=version+1, updated_at=? WHERE memory_id=?", (now, now, memory_id))
        self.conn.commit()
        self._audit("memory", memory_id, "memory_forget", actor, existing.get("source", ""), existing["version"] + 1)
        return {"forgotten": True, "memory_id": memory_id}

    def forget_collection(self, collection_id, actor="system"):
        existing = self.collections.get(collection_id)
        if not existing:
            raise NotFound(f"Collection not found: {collection_id}")
        if existing.get("purged_at"):
            raise ValidationError("Cannot forget a purged collection")
        now = utc_now()
        self.conn.execute("UPDATE memory_collection SET status='forgotten', forgotten_at=?, version=version+1, updated_at=? WHERE collection_id=?", (now, now, collection_id))
        self.conn.commit()
        self._audit("collection", collection_id, "collection_forget", actor, existing.get("source", ""), existing["version"] + 1)
        return {"forgotten": True, "collection_id": collection_id}

    def activate_memory(self, memory_id, expected_version=None, actor="system"):
        """Activate a standalone Memory (draft -> active).

        Idempotent for already-active Memories. Rejects superseded/forgotten
        Memories, and raises VersionConflict when expected_version is stale so
        an outdated client cannot silently overwrite a newer state.
        """
        existing = self.memories.get(memory_id)
        if not existing:
            raise NotFound(f"Memory not found: {memory_id}")
        if existing["status"] == "active":
            return existing
        if existing["status"] in ("superseded", "forgotten"):
            raise ValidationError(
                f"Cannot activate a memory with status '{existing['status']}'"
            )
        if expected_version is not None and existing["version"] != expected_version:
            raise VersionConflict(
                "memory modified by another request; refresh and retry"
            )
        self.conn.execute(
            "UPDATE memory SET status='active', version=version+1, updated_at=? WHERE memory_id=?",
            (utc_now(), memory_id),
        )
        self.conn.commit()
        self._audit("memory", memory_id, "memory_activate", actor,
                    existing.get("source", ""), existing["version"] + 1)
        return self.memories.get(memory_id)

    def create_collection(self, data, actor="system"):
        cid = data.get("collection_id") or generate_id("col-")
        data["collection_id"] = cid
        data["status"] = "draft"
        data["version"] = 1
        resp = self.collections.create(data)
        self._audit("collection", cid, "collection_create", actor, data.get("source", ""), 1)
        return resp

    def get_collection(self, collection_id):
        result = self.collections.get(collection_id)
        if not result:
            raise NotFound(f"Collection not found: {collection_id}")
        return result

    def update_collection(self, collection_id, data, actor="system"):
        existing = self.collections.get(collection_id)
        if not existing:
            raise NotFound(f"Collection not found: {collection_id}")
        if existing.get("purged_at"):
            raise ValidationError("Cannot edit a purged collection")
        sections = self.memories.list(collection_id=collection_id, limit=1000)
        if sections and (
            (data.get("subject") is not None and data.get("subject") != existing.get("subject"))
            or (data.get("scope") is not None and data.get("scope") != existing.get("scope"))
        ):
            raise ValidationError("Cannot change Collection subject/scope while sections exist")
        expected = data.pop("expected_version", None)
        result = self.collections.update(collection_id, data, expected)
        self._audit("collection", collection_id, "collection_update", actor, existing.get("source", ""), result["version"])
        return result

    def list_collections(self, **filters):
        return self.collections.list(**filters)

    def add_memory_to_collection(self, collection_id, memory_id, sequence_number, actor="system"):
        coll = self.collections.get(collection_id)
        if not coll:
            raise NotFound(f"Collection not found: {collection_id}")
        if coll.get("purged_at"):
            raise ValidationError("Cannot modify a purged collection")
        mem = self.memories.get(memory_id)
        if not mem:
            raise NotFound(f"Memory not found: {memory_id}")
        if mem.get("purged_at"):
            raise ValidationError("Cannot reuse a purged memory")
        if mem.get("subject") != coll.get("subject"):
            raise ValidationError("Memory subject must match the Collection subject")
        if mem.get("scope") != coll.get("scope"):
            raise ValidationError("Memory scope must match the Collection scope")
        self.conn.execute("UPDATE memory SET collection_id=?, sequence_number=? WHERE memory_id=?", (collection_id, sequence_number, memory_id))
        self.conn.commit()
        self._audit("collection", collection_id, "collection_structure_change", actor, coll.get("source", ""), coll["version"])
        return {"added": True}

    def add_section_to_collection(self, collection_id, data, actor="system"):
        """Create a new section Memory whose subject/scope come from the Collection.

        The section `title` is the section name only and is never used as a
        fallback subject. Any client-provided subject/scope must equal the
        Collection's values, otherwise the request is rejected.
        """
        coll = self.collections.get(collection_id)
        if not coll:
            raise NotFound(f"Collection not found: {collection_id}")
        if coll.get("purged_at"):
            raise ValidationError("Cannot modify a purged collection")
        client_subject = data.get("subject")
        client_scope = data.get("scope")
        if client_subject is not None and client_subject != coll.get("subject"):
            raise ValidationError("Section subject must match the Collection subject")
        if client_scope is not None and client_scope != coll.get("scope"):
            raise ValidationError("Section scope must match the Collection scope")
        title = (data.get("title") or "").strip()
        if not title:
            raise ValidationError("Section title is required")
        section = {
            "subject": coll.get("subject"),
            "scope": coll.get("scope"),
            "title": title,
            "memory_type": data.get("memory_type") or "fact",
            "raw_content": data.get("raw_content") or "",
            "structured_value_json": data.get("structured_value_json"),
            "source": data.get("source") or coll.get("source") or "portal",
            "language": data.get("language") or coll.get("language") or "en",
            "collection_id": collection_id,
        }
        if data.get("sequence_number") is not None:
            section["sequence_number"] = data["sequence_number"]
        created = self.create_memory(section, actor=actor)
        self._audit("collection", collection_id, "collection_structure_change", actor,
                    section.get("source", ""), coll["version"])
        return created

    def reorder_collection(self, collection_id, ordered_memory_ids, actor="system"):
        coll = self.collections.get(collection_id)
        if not coll:
            raise NotFound(f"Collection not found: {collection_id}")
        if coll.get("purged_at"):
            raise ValidationError("Cannot reorder a purged collection")
        for i, mid in enumerate(ordered_memory_ids):
            self.conn.execute("UPDATE memory SET sequence_number=? WHERE memory_id=? AND collection_id=?", (i + 1, mid, collection_id))
        self.conn.execute("UPDATE memory_collection SET version=version+1, updated_at=? WHERE collection_id=?", (utc_now(), collection_id))
        self.conn.commit()
        self._audit("collection", collection_id, "collection_structure_change", actor, coll.get("source", ""), coll["version"] + 1)
        return {"reordered": True}

    def activate_collection(self, collection_id, actor="system"):
        coll = self.collections.get(collection_id)
        if not coll:
            raise NotFound(f"Collection not found: {collection_id}")
        if coll.get("purged_at"):
            raise ValidationError("Cannot activate a purged collection")
        if coll["status"] == "active":
            return coll
        memories = self.memories.list(collection_id=collection_id, limit=1000)
        if coll.get("expected_item_count") is not None and len(memories) != coll["expected_item_count"]:
            raise ValidationError(f"Expected {coll['expected_item_count']} items, found {len(memories)}")
        seq_nums = [m["sequence_number"] for m in memories if m["sequence_number"] is not None]
        if len(seq_nums) != len(set(seq_nums)):
            raise ValidationError("Duplicate sequence numbers in collection")
        self.conn.execute("UPDATE memory_collection SET status='active', version=version+1, updated_at=? WHERE collection_id=?", (utc_now(), collection_id))
        self.conn.commit()
        self._audit("collection", collection_id, "collection_activate", actor, coll.get("source", ""), coll["version"] + 1)
        return self.collections.get(collection_id)

    def validate_collection(self, collection_id):
        coll = self.collections.get(collection_id)
        if not coll:
            raise NotFound(f"Collection not found: {collection_id}")
        memories = self.memories.list(collection_id=collection_id, limit=1000)
        issues = []
        seq_nums = [m["sequence_number"] for m in memories if m["sequence_number"] is not None]
        if len(seq_nums) != len(set(seq_nums)):
            issues.append("duplicate_sequence_numbers")
        for m in memories:
            if m["status"] == "forgotten":
                issues.append(f"forgotten_memory:{m['memory_id']}")
        if coll.get("expected_item_count") is not None and len(memories) != coll["expected_item_count"]:
            issues.append(f"expected_count_mismatch:{len(memories)}!={coll['expected_item_count']}")
        return {"valid": len(issues) == 0, "issues": issues, "memory_count": len(memories)}

    def get_collection_memories(self, collection_id, limit=20, offset=0):
        return self.memories.list(collection_id=collection_id, limit=limit, offset=offset, order_by="sequence_number ASC")

    def get_audit_records(self, entity_id=None, entity_type=None, action=None, since=None, until=None, limit=50, offset=0):
        """Retrieve audit records with filters and pagination (append-only)."""
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        if entity_id:
            query += " AND entity_id=?"
            params.append(entity_id)
        if entity_type:
            query += " AND entity_type=?"
            params.append(entity_type)
        if action:
            query += " AND action=?"
            params.append(action)
        if since:
            query += " AND created_at>=?"
            params.append(since)
        if until:
            query += " AND created_at<=?"
            params.append(until)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return [dict(r) for r in self.conn.execute(query, params).fetchall()]

    def audit_summary(self, entity_type=None, action=None, since=None, until=None):
        """Audit statistics grouped by action (append-only; no deletion)."""
        query = "SELECT action, COUNT(*) AS count FROM audit_log WHERE 1=1"
        params = []
        if entity_type:
            query += " AND entity_type=?"
            params.append(entity_type)
        if action:
            query += " AND action=?"
            params.append(action)
        if since:
            query += " AND created_at>=?"
            params.append(since)
        if until:
            query += " AND created_at<=?"
            params.append(until)
        query += " GROUP BY action ORDER BY count DESC"
        return [dict(r) for r in self.conn.execute(query, params).fetchall()]

    # ---- Restore / Purge lifecycle ----------------------------------------

    def _ensure_admin(self, actor):
        admins = {"admin"}
        if getattr(config, "portal_username", None):
            admins.add(config.portal_username)
        if not actor or actor not in admins:
            raise PermissionDenied("Purge requires an administrator")

    def _confirm(self, confirmation):
        expected = getattr(config, "purge_confirmation", None) or "PURGE"
        return (confirmation or "") == expected

    def _purge_info(self, forgotten_at):
        from datetime import datetime, timedelta, timezone as _tz
        import math as _math
        empty = {"date": "", "days_remaining": 0, "eligible": False}
        if not forgotten_at:
            return empty
        try:
            value = datetime.fromisoformat(forgotten_at.replace("Z", "+00:00"))
            if value.tzinfo is None:
                value = value.replace(tzinfo=_tz.utc)
        except (ValueError, TypeError):
            return empty
        min_days = getattr(config, "purge_min_age_days", None) or LIFECYCLE_PURGE_MIN_AGE_DAYS
        now = datetime.now(_tz.utc)
        purge_date = value + timedelta(days=min_days)
        remaining = (purge_date - now).total_seconds()
        eligible = remaining <= 0
        days_remaining = max(0, _math.ceil(remaining / 86400.0)) if not eligible else 0
        return {
            "date": purge_date.isoformat(),
            "days_remaining": days_remaining,
            "eligible": eligible,
        }

    def _purge_eligible(self, forgotten_at):
        return self._purge_info(forgotten_at)["eligible"]

    def _insert_tombstone(self, entity_type, entity_id, final_version, checksum, actor):
        self.conn.execute(
            "INSERT INTO lifecycle_tombstone (tombstone_id, entity_type, entity_id, final_version, content_checksum, purged_at, actor) VALUES (?,?,?,?,?,?,?)",
            (generate_id("tmb-"), entity_type, entity_id, final_version, checksum, utc_now(), actor),
        )

    def _bump_collection_version(self, collection_id, actor="system", source=""):
        coll = self.collections.get(collection_id)
        if not coll:
            return
        self.conn.execute(
            "UPDATE memory_collection SET version=version+1, updated_at=? WHERE collection_id=?",
            (utc_now(), collection_id),
        )
        self.conn.commit()
        self._audit("collection", collection_id, "collection_structure_change", actor, source, coll["version"] + 1)

    def restore_memory(self, memory_id, actor="system"):
        existing = self.memories.get(memory_id)
        if not existing:
            raise NotFound(f"Memory not found: {memory_id}")
        if existing.get("purged_at"):
            raise ValidationError("Cannot restore a purged memory")
        if existing["status"] != "forgotten":
            raise ValidationError("Only forgotten memories can be restored")
        self.conn.execute(
            "UPDATE memory SET status='draft', forgotten_at=NULL, version=version+1, updated_at=? WHERE memory_id=?",
            (utc_now(), memory_id),
        )
        self.conn.commit()
        self._audit("memory", memory_id, "memory_restore", actor, existing.get("source", ""), existing["version"] + 1)
        if existing.get("collection_id"):
            self._bump_collection_version(existing["collection_id"], actor, existing.get("source", ""))
        return self.memories.get(memory_id)

    def restore_collection(self, collection_id, actor="system"):
        existing = self.collections.get(collection_id)
        if not existing:
            raise NotFound(f"Collection not found: {collection_id}")
        if existing.get("purged_at"):
            raise ValidationError("Cannot restore a purged collection")
        if existing["status"] != "forgotten":
            raise ValidationError("Only forgotten collections can be restored")
        self.conn.execute(
            "UPDATE memory_collection SET status='draft', forgotten_at=NULL, version=version+1, updated_at=? WHERE collection_id=?",
            (utc_now(), collection_id),
        )
        self.conn.commit()
        self._audit("collection", collection_id, "collection_restore", actor, existing.get("source", ""), existing["version"] + 1)
        return self.collections.get(collection_id)

    def purge_memory(self, memory_id, confirmation="", expected_version=None, actor="system"):
        existing = self.memories.get(memory_id)
        if not existing:
            raise NotFound(f"Memory not found: {memory_id}")
        self._ensure_admin(actor)
        if existing.get("purged_at"):
            raise ValidationError("Memory is already purged")
        if existing["status"] != "forgotten":
            raise ValidationError("Only forgotten memories can be purged")
        if not self._purge_eligible(existing.get("forgotten_at")):
            raise ValidationError(
                f"Memory must be forgotten at least {getattr(config, 'purge_min_age_days', 30)} days before purge"
            )
        if not self._confirm(confirmation):
            raise ValidationError("Type PURGE to confirm")
        if expected_version is not None and existing["version"] != expected_version:
            raise VersionConflict("memory modified by another request; refresh and retry")
        return self._do_purge_memory(existing, actor)

    def _do_purge_memory(self, existing, actor):
        memory_id = existing["memory_id"]
        subject = existing.get("subject") or ""
        source = existing.get("source") or ""
        new_version = existing["version"] + 1
        try:
            self.conn.execute(
                "UPDATE memory SET title=NULL, section_path=NULL, raw_content='', structured_value_json=NULL,"
                " status='forgotten', purged_at=?, purged_by=?, version=version+1, updated_at=? WHERE memory_id=?",
                (utc_now(), actor, utc_now(), memory_id),
            )
            # Erase subject-scoped manual metadata transactionally, tombstone each.
            for table, id_col in (
                ("durable_alias", "alias_id"),
                ("durable_user_tag", "tag_id"),
                ("manual_override", "override_id"),
            ):
                for row in self.conn.execute(
                    f"SELECT {id_col} AS id, version AS version, content_checksum AS checksum FROM {table} WHERE subject=?",
                    (subject,),
                ).fetchall():
                    self._insert_tombstone(table, row["id"], row["version"], row["checksum"], actor)
                    self.conn.execute(f"DELETE FROM {table} WHERE {id_col}=?", (row["id"],))
            self._insert_tombstone("memory", memory_id, new_version, existing.get("content_checksum"), actor)
            if existing.get("collection_id"):
                self.conn.execute(
                    "UPDATE memory_collection SET version=version+1, updated_at=? WHERE collection_id=?",
                    (utc_now(), existing["collection_id"]),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        self._audit("memory", memory_id, "memory_purge", actor, source, new_version)
        return self.memories.get(memory_id)

    def purge_collection(self, collection_id, confirmation="", actor="system"):
        existing = self.collections.get(collection_id)
        if not existing:
            raise NotFound(f"Collection not found: {collection_id}")
        self._ensure_admin(actor)
        if existing.get("purged_at"):
            raise ValidationError("Collection is already purged")
        if existing["status"] != "forgotten":
            raise ValidationError("Only forgotten collections can be purged")
        if not self._purge_eligible(existing.get("forgotten_at")):
            raise ValidationError(
                f"Collection must be forgotten at least {getattr(config, 'purge_min_age_days', 30)} days before purge"
            )
        if not self._confirm(confirmation):
            raise ValidationError("Type PURGE to confirm")
        new_version = existing["version"] + 1
        self.conn.execute(
            "UPDATE memory_collection SET title='', summary=NULL, source_reference=NULL,"
            " status='forgotten', purged_at=?, purged_by=?, version=version+1, updated_at=? WHERE collection_id=?",
            (utc_now(), actor, utc_now(), collection_id),
        )
        self.conn.commit()
        self._insert_tombstone("collection", collection_id, new_version, existing.get("content_checksum"), actor)
        self._audit("collection", collection_id, "collection_purge", actor, existing.get("source", ""), new_version)
        return self.collections.get(collection_id)

    def _collection_valid(self, col, mems):
        """Collection passes the same checks validate_collection uses."""
        seq_nums = [m["sequence_number"] for m in mems if m["sequence_number"] is not None]
        if len(seq_nums) != len(set(seq_nums)):
            return False
        for m in mems:
            if m["status"] == "forgotten":
                return False
        if col.get("expected_item_count") is not None and len(mems) != col["expected_item_count"]:
            return False
        return True

    def _invalid_collection_ids(self):
        invalid = set()
        cols = self.conn.execute(
            "SELECT collection_id, expected_item_count FROM memory_collection"
        ).fetchall()
        for row in cols:
            col = dict(row)
            mems = [dict(r) for r in self.conn.execute(
                "SELECT m.* FROM memory m WHERE m.collection_id=? ORDER BY m.sequence_number",
                (col["collection_id"],),
            ).fetchall()]
            if not self._collection_valid(col, mems):
                invalid.add(col["collection_id"])
        return invalid

    def dashboard_stats(self):
        """Aggregate counts for the Portal Dashboard.

        Counting lives in CoreService so the Portal never touches the database
        or repositories directly. Standalone == collection_id is null/empty.
        """
        def _groups(sql):
            return {r["status"] or "unknown": r["n"] for r in self.conn.execute(sql).fetchall()}

        standalone = _groups(
            "SELECT status, COUNT(*) AS n FROM memory "
            "WHERE (collection_id IS NULL OR collection_id='') GROUP BY status"
        )
        sections = _groups(
            "SELECT status, COUNT(*) AS n FROM memory "
            "WHERE (collection_id IS NOT NULL AND collection_id!='') GROUP BY status"
        )
        colls = _groups(
            "SELECT status, COUNT(*) AS n FROM memory_collection GROUP BY status"
        )

        standalone_total = sum(standalone.values())
        section_total = sum(sections.values())
        coll_total = sum(colls.values())

        active_sections = self.conn.execute(
            "SELECT COUNT(*) AS n FROM memory m "
            "JOIN memory_collection c ON m.collection_id=c.collection_id "
            "WHERE m.status='active' AND c.status='active'"
        ).fetchone()["n"]

        return {
            "standalone_total": standalone_total,
            "standalone_draft": standalone.get("draft", 0),
            "standalone_active": standalone.get("active", 0),
            "standalone_superseded": standalone.get("superseded", 0),
            "standalone_forgotten": standalone.get("forgotten", 0),
            "collections_total": coll_total,
            "collections_draft": colls.get("draft", 0),
            "collections_active": colls.get("active", 0),
            "collection_sections_total": section_total,
            "invalid_collections": len(self._invalid_collection_ids()),
            "total_facts": standalone_total + section_total,
            "active_knowledge": standalone.get("active", 0) + active_sections,
        }

    def list_collections(self, status=None, invalid=None, limit=50, offset=0):
        """List collections, optionally filtered to invalid ones only."""
        rows = self.collections.list(status=status or None, limit=limit, offset=offset)
        if invalid:
            bad = self._invalid_collection_ids()
            rows = [c for c in rows if c["collection_id"] in bad]
        return rows

    def _db_ok(self):
        try:
            self.conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def admin_stats(self):
        """Aggregate data for the Portal Administration page (read-only)."""

        def _forgotten(table, entity_type, id_col):
            rows = []
            for r in self.conn.execute(
                f"SELECT * FROM {table} WHERE status='forgotten' AND purged_at IS NULL ORDER BY forgotten_at"
            ).fetchall():
                row = dict(r)
                info = self._purge_info(row.get("forgotten_at"))
                rows.append({
                    "entity_type": entity_type,
                    "entity_id": row[id_col],
                    "title": row.get("title") or row.get("subject") or "",
                    "subject": row.get("subject") or "",
                    "version": row.get("version"),
                    "forgotten_at": row.get("forgotten_at"),
                    "purge_eligible_date": info["date"],
                    "days_remaining": info["days_remaining"],
                    "purge_eligible": info["eligible"],
                })
            return rows

        def _purged(table, entity_type, id_col):
            rows = []
            for r in self.conn.execute(
                f"SELECT {id_col} AS entity_id, subject, title, status, version, content_checksum, purged_at, purged_by FROM {table} WHERE purged_at IS NOT NULL ORDER BY purged_at DESC"
            ).fetchall():
                row = dict(r)
                row["entity_type"] = entity_type
                rows.append(row)
            return rows

        return {
            "schema_version": CORE_SCHEMA_VERSION,
            "database_status": "ok" if self._db_ok() else "degraded",
            "forgotten_memories": _forgotten("memory", "memory", "memory_id"),
            "forgotten_collections": _forgotten("memory_collection", "collection", "collection_id"),
            "purged_memories": _purged("memory", "memory", "memory_id"),
            "purged_collections": _purged("memory_collection", "collection", "collection_id"),
            "tombstone_count": self.conn.execute(
                "SELECT COUNT(*) AS n FROM lifecycle_tombstone"
            ).fetchone()["n"],
            "audit_count": self.conn.execute(
                "SELECT COUNT(*) AS n FROM audit_log"
            ).fetchone()["n"],
            "audit_stats": self.audit_summary(),
        }

    def _audit(self, entity_type, entity_id, action, actor, source, version):
        from samjon_memory.shared.helpers import sanitize_for_audit
        audit_id = generate_id("aud-")
        details = sanitize_for_audit(f"{entity_type}:{entity_id}:{action}")
        self.conn.execute(
            "INSERT INTO audit_log (audit_id, entity_type, entity_id, action, actor, source, version, details_json, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (audit_id, entity_type, entity_id, action, actor, source, version, details, utc_now()),
        )
        self.conn.commit()