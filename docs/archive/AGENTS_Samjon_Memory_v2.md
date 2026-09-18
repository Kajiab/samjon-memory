---
SUPERSEDED: canonical replacement is ../../AGENTS.md
Implementation use: PROHIBITED
Archived from samjon-memory repository on 2026-09-18.
---

# AGENTS.md: Samjon Memory Developer Context

**Document ID:** SAMJON-MEMORY-AGENT-001  
**Version:** 2.0.0  
**Status:** Canonical repository instruction  
**Owner:** Samjon Memory Engineering  
**Approver:** Jeab  
**Last reviewed:** 2026-09-16  
**Repository:** `samjon-memory`

---

## 1. Purpose

This file is the mandatory working guide for Cline and other AI coding agents when reading, designing, editing, testing, or reviewing Samjon Memory.

Read this file before making any change.

Also read:

```text
HomeAI/AGENTS.md
HomeAI/docs/DOCUMENT_INDEX.md
HomeAI/docs/PROJECT_STATUS.md
HomeAI/docs/standards/BACKEND_TO_MCP_MODULE_STANDARD.md
HomeAI/samjon-memory/docs/DOCUMENT_INDEX.md
```

The cross-project architecture is defined under:

```text
HomeAI/docs/blueprints/
```

Project-level instructions may add stricter rules but may not weaken HomeAI umbrella rules.

If instructions, implementation, tests, schemas, or canonical documents conflict, report the conflict with exact file references before editing.

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

Samjon Memory uses two physically separate SQLite databases from the initial implementation:

```text
samjon_core.sqlite
= authoritative durable facts

samjon_resolver.sqlite
= derived, disposable, rebuildable search projections
```

The initial service may run Core and Resolver in one process on one REST port, but the databases, schemas, migrations, repositories, backup policies, and lifecycle remain separate.

---

## 3. Canonical Architecture

```text
Numchoke or Xiaozhi
        |
        v
Samjon Home MCP
  Samjon module
        |
        v
Samjon Memory REST API :8100
        |
        +-----------------------------+
        |                             |
        v                             v
Core Memory                     Resolver
Authoritative facts             Derived projections
samjon_core.sqlite              samjon_resolver.sqlite
```

Projection flow is one-way:

```text
Core API / Core service
        |
        v
Projection builder
        |
        v
Resolver database
```

Rules:

- Resolver must not write facts into Core.
- External services must not access either SQLite file directly.
- Search results resolve IDs through Resolver, then load authoritative facts through Core.
- Resolver may be deleted and rebuilt without loss of authoritative information.
- Samjon Memory does not implement MCP, OpenRouter conversation loops, Home Assistant control, Numchai playback, or Numsub rules.

---

## 4. Development Phases

### 4.1 Phase 1: Core Memory V1

Develop Core first until its schema and API are stable and frozen.

Core Phase 1 includes:

- Typed configuration.
- Core SQLite connection and pragmas.
- Explicit Core migrations.
- Fact creation with idempotency.
- Fact retrieval by ID.
- Bounded deterministic Core query by metadata.
- Versioning and supersession.
- Administrative forget lifecycle.
- Authentication and subject authorization.
- Sensitive-data rejection.
- Audit records.
- Backup and restore validation.
- Core Web Portal pages.
- Core OpenAPI and tests.

Core Phase 1 excludes:

- FTS5 search.
- AI enrichment.
- Derived aliases and semantic tags.
- Embeddings or vector search.
- Resolver ranking.
- Samjon Home MCP module.

### 4.2 Core Freeze Gate

Core is frozen as V1 when:

- [ ] Core schema migration tests pass.
- [ ] Core API tests pass.
- [ ] Idempotency tests pass.
- [ ] Version and supersession tests pass.
- [ ] Authentication and subject isolation tests pass.
- [ ] Sensitive-data policy tests pass.
- [ ] Backup and isolated restore tests pass.
- [ ] Core Web Portal uses only supported APIs.
- [ ] OpenAPI matches runtime behavior.
- [ ] Canonical documentation matches implementation.
- [ ] Known limitations are explicit.

Freeze means contract changes require versioning. It does not prohibit bug fixes.

### 4.3 Phase 2: Resolver V1

Begin Resolver implementation only after Core V1 is frozen and contains representative test data.

Resolver Phase 2 includes:

