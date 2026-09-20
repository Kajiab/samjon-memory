"""Audit API endpoints (append-only; filters + pagination + statistics)."""
from fastapi import APIRouter
from typing import Optional

from samjon_memory.core.service import CoreService

router = APIRouter()


@router.get("/api/v1/core/audit", response_model=None)
async def list_audit(
    entity_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    service = CoreService()
    return service.get_audit_records(
        entity_id=entity_id, entity_type=entity_type, action=action,
        since=since, until=until, limit=limit, offset=offset,
    )


@router.get("/api/v1/core/audit/stats", response_model=None)
async def audit_stats(
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
):
    service = CoreService()
    return service.audit_summary(
        entity_type=entity_type, action=action, since=since, until=until,
    )