# Portal Security

**Document ID:** SAMJON-PS-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Portal security for Samjon Memory Core V1.

## 2. Security

- X-Service-Token header for read access
- X-Admin-Token header for write access
- CSRF protection via SameSite=Strict cookies (portal_csrf)
- Token validation before portal access
- Admin authorization for all mutations
- Read/admin permission separation

## 3. Protection Mechanisms

- CSRF token generated per request and stored in SameSite=Strict cookie
- All mutating endpoints require admin token
- No direct database access by portal handlers
- XSS-safe HTML rendering via escape_html
- Version conflict detection on edits
- Validation feedback on collection operations
