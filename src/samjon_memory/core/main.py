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
    service = CoreService()
    app.state.service = service


STATIC_DIR = Path(__file__).parent.parent / "portal" / "static"

app.mount(
    "/portal/static",
    StaticFiles(directory=STATIC_DIR),
    name="portal-static",
)
