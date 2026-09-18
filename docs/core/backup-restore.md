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
- Validate schema version
- Run ensure_schema() if needed
- Isolated restore test required
