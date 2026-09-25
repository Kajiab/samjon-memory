# Samjon Memory Document Index

**Document ID:** SAMJON-MEMORY-DOC-INDEX-001
**Version:** 3.0.0
**Status:** Canonical
**Owner:** Samjon Memory Engineering
**Last reviewed:** 2026-09-25

## 1. Purpose

This is the reading map for Samjon Memory. The public entry point is
[`README.md`](../README.md); the documents below describe the current, verified
implementation and are kept in sync with it.

## 2. Reading map

| Area | Guide |
| ---- | ----- |
| Repository entry | [`README.md`](../README.md) |
| Agent rules | [`AGENTS.md`](../AGENTS.md) |
| Current status | [`docs/SAMJON_MEMORY_STATUS.md`](SAMJON_MEMORY_STATUS.md) |
| Architecture | [`docs/current/architecture.md`](current/architecture.md) |
| Capabilities | [`docs/current/capabilities.md`](current/capabilities.md) |
| Data ownership / privacy | [`docs/current/data-ownership.md`](current/data-ownership.md) |
| API / OpenAPI | [`docs/api/openapi.json`](api/openapi.json) · [`docs/core/api-contract.md`](core/api-contract.md) · [`docs/api/error-contract.md`](api/error-contract.md) |
| Core lifecycle | [`docs/core/data-model.md`](core/data-model.md) · [`docs/core/memory-lifecycle.md`](core/memory-lifecycle.md) · [`docs/core/migration-policy.md`](core/migration-policy.md) |
| Resolver | [`docs/resolver/RESOLVER_V1_SPEC.md`](resolver/RESOLVER_V1_SPEC.md) · [`docs/resolver/schema-and-migrations.md`](resolver/schema-and-migrations.md) · [`docs/resolver/search-ranking-and-freshness.md`](resolver/search-ranking-and-freshness.md) · [`docs/resolver/rebuild-and-test-plan.md`](resolver/rebuild-and-test-plan.md) · [`docs/resolver/RESOLVER_V1_FREEZE_EVALUATION.md`](resolver/RESOLVER_V1_FREEZE_EVALUATION.md) |
| Media | [`docs/core/media-foundation.md`](core/media-foundation.md) |
| Portal | [`docs/current/web-portal.md`](current/web-portal.md) |
| Docker / deployment | [`docs/deployment/docker.md`](deployment/docker.md) · [`docs/operations/deployment.md`](operations/deployment.md) |
| Security | [`docs/security/portal-security.md`](security/portal-security.md) · [`docs/security/privacy-policy.md`](security/privacy-policy.md) |
| Backup / restore | [`docs/core/backup-restore.md`](core/backup-restore.md) · [`docs/operations/core-backup-restore.md`](operations/core-backup-restore.md) |
| Troubleshooting | [`docs/operations/troubleshooting.md`](operations/troubleshooting.md) |
| Integration smoke test | [`docs/integration/home-assistant-smoke-test.md`](integration/home-assistant-smoke-test.md) |

## 3. Historical documents

These documents record earlier milestones and remain for historical evidence;
they are not active change targets.

- [`docs/core/CORE_V1_FREEZE.md`](core/CORE_V1_FREEZE.md) — Core V1 freeze
  record (commit `9ca5d57`, Core schema 1.0.0/1.1.0 era; Core is now 1.2.0).
- [`docs/design/forget-restore-purge.md`](design/forget-restore-purge.md) —
  lifecycle design spec; implemented (Core schema 1.1.0+).
- [`docs/core/subject-type-guidelines.md`](core/subject-type-guidelines.md) —
  subject / type conventions.

## 4. Authority

Executable code, migrations, generated OpenAPI, tests, and Docker files are
authoritative over this documentation. When prose and implementation conflict,
follow the implementation.




