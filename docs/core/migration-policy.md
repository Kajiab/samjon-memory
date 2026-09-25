# Migration Policy

**Document ID:** SAMJON-MIG-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Schema migration policy for Samjon Memory Core V1.

## 2. Policy

- Schema version stored in schema_metadata (current: 1.2.0)
- Migrations run on startup via ensure_schema()
- Versioned migrations in migration.py (ordered version -> SQL map)
- No down migrations (only forward)
- 1.1.0 adds lifecycle columns (`forgotten_at`, `purged_at`, `purged_by`), `lifecycle_tombstone`, and backfills `forgotten_at` from reliable audit evidence only (rows without evidence stay NULL and are purge-ineligible)
- 1.2.0 adds the `media` metadata table (entity/entity cover/display_order indexes)
