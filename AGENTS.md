# AGENTS.md: Samjon Memory Developer Context

**Document ID:** SAMJON-MEMORY-AGENT-001
**Version:** 2.1.0
**Status:** Canonical repository instruction
**Owner:** Samjon Memory Engineering
**Approver:** Jeab
**Last reviewed:** 2026-09-18
**Repository:** `samjon-memory`

---

## 1. Purpose

This file is the mandatory working guide for Cline and other coding agents when reading, designing, editing, testing, or reviewing Samjon Memory.

Read this file before changing the repository.



This repository-local `AGENTS.md` is sufficient for ordinary implementation
tasks.

Do not search parent directories for umbrella instructions.

Cross-project rules are read only in a separate integration task.

When implementation, tests, schemas, or canonical documents conflict, report the exact conflict before changing externally visible behavior.

---

## 2. Project Summary

Samjon Memory is the durable household knowledge backend and deterministic memory resolver.

It stores explicit, structured, text-based knowledge such as:

- User preferences.
- Household vocabulary and aliases.
- Device and location notes.
- Music preferences.
- Plant, inventory, and equipment knowledge.
- User-confirmed facts.

Samjon Memory uses two physically separate SQLite databases:

```text
samjon_core.sqlite
= authoritative, durable, backup-critical facts

samjon_resolver.sqlite
= derived, disposable, rebuildable search projections
```

Core and Resolver may run in one service process on REST port `8100`, but their database files, schemas, migrations, repositories, backup policies, and lifecycle remain separate.

---

## 3. Canonical Architecture

```text
Numchoke or another approved client
                |
                v
        Samjon Home MCP
          Samjon module
                |
                v
   Samjon Memory REST API :8100
                |
        +-------+--------+
        |                |
        v                v
 Core Memory          Resolver
 authoritative        derived
 samjon_core.sqlite   samjon_resolver.sqlite
```

Projection flow is one-way:

```text
Core service/API
    -> projection builder
    -> Resolver database
```

Rules:

- Resolver must not write facts into Core.
- External services must not open either SQLite file directly.
- Resolver may return matches and evidence, but authoritative fact content is loaded from Core.
- Resolver may be deleted and rebuilt without losing authoritative information.
- Samjon Memory does not implement MCP, Numchoke conversation logic, Numchai playback, Home Assistant control, or Numsub rules.

---

## 4. Development Phases

### 4.1 Phase 1: Core Memory V1

Core V1 includes:

- Typed configuration.
- Core SQLite connection and explicit migrations.
- Standalone Memory lifecycle.
- Collection and Collection Memory lifecycle.
- Idempotent creation.
- Deterministic metadata query.
- Versioning and supersession.
- Guarded forget behavior.
- Sensitive-data rejection.
- Audit records.
- Backup and isolated restore.
- Core REST API and OpenAPI.
- Core Web Portal.

Core V1 excludes:

- Resolver database.
- FTS5.
- Semantic search.
- AI enrichment.
- Embeddings or vector search.
- MCP implementation.

### 4.2 Core Freeze Gate

Core V1 may be frozen only when:

- Core migrations and migration idempotency pass.
- Core API tests pass.
- Memory and Collection lifecycle tests pass.
- Independent Collection Memory editing is proven.
- Idempotency tests pass.
- Version and supersession tests pass.
- Sensitive-data policy tests pass.
- Core Portal behavior and security tests pass.
- Backup and isolated restore pass.
- OpenAPI matches runtime behavior.
- Canonical documentation matches the implementation.
- Known limitations are explicit.
- Owner approval is recorded.

Freeze means incompatible schema or API changes require a new version. It does not prohibit bug fixes, security fixes, tests, or documentation corrections.

### 4.3 Phase 2: Resolver V1

Resolver implementation begins only after Core V1 is frozen and contains representative data.

Resolver V1 may include:

