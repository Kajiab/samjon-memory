"""Portal router.

The Portal uses the same application-service operations, validation,
authorization, concurrency, and audit behavior as the Core REST API.

Portal handlers never access SQLite connections, repositories,
arbitrary SQL, or database paths directly.
"""

from fastapi import APIRouter, Request, Header, Form, Cookie, Response
from fastapi.responses import HTMLResponse
from samjon_memory.portal.pages import (
    render_portal_index,
    render_memory_list,
    render_memory_create,
    render_memory_edit,
    render_memory_detail,
    render_collection_list,
    render_collection_create,
    render_collection_edit,
    render_collection_detail,
    render_audit_log,
    render_message,
)
from samjon_memory.core.service import CoreService
from samjon_memory.security.auth import get_current_token, get_admin_token
from samjon_memory.errors import VersionConflict, NotFound, ValidationError
from samjon_memory.constants import DEFAULT_PAGE_SIZE
import uuid

router = APIRouter()

CSRF_COOKIE_NAME = "portal_csrf"
READ_TOKEN_HEADER = "X-Service-Token"
ADMIN_TOKEN_HEADER = "X-Admin-Token"
CSRF_HEADER = "X-CSRF-Token"


def _generate_csrf_token() -> str:
    return uuid.uuid4().hex[:32]


def _get_csrf_token(request: Request) -> str:
    token = request.cookies.get(CSRF_COOKIE_NAME)
    if not token:
        token = _generate_csrf_token()
    return token


def _set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        CSRF_COOKIE_NAME,
        token,
        httponly=True,
        samesite="Strict",
        max_age=3600,
    )


def _require_read_token(x_service_token: str = Header(None)) -> str:
    return get_current_token(x_service_token)


def _require_admin_token(x_admin_token: str = Header(None)) -> str:
    return get_admin_token(x_admin_token)


def _get_service() -> CoreService:
    return CoreService()


@router.get("/portal/")
async def portal_index(x_service_token: str = Header(None)):
    _require_read_token(x_service_token)
    service = _get_service()


@router.get("/portal/memories")
async def portal_memories(
    request: Request,
    page: int = 1,
    q: str = "",
    x_service_token: str = Header(None),
):
    _require_read_token(x_service_token)
    service = _get_service()
    csrf_token = _get_csrf_token(request)
    memories = service.query_memories(subject=q, limit=DEFAULT_PAGE_SIZE, offset=(page - 1) * DEFAULT_PAGE_SIZE)
    response = HTMLResponse(content=render_memory_list(memories, page, q, csrf_token))
    _set_csrf_cookie(response, csrf_token)
    return response


@router.get("/portal/memories/create")
async def portal_memory_create_form(x_service_token: str = Header(None)):
    _require_admin_token(x_service_token)
    return HTMLResponse(content=render_memory_create())


@router.post("/portal/memories/create")
async def portal_memory_create(
    request: Request,
    subject: str = Form(...),
    raw_content: str = Form(...),
    source: str = Form("portal"),
    x_admin_token: str = Header(None),
):
    _require_admin_token(x_admin_token)
    service = _get_service()
    csrf_token = _get_csrf_token(request)
    try:
        memory = service.create_memory({
            "subject": subject,
            "raw_content": raw_content,
            "source": source,
        })
        msg = f"Memory {memory['memory_id']} created successfully."
        response = HTMLResponse(content=render_message("Memory created", msg, "success"))
    except Exception as e:
        response = HTMLResponse(content=render_message("Error", str(e), "error"))
    _set_csrf_cookie(response, csrf_token)
    return response


@router.get("/portal/memories/{memory_id}")
async def portal_memory_detail(memory_id: str, x_service_token: str = Header(None)):
    _require_read_token(x_service_token)
    service = _get_service()
    memory = service.get_memory(memory_id)


