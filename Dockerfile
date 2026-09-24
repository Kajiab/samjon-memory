# syntax=docker/dockerfile:1
#
# Samjon Memory - production-like local image.
#
# Multi-stage build:
#   builder  - builds the samjon-memory wheel (incl. Jinja templates + static
#              assets declared in [tool.setuptools.package-data]) and installs it
#              into a self-contained virtualenv at /opt/venv.
#   runtime  - copies only the venv + runtime files, runs as the unprivileged
#              `samjon` user (uid/gid 10001), binds to 0.0.0.0:8100.
#
# No shell entrypoint is required: Core/Resolver migrations run automatically on
# startup (ensure_schema), and the named volume in compose.yaml preserves the
# image directory ownership so the non-root user can write /app/data.

# ---------------------------------------------------------------------------
# Builder stage
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Copy package metadata first for layer caching.
# MANIFEST.in is required by setuptools to ship the Jinja templates and Portal
# static assets as package data; README is referenced by MANIFEST.in.
COPY pyproject.toml MANIFEST.in README.md ./
# Copy the application source.
COPY src ./src

# Create a self-contained virtualenv, build the wheel, install it + runtime deps.
# Pillow and Jinja2 are explicit runtime dependencies in pyproject.toml.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel build \
    && /opt/venv/bin/python -m build --wheel \
    && /opt/venv/bin/pip install --no-cache-dir dist/*.whl

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy the installed application (venv only) - no tests, no .git, no source tree.
COPY --from=builder /opt/venv /opt/venv

# Non-root service user + predictable data directories owned by that user.
RUN groupadd --system --gid 10001 samjon \
    && useradd --system --uid 10001 --gid samjon --home-dir /app --shell /usr/sbin/nologin samjon \
    && mkdir -p /app/data/media/originals \
                /app/data/media/thumbnails \
                /app/data/media/archived \
    && chown -R samjon:samjon /app

USER samjon

EXPOSE 8100

# exec-form CMD; single worker (SQLite, no proven multi-worker evidence);
# no --reload; binds inside the container so compose maps the host port.
CMD ["python", "-m", "uvicorn", "samjon_memory.core.main:app", "--host", "0.0.0.0", "--port", "8100"]