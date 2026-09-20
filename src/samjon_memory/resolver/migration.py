"""Versioned migrations for Samjon Memory Resolver V1."""

from samjon_memory.errors import MigrationRequired
from samjon_memory.resolver.database import execute_script, table_exists
from samjon_memory.resolver.constants import RESOLVER_SCHEMA_VERSION

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY, value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS resolver_state (
    state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
    last_full_build_id TEXT,
    projected_at TEXT,
    core_schema_projected TEXT,
    resolver_schema_version TEXT,
    count_memories INTEGER NOT NULL DEFAULT 0,
    count_collections INTEGER NOT NULL DEFAULT 0,
    count_sections INTEGER NOT NULL DEFAULT 0,
    snapshot_checksum TEXT
);
INSERT OR IGNORE INTO resolver_state (state_id) VALUES (1);
CREATE TABLE IF NOT EXISTS projection_audit (
    build_id TEXT PRIMARY KEY,
    build_type TEXT NOT NULL CHECK (build_type IN ('full','selective')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'failed'
        CHECK (status IN ('ok','failed','rolling_back','rolled_back')),
    entity_id TEXT,
    result_count INTEGER,
    error_code TEXT
);
CREATE INDEX IF NOT EXISTS idx_proj_audit_status ON projection_audit(status);
CREATE INDEX IF NOT EXISTS idx_proj_audit_build_type ON projection_audit(build_type);
CREATE TABLE IF NOT EXISTS projection_status (
    entity_type TEXT NOT NULL CHECK (entity_type IN ('memory','collection')),
    entity_id TEXT NOT NULL,
    core_version INTEGER,
    core_checksum TEXT,
    projected_at TEXT,
    PRIMARY KEY (entity_type, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_proj_status_entity ON projection_status(entity_type, entity_id);
"""

_V110_SQL = """
CREATE TABLE IF NOT EXISTS resolver_document_snapshot (
    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL
        CHECK (entity_type IN ('standalone_memory','collection_memory','collection')),
    entity_id TEXT NOT NULL,
    collection_id TEXT,
    sequence_number INTEGER,
    subject TEXT,
    scope TEXT,
    title TEXT,
    section_path TEXT,
    raw_content TEXT,
    source TEXT,
    language TEXT,
    normalized_text TEXT,
    match_scope_key TEXT,
    core_version INTEGER,
    core_checksum TEXT,
    projected_at TEXT,
    UNIQUE (entity_type, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_snapshot_entity ON resolver_document_snapshot(entity_type, entity_id);
CREATE VIRTUAL TABLE resolver_document_fts USING fts5(
    entity_type UNINDEXED,
    entity_id UNINDEXED,
    collection_id UNINDEXED,
    sequence_number UNINDEXED,
    match_scope_key UNINDEXED,
    subject,
    title,
    section_path,
    raw_content,
    normalized_text,
    tokenize = 'unicode61'
);
CREATE TABLE IF NOT EXISTS resolver_alias_map (
    alias_id TEXT PRIMARY KEY,
    alias_term TEXT NOT NULL,
    subject TEXT NOT NULL,
    language TEXT NOT NULL,
    source TEXT,
    core_version INTEGER,
    core_checksum TEXT,
    projected_at TEXT
);
CREATE TABLE IF NOT EXISTS resolver_vocab_map (
    vocabulary_id TEXT PRIMARY KEY,
    term TEXT NOT NULL,
    definition_norm TEXT NOT NULL,
    language TEXT NOT NULL,
    source TEXT,
    core_version INTEGER,
    core_checksum TEXT,
    projected_at TEXT
);
CREATE TABLE IF NOT EXISTS resolver_tag_map (
    tag_id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    tag TEXT NOT NULL,
    language TEXT NOT NULL,
    source TEXT,
    core_version INTEGER,
    core_checksum TEXT,
    projected_at TEXT
);
CREATE TABLE IF NOT EXISTS resolver_override_map (
    override_id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    scope TEXT NOT NULL,
    key TEXT NOT NULL,
    value_snippet TEXT,
    core_version INTEGER,
    core_checksum TEXT,
    projected_at TEXT
);
"""

_MIGRATIONS = {
    "1.0.0": [_SCHEMA_SQL],
    "1.1.0": [_V110_SQL],
}


def _ver_tuple(version: str):
    return tuple(int(part) for part in version.split("."))


def get_schema_version(conn):
    """Return the current Resolver schema version."""
    row = conn.execute(
        "SELECT value FROM schema_metadata WHERE key=?",
        ("resolver_schema_version",),
    ).fetchone()
    if row is None:
        return "0.0.0"
    try:
        return row["value"]
    except (TypeError, IndexError):
        return row[0] if row else "0.0.0"


def run_migrations(conn, target_version: str = RESOLVER_SCHEMA_VERSION) -> list:
    """Run pending Resolver migrations and return applied versions."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_metadata "
        "(key TEXT PRIMARY KEY, value TEXT NOT NULL, "
        "updated_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    conn.commit()
    current = get_schema_version(conn)
    applied = []

    for version_sql in sorted(_MIGRATIONS.keys(), key=_ver_tuple):
        if (
            _ver_tuple(version_sql) > _ver_tuple(current)
            and _ver_tuple(version_sql) <= _ver_tuple(target_version)
        ):
            for sql in _MIGRATIONS[version_sql]:
                execute_script(conn, sql)
            applied.append(version_sql)

    if applied:
        conn.execute(
            "INSERT OR REPLACE INTO schema_metadata (key, value) VALUES (?, ?)",
            ("resolver_schema_version", target_version),
        )
        conn.commit()

    return applied


def ensure_schema(conn) -> None:
    """Ensure the Resolver schema is initialized and current."""
    from samjon_memory.resolver.database import ensure_fts5

    ensure_fts5(conn)
    if not table_exists(conn, "schema_metadata"):
        run_migrations(conn)

    version = get_schema_version(conn)
    if version != RESOLVER_SCHEMA_VERSION:
        raise MigrationRequired(
            f"Resolver migration required: current={version}, "
            f"target={RESOLVER_SCHEMA_VERSION}"
        )
