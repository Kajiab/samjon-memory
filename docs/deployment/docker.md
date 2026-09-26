# Samjon Memory - Docker deployment

Containers Samjon Memory (Core, Resolver, Media, Portal) as a self-contained,
production-like local service. Runtime data persists on the host via **bind
mounts** - the host sees and owns the data.

> **Runtime user:** the current image runs as **root** (`USER samjon` is commented
> out to match the bind-mount workflow). The hardened non-root baseline still
> exists in the image (uid/gid 10001, data dirs pre-created and `chown`ed on
> build) - uncomment `USER samjon` in the `Dockerfile` to restore it.

- [Files](#files)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Bind mounts & host layout](#bind-mounts--host-layout)
- [Persistence & permissions](#persistence--permissions)
- [Operations](#operations)
- [Security notes](#security-notes)
- [Backup & restore](#backup--restore)
- [When a rebuild is required](#when-a-rebuild-is-required)
- [Portainer stack](#portainer-stack)
- [Troubleshooting](#troubleshooting)
- [Design decisions](#design-decisions)

## Files

| File | Purpose |
| ---- | ------- |
| `Dockerfile` | Multi-stage build (builder + runtime image) |
| `compose.yaml` | Recommended `docker compose` deployment (bind mounts) |
| `.dockerignore` | Keeps tests / venv / data / secrets out of the build context |
| `.env.docker.example` | Template for stack configuration (copy to `.env`) |
| `.env.example` | (repo root) original local-dev template; unaffected |
| `samjon_stack.yaml` | Self-contained Portainer stack (absolute bind paths) |
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
        +-- /app/data/backups/
        |
        v  bind mounts (host-visible)
  ./data            /app/data
  ./src             /app/src (live application source)
  ./category-covers /app/category-covers (read-only)
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

# 2) Build and start (creates ./data and ./category-covers host dirs first)
powershell -ExecutionPolicy Bypass -File .\scripts\docker-up.ps1
#    equivalent: docker compose up -d --build
```

Then open:

- Portal UI: <http://localhost:8100/portal/> (HTTP Basic - use the Portal credentials)
- Health:  <http://localhost:8100/health>
- Resolver Debug: <http://localhost:8100/portal/resolver/>

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
SAMJON_CATEGORY_COVERS_ROOT=/app/category-covers
```

The full list of tunable variables is in `.env.docker.example`.

## Bind mounts & host layout

`compose.yaml` uses two host-visible bind mounts (no named volume):

| Host path (relative to compose project) | Container path | Mode |
| ---- | ---- | ---- |
| `./data` | `/app/data` | read-write |
| `./src` | `/app/src` | read-write (live application source) |
| `./category-covers` | `/app/category-covers` | read-only |

Persisted under the repository-local `./data/`:

```text
data/
├── samjon_core.sqlite
├── samjon_resolver.sqlite
├── media/
│   ├── originals/
│   ├── thumbnails/
│   └── archived/
└── backups/
```

SQLite files are never mounted individually; the whole `data/` directory is
mounted as one unit. `category-covers/` holds replaceable configured category
covers (JPEG/JPG/PNG/WebP); user-uploaded media never lives there.

## Persistence & permissions

- Data lives directly on the host under `./data` (bind mount to `/app/data`).
  It survives `docker compose down` and image rebuilds - it is never stored in
  the image and never inside a Docker-managed named volume.
- The image defines the non-root user `samjon` (uid/gid `10001`) and pre-creates
  the `/app/data/media/...` directories owned by it. The current `Dockerfile`
  keeps `USER samjon` commented out, so the process runs as root; for the
  hardened baseline re-enable `USER samjon` (that user only needs write access
  to `/app/data` and `/app/data/media`).
- On startup (production mode) the application runs a **writeability check** for
  `/app/data` and `/app/data/media`: it creates them from trusted configuration
  if missing and fails with a clear message if `/app/data` is not writable. An
  unwritable host mount therefore surfaces as a startup error in the logs rather
  than an obscure crash. The application never recursively `chown`s arbitrary
  host paths from a privileged entrypoint.
- **Windows / Docker Desktop:** bind mounts into a Linux container are generally
  read/writable without extra setup; Docker Desktop maps the Windows folder into
  the Linux VM transparently.
- **Linux:** the container user is uid/gid `10001`. A host directory owned by
  your user/root is **not** writable by the container. Either pre-create and own
  it, or set ownership once:

  ```bash
  sudo chown -R 10001:10001 ./data
  ```

  (Repeat after a fresh clone/`git clean`, which recreates owned-by-root dirs.)
- If you keep a `category-covers/` folder empty, configured category covers are
  simply absent and the app falls back to Collection/Memory covers, then the
  placeholder. To restore the packaged look in Docker, copy the bundled covers:

  ```powershell
  Copy-Item .\src\samjon_memory\portal\static\category-covers\* .\category-covers\
  ```

## Operations

```powershell
.\scripts\docker-build.ps1            # build only
.\scripts\docker-up.ps1               # creates host dirs, then build + start detached
.\scripts\docker-down.ps1             # stop (data kept on host)
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
- SQLite files live on a host bind mount (`./data` -> `/app/data`) and are never
  baked into the image. When `USER samjon` is re-enabled they are owned by
  uid 10001 inside the container; with the current root runtime the host files
  themselves own the data.
- Leave `SAMJON_CORE_ENV=production`. The REST API becomes token-authenticated
  when the three tokens are set; the Portal always requires HTTP Basic.
- Never commit `.env`; it is excluded by `.gitignore` and `.dockerignore`.

## Backup & restore

Data backup:

1. Stop the service: `docker compose stop` (or `docker-down.ps1`).
2. Copy the **complete** `data/` directory to your backup location
   (e.g. `data/` -> `backup/YYYY-MM-DD/data/`).
3. Start the service: `docker compose start` (or `docker-up.ps1`).

Data restore:

1. Stop the service.
2. Back up the current `data/` directory (safety copy).
3. Replace the complete `data/` directory with the backup.
4. Start the service.
5. Verify health (`/health`) and the Library (Portal) list/reader.

Warnings:

- Never copy a live SQLite file independently (an open WAL database is
  inconsistent mid-write); always copy `data/` with the service stopped.
- Core DB, Resolver DB, and media should move together as one directory tree.
- Do not copy only `*-wal`/`*-shm` files - they are sidecars of a live DB.
- Configured **category covers are a separate concern**: they live in
  `category-covers/` (`./category-covers` on the host) and are backed up/replaced
  independently of runtime media.

## When a rebuild is required

- **Data or uploaded images changed** (Core/Resolver records, `data/media`):
  no image rebuild required. Stop the service, copy files into `./data`, start.
  (SQLite files must be moved while the service is stopped.)
- **Category covers changed:** copy the new images into `category-covers/`; a
  container **restart is sufficient** (`docker compose restart` or
  `docker-up.ps1`). No rebuild.
- **Application source changed** (`*.py`, Jinja templates, CSS/JS under
  `src/`): a **restart is sufficient** - the source is bind-mounted
  (`./src` -> `/app/src`) and read live. Use `docker compose restart` (or the
  helpers). Static assets and Jinja templates load from disk on demand; Python
  modules are re-imported on restart (no `--reload` is enabled).
- **Python / system / library dependencies changed** (`pyproject.toml`): a full
  image rebuild is required (`docker compose up -d --build`), because the venv
  is baked into the image.

> The live-source bind mount is the chosen workflow here: edits under
> `src/` never require an image rebuild. The image remains the single source of
> the runtime venv (dependencies); the host source drives application code.

## Portainer stack

`samjon_stack.yaml` is a self-contained Compose file for Portainer Standalone.
Portainer treats relative bind paths ambiguously, so it uses **absolute
placeholder** host paths that you must edit before deploying:

```yaml
volumes:
  - type: bind
    source: /absolute/path/to/samjon-memory/data        # EDIT
    target: /app/data
  - type: bind
    source: /absolute/path/to/samjon-memory/category-covers  # EDIT
    target: /app/category-covers
    read_only: true
```

Example (clearly an example, not hard-coded for you):

```text
D:/HomeAssistant/samjon-memory/data:/app/data
D:/HomeAssistant/samjon-memory/category-covers:/app/category-covers:ro
```

1. Portainer > Stacks > Add stack.
2. Paste the contents of `samjon_stack.yaml` ("Web editor"), or point the repo's
   Git provider at this repository with `samjon_stack.yaml` as the stack file.
3. Set the absolute bind paths (edit the placeholders above) and provide the
   secret variables in the stack's "Environment variables" field.
4. Deploy. Runtime data persists under the host paths you chose.

## Troubleshooting

- **`Samjon data directory is not writable`** on startup (only when `USER samjon`
  is re-enabled): the host bind mount `./data` is not writable by the container
  user. On Linux run `sudo chown -R 10001:10001 ./data` (see Persistence). The
  current image runs as root, so this check usually passes; re-enabling the
  non-root baseline reintroduces the requirement.
- **Container unhealthy / restarting:** check logs (`docker-logs.ps1`). `/health`
  returns `degraded` if Core cannot open its database.
- **Portal returns 401:** Portal credentials are not set (or wrong) - set
  `SAMJON_PORTAL_USERNAME`/`SAMJON_PORTAL_PASSWORD` and restart.
- **Host port 8100 busy:** change `SAMJON_CORE_PORT` in `.env` (Compose publishes
  that host port to container `8100`).
- **Templates or static assets missing / 404:** the `./src` bind mount is not
  mapped (or the file was deleted on the host). Check `docker compose ps` shows
  the mount and that `src/samjon_memory/portal/templates`/`static` exists on the
  host; a `docker compose restart` refreshes the mounted tree.

## Design decisions

- **Bind mounts instead of a named volume:** host-visible data (`./data`,
  `./category-covers`) for easy backup, inspection, and cover replacement.
- **Multi-stage build** keeps the runtime image lean: the builder installs the
  runtime libraries directly into a venv (no wheel build step). The image does
  **not** bake application source; at run time the host `./src` is bind-mounted
  to `/app/src`, and the app imports it via `PYTHONPATH=/app/src`. No tests, no
  `.git`, no `data/` in the image.
- **No shell entrypoint** is used for privilege dropping or migrations: migrations
  run automatically, and the startup writeability check surfaces permission
  problems clearly without recursive host `chown` from a privileged step.
- **Single Uvicorn worker**: SQLite benefits from a single writer; there is no
  proven multi-worker evidence, so the image uses one worker and no `--reload`.
- **Jinja2, Pillow and python-multipart** are explicit runtime dependencies in
  `pyproject.toml`; the builder installs them directly into the venv. Portal
  templates/static assets ship with the application source copy under `/app/src`
  (`MANIFEST.in` still declares the same package data for wheel builds).