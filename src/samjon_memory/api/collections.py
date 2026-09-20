"Collection API endpoints."""
from fastapi import APIRouter, Header
from typing import List
from pydantic import BaseModel
from samjon_memory.core.service import CoreService
from samjon_memory.core.models import CollectionCreate, CollectionUpdate, CollectionMemoryCreate
router = APIRouter()


class _CollectionPurgeRequest(BaseModel):
    confirmation: str = ""

@router.post("/api/v1/core/collections", response_model=None)
async def create_collection(body: CollectionCreate, actor: str = Header("system")):
    service = CoreService()
    data = body.model_dump(exclude_unset=True)
    return service.create_collection(data, actor=actor)

@router.get("/api/v1/core/collections/{collection_id}", response_model=None)
async def get_collection(collection_id: str):
    service = CoreService()
    return service.get_collection(collection_id)

@router.patch("/api/v1/core/collections/{collection_id}", response_model=None)
async def update_collection(collection_id: str, body: CollectionUpdate, actor: str = Header("system")):
    service = CoreService()
    data = body.model_dump(exclude_unset=True)
    return service.update_collection(collection_id, data, actor=actor)

@router.get("/api/v1/core/collections/{collection_id}/memories", response_model=None)
async def get_collection_memories(collection_id: str, limit: int = 20, offset: int = 0):
    service = CoreService()
    return service.get_collection_memories(collection_id, limit=limit, offset=offset)

@router.post("/api/v1/core/collections/{collection_id}/memories", response_model=None)
async def add_memory_to_collection(collection_id: str, body: CollectionMemoryCreate, actor: str = Header("system")):
    service = CoreService()
    return service.add_section_to_collection(collection_id, body.model_dump(exclude_unset=True), actor=actor)

@router.put("/api/v1/core/collections/{collection_id}/order", response_model=None)
async def reorder_collection(collection_id: str, ordered_memory_ids: List[str], actor: str = Header("system")):
    service = CoreService()
    return service.reorder_collection(collection_id, ordered_memory_ids, actor=actor)

@router.post("/api/v1/core/collections/{collection_id}/activate", response_model=None)
async def activate_collection(collection_id: str, actor: str = Header("system")):
    service = CoreService()
    return service.activate_collection(collection_id, actor=actor)

@router.get("/api/v1/core/collections/{collection_id}/validate", response_model=None)
async def validate_collection(collection_id: str):
    service = CoreService()
    return service.validate_collection(collection_id)


@router.post("/api/v1/core/collections/{collection_id}/restore", response_model=None)
async def restore_collection(collection_id: str, actor: str = Header("system")):
    service = CoreService()
    return service.restore_collection(collection_id, actor=actor)


@router.post("/api/v1/core/collections/{collection_id}/purge", response_model=None)
async def purge_collection(collection_id: str, body: _CollectionPurgeRequest, actor: str = Header("system")):
    service = CoreService()
    return service.purge_collection(collection_id, confirmation=body.confirmation, actor=actor)
