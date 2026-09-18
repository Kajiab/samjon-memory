"""Typed configuration for Samjon Memory Core."""
import os
from dataclasses import dataclass, field
from typing import Optional

@dataclass(frozen=True)
class CoreConfig:
    database_path: str = field(default_factory=lambda: os.environ.get("SAMJON_CORE_DATABASE_PATH", "/data/samjon_core.sqlite"))
    service_token: str = field(default_factory=lambda: os.environ.get("SAMJON_CORE_SERVICE_TOKEN", ""))
    admin_token: str = field(default_factory=lambda: os.environ.get("SAMJON_CORE_ADMIN_TOKEN", ""))
    read_token: str = field(default_factory=lambda: os.environ.get("SAMJON_CORE_READ_TOKEN", ""))
    host: str = field(default_factory=lambda: os.environ.get("SAMJON_CORE_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.environ.get("SAMJON_CORE_PORT", "8100")))
    idempotency_ttl_hours: int = field(default_factory=lambda: int(os.environ.get("SAMJON_CORE_IDEMPOTENCY_TTL_HOURS", "24")))
    portal_enabled: bool = field(default_factory=lambda: os.environ.get("SAMJON_CORE_PORTAL_ENABLED", "true").lower() in ("true", "1", "yes"))
    log_level: str = field(default_factory=lambda: os.environ.get("SAMJON_CORE_LOG_LEVEL", "INFO"))
    max_raw_content_chars: int = field(default_factory=lambda: int(os.environ.get("SAMJON_CORE_MAX_RAW_CONTENT_CHARS", "16384")))
    max_raw_content_bytes: int = field(default_factory=lambda: int(os.environ.get("SAMJON_CORE_MAX_RAW_CONTENT_BYTES", "65536")))
    max_query_limit: int = field(default_factory=lambda: int(os.environ.get("SAMJON_CORE_MAX_QUERY_LIMIT", "100")))
    cors_origins: list[str] = field(default_factory=lambda: os.environ.get("SAMJON_CORE_CORS_ORIGINS", "*").split(","))
    @property
    def has_auth(self): return bool(self.service_token and self.admin_token and self.read_token)
    @property
    def is_development(self): return os.environ.get("SAMJON_CORE_ENV", "development") == "development"

config = CoreConfig()
