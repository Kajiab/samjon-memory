# Forget / Restore / Purge / Audit Retention — Design Spec

**Status:** DRAFT — PENDING REVIEW (do not implement before approval)
**Document ID:** SAMJON-LIFECYCLE-001
**Owner:** Samjon Memory Engineering

---

## 1. Purpose

Extend Core lifecycle management so that:

- `forget` remains a **soft delete** (status → `forgotten`).
- A forgotten Memory/Collection can be **restored** (brought back to `active`).
- A forgotten record can be **purged** — an administrative, hard-erasure workflow that
  removes content while keeping a minimal **tombstone** and its **lifecycle audit**.
- **Automatic purge is off by default**; purge is manual, guarded, and confirmable.
- Audit retention is explicit: lifecycle audit is archived, operational logs are
  not stored in Core audit, and audit gains **statistics + pagination**.

## 2. Scope

In scope: Core schema (proposed migration), CoreService operations, REST routes,
Portal UI, audit retention, config. `Resolver` is explicitly **out of scope**.

## 3. Lifecycle state machine

```
                 forget                      restore
 draft ─────────────┐                         ┌───────────▶ active
 active ────────────┼──▶ forgotten ───────────┤
 superseded ────────┘            │             └──(not purged only)
                                 │  purge (admin, ≥30d, "PURGE")
                                 ▼
                             tombstone (hard-erased, immutable)
```

Rules
- `forget`: `draft/active/superseded` → `forgotten` (soft delete; unchanged).
- `restore`: `forgotten` (and **not purged**) → **`draft`** (approved decision).
  Increments version. A restored **section** also increments its parent Collection version.
- `purge`: **only `forgotten`** records, **≥ 30 days** forgotten, confirmation
  `"PURGE"` required, **admin actor** required. Content erased; tombstone kept.
  A purged **section** increments its parent Collection version.
- A **purged** record is inert: cannot be restored, edited, activated, or reused
  (update/supersede/forget/activate/restore all reject purged entities).
- `automatic purge` is off. No scheduled purge job.

## 4. Tombstone contract

After purge the live row remains (FK-safe, no cascade) with:

- `memory_id` / `collection_id` (identity kept)
- `version` = final (pre-purge) version + 1 (purge is a lifecycle change)
- `content_checksum` = checksum of the original (purged) content
- `purged_at` / `purged_by` (purge time + actor)
- `raw_content` = `''` and `structured_value_json` = `NULL` (content hard-erased)
- a row in the new immutable `lifecycle_tombstone` archive (durable purge record)
- lifecycle audit rows (`memory_purge` / `collection_purge`) retained in `audit_log`

Referential integrity is preserved: purging does **not** delete the row, so
`memory.collection_id REFERENCES memory_collection` stays valid. We never cascade.

## 5. Requirements checklist

- [ ] Forget remains soft delete
- [ ] Restore for forgotten Memory/Collection
- [ ] Purge = administrative hard-erasure workflow
- [ ] Purge only for `forgotten` records
- [ ] Purge requires forgotten **≥ 30 days** (default)
- [ ] Automatic purge OFF
- [ ] Manual purge requires typing `PURGE` to confirm
- [ ] Purge erases `raw_content` + `structured_value`, keeps tombstone
      (ID, final version, checksum, purge time, lifecycle audit)
- [ ] Referential integrity preserved
- [ ] Collection version increments when a Section is restored or purged
- [ ] Resolver untouched
- [ ] Lifecycle audit archived (tombstone + retained audit_log)
- [ ] Operational logs NOT stored in Core audit
- [ ] No full content / request body / password / token in audit
- [ ] Audit statistics + pagination
- [ ] Cancel / page views create no audit

---

## 6. Proposed data-model changes (DRAFT — NOT APPLIED)

Adds **columns** (non-breaking `ALTER TABLE ... ADD COLUMN`, no table rebuild) to
`memory` and `memory_collection`:

| Table | New column | Purpose |
|-------|-----------|---------|
| `memory` | `forgotten_at TEXT` | set on forget, cleared on restore (purge-age basis) |
| `memory` | `purged_at TEXT` | set on purge (tombstone time) |
| `memory` | `purged_by TEXT` | admin actor who purged |
| `memory_collection` | `forgotten_at TEXT` | set on forget, cleared on restore |
| `memory_collection` | `purged_at TEXT` | set on purge |
| `memory_collection` | `purged_by TEXT` | admin actor who purged |

New **immutable archive table** `lifecycle_tombstone` (durable lifecycle-audit
archive + purge record):

```sql
CREATE TABLE IF NOT EXISTS lifecycle_tombstone (
    tombstone_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('memory','collection')),
    entity_id TEXT NOT NULL,
    final_version INTEGER NOT NULL,
    content_checksum TEXT,
    purged_at TEXT NOT NULL DEFAULT (datetime('now')),
    actor TEXT NOT NULL
);
```

Indexes:

