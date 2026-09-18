# Core Backup and Restore

**Document ID:** SAMJON-CBR-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Core backup and restore for Samjon Memory Core V1.

## 2. Backup Procedure

1. Copy samjon_core.sqlite
2. Verify schema_metadata exists
3. Verify all tables exist

## 3. Restore Procedure

1. Restore samjon_core.sqlite from backup
2. Validate schema version
3. Run ensure_schema() if needed
4. Test isolated restore