@router.post("/portal/memories/{memory_id}/edit")
async def portal_memory_edit(
    request: Request,
    memory_id: str,
    subject: str = Form(None),
    raw_content: str = Form(None),
    expected_version: int = Form(None),
    x_admin_token: str = Header(None),
):
    _require_admin_token(x_admin_token)
    service = _get_service()
    csrf_token = _get_csrf_token(request)
    try:
        data = {}
        if subject is not None:
            data["subject"] = subject
        if raw_content is not None:
            data["raw_content"] = raw_content
        if expected_version is not None:
            data["expected_version"] = expected_version
        memory = service.update_memory(memory_id, data)
        msg = f"Memory {memory_id} updated to version {memory['version']}."
        response = HTMLResponse(content=render_message("Memory updated", msg, "success"))
    except ValueError as e:
        if "VERSION_CONFLICT" in str(e):
            current = service.get_memory(memory_id)
            warn = f"The memory was modified by another user. Current version is {current['version']}. Please reload and retry."
            response = HTMLResponse(content=render_message("Version Conflict", warn, "warning"))
        else:
            response = HTMLResponse(content=render_message("Error", str(e), "error"))
    except NotFound as e:
        response = HTMLResponse(content=render_message("Not Found", e.message, "error"))
    _set_csrf_cookie(response, csrf_token)
    return response


@router.post("/portal/memories/{memory_id}/supersede")
async def portal_memory_supersede(
    request: Request,
    memory_id: str,
    replacement_id: str = Form(...),
    x_admin_token: str = Header(None),
):
    _require_admin_token(x_admin_token)
    service = _get_service()
    csrf_token = _get_csrf_token(request)
    try:
        service.supersede_memory(memory_id, replacement_id)
        msg = f"Memory {memory_id} superseded by {replacement_id}."
        response = HTMLResponse(content=render_message("Memory superseded", msg, "success"))
    except NotFound as e:
        response = HTMLResponse(content=render_message("Not Found", e.message, "error"))
    _set_csrf_cookie(response, csrf_token)


@router.get("/portal/collections")
async def portal_collections(
    request: Request,
    page: int = 1,
    q: str = "",
    x_service_token: str = Header(None),
):
    _require_read_token(x_service_token)
    service = _get_service()
    csrf_token = _get_csrf_token(request)
    collections = service.list_collections(subject=q, limit=DEFAULT_PAGE_SIZE, offset=(page - 1) * DEFAULT_PAGE_SIZE)
    response = HTMLResponse(content=render_collection_list(collections, page, q, csrf_token))
    _set_csrf_cookie(response, csrf_token)
    return response


@router.get("/portal/collections/create")
async def portal_collection_create_form(x_service_token: str = Header(None)):
    _require_admin_token(x_service_token)
    return HTMLResponse(content=render_collection_create())


@router.post("/portal/collections/create")
async def portal_collection_create(
    request: Request,
    subject: str = Form(...),
    title: str = Form(...),
    source: str = Form("portal"),
    expected_item_count: int = Form(None),
    x_admin_token: str = Header(None),
):
    _require_admin_token(x_admin_token)
    service = _get_service()
    csrf_token = _get_csrf_token(request)
    try:
        collection = service.create_collection({
            "subject": subject,
            "title": title,
            "source": source,
            "expected_item_count": expected_item_count,
        })
        msg = f"Collection {collection['collection_id']} created in draft state."
        response = HTMLResponse(content=render_message("Collection created", msg, "success"))
    except Exception as e:
        response = HTMLResponse(content=render_message("Error", str(e), "error"))
    _set_csrf_cookie(response, csrf_token)
    return response


@router.get("/portal/collections/{collection_id}")
async def portal_collection_detail(
    request: Request,
    collection_id: str,
    x_service_token: str = Header(None),
):
    _require_read_token(x_service_token)
    service = _get_service()
    csrf_token = _get_csrf_token(request)
    collection = service.get_collection(collection_id)
    memories = service.get_collection_memories(collection_id, limit=100)
    validation = service.validate_collection(collection_id)
    response = HTMLResponse(content=render_collection_detail(collection, memories, validation, csrf_token))
    _set_csrf_cookie(response, csrf_token)
    return response


@router.post("/portal/collections/{collection_id}/edit")
async def portal_collection_edit(
    request: Request,
    collection_id: str,
    subject: str = Form(None),
    title: str = Form(None),
    expected_version: int = Form(None),
    x_admin_token: str = Header(None),
):
    _require_admin_token(x_admin_token)
    service = _get_service()
    csrf_token = _get_csrf_token(request)
    try:
        data = {}
        if subject is not None:
            data["subject"] = subject
        if title is not None:
            data["title"] = title
        if expected_version is not None:
            data["expected_version"] = expected_version
        collection = service.update_collection(collection_id, data)
        msg = f"Collection {collection_id} updated to version {collection['version']}."
        response = HTMLResponse(content=render_message("Collection updated", msg, "success"))
    except ValueError as e:
        if "VERSION_CONFLICT" in str(e):
            current = service.get_collection(collection_id)
            warn = f"The collection was modified by another user. Current version is {current['version']}. Please reload and retry."
            response = HTMLResponse(content=render_message("Version Conflict", warn, "warning"))
        else:
            response = HTMLResponse(content=render_message("Error", str(e), "error"))
    except NotFound as e:
        response = HTMLResponse(content=render_message("Not Found", e.message, "error"))
    _set_csrf_cookie(response, csrf_token)
    return response


