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
| Collection lifecycle | PROVEN | draft/active/reorder/validate |
| Durable metadata | PROVEN | alias/vocabulary/tag/manual_override |
| Idempotency | PROVEN | header-based |
| Audit | PROVEN | audit_log table |
| Backup/restore | PROVEN | isolated restore |
| Sensitive data rejection | PROVEN | credential detection |
| Web Portal | PROVEN | HTML portal |
| OpenAPI | PROVEN | drift test |

## 3. Limitations

- No FTS5
- No Resolver/FTS5/embeddings/MCP/AI
- No semantic search
- No AI enrichment
