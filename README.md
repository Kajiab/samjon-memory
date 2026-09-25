# Samjon Memory

Samjon Memory is a **local, durable household-knowledge backend** for personal
AI assistants. It stores explicit, structured facts a household cares about —
preferences, vocabulary and aliases, device and location notes, music, plants,
inventory, recipes, and any user-confirmed knowledge — as **Memories** and
**Collections** in a small, predictable stack built on SQLite and FastAPI.

Nothing is extracted from conversations automatically. Durable knowledge is
created only when you (or an approved client) explicitly write it, with its
subject, source, and scope recorded.

> This backend is not a chatbot and does not implement MCP itself. It exposes a
> documented REST API and a human Portal so that a separate assistant / MCP
> adapter (a different repository) can read and manage knowledge over HTTP.

## Current capabilities

- **Memories and Collections** — standalone facts and ordered, independently
  editable Collections of sections.
- **Lifecycle management** — draft → active, versioned edits with optimistic
  concurrency, supersede, forget (soft delete), restore, and a guarded,
  admin-only **purge** (30-day retention, `PURGE` confirmation, tombstone).
- **Deterministic Resolver** — a derived, rebuildable search projection.
- **Exact, prefix, and Thai infix search** — deterministic FTS5 ranking with
  alias, vocabulary, and tag boosts; no recency, no randomness.
- **FTS5 projection** — normalized search documents plus derived expansion maps.
- **Freshness evidence** — every result carries fresh / stale / missing /
  orphaned state derived from the current Core version and checksum.
- **Bounded Collection context** — retrieval is capped and explained; a
  Collection result does not silently include every section.
- **Media** — image covers and galleries for Memories and Collections
  (originals + thumbnails), with per-entity lifecycle and backup.
- **Library and Reader views** — a calm, cover-first reading surface for the
  household knowledge base.
- **Jinja2 Portal** — a single server-rendered Portal (no SPA).
- **Authenticated Administration** — exactly one configured household admin
  via HTTP Basic with exact Origin validation for mutations.
- **Docker deployment** — a portable container running as a non-root user.
- **Host bind-mounted databases and media** — durable data lives on the host
  under `./data/` and is never baked into the image.
- **External category covers** — replaceable cover images bind-mounted from
  `./category-covers/` (no image rebuild required).

Not implemented and out of scope for this backend: semantic / vector search,
embeddings, AI enrichment, completed MCP or Numchoke integration, public
multi-user support, and production Internet exposure.

## Architecture

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
```

- **Core** — authoritative Memories and Collections (`samjon_core.sqlite`).
- **Resolver** — deterministic retrieval projection (`samjon_resolver.sqlite`),
  fully disposable and rebuildable.
- **Media** — images, covers, thumbnails, and media lifecycle under
  `data/media/` (metadata in Core).
- **Portal** — a Jinja2-rendered Library and Administration interface.
- **Docker** — portable deployment with host bind mounts.

Projection flow is one-way (Core → Resolver). The Resolver never writes facts
into Core, and no external service opens either SQLite file directly.

## Quick start with Docker

Prerequisites: Docker Engine with the Compose plugin (Docker Desktop covers
both).

```powershell
# 1) Configure (no safe defaults for secrets)
Copy-Item .env.docker.example .env
#    edit .env and set SAMJON_PORTAL_USERNAME / SAMJON_PORTAL_PASSWORD (and,
#    for a production-like deployment, the REST API tokens)

# 2) Build and start; creates ./data and ./category-covers host dirs first
powershell -ExecutionPolicy Bypass -File .\scripts\docker-up.ps1
#    equivalent: docker compose up -d --build
```

Core/Resolver migrations run automatically on startup. Stop the stack with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\docker-down.ps1
```

## Local development

```powershell
# Create a config from the template
Copy-Item .env.example .env
#    set SAMJON_PORTAL_USERNAME / SAMJON_PORTAL_PASSWORD and source the file
#    (or export the variables) before running

python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# Run locally (uvicorn on 127.0.0.1:8100)
powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1
```

## Portal URL

The human-facing Portal is served at:

```text
http://localhost:8100/portal/
```