```sql
CREATE INDEX IF NOT EXISTS idx_lt_entity ON lifecycle_tombstone(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_m_forgotten ON memory(forgotten_at);
CREATE INDEX IF NOT EXISTS idx_m_purged ON memory(purged_at);
CREATE INDEX IF NOT EXISTS idx_mc_forgotten ON memory_collection(forgotten_at);
CREATE INDEX IF NOT EXISTS idx_mc_purged ON memory_collection(purged_at);
```

Notes
- The existing `status CHECK (IN 'draft','active','superseded','forgotten')`
  already includes `forgotten` and no `purged` status is needed (purge is marked by
  `purged_at`, keeping the CHECK untouched).
- `raw_content` stays `NOT NULL`; purge writes `''` (NOT NULL satisfied, content
  erased). Truly NULLing would require a table rebuild — deemed unnecessary and
  proposed against.
- `forgotten_at` is **source of truth** for purge-age eligibility (not derived from
  audit), indexed for the purge-eligibility query.

### Proposed migration version

`CORE_SCHEMA_VERSION` → **`1.1.0`** (applied). `run_migrations` is now an ordered
`{version: [sql,...]}` map. **`forgotten_at` is backfilled from reliable audit
evidence only** (the most recent matching `*_forget` audit `created_at`); rows
without reliable evidence keep `NULL` and are purge-ineligible.

### Transactional erasure of related manual metadata (confirmed)

Memory purge erases content fields **and** subject-scoped manual metadata
(`durable_alias`, `durable_user_tag`, `manual_override`) **in a single CoreService
transaction** (`BEGIN`…`COMMIT` with `ROLLBACK` on error), writing a tombstone row
per erased related entity. Collection purge erases `title`, `summary`,
`source_reference` transactionally. No cascade deletes; `memory.collection_id`
FKs stay valid because purged rows are retained as tombstones.

---

## 7. CoreService operations (proposed signatures)

```python
def restore_memory(self, memory_id, expected_version=None, actor="system") -> dict
def restore_collection(self, collection_id, actor="system") -> dict
def purge_memory(self, memory_id, confirmation="", expected_version=None, actor="system") -> dict
def purge_collection(self, collection_id, confirmation="", expected_version=None, actor="system") -> dict
def audit_summary(self, entity_type=None, action=None, since=None) -> list[dict]
def get_audit_records(self, entity_id=None, entity_type=None, action=None, limit=50, offset=0)  # exists; pagination
```

Behaviors
- `restore_memory`: requires `status == 'forgotten'` and `purged_at IS NULL`;
  else `ValidationError`. Sets `status='active'`, `forgotten_at=NULL`,
  `version=version+1`, `updated_at=now`, audit `memory_restore`. If the memory is a
  collection section (`collection_id` set), bump the parent Collection version and
  audit `collection_structure_change`.
- `restore_collection`: requires `status == 'forgotten'` + not purged; sets
  `status='active'`, clears `forgotten_at`, `version=version+1`, audit
  `collection_restore`. (Sections are not auto-restored.)
- `purge_memory`: requires admin `actor`; `status=='forgotten'`; not already purged;
  age since `forgotten_at` >= `purge_min_age_days`; `confirmation == "PURGE"`.
  Otherwise stable error (`ValidationError` / `PermissionDenied`). Erases
  `raw_content=''`, `structured_value_json=NULL`; sets `purged_at`, `purged_by`;
  `version=version+1`; audits `memory_purge`; writes a `lifecycle_tombstone` row;
  bumps parent Collection version (section case).
- `purge_collection`: same guards; erases content, `purged_at`, audit
  `collection_purge`, tombstone row. **Does not cascade** to sections.
- Stable errors: reuse `NotFound`, `ValidationError`, `Conflict`,
  `VersionConflict`; use `PermissionDenied` for non-admin purge.

## 8. REST routes (proposed)

```text
POST /api/v1/core/memories/{memory_id}/restore
POST /api/v1/core/collections/{collection_id}/restore
POST /api/v1/core/memories/{memory_id}/purge        # body: confirmation, expected_version
POST /api/v1/core/collections/{collection_id}/purge # body: confirmation, expected_version
GET  /api/v1/core/audit/stats                       # audit statistics
```

Security: purge/restore require the **admin** service token; others follow the
existing `actor` header pattern. All documented in OpenAPI.

## 9. Portal UI (proposed)

- **Memory detail** when `status == 'forgotten'` (and not purged):
  - **Restore** button → `POST /portal/memories/{id}/restore` (HTTP Basic + Origin).
  - **Purge** card: "type `PURGE` to confirm" input, disabled submit until input
    equals `PURGE` (server validates too), admin-only. Shows purge-eligibility
    date when < 30 days.
- **Collection detail** when `status == 'forgotten'`: same Restore + Purge pattern.
- **Collection section rows**: a forgotten section shows **Restore**; restoring or
  purging a section surfaces the parent Collection version bump.
- **Audit page**: add a statistics/summary block + keep pagination (Previous/Next).
- Cancel remains a navigation link; **page views / Cancel create no audit** (GET
  routes never audit — already the rule, reinforced by tests).