@router.post("/portal/collections/{collection_id}/reorder")
async def portal_collection_reorder(
    request: Request,
    collection_id: str,
    ordered_memory_ids: str = Form(...),
    x_admin_token: str = Header(None),
):
    _require_admin_token(x_admin_token)
    service = _get_service()
    csrf_token = _get_csrf_token(request)
    try:
        ids = [mid.strip() for mid in ordered_memory_ids.split(",") if mid.strip()]
        service.reorder_collection(collection_id, ids)
        msg = f"Collection {collection_id} reordered."
        response = HTMLResponse(content=render_message("Collection reordered", msg, "success"))
    except NotFound as e:
        response = HTMLResponse(content=render_message("Not Found", e.message, "error"))
    _set_csrf_cookie(response, csrf_token)
    return response


@router.post("/portal/collections/{collection_id}/validate")
async def portal_collection_validate(
    request: Request,
    collection_id: str,
    x_admin_token: str = Header(None),
):
    _require_admin_token(x_admin_token)
    service = _get_service()
    csrf_token = _get_csrf_token(request)
    try:
        validation = service.validate_collection(collection_id)
        issues_str = ", ".join(validation["issues"]) if validation["issues"] else "none"
        level = "info" if validation["valid"] else "warning"
        msg = f"Valid: {validation['valid']}, Issues: {issues_str}, Memories: {validation['memory_count']}"
        response = HTMLResponse(content=render_message("Validation result", msg, level))
    except NotFound as e:
        response = HTMLResponse(content=render_message("Not Found", e.message, "error"))
    _set_csrf_cookie(response, csrf_token)
    return response


@router.get("/portal/audit")
async def portal_audit(
    request: Request,
    page: int = 1,
    x_service_token: str = Header(None),
):
    _require_read_token(x_service_token)
    service = _get_service()
    csrf_token = _get_csrf_token(request)
    audits = service.get_audit_records(limit=DEFAULT_PAGE_SIZE, offset=(page - 1) * DEFAULT_PAGE_SIZE)
    response = HTMLResponse(content=render_audit_log(audits, page, csrf_token))
    _set_csrf_cookie(response, csrf_token)
    return response


@router.post("/portal/collections/{collection_id}/activate")
async def portal_collection_activate(
    request: Request,
    collection_id: str,
    x_admin_token: str = Header(None),
):
    _require_admin_token(x_admin_token)
    service = _get_service()
    csrf_token = _get_csrf_token(request)
    try:
        collection = service.activate_collection(collection_id)
        msg = f"Collection {collection_id} is now {collection['status']} at version {collection['version']}."
        response = HTMLResponse(content=render_message("Collection activated", msg, "success"))
    except ValidationError as e:
        response = HTMLResponse(content=render_message("Validation Error", e.message, "warning"))
    except NotFound as e:
        response = HTMLResponse(content=render_message("Not Found", e.message, "error"))
    _set_csrf_cookie(response, csrf_token)
    return response


@router.post("/portal/memories/{memory_id}/forget")
async def portal_memory_forget(
    request: Request,
    memory_id: str,
    x_admin_token: str = Header(None),
):
    _require_admin_token(x_admin_token)
    service = _get_service()
    csrf_token = _get_csrf_token(request)
    try:
        service.forget_memory(memory_id)
        msg = f"Memory {memory_id} forgotten."
        response = HTMLResponse(content=render_message("Memory forgotten", msg, "success"))
    except NotFound as e:
        response = HTMLResponse(content=render_message("Not Found", e.message, "error"))
    _set_csrf_cookie(response, csrf_token)
    return response
    return HTMLResponse(content=render_memory_detail(memory))


@router.get("/portal/memories/{memory_id}/edit")
async def portal_memory_edit_form(memory_id: str, x_service_token: str = Header(None)):
    _require_admin_token(x_service_token)
    service = _get_service()
    memory = service.get_memory(memory_id)
    return HTMLResponse(content=render_memory_edit(memory))
    return HTMLResponse(content=render_portal_index())
