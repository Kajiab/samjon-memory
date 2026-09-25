# Architecture

**Document ID:** SAMJON-ARCH-001
**Version:** 2.0.0
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering
**Last reviewed:** 2026-09-25

## 1. Purpose

Runtime architecture for the current Samjon Memory backend (Core, Resolver,
Media, Portal, Docker).

## 2. Architecture

```text
        Client / Assistant / MCP adapter
                    |
                    v
        Samjon Memory REST API  :8100
                    |
          +---------+---------+---------+
          |         |         |         |
          v         v         v         v
        Core     Resolver   Media    Portal
    (author.  (derived   (images,  (Jinja2,
     SQLite)   search)    covers)   Library + Admin)
 samjon_core  samjon_    data/media
 .sqlite      resolver.sqlite

 Runtime data (Docker: host bind mounts)
 ./data            -> /app/data
 ./category-covers -> /app/category-covers (read-only)
```

## 3. Components

- **Core** — authoritative Memories and Collections; Durable manual metadata;
  lifecycle (activate / restore / purge), audit, idempotency, Media metadata.
  Backed by `samjon_core.sqlite` (schema 1.2.0).
- **Resolver** — deterministic retrieval projection: FTS5 search, exact /
  prefix / Thai infix matching, freshness evidence, bounded Collection
  context. Backed by `samjon_resolver.sqlite` (schema 1.1.0), disposable and
  rebuildable. Qualifies: `/resolver/ready`, `/api/v1/resolver/*`.
- **Media** — image covers and galleries; originals + thumbnails under
  `data/media/`; metadata in Core.
- **Portal** — server-rendered Library + Administration, rendered from Jinja2
  templates; HTTP Basic (one configured admin) + exact Origin validation for
  mutations. No SPA, no direct database access.
- **API layer** — REST endpoints (memory, collection, audit, resolver).
- **Database layer** — two independent SQLite databases, foreign keys on, WAL,
  busy timeout.
- **Lifecycle** — activate / restore / purge (with audit + tombstones).
- **Security** — HTTP Basic (Portal) + service tokens (API).
- **Audit** — append-only audit log (summary, filters, pagination).
- **Docker** — single container, non-root user, single worker; host bind
  mounts for runtime data and external category covers.

## 4. Data ownership

```text
Core -> authoritative Memories and Collections
Resolver -> derived, rebuildable retrieval projection (never writes Core)
Media -> images, covers, thumbnails, lifecycle
Portal -> Jinja2 Library + Administration (CoreService only)
Docker -> portable deployment with host bind mounts
```

Projection flow is one-way: Core → Resolver. The Resolver never writes facts
into Core, and no external service opens either SQLite file directly.

## 5. Boundaries

- Core owns durable knowledge.
- Resolver returns matches and evidence; authoritative content is loaded from
  Core.
- Portal handlers use CoreService / ResolverService only; they never open
  SQLite, repositories, or the media filesystem directly.
- External MCP modules (future / separate repository) must call Samjon Memory
  through the REST API only.
- Core does not call OpenRouter, select models, or implement skills; no
  semantic search, embeddings, or AI enrichment in the backend.
