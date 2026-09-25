# Resolver V1 Freeze Evaluation

**Document ID:** SAMJON-RESOLVER-V1-FREEZE-001
**Status:** PASS (evaluation from executable evidence)
**Owner:** Samjon Memory Engineering
**Approver:** Jeab (approval pending — freeze is NOT automatic)
**Last reviewed:** 2026-09-20
**Depends on:** Custom Core V1.1 frozen baseline + Resolver Foundations A, B, C1, C2, D

> Completeness: every Resolver V1 Release Gate (AGENTS.md §32.2) is evaluated
> strictly from executable test evidence (`python -m pytest tests/`).
> Resources are not marked frozen automatically.

## Full test evidence

- Focused Resolver suites: `test_resolver.py`, `test_resolver_rebuild.py`,
  `test_resolver_search.py`, `test_resolver_selective.py`,
  `test_resolver_acceptance.py` — all pass.
- OpenAPI drift: PASS.
- Full suite: `python -m pytest tests/` -> **453 passed, 0 failed**.

## Resolver V1 Done Gates (AGENTS.md §32.2)

| Gate | Verdict | Evidence |
|---|---|---|
| Resolver DB physically separate and rebuildable | PASS | Database-isolation tests; `samjon_resolver.sqlite` separate; rebuild tests |
| Projection uses frozen Core data | PASS | `resolver_projection_snapshot()` (read-only) via CoreService; Core untouched |
| Collection-level and Memory-level search work from one intent | PASS | C1 search + `auto/memory/collection` target tests |
| FTS5, vocabulary, aliases, tags, ranking, and freshness are tested | PASS | C1 search/ranking/freshness tests; FTS5 availability + match tests |
| Atomic rebuild and rollback pass | PASS | Foundation B: temp-DB swap, `.prev` rollback, interrupted-swap recovery, rollback tests |
| Resolver Portal exposes evidence and guarded rebuild operations | PASS | Foundation D: Portal auth/origin/confirmation/cancel + evidence viewer tests |
| Resolver recreation leaves Core unchanged | PASS | Core hash/versions/audit unchanged across full/selective/portal tests |
| OpenAPI and canonical documentation match implementation | PASS | OpenAPI drift test; docs updated from evidence |

## Resolver Release-Blocking (AGENTS.md §31)

| Gate | Verdict | Evidence |
|---|---|---|
| Resolver does not modify Core facts | PASS | No Core writes; Core-unchanged tests |
| Durable manual information does not live only in Resolver | PASS | aliases/vocab/tags/overrides are read from Core; Resolver derived |
| Resolver can be deleted and rebuilt | PASS | full rebuild tests + `delete & rebuild` semantics |
| Rebuild never exposes a half-built index | PASS | atomic file swap; queries only see complete DB |
| Projection freshness is exposed | PASS | `projection_freshness` + freshness states returned |
| Retrieval is bounded and explained | PASS | limit/offset + deterministic `match_reasons` |
| Resolver migrations / rebuild tests pass | PASS | migration idempotency + rebuild/selective tests |

## Known limitations (non-blocking for Resolver V1 freeze)

- Selective rebuild refreshes expansion maps but does not re-normalize unrelated
  projections (bounded, approved scope).
- Neighbor context expansion is bounded and explicit; no automatic background
  rebuild jobs.
- Embeddings / vector search / AI enrichment / MCP / Numchoke are out of scope.

## Recommendation

**Resolver Freeze Recommendation: READY_FOR_OWNER_APPROVAL**

All executable gates PASS. The Resolver is not frozen automatically; final
freeze requires explicit owner (Jeab) approval, recorded separately.
