# Backup and Restore

**Document ID:** SAMJON-BR-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Backup and restore for Samjon Memory Core V1.

## 2. Backup

- Copy samjon_core.sqlite
- Verify schema_metadata exists
- Verify all tables exist

## 3. Restore

- Restore samjon_core.sqlite from backup
- Validate schema version (1.1.0)
- Run ensure_schema() if needed
- Isolated restore test required

## 4. Lifecycle / Purge note

- Purge hard-erases content (irreversible); backups are the only recovery path
- Purged records keep an identity tombstone + lifecycle audit
- Purge-admin action is audit-logged (`memory_purge` / `collection_purge`)