- Separate Resolver SQLite connection and migrations.
- Projection builder reading Core through an approved service or API boundary.
- Normalized text and FTS5.
- Derived aliases and tags.
- Vocabulary resolution.
- Deterministic ranking and match reasons.
- Collection-level and Memory-level intent search.
- Bounded context retrieval.
- Projection freshness.
- Selective rebuild.
- Atomic full rebuild and rollback.
- Resolver Portal pages.

### 4.4 Phase 3: Samjon Home MCP Module

After Core and Resolver APIs reach final-test quality:

```text
Final Samjon Memory API
    -> thin Samjon Home MCP module
    -> module tests
    -> live compatibility tests
    -> consumer tests
    -> contract freeze
    -> publish to home-ai-contracts
```

The MCP module belongs in the Samjon Home MCP repository, not here.

---

## 5. Core Invariants

### 5.1 Core is authoritative

`samjon_core.sqlite` is the source of truth for durable Memory.

Core owns:

- Fact identity.
- Raw user-confirmed content.
- Structured values.
- Subject, type, and scope.
- Source and provenance.
- Durable manual aliases, vocabulary, tags, and overrides.
- Version and supersession.
- Lifecycle status.
- Idempotency records.
- Audit records.

Core facts are never silently overwritten.

### 5.2 Resolver is derived

`samjon_resolver.sqlite` stores rebuildable projections only.

Derived content may include:

- Normalized text.
- FTS5 documents.
- Derived aliases and tags.
- Ranking metadata.
- Projection state.
- Future approved AI enrichment or embeddings.

Anything that must survive a complete Resolver rebuild belongs in Core.

### 5.3 REST is the external boundary

External systems use documented REST APIs.

The Portal may call the same Core application-service operations used by REST handlers. It does not need to make an HTTP request back into the same process.

Portal handlers must not access SQLite connections, repositories, arbitrary SQL, or database paths directly.

### 5.4 Conversation history is not Memory

Conversation history is not stored automatically as durable Memory.

Durable Memory is created only when:

- The user explicitly requests it.
- An approved workflow confirms it.
- Subject and source are recorded.

### 5.5 Retrieval returns evidence

Resolver results must be bounded and identify:

- Memory or Collection identity.
- Core version.
- Projected Core version.
- Projection freshness.
- Score.
- Match reasons.
- Conflicts.
- Result type.

Numchoke owns the final conversational answer.

---

## 6. Explicit Non-Goals

Do not add without an accepted ADR:

- MCP transport or MCP tool registration.
- Direct OpenRouter or LLM calls in Core.
- Automatic Memory extraction from every conversation.
- Vector database or embeddings.
- Autonomous fact deletion.
- Direct database access from another service.
- Browser-side SQLite access.
- Raw Home Assistant state mirroring.
- Numchai playback logic.
- Numsub high-frequency event ingestion.
- Credentials, tokens, private keys, security codes, recovery keys, biometrics, or raw audio as Memory.
- Public internet exposure of the Portal.
- Portal user registration or a users table.

---

## 7. Authority Order

When sources conflict, use this order:

1. Executable migration, API, Portal, security, backup, restore, projection, and retrieval tests.
2. Current implementation.
3. Generated OpenAPI and schema exports.
4. Accepted ADRs.
5. Canonical documentation.
6. Supporting documentation.
7. Historical reports and drafts.

Do not let a historical plan override current executable evidence.

---

## 8. Repository Structure

```text
samjon-memory/
├── README.md
├── AGENTS.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── src/
│   └── samjon_memory/
│       ├── config.py
│       ├── constants.py
│       ├── errors.py
│       ├── api/
│       ├── core/
│       │   ├── database.py
│       │   ├── migration.py
│       │   ├── models.py
│       │   ├── repositories.py
│       │   ├── service.py
│       │   └── main.py
│       ├── resolver/
│       │   └── future implementation
│       ├── portal/
│       │   ├── router.py
│       │   ├── pages.py
│       │   └── static/
│       ├── security/
│       ├── observability/
│       └── shared/
├── tests/
├── docs/
├── artifacts/
└── scripts/
```

