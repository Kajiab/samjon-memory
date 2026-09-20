# Samjon Memory Document Index

**Document ID:** SAMJON-MEMORY-DOC-INDEX-001
**Version:** 2.0.0
**Status:** Canonical
**Owner:** Samjon Memory Engineering
**Last reviewed:** 2026-09-18

## 1. Purpose

This is the documentation entry point and authority map for Samjon Memory.

## 2. Authority Order

1. Executable API, migration, retrieval, security, and restore tests.
2. Current implementation.
3. Generated OpenAPI and schema artifacts.
4. docs/SAMJON_MEMORY_STATUS.md
5. HomeAI/docs/PROJECT_STATUS.md
6. Planning documents.

## 3. Canonical Documents

| Document | Status | Purpose |
|---|---|---|
| README.md | CANONICAL | Setup and repository entry point |
| AGENTS.md | CANONICAL | Agent rules and invariants |
| docs/DOCUMENT_INDEX.md | CANONICAL | Documentation map |
| docs/SAMJON_MEMORY_STATUS.md | CANONICAL | Detailed current implementation status |
| docs/current/architecture.md | CANONICAL | Runtime architecture |
| docs/current/capabilities.md | CANONICAL | Proven capabilities |
| docs/current/data-ownership.md | CANONICAL | Data ownership and privacy |
| docs/current/web-portal.md | CANONICAL | Web portal features and architecture |
| docs/core/data-model.md | CANONICAL | Data model |
| docs/core/memory-lifecycle.md | CANONICAL | Memory lifecycle |
| docs/core/api-contract.md | CANONICAL | API contract |
| docs/core/migration-policy.md | CANONICAL | Migration policy |
| docs/core/backup-restore.md | CANONICAL | Backup and restore |
| docs/api/error-contract.md | CANONICAL | Error contract |
| docs/api/openapi.json | CANONICAL | OpenAPI specification |
| docs/security/privacy-policy.md | CANONICAL | Privacy policy |
| docs/security/portal-security.md | CANONICAL | Portal security |
| docs/operations/deployment.md | CANONICAL | Deployment |
| docs/operations/core-backup-restore.md | CANONICAL | Backup and restore operations |
| docs/operations/troubleshooting.md | CANONICAL | Troubleshooting |
| docs/design/forget-restore-purge.md | CANONICAL | Lifecycle spec (Forget/Restore/Purge) |
| docs/integration/home-assistant-smoke-test.md | CANONICAL | Home Assistant smoke test |

## 4. Documentation Structure

```text
docs/
├── DOCUMENT_INDEX.md
├── SAMJON_MEMORY_STATUS.md
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
├── api/
│   ├── error-contract.md
│   └── openapi.json
├── security/
│   ├── privacy-policy.md
│   └── portal-security.md
├── operations/
│   ├── deployment.md
│   ├── core-backup-restore.md
│   └── troubleshooting.md
├── design/
│   └── forget-restore-purge.md
├── integration/
│   └── home-assistant-smoke-test.md
├── adr/
└── archive/
```

## 5. Cline Reading Map

All tasks:
```text
HomeAI/AGENTS.md
HomeAI/docs/DOCUMENT_INDEX.md
HomeAI/docs/PROJECT_STATUS.md
samjon-memory/AGENTS.md
samjon-memory/docs/DOCUMENT_INDEX.md
samjon-memory/docs/SAMJON_MEMORY_STATUS.md
```

## 6. Capability Register

| Capability | Status | Evidence required |
|---|---|---|
| SQLite schema and migrations | PROVEN | Migration tests |
| Create memory | PROVEN | API and idempotency tests |
| CRUD memory operations | PROVEN | Memory tests |
| Collection lifecycle | PROVEN | Collection tests |
| Memory activate | PROVEN | Lifecycle tests |
| Restore (-> draft) | PROVEN | Lifecycle tests |
| Purge (irreversible, 30-day) | PROVEN | Lifecycle tests |
| Administration page | PROVEN | Admin portal tests |
| Dashboard metrics | PROVEN | Dashboard tests |
| Idempotency | PROVEN | Idempotency tests |
| Durable manual metadata | PROVEN | Schema evidence |
| Audit records | PROVEN | Audit tests |
| Web Portal | PROVEN | Portal tests |
| Backup and restore | PROVEN | Backup tests |
| FTS5 | NOT STARTED | Deferred |
| Semantic search | NOT STARTED | Deferred |
| AI enrichment | NOT STARTED | Deferred |
| Embeddings/vector search | NOT STARTED | ADR required |
| Samjon Home MCP module | NOT STARTED | Pending Core V1 freeze |
| Numchoke integration | NOT STARTED | Pending MCP module |

## 7. Generated Artifacts

```text
docs/api/openapi.json
artifacts/generated/schema.sql
artifacts/generated/migration-inventory.json
artifacts/generated/test-inventory.json
```

## 8. Documentation Update Rules

Update canonical documents for externally visible API, schema, retrieval, migration, security, configuration, backup, or capability changes.

## 9. Current Documentation Tasks

- [x] Create architecture and capabilities documents.
- [x] Define data model and lifecycle.
- [x] Define API and error contracts.
- [x] Define privacy policy.
- [x] Define migration and backup/restore operations.

## 10. Approval Checklist

- [x] REST is the external backend boundary.
- [x] No external database access.
- [x] Deterministic retrieval is documented.
- [x] Durable memory requires explicit source.
- [x] Sensitive-data policy is documented.
- [x] Migrations and restore are tested.
- [x] OpenAPI matches implementation.
- [x] RAG remains deferred unless approved.
