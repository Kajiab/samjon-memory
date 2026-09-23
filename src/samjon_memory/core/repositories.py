"""Data access layer for Samjon Memory Core."""

import sqlite3
from typing import Any, Optional

from samjon_memory.shared.helpers import utc_now


class CollectionRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, data: dict) -> dict:
        cid = data["collection_id"]
        self.conn.execute(
            """INSERT INTO memory_collection
            (collection_id, subject, collection_type, scope, title, summary,
             language, source, source_reference, status, version,
             supersedes_collection_id, expected_item_count, content_checksum,
             created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cid, data["subject"], data.get("collection_type", "fact"),
             data.get("scope", "household"), data["title"], data.get("summary"),
             data.get("language", "en"), data["source"], data.get("source_reference"),
             data.get("status", "draft"), 1, data.get("supersedes_collection_id"),
             data.get("expected_item_count"), data.get("content_checksum"),
             utc_now(), utc_now()),
        )
        self.conn.commit()
        return self.get(cid)

    def get(self, collection_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM memory_collection WHERE collection_id=?", (collection_id,)
        ).fetchone()
        return dict(row) if row else None

    def update(self, collection_id: str, data: dict, expected_version: Optional[int]) -> dict:
        existing = self.get(collection_id)
        if not existing:
            raise ValueError("Collection not found")
        if expected_version is not None and existing["version"] != expected_version:
            raise ValueError("VERSION_CONFLICT")
        fields = []
        params = []
        for k in ["subject", "collection_type", "scope", "title", "summary",
                   "source", "source_reference", "expected_item_count"]:
            if k in data and data[k] is not None:
                fields.append(f"{k}=?")
                params.append(data[k])
        if not fields:
            return existing
        fields.append("version=version+1")
        fields.append("updated_at=?")
        params.append(utc_now())
        params.append(collection_id)
        self.conn.execute(
            f"UPDATE memory_collection SET {', '.join(fields)} WHERE collection_id=?",
            params,
        )
        self.conn.commit()
        return self.get(collection_id)

    def list(self, subject=None, status=None, scope=None, source=None, limit=20, offset=0):
        query = "SELECT * FROM memory_collection WHERE 1=1"
        params = []
        if subject:
            query += " AND subject LIKE ?"
            params.append(f"%{subject}%")
        if status:
            query += " AND status=?"
            params.append(status)
        if scope:
            query += " AND scope=?"
            params.append(scope)
        if source:
            query += " AND source=?"
            params.append(source)
        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


class MemoryRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, data: dict, commit: bool = True) -> dict:
        mid = data["memory_id"]
        self.conn.execute(
            """INSERT INTO memory
            (memory_id, collection_id, sequence_number, subject, memory_type,
             scope, title, section_path, raw_content, structured_value_json,
             source, language, status, version, supersedes_memory_id,
             content_checksum, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (mid, data.get("collection_id"), data.get("sequence_number"),
             data["subject"], data.get("memory_type", "fact"),
             data.get("scope", "household"), data.get("title"),
             data.get("section_path"), data["raw_content"],
             data.get("structured_value_json"), data["source"],
             data.get("language", "en"), data.get("status", "draft"),
             1, data.get("supersedes_memory_id"), data.get("content_checksum"),
             utc_now(), utc_now()),
        )
        if commit:
            self.conn.commit()
        return self.get(mid)

    def get(self, memory_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM memory WHERE memory_id=?", (memory_id,)
        ).fetchone()
        return dict(row) if row else None

    def update(self, memory_id: str, data: dict, expected_version=None) -> dict:
        existing = self.get(memory_id)
        if not existing:
            raise ValueError("Memory not found")
        if expected_version is not None and existing["version"] != expected_version:
            raise ValueError("VERSION_CONFLICT")
        fields = []
        params = []
        for k in ["subject", "memory_type", "scope", "title", "section_path",
                   "raw_content", "structured_value_json", "source", "language"]:
            if k in data and data[k] is not None:
                fields.append(f"{k}=?")
                params.append(data[k])
        if not fields:
            return existing
        fields.append("version=version+1")
        fields.append("updated_at=?")
        params.append(utc_now())
        params.append(memory_id)
        self.conn.execute(
            f"UPDATE memory SET {', '.join(fields)} WHERE memory_id=?",
            params,
        )
        self.conn.commit()
        return self.get(memory_id)

    def list(self, subject=None, memory_type=None, scope=None, status=None,
             source=None, collection_id=None, durable_user_tag=None,
             created_after=None, created_before=None,
             updated_after=None, updated_before=None, limit=20, offset=0,
             order_by=None, collection_scope=None):
        query = "SELECT m.* FROM memory m WHERE 1=1"
        params = []
        if subject:
            query += " AND m.subject LIKE ?"
            params.append(f"%{subject}%")
        if memory_type:
            query += " AND m.memory_type=?"
            params.append(memory_type)
        if scope:
            query += " AND m.scope=?"
            params.append(scope)
        if status:
            query += " AND m.status=?"
            params.append(status)
        if source:
            query += " AND m.source=?"
            params.append(source)
        if collection_id:
            query += " AND m.collection_id=?"
            params.append(collection_id)
        if durable_user_tag:
            query += " AND EXISTS(SELECT 1 FROM durable_user_tag t WHERE t.subject=m.subject AND t.tag=? AND t.status='active')"
            params.append(durable_user_tag)
        if created_after:
            query += " AND m.created_at>=?"
            params.append(created_after)
        if created_before:
            query += " AND m.created_at<=?"
            params.append(created_before)
        if updated_after:
            query += " AND m.updated_at>=?"
            params.append(updated_after)
        if updated_before:
            query += " AND m.updated_at<=?"
            params.append(updated_before)
        if collection_scope == "standalone":
            query += " AND (m.collection_id IS NULL OR m.collection_id='')"
        elif collection_scope == "collection":
            query += " AND (m.collection_id IS NOT NULL AND m.collection_id!='')"
        elif collection_scope == "active_knowledge":
            query += (
                " AND m.status='active' AND (m.collection_id IS NULL OR m.collection_id=''"
                " OR m.collection_id IN (SELECT collection_id FROM memory_collection WHERE status='active'))"
            )
        if order_by:
            query += f" ORDER BY {order_by}"
        else:
            query += " ORDER BY m.updated_at DESC"
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
        return dict(row) if row else None