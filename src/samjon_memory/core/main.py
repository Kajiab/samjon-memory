"""Samjon Memory Core V1 - FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from samjon_memory.config import config
from samjon_memory.core.service import CoreService
from samjon_memory.api.health import router as health_router
from samjon_memory.api.capabilities import router as capabilities_router
from samjon_memory.api.memories import router as memories_router
from samjon_memory.api.collections import router as collections_router
from samjon_memory.api.audit import router as audit_router
from samjon_memory.portal.router import router as portal_router
from samjon_memory.resolver.api import router as resolver_router
from samjon_memory.observability.logging import setup_logging

setup_logging(config.log_level)

app = FastAPI(title="Samjon Memory Core V1", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(capabilities_router)
app.include_router(memories_router)
app.include_router(collections_router)
app.include_router(audit_router)
app.include_router(portal_router)
app.include_router(resolver_router)


@app.on_event("startup")
async def startup():
    # Fail fast (clear logs, non-zero exit) when the bind-mounted data dirs are
    # missing or unwritable. Enforced in production only (Docker sets ENV=production).
    if not config.is_development:
        from samjon_memory.core.startup import ensure_data_writeable
        ensure_data_writeable(config.database_path, config.media_root)
    service = CoreService()
    app.state.service = service


STATIC_DIR = Path(__file__).parent.parent / "portal" / "static"

# When SAMJON_CATEGORY_COVERS_ROOT is configured (a Docker bind mount of host
# ./category-covers), serve category covers from that directory so they can be
# replaced without rebuilding the image. Registered before the general static
# mount so this more-specific prefix wins; skipped if the directory is absent.
if config.category_covers_root:
    _ext_covers = Path(config.category_covers_root)
    if _ext_covers.is_dir():
        app.mount(
            "/portal/static/category-covers",
            StaticFiles(directory=str(_ext_covers)),
            name="portal-category-covers",
        )

app.mount(
    "/portal/static",
    StaticFiles(directory=STATIC_DIR),
    name="portal-static",
)