- Separate Resolver SQLite connection and migrations.
- Projection builder reading Core through an approved service/API boundary.
- Normalized search text.
- FTS5 projection.
- Derived aliases and tags.
- Vocabulary resolution.
- Deterministic ranking and match reasons.
- Bounded context retrieval.
- Stale projection detection.
- Full and selective rebuild.
- Atomic resolver replacement.
- Resolver Web Portal pages.
- Resolver OpenAPI and tests.

### 4.4 Phase 3: Samjon Home MCP Module

After Core and Resolver APIs are final-test quality:

```text
Final Samjon Memory API
-> thin Samjon Home MCP module
-> module tests
-> live compatibility tests
-> consumer tests
-> contract freeze
-> publish to home-ai-contracts
```

Follow:

```text
HomeAI/docs/standards/BACKEND_TO_MCP_MODULE_STANDARD.md
```

Do not implement the MCP module inside this repository.

---

## 5. Core Invariants

### 5.1 Core is authoritative

`samjon_core.sqlite` is the source of truth for durable memory.

Core owns:

- Fact identity.
- Raw user-confirmed content.
- Structured value.
- Subject, type, and scope.
- Source and provenance.
- User-confirmed aliases and vocabulary that must survive Resolver rebuild.
- Manual overrides.
- Version and supersession.
- Lifecycle status.
- Idempotency records.
- Audit records.

Core facts are never silently overwritten.

### 5.2 Resolver is derived and disposable

`samjon_resolver.sqlite` contains rebuildable projections.

Resolver may contain:

- Normalized text.
- Search text.
- FTS5 indexes.
- Derived aliases.
- Derived semantic tags.
- Projection state.
- Ranking metadata.
- AI-generated search enrichment in a future approved phase.
- Embeddings in a future approved phase.

Deleting Resolver must not delete authoritative user information.

### 5.3 Manual durable metadata belongs in Core

Anything that must survive complete Resolver deletion belongs in Core.

Examples:

```text
User-confirmed alias
User-confirmed vocabulary
Manual correction
Manual classification
Explicit user tag that carries durable meaning
```

Resolver duplicates these only as search projections.

### 5.4 REST API is the external boundary

External systems call documented Samjon Memory APIs.

Do not allow Samjon Home MCP, Numchoke, the Web Portal, scripts, or other services to open either SQLite file directly.

### 5.5 Conversation history is not durable memory

A conversation transcript is not automatically stored as memory.

Create durable memory only when:

- The user explicitly asks to remember it.
- An approved workflow confirms it.
- Subject and source are recorded.

### 5.6 Retrieval returns evidence

Resolver responses return bounded structured results with:

- Memory ID.
- Core version.
- Score.
- Match reasons.
- Conflicts.
- Projection freshness.

Numchoke owns the final conversational answer.

---

## 6. Explicit Non-Goals

Do not add without an accepted ADR:

- MCP transport or MCP tool registration.
- Direct OpenRouter or other LLM calls in Core V1.
- Automatic extraction from every conversation.
- Vector database or embeddings.
- Autonomous fact deletion.
- Direct database access from another service.
- Browser-side SQLite access.
- Raw Home Assistant state mirroring.
- Numchai playback logic.
- Numsub event ingestion at sensor frequency.
- Security codes, passwords, tokens, private keys, biometrics, or raw audio storage.
- Public unauthenticated APIs or Web Portal.

---

## 7. Source of Truth

Authority order:

1. Executable migration, API, security, portal, backup, restore, projection, and retrieval tests.
2. Current implementation.
3. Generated OpenAPI and schema exports.
4. Accepted ADRs.
5. Canonical documents.
6. Supporting documents.
7. Historical reports and drafts.

When documentation conflicts with code or tests, report exact file and line references before changing either.

---

## 8. Recommended Repository Structure

