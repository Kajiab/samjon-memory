"""Resolver V1 constants and limits."""

# Resolver database
RESOLVER_SCHEMA_VERSION = "1.1.0"
RESOLVER_DB_FILENAME = "samjon_resolver.sqlite"

# Projected document entity types
ENTITY_STANDALONE_MEMORY = "standalone_memory"
ENTITY_COLLECTION_MEMORY = "collection_memory"
ENTITY_COLLECTION = "collection"
DOCUMENT_ENTITY_TYPES = {
    ENTITY_STANDALONE_MEMORY,
    ENTITY_COLLECTION_MEMORY,
    ENTITY_COLLECTION,
}

# Projection audit history bound (rows kept in each rebuilt Resolver DB)
PROJECTION_AUDIT_HISTORY_LIMIT = 50

# Projection audit build types
BUILD_TYPE_FULL = "full"
BUILD_TYPE_SELECTIVE = "selective"
BUILD_TYPES = {BUILD_TYPE_FULL, BUILD_TYPE_SELECTIVE}

# Projection audit statuses
PROJECTION_AUDIT_OK = "ok"
PROJECTION_AUDIT_FAILED = "failed"
PROJECTION_AUDIT_ROLLING_BACK = "rolling_back"
PROJECTION_AUDIT_ROLLED_BACK = "rolled_back"
PROJECTION_AUDIT_STATUSES = {
    PROJECTION_AUDIT_OK,
    PROJECTION_AUDIT_FAILED,
    PROJECTION_AUDIT_ROLLING_BACK,
    PROJECTION_AUDIT_ROLLED_BACK,
}

# Projection status entity types
PROJECTION_ENTITY_MEMORY = "memory"
PROJECTION_ENTITY_COLLECTION = "collection"
PROJECTION_ENTITY_TYPES = {PROJECTION_ENTITY_MEMORY, PROJECTION_ENTITY_COLLECTION}

# Resolver SQLite pragmas (separate from Core)
RESOLVER_SQLITE_PRAGMAS = [
    "PRAGMA foreign_keys = ON",
    "PRAGMA journal_mode = WAL",
    "PRAGMA busy_timeout = 5000",
    "PRAGMA synchronous = NORMAL",
]