All Portal routes require HTTP Basic credentials (the single configured admin).
The actual host port is configurable via `SAMJON_CORE_PORT` (default `8100`),
so the URL changes accordingly when you change the port.

## Runtime data locations

| Path | Purpose |
| ---- | ------- |
| `./data/samjon_core.sqlite` | Authoritative Core database (backup-critical) |
| `./data/samjon_resolver.sqlite` | Derived, rebuildable Resolver database |
| `./data/media/` | Media originals, thumbnails, and archived files |
| `./category-covers/` | External category covers (bind-mounted, read-only) |

These paths are configurable via `SAMJON_CORE_DATABASE_PATH`,
`SAMJON_RESOLVER_DATABASE_PATH`, `SAMJON_MEDIA_ROOT`, and
`SAMJON_CATEGORY_COVERS_ROOT`. In Docker the container paths are fixed
under `/app/` and mapped to host bind mounts.

## Backup and restore

- **Core** — backup `samjon_core.sqlite` (SQLite-safe method), plus the Media
  files under `data/media/`. Restore is verified in isolation before use.
- **Resolver** — normally **rebuilt** rather than restored; it holds no
  durable facts.
- Backups must be protected like the live database (they contain household
  knowledge).

## Testing

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test-local.ps1
#   or
python -m pytest tests/ -q
```

The full suite (migrations, Core lifecycle, idempotency, Resolver projection /
search / ranking / freshness / rebuild, Media, Portal security and workflows,
Docker packaging, OpenAPI drift) passes:

```text
453 passed, 0 failed
```

## Security notes

- The Portal exposes **exactly one** configured household administrator (HTTP
  Basic). No users table, no registration, no session cookies, no roles.
- All Portal mutations validate the request **Origin** against
  `SAMJON_PORTAL_ALLOWED_ORIGINS` (exact scheme + host + port).
- Plain HTTP Basic is approved only for localhost and an explicitly trusted
  household LAN. The default local bind is `127.0.0.1`; direct public Internet
  exposure is prohibited.
- REST API access uses separate service / admin / read tokens.
- Credentials and full fact content are never logged by default.
- Stored content and Resolver projections are treated as untrusted input.
- Protected/sensitive credentials and raw audio are rejected as Memory.

## Current exclusions

- No semantic / vector search or embeddings.
- No AI enrichment or automatic fact extraction from conversation.
- No MCP transport or MCP tool registration (`samjon-memory` does not
  implement MCP; the independent Samjon Home MCP adapter is a separate work
  item and repository).
- No Numchoke integration.
- No public multi-user support or user registration.
- No production Internet exposure of the Portal.

## Documentation links

- [`docs/SAMJON_MEMORY_STATUS.md`](docs/SAMJON_MEMORY_STATUS.md) — current implementation status
- [`docs/DOCUMENT_INDEX.md`](docs/DOCUMENT_INDEX.md) — documentation map
- [`docs/current/architecture.md`](docs/current/architecture.md) — runtime architecture
- [`docs/current/capabilities.md`](docs/current/capabilities.md) — proven capabilities
- [`docs/api/openapi.json`](docs/api/openapi.json) — OpenAPI specification
- [`docs/core/data-model.md`](docs/core/data-model.md) — data model
- [`docs/core/memory-lifecycle.md`](docs/core/memory-lifecycle.md) — lifecycle
- [`docs/resolver/RESOLVER_V1_SPEC.md`](docs/resolver/RESOLVER_V1_SPEC.md) — Resolver specification
- [`docs/core/media-foundation.md`](docs/core/media-foundation.md) — Media foundation
- [`docs/current/web-portal.md`](docs/current/web-portal.md) — Portal features
- [`docs/deployment/docker.md`](docs/deployment/docker.md) — Docker deployment
- [`docs/operations/core-backup-restore.md`](docs/operations/core-backup-restore.md) — backup & restore
- [`docs/security/portal-security.md`](docs/security/portal-security.md) — Portal security
- [`docs/operations/troubleshooting.md`](docs/operations/troubleshooting.md) — troubleshooting

## License

No license file is present in this repository yet.