```text
samjon-memory/
├── README.md
├── AGENTS.md
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── compose.example.yml
├── src/
│   └── samjon_memory/
│       ├── __init__.py
│       ├── samjon_memory_main.py
│       ├── samjon_memory_config.py
│       ├── samjon_memory_lifecycle.py
│       ├── core/
│       │   ├── api/
│       │   │   ├── core_memory_api.py
│       │   │   ├── core_query_api.py
│       │   │   ├── core_admin_api.py
│       │   │   └── core_api_schemas.py
│       │   ├── services/
│       │   │   ├── core_memory_service.py
│       │   │   └── core_lifecycle_service.py
│       │   ├── repositories/
│       │   │   ├── core_memory_repository.py
│       │   │   ├── core_alias_repository.py
│       │   │   ├── core_vocabulary_repository.py
│       │   │   ├── core_idempotency_repository.py
│       │   │   └── core_audit_repository.py
│       │   └── database/
│       │       ├── core_database.py
│       │       ├── core_schema.py
│       │       ├── core_migrations.py
│       │       └── migrations/
│       ├── resolver/
│       │   ├── api/
│       │   │   ├── resolver_search_api.py
│       │   │   ├── resolver_context_api.py
│       │   │   ├── resolver_vocabulary_api.py
│       │   │   ├── resolver_admin_api.py
│       │   │   └── resolver_api_schemas.py
│       │   ├── services/
│       │   │   ├── resolver_search_service.py
│       │   │   ├── resolver_projection_service.py
│       │   │   └── resolver_rebuild_service.py
│       │   ├── repositories/
│       │   │   ├── resolver_projection_repository.py
│       │   │   ├── resolver_alias_repository.py
│       │   │   ├── resolver_tag_repository.py
│       │   │   └── resolver_vocabulary_repository.py
│       │   ├── retrieval/
│       │   │   ├── resolver_query_normalizer.py
│       │   │   ├── resolver_fts_search.py
│       │   │   ├── resolver_ranker.py
│       │   │   └── resolver_conflict_detector.py
│       │   └── database/
│       │       ├── resolver_database.py
│       │       ├── resolver_schema.py
│       │       ├── resolver_migrations.py
│       │       └── migrations/
│       ├── portal/
│       │   ├── portal_routes.py
│       │   ├── portal_auth.py
│       │   └── static/
│       │       ├── index.html
│       │       ├── portal.js
│       │       └── portal.css
│       ├── api/
│       │   ├── health_api.py
│       │   ├── capability_api.py
│       │   └── common_api_schemas.py
│       ├── security/
│       │   ├── authentication.py
│       │   ├── authorization.py
│       │   ├── sensitive_data.py
│       │   ├── csrf.py
│       │   └── redaction.py
│       ├── observability/
│       │   ├── logging.py
│       │   ├── metrics.py
│       │   └── audit.py
│       └── shared/
│           ├── errors.py
│           ├── ids.py
│           ├── normalization.py
│           └── result.py
├── tests/
│   ├── core/
│   ├── resolver/
│   ├── portal/
│   ├── api/
│   ├── migration/
│   ├── security/
│   ├── backup_restore/
│   └── integration/
├── docs/
├── artifacts/
└── scripts/
```

Use project-prefixed or layer-specific filenames consistently.

---

## 9. Database Files and Configuration

Default logical configuration:

```text
SAMJON_CORE_DATABASE_PATH=/data/samjon_core.sqlite
SAMJON_RESOLVER_DATABASE_PATH=/data/samjon_resolver.sqlite
```

Rules:

- Paths are configurable.
- Production paths are not hard-coded.
- Database files use separate connections.
- Each database has independent `schema_meta` and migrations.
- Core and Resolver schema versions are reported separately.
- Foreign keys are enabled for every connection.
- WAL and busy timeout are configured deliberately and tested.
- Resolver database can be replaced while Core remains intact.

---

## 10. Core Data Model

Core facts should support these fields or approved equivalents:

```text
memory_id
subject
memory_type
scope
raw_content
structured_value_json
source
language
status
version
supersedes_memory_id
created_at
updated_at
```

Core supporting tables should cover:

```text
core_memory_alias
core_vocabulary
core_memory_tag
core_idempotency
core_audit
schema_meta
```

Rules:

- IDs are server-generated and stable.
- Subject is explicit.
- Memory type and scope use approved values.
- Raw content preserves the confirmed statement.
- Structured value stores typed facts when useful.
- Superseded and forgotten facts remain auditable according to policy.
- Manual metadata is not overwritten by derived data.
- Schema changes require explicit migrations and tests.

---

## 11. Resolver Data Model

Resolver should support these fields or approved equivalents:

