"""Business logic layer for Samjon Memory Core."""

from samjon_memory.core.database import get_connection
from samjon_memory.core.migration import ensure_schema
from samjon_memory.core.repositories import CollectionRepo, MemoryRepo
from samjon_memory.shared.helpers import generate_id, utc_now
from samjon_memory.shared.checksum import content_checksum
from samjon_memory.errors import NotFound, VersionConflict, ValidationError
from samjon_memory.constants import CORE_SCHEMA_VERSION


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
        self.conn.execute("UPDATE memory SET status='superseded', version=version+1, updated_at=? WHERE memory_id=?", (utc_now(), memory_id))
        self.conn.execute("UPDATE memory SET supersedes_memory_id=? WHERE memory_id=?", (memory_id, replacement_id))
        self.conn.commit()
        self._audit("memory", memory_id, "memory_supersede", actor, existing.get("source", ""), existing["version"] + 1)
        return self.memories.get(memory_id)

    def forget_memory(self, memory_id, actor="system"):
        existing = self.memories.get(memory_id)
        if not existing:
            raise NotFound(f"Memory not found: {memory_id}")
        self.conn.execute("UPDATE memory SET status='forgotten', version=version+1, updated_at=? WHERE memory_id=?", (utc_now(), memory_id))
        self.conn.commit()
        self._audit("memory", memory_id, "memory_forget", actor, existing.get("source", ""), existing["version"] + 1)
        return {"forgotten": True, "memory_id": memory_id}

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
        mem = self.memories.get(memory_id)
        if not mem:
            raise NotFound(f"Memory not found: {memory_id}")
        self.conn.execute("UPDATE memory SET collection_id=?, sequence_number=? WHERE memory_id=?", (collection_id, sequence_number, memory_id))
        self.conn.commit()
        self._audit("collection", collection_id, "collection_structure_change", actor, coll.get("source", ""), coll["version"])
        return {"added": True}

    def reorder_collection(self, collection_id, ordered_memory_ids, actor="system"):
        coll = self.collections.get(collection_id)
        if not coll:
            raise NotFound(f"Collection not found: {collection_id}")
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

    def get_audit_records(self, entity_id=None, entity_type=None, action=None, limit=50, offset=0):
        """Retrieve audit records with optional filters."""
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
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return [dict(r) for r in self.conn.execute(query, params).fetchall()]

    def _audit(self, entity_type, entity_id, action, actor, source, version):
        from samjon_memory.shared.helpers import sanitize_for_audit
        audit_id = generate_id("aud-")
        details = sanitize_for_audit(f"{entity_type}:{entity_id}:{action}")
        self.conn.execute(
            "INSERT INTO audit_log (audit_id, entity_type, entity_id, action, actor, source, version, details_json, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (audit_id, entity_type, entity_id, action, actor, source, version, details, utc_now()),
        )
        self.conn.commit()