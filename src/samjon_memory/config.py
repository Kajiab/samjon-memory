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
    portal_allowed_origins: list[str] = field(default_factory=lambda: os.environ.get("SAMJON_PORTAL_ALLOWED_ORIGINS", "http://localhost:8100,http://127.0.0.1:8100").split(","))
    log_level: str = field(default_factory=lambda: os.environ.get("SAMJON_CORE_LOG_LEVEL", "INFO"))
    max_raw_content_chars: int = field(default_factory=lambda: int(os.environ.get("SAMJON_CORE_MAX_RAW_CONTENT_CHARS", "16384")))
    max_raw_content_bytes: int = field(default_factory=lambda: int(os.environ.get("SAMJON_CORE_MAX_RAW_CONTENT_BYTES", "65536")))
    max_query_limit: int = field(default_factory=lambda: int(os.environ.get("SAMJON_CORE_MAX_QUERY_LIMIT", "100")))
    purge_min_age_days: int = field(default_factory=lambda: int(os.environ.get("SAMJON_LIFECYCLE_PURGE_MIN_AGE_DAYS", "30")))
    automatic_purge_enabled: bool = field(default_factory=lambda: os.environ.get("SAMJON_LIFECYCLE_AUTOMATIC_PURGE_ENABLED", "false").lower() in ("true", "1", "yes", "on"))
    purge_confirmation: str = field(default_factory=lambda: os.environ.get("SAMJON_LIFECYCLE_PURGE_CONFIRMATION", "PURGE"))
    cors_origins: list[str] = field(default_factory=lambda: os.environ.get("SAMJON_CORE_CORS_ORIGINS", "*").split(","))

    # Media (images) configuration - typed, no unsafe defaults.
    media_root: str = field(default_factory=lambda: os.environ.get("SAMJON_MEDIA_ROOT", "./data/media"))
    media_max_upload_bytes: int = field(default_factory=lambda: int(os.environ.get("SAMJON_MEDIA_MAX_UPLOAD_BYTES", "10485760")))
    media_max_width: int = field(default_factory=lambda: int(os.environ.get("SAMJON_MEDIA_MAX_WIDTH", "8192")))
    media_max_height: int = field(default_factory=lambda: int(os.environ.get("SAMJON_MEDIA_MAX_HEIGHT", "8192")))
    media_thumb_width: int = field(default_factory=lambda: int(os.environ.get("SAMJON_MEDIA_THUMB_WIDTH", "400")))
    media_thumb_height: int = field(default_factory=lambda: int(os.environ.get("SAMJON_MEDIA_THUMB_HEIGHT", "400")))
    media_max_per_entity: int = field(default_factory=lambda: int(os.environ.get("SAMJON_MEDIA_MAX_PER_ENTITY", "20")))
    media_max_alt_text: int = field(default_factory=lambda: int(os.environ.get("SAMJON_MEDIA_MAX_ALT_TEXT", "500")))
    media_max_caption: int = field(default_factory=lambda: int(os.environ.get("SAMJON_MEDIA_MAX_CAPTION", "2000")))

    @property
    def portal_username(self) -> str:
        return os.environ.get("SAMJON_PORTAL_USERNAME", "")

    @property
    def portal_password(self) -> str:
        return os.environ.get("SAMJON_PORTAL_PASSWORD", "")

    @property
    def has_auth(self): return bool(self.service_token and self.admin_token and self.read_token)

    @property
    def is_development(self): return os.environ.get("SAMJON_CORE_ENV", "development") == "development"

config = CoreConfig()
