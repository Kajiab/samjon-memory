# Samjon Memory Status

**Document ID:** SAMJON-MEMORY-STATUS-001
**Version:** 3.0.0
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering
**Last reviewed:** 2026-09-25

## Current Phase

The Samjon Memory **backend** is complete and usable.

- Project status: Core, Resolver, Media, Library, Administration, and Docker packaging are implemented
- Current phase: Core V1 delivered and extended; Resolver V1 delivered (freeze evaluation: ALL GATES PASS)
- Core database schema: **1.2.0** (1.1.0 lifecycle/purge + 1.2.0 media table)
- Resolver database schema: **1.1.0** (snapshot + FTS5 + expansion maps)
- Core REST API: V1
- CoreService: Implemented
- Core Portal: Server-rendered (Jinja2 templates), verified
- Memory Activate: Implemented
- Lifecycle (Forget / Restore / Purge): Implemented
- Media (images, covers, thumbnails, lifecycle): Implemented
- Library and Reader views: Implemented
- Administration page: Implemented
- Dashboard metrics: Implemented
- Audit summary, filters, pagination: Implemented
- Resolver: Implemented (projection, FTS5 search, ranking, freshness, selective + atomic rebuild, Debug Portal)
- Docker: Implemented (host bind mounts for data + external category covers)
- Manual Portal verification: PASS
- Samjon Memory MCP adapter: **separate repository / work item** (not part of this repository)

### MCP readiness

The **backend** is MCP-ready: it exposes the read/query APIs an external MCP
adapter needs (`POST /api/v1/resolver/query`, memory and collection read
endpoints, and `GET /api/v1/capabilities` for discovery). The backend does not
itself implement MCP transport or tool registration — that is the Samjon Home
MCP module, a separate repository and work item. The backend being a complete
service does not imply the independent MCP adapter exists.

## System components

```text
Core     -> authoritative Memories and Collections   (samjon_core.sqlite, schema 1.2.0)
Resolver -> deterministic retrieval projection        (samjon_resolver.sqlite, schema 1.1.0)
Media    -> images, covers, thumbnails, lifecycle      (data/media + media table in Core)
Portal   -> Jinja2 Library + Administration            (HTTP Basic + exact Origin)
Docker   -> portable deployment, host bind mounts      (Dockerfile, compose.yaml)
```

## Core Baseline

- Core schema is versioned at 1.2.0
- Lifecycle (activate / restore / purge) and audit (summary, filters, pagination) are implemented on top of the V1 core
- Media metadata is stored in Core (schema 1.2.0); binary files live under `data/media/`
- Portal is server-rendered with HTTP Basic auth and exact Origin validation

## Portal Implementation

The Core Portal has been verified with:

- One server-rendered Portal rendered from **Jinja2 templates** (autoescaped; no Python HTML-string renderers, no SPA)
- FastAPI HTTP Basic Authentication
- Exactly one configured administrator
- No users table, no registration, no custom login page
- No session cookies, no login nonce, no logout tracking
- No multiple Portal users or roles
- Exact Origin validation for mutations
- No-side-effect Cancel behavior
- Add Section creates Memory ID automatically
- Vocabulary hints (Portal-only): Subject/Type/Scope fields show collected words as datalist suggestions, new words used in successful saves are remembered automatically, curated at `/portal/vocabulary` (file-backed, never in Core/Resolver SQLite)
- Collection subject/scope consistency invariant (sections inherit; move requires match; immutable once sections exist)
- Collection Memories sorted by sequence_number ASC
- Move Up / Move Down works correctly
- Reorder increments Collection version
- Memory Activate (draft -> active)
- Restore returns to draft
- Purge is irreversible (30-day retention, admin + "PURGE" confirmation)
- Administration page (forgotten/purged, retention, audit, schema + db status)
- Dashboard metrics (Memories / Collections / System Overview)
- Audit summary + filters + pagination

Required configuration:

- `SAMJON_PORTAL_USERNAME`
- `SAMJON_PORTAL_PASSWORD`
- `SAMJON_PORTAL_ALLOWED_ORIGINS`

## Portal Status

- Server-rendered Portal: Implemented (Jinja2 templates)
- HTTP Basic authentication: Verified by tests
- Exact Origin validation: Verified by tests
- Memory Portal workflow: Verified by tests
- Collection Portal workflow: Verified by tests
- Cancel behavior: Verified by tests
- Portal security tests: All passing
- Capability reporting: Verified by tests
- Resolver Debug Portal (/portal/resolver/): Implemented, verified by tests

## Resolver

