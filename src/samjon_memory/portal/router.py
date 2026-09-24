"""Server-rendered Core Portal router. AGENTS.md v2.1.0."""
import html as _html
import hmac as _hmac
from urllib.parse import urlparse as _urlparse
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from samjon_memory.core.service import CoreService
from samjon_memory.errors import SamjonMemoryError
from samjon_memory.config import config
from samjon_memory.constants import DEFAULT_PAGE_SIZE
import samjon_memory.portal.pages as pages
import samjon_memory.portal.templating as templating
import samjon_memory.portal.viewmodels as viewmodels
import samjon_memory.resolver.portal as rpages
from samjon_memory.resolver.service import ResolverService

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


def _resolver_svc(request: Request) -> ResolverService:
    svc = getattr(request.app.state, "resolver_service", None)
    if svc is None:
        svc = ResolverService()
        request.app.state.resolver_service = svc
    return svc


def _q(request: Request, key: str, default: str = "") -> str:
    return request.query_params.get(key, default)


@router.get("/portal/", response_class=HTMLResponse)
async def portal_index(request: Request, _: str = Depends(portal_auth)):
    svc = _svc(request)
    q = _q(request, "q")
    active = svc.library_active()
    categories = pages.category_model(active)
    # Representative cover per category (presentation-only view model).
    for cat in categories:
        cover = None
        for col in active["collections"]:
            if pages.category_matches(cat, col.get("subject")):
                cover = svc._library_cover("collection", col)
                break
        if not cover:
            for m in active["memories"]:
                if pages.category_matches(cat, m.get("subject")):
                    cover = svc._library_cover("memory", m)
                    break
        if cover:
            cat["entity_cover"] = cover
    discover = svc.library_discover(12)
    recent = svc.library_recent(8)
    return HTMLResponse(content=templating.render(
        "library/home.html", active="library",
        **viewmodels.library_home_vm(categories, discover, recent, q)))


@router.get("/portal/status", response_class=HTMLResponse)
async def portal_status(request: Request, _: str = Depends(portal_auth)):
    svc = _svc(request)
    stats = svc.dashboard_stats()
    recent = svc.get_audit_records(limit=8, offset=0)
    message = _q(request, "message")
    return HTMLResponse(content=templating.render(
        "admin/status.html", active="status",
        **viewmodels.dashboard_vm(stats, recent, message)))


@router.get("/portal/library/subjects/{category_key}", response_class=HTMLResponse)
async def portal_subject_category(request: Request, category_key: str, _: str = Depends(portal_auth)):
    svc = _svc(request)
    category = pages.category_by_key(category_key)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    page_size = 20
    offset = int(_q(request, "offset", "0"))
    active = svc.library_active()
    cols = [c for c in active["collections"] if pages.category_matches(category, c.get("subject"))]
    mems = [m for m in active["memories"] if pages.category_matches(category, m.get("subject"))]
    ordered = [("collection", c) for c in cols] + [("memory", m) for m in mems]
    total = len(ordered)
    page = ordered[offset:offset + page_size]
    page_cols, page_mems = [], []
    for t, e in page:
        e["cover"] = svc._library_cover(t, e)
        (page_cols if t == "collection" else page_mems).append(e)
    return HTMLResponse(content=templating.render(
        "library/category.html", active="library",
        **viewmodels.category_page_vm(category, page_cols, page_mems,
                                      offset, total, page_size)))


@router.get("/portal/admin", response_class=HTMLResponse)
async def portal_admin(request: Request, _: str = Depends(portal_auth)):
    svc = _svc(request)
    stats = svc.admin_stats()
    resolver = {}
    try:
        resolver = _resolver_svc(request).portal_dashboard(svc)
    except Exception:
        resolver = {"status": "not_ready"}
    message = _q(request, "message")
    return HTMLResponse(content=templating.render(
        "admin/administration.html", active="admin",
        **viewmodels.admin_vm(stats, message, resolver)))


@router.get("/portal/memories", response_class=HTMLResponse)
async def portal_memories(request: Request, _: str = Depends(portal_auth)):
    svc = _svc(request)
    subject = _q(request, "subject")
    status_filter = _q(request, "status")
    scope = _q(request, "scope")
    offset = int(_q(request, "offset", "0"))
    memories = svc.query_memories(
        subject=subject or None,
        status=status_filter or None,
        collection_scope=scope or None,
        limit=DEFAULT_PAGE_SIZE,
        offset=offset,
    )
    message = _q(request, "message")
    return HTMLResponse(content=templating.render(
        "memories/list.html", active="memories",
        **viewmodels.memory_list_vm(memories, subject or "", status_filter,
                                    scope, offset, message)))


