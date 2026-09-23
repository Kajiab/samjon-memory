# Resolver Search, Ranking, and Freshness

**Document ID:** SAMJON-RESOLVER-RANKING-001
**Status:** PLANNED
**Owner:** Samjon Memory Engineering
**Approver:** Jeab
**Last reviewed:** 2026-09-20

> Foundations C1 and C2 (search, ranking, freshness, and bounded context
> expansion) are implemented and tested; this document records the design/rules.

## 1. FTS5 Query Handling (Decision 10)

- User queries are sanitized and parsed before use.
- Raw user input is never passed directly into FTS MATCH syntax.
- The parser keeps only normalized tokens (`[0-9a-z<Thai>\s]`); quotes,
  parentheses, hyphens, colons, asterisks, Thai punctuation, and FTS operators
  typed by the user are stripped and never reach MATCH as raw syntax.
- Build a safe FTS5 query string from parsed tokens. Each token of at least
  `MIN_PREFIX_LENGTH` characters becomes a code-added prefix term `"tok"*`
  (the `*` is appended by the resolver after validation, never from the user).
  A FTS5 prefix term also matches the token itself (a token starts with itself),
  so the prefix term doubles as the exact-match term. Shorter tokens are matched
  exact-only. Multi-token queries are AND-ed together.
- Wildcard-only queries (bare `*`, punctuation-only) yield no tokens and are
  rejected as empty.
- `*`, `%`, `_` can never appear inside a normalized token, so LIKE-based
  fallback patterns cannot be injected either.
- Thai is a partly-spaced script: FTS5/`unicode61` treats a whole unspaced run
  as one token (`แมวไทย` -> one token), so a shorter term such as `แมว` is
  neither an exact token nor, when it appears mid-token, a prefix of it
  (`แมว` is an infix of `คู่มือแมวไทย`). To keep such facts reachable we add a
  bounded, **Thai-token-only** substring (infix) fallback over the already
  normalized snapshot for discovery, and score those infix hits at a lower
  weight than true prefixes. Restricting the infix fallback to Thai avoids
  English false positives (e.g. `son` matching `person`).

## 2. Deterministic Ranking

Ranking is a pure deterministic function over the snapshot and FTS5 BM25.
No randomness, no AI, and **no recency boost** (Decision 6).

### 2.1 Target Filtering (Decision 5)

- `memory` -> `standalone_memory`, `collection_memory`
- `collection` -> `collection`, `collection_with_selected_memories`
- `auto` -> all result types

### 2.2 Score Components

- Exact title matches rank highest, then exact content, then title prefix,
  then title infix, then content prefix, then content infix. Specifically:
  `exact_title > exact_content > title_prefix > title_substring >
  content_prefix > content_substring`; exact always outranks prefix/infix and
  a title hit outranks a content hit for the same term.
- Exact title or subject match (highest weight).
- Field weight: title > section_path > subject > raw_content.
- FTS5 BM25 rank over `normalized_text`.
- Alias boost when the query term equals a durable alias/vocabulary expansion.
- Tag boost when the subject has a matching durable tag.
- Scope penalty when the result scope does not match a provided scope filter
  (no penalty when no scope filter is given).

### 2.2.1 Match reasons

Each result reports deterministic `match_reasons`, such as:

- `token_match`, `subject_match`, `exact_subject_match`, `title_match`,
  `section_path_match`, `alias_match`, `vocabulary_match`, `tag_match`
- `exact_title_match` - a query token equals a title/section-path token.
- `title_prefix_match` - a query token is a leading prefix of a title/section-path token.
- `content_prefix_match` - a query token is a leading prefix of a raw-content token.
- `title_substring_match` / `content_substring_match` - a Thai query token
  appears as an infix (non-prefix) within a title/raw-content token.

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