```text
resolver_projection
- memory_id
- core_version
- normalized_text
- search_text
- projection_version
- generated_by
- confidence
- projection_status
- indexed_at

resolver_alias
- memory_id
- alias
- normalized_alias
- source
- priority

resolver_tag
- memory_id
- tag
- normalized_tag
- source
- confidence

resolver_vocabulary
- subject
- phrase
- normalized_phrase
- canonical_value
- source
- priority

projection_state
- memory_id
- core_version
- projected_version
- projection_status
- last_error
- updated_at

resolver_fts
- FTS5 search projection

schema_meta
- independent resolver schema version
```

Resolver records are not authoritative facts.

---

## 12. Core API V1

Initial Core routes should use a clear versioned prefix, for example:

```text
GET  /health
GET  /ready
GET  /api/v1/capabilities

POST /api/v1/core/memories
GET  /api/v1/core/memories/{memory_id}
POST /api/v1/core/memories/query
PATCH /api/v1/core/memories/{memory_id}
POST /api/v1/core/memories/{memory_id}/supersede
POST /api/v1/core/memories/{memory_id}/forget
```

Exact paths must be documented and generated from implementation.

Core query is metadata-based, not semantic search. It may filter by:

```text
subject
memory_types
scopes
statuses
source
tags
created or updated range
limit
```

Every route defines authentication, authorization, schema, limits, stable errors, side effects, idempotency, and timeout behavior.

---

## 13. Resolver API V1

After Core freeze, Resolver routes may include:

```text
GET  /api/v1/resolver/capabilities
POST /api/v1/resolver/search
POST /api/v1/resolver/context
POST /api/v1/resolver/vocabulary/resolve
GET  /api/v1/resolver/projections/{memory_id}
POST /api/v1/resolver/admin/rebuild
GET  /api/v1/resolver/admin/rebuild/status
```

Rules:

- Search is bounded.
- Results identify match reasons and projection freshness.
- Admin rebuild requires separate authorization.
- Resolver never claims stale data is current.
- Search obtains authoritative fact data from Core before responding.

---

## 14. Resolver Rebuild Standard

Full rebuild must preserve Core and avoid serving a half-built index.

Preferred flow:

```text
1. Create samjon_resolver.next.sqlite.
2. Initialize the target Resolver schema.
3. Read active Core facts in bounded pages.
4. Build projections, aliases, tags, vocabulary, and FTS5.
5. Validate counts, foreign references, schema, and integrity.
6. Stop new Resolver readers or switch them to maintenance mode.
7. Close the current Resolver connection.
8. Atomically replace the Resolver database.
9. Reopen and verify readiness.
10. Retain the prior Resolver temporarily for rollback.
```

Do not empty the active Resolver in place while normal search traffic continues.

Selective rebuild may update one memory when Core version changes.

---

## 15. Web Portal Requirement

Samjon Memory must include a human-facing Web Portal because it has no other visual interface for inspecting and verifying stored facts and resolver behavior.

The Portal is a supported test and administration surface, not a direct database editor.

### 15.1 Portal location

Initial route:

```text
GET /portal/
```

It may be served by the same Samjon Memory process and port `8100`.

### 15.2 Portal architecture

```text
Browser
-> authenticated Portal
-> documented Core and Resolver APIs
-> service/repository layers
-> separate SQLite databases
```

The browser and Portal routes must never open or modify SQLite directly.

### 15.3 Core Portal capabilities

The Core section should support:

- Dashboard with Core health, schema version, counts, and last backup status.
- List and paginate facts.
- Filter by subject, type, scope, status, source, and date.
- View complete fact details and audit history.
- Create a fact through the supported Core API.
- Edit a fact with expected-version checking.
- Supersede a fact.
- Forget a fact through guarded administrative flow.
- Manage durable manual aliases, vocabulary, and user tags.
- View idempotency outcome without exposing sensitive request content.
- Export a bounded sanitized record for debugging.

### 15.4 Resolver Portal capabilities

The Resolver section should support:

- Resolver health, schema version, projection counts, and freshness summary.
- Search using the same Resolver API used by clients.
- Show score, match reasons, aliases, tags, and conflicts.
- Compare Resolver projection with the current Core fact/version.
- List stale, failed, and missing projections.
- Rebuild one memory.
- Preview full rebuild impact.
- Start a guarded full rebuild.
- View rebuild progress and validation result.
- Inspect derived aliases, tags, vocabulary, and FTS document.
- Delete and recreate Resolver only through guarded rebuild operations.

### 15.5 Portal safety

