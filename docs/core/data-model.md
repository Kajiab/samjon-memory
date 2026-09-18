# Data Model

**Document ID:** SAMJON-DM-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Data model for Samjon Memory Core V1.

## 2. Entities

### memory_collection
- collection_id, subject, collection_type, scope, title, summary, language, source, source_reference, status, version, supersedes_collection_id, expected_item_count, content_checksum, created_at, updated_at

### memory
- memory_id, collection_id, sequence_number, subject, memory_type, scope, title, section_path, raw_content, structured_value_json, source, language, status, version, supersedes_memory_id, content_checksum, created_at, updated_at

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

## 3. Constraints

- raw_content <= 16384 chars
- title <= 500 chars
- alias <= 200 chars
- tag <= 80 chars
- status IN (draft, active, superseded, forgotten)
