# Deployment

**Document ID:** SAMJON-DEP-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Deployment for Samjon Memory Core V1.

## 2. Supported Deployment

- Standalone FastAPI service
- Two separate SQLite databases (Core + Resolver)
- Media stored under a configurable media root
- Environment variables for configuration
- Docker deployment (Dockerfile + compose.yaml, bind mounts) — see
  [`docs/deployment/docker.md`](../deployment/docker.md)

## 3. Configuration

Core:

- SAMJON_CORE_DATABASE_PATH
- SAMJON_CORE_SERVICE_TOKEN
- SAMJON_CORE_ADMIN_TOKEN
- SAMJON_CORE_READ_TOKEN
- SAMJON_CORE_HOST
- SAMJON_CORE_PORT
- SAMJON_CORE_CORS_ORIGINS
- SAMJON_CORE_IDEMPOTENCY_TTL_HOURS
- SAMJON_CORE_PORTAL_ENABLED
- SAMJON_CORE_LOG_LEVEL
- SAMJON_CORE_MAX_RAW_CONTENT_CHARS
- SAMJON_CORE_MAX_RAW_CONTENT_BYTES
- SAMJON_CORE_MAX_QUERY_LIMIT
- SAMJON_CORE_ENV

Resolver:

- SAMJON_RESOLVER_DATABASE_PATH
- SAMJON_RESOLVER_FTS5_REQUIRED

Media:

- SAMJON_MEDIA_ROOT
- SAMJON_MEDIA_MAX_UPLOAD_BYTES
- SAMJON_MEDIA_MAX_WIDTH / SAMJON_MEDIA_MAX_HEIGHT
- SAMJON_MEDIA_THUMB_WIDTH / SAMJON_MEDIA_THUMB_HEIGHT
- SAMJON_MEDIA_MAX_PER_ENTITY
- SAMJON_MEDIA_MAX_ALT_TEXT / SAMJON_MEDIA_MAX_CAPTION

Category covers:

- SAMJON_CATEGORY_COVERS_ROOT (external cover directory, e.g. Docker bind mount)

Portal:

- SAMJON_PORTAL_USERNAME
- SAMJON_PORTAL_PASSWORD
- SAMJON_PORTAL_ALLOWED_ORIGINS

Lifecycle:

- SAMJON_LIFECYCLE_PURGE_MIN_AGE_DAYS (default 30)
- SAMJON_LIFECYCLE_AUTOMATIC_PURGE_ENABLED (default false)
- SAMJON_LIFECYCLE_PURGE_CONFIRMATION (default "PURGE")