- Portal requires authentication.
- Administrative actions require an admin role.
- Mutating requests require CSRF protection or an equivalent same-origin defense.
- Destructive operations require an explicit confirmation phrase.
- Full Core raw dumps are prohibited.
- Sensitive fields are redacted.
- Portal logs do not include full fact content by default.
- Resolver deletion must never target the Core path.
- Portal response sizes and pagination are bounded.
- Production deployment should bind to trusted LAN or authenticated reverse proxy.

### 15.6 Portal test requirements

Tests must cover:

- Authentication and authorization.
- CSRF or equivalent mutation protection.
- Core list, detail, create, update, supersede, and guarded forget.
- Optimistic version conflict.
- Resolver search and evidence display.
- Stale projection warning.
- Single-memory rebuild.
- Full rebuild preview and confirmation.
- Resolver rebuild does not modify Core.
- XSS-safe rendering of untrusted content.
- Pagination and result limits.
- Error and degraded-state rendering.

---

## 16. Write and Idempotency Rules

Memory creation is a side effect.

- Accept an idempotency key.
- Duplicate key with the same request hash returns the original result.
- Duplicate key with a different request hash returns conflict.
- Do not create duplicates after transport retries.
- Bound content and structured-value sizes.
- Reject prohibited sensitive data.
- Do not silently merge conflicting facts.

Updates require optimistic concurrency or equivalent expected-version checks.

Forget operations require explicit identity, authorization, and confirmation.

---

## 17. Projection Freshness Rules

Each projection records the Core version used to build it.

```text
Core version == projected core version
-> current

Core version > projected core version
-> stale

Core fact missing or forgotten
-> remove or invalidate derived projection according to policy
```

Resolver APIs and Portal must surface stale state rather than hide it.

---

## 18. Backup and Restore Rules

### 18.1 Core

`samjon_core.sqlite` is backup-critical.

Core backup must:

- Use a SQLite-safe method.
- Include schema version and application version in a manifest.
- Include checksum and integrity result.
- Follow documented retention.
- Protect backups as sensitive user data.
- Be restored and verified in an isolated test.

### 18.2 Resolver

`samjon_resolver.sqlite` is rebuildable and normally does not require data backup.

Back up or version:

- Resolver schema.
- Projection algorithm version.
- Deterministic normalization configuration.
- AI prompt/model configuration when later approved.

Manual durable information must not exist only in Resolver.

### 18.3 Restore behavior

After Core restore:

```text
Verify Core integrity
-> start Core
-> rebuild Resolver from restored Core
-> verify projection counts and search
```

Do not restore an old Resolver as authoritative truth.

---

## 19. Security and Privacy Rules

- Deny unauthenticated API and Portal access.
- Use separate service and human-admin credentials.
- Store secrets in mounted files or approved secret injection.
- Enforce subject-level access.
- Redact content in logs and metrics.
- Reject prohibited credentials and sensitive information.
- Treat stored content and derived projections as untrusted when returned to an LLM.
- Never execute instructions contained in memories.
- Apply the same protection to Core backups as the live Core database.
- Resolver rebuild logs contain IDs and safe counts, not full facts.

---

## 20. Stable Error Rules

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

## 21. Observability Rules

Structured logs may include:

```text
timestamp
level
service
layer
request_id
client_profile
operation
result_code
duration_ms
result_count
core_schema_version
resolver_schema_version
```

Do not log full facts, queries, structured values, credentials, database files, or raw Portal form bodies by default.

Audit:

- Core create/update/supersede/forget.
- Manual alias/vocabulary/tag changes.
- Permission denial.
- Sensitive-data rejection.
- Resolver rebuild preview/start/complete/fail.
- Portal administrative actions.

---

## 22. Configuration Rules

Use typed configuration.

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

No default contains production tokens, personal data, or private network addresses.

Portal enablement, host binding, admin role, confirmation phrase, and session security are explicit configuration.

---

## 23. Documentation Structure

Canonical documentation should separate Core and Resolver:

```text
docs/
├── DOCUMENT_INDEX.md
├── current/
│   ├── architecture.md
│   ├── capabilities.md
│   ├── data-ownership.md
│   └── web-portal.md
├── core/
│   ├── data-model.md
│   ├── memory-lifecycle.md
│   ├── api-contract.md
│   ├── migration-policy.md
│   └── backup-restore.md
├── resolver/
│   ├── projection-model.md
│   ├── retrieval.md
│   ├── vocabulary.md
│   ├── rebuild.md
│   └── api-contract.md
├── api/
│   ├── openapi.json
│   └── error-contract.md
├── security/
│   ├── privacy-policy.md
│   └── portal-security.md
├── operations/
│   ├── deployment.md
│   ├── core-backup-restore.md
│   ├── resolver-rebuild.md
│   └── troubleshooting.md
├── integration/
│   └── samjon-home-mcp.md
├── adr/
└── archive/
```

---

## 24. Documentation Sync Rule

After every externally visible behavior change, review affected canonical documentation.

Update documentation when Core or Resolver API, schema, capability, configuration, migration, projection, retrieval, error, Portal, security, backup, rebuild, or integration behavior changes.

Internal refactoring with unchanged observable behavior does not require a documentation update.

Before completion, report one of:

```text
Documentation updated: <files>
Documentation unchanged: no externally visible behavior changed
Documentation update blocked: <reason>
```

Do not create a new Markdown report for every task. Store validation evidence under `artifacts/reports/`.

---

## 25. Testing Requirements

### Core tests

- Core initial migration.
- Migration idempotency.
- Create with idempotency.
- Idempotency conflict.
- Get by ID.
- Metadata query and bounds.
- Update with expected version.
- Supersession.
- Guarded forget.
- Subject isolation.
- Sensitive-data rejection.
- Audit behavior.
- Core backup and isolated restore.
- Core OpenAPI drift.

### Resolver tests

- Resolver initial migration.
- Projection from frozen Core API.
- FTS5 search.
- Aliases, tags, and vocabulary.
- Score and match reasons.
- Stale projection detection.
- Selective rebuild.
- Atomic full rebuild.
- Failed rebuild rollback.
- Resolver deletion/recreation leaves Core unchanged.
- Bounded search and context.
- Resolver OpenAPI drift.

### Portal tests

Follow Section 15.6.

Normal tests use temporary Core and Resolver databases and never production data.

---

## 26. Editing Policy

- Prefer minimal controlled patches.
- Do not refactor unrelated files.
- Keep Core and Resolver SQL in their respective repositories/database layers.
- Keep API routes thin.
- Do not place FTS5 or derived search columns in Core merely for convenience.
- Do not add LLM dependency to Core.
- Do not let Portal bypass API/service policy.
- Do not weaken privacy or confirmation policy to make a test pass.
- Preserve backward compatibility after Core or Resolver freeze unless a new version is approved.
- Add regression tests for bug fixes.

Final reports include problem, root cause, files changed, Core/Resolver impact, API impact, migration impact, Portal impact, security impact, exact tests, results, and limitations.

---

## 27. Task Scope Rules for Cline

Default editable scope:

```text
HomeAI/samjon-memory/
```

Read-only unless explicitly authorized:

```text
HomeAI/samjon-home-mcp/
HomeAI/numchoke/
HomeAI/numchai/
HomeAI/numsub/
HomeAI/home-ai-contracts/
HomeAI/home-ai-deploy/
HomeAI/docs/
```

Do not modify an MCP consumer to hide a Samjon Memory defect.

Before editing, state:

- Development phase: Core or Resolver.
- Files and tests to read.
- Files to change.
- Core and Resolver database impact.
- API impact.
- Portal impact.
- Security/privacy impact.
- Backup/rebuild impact.
- Test plan.

Resolver implementation must not begin before the Core Freeze Gate is evidenced, unless the task is explicitly limited to non-operational scaffolding.

---

## 28. Initial Development Sequence

```text
Phase 1: Core
1. Scaffold service, configuration, tests, and canonical docs.
2. Define Core memory model and explicit migrations.
3. Implement Core database lifecycle.
4. Implement authentication, authorization, and sensitive-data policy.
5. Implement create/get/metadata-query APIs.
6. Implement idempotency, versioning, supersession, and guarded forget.
7. Implement Core audit.
8. Implement Core Web Portal through supported APIs.
9. Implement Core backup and isolated restore validation.
10. Export and review Core OpenAPI.
11. Run the Core Freeze Gate.
12. Mark Core V1 frozen with evidence.

Phase 2: Resolver
13. Define Resolver projection schema and migrations.
14. Implement projection from frozen Core API/service boundary.
15. Implement FTS5, aliases, tags, vocabulary, ranking, and evidence.
16. Implement freshness and selective rebuild.
17. Implement atomic full rebuild and rollback.
18. Implement Resolver Web Portal through supported APIs.
19. Export and review Resolver OpenAPI.
20. Run Resolver tests using representative Core facts.
21. Freeze Resolver V1.

Phase 3: MCP readiness
22. Finalize Samjon Memory capability and integration documents.
23. Produce final API evidence for Samjon Home MCP.
24. Build the MCP module in the Samjon Home MCP repository.
```