Use `src/samjon_memory/` as the top-level Python package. Do not create a separate `src/samjon_core/` application.

---

## 9. Database Configuration

Expected configuration:

```text
SAMJON_CORE_DATABASE_PATH
SAMJON_RESOLVER_DATABASE_PATH
```

Rules:

- Paths are configurable.
- Local development may use `./data/samjon_core.sqlite`.
- Container deployment may explicitly use `/data/samjon_core.sqlite`.
- Parent directories may be created only from trusted application configuration.
- Each database has independent schema metadata and migrations.
- Foreign keys are enabled.
- WAL and busy timeout are deliberate and tested.
- Resolver replacement must not affect Core.
- API or Portal input must never supply a database path.

---

## 10. Core Data Model

Core supports standalone Memories and Collections.

### 10.1 Memory

Required concepts:

```text
memory_id
collection_id, nullable
sequence_number, nullable
subject
memory_type
scope
title, nullable
section_path, nullable
raw_content
structured_value_json, nullable
source
language
status
version
supersedes_memory_id, nullable
content_checksum
created_at
updated_at
```

Memory statuses:

```text
draft
active
superseded
forgotten
```

### 10.2 Collection

Required concepts:

```text
collection_id
subject
collection_type
scope
title
summary
language
source
source_reference
status
version
supersedes_collection_id
expected_item_count
content_checksum
created_at
updated_at
```

Collection statuses:

```text
draft
active
superseded
forgotten
```

### 10.3 Durable manual metadata

Core owns durable information that must survive Resolver rebuild:

- User-confirmed aliases.
- User-confirmed vocabulary.
- Durable user tags.
- Manual corrections and overrides.

AI-derived aliases, semantic tags, ranking state, FTS5, and embeddings belong in Resolver.

---

## 11. Memory versus Collection Decision Rule

The creating user or approved client explicitly chooses:

- Standalone Memory, or
- Collection containing independently managed Memories.

Core must not infer or silently change the storage type.

Use Standalone Memory when content is one cohesive fact or note that remains understandable independently.

Use Collection when content contains ordered or separately maintained sections sharing a title, subject, source, or lifecycle.

Content length is a safety constraint, not the primary semantic decision.

Core may:

- Validate the selected structure.
- Recommend a Collection.
- Detect headings and safe boundaries for preview.
- Reject oversized standalone content.
- Report structural inconsistencies.

Core must not silently:

- Split content.
- Merge Memories.
- Summarize or reinterpret facts.
- Convert Memory to Collection.
- Convert Collection to Memory.

AI may propose a Collection plan, but the original content, boundaries, titles, order, and resulting sections must remain reviewable. Activation requires explicit approval.

---

## 12. Collection Lifecycle and Independent Editing

A new Collection starts as `draft`.

Resolver may project only active Collections and active Memories.

Each Memory inside a Collection has its own:

- Memory ID.
- Version.
- Lifecycle.
- Content.
- Structured value.
- Source metadata.
- Audit history.
- Edit operation.

Editing one Collection Memory must not rewrite the complete Collection.

A Memory content change increments that Memory version.

A structural or assembled-view change increments Collection version.

Structural changes include:

- Adding or removing a Memory.
- Forgetting a Memory.
- Moving a Memory.
- Reordering sections.
- Changing Collection title or summary.
- Changing Collection lifecycle status.

`collection_id` plus `sequence_number` is the canonical section order.

Unchanged Memories retain IDs, versions, and content.

---

## 13. Core API V1

Canonical Core routes include:

```text
GET  /health
GET  /ready
GET  /api/v1/capabilities

POST /api/v1/core/memories
GET  /api/v1/core/memories/{memory_id}
PATCH /api/v1/core/memories/{memory_id}
POST /api/v1/core/memories/query
POST /api/v1/core/memories/{memory_id}/supersede
POST /api/v1/core/memories/{memory_id}/forget

POST /api/v1/core/collections
GET  /api/v1/core/collections/{collection_id}
PATCH /api/v1/core/collections/{collection_id}
GET  /api/v1/core/collections/{collection_id}/memories
POST /api/v1/core/collections/{collection_id}/memories
PUT  /api/v1/core/collections/{collection_id}/order
POST /api/v1/core/collections/{collection_id}/activate
GET  /api/v1/core/collections/{collection_id}/validate
```

Exact paths and schemas are generated from current implementation.

Core query is deterministic metadata filtering, not semantic search.

Every mutation defines authentication, validation, limits, stable errors, expected-version behavior, idempotency where applicable, and audit behavior.

---

## 14. Content Limits

Use typed and configurable limits.

Initial defaults:

```text
raw_content: 16,384 Unicode characters
raw_content: 65,536 UTF-8 bytes
Collection title: 500 characters
Collection summary: 8,192 characters
Memory title: 500 characters
Alias: 200 characters
Tag: 80 characters
Aliases per Memory: 20
Tags per Memory: 30
```

Do not silently truncate.

Oversized content is rejected with a stable validation error.

---

## 15. Resolver Contract

Resolver must search both:

- Collection-level projections.
- Memory-level projections.

Default target:

```text
auto
```

Resolver result types:

```text
standalone_memory
collection_memory
collection
collection_with_selected_memories
ambiguous
no_match
```

Resolver must not split, merge, reorder, summarize as replacement, or rewrite Core records.

A Collection result is bounded. It does not automatically include every Memory.

Context expansion may include neighboring sections only when needed to preserve meaning and within the configured context budget.

---

## 16. Core Portal Purpose and Architecture

Samjon Memory includes a human-facing Core Portal for inspecting and managing authoritative facts.

Route:

```text
/portal/
```

Canonical architecture:

```text
Browser
    -> HTTP Basic authenticated server-rendered Portal
    -> Core application-service operations
    -> Core repositories
    -> samjon_core.sqlite
```

The Portal is not a direct database editor.

Portal handlers must not access:

- SQLite connections.
- Repositories directly.
- Arbitrary SQL.
- Database paths.

Static assets are limited to non-sensitive CSS, icons, and progressive-enhancement JavaScript.

Do not maintain a second SPA with separate authentication, token storage, payload logic, or duplicate CRUD forms.

---

## 17. Core Portal Authentication Baseline

### 17.1 Exactly one configured Portal user

Core Portal V1 supports exactly one configured household administrator account.

Configuration:

```text
SAMJON_PORTAL_USERNAME
SAMJON_PORTAL_PASSWORD
SAMJON_PORTAL_ALLOWED_ORIGINS
```

There is:

- No users table.
- No user registration.
- No user-management UI.
- No multiple Portal accounts.
- No read-only Portal role.
- No password storage in SQLite.

Changing the Portal account requires changing trusted configuration and restarting the service.

### 17.2 Approved authentication model

Core Portal V1 uses FastAPI HTTP Basic Authentication.

All Portal application routes require valid HTTP Basic credentials:

```text
/portal/
/portal/memories
/portal/memories/*
/portal/collections
/portal/collections/*
/portal/audit
```

Missing or invalid credentials return:

```text
401 Unauthorized
WWW-Authenticate: Basic
```

Use constant-time credential comparison where practical.

### 17.3 Credential handling

Portal credentials must:

- Come from trusted configuration.
- Have no production default.
- Use synthetic values in tests.
- Never appear in HTML.
- Never appear in JavaScript.
- Never appear in URLs.
- Never appear in logs.
- Never appear in audit records.
- Never appear in capability responses.
- Never be committed to source control.

REST API service/admin tokens remain separate from Portal credentials.

