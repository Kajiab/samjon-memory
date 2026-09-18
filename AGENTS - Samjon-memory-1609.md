# AGENTS.md: Samjon Memory Developer Context

**Document ID:** SAMJON-MEMORY-AGENT-001  
**Version:** 1.0.0  
**Status:** Canonical repository instruction  
**Owner:** Samjon Memory Engineering  
**Last reviewed:** 2026-09-14  
**Repository:** `samjon-memory`

---

## 1. Purpose

This file is the mandatory working guide for Cline and other AI coding agents when reading, designing, editing, testing, or reviewing Samjon Memory.

Read this file before making any change.

Documentation authority and task-specific reading paths are defined in:

```text
docs/DOCUMENT_INDEX.md
```

The cross-project target architecture is defined outside this repository:

```text
HomeAI/docs/blueprints/
Samjon_Home_MCP_development_blueprint_2026-09-14.md
```

If instructions conflict, report the conflict before editing.

---

## 2. Project Summary

Samjon Memory is the durable household knowledge and memory backend.

It stores and retrieves explicit, structured, text-based knowledge such as:

- User preferences.
- Household vocabulary and aliases.
- Device and location notes.
- Music preferences.
- Plant, inventory, and equipment knowledge.
- Explicitly remembered facts.

Initial implementation principles:

```text
SQLite is the durable store.
FTS5 provides deterministic text retrieval.
Aliases, tags, vocabulary, subject, scope, and memory type are first-class metadata.
REST API is the operational boundary.
Samjon Home MCP is an external AI-facing adapter.
RAG and embeddings are future enhancements, not V0.1 requirements.
```

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
Samjon Memory REST API
        |
        v
Application service
        |
        v
SQLite + FTS5
```

Samjon Memory does not implement MCP, OpenRouter, conversation loops, Home Assistant control, or Numchai playback.

---

## 4. Core Invariants

### 4.1 REST API is the external boundary

External systems call the documented Samjon Memory API.

Do not permit Samjon Home MCP, Numchoke, or other services to access the SQLite file directly.

### 4.2 Database access is owned here

Only Samjon Memory owns:

- Database connection lifecycle.
- Schema and migrations.
- Transactions.
- FTS indexes.
- Memory-version and supersession rules.
- Backup and restore validation.

### 4.3 Explicit memory is different from conversation history

A conversation transcript is not automatically durable memory.

Store durable memory only when:

- The user explicitly asks to remember it.
- An approved workflow confirms it.
- The source and subject are recorded.

### 4.4 Deterministic retrieval first

V0.1 retrieval uses:

```text
subject
memory_type
scope
tags
aliases
vocabulary
FTS5 search text
status and supersession
```

Do not add embeddings, vector databases, rerankers, or an LLM dependency without an accepted ADR.

### 4.5 Memory lifecycle is auditable

Memories are not silently overwritten.

Updates must preserve:

- Stable memory ID or explicit replacement relation.
- Version information.
- Supersession history.
- Created and updated timestamps.
- Source metadata.

### 4.6 Retrieval returns evidence, not conversational prose

The API returns bounded structured records, scores, match reasons, conflicts, and metadata.

Numchoke owns the final answer.

---

## 5. Explicit Non-Goals

Do not add these without an accepted ADR:

- MCP transport or tool registration.
- OpenRouter or any LLM call.
- Automatic extraction of memory from all conversations.
- Vector database or embeddings.
- Autonomous deletion.
- Raw Home Assistant state mirroring.
- Numchai playback logic.
- Numsub event ingestion at sensor frequency.
- Security codes, passwords, tokens, private keys, biometrics, or raw audio storage.
- Public unauthenticated endpoints.

---

## 6. Source of Truth

Authority order:

1. Executable migration, API, retrieval, security, and backup tests.
2. Current implementation.
3. Generated OpenAPI and schema exports.
4. Accepted ADRs.
5. Canonical documents.
6. Supporting documents.
7. Historical reports and drafts.

When documentation conflicts with code or tests, report exact file and line references before changing either.

---

## 7. Recommended Repository Structure

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
│       ├── api/
│       │   ├── samjon_memory_api.py
│       │   ├── samjon_search_api.py
│       │   ├── samjon_context_api.py
│       │   ├── samjon_vocabulary_api.py
│       │   ├── samjon_health_api.py
│       │   └── samjon_api_schemas.py
│       ├── services/
│       │   ├── samjon_memory_service.py
│       │   ├── samjon_search_service.py
│       │   ├── samjon_context_service.py
│       │   └── samjon_vocabulary_service.py
│       ├── repositories/
│       │   ├── samjon_memory_repository.py
│       │   ├── samjon_vocabulary_repository.py
│       │   └── samjon_audit_repository.py
│       ├── database/
│       │   ├── samjon_database.py
│       │   ├── samjon_schema.py
│       │   ├── samjon_migrations.py
│       │   └── migrations/
│       ├── retrieval/
│       │   ├── samjon_query_normalizer.py
│       │   ├── samjon_fts_search.py
│       │   ├── samjon_ranker.py
│       │   └── samjon_conflict_detector.py
│       ├── security/
│       │   ├── samjon_authentication.py
│       │   ├── samjon_authorization.py
│       │   ├── samjon_sensitive_data.py
│       │   └── samjon_redaction.py
│       ├── observability/
│       │   ├── samjon_logging.py
│       │   ├── samjon_metrics.py
│       │   └── samjon_audit.py
│       └── shared/
│           ├── samjon_errors.py
│           ├── samjon_ids.py
│           └── samjon_result.py
├── tests/
│   ├── unit/
│   ├── api/
│   ├── migration/
│   ├── retrieval/
│   ├── security/
│   └── integration/
├── docs/
├── artifacts/
└── scripts/
```

