"""Server-rendered Core Portal router. AGENTS.md v2.1.0."""
import html as _html
import hmac as _hmac
from urllib.parse import urlparse as _urlparse
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, RedirectResponse
from samjon_memory.core.service import CoreService
from samjon_memory.errors import SamjonMemoryError
from samjon_memory.config import config
from samjon_memory.constants import DEFAULT_PAGE_SIZE
import samjon_memory.portal.pages as pages

router = APIRouter()
basic_auth = HTTPBasic(auto_error=False)


def _parse_origin(origin_header: str) -> str:
    if not origin_header:
        return ""
    parsed = _urlparse(origin_header)
    host = parsed.hostname or ""
    port = parsed.port
    if port and not ((parsed.scheme == "http" and port == 80) or (parsed.scheme == "https" and port == 443)):
        return f"{parsed.scheme}://{host}:{port}"
    return f"{parsed.scheme}://{host}"


def _require_credentials() -> None:
    if not config.portal_username or not config.portal_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Portal credentials not configured",
                            headers={"WWW-Authenticate": "Basic"})


def _hmac_eq(a: str, b: str) -> bool:
    return _hmac.compare_digest(a, b)


def portal_auth(credentials: HTTPBasicCredentials = Depends(basic_auth)) -> str:
    if not credentials:
        _require_credentials()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication required",
                            headers={"WWW-Authenticate": "Basic"})
    _require_credentials()
    if not _hmac_eq(credentials.username, config.portal_username):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid credentials",
                            headers={"WWW-Authenticate": "Basic"})
    if not _hmac_eq(credentials.password, config.portal_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid credentials",
                            headers={"WWW-Authenticate": "Basic"})
    return credentials.username


def validate_origin(request: Request) -> None:
    origin = request.headers.get("origin") or request.headers.get("referer") or ""
    if not origin:
        return
    parsed = _parse_origin(origin)
    if parsed not in config.portal_allowed_origins:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unapproved Origin")


def _svc(request: Request) -> CoreService:
    svc = getattr(request.app.state, "service", None)
    if svc is None:
        svc = CoreService()
        request.app.state.service = svc
    return svc


def _e(text) -> str:
    return _html.escape(str(text) if text is not None else "")


def _q(request: Request, key: str, default: str = "") -> str:
    return request.query_params.get(key, default)


@router.get("/portal/", response_class=HTMLResponse)
async def portal_index(request: Request):
    return RedirectResponse(url="/portal/memories", status_code=303)


@router.get("/portal/memories", response_class=HTMLResponse)
async def portal_memories(request: Request, _: str = Depends(portal_auth)):
    svc = _svc(request)
    subject = _q(request, "subject")
    status_filter = _q(request, "status")
    offset = int(_q(request, "offset", "0"))
    memories = svc.query_memories(
        subject=subject or None,
        status=status_filter or None,
        limit=DEFAULT_PAGE_SIZE,
        offset=offset,
    )
    message = _q(request, "message")
    return HTMLResponse(content=pages.memory_list(
        memories=memories, subject=subject or "", status_filter=status_filter,
        offset=offset, message=message,
    ))


@router.get("/portal/memories/create", response_class=HTMLResponse)
async def portal_memory_create_form(request: Request, _: str = Depends(portal_auth)):
    message = _q(request, "message")
    error = _q(request, "error")
    return HTMLResponse(content=pages.memory_create_form(message=message, error=error))