### 17.4 Explicitly deferred features

Core Portal V1 must not implement:

- Custom login page.
- Signed Portal sessions.
- Portal session cookies.
- Server-side session storage.
- Login nonce.
- Logout tracking.
- Custom HMAC session tokens.
- Multiple Portal users or roles.
- OAuth, OpenID Connect, or external identity providers.

These require a separate approved security revision.

### 17.5 Static assets

`/portal/static/*` may remain public only when assets contain no credentials, tokens, Memory content, user data, private configuration, or database information.

### 17.6 Mutation Origin validation

Every Portal mutation must:

- Require valid HTTP Basic credentials.
- Validate Origin against `SAMJON_PORTAL_ALLOWED_ORIGINS`.
- Preserve expected-version validation.
- Preserve Core validation and lifecycle rules.
- Preserve audit behavior.

Development origins may include only exact configured values such as:

```text
http://localhost:8100
http://127.0.0.1:8100
```

Origin comparison includes exact scheme, host, and port.

Do not allow all HTTPS origins.

Custom session-based CSRF tokens are not required because Core Portal V1 does not use cookie-session authentication. Exact Origin validation and explicit HTTP Basic authentication are the approved baseline mutation protections.

### 17.7 Deployment limits

Plain HTTP Basic is approved only for:

- Localhost development.
- An explicitly trusted household LAN.

Default local bind:

```text
127.0.0.1
```

Binding to `0.0.0.0` requires explicit operator action.

Direct public internet exposure and router port forwarding are prohibited.

Broader exposure requires HTTPS, an authenticated reverse proxy, trusted-host validation, and reviewed deployment configuration.

---

## 18. Core Portal Capabilities

The Core Portal should support:

- Core health, readiness, schema version, and capability display.
- Memory list, detail, pagination, and filters.
- Standalone Memory creation and editing.
- Guarded supersede and forget.
- Collection creation as draft.
- Collection metadata editing.
- Adding independently managed Collection Memories.
- Editing one Collection Memory without rewriting the Collection.
- Section ordering.
- Assembled Collection preview.
- Collection validation and explicit activation.
- Audit history.
- Clear validation and version-conflict feedback.

Resolver UI is not implemented before Resolver V1.

---

## 19. Portal Cancel Behavior

The canonical Portal is server-rendered.

Cancel controls must be navigation links or non-submit buttons.

Approved navigation:

```text
Create Memory Cancel -> /portal/memories
Create Collection Cancel -> /portal/collections
Edit Memory Cancel -> Memory detail
Edit Collection Cancel -> Collection detail
```

Cancel must:

- Send no mutation.
- Create no record.
- Create no audit event.
- Increment no version.
- Preserve existing content.
- Preserve Collection ordering.

Obsolete SPA dialogs and duplicate form implementations must be removed.

If an approved dialog remains, Cancel uses `type="button"`, resets transient state, clears transient errors, closes the dialog, restores focus, and supports Escape safely.

---

## 20. Portal Capability Reporting

The capability endpoint describes actual proven behavior.

Expected Portal shape after tests pass:

```json
{
  "portal": {
    "implemented": true,
    "architecture": "server_rendered",
    "authentication": "http_basic",
    "users_supported": 1,
    "roles": ["admin"],
    "session_cookie": false,
    "custom_login_page": false,
    "origin_validation": true,
    "local_network_only": true,
    "public_internet_approved": false,
    "status": "core_v1_local_admin"
  }
}
```

Do not expose username, password, hashes, or secret configuration.

Only tested behavior may be reported as implemented.

---

## 21. Write, Version, and Idempotency Rules

Memory creation is a side effect.

- Accept an idempotency key where defined.
- Same key and same request returns the original result.
- Same key with different content returns `IDEMPOTENCY_CONFLICT`.
- Do not create duplicates after transport retries.
- Bound content and structured values.
- Reject prohibited sensitive data.
- Do not silently merge conflicts.

