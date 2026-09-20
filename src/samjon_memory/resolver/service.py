"""Application service for Samjon Memory Resolver V1 foundation."""

import sqlite3
from typing import Optional

from samjon_memory.resolver.constants import RESOLVER_SCHEMA_VERSION
from samjon_memory.resolver.config import load_config
from samjon_memory.resolver.database import fts5_available, get_connection
from samjon_memory.resolver.migration import ensure_schema, get_schema_version


class ResolverService:
    """Foundation service: Resolver database lifecycle and readiness.

    Projection, rebuild, search, ranking, and freshness are intentionally not
    implemented in Foundation A.
    """

    def __init__(self, database_path: Optional[str] = None):
        self.database_path = database_path or load_config().database_path
        from samjon_memory.resolver.rebuild import recover_interrupted_swap
        recover_interrupted_swap(self.database_path)
        self.conn = get_connection(self.database_path)
        ensure_schema(self.conn)

    def _db_ok(self) -> bool:
        try:
            self.conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def _schema_ok(self) -> bool:
        try:
            return get_schema_version(self.conn) == RESOLVER_SCHEMA_VERSION
        except sqlite3.Error:
            return False

    def _projection_built(self) -> bool:
        try:
            row = self.conn.execute(
                "SELECT last_full_build_id FROM resolver_state WHERE state_id=1"
            ).fetchone()
            if row is None:
                return False
            return bool(row["last_full_build_id"])
        except sqlite3.Error:
            return False

    def readiness(self) -> dict:
        """Resolver readiness, independent of Core readiness."""
        db_ok = self._db_ok()
        fts5 = fts5_available(self.conn)
        schema_ok = self._schema_ok()
        status = "ok" if (db_ok and fts5 and schema_ok) else "degraded"
        return {
            "resolver": {
                "status": status,
                "database_available": db_ok,
                "schema_version": RESOLVER_SCHEMA_VERSION,
                "schema_ok": schema_ok,
                "fts5_available": fts5,
                "projection_built": self._projection_built(),
                "projection_freshness": self._projection_freshness(),
                "counts": self._counts(),
                "snapshot_checksum": self._snapshot_checksum(),
            }
        }

    def state(self) -> dict:
        """Return the single resolver_state row (foundation)."""
        row = self.conn.execute(
            "SELECT * FROM resolver_state WHERE state_id=1"
        ).fetchone()
        return dict(row) if row else {}

    def _projection_freshness(self):
        return "fresh" if self._projection_built() else None

    def _counts(self) -> dict:
        state = {}
        try:
            state = self.state()
        except sqlite3.Error:
            state = {}
        return {
            "collections": state.get("count_collections"),
            "memories": state.get("count_memories"),
            "sections": state.get("count_sections"),
        }

    def _snapshot_checksum(self):
        try:
            return self.state().get("snapshot_checksum")
        except sqlite3.Error:
            return None

    def full_rebuild(self, core_service):
        """Run an atomic full projection rebuild (Admin action)."""
        from samjon_memory.resolver import rebuild as _rebuild

        self._close_conn()
        try:
            return _rebuild.full_rebuild(core_service, self.database_path)
        finally:
            self.conn = get_connection(self.database_path)
            ensure_schema(self.conn)

    def _close_conn(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def rebuild_status(self) -> dict:
        from samjon_memory.resolver import rebuild as _rebuild

        state = {}
        try:
            state = self.state()
        except sqlite3.Error:
            state = {}
        rows = self.projection_audit(limit=5)
        last_status = rows[0]["status"] if rows else None
        return {
            "in_progress": _rebuild.rebuild_in_progress(),
            "last_build_id": state.get("last_full_build_id"),
            "last_build_status": last_status,
            "projected_at": state.get("projected_at"),
            "snapshot_checksum": state.get("snapshot_checksum"),
            "counts": self._counts(),
        }

    def projection_status(self, limit: int = 200) -> dict:
        state = {}
        try:
            state = self.state()
        except sqlite3.Error:
            state = {}
        rows = self.conn.execute(
            "SELECT entity_type, entity_id, core_version, core_checksum, "
            "projected_at FROM projection_status ORDER BY entity_type, entity_id "
            "LIMIT ?",
            (limit,),
        ).fetchall()
        return {
            "last_full_build_id": state.get("last_full_build_id"),
            "projected_at": state.get("projected_at"),
            "snapshot_checksum": state.get("snapshot_checksum"),
            "resolver_schema_version": state.get("resolver_schema_version"),
            "count": len(rows),
            "entities": [dict(r) for r in rows],
        }

    def search(self, core_service, query, target="auto", collection_id=None,
               scope=None, limit=10, offset=0, allow_stale=False, epsilon=None):
        """Deterministic search over the Resolver projection (Foundation C1)."""
        from samjon_memory.resolver.constants import AMBIGUOUS_EPSILON
        from samjon_memory.resolver import search as _search

        return _search.search(
            self.conn,
            core_service,
            query,
            target=target,
            collection_id=collection_id,
            scope=scope,
            limit=limit,
            offset=offset,
            allow_stale=allow_stale,
            epsilon=AMBIGUOUS_EPSILON if epsilon is None else epsilon,
        )

    def projection_audit(self, limit: int = 20) -> list:
        """Return recent projection_audit rows (foundation, read-only)."""
        rows = self.conn.execute(
            "SELECT * FROM projection_audit ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