@router.get("/portal/memories/create", response_class=HTMLResponse)
async def portal_memory_create_form(request: Request, _: str = Depends(portal_auth)):
    message = _q(request, "message")
    error = _q(request, "error")
    return HTMLResponse(content=templating.render(
        "memories/create.html", active="memories",
        **viewmodels.memory_create_vm(message, error)))


@router.post("/portal/memories", response_class=HTMLResponse)
async def portal_memory_create(request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    data = {
        "subject": form.get("subject", ""),
        "title": form.get("title", "") or None,
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
        return HTMLResponse(content=templating.render(
            "memories/create.html", active="memories",
            **viewmodels.memory_create_vm("", e.message)), status_code=e.status_code)


@router.get("/portal/memories/{memory_id}", response_class=HTMLResponse)
async def portal_memory_detail(request: Request, memory_id: str, _: str = Depends(portal_auth)):
    svc = _svc(request)
    try:
        memory = svc.get_memory(memory_id)
    except SamjonMemoryError as e:
        return HTMLResponse(content=templating.render("error.html", message=e.message),
                            status_code=e.status_code)
    message = _q(request, "message")
    media = svc.list_media("memory", memory["memory_id"])
    return HTMLResponse(content=templating.render(
        "memories/detail.html", active="memories",
        **viewmodels.memory_detail_vm(memory, message, media)))


@router.post("/portal/memories/{memory_id}/activate", response_class=HTMLResponse)
async def portal_activate_memory(memory_id: str, request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    raw = form.get("expected_version")
    try:
        expected_version = int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        expected_version = None
    try:
        svc.activate_memory(memory_id, expected_version=expected_version, actor="portal")
        return RedirectResponse(
            url=f"/portal/memories/{memory_id}?message=memory_activated", status_code=303,
        )
    except SamjonMemoryError as e:
        return RedirectResponse(
            url=f"/portal/memories/{memory_id}?message=error: {e.message}", status_code=303,
        )


@router.post("/portal/memories/{memory_id}/restore", response_class=HTMLResponse)
async def portal_restore_memory(memory_id: str, request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    try:
        svc.restore_memory(memory_id, actor="portal")
        return RedirectResponse(url=f"/portal/memories/{memory_id}?message=restored", status_code=303)
    except SamjonMemoryError as e:
        return RedirectResponse(url=f"/portal/memories/{memory_id}?message=error: {e.message}", status_code=303)


@router.post("/portal/memories/{memory_id}/purge", response_class=HTMLResponse)
async def portal_purge_memory(memory_id: str, request: Request, username: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    confirmation = form.get("confirmation", "") or ""
    raw = form.get("expected_version")
    try:
        expected_version = int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        expected_version = None
    try:
        svc.purge_memory(memory_id, confirmation=confirmation, expected_version=expected_version, actor=username)
        return RedirectResponse(url=f"/portal/memories/{memory_id}?message=purged", status_code=303)
    except SamjonMemoryError as e:
        return RedirectResponse(url=f"/portal/memories/{memory_id}?message=error: {e.message}", status_code=303)


@router.get("/portal/memories/{memory_id}/edit", response_class=HTMLResponse)
async def portal_memory_edit_form(request: Request, memory_id: str, _: str = Depends(portal_auth)):
    svc = _svc(request)
    try:
        memory = svc.get_memory(memory_id)
    except SamjonMemoryError as e:
        return HTMLResponse(content=templating.render("error.html", message=e.message),
                            status_code=e.status_code)
    message = _q(request, "message")
    error = _q(request, "error")
    return HTMLResponse(content=templating.render(
        "memories/edit.html", active="memories",
        **viewmodels.memory_edit_vm(memory, message, error)))


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
            return HTMLResponse(content=templating.render(
                "memories/edit.html", active="memories",
                **viewmodels.memory_edit_vm(
                    mem, "",
                    "Version conflict: the memory was modified by another request. "
                    "Please review and resubmit.")), status_code=409)
        try:
            mem = svc.get_memory(memory_id)
        except SamjonMemoryError:
            mem = None
        error_msg = e.message if isinstance(e, SamjonMemoryError) else str(e)
        return HTMLResponse(content=templating.render(
            "memories/edit.html", active="memories",
            **viewmodels.memory_edit_vm(mem, "", error_msg)),
            status_code=400 if isinstance(e, ValueError) else e.status_code)


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
        return HTMLResponse(content=templating.render(
            "memories/detail.html", active="memories",
            **viewmodels.memory_detail_vm(
                memory, e.message,
                (svc.list_media("memory", memory["memory_id"]) if memory else []))),
            status_code=e.status_code)


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
        return HTMLResponse(content=templating.render(
            "memories/detail.html", active="memories",
            **viewmodels.memory_detail_vm(
                memory, e.message,
                (svc.list_media("memory", memory["memory_id"]) if memory else []))),
            status_code=e.status_code)


@router.get("/portal/collections", response_class=HTMLResponse)
async def portal_collections(request: Request, _: str = Depends(portal_auth)):
    svc = _svc(request)
    status = _q(request, "status")
    invalid = _q(request, "invalid") in ("1", "true", "True", "on")
    collections = svc.list_collections(status=status or None, invalid=invalid, limit=100, offset=0)
    message = _q(request, "message")
    return HTMLResponse(content=templating.render(
        "collections/list.html", active="collections",
        **viewmodels.collection_list_vm(collections, message, status, invalid)))


@router.get("/portal/collections/create", response_class=HTMLResponse)
async def portal_collection_create_form(request: Request, _: str = Depends(portal_auth)):
    message = _q(request, "message")
    error = _q(request, "error")
    return HTMLResponse(content=templating.render(
        "collections/create.html", active="collections",
        **viewmodels.collection_create_vm(message, error)))


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
        return HTMLResponse(content=templating.render(
            "collections/create.html", active="collections",
            **viewmodels.collection_create_vm("", e.message)), status_code=e.status_code)


@router.get("/portal/collections/{collection_id}", response_class=HTMLResponse)
async def portal_collection_detail(request: Request, collection_id: str, _: str = Depends(portal_auth)):
    svc = _svc(request)
    try:
        collection = svc.get_collection(collection_id)
    except SamjonMemoryError as e:
        return HTMLResponse(content=templating.render("error.html", message=e.message),
                            status_code=e.status_code)
    memories = svc.get_collection_memories_all(collection_id)
    for _m in memories:
        try:
            _m["media"] = svc.list_media("memory", _m["memory_id"])
        except Exception:
            _m["media"] = []
    validation = svc.validate_collection(collection_id)
    message = _q(request, "message")
    reopened = svc.collection_was_reopened(collection_id)
    media = svc.list_media("collection", collection_id)
    return HTMLResponse(content=templating.render(
        "collections/detail.html", active="collections",
        **viewmodels.collection_detail_vm(
            collection, memories, validation, message, reopened, media)))


@router.get("/portal/collections/{collection_id}/edit", response_class=HTMLResponse)
async def portal_collection_edit_form(request: Request, collection_id: str, _: str = Depends(portal_auth)):
    svc = _svc(request)
    try:
        collection = svc.get_collection(collection_id)
    except SamjonMemoryError as e:
        return HTMLResponse(content=templating.render("error.html", message=e.message),
                            status_code=e.status_code)
    message = _q(request, "message")
    error = _q(request, "error")
    return HTMLResponse(content=templating.render(
        "collections/edit.html", active="collections",
        **viewmodels.collection_edit_vm(collection, message, error)))


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
            content=templating.render(
                "collections/detail.html", active="collections",
                **viewmodels.collection_detail_vm(
                    collection, [], {"valid": True, "issues": [], "memory_count": 0},
                    e.message, False,
                    (svc.list_media("collection", collection_id) if collection else []))),
            status_code=e.status_code,
        )


@router.post("/portal/collections/{collection_id}/memories", response_class=HTMLResponse)
async def portal_add_memory_to_collection(collection_id: str, request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    data = {
        "title": form.get("title", ""),
        "memory_type": form.get("memory_type", "fact"),
        "raw_content": form.get("raw_content", ""),
        "language": form.get("language", "en"),
        "source": "portal",
    }
    if form.get("structured_value", ""):
        data["structured_value_json"] = form["structured_value"]
    if form.get("sequence_number", ""):
        try:
            data["sequence_number"] = int(form["sequence_number"])
        except (TypeError, ValueError):
            pass
    try:
        svc.add_section_to_collection(collection_id, data, actor="portal")
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=section_added", status_code=303)
    except SamjonMemoryError as e:
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=error: {e.message}", status_code=303)


@router.post("/portal/collections/{collection_id}/memories/{memory_id}/move-up", response_class=HTMLResponse)
async def portal_move_memory_up(collection_id: str, memory_id: str, request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    try:
        memories = svc.get_collection_memories_all(collection_id)
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
        memories = svc.get_collection_memories_all(collection_id)
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


@router.post("/portal/collections/{collection_id}/restore", response_class=HTMLResponse)
async def portal_restore_collection(collection_id: str, request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    try:
        svc.restore_collection(collection_id, actor="portal")
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=restored", status_code=303)
    except SamjonMemoryError as e:
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=error: {e.message}", status_code=303)


@router.post("/portal/collections/{collection_id}/purge", response_class=HTMLResponse)
async def portal_purge_collection(collection_id: str, request: Request, username: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    confirmation = form.get("confirmation", "") or ""
    try:
        svc.purge_collection(collection_id, confirmation=confirmation, actor=username)
        return RedirectResponse(url=f"/portal/collections/{collection_id}?message=purged", status_code=303)
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


def _q_int(request: Request, key: str, default: int) -> int:
    try:
        return int(request.query_params.get(key, default))
    except (TypeError, ValueError):
        return default


@router.get("/portal/audit", response_class=HTMLResponse)
async def portal_audit(request: Request, _: str = Depends(portal_auth)):
    svc = _svc(request)
    entity_id = _q(request, "entity_id")
    entity_type = _q(request, "entity_type")
    action = _q(request, "action")
    since = _q(request, "since")
    until = _q(request, "until")
    offset = _q_int(request, "offset", 0)
    page_size = 50
    records = svc.get_audit_records(
        entity_id=entity_id or None, entity_type=entity_type or None,
        action=action or None, since=since or None, until=until or None,
        limit=page_size, offset=offset,
    )
    summary = svc.audit_summary(
        entity_type=entity_type or None, action=action or None,
        since=since or None, until=until or None,
    )
    message = _q(request, "message")
    return HTMLResponse(content=templating.render(
        "admin/audit.html", active="audit",
        **viewmodels.audit_vm(
            records=records, entity_id=entity_id, entity_type=entity_type, action=action,
            since=since, until=until, offset=offset, page_size=page_size,
            count=offset + len(records) + (1 if len(records) == page_size else 0),
            message=message, summary=summary)))
# ---- Resolver Search (user-facing) ----------------------------------------

def _enrich_search_result(core, entry):
    """Return a result entry only if its authoritative Core entity is active.

    Drops drafts/superseded/forgotten/purged entities and anything whose
    authoritative record cannot be loaded (no fallback to stale projection).
    For Collection sections the parent Collection must also be active.
    """
    entry = dict(entry)
    rt = entry.get("result_type")
    entry["entity_id"] = entry.get("memory_id") or entry.get("collection_id")
    if rt in ("standalone_memory", "collection_memory"):
        try:
            m = core.get_memory(entry.get("memory_id"))
        except Exception:
            return None
        if m.get("status") != "active":
            return None
        entry["title"] = m.get("title") or m.get("subject")
        entry["excerpt"] = (m.get("raw_content") or "")[:240]
        entry["checksum"] = m.get("content_checksum")
        entry["core_version"] = m.get("version")
        entry["status"] = m.get("status")
        if rt == "collection_memory" and entry.get("collection_id"):
            try:
                parent = core.get_collection(entry["collection_id"])
            except Exception:
                return None
            if parent.get("status") != "active":
                return None
            entry["collection_title"] = parent.get("title") or parent.get("subject")
    else:  # collection / collection_with_selected_memories
        try:
            c = core.get_collection(entry.get("collection_id"))
        except Exception:
            return None
        if c.get("status") != "active":
            return None
        entry["title"] = c.get("title") or c.get("subject")
        entry["excerpt"] = (c.get("summary") or "")[:240]
        entry["checksum"] = c.get("content_checksum")
        entry["core_version"] = c.get("version")
        entry["status"] = c.get("status")
        entry["collection_title"] = entry.get("title")
        clean = []
        for sec in entry.get("selected_sections") or []:
            try:
                sm = core.get_memory(sec.get("memory_id"))
            except Exception:
                continue
            if sm.get("status") != "active":
                continue
            sec["title"] = sm.get("title") or sm.get("subject")
            clean.append(sec)
        entry["selected_sections"] = clean
    try:
        if rt in ("collection", "collection_with_selected_memories"):
            cover = core.get_media_cover("collection", entry.get("collection_id"))
        else:
            cover = core.get_media_cover("memory", entry.get("memory_id"))
        if cover:
            entry["cover_thumb_url"] = pages._media_thumb_url(cover["media_id"])
            entry["cover_thumb_source"] = (
                "collection" if rt in ("collection", "collection_with_selected_memories") else "memory")
            entry["cover_alt"] = cover.get("alt_text") or cover.get("caption") or ""
            entry["cover_width"] = cover.get("width")
            entry["cover_height"] = cover.get("height")
        elif rt == "collection_memory" and entry.get("collection_id"):
            # Optional fallback: a Section without its own cover may use the
            # parent Collection cover as a visual placeholder (source marked).
            try:
                pcover = core.get_media_cover("collection", entry["collection_id"])
            except Exception:
                pcover = None
            if pcover:
                entry["cover_thumb_url"] = pages._media_thumb_url(pcover["media_id"])
                entry["cover_thumb_source"] = "collection_cover_fallback"
                entry["cover_alt"] = pcover.get("alt_text") or pcover.get("caption") or ""
                entry["cover_width"] = pcover.get("width")
                entry["cover_height"] = pcover.get("height")
    except Exception:
        pass
    return entry


def _suggestion_for(q):
    words = [w for w in (q or "").split() if w]
    if not words:
        return ""
    return f"Try a single keyword like \"{words[0]}\", or use the exact title name."


def _portal_search_page(request, q):
    core = _svc(request)
    result = None
    enriched = []
    stale = False
    error = ""
    try:
        _resolver_svc(request).readiness()
    except Exception:
        pass
    if q:
        try:
            result = _resolver_svc(request).search(
                core, q, target="auto", limit=20, allow_stale=True)
        except SamjonMemoryError as exc:
            error = exc.message
            result = None
        if result is not None:
            stale = bool(result.get("projection_freshness") == "stale") or bool(result.get("incomplete"))
            enriched = [e for e in (_enrich_search_result(core, e) for e in result.get("results", [])) if e]
    total = result.get("total", 0) if result else 0
    memories = [e for e in enriched if e.get("result_type") == "standalone_memory"]
    collections = [e for e in enriched if e.get("result_type") in ("collection", "collection_with_selected_memories")]
    sections = [e for e in enriched if e.get("result_type") == "collection_memory"]
    return HTMLResponse(content=templating.render(
        "search.html", active="library",
        **viewmodels.search_vm(q, memories, collections, sections,
                               stale, error, total, _suggestion_for(q))))


@router.get("/portal/search", response_class=HTMLResponse)
async def portal_search(request: Request, _: str = Depends(portal_auth)):
    q = (_q(request, "q") or "").strip()
    return _portal_search_page(request, q)


@router.post("/portal/search", response_class=HTMLResponse)
async def portal_search_post(request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    form = await request.form()
    q = (form.get("q") or "").strip()
    return _portal_search_page(request, q)


# ---- Library Reader (read-only) --------------------------------------------

@router.get("/portal/library/memories/{memory_id}", response_class=HTMLResponse)
async def portal_library_memory(request: Request, memory_id: str, _: str = Depends(portal_auth)):
    svc = _svc(request)
    try:
        memory = svc.get_memory(memory_id)
    except SamjonMemoryError as e:
        return HTMLResponse(content=templating.render("error.html", message=e.message),
                            status_code=e.status_code)
    back = _q(request, "back", "/portal/search")
    collection_title = ""
    if memory.get("collection_id"):
        try:
            parent = svc.get_collection(memory["collection_id"])
            collection_title = parent.get("title") or parent.get("subject")
        except Exception:
            collection_title = ""
    media = svc.list_media("memory", memory["memory_id"])
    return HTMLResponse(content=templating.render(
        "library/memory_reader.html", active="library",
        **viewmodels.memory_reader_vm(memory, back, collection_title, media)))


@router.get("/portal/library/collections/{collection_id}", response_class=HTMLResponse)
async def portal_library_collection(request: Request, collection_id: str, _: str = Depends(portal_auth)):
    svc = _svc(request)
    try:
        collection = svc.get_collection(collection_id)
        sections = svc.get_collection_memories_all(collection_id)
    except SamjonMemoryError as e:
        return HTMLResponse(content=templating.render("error.html", message=e.message),
                            status_code=e.status_code)
    back = _q(request, "back", "/portal/search")
    media = svc.list_media("collection", collection_id)
    for sec in sections:
        try:
            sec["media"] = svc.list_media("memory", sec["memory_id"])
        except Exception:
            sec["media"] = []
    return HTMLResponse(content=templating.render(
        "library/collection_reader.html", active="library",
        **viewmodels.collection_reader_vm(collection, sections, back, media)))


@router.post("/portal/admin/resolver/rebuild", response_class=HTMLResponse)
async def portal_admin_resolver_rebuild(request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    if (form.get("confirmation") or "").strip() != "REBUILD":
        return RedirectResponse(url="/portal/admin?message=error: Type REBUILD to confirm", status_code=303)
    try:
        _resolver_svc(request).full_rebuild(svc)
        return RedirectResponse(url="/portal/admin?message=resolver_rebuilt", status_code=303)
    except SamjonMemoryError as e:
        return RedirectResponse(url=f"/portal/admin?message=error: {e.message}", status_code=303)


@router.post("/portal/admin/resolver/rebuild/selective", response_class=HTMLResponse)
async def portal_admin_resolver_rebuild_selective(request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    if (form.get("confirmation") or "").strip() != "REBUILD":
        return RedirectResponse(url="/portal/admin?message=error: Type REBUILD to confirm", status_code=303)
    entity_type = (form.get("entity_type") or "").strip()
    entity_id = (form.get("entity_id") or "").strip()
    try:
        _resolver_svc(request).selective_rebuild(svc, entity_type, entity_id)
        return RedirectResponse(url="/portal/admin?message=resolver_rebuilt", status_code=303)
    except SamjonMemoryError as e:
        return RedirectResponse(url=f"/portal/admin?message=error: {e.message}", status_code=303)


# ---- Resolver Debug Portal (reuses Portal HTTP Basic + exact Origin) ------
import urllib.parse as _urlparse_redirect


def _res_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(
        url="/portal/resolver/rebuild?message=" + _urlparse_redirect.quote(message),
        status_code=303,
    )


@router.get("/portal/resolver/", response_class=HTMLResponse)
async def resolver_portal_dashboard(request: Request, _: str = Depends(portal_auth)):
    core = _svc(request)
    data = _resolver_svc(request).portal_dashboard(core)
    return HTMLResponse(content=rpages.dashboard(data))


@router.get("/portal/resolver/query", response_class=HTMLResponse)
async def resolver_portal_query(request: Request, _: str = Depends(portal_auth)):
    core = _svc(request)
    form = {
        "query": _q(request, "query"),
        "target": _q(request, "target", "auto"),
        "scope": _q(request, "scope"),
        "collection_id": _q(request, "collection_id"),
        "allow_stale": _q(request, "allow_stale"),
        "neighbor_items": _q(request, "neighbor_items", "0"),
        "context_budget": _q(request, "context_budget", "0"),
    }
    result = None
    error = ""
    if form["query"]:
        try:
            result = _resolver_svc(request).search(
                core,
                form["query"],
                target=form["target"] or "auto",
                scope=form["scope"] or None,
                collection_id=form["collection_id"] or None,
                allow_stale=form["allow_stale"] == "1",
                neighbor_items=int(form["neighbor_items"] or 0),
                context_budget=int(form["context_budget"] or 0),
            )
        except SamjonMemoryError as exc:
            error = exc.message
    html = rpages.query_page(form, result)
    if error:
        html = html.replace(
            "<h2>Query Debug</h2>",
            '<h2>Query Debug</h2><div class="err">' + _e(error) + "</div>",
        )
    return HTMLResponse(content=html)


@router.get("/portal/resolver/projection", response_class=HTMLResponse)
async def resolver_portal_projection(request: Request, _: str = Depends(portal_auth)):
    core = _svc(request)
    entity_type = _q(request, "entity_type") or None
    freshness = _q(request, "freshness") or None
    offset = 0
    try:
        offset = max(0, int(_q(request, "offset", "0")))
    except (TypeError, ValueError):
        offset = 0
    data = _resolver_svc(request).portal_projection(
        core, entity_type=entity_type, freshness_filter=freshness, limit=100, offset=offset)
    return HTMLResponse(content=rpages.projection_page(
        data, {"entity_type": entity_type or "", "freshness": freshness or ""}))


@router.get("/portal/resolver/rebuild", response_class=HTMLResponse)
async def resolver_portal_rebuild(request: Request, _: str = Depends(portal_auth)):
    core = _svc(request)
    rsvc = _resolver_svc(request)
    build = rsvc.portal_dashboard(core)
    status = rsvc.rebuild_status()
    message = _q(request, "message")
    return HTMLResponse(content=rpages.rebuild_page(build, status, message))


@router.get("/portal/resolver/evidence", response_class=HTMLResponse)
async def resolver_portal_evidence(request: Request, _: str = Depends(portal_auth)):
    core = _svc(request)
    entity_type = _q(request, "entity_type")
    entity_id = _q(request, "entity_id")
    data = {}
    if entity_type and entity_id:
        data = _resolver_svc(request).portal_evidence(core, entity_type, entity_id)
    return HTMLResponse(content=rpages.evidence_page(data))


@router.post("/portal/resolver/rebuild", response_class=HTMLResponse)
async def resolver_portal_rebuild_post(request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    core = _svc(request)
    form = await request.form()
    confirmation = str(form.get("confirmation") or "").strip().lower()
    if confirmation != "rebuild":
        return _res_redirect("confirmation required")
    try:
        _resolver_svc(request).full_rebuild(core)
        return _res_redirect("full rebuild ok")
    except SamjonMemoryError as exc:
        return _res_redirect("error: " + exc.message)


@router.post("/portal/resolver/rebuild/selective", response_class=HTMLResponse)
async def resolver_portal_rebuild_selective_post(request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    core = _svc(request)
    form = await request.form()
    confirmation = str(form.get("confirmation") or "").strip().lower()
    if confirmation != "rebuild":
        return _res_redirect("confirmation required")
    entity_type = str(form.get("entity_type") or "")
    entity_id = str(form.get("entity_id") or "")
    if entity_type not in ("memory", "collection") or not entity_id:
        return _res_redirect("invalid selective target")
    try:
        _resolver_svc(request).selective_rebuild(core, entity_type, entity_id)
        return _res_redirect("selective rebuild ok")
    except SamjonMemoryError as exc:
        return _res_redirect("error: " + exc.message)
# ---- Media (images) routes --------------------------------------------------
# Mutations require HTTP Basic (portal_auth) + exact Origin. Image serving
# requires Portal authentication. All paths are server-generated; never user
# controlled. Portal/API call CoreService only (never the filesystem directly).

def _media_admin_back(entity_type: str, entity_id: str) -> str:
    prefix = "collections" if entity_type == "collection" else "memories"
    return f"/portal/{prefix}/{entity_id}"


def _safe_media_back(raw, fallback: str) -> str:
    """Allow only internal Portal redirect targets for inline Section media.

    Rejects absolute URLs, protocol-relative URLs (//), parent-directory
    traversal, schemes (':'), and any non-/portal path. Falls back otherwise.
    """
    if not raw:
        return fallback
    path = str(raw).strip()
    if path.startswith(("//", "http:", "https:", "ftp:")):
        return fallback
    if ".." in path or "\\" in path or ":" in path:
        return fallback
    if not (path.startswith("/portal/memories/") or path.startswith("/portal/collections/")):
        return fallback
    return path


def _media_back(form, fallback: str) -> str:
    """Validate the ``back`` hidden field from a media mutation form."""
    return _safe_media_back(form.get("back", "") if form else "", fallback)


def _media_redirect(back: str, message: str) -> RedirectResponse:
    path = back
    frag = ""
    if "#" in back:
        path, frag = back.split("#", 1)
        frag = "#" + frag
    url = path + ("&" if "?" in path else "?") + "message=" + _urlparse_redirect.quote(message)
    return RedirectResponse(url=url + frag, status_code=303)


@router.post("/portal/media/upload", response_class=HTMLResponse)
async def portal_media_upload(request: Request, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    entity_type = str(form.get("entity_type") or "")
    entity_id = str(form.get("entity_id") or "")
    alt_text = (form.get("alt_text") or "") or None
    caption = (form.get("caption") or "") or None
    raw = form.get("file")
    data = (await raw.read()) if raw else b""
    back = _media_back(form, _media_admin_back(entity_type, entity_id))
    try:
        svc.upload_media(entity_type, entity_id, data, alt_text=alt_text,
                         caption=caption, actor="portal")
        return _media_redirect(back, "image-uploaded")
    except SamjonMemoryError as e:
        return _media_redirect(back, "error: " + e.message)


@router.post("/portal/media/{media_id}/cover", response_class=HTMLResponse)
async def portal_media_cover(request: Request, media_id: str, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    try:
        record = svc.get_media(media_id)
        svc.set_media_cover(media_id, actor="portal")
        return _media_redirect(_media_back(form, _media_admin_back(record["entity_type"], record["entity_id"])),
                               "cover-updated")
    except SamjonMemoryError as e:
        return _media_redirect("/portal/memories", "error: " + e.message)


@router.post("/portal/media/{media_id}/metadata", response_class=HTMLResponse)
async def portal_media_metadata(request: Request, media_id: str, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    alt_text = (form.get("alt_text") or "") or None
    caption = (form.get("caption") or "") or None
    try:
        record = svc.get_media(media_id)
        svc.update_media_metadata(media_id, alt_text=alt_text, caption=caption, actor="portal")
        return _media_redirect(_media_back(form, _media_admin_back(record["entity_type"], record["entity_id"])),
                               "metadata-updated")
    except SamjonMemoryError as e:
        return _media_redirect("/portal/memories", "error: " + e.message)
def _move_media(svc, media_id, direction):
    record = svc.get_media(media_id)
    active = svc.list_media(record["entity_type"], record["entity_id"])
    ids = [m["media_id"] for m in active]
    idx = ids.index(media_id)
    swap = idx - 1 if direction == "left" else idx + 1
    if swap < 0 or swap >= len(ids):
        raise ValueError("cannot move")
    ids[idx], ids[swap] = ids[swap], ids[idx]
    svc.reorder_media(record["entity_type"], record["entity_id"], ids, actor="portal")


@router.post("/portal/media/{media_id}/move-left", response_class=HTMLResponse)
async def portal_media_move_left(request: Request, media_id: str, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    try:
        record = svc.get_media(media_id)
        _move_media(svc, media_id, "left")
        return _media_redirect(_media_back(form, _media_admin_back(record["entity_type"], record["entity_id"])),
                               "reordered")
    except SamjonMemoryError as e:
        return _media_redirect("/portal/memories", "error: " + e.message)


@router.post("/portal/media/{media_id}/move-right", response_class=HTMLResponse)
async def portal_media_move_right(request: Request, media_id: str, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    try:
        record = svc.get_media(media_id)
        _move_media(svc, media_id, "right")
        return _media_redirect(_media_back(form, _media_admin_back(record["entity_type"], record["entity_id"])),
                               "reordered")
    except SamjonMemoryError as e:
        return _media_redirect("/portal/memories", "error: " + e.message)


@router.post("/portal/media/{media_id}/replace", response_class=HTMLResponse)
async def portal_media_replace(request: Request, media_id: str, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    raw = form.get("file")
    data = (await raw.read()) if raw else b""
    try:
        record = svc.get_media(media_id)
        svc.replace_media(media_id, data, actor="portal")
        return _media_redirect(_media_back(form, _media_admin_back(record["entity_type"], record["entity_id"])),
                               "image-replaced")
    except SamjonMemoryError as e:
        return _media_redirect("/portal/memories", "error: " + e.message)


@router.post("/portal/media/{media_id}/remove", response_class=HTMLResponse)
async def portal_media_remove(request: Request, media_id: str, _: str = Depends(portal_auth)):
    validate_origin(request)
    svc = _svc(request)
    form = await request.form()
    try:
        record = svc.get_media(media_id)
        svc.remove_media(media_id, actor="portal")
        return _media_redirect(_media_back(form, _media_admin_back(record["entity_type"], record["entity_id"])),
                               "image-removed")
    except SamjonMemoryError as e:
        return _media_redirect("/portal/memories", "error: " + e.message)


@router.get("/portal/media/{media_id}/original")
async def portal_media_original(request: Request, media_id: str, _: str = Depends(portal_auth)):
    try:
        data, record = _svc(request).read_media_original(media_id)
    except SamjonMemoryError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return Response(content=data, media_type=record["mime_type"])


@router.get("/portal/media/{media_id}/thumb")
async def portal_media_thumb(request: Request, media_id: str, _: str = Depends(portal_auth)):
    try:
        data, record = _svc(request).read_media_thumbnail(media_id)
    except SamjonMemoryError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return Response(content=data, media_type=record["mime_type"])