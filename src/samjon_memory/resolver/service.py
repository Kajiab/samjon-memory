"""Application service for Samjon Memory Resolver V1 foundation."""

import sqlite3
from typing import Optional

from samjon_memory.resolver.constants import RESOLVER_SCHEMA_VERSION
from samjon_memory.resolver.database import fts5_available, get_connection
from samjon_memory.resolver.migration import ensure_schema, get_schema_version


class ResolverService:
    """Foundation service: Resolver database lifecycle and readiness.

    Projection, rebuild, search, ranking, and freshness are intentionally not
    implemented in Foundation A.
    """

    def __init__(self, database_path: Optional[str] = None):
        self.conn = get_connection(database_path)
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
                "projection_freshness": None,
            }
        }

    def state(self) -> dict:
        """Return the single resolver_state row (foundation)."""
        row = self.conn.execute(
            "SELECT * FROM resolver_state WHERE state_id=1"
        ).fetchone()
        return dict(row) if row else {}

    def projection_audit(self, limit: int = 20) -> list:
        """Return recent projection_audit rows (foundation, read-only)."""
        rows = self.conn.execute(
            "SELECT * FROM projection_audit ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
