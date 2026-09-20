"""Resolver V1 REST routers (Foundation A)."""

from fastapi import APIRouter, Request

from samjon_memory.resolver.service import ResolverService

router = APIRouter()


def _svc(request: Request) -> ResolverService:
    svc = getattr(request.app.state, "resolver_service", None)
    if svc is None:
        svc = ResolverService()
        request.app.state.resolver_service = svc
    return svc


@router.get("/resolver/ready", response_model=None)
async def resolver_ready(request: Request):
    """Dedicated Resolver readiness endpoint (independent of Core readiness)."""
    return _svc(request).readiness()
