# Web Portal

**Document ID:** SAMJON-PORTAL-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Web Portal documentation for Samjon Memory Core V1.

## 2. Portal Features

### Read Access (HTTP Basic Auth)
- Memory list/search with pagination and filters
- Memory detail view
- Collection list/search with pagination
- Collection detail with assembled memory preview
- Validation status display
- Audit log view

### Admin Access (HTTP Basic Auth)
- Standalone memory create
- Standalone memory edit (with expected_version)
- Guarded supersede and forget
- Collection create (draft state)
- Collection metadata edit (with expected_version)
- Collection memory reorder
- Collection validation
- Explicit collection activation

## 3. Authentication

- HTTP Basic Authentication for all Portal routes
- Exactly one configured household administrator account
- Configuration: `SAMJON_PORTAL_USERNAME`, `SAMJON_PORTAL_PASSWORD`
- No users table, no registration, no custom login page
- No session cookies, no login nonce, no logout tracking
- No multiple Portal users or roles

## 4. Portal Architecture

- Uses CoreService application layer (not REST over HTTP)
- No direct SQLite/repository/SQL access
- XSS-safe rendering via html.escape
- Version conflict feedback on edit operations
- Validation and activation feedback
- Exact Origin validation for all mutations
- Cancel controls are navigation links with no side effects

## 5. Boundary Rules

- Portal handlers use CoreService only
- No direct database access
- No Resolver/FTS5/embeddings/MCP code
- Read/write permission separation via single admin account
- HTTP Basic credentials never appear in HTML, JavaScript, URLs, logs, audit, or capabilities