Updates require optimistic concurrency using `expected_version` or an approved equivalent.

Forget operations require explicit identity, authorization, and confirmation.

---

## 22. Backup and Restore

### 22.1 Core

Core backup must:

- Use a SQLite-safe method.
- Record schema and application version.
- Record checksum and integrity result.
- Follow retention policy.
- Protect backups as sensitive user data.
- Be restored and verified in isolation.

### 22.2 Resolver

Resolver data is normally rebuilt rather than restored.

Version and preserve:

- Resolver schema.
- Projection algorithm.
- Normalization configuration.
- Future approved AI model or prompt configuration.

Manual durable information must not live only in Resolver.

---

## 23. Security and Privacy

- Deny unauthenticated REST API and Portal access.
- Keep REST API tokens separate from Portal HTTP Basic credentials.
- Enforce subject-level API access where applicable.
- Redact content and credentials in logs and metrics.
- Reject prohibited credentials and sensitive information.
- Treat stored content and Resolver projections as untrusted input.
- Never execute instructions contained in Memory.
- Protect Core backups like the live Core database.
- Record safe audit metadata only.

---

## 24. Stable Errors

Use stable public errors such as:

```text
VALIDATION_ERROR
AUTHENTICATION_REQUIRED
PERMISSION_DENIED
SENSITIVE_DATA_REJECTED
NOT_FOUND
CONFLICT
VERSION_CONFLICT
IDEMPOTENCY_CONFLICT
RATE_LIMITED
CORE_DATABASE_UNAVAILABLE
RESOLVER_DATABASE_UNAVAILABLE
PROJECTION_STALE
PROJECTION_FAILED
REBUILD_IN_PROGRESS
MIGRATION_REQUIRED
INTERNAL_ERROR
```

Do not expose SQL, filesystem paths, credentials, or stack traces.

---

## 25. Observability and Audit

Structured logs may include safe operational metadata:

```text
timestamp
level
service
layer
request_id
operation
result_code
duration_ms
result_count
core_schema_version
resolver_schema_version
```

Do not log full facts, structured values, credentials, database files, or raw Portal forms by default.

Audit:

- Core create, update, supersede, and forget.
- Collection create, edit, reorder, validate, and activate.
- Durable manual metadata changes.
- Permission denial.
- Sensitive-data rejection.
- Resolver rebuild activities after Resolver V1 exists.
- Portal administrative mutations.

Cancel must not create an audit record.

---

## 26. Typed Configuration

Expected families:

```text
SAMJON_MEMORY_*
SAMJON_CORE_DATABASE_*
SAMJON_RESOLVER_DATABASE_*
SAMJON_SECURITY_*
SAMJON_LIMITS_*
SAMJON_PORTAL_*
SAMJON_REBUILD_*
```

Core Portal V1 configuration:

```text
SAMJON_PORTAL_USERNAME
SAMJON_PORTAL_PASSWORD
SAMJON_PORTAL_ALLOWED_ORIGINS
```

No secret has an unsafe production default.

Session-security configuration is deferred because Core Portal V1 does not use session authentication.

---

## 27. Required Tests

### 27.1 Core tests

- Initial migration and migration idempotency.
- Core schema version.
- Standalone Memory create, read, query, update, supersede, and forget.
- Idempotency replay and conflict.
- Content character and UTF-8 byte limits.
- Collection create, edit, order, validate, and activate.
- Independent Collection Memory editing.
- Expected-version conflict.
- Subject isolation.
- Sensitive-data rejection.
- Audit behavior.
- Core backup and isolated restore.
- OpenAPI drift.

### 27.2 Portal tests

