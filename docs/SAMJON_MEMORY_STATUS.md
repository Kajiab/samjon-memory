# Samjon Memory Status

**Document ID:** SAMJON-MEMORY-STATUS-001
**Version:** 2.1.0
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering
**Last reviewed:** 2026-09-20

## Current Phase

- Project status: Core V1 complete and verified
- Current phase: Core V1 delivered, Resolver not started
- Core database schema: 1.1.0
- Core REST API: V1
- CoreService: Implemented
- Core Portal: Server-rendered, verified
- Memory Activate: Implemented
- Lifecycle (Forget / Restore / Purge): Implemented
- Administration page: Implemented
- Dashboard metrics: Implemented
- Audit summary, filters, pagination: Implemented
- Manual Portal verification: PASS
- Resolver: Foundation C2 (schema 1.1.0, selective rebuild + bounded context)
- MCP readiness: Not ready

## Core Baseline

- Core schema is versioned at 1.1.0
- Lifecycle (activate / restore / purge) and audit (summary, filters, pagination) are implemented on top of the V1 core
- Portal is server-rendered with HTTP Basic auth and exact Origin validation

## Portal Implementation

The Core Portal has been verified with:

- One server-rendered Portal
- FastAPI HTTP Basic Authentication
- Exactly one configured administrator
- No users table, no registration, no custom login page
- No session cookies, no login nonce, no logout tracking
- No multiple Portal users or roles
- Exact Origin validation for mutations
- No-side-effect Cancel behavior
- Add Section creates Memory ID automatically
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

- Server-rendered Portal: Implemented
- HTTP Basic authentication: Verified by tests
- Exact Origin validation: Verified by tests
- Memory Portal workflow: Verified by tests
- Collection Portal workflow: Verified by tests
- Cancel behavior: Verified by tests
- Portal security tests: All passing
- Capability reporting: Verified by tests

## Resolver

- Status: Foundation C2 delivered (selective rebuild, bounded context); Resolver Portal not implemented
- Resolver database (samjon_resolver.sqlite): created, schema 1.1.0
- FTS5 availability check: Implemented (fail-fast RESOLVER_DATABASE_UNAVAILABLE)
- Resolver migrations: Implemented and idempotent
- Resolver schema metadata: Implemented
- Resolver state + projection-audit foundations: schema only
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
- Not implemented: Resolver Portal, embeddings, vector search, AI enrichment, MCP
- Semantic search: Not implemented
- AI enrichment: Not implemented
- Embeddings: Not implemented
- MCP implementation: Not implemented

## Test Evidence

All tests pass with executable evidence:

- Command: `python -m pytest tests/ -v --tb=short`
- Passed: 257
- Failed: 0
- Skipped: 0
- Verified: 2026-09-20

### Coverage Areas
- Migration and migration idempotency (schema 1.1.0, backfill of `forgotten_at` from audit)
- Memory create/read/query/update/supersede/forget/activate/restore/purge
- Collection create/edit/order/validate/activate/restore/purge, independent section editing
- Collection subject/scope consistency (sections inherit subject/scope, title is the section name, move-existing requires match, collection immutable once sections exist)
- Dashboard metrics + filtered-list links
- Forget/Restore/Purge lifecycle, purge guards (30-day retention, admin, `PURGE` confirmation), tombstones, related-metadata erasure
- Audit summary, filters (action/entity_type/entity_id/since/until), pagination, sanitization, append-only
- Portal UI + security (HTTP Basic, exact Origin, XSS, Cancel no-side-effect)
- Administration page (forgotten/purged, purge eligibility, tombstone/audit counts, schema/db status)
- Idempotency, content limits, sensitive-data rejection, backup/isolated restore
- OpenAPI drift + route registration