# Core Backup and Restore

**Document ID:** SAMJON-CBR-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Core backup and restore for Samjon Memory Core V1.

## 2. Backup Procedure

1. Copy samjon_core.sqlite
2. Copy media files under `data/media/` (originals + thumbnails) — or use
   `media_create_backup` to package them with a checksummed manifest
3. Verify schema_metadata exists
4. Verify all tables exist

## 3. Restore Procedure

1. Restore samjon_core.sqlite from backup
2. Restore media files under `data/media/` (idempotent; never duplicates)
3. Validate schema version
4. Run ensure_schema() if needed
5. Test isolated restore
