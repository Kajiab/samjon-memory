"""Resolver V1 REST routers (Foundation A + B)."""

from fastapi import APIRouter, Depends, Request

from samjon_memory.core.service import CoreService
from samjon_memory.resolver.models import ResolverQuery, ResolverSelective
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


@router.post("/api/v1/resolver/query", response_model=None)
async def resolver_query(request: Request, body: ResolverQuery, _: bool = Depends(require_read)):
    """Deterministic Resolver search (requires the existing REST read token)."""
    return _svc(request).search(
        _core(request),
        body.query,
        target=body.target,
        collection_id=body.collection_id,
        scope=body.scope,
        limit=body.limit,
        offset=body.offset,
        allow_stale=body.allow_stale,
        epsilon=body.epsilon,
        neighbor_items=body.neighbor_items,
        context_budget=body.context_budget,
    )


@router.post("/api/v1/resolver/rebuild/selective", response_model=None)
async def resolver_selective_rebuild(request: Request, body: ResolverSelective,
                                     _: bool = Depends(require_admin)):
    """Rebuild one Memory or Collection projection (requires the admin token)."""
    svc = _svc(request)
    return svc.selective_rebuild(_core(request), body.entity_type, body.entity_id)
