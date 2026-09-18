"""Capabilities endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/v1/capabilities")
async def capabilities():
    return {
        "service": "samjon-memory-core",
        "version": "1.0.0",
        "core_schema_version": "1.0.0",
        "routes": [
            "GET /health",
            "GET /ready",
            "GET /api/v1/capabilities",
            "POST /api/v1/core/memories",
            "GET /api/v1/core/memories/{memory_id}",
            "PATCH /api/v1/core/memories/{memory_id}",
            "POST /api/v1/core/memories/query",
            "POST /api/v1/core/memories/{memory_id}/supersede",
            "POST /api/v1/core/memories/{memory_id}/forget",
            "POST /api/v1/core/collections",
            "GET /api/v1/core/collections/{collection_id}",
            "PATCH /api/v1/core/collections/{collection_id}",
            "GET /api/v1/core/collections/{collection_id}/memories",
            "POST /api/v1/core/collections/{collection_id}/memories",
            "PUT /api/v1/core/collections/{collection_id}/order",
            "POST /api/v1/core/collections/{collection_id}/activate",
            "GET /api/v1/core/collections/{collection_id}/validate",
        ],
        "features": {
            "core_database": "samjon_core.sqlite",
            "resolver_database": "not implemented",
            "fts5": "not implemented",
            "semantic_search": "not implemented",
            "embeddings": "not implemented",
            "ai_enrichment": "not implemented",
            "portal": "authenticated",
            "backup_restore": "implemented",
        },
    }
