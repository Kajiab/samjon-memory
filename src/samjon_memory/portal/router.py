"""Portal router."""

from fastapi import APIRouter, Request, Header
from fastapi.responses import HTMLResponse
from samjon_memory.portal.pages import (
    render_portal_index,
    render_memory_list,
    render_collection_list,
    render_memory_detail,
    render_collection_detail,
    render_audit_log,
)
from samjon_memory.core.service import CoreService
from samjon_memory.security.auth import get_current_token

router = APIRouter()


def get_service():
    return CoreService()


@router.get("/portal/")
async def portal_index():
    return HTMLResponse(content=render_portal_index())


@router.get("/portal/memories", response_model=None)
async def portal_memories(page: int = 1, q: str = "", x_service_token: str = Header(None)):
    from samjon_memory.security.auth import get_current_token
    get_current_token(x_service_token)
    service = CoreService()
    memories = service.query_memories(subject=q, limit=20, offset=(page - 1) * 20)
    from samjon_memory.portal.pages import render_memory_list
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=render_memory_list(memories, page, q))


@router.get("/portal/collections", response_model=None)
async def portal_collections(page: int = 1, q: str = "", x_service_token: str = Header(None)):
    get_current_token(x_service_token)
    service = CoreService()
    collections = service.list_collections(subject=q, limit=20, offset=(page - 1) * 20)
    return HTMLResponse(content=render_collection_list(collections, page, q))


@router.get("/portal/memories/{memory_id}", response_model=None)
async def portal_memory_detail(memory_id: str, x_service_token: str = Header(None)):
    get_current_token(x_service_token)
    service = CoreService()
    memory = service.get_memory(memory_id)
    return HTMLResponse(content=render_memory_detail(memory))


@router.get("/portal/collections/{collection_id}", response_model=None)
async def portal_collection_detail(collection_id: str, x_service_token: str = Header(None)):
    get_current_token(x_service_token)
    service = CoreService()
    collection = service.get_collection(collection_id)
    memories = service.get_collection_memories(collection_id, limit=50)
    return HTMLResponse(content=render_collection_detail(collection, memories))


@router.get("/portal/audit", response_model=None)
async def portal_audit(page: int = 1, x_service_token: str = Header(None)):
    get_current_token(x_service_token)
    service = CoreService()
    audits = service.conn.execute("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ? OFFSET ?", (20, (page - 1) * 20)).fetchall()
    return HTMLResponse(content=render_audit_log([dict(a) for a in audits], page))
