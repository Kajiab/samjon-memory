# Proven Capabilities

**Document ID:** SAMJON-CAP-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Proven capabilities for Samjon Memory Core V1.

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
| OpenAPI | PROVEN | drift test |

## 3. Limitations

- Resolver search/ranking/freshness: Implemented (Foundation C1)
- Resolver Debug Portal: Implemented (Foundation D)
- No semantic search / embeddings / vector search / AI enrichment / MCP / Numchoke
