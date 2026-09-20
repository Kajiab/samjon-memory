# Resolver Rebuild and Test Plan

**Document ID:** SAMJON-RESOLVER-REBUILD-001
**Status:** PLANNED
**Owner:** Samjon Memory Engineering
**Approver:** Jeab
**Last reviewed:** 2026-09-20

> Foundation B (full projection rebuild) is implemented and tested; this
> document records the design and the remaining Foundation C work.

## 1. Rebuild Design

### 1.1 Full Atomic Rebuild (Decision 1)

Use a temporary DB plus a coordinated file swap:

1. Read Active facts from Core through the approved CoreService boundary.
2. Build a fresh Resolver DB in a temp file (same directory as the Resolver path).
3. Create FTS5, populate, and optimize.
4. Close all Resolver connections and checkpoint WAL.
5. Compute the snapshot checksum and write `resolver_state`, then commit.
6. Coordinated file swap: atomically replace `samjon_resolver.sqlite`, keeping
   the previous file as a rollback copy.
7. Write `projection_audit` status `ok`.

Core connections are not affected by any step of the swap.

### 1.2 Interrupted Swap Recovery

On startup, Resolver detects an interrupted swap (partial/absent final DB or a
pending temp/rollback artifact). Recovery:

- Completes or rolls back the swap using the rollback copy.
- Records the recovery in `projection_audit`.

### 1.3 Rollback

If the swap or verification fails:

- Restore the previous Resolver file from the rollback copy.
- Record status `rolling_back` / `rolled_back`.
- Core is unchanged.

### 1.4 Selective Rebuild (Decision 2)

- Implemented after full rebuild.
- Mandatory for Resolver V1 completion.
- Reprojects one entity by reading its current Core state and updating its
  snapshot, FTS rows, and `projection_status`.

### 1.5 In-progress Build

A running rebuild returns `REBUILD_IN_PROGRESS` for rebuild/status calls.

## 2. Auth Boundary (Decision 4)

- query / projection status: existing service read token.
- rebuild operations: existing admin token.
- Resolver Portal: existing HTTP Basic Admin.
- No Resolver-specific token in V1.

## 3. Readiness (Decision 9)

- Core readiness and Resolver readiness are separate.
- A dedicated Resolver readiness endpoint is provided.
- Resolver readiness reflects Resolver database availability, schema state,
  and FTS5 availability, independent of Core readiness.

## 4. Test Plan

All tests use temporary databases and synthetic credentials, consistent with
`tests/conftest.py`.

### 4.1 Migration

- Resolver initial migration and migration idempotency.
- Resolver schema version.
- No Core tables in Resolver DB and no Resolver tables in Core DB.
- FTS5 fail-fast when unavailable.

### 4.2 Projection

- Only Active facts are projected (draft/superseded/forgotten/purged excluded).
- Collections project at collection + Section level; standalone at Memory level.
- Durable alias/vocab/tag/override used as expansion.
- Sensitive data is not indexed.
- Core is never modified or opened directly by Resolver.

### 4.3 Retrieval

- All result types + `auto`/`memory`/`collection` targets.
- FTS5, alias, vocab, and tag matches.
- Deterministic ranking and match reasons.
- Bounded results and context budget.
- Evidence integrity: authoritative content read from Core.
- Conflicts identified.

### 4.4 Freshness

- fresh / stale / missing / orphaned derived from current Core version/checksum.
- Default `allow_stale=false` returns `PROJECTION_STALE`.
- `allow_stale=true` returns IDs + evidence with `freshness=stale`,
  `incomplete=true`.

### 4.5 Rebuild

- Full rebuild produces fresh state and consistent checksums.
- Rollback restores the previous DB on a simulated failed swap.
- Interrupted swap startup recovery.
- Selective rebuild refreshes one entity.
- Core is unchanged after any rebuild or rollback.

### 4.6 API / Auth

- OpenAPI drift incl. Resolver routes.
- Capabilities report Resolver as implemented only after tests pass.
- Read token required for query/status; admin token required for rebuild.
- Resolver readiness endpoint independent of Core readiness.

### 4.7 Resolver Portal

- HTTP Basic covers all routes, `WWW-Authenticate: Basic`.
- Reject missing/invalid credentials; mutations require exact approved Origin.
- Credentials absent from HTML/JS/URL/log/audit/capabilities.
- Query debug + guarded rebuild; cancel has no side effects.
