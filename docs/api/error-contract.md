# Error Contract

**Document ID:** SAMJON-ERR-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Stable error contract for Samjon Memory Core V1.

## 2. Errors

| Code | Message | Status |
|---|---|---|
| VALIDATION_ERROR | Validation failed | 422 |
| AUTHENTICATION_REQUIRED | Auth required | 401 |
| PERMISSION_DENIED | Admin required | 403 |
| SENSITIVE_DATA_REJECTED | Sensitive data rejected | 400 |
| NOT_FOUND | Resource not found | 404 |
| CONFLICT | Resource conflict | 409 |
| VERSION_CONFLICT | Version mismatch | 409 |
| IDEMPOTENCY_CONFLICT | Same key different content | 409 |
| CORE_DATABASE_UNAVAILABLE | DB unavailable | 503 |
| MIGRATION_REQUIRED | Migration needed | 503 |
| INTERNAL_ERROR | Unexpected error | 500 |
