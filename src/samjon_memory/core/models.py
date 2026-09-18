"""Pydantic models for Samjon Memory Core."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class MemoryCreate(BaseModel):
    collection_id: Optional[str] = None
    sequence_number: Optional[int] = None
    subject: str = Field(..., min_length=1, max_length=500)
    memory_type: str = Field(default="fact", max_length=100)
    scope: str = Field(default="household", max_length=100)
    title: Optional[str] = Field(default=None, max_length=500)
    section_path: Optional[str] = None
    raw_content: str = Field(..., min_length=1)
    structured_value_json: Optional[str] = None
    source: str = Field(..., max_length=200)
    language: str = Field(default="en", max_length=10)
    status: str = Field(default="draft")
    content_checksum: Optional[str] = None

    @field_validator("raw_content")
    @classmethod
    def validate_raw_content(cls, v: str) -> str:
        if len(v) > 16384:
            raise ValueError("raw_content exceeds 16384 characters")
        return v


class MemoryUpdate(BaseModel):
    subject: Optional[str] = Field(default=None, max_length=500)
    memory_type: Optional[str] = Field(default=None, max_length=100)
    scope: Optional[str] = Field(default=None, max_length=100)
    title: Optional[str] = Field(default=None, max_length=500)
    section_path: Optional[str] = None
    raw_content: Optional[str] = None
    structured_value_json: Optional[str] = None
    source: Optional[str] = Field(default=None, max_length=200)
    language: Optional[str] = Field(default=None, max_length=10)
    expected_version: Optional[int] = None

    @field_validator("raw_content")
    @classmethod
    def validate_raw_content(cls, v):
        if v is not None and len(v) > 16384:
            raise ValueError("raw_content exceeds 16384 characters")
        return v


class MemoryResponse(BaseModel):
    memory_id: str
    collection_id: Optional[str]
    sequence_number: Optional[int]
    subject: str
    memory_type: str
    scope: str
    title: Optional[str]
    section_path: Optional[str]
    raw_content: str
    structured_value_json: Optional[str]
    source: str
    language: str
    status: str
    version: int
    supersedes_memory_id: Optional[str]
    content_checksum: str
    created_at: str
    updated_at: str


class CollectionCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=500)
    collection_type: str = Field(default="fact", max_length=100)
    scope: str = Field(default="household", max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    summary: Optional[str] = Field(default=None, max_length=8192)
    language: str = Field(default="en", max_length=10)
    source: str = Field(..., max_length=200)
    source_reference: Optional[str] = None
    expected_item_count: Optional[int] = None


class CollectionUpdate(BaseModel):
    subject: Optional[str] = Field(default=None, max_length=500)
    collection_type: Optional[str] = Field(default=None, max_length=100)
    scope: Optional[str] = Field(default=None, max_length=100)
    title: Optional[str] = Field(default=None, max_length=500)
    summary: Optional[str] = Field(default=None, max_length=8192)
    source: Optional[str] = Field(default=None, max_length=200)
    source_reference: Optional[str] = None
    expected_item_count: Optional[int] = None


class CollectionResponse(BaseModel):
    collection_id: str
    subject: str
    collection_type: str
    scope: str
    title: str
    summary: Optional[str]
    language: str
    source: str
    source_reference: Optional[str]
    status: str
    version: int
    supersedes_collection_id: Optional[str]
    expected_item_count: Optional[int]
    content_checksum: str
    created_at: str
    updated_at: str


class MemoryQuery(BaseModel):
    subject: Optional[str] = None
    memory_type: Optional[str] = None
    scope: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    durable_user_tag: Optional[str] = None
    collection_id: Optional[str] = None
    created_after: Optional[str] = None
    created_before: Optional[str] = None
    updated_after: Optional[str] = None
    updated_before: Optional[str] = None
    limit: int = 20
    offset: int = 0