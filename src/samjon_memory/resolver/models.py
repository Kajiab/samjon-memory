"""Pydantic models for the Resolver query API."""

from typing import Optional

from pydantic import BaseModel, Field

from samjon_memory.resolver.constants import (
    DEFAULT_QUERY_LIMIT,
    MAX_QUERY_LIMIT,
    TARGET_AUTO,
)


class ResolverQuery(BaseModel):
    query: str = Field(..., min_length=1)
    target: str = Field(default=TARGET_AUTO)
    collection_id: Optional[str] = None
    scope: Optional[str] = None
    limit: int = Field(default=DEFAULT_QUERY_LIMIT, ge=1, le=MAX_QUERY_LIMIT)
    offset: int = Field(default=0, ge=0)
    allow_stale: bool = Field(default=False)
    epsilon: Optional[float] = None