---

## 29. Release Blocking Conditions

Block Core release when:

- External services or Portal access Core SQLite directly.
- Conversation history is stored automatically.
- Sensitive credentials can be stored.
- Writes are non-idempotent under retries.
- Core migrations lack tests.
- Subject authorization is missing.
- Core backup/restore is untested.
- Core Portal bypasses service/API validation.
- Core API/OpenAPI drift exists.

Block Resolver release when:

- Resolver can modify Core facts.
- Manual durable data exists only in Resolver.
- Resolver cannot be deleted and rebuilt.
- Rebuild exposes a half-built active index.
- Projection freshness is hidden.
- Retrieval is unbounded or unexplained.
- Resolver migrations or rebuild tests fail.
- Resolver Portal can target the Core database path.
- Resolver API/OpenAPI drift exists.

Block all releases when:

- Secrets or full fact content appear in logs by default.
- Embeddings or LLM calls are added without ADR.
- Documentation claims more than tests prove.

---

## 30. Definition of Done

### Core V1

- Core schema and API are versioned and frozen.
- Create, get, metadata query, update, supersede, and guarded forget are tested.
- Idempotency and authorization are tested.
- Core Portal supports safe inspection and editing through APIs.
- Backup and isolated restore pass.
- OpenAPI and canonical docs match implementation.

### Resolver V1

- Resolver database is physically separate and rebuildable.
- Projection uses frozen Core data.
- FTS5, vocabulary, aliases, tags, ranking, and freshness are tested.
- Atomic rebuild and rollback pass.
- Resolver Portal exposes search evidence and guarded rebuild controls.
- Resolver deletion/recreation leaves Core unchanged.
- OpenAPI and canonical docs match implementation.

---

## 31. Final Engineering Principle

```text
Core stores authoritative facts.
Resolver stores derived search projections.
Core is backup-critical.
Resolver is disposable and rebuildable.
Manual durable knowledge belongs in Core.
AI may enrich Resolver but may not rewrite Core facts.
The Portal uses supported APIs and never edits SQLite directly.
Core freezes before Resolver implementation.
REST remains the external boundary.
```

---

## 32. Change Log

### 2.0.0, 2026-09-16

- Split Samjon Memory into physically separate Core and Resolver SQLite databases.
- Defined Core-first development and Core V1 freeze before Resolver implementation.
- Defined Resolver as disposable, rebuildable, and one-way derived from Core.
- Moved FTS5, aliases, semantic tags, vocabulary projection, and ranking to Resolver.
- Kept durable manual metadata and authoritative facts in Core.
- Added the authenticated Web Portal requirement for inspecting and editing Core and Resolver through supported APIs.
- Added guarded Resolver rebuild, freshness, backup, restore, and Portal security requirements.


## 33. Memory versus Collection Decision Rule

### 33.1 Storage-type ownership

The creating user or approved client explicitly chooses whether content
is stored as:

- a standalone memory, or
- a collection containing one or more independently managed memories.

Core must not infer or automatically change the selected storage type.

Use a standalone memory when the content represents one cohesive fact or
note that remains understandable independently.

Use a collection when the content contains multiple ordered or separately
maintained sections that share one title, subject, source, or lifecycle.

Content length is a safety constraint, not the primary semantic decision.

### 33.2 Core responsibilities

Core stores facts only.

Core may:

- validate the selected structure
- recommend using a collection
- detect headings and safe section boundaries for preview
- reject content exceeding the standalone-memory hard limit
- report structural inconsistencies
- preserve the original submitted content for review

Core must not silently:

- split content
- merge memories
- summarize content
- reinterpret facts
- change a standalone memory into a collection
- change a collection into a standalone memory

An AI-assisted workflow may propose a collection plan, including:

- collection title
- collection summary
- section titles
- proposed section boundaries
- proposed ordering

The original content, proposed boundaries, titles, ordering, and resulting
memory sections must remain reviewable.

