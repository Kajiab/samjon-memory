# Proven Capabilities

**Document ID:** SAMJON-CAP-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Proven capabilities for Samjon Memory Core V1.

## 2. Capabilities

| Capability | Status | Notes |
|---|---|---|
| SQLite schema | PROVEN | migrations.py |
| Core memory CRUD | PROVEN | create/get/update/query/supersede/forget |
| Memory activate | PROVEN | draft -> active, version bump, audit |
| Restore | PROVEN | forgotten -> draft, version bump, audit |
| Purge | PROVEN | irreversible, forgotten >= 30 days, admin + "PURGE" confirmation, tombstone |
| Collection lifecycle | PROVEN | draft/active/reorder/validate/restore/purge |
| Durable metadata | PROVEN | alias/vocabulary/tag/manual_override; erased on memory purge |
| Idempotency | PROVEN | header-based |
| Audit | PROVEN | audit_log; summary, filters, pagination |
| Dashboard metrics | PROVEN | Memories / Collections / System Overview |
| Administration page | PROVEN | forgotten/purged, retention, schema/db status |
| Backup/restore | PROVEN | isolated restore |
| Sensitive data rejection | PROVEN | credential detection |
| Web Portal | PROVEN | HTML portal, server-rendered |
| HTTP Basic Authentication | PROVEN | single admin, env config |
| Exact Origin validation | PROVEN | SAMJON_PORTAL_ALLOWED_ORIGINS |
| Add Section auto-generates Memory ID | PROVEN | backend generates ID |
| Collection Memories sorted by sequence_number ASC | PROVEN | Move Up/Down buttons correct |
| OpenAPI | PROVEN | drift test |

## 3. Limitations

- No FTS5
- No Resolver/FTS5/embeddings/MCP/AI
- No semantic search
- No AI enrichment
