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

_V110_SQL = """
ALTER TABLE memory ADD COLUMN forgotten_at TEXT;
ALTER TABLE memory ADD COLUMN purged_at TEXT;
ALTER TABLE memory ADD COLUMN purged_by TEXT;
ALTER TABLE memory_collection ADD COLUMN forgotten_at TEXT;
ALTER TABLE memory_collection ADD COLUMN purged_at TEXT;
ALTER TABLE memory_collection ADD COLUMN purged_by TEXT;
CREATE TABLE IF NOT EXISTS lifecycle_tombstone (
    tombstone_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('memory','collection','durable_alias','durable_user_tag','manual_override')),
    entity_id TEXT NOT NULL,
    final_version INTEGER,
    content_checksum TEXT,
    purged_at TEXT NOT NULL DEFAULT (datetime('now')),
    actor TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lt_entity ON lifecycle_tombstone(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_lt_purged ON lifecycle_tombstone(purged_at);
CREATE INDEX IF NOT EXISTS idx_m_forgotten ON memory(forgotten_at);
CREATE INDEX IF NOT EXISTS idx_m_purged ON memory(purged_at);
CREATE INDEX IF NOT EXISTS idx_mc_forgotten ON memory_collection(forgotten_at);
CREATE INDEX IF NOT EXISTS idx_mc_purged ON memory_collection(purged_at);
-- Backfill forgotten_at for currently-forgotten rows using reliable audit
-- evidence only (the most recent matching forget audit). Rows with no reliable
-- timestamp keep NULL and remain ineligible for purge.
UPDATE memory SET forgotten_at=(
    SELECT MAX(created_at) FROM audit_log
    WHERE entity_type='memory' AND entity_id=memory.memory_id AND action='memory_forget'
) WHERE status='forgotten' AND forgotten_at IS NULL;
UPDATE memory_collection SET forgotten_at=(
    SELECT MAX(created_at) FROM audit_log
    WHERE entity_type='collection' AND entity_id=memory_collection.collection_id AND action='collection_forget'
) WHERE status='forgotten' AND forgotten_at IS NULL;
"""

_MEDIA_SQL = """
CREATE TABLE IF NOT EXISTS media (
    media_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('memory','collection')),
    entity_id TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    thumbnail_path TEXT,
    mime_type TEXT NOT NULL CHECK(mime_type IN ('image/jpeg','image/png','image/webp')),
    file_size INTEGER NOT NULL CHECK(file_size >= 0),
    width INTEGER NOT NULL CHECK(width > 0),
    height INTEGER NOT NULL CHECK(height > 0),
    alt_text TEXT,
    caption TEXT,
    display_order INTEGER NOT NULL DEFAULT 0,
    is_cover INTEGER NOT NULL DEFAULT 0 CHECK(is_cover IN (0,1)),
    checksum TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL DEFAULT 'active'
        CHECK(lifecycle_status IN ('active','hidden','purged')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_media_entity ON media(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_media_entity_cover ON media(entity_type, entity_id, is_cover);
CREATE INDEX IF NOT EXISTS idx_media_display ON media(display_order);
"""

_MIGRATIONS = {
    "1.0.0": [_SCHEMA_SQL, _DURABLE_SQL, _IDEMPOTENCY_SQL, _AUDIT_SQL, _INDEX_SQL],
    "1.1.0": [_V110_SQL],
    "1.2.0": [_MEDIA_SQL],
}


def _ver_tuple(version: str):
    return tuple(int(part) for part in version.split("."))


def run_migrations(conn, target_version: str = CORE_SCHEMA_VERSION) -> list[str]:
    """Run pending migrations and return applied versions."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT (datetime('now')))")
    conn.commit()
    current = get_schema_version(conn)
    applied = []

    for version_sql in sorted(_MIGRATIONS.keys(), key=_ver_tuple):
        if _ver_tuple(version_sql) > _ver_tuple(current) and _ver_tuple(version_sql) <= _ver_tuple(target_version):
            for sql in _MIGRATIONS[version_sql]:
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