No AI-proposed structure may be activated without explicit approval from
the creating user or an authorized approving client.

### 33.3 Collection lifecycle

A new collection is created with `draft` status.

A draft collection is not visible to Resolver.

The collection becomes `active` only after:

- its structure passes validation
- all required memory sections are present
- section ordering is valid
- the creating user or approved client explicitly activates it

Only active collections and active memories are eligible for Resolver
projection.

### 33.4 Collection-memory independence

Each memory inside a collection has its own:

- memory ID
- version
- lifecycle status
- content
- structured value
- source metadata
- audit history
- edit endpoint

Editing one memory inside a collection must not require replacing or
rewriting the complete collection.

A memory-content change increments that memory's version.

A change affecting the assembled collection view also increments the
collection version.

Structural collection changes include:

- adding a memory
- removing or forgetting a memory
- moving a memory
- changing section order
- changing collection title or summary
- changing collection lifecycle status

Unchanged memories retain their existing IDs, versions, and content.

### 33.5 Resolver boundaries

Resolver must not:

- split Core memories
- merge Core memories
- rewrite Core facts
- summarize Core facts as replacements
- change collection membership
- change section ordering
- write directly to the Core database

Resolver builds derived projections only.

Resolver must search both:

- collection-level projections
- memory-level projections

from one search intent.

The default Resolver target is:

`auto`

An authorized client may explicitly request:

- `memory`
- `collection`
- `auto`

### 33.6 Resolver result types

Resolver may return one of these resolution types:

- `standalone_memory`
- `collection_memory`
- `collection`
- `collection_with_selected_memories`
- `ambiguous`
- `no_match`

Definitions:

`standalone_memory`
means one independent memory matched the intent.

`collection_memory`
means one memory inside a collection matched the intent.

`collection`
means the collection title, summary, or overall purpose matched the
intent.

`collection_with_selected_memories`
means multiple relevant memories from the same collection matched the
intent.

`ambiguous`
means the available evidence is insufficient to choose safely.

`no_match`
means no result met the configured threshold.

Resolver must not guess when the result is ambiguous.

### 33.7 Collection result limits

A collection result does not automatically include every memory in the
collection.

Resolver must apply a bounded context budget.

When the complete collection exceeds the applicable limit, Resolver
returns:

- collection identity
- collection title
- collection summary
- collection version
- section index
- the memories most relevant to the intent
- continuation or retrieval metadata when supported

Resolver may return the complete collection only when:

- the client requests collection-level context
- authorization permits access to every included memory
- the collection fits within the configured result limit
- the assembled result remains within the response budget

Resolver must never produce an unbounded Core data dump.

### 33.8 Context expansion

When a memory inside a collection matches, Resolver may include neighboring
memories when they are necessary to preserve meaning.

Examples include:

- a preceding definition
- a following exception
- a prerequisite section
- a directly related step
- an immediately adjacent section required for continuity

Context expansion must:

- remain inside the same authorized collection
- respect sequence order
- remain within the configured context budget
- identify primary and supporting memories separately
- provide reasons for including supporting memories

Neighboring memories must not be included automatically when the primary
memory is independently understandable.

### 33.9 Authoritative result loading

Resolver returns matched identities, scores, match reasons, conflicts,
and projection metadata.

Before returning fact content, the service loads the authoritative
records from Core.

Resolver projection content must not replace the current Core fact.

Every resolved result must identify:

- memory ID or collection ID
- Core version
- projected Core version
- projection freshness
- score
- match reasons
- result type

If the Resolver projection is stale, the response must report that state
according to the approved freshness policy.

### 33.10 Canonical summary

```text
Creator chooses Memory or Collection.

Core validates but never infers storage structure.

Core stores facts only.

Each memory inside a Collection has its own identity, version, lifecycle,
audit history, and edit endpoint.

Editing one Collection memory does not require rewriting the whole
Collection.

Structural or assembled-view changes increment the Collection version.

AI may propose structure but cannot activate it without approval.

Resolver cannot split, merge, summarize as replacement, or rewrite Core
records.

Resolver searches Collection-level and Memory-level projections from one
intent.

Resolver target defaults to auto.

Resolver may return a standalone memory, one memory in a collection,
a bounded collection, selected memories from a collection, ambiguity,
or no match.

Resolver returns evidence and identities, then authoritative content is
loaded from Core.
