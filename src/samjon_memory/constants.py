"""Samjon Memory Core constants and limits."""

# Service
APP_TITLE = "Samjon Memory Core V1"
APP_VERSION = "1.0.0"
CORE_SCHEMA_VERSION = "1.2.0"

# Core database
CORE_DB_FILENAME = "samjon_core.sqlite"

# Content limits (typed, configurable)
MAX_RAW_CONTENT_CHARS = 16384
MAX_RAW_CONTENT_BYTES = 65536
MAX_COLLECTION_TITLE = 500
MAX_COLLECTION_SUMMARY = 8192
MAX_MEMORY_TITLE = 500
MAX_ALIAS = 200
MAX_TAG = 80
MAX_ALIASES_PER_MEMORY = 20
MAX_TAGS_PER_MEMORY = 30
MAX_QUERY_LIMIT = 100
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Collection statuses
COLLECTION_STATUS_DRAFT = "draft"
COLLECTION_STATUS_ACTIVE = "active"
COLLECTION_STATUS_SUPERSEDED = "superseded"
COLLECTION_STATUS_FORGOTTEN = "forgotten"
COLLECTION_STATUSES = {COLLECTION_STATUS_DRAFT, COLLECTION_STATUS_ACTIVE, COLLECTION_STATUS_SUPERSEDED, COLLECTION_STATUS_FORGOTTEN}

# Memory statuses
MEMORY_STATUS_DRAFT = "draft"
MEMORY_STATUS_ACTIVE = "active"
MEMORY_STATUS_SUPERSEDED = "superseded"
MEMORY_STATUS_FORGOTTEN = "forgotten"
MEMORY_STATUSES = {MEMORY_STATUS_DRAFT, MEMORY_STATUS_ACTIVE, MEMORY_STATUS_SUPERSEDED, MEMORY_STATUS_FORGOTTEN}

# Durable metadata statuses
DURABLE_STATUS_ACTIVE = "active"
DURABLE_STATUS_SUPERSEDED = "superseded"
DURABLE_STATUS_FORGOTTEN = "forgotten"
DURABLE_STATUSES = {DURABLE_STATUS_ACTIVE, DURABLE_STATUS_SUPERSEDED, DURABLE_STATUS_FORGOTTEN}

# Audit actions
AUDIT_MEMORY_CREATE = "memory_create"
AUDIT_MEMORY_UPDATE = "memory_update"
AUDIT_MEMORY_SUPERSEDE = "memory_supersede"
AUDIT_MEMORY_FORGET = "memory_forget"
AUDIT_COLLECTION_CREATE = "collection_create"
AUDIT_COLLECTION_UPDATE = "collection_update"
AUDIT_COLLECTION_ACTIVATE = "collection_activate"
AUDIT_COLLECTION_STRUCTURE_CHANGE = "collection_structure_change"
AUDIT_COLLECTION_REOPENED = "collection_reopened"
AUDIT_MEMORY_RESTORE = "memory_restore"
AUDIT_COLLECTION_RESTORE = "collection_restore"
AUDIT_MEMORY_PURGE = "memory_purge"
AUDIT_COLLECTION_PURGE = "collection_purge"
AUDIT_COLLECTION_FORGET = "collection_forget"
AUDIT_DURABLE_ALIAS_CHANGE = "durable_alias_change"
AUDIT_DURABLE_VOCABULARY_CHANGE = "durable_vocabulary_change"
AUDIT_DURABLE_TAG_CHANGE = "durable_tag_change"
AUDIT_PORTAL_OPERATION = "portal_operation"

# Idempotency
IDEMPOTENCY_DEFAULT_TTL_HOURS = 24

# Auth
DEFAULT_ADMIN_TOKEN_PREFIX = "samjon-admin-"
DEFAULT_READ_TOKEN_PREFIX = "samjon-read-"

# Portal
PORTAL_ROUTE = "/portal/"

# Lifecycle / purge
PURGE_CONFIRMATION = "PURGE"
LIFECYCLE_PURGE_MIN_AGE_DAYS = 30
LIFECYCLE_AUTOMATIC_PURGE_ENABLED = False

# Schema metadata
SCHEMA_METADATA_KEY = "core_schema_version"

# Media (images)
MEDIA_ENTITY_TYPES = {"memory", "collection"}
MEDIA_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MEDIA_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MEDIA_LIFECYCLE_ACTIVE = "active"
MEDIA_LIFECYCLE_HIDDEN = "hidden"
MEDIA_LIFECYCLE_PURGED = "purged"
MEDIA_LIFECYCLE_STATUSES = {
    MEDIA_LIFECYCLE_ACTIVE,
    MEDIA_LIFECYCLE_HIDDEN,
    MEDIA_LIFECYCLE_PURGED,
}
# Pillow format id -> canonical mime
MEDIA_FORMAT_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}

# Audit actions
AUDIT_MEDIA_UPLOAD = "media_upload"
AUDIT_MEDIA_UPDATE = "media_update"
AUDIT_MEDIA_REPLACE = "media_replace"
AUDIT_MEDIA_SET_COVER = "media_set_cover"
AUDIT_MEDIA_REORDER = "media_reorder"
AUDIT_MEDIA_REMOVE = "media_remove"
AUDIT_MEDIA_PURGE = "media_purge"

# SQLite pragmas
SQLITE_PRAGMAS = [
    "PRAGMA foreign_keys = ON",
    "PRAGMA journal_mode = WAL",
    "PRAGMA busy_timeout = 5000",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA cache_size = -64000",
]