---

## 10. Audit retention rules

- Lifecycle audit (create/update/supersede/forget/restore/purge/activation) is
  retained in `audit_log` and archived via `lifecycle_tombstone` for purged records.
- Operational logs are **not** written to Core audit (no ingestion — out of scope).
- `details_json` stays **sanitized**: never full content, request body, password,
  or token (existing `sanitize_for_audit`).
- New `audit_summary()` returns counts (e.g. by `action`, by `entity_type`, for an
  optional `since` window); `get_audit_records` already supports `limit`/`offset`
  pagination.

## 11. Configuration (proposed, in `config.py`)

```text
SAMJON_LIFECYCLE_PURGE_MIN_AGE_DAYS        # default 30
SAMJON_LIFECYCLE_AUTOMATIC_PURGE_ENABLED   # default "false"
SAMJON_LIFECYCLE_PURGE_CONFIRMATION        # default "PURGE"
```

`PURGE_CONFIRMATION = "PURGE"` also exposed from `constants.py`.

---

## 12. Impact analysis (for review)

| Area | Impact | Mitigation |
|------|--------|------------|
| Schema | +3 columns × 2 tables, +1 table, +5 indexes; bump schema 1.1.0 | Non-breaking ADD COLUMN; no table rebuild; new table only |
| Migration runner | `run_migrations` needs an ordered version→SQL map | Refactor to explicit migration list; keep idempotency tests green |
| Existing data | existing forgotten rows get no `forgotten_at` (NULL) → purge ineligible until re-forgotten | Document; optional backfill from audit on migration |
| `memory` CHECK | unchanged (`forgotten` already allowed) | none |
| `raw_content NOT NULL` | purge writes `''` (not NULL) | no rebuild; content erased |
| FK integrity | no cascade; rows kept | tombstone model keeps FKs valid |
| CoreService | +5 public methods, +2 private helpers | thin; reuse existing patterns |
| REST API | +5 endpoints (new, additive) | OpenAPI regeneration required |
| Portal | memory/collection detail + audit page changes | server-rendered, Basic + Origin |
| Resolver | none | unchanged |
| Docs | api-contract, OpenAPI, status, AGENTS.md | update post-implementation |
| Release-blocking | purge admin-only + confirm + >=30 days; no auto purge | enforced by tests |

**Nothing is applied in this change.** Schema, migration, `CORE_SCHEMA_VERSION`,
constants, services, routes, Portal, and docs remain as-is until review approval.

---

## 13. Test plan (see `tests/test_lifecycle.py`)

1. Restore forgotten Memory → active, version+1, audit `memory_restore`.
2. Restore forgotten Collection → active, version+1, audit `collection_restore`.
3. Restore rejects non-forgotten (draft/active/superseded). (ValidationError)
4. Restore/purge a forgotten **section** bumps its parent Collection version.
5. Purge rejects non-forgotten. (ValidationError)
6. Purge rejects age < 30 days. (ValidationError)
7. Purge rejects wrong confirmation (≠ `PURGE`). (ValidationError)
8. Purge rejects non-admin actor. (PermissionDenied)
9. Purge erases content, sets `purged_at`, keeps id/version/checksum, creates tombstone.
10. Purge keeps lifecycle audit (`memory_purge`) + tombstone archive.
11. Restore rejects a purged record. (ValidationError)
12. `automatic_purge_enabled` default False; no purge-all job.
13. `audit_summary()` returns counts; `get_audit_records` pagination (limit/offset).
14. Audit details carry no full content / password / token.
15. Cancel / page view (GET) creates no audit record.
16. Referential integrity: after section purge, `memory_collection` intact.
17. REST routes registered in OpenAPI.
18. Portal: forgotten shows Restore + Purge; active does not; purge server-validates `PURGE`.

## 14. Resolved decisions (was "Open questions")

- **Collection purge** erases `title`, `summary`, `source_reference` (user content),
  keeping subject/identity/checksum. **Memory purge** erases `title`, `section_path`,
  `raw_content`, `structured_value_json`, and subject-scoped `durable_alias` /
  `durable_user_tag` / `manual_override`, all transactionally.
- **Restore** always returns Memory/Collection to **`draft`**.
- **`forgotten_at` backfill** uses reliable audit evidence only; rows without it stay
  `NULL` and are purge-ineligible.
- **Purged entities are inert** (no restore/edit/activate/reuse).
- Audit is **append-only** in V1.1 with pagination + indexes and **no automatic
  deletion**; filters: `action`, `entity_type`, `entity_id`, `since`, `until`.

## 15. Change control

**IMPLEMENTED (V1.1).** Applied: `1.1.0` migration, `CORE_SCHEMA_VERSION` bump,
CoreService restore/purge + audit summary/filters, REST routes, Portal (Restore /
Purge with `PURGE` confirmation, purged-inert UI, audit stats + pagination),
OpenAPI regenerated, and acceptance tests in `tests/test_lifecycle.py` /
`tests/test_migration.py`. Full suite: **144 passed**.