- Missing credentials return `401`.
- `WWW-Authenticate: Basic` is present.
- Invalid username is rejected.
- Invalid password is rejected.
- Valid credentials allow Portal access.
- Memory, Collection, and audit routes require credentials.
- Mutation without credentials is rejected.
- Unapproved Origin is rejected.
- Approved Origin succeeds.
- Credentials are absent from HTML, JavaScript, URLs, logs, audit, and capabilities.
- Memory and Collection Portal workflows pass.
- Independent Collection Memory editing passes.
- Cancel creates no Memory, Collection, mutation, version increment, or audit event.
- XSS-safe rendering passes.
- Pagination and response limits pass.
- Static assets contain no sensitive configuration.

### 27.3 Resolver tests

Resolver tests begin only in Phase 2 and include migrations, projection, FTS5, aliases, vocabulary, ranking, freshness, selective rebuild, atomic rebuild, rollback, bounded context, and Core preservation.

All normal tests use temporary databases and synthetic credentials.

---

## 28. Editing and Tool Policy

- Prefer small, controlled patches.
- Use Cline native file editing tools for source changes.
- Do not use `python -c` to generate multiline patch scripts.
- Do not create `patch.py`, `fix_*.py`, or generator scripts for ordinary edits.
- Do not repeat identical failed shell-edit commands.
- Do not use `git reset --hard` to recover from an interrupted task.
- Inspect `git status` and `git diff` before resuming interrupted work.
- Preserve unrelated valid changes.
- Keep Core and Resolver SQL separate.
- Keep API and Portal handlers thin.
- Do not place Resolver search data in Core.
- Do not add LLM dependencies to Core.
- Do not let Portal bypass Core service policy.
- Add regression tests for bug fixes.

---

## 29. Task Scope for Cline

The currently open repository is the complete working scope.

Use relative paths only.

Do not inspect parent directories or sibling repositories during
repository-local implementation tasks.

Default editable scope:

- `src/`
- `tests/`
- `docs/`
- repository configuration files required by the task

Cross-project integration requires a separate task and workspace.

---

## 30. Documentation Structure and Sync

Canonical documents include:

```text
docs/DOCUMENT_INDEX.md
docs/SAMJON_MEMORY_STATUS.md
docs/current/architecture.md
docs/current/capabilities.md
docs/current/data-ownership.md
docs/current/web-portal.md
docs/core/data-model.md
docs/core/memory-lifecycle.md
docs/core/api-contract.md
docs/core/migration-policy.md
docs/core/backup-restore.md
docs/api/openapi.json
docs/api/error-contract.md
docs/security/privacy-policy.md
docs/security/portal-security.md
docs/operations/deployment.md
docs/operations/core-backup-restore.md
docs/operations/troubleshooting.md
docs/integration/home-assistant-smoke-test.md
```

After externally visible behavior changes, update affected canonical documentation.

Detailed project status:

`docs/SAMJON_MEMORY_STATUS.md`

Do not inspect or update umbrella status documents during repository-local
tasks.

Do not create a project-local `PROJECT_STATUS.md` under the repository root or docs directory.

Historical test evidence belongs under `artifacts/reports/`.

---

## 31. Release Blocking Conditions

Block Core release when:

- External systems or Portal access Core SQLite directly.
- Conversation history is stored automatically.
- Sensitive credentials can be stored as Memory.
- Writes are non-idempotent under retries.
- Core migrations lack tests.
- Core backup and restore are untested.
- Core API/OpenAPI drift exists.
- Portal application routes lack HTTP Basic authentication.
- Portal credentials are hard-coded or exposed.
- Portal mutations accept unapproved Origins.
- Cancel performs a mutation or creates audit.
- Duplicate SPA and server-rendered editing paths remain active.
- Capabilities claim session, role, CSRF, authentication, or CRUD behavior that is not implemented.

Block Resolver release when:

- Resolver modifies Core facts.
- Durable manual information exists only in Resolver.
- Resolver cannot be deleted and rebuilt.
- Rebuild exposes a half-built index.
- Projection freshness is hidden.
- Retrieval is unbounded or unexplained.
- Resolver migrations or rebuild tests fail.

