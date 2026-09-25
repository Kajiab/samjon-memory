# Data Model

**Document ID:** SAMJON-DM-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Data model for Samjon Memory Core V1.

## 2. Entities

### memory_collection
- collection_id, subject, collection_type, scope, title, summary, language, source, source_reference, status, version, supersedes_collection_id, expected_item_count, content_checksum, created_at, updated_at, forgotten_at, purged_at, purged_by

### memory
- memory_id, collection_id, sequence_number, subject, memory_type, scope, title, section_path, raw_content, structured_value_json, source, language, status, version, supersedes_memory_id, content_checksum, created_at, updated_at, forgotten_at, purged_at, purged_by

### durable_alias
- alias_id, subject, alias, language, source, status, version, supersedes_alias_id, content_checksum, created_at, updated_at

### durable_vocabulary
- vocabulary_id, term, definition, language, source, status, version, supersedes_vocabulary_id, content_checksum, created_at, updated_at

### durable_user_tag
- tag_id, subject, tag, language, source, status, version, supersedes_tag_id, content_checksum, created_at, updated_at

### manual_override
- override_id, subject, scope, key, value_json, source, status, version, supersedes_override_id, content_checksum, created_at, updated_at

### idempotency_record
- idempotency_key, request_hash, operation, resulting_entity_type, resulting_entity_id, created_at, expires_at

### audit_log
- audit_id, entity_type, entity_id, action, actor, source, version, details_json, created_at

### lifecycle_tombstone
- tombstone_id, entity_type, entity_id, final_version, content_checksum, purged_at, actor

### media
- media_id, entity_type ('memory'|'collection'), entity_id, relative_path,
  thumbnail_path, mime_type (jpeg/png/webp), file_size, width, height,
  alt_text, caption, display_order, is_cover, checksum,
  lifecycle_status ('active'|'hidden'|'purged'), created_at, updated_at
- Only one `is_cover=1` row per entity (enforced in the service)
- Binary bytes and absolute filesystem paths are never stored

## 3. Constraints

- raw_content <= 16384 chars
- title <= 500 chars
- alias <= 200 chars
- tag <= 80 chars
- status IN (draft, active, superseded, forgotten)

## 4. Lifecycle & purge

- A purged row is a tombstone: `raw_content` is emptied, `title`/`section_path`/`structured_value_json` cleared, and `purged_at`/`purged_by` set. Identity, `content_checksum`, and `version` are retained.
- Purged entities cannot be restored, edited, activated, or reused.
- `lifecycle_tombstone` records each hard-erased entity (identity + final version + checksum + actor).

## 5. Collection subject/scope consistency (invariant)

- A new Collection **Section** inherits `subject` and `scope` from its Collection;
  `title` is used only as the section name (never as a fallback subject).
- Moving an existing Memory into a Collection is allowed only when the Memory's
  `subject` and `scope` both match the Collection's; a mismatch is rejected
  without changing the Memory or the Collection.
- A Collection that already has Sections cannot change its `subject` or `scope`.
- Collection ordering is by `sequence_number` ASC.
