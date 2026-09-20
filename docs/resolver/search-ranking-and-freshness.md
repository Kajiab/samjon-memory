# Resolver Search, Ranking, and Freshness

**Document ID:** SAMJON-RESOLVER-RANKING-001
**Status:** PLANNED
**Owner:** Samjon Memory Engineering
**Approver:** Jeab
**Last reviewed:** 2026-09-20

> Foundation C1 (search, ranking, freshness) is implemented and tested; this
> document records design, rules, and the remaining Foundation C2 work.

## 1. FTS5 Query Handling (Decision 10)

- User queries are sanitized and parsed before use.
- Raw user input is never passed directly into FTS MATCH syntax.
- Build a safe FTS5 query string from parsed tokens (identifiers, phrases, and
  safe prefixes), rejecting or escaping unsafe syntax (e.g. bare `*`, stray
  quotes, operators passed through untrusted paths).
- FTS5 features such as `matchinfo` are used only over normalized, safe input.

## 2. Deterministic Ranking

Ranking is a pure deterministic function over the snapshot and FTS5 BM25.
No randomness, no AI, and **no recency boost** (Decision 6).

### 2.1 Target Filtering (Decision 5)

- `memory` -> `standalone_memory`, `collection_memory`
- `collection` -> `collection`, `collection_with_selected_memories`
- `auto` -> all result types

### 2.2 Score Components

- Exact title or subject match (highest weight).
- Field weight: title > section_path > subject > raw_content.
- FTS5 BM25 rank over `normalized_text`.
- Alias boost when the query term equals a durable alias/vocabulary expansion.
- Tag boost when the subject has a matching durable tag.
- Scope penalty when the result scope does not match a provided scope filter
  (no penalty when no scope filter is given).

### 2.3 Collection Aggregation

- Collection score = best of its matching Sections plus Collection metadata.
- `collection_with_selected_memories` keeps only Sections above threshold,
  ordered by `collection_id + sequence_number`.

### 2.4 Tie-Break

Order by `(score DESC, memory_id ASC, collection_id ASC, sequence_number ASC)`
to guarantee determinism.

### 2.5 Ambiguity

When the top candidates are within an epsilon and differ by result type,
return `ambiguous` with the candidates.

## 3. Freshness (Decisions 3 and 7)

- Freshness is computed from the current Core version/checksum at query time.
- A stored derived freshness label (`projection_status`) is not authoritative
  by itself; it is validated against current Core.
- Freshness states:
  - `fresh` - active in Core and projection matches current version/checksum.
  - `stale` - active in Core but projection version/checksum is older.
  - `missing` - active in Core but no projection row.
  - `orphaned` - projected but not active/current in Core.

### 3.1 allow_stale Policy

- `allow_stale` defaults to `false`.
- Default behavior on a stale projection: return `PROJECTION_STALE`.
- `allow_stale=true`: may return IDs and evidence with
  `freshness=stale` and `incomplete=true`.
- Authoritative content is **always** loaded from Core.

## 4. Bounded Retrieval

- Results are capped by configured limits.
- Context expansion stays within the configured context budget.