@router.post("/portal/memories", response_class=HTMLResponse)
async def portal_memory_create(request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    data = {
        "subject": form.get("subject", ""),
        "raw_content": form.get("raw_content", ""),
        "source": form.get("source", "portal"),
        "memory_type": form.get("memory_type", "fact"),
        "scope": form.get("scope", "household"),
        "language": form.get("language", "en"),
    }
    try:
        mem = svc.create_memory(data, actor="portal")
        return RedirectResponse(url=f"/portal/memories/{mem['memory_id']}?message=created", status_code=303)
    except SamjonMemoryError as e:
        return HTMLResponse(content=pages.memory_create_form(error=e.message), status_code=e.status_code)


@router.get("/portal/memories/{memory_id}", response_class=HTMLResponse)
async def portal_memory_detail(request: Request, memory_id: str, _: str = Depends(portal_auth)):
    svc = _svc(request)
    try:
        memory = svc.get_memory(memory_id)
    except SamjonMemoryError as e:
        return HTMLResponse(content=pages.error_page(message=e.message), status_code=e.status_code)
    message = _q(request, "message")
    return HTMLResponse(content=pages.memory_detail(memory=memory, message=message))


@router.get("/portal/memories/{memory_id}/edit", response_class=HTMLResponse)
async def portal_memory_edit_form(request: Request, memory_id: str, _: str = Depends(portal_auth)):
    svc = _svc(request)
    try:
        memory = svc.get_memory(memory_id)
    except SamjonMemoryError as e:
        return HTMLResponse(content=pages.error_page(message=e.message), status_code=e.status_code)
    message = _q(request, "message")
    error = _q(request, "error")
    return HTMLResponse(content=pages.memory_edit_form(memory=memory, message=message, error=error))


@router.post("/portal/memories/{memory_id}", response_class=HTMLResponse)
async def portal_memory_edit(request: Request, memory_id: str, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    data = {}
    for key in ["subject", "memory_type", "scope", "title", "raw_content", "source", "language"]:
        if key in form and form[key]:
            data[key] = form[key]
    if "expected_version" in form:
        data["expected_version"] = int(form["expected_version"])
    try:
        svc.update_memory(memory_id, data, actor="portal")
        return RedirectResponse(url=f"/portal/memories/{memory_id}?message=updated", status_code=303)
    except (SamjonMemoryError, ValueError) as e:
        is_version_conflict = (
            isinstance(e, ValueError) and "VERSION_CONFLICT" in str(e)
        ) or (isinstance(e, SamjonMemoryError) and e.status_code == 409)
        if is_version_conflict:
            try:
                mem = svc.get_memory(memory_id)
            except SamjonMemoryError:
                mem = None
            return HTMLResponse(content=pages.memory_edit_form(memory=mem, error="Version conflict: the memory was modified by another request. Please review and resubmit."), status_code=409)
        try:
            mem = svc.get_memory(memory_id)
        except SamjonMemoryError:
            mem = None
        error_msg = e.message if isinstance(e, SamjonMemoryError) else str(e)
        return HTMLResponse(content=pages.memory_edit_form(memory=mem, error=error_msg), status_code=400 if isinstance(e, ValueError) else e.status_code)


@router.post("/portal/memories/{memory_id}/supersede", response_class=HTMLResponse)
async def portal_memory_supersede(request: Request, memory_id: str, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    replacement_id = form.get("replacement_memory_id", "")
    try:
        svc.supersede_memory(memory_id, replacement_id, actor="portal")
        return RedirectResponse(url=f"/portal/memories/{memory_id}?message=superseded", status_code=303)
    except SamjonMemoryError as e:
        try:
            memory = svc.get_memory(memory_id)
        except SamjonMemoryError:
            memory = None
        return HTMLResponse(content=pages.memory_detail(memory=memory, message=e.message), status_code=e.status_code)


@router.post("/portal/memories/{memory_id}/forget", response_class=HTMLResponse)
async def portal_memory_forget(request: Request, memory_id: str, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    try:
        svc.forget_memory(memory_id, actor="portal")
        return RedirectResponse(url="/portal/memories?message=forgotten", status_code=303)
    except SamjonMemoryError as e:
        try:
            memory = svc.get_memory(memory_id)
        except SamjonMemoryError:
            memory = None
        return HTMLResponse(content=pages.memory_detail(memory=memory, message=e.message), status_code=e.status_code)


@router.get("/portal/collections", response_class=HTMLResponse)
async def portal_collections(request: Request, _: str = Depends(portal_auth)):
    svc = _svc(request)
    collections = svc.collections.list(limit=100, offset=0)
    message = _q(request, "message")
    return HTMLResponse(content=pages.collection_list(collections=collections, message=message))


@router.get("/portal/collections/create", response_class=HTMLResponse)
async def portal_collection_create_form(request: Request, _: str = Depends(portal_auth)):
    message = _q(request, "message")
    error = _q(request, "error")
    return HTMLResponse(content=pages.collection_create_form(message=message, error=error))


@router.post("/portal/collections", response_class=HTMLResponse)
async def portal_collection_create(request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    data = {}
    for key in ["subject", "collection_type", "scope", "title", "summary", "source", "source_reference", "language"]:
        if key in form and form[key]:
            data[key] = form[key]
    if "expected_item_count" in form and form["expected_item_count"]:
        data["expected_item_count"] = int(form["expected_item_count"])
    try:
        coll = svc.create_collection(data, actor="portal")
        return RedirectResponse(url=f"/portal/collections/{coll['collection_id']}?message=created", status_code=303)
    except SamjonMemoryError as e:
        return HTMLResponse(content=pages.collection_create_form(error=e.message), status_code=e.status_code)


@router.get("/portal/collections/{collection_id}", response_class=HTMLResponse)
async def portal_collection_detail(request: Request, collection_id: str, _: str = Depends(portal_auth)):
    svc = _svc(request)
    try:
        collection = svc.get_collection(collection_id)
    except SamjonMemoryError as e:
        return HTMLResponse(content=pages.error_page(message=e.message), status_code=e.status_code)
    memories = svc.get_collection_memories(collection_id, limit=100, offset=0)
    validation = svc.validate_collection(collection_id)
    message = _q(request, "message")
    return HTMLResponse(content=pages.collection_detail(
        collection=collection, memories=memories, validation=validation, message=message,
    ))


@router.get("/portal/collections/{collection_id}/edit", response_class=HTMLResponse)
async def portal_collection_edit_form(request: Request, collection_id: str, _: str = Depends(portal_auth)):
    svc = _svc(request)
    try:
        collection = svc.get_collection(collection_id)
    except SamjonMemoryError as e:
        return HTMLResponse(content=pages.error_page(message=e.message), status_code=e.status_code)
    message = _q(request, "message")
    error = _q(request, "error")
    return HTMLResponse(content=pages.collection_edit_form(collection=collection, message=message, error=error))


@router.post("/portal/collections/{collection_id}", response_class=HTMLResponse)
async def portal_collection_edit(request: Request, collection_id: str, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    data = {}
    for key in ["subject", "collection_type", "scope", "title", "summary", "source", "source_reference", "language"]:
        if key in form and form[key]:
            data[key] = form[key]
    if "expected_item_count" in form and form["expected_item_count"]:
        data["expected_item_count"] = int(form["expected_item_count"])
    try:
        svc.update_collection(collection_id, data, actor="portal")
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=updated", status_code=303)
    except SamjonMemoryError as e:
        try:
            collection = svc.get_collection(collection_id)
        except SamjonMemoryError:
            collection = None
        return HTMLResponse(
            content=pages.collection_detail(
                collection=collection, memories=[],
                validation={"valid": True, "issues": [], "memory_count": 0},
                message=e.message,
            ),
            status_code=e.status_code,
        )


@router.post("/portal/collections/{collection_id}/memories", response_class=HTMLResponse)
async def portal_add_memory_to_collection(collection_id: str, request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    memory_data = {
        "subject": form.get("title", ""),
        "memory_type": form.get("memory_type", "fact"),
        "raw_content": form.get("raw_content", ""),
        "source": "portal",
        "language": form.get("language", "en"),
    }
    if form.get("structured_value", ""):
        memory_data["structured_value_json"] = form["structured_value"]
    try:
        mem = svc.create_memory(memory_data, actor="portal")
        sequence_number = int(form.get("sequence_number", "1"))
        svc.add_memory_to_collection(collection_id, mem["memory_id"], sequence_number, actor="portal")
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=section_added", status_code=303)
    except SamjonMemoryError as e:
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=error: {e.message}", status_code=303)


@router.post("/portal/collections/{collection_id}/memories/{memory_id}/move-up", response_class=HTMLResponse)
async def portal_move_memory_up(collection_id: str, memory_id: str, request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    try:
        memories = svc.get_collection_memories(collection_id, limit=100, offset=0)
        ordered = sorted(memories, key=lambda m: m.get("sequence_number", 0))
        for i, m in enumerate(ordered):
            if m["memory_id"] == memory_id:
                if i > 0:
                    ordered[i], ordered[i-1] = ordered[i-1], ordered[i]
                break
        ordered_ids = [m["memory_id"] for m in ordered]
        svc.reorder_collection(collection_id, ordered_ids, actor="portal")
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=moved_up", status_code=303)
    except SamjonMemoryError as e:
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=error: {e.message}", status_code=303)


@router.post("/portal/collections/{collection_id}/memories/{memory_id}/move-down", response_class=HTMLResponse)
async def portal_move_memory_down(collection_id: str, memory_id: str, request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    try:
        memories = svc.get_collection_memories(collection_id, limit=100, offset=0)
        ordered = sorted(memories, key=lambda m: m.get("sequence_number", 0))
        for i, m in enumerate(ordered):
            if m["memory_id"] == memory_id:
                if i < len(ordered) - 1:
                    ordered[i], ordered[i+1] = ordered[i+1], ordered[i]
                break
        ordered_ids = [m["memory_id"] for m in ordered]
        svc.reorder_collection(collection_id, ordered_ids, actor="portal")
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=moved_down", status_code=303)
    except SamjonMemoryError as e:
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=error: {e.message}", status_code=303)


@router.post("/portal/collections/{collection_id}/order", response_class=HTMLResponse)
async def portal_reorder_collection(collection_id: str, request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    ordered = form.get("ordered_memory_ids", "")
    ordered_ids = [mid.strip() for mid in ordered.split(",") if mid.strip()]
    try:
        svc.reorder_collection(collection_id, ordered_ids, actor="portal")
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=reordered", status_code=303)
    except SamjonMemoryError as e:
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=error: {e.message}", status_code=303)


@router.post("/portal/collections/{collection_id}/activate", response_class=HTMLResponse)
async def portal_activate_collection(collection_id: str, request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    try:
        svc.activate_collection(collection_id, actor="portal")
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=activated", status_code=303)
    except SamjonMemoryError as e:
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=error: {e.message}", status_code=303)


@router.get("/portal/audit", response_class=HTMLResponse)
async def portal_audit(request: Request, _: str = Depends(portal_auth)):
    svc = _svc(request)
    entity_id = _q(request, "entity_id")
    entity_type = _q(request, "entity_type")
    action = _q(request, "action")
    records = svc.get_audit_records(
        entity_id=entity_id or None, entity_type=entity_type or None,
        action=action or None, limit=100, offset=0,
    )
    message = _q(request, "message")
    return HTMLResponse(content=pages.audit_log(
        records=records, entity_id=entity_id, entity_type=entity_type, action=action, message=message,
    ))