- Status: Implemented; Resolver V1 Freeze Evaluation: ALL GATES PASS -> READY_FOR_OWNER_APPROVAL
- Resolver database (samjon_resolver.sqlite): created, schema 1.1.0
- FTS5 availability check: Implemented (fail-fast RESOLVER_DATABASE_UNAVAILABLE)
- Resolver migrations: Implemented and idempotent
- Resolver schema metadata: Implemented
- Resolver state + projection-audit: Implemented (single-row resolver_state, append-only projection_audit)
- Resolver database isolation from Core: PROVEN by tests
- Resolver readiness independent of Core: PROVEN; `/resolver/ready` endpoint
- Full projection build (active standalone / collection / sections ordered by sequence): Implemented, PROVEN by tests
- Active aliases, vocabulary, tags, and sanitized overrides projected: Implemented
- Draft / superseded / forgotten / purged excluded: PROVEN by tests
- Deterministic snapshot checksum: PROVEN by tests
- Resolver schema `1.1.0`: snapshot + FTS5 + expansion-map tables
- Atomic full rebuild (temp DB + coordinated swap + `.prev` rollback): Implemented
- Interrupted-swap startup recovery: Implemented
- Single-process rebuild lock (`REBUILD_IN_PROGRESS`): Implemented
- Rebuild API: `POST /api/v1/resolver/rebuild` (admin), `GET .../rebuild/status` + `GET .../projection/status` (read token)
- FTS5 rows match snapshot rows: PROVEN
- Resolver search API: `POST /api/v1/resolver/query` (read token) Implemented, PROVEN by tests
- Safe FTS5 query parsing (quotes/parens/hyphens/colons/asterisks/Thai punctuation/operators/empty/oversized): Implemented
- Deterministic ranking (no recency): title + exact-subject above content; alias/vocab/tag boosts; deterministic tie-break
- Result types: standalone_memory, collection_memory, collection, collection_with_selected_memories, ambiguous, no_match
- Human-readable match reasons: Implemented
- Projection freshness (fresh/stale/missing/orphaned from current Core version + checksum): Implemented
- `allow_stale`: default false -> PROJECTION_STALE; true -> IDs + evidence with freshness=stale and incomplete=true
- Bounded results + limit/offset pagination: Implemented
- Selective Memory rebuild (standalone or Section + containing Collection projection): Implemented, PROVEN by tests
- Selective Collection rebuild (Collection + all active Sections + FTS + projection status): Implemented
- Inactive / forgotten / purged / orphaned projections, FTS rows, and status removed: Implemented
- Alias / vocabulary / tag / override expansion refresh: Implemented; unsafe/ambiguous impact falls back to full rebuild
- Selective operations transactional; failure rolls back to the previous usable projection: PROVEN
- Bounded context expansion (neighboring Sections, sequence ASC, active-only, never cross Collection): Implemented
- `context_budget` + neighbor count enforced; truncation reported explicitly: PROVEN
- Selective rebuild API `POST /api/v1/resolver/rebuild/selective` (admin token)
- Query fields `neighbor_items` + `context_budget`; evidence includes selected Section IDs, sequence numbers, budget used, truncated flag, inclusion reason
- Resolver Debug Portal under /portal/resolver/: Implemented (Dashboard, Query Debug, Projection Status, Rebuild Controls, Evidence Viewer)
- Portal reuses existing Portal HTTP Basic auth + exact Origin validation; server-rendered only; no duplicate SPA
- Portal handlers call ResolverService / CoreService only; never open SQLite or repositories directly; no Core writes
- Rebuild controls require explicit `rebuild` confirmation; Cancel is a no-side-effect navigation link
- Acceptance dataset (synthetic) + acceptance tests: Thai/English search, aliases, vocabulary, collections/sections, ambiguous/no-match, stale/allow_stale
- Resolver V1 Freeze Evaluation: ALL GATES PASS (see `docs/resolver/RESOLVER_V1_FREEZE_EVALUATION.md`)
- Not implemented / out of scope in the backend: embeddings, vector search, AI enrichment, Numchoke integration
- Semantic search: Not implemented
- AI enrichment: Not implemented
- Embeddings: Not implemented
- MCP implementation: Not implemented

## Test Evidence

All tests pass with executable evidence:

- Command: `python -m pytest tests/ -q --no-header`
- Passed: 453
- Failed: 0
- Skipped: 0
- Verified: 2026-09-26

### Coverage Areas
- Migration and migration idempotency (Core schema 1.2.0; 1.1.0 backfills `forgotten_at` from reliable audit evidence)
- Memory create/read/query/update/supersede/forget/activate/restore/purge
- Collection create/edit/order/validate/activate/restore/purge, independent section editing
- Resolver migrations, schema 1.1.0, projection, FTS5 search, deterministic ranking, freshness, atomic + selective rebuild, bounded context
- Media lifecycle (upload, covers, reorder, replace, remove, purge, backup/restore) and Resolver media-text indexing
- Jinja2 Portal: Library, Readers, Administration; HTTP Basic, exact Origin, XSS, Cancel no-side-effect, credentials absent
- Docker packaging: bind mounts, no named volume, external category covers, host-dir creation, read-only cover mount
- Collection subject/scope consistency (sections inherit subject/scope, title is the section name, move-existing requires match, collection immutable once sections exist)
- Dashboard metrics + filtered-list links
- Forget/Restore/Purge lifecycle, purge guards (30-day retention, admin, `PURGE` confirmation), tombstones, related-metadata erasure
- Audit summary, filters (action/entity_type/entity_id/since/until), pagination, sanitization, append-only
- Portal UI + security (HTTP Basic, exact Origin, XSS, Cancel no-side-effect)
- Administration page (forgotten/purged, purge eligibility, tombstone/audit counts, schema/db status)
- Idempotency, content limits, sensitive-data rejection, backup/isolated restore
- OpenAPI drift + route registration
