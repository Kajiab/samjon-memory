"""Versioned migrations for Samjon Memory Core."""

from samjon_memory.core.database import execute_script, get_schema_version, table_exists
from samjon_memory.constants import CORE_SCHEMA_VERSION
from samjon_memory.errors import MigrationRequired

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY, value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS memory_collection (
    collection_id TEXT PRIMARY KEY, subject TEXT NOT NULL,
    collection_type TEXT NOT NULL DEFAULT 'fact',
    scope TEXT NOT NULL DEFAULT 'household',
    title TEXT NOT NULL CHECK(length(title) <= 500),
    summary TEXT CHECK(length(summary) <= 8192),
    language TEXT NOT NULL DEFAULT 'en', source TEXT NOT NULL,
    source_reference TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','active','superseded','forgotten')),
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_collection_id TEXT REFERENCES memory_collection(collection_id),
    expected_item_count INTEGER, content_checksum TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS memory (
    memory_id TEXT PRIMARY KEY, collection_id TEXT REFERENCES memory_collection(collection_id),
    sequence_number INTEGER, subject TEXT NOT NULL,
    memory_type TEXT NOT NULL DEFAULT 'fact', scope TEXT NOT NULL DEFAULT 'household',
    title TEXT CHECK(length(title) <= 500), section_path TEXT,
    raw_content TEXT NOT NULL CHECK(length(raw_content) <= 16384),
    structured_value_json TEXT, source TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','active','superseded','forgotten')),
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_memory_id TEXT REFERENCES memory(memory_id),
    content_checksum TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_DURABLE_SQL = """
CREATE TABLE IF NOT EXISTS durable_alias (
    alias_id TEXT PRIMARY KEY, subject TEXT NOT NULL, alias TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en', source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','superseded','forgotten')),
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_alias_id TEXT REFERENCES durable_alias(alias_id),
    content_checksum TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS durable_vocabulary (
    vocabulary_id TEXT PRIMARY KEY, term TEXT NOT NULL, definition TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en', source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','superseded','forgotten')),
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_vocabulary_id TEXT REFERENCES durable_vocabulary(vocabulary_id),
    content_checksum TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS durable_user_tag (
    tag_id TEXT PRIMARY KEY, subject TEXT NOT NULL, tag TEXT NOT NULL CHECK(length(tag) <= 80),
    language TEXT NOT NULL DEFAULT 'en', source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','superseded','forgotten')),
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_tag_id TEXT REFERENCES durable_user_tag(tag_id),
    content_checksum TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS manual_override (
    override_id TEXT PRIMARY KEY, subject TEXT NOT NULL, scope TEXT NOT NULL DEFAULT 'household',
    key TEXT NOT NULL, value_json TEXT NOT NULL, source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','superseded','forgotten')),
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_override_id TEXT REFERENCES manual_override(override_id),
    content_checksum TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_IDEMPOTENCY_SQL = """
CREATE TABLE IF NOT EXISTS idempotency_record (
    idempotency_key TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
    operation TEXT NOT NULL, resulting_entity_type TEXT NOT NULL,
    resulting_entity_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT
);
"""

_AUDIT_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
    action TEXT NOT NULL, actor TEXT NOT NULL, source TEXT NOT NULL,
    version INTEGER, details_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_mc_subject ON memory_collection(subject);
CREATE INDEX IF NOT EXISTS idx_mc_status ON memory_collection(status);
CREATE INDEX IF NOT EXISTS idx_mc_scope ON memory_collection(scope);
CREATE INDEX IF NOT EXISTS idx_mc_source ON memory_collection(source);
CREATE INDEX IF NOT EXISTS idx_mc_updated ON memory_collection(updated_at);
CREATE INDEX IF NOT EXISTS idx_m_collection_id ON memory(collection_id);
CREATE INDEX IF NOT EXISTS idx_m_subject ON memory(subject);
CREATE INDEX IF NOT EXISTS idx_m_status ON memory(status);
CREATE INDEX IF NOT EXISTS idx_m_scope ON memory(scope);
CREATE INDEX IF NOT EXISTS idx_m_source ON memory(source);
CREATE INDEX IF NOT EXISTS idx_m_type ON memory(memory_type);
CREATE INDEX IF NOT EXISTS idx_m_updated ON memory(updated_at);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_idem_expires ON idempotency_record(expires_at);
"""

_MIGRATION_SEQUENCE = [_SCHEMA_SQL, _DURABLE_SQL, _IDEMPOTENCY_SQL, _AUDIT_SQL, _INDEX_SQL]


def run_migrations(conn, target_version: str = CORE_SCHEMA_VERSION) -> list[str]:
    """Run pending migrations and return applied versions."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT (datetime('now')))")
    conn.commit()
    current = get_schema_version(conn)
    applied = []

    if current == target_version:
        return applied

    for version_sql in sorted(["1.0.0"]):
        if version_sql > current and version_sql <= target_version:
            for sql in _MIGRATION_SEQUENCE:
                execute_script(conn, sql)
            applied.append(version_sql)

    if applied:
        conn.execute(
            "INSERT OR REPLACE INTO schema_metadata (key, value) VALUES (?, ?)",
            ("core_schema_version", target_version),
        )
        conn.commit()

    return applied


def ensure_schema(conn) -> None:
    """Ensure the Core schema is initialized."""
    if not table_exists(conn, "schema_metadata"):
        run_migrations(conn)

    version = get_schema_version(conn)
    if version != CORE_SCHEMA_VERSION:
        raise MigrationRequired(f"Migration required: current={version}, target={CORE_SCHEMA_VERSION}")
