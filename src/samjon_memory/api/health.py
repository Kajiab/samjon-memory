"""Health and readiness endpoints."""

from fastapi import APIRouter
from samjon_memory.core.service import CoreService

router = APIRouter()


@router.get("/health", response_model=None)
async def health():
    service = CoreService()
    return service.health()


@router.get("/ready", response_model=None)
async def ready():
    service = CoreService()
    h = service.health()
    h["ready"] = h.get("status") == "ok"
    return h
