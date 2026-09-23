# Resolver V1 Specification

**Document ID:** SAMJON-RESOLVER-SPEC-001
**Status:** PLANNED
**Owner:** Samjon Memory Engineering
**Approver:** Jeab
**Last reviewed:** 2026-09-20
**Depends on:** Core V1.1 frozen baseline (`docs/core/CORE_V1_FREEZE.md`)
**Implementation status:** Foundations A, B, C1, C2, and D are implemented and tested. The Resolver Debug Portal is implemented; only MCP / Numchoke integration remains out of scope. See `RESOLVER_V1_FREEZE_EVALUATION.md` (all Resolver V1 freeze gates PASS -> READY_FOR_OWNER_APPROVAL).

> This is a planning document. No code, migrations, routes, Portal, or
> capability changes are implemented in this task. Resolver status is
> **PLANNED** and becomes `IMPLEMENTED` / `PROVEN` only after executable tests
> pass (AGENTS.md §20, §30).

## 1. Purpose

Resolver V1 is the deterministic, derived search projection layer for Samjon
Memory. It reads Active facts from Core over the approved CoreService service
boundary and searches them with FTS5.

## 2. Hard Constraints

- Core (`samjon_core.sqlite`) is an authoritative, frozen baseline (schema `1.1.0`).
- Do not change Core schema, CoreService behavior, or Core API contracts.
- Resolver (`samjon_resolver.sqlite`) is a separate database file, schema,
  migration set, repository, backup policy, and lifecycle.
- Resolver reads Core only through the approved CoreService boundary.
- Resolver must never access Core repositories or open `samjon_core.sqlite` directly.
- Resolver must never write facts into Core.
- Use relative paths only. Do not read parent docs or sibling repositories.
- Keep Core readiness separate from Resolver readiness.

## 3. Approved Decisions (recorded 2026-09-20)

1. Full rebuild uses a temp DB plus coordinated file swap. Resolver
   connections are closed and WAL is checkpointed before the swap. Core
   connections remain unaffected. Startup recovery handles interrupted swaps.
2. Full rebuild is implemented before selective rebuild. Selective rebuild is
   mandatory for Resolver V1 completion.
3. Freshness policy:
   - `allow_stale` defaults to `false`.
   - A stale projection returns `PROJECTION_STALE`.
   - `allow_stale=true` may return IDs and evidence with `freshness=stale` and
     `incomplete=true`.
   - Authoritative content is always loaded from Core.
4. Authentication:
   - query/status use the existing service read token.
   - rebuild operations use the existing admin token.
   - The Resolver Portal uses the existing HTTP Basic Admin.
   - No Resolver-specific token is created in V1.
5. Target rules:
   - `memory` -> `standalone_memory`, `collection_memory`
   - `collection` -> `collection`, `collection_with_selected_memories`
   - `auto` -> all result types
6. No recency boost is used in Ranking V1.
7. Freshness is computed from the current Core version/checksum. A stored
   derived freshness label is not treated as authoritative.
8. New read-only CoreService projection methods are permitted only when
   required. Existing Core behavior, schema, and API contracts are unchanged.
9. Core readiness and Resolver readiness are independent. A dedicated Resolver
   readiness endpoint is provided.
10. FTS5 queries are sanitized and parsed. Raw user input is never passed
    directly into MATCH syntax.

## 4. Projection Scope

Only Active facts are projected:

- `memory.status = 'active'` -> standalone Memory or Collection Section Memory.
- `memory_collection.status = 'active'` -> Collection-level projection plus its
  Active Section Memories.
- Active durable metadata (`durable_alias`, `durable_vocabulary`,
  `durable_user_tag`, `manual_override`) is used as derived expansion sources,
  not as primary results.

Not projected: `draft`, `superseded`, `forgotten`, `purged` facts.

## 5. Result Types

```text
standalone_memory
collection_memory
collection
collection_with_selected_memories
ambiguous
no_match
```

## 6. Target Rules

| target | allowed result types |
|---|---|
| `memory` | `standalone_memory`, `collection_memory` |
| `collection` | `collection`, `collection_with_selected_memories` |
| `auto` | all result types |

## 7. Evidence Contract

Responses are bounded and identify:

- Memory or Collection identity.
- Core version.
- Projected Core version.
- Projection freshness.
- Score.
- Match reasons.
- Conflicts.
- Result type.

Authoritative content is loaded from Core, never from Resolver.

## 8. Retrieval Is Bounded

- Result counts are limited by configuration.
- A Collection result does not include every Memory automatically.
- Context expansion may include neighboring sections only when required to
  preserve meaning and within the configured context budget.

## 9. Non-Goals (V1)

- No embeddings, vector search, or AI enrichment.
- No MCP implementation or Numchoke integration.
- No resolution of facts in Core by Resolver.

## 10. Data Ownership

- Core stores authoritative facts.
- Resolver stores derived, rebuildable search projections.
- Resolver may be deleted and rebuilt without losing authoritative information.
