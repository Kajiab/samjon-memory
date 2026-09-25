# Resolver Schema and Migrations

**Document ID:** SAMJON-RESOLVER-SCHEMA-001
**Status:** PROVEN / IMPLEMENTED
**Owner:** Samjon Memory Engineering
**Approver:** Jeab
**Last reviewed:** 2026-09-25

> Implemented and tested for schema `1.1.0`; this
> document records the design and guiding principles.

## 1. Principles

- `samjon_resolver.sqlite` is physically separate from `samjon_core.sqlite`.
- Each database has independent schema metadata and migrations.
- The Core database must contain no Resolver tables and vice versa
  (regression guard: `tests/test_migration.py::test_no_resolver_tables`).
- Resolver is disposable and rebuildable. An incompatible schema change bumps
  the Resolver schema version and requires a full rebuild rather than a
  destructive ALTER of every column.
- Resolver never opens Core repositories or the Core SQLite file directly.

## 2. Resolver Schema Version

- `RESOLVER_SCHEMA_VERSION = "1.1.0"` (implemented: snapshot + FTS5 + expansion tables).
- Stored in the Resolver `schema_metadata` under `resolver_schema_version`.

## 3. Tables

### 3.1 schema_metadata
Key/value store for the Resolver schema version and metadata.

### 3.2 resolver_state (single row, state_id = 1)
Records full-build identity and freshness facts for reporting.

```text
last_full_build_id
projected_at
core_schema_projected
resolver_schema_version
count_memories
count_collections
count_sections
snapshot_checksum
```

### 3.3 projection_audit
Append-only rebuild audit. Resolver-local; not a Core audit record.

```text
build_id, build_type ('full'|'selective'), started_at, finished_at,
status ('ok'|'failed'|'rolling_back'|'rolled_back'),
entity_id, result_count, error_code
```

### 3.4 projection_status (per projected entity)
Used to derive fresh/stale/missing/orphaned by comparing against current Core.

```text
entity_type ('memory'|'collection'), entity_id,
core_version, core_checksum, projected_at
PRIMARY KEY (entity_type, entity_id)
```

### 3.5 resolver_document_snapshot + resolver_document_fts
FTS5 external content over a shadow snapshot table.

```text
entity_id, entity_type ('standalone_memory'|'collection_memory'|'collection'),
collection_id, sequence_number,
subject, title, section_path, raw_content,
source, language, normalized_text, match_scope_key
```

### 3.6 Derived expansion maps (from Core durable metadata)

```text
resolver_alias_map    (alias_term, subject, language, source)
resolver_vocab_map    (term, definition_norm, language, source)
resolver_tag_map      (subject, tag)
resolver_override_map (subject, scope, key, value_snippet)
```

## 4. FTS5 Availability

- Runtime requires SQLite compiled with FTS5 (`ENABLE_FTS5`).
- Verified: Python sqlite3 `3.49.1` reports `FTS5 enabled: True`.
- Resolver schema bootstrap fails fast (`RESOLVER_DATABASE_UNAVAILABLE` /
  `MIGRATION_REQUIRED`) if FTS5 is unavailable.

## 5. Migration Plan

- Follow the Core migration pattern (versioned `version -> [SQL]` map, forward
  only, no down migrations) in a Resolver-local migration module.
- Run on startup via `ensure_schema`.
- Incompatible change: bump Resolver schema version and require a full rebuild.
- Backward-compatible addition: add an incremental forward migration.

## 6. Core Interaction

- The projection builder calls CoreService through the approved service
  boundary (e.g. existing read methods such as
  `query_memories(..., collection_scope='active_knowledge')`).
- New read-only CoreService projection methods are permitted only when required
  and must not change existing Core behavior, schema, or API contracts.
- Resolver never opens Core repositories or the Core SQLite file directly.