Use project-prefixed filenames for clarity.

---

## 8. Layer Responsibilities

### API layer

- Validates HTTP input.
- Authenticates and authorizes clients.
- Calls application services.
- Maps stable public errors.
- Contains no SQL or ranking logic.

### Service layer

- Owns memory and retrieval workflows.
- Enforces lifecycle and policy.
- Coordinates repositories in transactions.

### Repository layer

- Owns SQL and persistence mapping.
- Does not generate conversational responses.
- Does not call external AI services.

### Retrieval layer

- Normalizes queries.
- Applies filters and FTS5.
- Produces deterministic rank and match reasons.
- Detects conflicts and superseded records.

### Database layer

- Owns connection, schema, migrations, pragmas, and backup integrity.

---

## 9. Canonical Memory Model

A durable memory should support these fields or their approved equivalents:

```text
memory_id
subject
memory_type
scope
content
search_text
structured_value
aliases
tags
source
language
status
version
supersedes_memory_id
created_at
updated_at
```

Rules:

- IDs are server-generated and stable.
- `subject` is explicit.
- `memory_type` and `scope` use approved values.
- `content` is human-readable.
- `structured_value` stores typed facts when useful.
- `search_text` is optimized for deterministic retrieval.
- Deleted or superseded records are excluded by default.
- Schema changes require migration tests.

---

## 10. Write and Idempotency Rules

Memory creation is a side effect.

- Accept an idempotency key for retried client requests.
- Duplicate idempotency keys return the original result.
- Do not create duplicate memories after transport retries.
- Validate maximum content, alias, tag, and structured-value sizes.
- Reject prohibited sensitive data.
- Do not silently merge conflicting memories.

Updates require optimistic concurrency or an equivalent expected-version check.

Deletion is not exposed to ordinary voice clients. Administrative deletion requires explicit ID, authorization, and confirmation policy at the caller.

---

## 11. Retrieval Rules

Search requests should support bounded filters:

```text
subject
memory_types
scopes
tags
search_terms
vocabulary_terms
limit
include_superseded, default false
```

Search results include:

```text
memory_id
content
structured_value
score
match_reasons
status
version
conflicts
```

Rules:

- Maximum result count is bounded.
- Maximum response size is bounded.
- Match reasons are explainable.
- No raw database dump.
- No hidden cross-subject search without authorization.
- Ranking changes require regression tests.

---

## 12. Vocabulary Rules

Household vocabulary resolves subject-specific terms such as room aliases or preference phrases.

- Resolution is subject-aware.
- Exact and alias matches are distinguishable.
- Ambiguous results return conflicts rather than guesses.
- Vocabulary terms do not grant tool permissions.
- Vocabulary values must not contain executable instructions.

---

## 13. API Contract Rules

Initial candidate operations:

```text
Create memory
Search memory
Get bounded context
Resolve vocabulary
Update memory
Forget memory, administrative only
Health and readiness
```

For every endpoint define:

- Method and path.
- Authentication.
- Request schema.
- Response schema.
- Stable error codes.
- Side-effect classification.
- Idempotency.
- Timeout behavior.
- Maximum sizes.

Generated OpenAPI must match the implementation and committed approved snapshot.

---

## 14. Stable Error Rules

Use stable public errors such as:

```text
VALIDATION_ERROR
AUTHENTICATION_REQUIRED
PERMISSION_DENIED
SENSITIVE_DATA_REJECTED
NOT_FOUND
CONFLICT
VERSION_CONFLICT
RATE_LIMITED
DATABASE_UNAVAILABLE
MIGRATION_REQUIRED
INTERNAL_ERROR
```

Do not expose SQL, filesystem paths, tokens, or stack traces.

---

## 15. Security and Privacy Rules