Block all releases when secrets or full fact content appear in logs by default, or documentation claims more than tests prove.

---

## 32. Definition of Done

### 32.1 Core V1

Core V1 is done when:

- Schema and API are versioned.
- Memory and Collection lifecycle operations are tested.
- Independent Collection Memory editing is tested.
- Idempotency, authorization, limits, and audit are tested.
- Core Portal supports safe inspection and editing.
- Portal is protected by HTTP Basic Authentication.
- Portal mutations validate exact Origin.
- Credentials are absent from rendered and logged content.
- Cancel has no mutation or audit side effects.
- Backup and isolated restore pass.
- OpenAPI and canonical documentation match implementation.
- Owner approval records the freeze.

### 32.2 Resolver V1

Resolver V1 is done when:

- Resolver database is physically separate and rebuildable.
- Projection uses frozen Core data.
- Collection-level and Memory-level search work from one intent.
- FTS5, vocabulary, aliases, tags, ranking, and freshness are tested.
- Atomic rebuild and rollback pass.
- Resolver Portal exposes evidence and guarded rebuild operations.
- Resolver recreation leaves Core unchanged.
- OpenAPI and canonical documentation match implementation.

---

## 33. Initial Development Sequence

```text
Phase 1: Core
1. Define Core schema and migrations.
2. Implement Memory and Collection lifecycle.
3. Implement idempotency, audit, limits, and sensitive-data policy.
4. Implement API and OpenAPI.
5. Implement server-rendered Core Portal.
6. Protect Portal with one-user HTTP Basic Authentication.
7. Validate exact mutation Origins.
8. Test Cancel as a no-side-effect action.
9. Validate backup and isolated restore.
10. Freeze Core with owner approval.

Phase 2: Resolver
11. Define Resolver projection schema and migrations.
12. Project frozen Core data.
13. Implement Collection and Memory intent search.
14. Implement FTS5, ranking, evidence, and freshness.
15. Implement selective and atomic full rebuild.
16. Implement Resolver Portal.
17. Freeze Resolver.

Phase 3: MCP
18. Finalize Samjon Memory API evidence.
19. Build the thin Samjon module in Samjon Home MCP.
20. Run compatibility and consumer tests.
21. Publish approved contract.
```

---

## 34. Final Engineering Principles

```text
Core stores authoritative facts.
Resolver stores derived search projections.
Core is backup-critical.
Resolver is disposable and rebuildable.
Manual durable knowledge belongs in Core.
AI may enrich Resolver but may not rewrite Core.
Creator chooses Memory or Collection.
Collection Memories are independently editable.
The Portal never edits SQLite directly.
Core Portal V1 has one configured Admin user.
Core Portal V1 uses HTTP Basic Authentication.
Custom Portal sessions are deferred.
Portal mutations validate exact Origin.
Cancel has no side effects.
Core freezes before Resolver implementation.
REST remains the external system boundary.
```

---

## 35. Change Log

### 2.1.0, 2026-09-18

- Replaced the incomplete custom Portal-session direction with HTTP Basic Authentication.
- Defined exactly one configured household Portal administrator.
- Prohibited a users table, user registration, multiple Portal accounts, and Portal role management in Core V1.
- Deferred custom login pages, session cookies, login nonces, logout tracking, and HMAC session frameworks.
- Required exact Origin allowlisting for Portal mutations.
- Standardized on one canonical server-rendered Portal.
- Defined no-side-effect Cancel behavior.
- Added native-editing guidance to prevent repeated PowerShell and Python patch-script failures.

### 2.0.0, 2026-09-16

- Split Samjon Memory into separate Core and Resolver SQLite databases.
- Defined Core-first development and Core freeze before Resolver.
- Added the Core and Resolver Portal requirements.
- Added Memory versus Collection ownership and independent Collection Memory editing.

EOF