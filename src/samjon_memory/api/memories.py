"Memory API endpoints."""
from fastapi import APIRouter, Header
from typing import Optional
from samjon_memory.core.service import CoreService
from samjon_memory.core.models import MemoryCreate, MemoryUpdate, MemoryQuery
from samjon_memory.errors import IdempotencyConflict
router = APIRouter()

@router.post("/api/v1/core/memories", response_model=None)
async def create_memory(body: MemoryCreate, x_idempotency_key: Optional[str] = Header(None), actor: str = Header("system")):
    service = CoreService()
    data = body.model_dump(exclude_unset=True)
    if x_idempotency_key:
        existing = service.conn.execute("SELECT * FROM idempotency_record WHERE idempotency_key=?", (x_idempotency_key,)).fetchone()
        if existing and existing["request_hash"] != str(hash(str(data))):
            raise IdempotencyConflict()
        if existing:
            return service.memories.get(existing["resulting_entity_id"])
    result = service.create_memory(data, actor=actor)
    return result

@router.get("/api/v1/core/memories/{memory_id}", response_model=None)
async def get_memory(memory_id: str):
    service = CoreService()
    return service.get_memory(memory_id)

@router.patch("/api/v1/core/memories/{memory_id}", response_model=None)
async def update_memory(memory_id: str, body: MemoryUpdate, actor: str = Header("system")):
    service = CoreService()
    data = body.model_dump(exclude_unset=True)
    return service.update_memory(memory_id, data, actor=actor)

@router.post("/api/v1/core/memories/query", response_model=None)
async def query_memories(body: MemoryQuery):
    service = CoreService()
    filters = body.model_dump(exclude_unset=True)
    return service.query_memories(**filters)

@router.post("/api/v1/core/memories/{memory_id}/supersede", response_model=None)
async def supersede_memory(memory_id: str, replacement_id: str, actor: str = Header("system")):
    service = CoreService()
    return service.supersede_memory(memory_id, replacement_id, actor=actor)

@router.post("/api/v1/core/memories/{memory_id}/forget", response_model=None)
async def forget_memory(memory_id: str, actor: str = Header("system")):
    service = CoreService()
    return service.forget_memory(memory_id, actor=actor)
