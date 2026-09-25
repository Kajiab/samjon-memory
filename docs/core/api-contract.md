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
- POST /api/v1/core/collections/{collection_id}/memories - Add Section: creates a Memory that inherits subject/scope from the Collection; `title` is the section name (client subject/scope must match the Collection else rejected)
- PUT /api/v1/core/collections/{collection_id}/order - Reorder collection
- POST /api/v1/core/collections/{collection_id}/activate - Activate collection
- GET /api/v1/core/collections/{collection_id}/validate - Validate collection
- POST /api/v1/core/collections/{collection_id}/restore - Restore forgotten collection (-> draft)
- POST /api/v1/core/collections/{collection_id}/purge - Purge forgotten collection (admin, hard erase)

Collection consistency invariant:
- Every Section inherits `subject`/`scope` from its Collection; `title` is the section name
- Moving an existing Memory into a Collection requires matching `subject`/`scope`; a mismatch is rejected with no change
- A Collection with existing Sections cannot change its `subject`/`scope`
- Collection ordering is by `sequence_number` ASC

### Audit
- GET /api/v1/core/audit - List audit records (filters: entity_id, entity_type, action, since, until)
- GET /api/v1/core/audit/stats - Audit statistics (counts grouped by action)

### Health / readiness
- GET /health
- GET /ready

> The exact, authoritative route set is always the generated
> [`docs/api/openapi.json`](../api/openapi.json); this list is a summary. All
> Media and Resolver additions are additive and non-breaking.

## 3. Media endpoints (summary)

- POST /api/v1/core/media - Upload an image for a Memory or Collection
- GET /api/v1/core/media - List media for an entity
- PATCH /api/v1/core/media/{media_id} - Update alt text / caption / cover
- DELETE /api/v1/core/media/{media_id} - Remove (hide) media
- GET /api/v1/core/media/{media_id}/original - Serve original bytes
- GET /api/v1/core/media/{media_id}/thumbnail - Serve thumbnail bytes
- POST /api/v1/core/media/{media_id}/cover - Set as cover
- POST /api/v1/core/media/{media_id}/reorder - Change display order
- POST /api/v1/core/media/{media_id}/replace - Replace file (new checksum)
- POST /api/v1/core/media/{media_id}/purge - Purge media (admin)

> The Portal media routes (`/portal/media/...`) provide the same operations with
> HTTP Basic + exact Origin. See [`docs/core/media-foundation.md`](media-foundation.md).

## 4. Resolver endpoints (summary)

- GET /resolver/ready - Resolver readiness (independent of Core)
- POST /api/v1/resolver/query - Deterministic search (read token)
- POST /api/v1/resolver/rebuild - Full projection rebuild (admin token)
- GET /api/v1/resolver/rebuild/status - Rebuild status (read token)
- GET /api/v1/resolver/projection/status - Projection state (read token)
- POST /api/v1/resolver/rebuild/selective - Selective rebuild of one entity (admin token)

## 5. Headers

- X-Idempotency-Key - Idempotency key
- X-Service-Token - Service authentication
- X-Admin-Token - Admin authentication
- actor - Actor header
