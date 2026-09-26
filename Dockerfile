# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Builder stage (บังคับติดตั้งไลบรารีตรงๆ ป้องกันปัญหาหลุดร่วง)
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

COPY pyproject.toml MANIFEST.in README.md ./
#COPY src ./src

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install --no-cache-dir fastapi uvicorn pydantic pyyaml Pillow Jinja2 python-multipart 
#    && /opt/venv/bin/pip install --no-cache-dir --no-deps .

# ---------------------------------------------------------------------------
# Runtime stage (ใช้ของเดิมที่คุณมีได้เลยครับ)
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src"

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
# The application source is NOT baked into the image: it is provided at run
# time as a host bind mount (./src -> /app/src) and imported via
# PYTHONPATH=/app/src, so editing *.py or Portal files requires only a
# container restart - never an image rebuild.

RUN groupadd --system --gid 10001 samjon \
    && useradd --system --uid 10001 --gid samjon --home-dir /app --shell /usr/sbin/nologin samjon \
    && mkdir -p /app/data/media/originals \
                /app/data/media/thumbnails \
                /app/data/media/archived \
    && chown -R samjon:samjon /app

# NOTE: `USER samjon` stays disabled here so the container runs as root
# (matches the current bind-mount workflow). Re-enable it for the hardened
# non-root baseline - the data dirs under /app/data are already owned by
# uid 10001.
#USER samjon

EXPOSE 8100

CMD ["python", "-m", "uvicorn", "samjon_memory.core.main:app", "--host", "0.0.0.0", "--port", "8100"]