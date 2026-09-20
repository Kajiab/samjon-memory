# API Contract

**Document ID:** SAMJON-API-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

REST API contract for Samjon Memory Core V1.

## 2. Endpoints

### Memory
- POST /api/v1/core/memories - Create memory
- GET /api/v1/core/memories/{memory_id} - Get memory
- PATCH /api/v1/core/memories/{memory_id} - Update memory
- POST /api/v1/core/memories/query - Query memories
- POST /api/v1/core/memories/{memory_id}/supersede - Supersede memory
- POST /api/v1/core/memories/{memory_id}/forget - Forget memory
- POST /api/v1/core/memories/{memory_id}/activate - Activate memory (draft -> active)
- POST /api/v1/core/memories/{memory_id}/restore - Restore forgotten memory (-> draft)
- POST /api/v1/core/memories/{memory_id}/purge - Purge forgotten memory (admin, hard erase)

### Collection
- POST /api/v1/core/collections - Create collection
- GET /api/v1/core/collections/{collection_id} - Get collection
- PATCH /api/v1/core/collections/{collection_id} - Update collection
- GET /api/v1/core/collections/{collection_id}/memories - List collection memories
- POST /api/v1/core/collections/{collection_id}/memories - Add memory to collection
- PUT /api/v1/core/collections/{collection_id}/order - Reorder collection
- POST /api/v1/core/collections/{collection_id}/activate - Activate collection
- GET /api/v1/core/collections/{collection_id}/validate - Validate collection
- POST /api/v1/core/collections/{collection_id}/restore - Restore forgotten collection (-> draft)
- POST /api/v1/core/collections/{collection_id}/purge - Purge forgotten collection (admin, hard erase)

### Audit
- GET /api/v1/core/audit - List audit records (filters: entity_id, entity_type, action, since, until)
- GET /api/v1/core/audit/stats - Audit statistics (counts grouped by action)

## 3. Headers

- X-Idempotency-Key - Idempotency key
- X-Service-Token - Service authentication
- X-Admin-Token - Admin authentication
- actor - Actor header
