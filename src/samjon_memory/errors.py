"""Stable public error classes."""
class SamjonMemoryError(Exception):
    def __init__(self, code, message, status_code=400, details=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

class ValidationError(SamjonMemoryError):
    def __init__(self, message="VALIDATION_ERROR", details=None):
        super().__init__("VALIDATION_ERROR", message, 422, details)

class AuthenticationRequired(SamjonMemoryError):
    def __init__(self, message="AUTHENTICATION_REQUIRED"):
        super().__init__("AUTHENTICATION_REQUIRED", message, 401)

class PermissionDenied(SamjonMemoryError):
    def __init__(self, message="PERMISSION_DENIED"):
        super().__init__("PERMISSION_DENIED", message, 403)

class SensitiveDataRejected(SamjonMemoryError):
    def __init__(self, message="SENSITIVE_DATA_REJECTED"):
        super().__init__("SENSITIVE_DATA_REJECTED", message, 400)

class NotFound(SamjonMemoryError):
    def __init__(self, message="NOT_FOUND", details=None):
        super().__init__("NOT_FOUND", message, 404, details)

class Conflict(SamjonMemoryError):
    def __init__(self, message="CONFLICT", details=None):
        super().__init__("CONFLICT", message, 409, details)

class VersionConflict(SamjonMemoryError):
    def __init__(self, message="VERSION_CONFLICT", details=None):
        super().__init__("VERSION_CONFLICT", message, 409, details)

class IdempotencyConflict(SamjonMemoryError):
    def __init__(self, message="IDEMPOTENCY_CONFLICT"):
        super().__init__("IDEMPOTENCY_CONFLICT", message, 409)

class CoreDatabaseUnavailable(SamjonMemoryError):
    def __init__(self, message="CORE_DATABASE_UNAVAILABLE"):
        super().__init__("CORE_DATABASE_UNAVAILABLE", message, 503)

class ResolverDatabaseUnavailable(SamjonMemoryError):
    def __init__(self, message="RESOLVER_DATABASE_UNAVAILABLE"):
        super().__init__("RESOLVER_DATABASE_UNAVAILABLE", message, 503)

class MigrationRequired(SamjonMemoryError):
    def __init__(self, message="MIGRATION_REQUIRED"):
        super().__init__("MIGRATION_REQUIRED", message, 503)

class InternalError(SamjonMemoryError):
    def __init__(self, message="INTERNAL_ERROR"):
        super().__init__("INTERNAL_ERROR", message, 500)
