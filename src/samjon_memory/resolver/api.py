"""Resolver V1 REST routers (Foundation A + B)."""

from fastapi import APIRouter, Depends, Request

from samjon_memory.core.service import CoreService
from samjon_memory.resolver.service import ResolverService
from samjon_memory.security.auth import require_admin, require_read

router = APIRouter()


def _svc(request: Request) -> ResolverService:
    svc = getattr(request.app.state, "resolver_service", None)
    if svc is None:
        svc = ResolverService()
        request.app.state.resolver_service = svc
    return svc


def _core(request: Request) -> CoreService:
    core = getattr(request.app.state, "service", None)
    if core is None:
        core = CoreService()
        request.app.state.service = core
    return core


@router.get("/resolver/ready", response_model=None)
async def resolver_ready(request: Request):
    """Dedicated Resolver readiness endpoint (independent of Core readiness)."""
    return _svc(request).readiness()


@router.post("/api/v1/resolver/rebuild", response_model=None)
async def rebuild_resolver(request: Request, _: bool = Depends(require_admin)):
    """Run a full projection rebuild (requires the existing REST admin token)."""
    svc = _svc(request)
    result = svc.full_rebuild(_core(request))
    return {"status": "ok", "rebuild": result}


@router.get("/api/v1/resolver/rebuild/status", response_model=None)
async def resolver_rebuild_status(request: Request, _: bool = Depends(require_read)):
    """Return the latest rebuild status (requires the existing REST read token)."""
    return _svc(request).rebuild_status()


@router.get("/api/v1/resolver/projection/status", response_model=None)
async def resolver_projection_status(request: Request, _: bool = Depends(require_read)):
    """Return projection state and per-entity status (read-token boundary)."""
    return _svc(request).projection_status()
