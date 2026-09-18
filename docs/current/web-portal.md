# Web Portal

**Document ID:** SAMJON-PORTAL-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Web Portal documentation for Samjon Memory Core V1.

## 2. Portal Features

### Read Access (X-Service-Token)
- Memory list/search with pagination
- Memory detail view
- Collection list/search with pagination
- Collection detail with assembled memory preview
- Validation status display
- Audit log view

### Admin Access (X-Admin-Token)
- Standalone memory create
- Standalone memory edit (with expected_version)
- Guarded supersede and forget
- Collection create (draft state)
- Collection metadata edit (with expected_version)
- Collection memory reorder
- Collection validation
- Explicit collection activation

## 3. Authentication

- X-Service-Token header for read access
- X-Admin-Token header for write access
- CSRF protection via SameSite=Strict cookie (portal_csrf)
- Token validation before portal access

## 4. Portal Architecture

- Uses CoreService application layer (not REST over HTTP)
- No direct SQLite/repository/SQL access
- XSS-safe rendering via escape_html
- Version conflict feedback on edit operations
- Validation and activation feedback

## 5. Boundary Rules

- Portal handlers use CoreService only
- No direct database access
- No Resolver/FTS5/embeddings/MCP code
- Read/write permission separation enforced
