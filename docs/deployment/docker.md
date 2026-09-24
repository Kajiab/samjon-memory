# Samjon Memory - Docker deployment

Containers Samjon Memory (Core, Resolver, Media, Portal) as a self-contained,
production-like local service. The image runs as a non-root user, stores all
durable data under a persistent volume, and needs no host Python or virtual
environment.

- [Files](#files)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Persistence & permissions](#persistence--permissions)
- [Operations](#operations)
- [Security notes](#security-notes)
- [Backup & restore](#backup--restore)
- [Portainer stack](#portainer-stack)
- [Troubleshooting](#troubleshooting)
- [Design decisions](#design-decisions)

## Files

| File | Purpose |
| ---- | ------- |
| `Dockerfile` | Multi-stage build (builder + runtime image) |
| `compose.yaml` | Recommended `docker compose` deployment |
| `.dockerignore` | Keeps tests / venv / data / secrets out of the build context |
| `.env.docker.example` | Template for stack configuration (copy to `.env`) |
| `.env.example` | (repo root) original local-dev template; unaffected |
| `samjon_stack.yaml` | Self-contained Portainer stack (compose-compatible) |
| `scripts/docker-*.ps1` | Convenience wrappers around `docker compose` |
| `docs/deployment/docker.md` | This document |

## Architecture

```
Browser (Portal) / Numchoke (HTTP APIs)
        |
        v
  Samjon Memory container  (python uvicorn, single worker)
        |
        +-- /app/data/samjon_core.sqlite      (Core, authoritative)
        +-- /app/data/samjon_resolver.sqlite  (Resolver, derived/rebuildable)
        +-- /app/data/media/                  (originals, thumbnails, archived)
        |
        v
  named volume: samjon_memory_data:/app/data  (persistent on the host)
```

- The application container is the **only** owner of every SQLite file and media
  file. No other service opens them.
- Future MCP modules must call Samjon Memory through HTTP APIs only - they must
  never mount or open the SQLite files.
- Core/Resolver migrations run automatically on startup (`ensure_schema`), so
  no separate migration step is needed at deploy time.

## Quick start

Prerequisites: Docker Engine with the Compose plugin (Docker Desktop covers both).

```powershell
# 1) Create configuration and set real secrets
Copy-Item .env.docker.example .env
#    edit .env and set at least SAMJON_PORTAL_USERNAME and SAMJON_PORTAL_PASSWORD

# 2) Build and start
powershell -ExecutionPolicy Bypass -File .\scripts\docker-up.ps1
#    equivalent: docker compose up -d --build
```

Then open:

- Portal UI: <http://localhost:8100/portal/> (HTTP Basic - use the Portal credentials)
- Health:  <http://localhost:8100/health>
- Resolver Debug: <http://localhost:8100/portal/resolver/>

On another machine the same commands build and run the service; all state stays
in the `samjon_memory_data` volume, so no host paths need to exist.

## Configuration

Copy `.env.docker.example` to `.env` and edit. Docker Compose reads `.env`
automatically for interpolation into `compose.yaml`.

Required (no safe default):

| Variable | Notes |
| -------- | ----- |
| `SAMJON_PORTAL_USERNAME` | The single household Portal administrator |
| `SAMJON_PORTAL_PASSWORD` | HTTP Basic password for the Portal (strong value) |
| `SAMJON_CORE_SERVICE_TOKEN` | Service token for the REST API |
| `SAMJON_CORE_ADMIN_TOKEN` | Admin token for the REST API |
| `SAMJON_CORE_READ_TOKEN` | Read token for the REST API |

Fixed container layout:

```text
SAMJON_CORE_DATABASE_PATH=/app/data/samjon_core.sqlite
SAMJON_RESOLVER_DATABASE_PATH=/app/data/samjon_resolver.sqlite
SAMJON_MEDIA_ROOT=/app/data/media
```

The full list of tunable variables is in `.env.docker.example`.

## Persistence & permissions

- `compose.yaml` mounts the named volume **`samjon_memory_data`** at `/app/data`.
  Named volumes survive `docker compose down` and container rebuilds.
- The image pre-creates `/app/data` and its subdirectories, owned by the non-root
  `samjon` user (uid/gid `10001`). On first use Docker copies that ownership into
  the new named volume, so the app can write with no privileged entrypoint.
- If you prefer a bind mount (files visible under a host path), replace the
  volume with e.g. `./samjon-data:/app/data`; on Linux the host directory must be
  writable by uid `10001` (`chown -R 10001:10001 ./samjon-data`). The named
  volume avoids this on all platforms.

## Operations

```powershell
.\scripts\docker-build.ps1            # build only
.\scripts\docker-up.ps1               # build + start detached
.\scripts\docker-down.ps1             # stop (data kept)
.\scripts\docker-logs.ps1 -Follow     # follow logs
.\scripts\docker-test.ps1             # build + start + health/Portal smoke test
```

Raw equivalents:

```bash
docker compose build
docker compose up -d --build
docker compose down
docker compose logs -f samjon-memory
```

Health check: compose marks the service healthy once `GET /health` returns
`{"status":"ok"}`.

## Security notes

- The container binds `0.0.0.0:8100` **inside** the container; the host is only
  exposed on the published port (default `8100`). Do not expose the service to
  the public internet; it is intended for an explicitly trusted local network.
- SQLite files are owned only by the `samjon` user inside the container and live
  on a host-persistent volume - never bake them into the image.
- Leave `SAMJON_CORE_ENV=production`. The REST API becomes token-authenticated
  when the three tokens are set; the Portal always requires HTTP Basic.
- Never commit `.env`; it is excluded by `.gitignore` and `.dockerignore`.

## Backup & restore

Back up the whole `/app/data` while the container is stopped (keeps SQLite + WAL
consistent):

```bash
docker compose stop
docker run --rm -v samjon_memory_data:/data -v "$PWD:/backup" alpine \
  tar czf /backup/samjon-memory-backup.tgz -C /data .
docker compose start
```

Restore:

```bash
docker compose stop
docker run --rm -v samjon_memory_data:/data -v "$PWD:/backup" alpine \
  sh -c "rm -rf /data/* && tar xzf /backup/samjon-memory-backup.tgz -C /data"
docker compose start
```

The Resolver database is a disposable projection - after restoring a Core backup
it can be rebuilt on demand. Core is the authoritative, backup-critical store.

## Portainer stack

`samjon_stack.yaml` is a self-contained Compose file for Portainer Standalone:

1. Portainer > Stacks > Add stack.
2. Paste the contents of `samjon_stack.yaml` ("Web editor"), or point the repo's
   Git provider at this repository with `samjon_stack.yaml` as the stack file.
3. Provide the secret variables (Portal username/password, API tokens) in the
   stack's "Environment variables" field.
4. Deploy. Data persists in the `samjon_memory_data` volume.

## Troubleshooting

- **Container unhealthy / restarting:** check logs (`docker-logs.ps1`). `/health`
  returns `degraded` if Core cannot open its database.
- **Portal returns 401:** Portal credentials are not set (or wrong) - set
  `SAMJON_PORTAL_USERNAME`/`SAMJON_PORTAL_PASSWORD` and restart.
- **``unable to open database file``:** `/app/data` is unwritable. If you use a
  bind mount instead of the named volume, fix the host directory ownership
  (uid `10001`) - see Persistence above.
- **Host port 8100 busy:** change `SAMJON_CORE_PORT` in `.env` (Compose publishes
  that host port to container `8100`).
- **Templates or static assets missing:** the image was built from an older
  wheel; rebuild with `docker compose up -d --build` after updating
  `[tool.setuptools.package-data]` in `pyproject.toml`.

## Design decisions

- **Multi-stage build** keeps the runtime image small (only the venv is copied;
  no tests, no `.git`, no source tree, no `data/`).
- **No shell entrypoint** is used: migrations start automatically, and the named
  volume preserves image directory ownership, so no privileged "fix up
  permissions then drop" step is required.
- **Single Uvicorn worker**: SQLite benefits from a single writer; there is no
  proven multi-worker evidence, so the image uses one worker and no `--reload`.
- **Jinja2 + Pillow** are explicit runtime dependencies in `pyproject.toml`;
  templates and Portal static assets are shipped in the wheel via
  `[tool.setuptools.package-data]`.