- Deny unauthenticated access.
- Use separate client credentials.
- Store secrets in mounted files or approved secret injection.
- Enforce subject-level access where applicable.
- Redact content in logs and metrics.
- Reject security credentials and prohibited sensitive data.
- Treat stored content as untrusted when returned to an LLM through MCP.
- Do not execute instructions contained in memories.
- Backups receive the same protection as the live database.

---

## 16. Database and Migration Rules

- Use explicit migrations.
- Never modify production schema implicitly at import time without migration control.
- Migrations are transactional where SQLite permits.
- Every migration has upgrade tests and backup/restore evidence.
- FTS rebuild behavior is documented and tested.
- Configure SQLite pragmas deliberately and document production values.
- One canonical process owns writes unless a reviewed concurrency design states otherwise.

---

## 17. Backup and Restore Rules

- Backups use a SQLite-safe method.
- Restore is tested, not assumed.
- Backup filenames contain no sensitive user content.
- Retention policy is documented.
- Restoration validates schema version and integrity.
- MCP and Numchoke are not required to perform database recovery.

---

## 18. Observability Rules

Structured logs may include:

```text
timestamp
level
service
request_id
client_profile
operation
result_code
duration_ms
result_count
```

Do not log full memory content, search queries, structured values, tokens, or database files by default.

Metrics use bounded labels only.

Audit write, update, delete, permission denial, and sensitive-data rejection with safe metadata.

---

## 19. Configuration Rules

Use typed configuration.

Expected configuration families:

```text
SAMJON_MEMORY_*
SAMJON_DATABASE_*
SAMJON_SECURITY_*
SAMJON_LIMITS_*
```

No default may contain production tokens, personal data, or private network addresses.

---

## 20. Documentation Sync Rule

After every externally visible behavior change, review affected canonical documentation.

Update documentation when API, schema, capability, configuration, migration, retrieval, error, security, backup, or integration behavior changes.

Internal refactoring with unchanged observable behavior does not require a documentation update.

Before completion, report one of:

```text
Documentation updated: <files>
Documentation unchanged: no externally visible behavior changed
Documentation update blocked: <reason>
```

Do not create a new Markdown report for every task. Update canonical documents and place validation evidence under `artifacts/reports/`.

---

## 21. Testing Requirements

Tests must cover:

- API validation and authentication.
- Idempotent creation.
- Optimistic update conflict.
- Sensitive-data rejection.
- FTS retrieval and filters.
- Aliases and vocabulary.
- Supersession and deletion defaults.
- Ranking and match reasons.
- Migration upgrade.
- Backup and restore integrity.
- Subject isolation.
- Response-size and result-count limits.
- Database unavailable behavior.
- OpenAPI drift.

Normal tests use temporary databases and never production data.

---

## 22. Editing Policy

- Prefer minimal controlled patches.
- Do not refactor unrelated files.
- Keep SQL in repositories/database layer.
- Keep API routes thin.
- Do not add an LLM dependency to solve retrieval problems.
- Do not weaken privacy policy to make a test pass.
- Preserve backward compatibility unless a new contract version is approved.
- Add regression tests with bug fixes.

Final reports include problem, root cause, files changed, contract impact, migration impact, security impact, exact tests, results, and limitations.

---

## 23. Task Scope Rules for Cline

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
HomeAI/docs/blueprints/
```

Do not modify an MCP consumer to hide a Samjon Memory API defect.

Before editing, state files to read, files to change, API or migration impact, security impact, and test plan.

---

## 24. Initial Development Sequence

```text
1. Scaffold service, configuration, tests, and documentation.
2. Define memory model and migration strategy.
3. Implement SQLite connection and first schema.
4. Implement repositories and transactional service layer.
5. Implement create memory with idempotency.
6. Implement deterministic search and FTS5.
7. Implement vocabulary resolution.
8. Implement bounded context.
9. Implement update and administrative forget.
10. Export and review OpenAPI.
11. Add security, backup, migration, and restore tests.
12. Produce MCP integration documents for Samjon Home MCP.
```

---

## 25. Release Blocking Conditions

Block release when:

- External services access SQLite directly.
- Conversation history is stored automatically as durable memory.
- Sensitive credentials can be stored.
- Writes are non-idempotent under retries.
- Migrations lack tests.
- Search crosses subjects without authorization.
- Responses can dump unbounded data.
- Raw memory content appears in logs by default.
- API/OpenAPI contracts drift.
- Embeddings or LLM calls are added without ADR.
- Backup restore is untested.

---

## 26. Final Engineering Principle

```text
Samjon stores explicit durable knowledge.
SQLite and FTS5 provide deterministic behavior first.
REST is the backend boundary.
MCP is an external adapter.
Conversation context is not durable memory.
Evidence accompanies retrieval.
Privacy and auditability override convenience.
```
