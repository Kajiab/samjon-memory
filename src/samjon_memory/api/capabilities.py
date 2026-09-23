"""Capabilities endpoint."""

from fastapi import APIRouter

from samjon_memory.constants import APP_VERSION, CORE_SCHEMA_VERSION

router = APIRouter()


@router.get("/api/v1/capabilities")
async def capabilities():
    return {
        "service": "samjon-memory-core",
        "version": APP_VERSION,
        "core_schema_version": CORE_SCHEMA_VERSION,
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
            "portal": {
                "implemented": True,
                "architecture": "server_rendered",
                "authentication": "http_basic",
                "users_supported": 1,
                "roles": ["admin"],
                "session_cookie": False,
                "custom_login_page": False,
                "origin_validation": True,
                "local_network_only": True,
                "public_internet_approved": False,
                "status": "core_v1_local_admin",
            },
            "backup_restore": "implemented",
        },
    }
