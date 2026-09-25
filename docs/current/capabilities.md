# Proven Capabilities

**Document ID:** SAMJON-CAP-001
**Version:** 2.0.0
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering
**Last reviewed:** 2026-09-25

## 1. Purpose

Proven capabilities for the current Samjon Memory backend (Core, Resolver,
Media, Library, Portal, Docker). Only behavior with executable test evidence is
listed as PROVEN.

## 2. Capabilities

| Capability | Status | Notes |
|---|---|---|
| SQLite schema | PROVEN | migrations.py |
| Core memory CRUD | PROVEN | create/get/update/query/supersede/forget |
| Memory activate | PROVEN | draft -> active, version bump, audit |
| Restore | PROVEN | forgotten -> draft, version bump, audit |
| Purge | PROVEN | irreversible, forgotten >= 30 days, admin + "PURGE" confirmation, tombstone |
| Collection lifecycle | PROVEN | draft/active/reorder/validate/restore/purge |
| Durable metadata | PROVEN | alias/vocabulary/tag/manual_override; erased on memory purge |
| Idempotency | PROVEN | header-based |
| Audit | PROVEN | audit_log; summary, filters, pagination |
| Dashboard metrics | PROVEN | Memories / Collections / System Overview |
| Administration page | PROVEN | forgotten/purged, retention, schema/db status |
| Backup/restore | PROVEN | isolated restore |
| Sensitive data rejection | PROVEN | credential detection |
| Web Portal | PROVEN | HTML portal, server-rendered |
| HTTP Basic Authentication | PROVEN | single admin, env config |
| Exact Origin validation | PROVEN | SAMJON_PORTAL_ALLOWED_ORIGINS |
| Add Section auto-generates Memory ID | PROVEN | backend generates ID |
| Collection Memories sorted by sequence_number ASC | PROVEN | Move Up/Down buttons correct |
| Resolver database isolation | PROVEN | separate resolver DB; no Core fact tables and vice versa |
| Resolver schema + migrations | PROVEN | `1.1.0` snapshot + FTS5 + expansion tables; idempotent |
| Resolver FTS5 availability | PROVEN | fail-fast RESOLVER_DATABASE_UNAVAILABLE |
| Resolver readiness endpoint | PROVEN | GET /resolver/ready, Core-independent |
| Resolver full projection build | PROVEN | active standalone/collection/sections + durable metadata; inactive excluded |
| Resolver atomic rebuild + rollback | PROVEN | temp DB swap, .prev rollback, interrupted-swap recovery |
| Resolver rebuild lock | PROVEN | REBUILD_IN_PROGRESS |
| Resolver rebuild API | PROVEN | admin-token rebuild; read-token status |
| Resolver search API + result types | PROVEN | POST /api/v1/resolver/query (read token); standalone/collection/collection_with_selected/ambiguous/no_match |
| Resolver deterministic ranking | PROVEN | title/exact-subject above content; alias/vocab/tag boosts; deterministic tie-break; no recency |
| Resolver safe FTS5 query parsing | PROVEN | quotes/parens/hyphens/colons/asterisks/Thai punctuation/operators/empty/oversized |
| Resolver freshness + allow_stale | PROVEN | fresh/stale/missing/orphaned from Core version+checksum; allow_stale |
| Resolver selective rebuild + expansion refresh | PROVEN | memory/collection selective; inactive/orphaned cleanup; fallback to full |
| Resolver bounded context expansion | PROVEN | neighbors ordered by sequence, active-only, no cross-Collection, budget+truncation |
| Resolver Debug Portal | PROVEN | /portal/resolver/ server-rendered; HTTP Basic + exact Origin; evidence viewer; guarded rebuild |
| Media upload / covers / galleries | PROVEN | media lifecycle tests (upload, cover, reorder, replace, remove, purge) |
| Media lifecycle (forget/restore/purge) | PROVEN | media tests; purge erases files + metadata |
| Media backup / restore | PROVEN | media_create_backup / check / restore tests |
| Resolver media-text indexing | PROVEN | selective rebuild picks up alt/caption changes |
| Jinja2 Portal rendering | PROVEN | template tests + portal tests (no HTML-string renderers) |
| Library and Reader views | PROVEN | library/reader portal tests |
| Docker bind-mount persistence | PROVEN | compose has bind mounts, no named volume |
| External category covers | PROVEN | SAMJON_CATEGORY_COVERS_ROOT config + read-only bind; no image rebuild |
| OpenAPI | PROVEN | drift test |

## 3. Limitations

- No semantic search / embeddings / vector search / AI enrichment in the backend.
- MCP and Numchoke integration are separate repositories / work items; the
  backend does not implement MCP transport or tool registration.
- No public multi-user support or user registration; no production Internet
  exposure.
