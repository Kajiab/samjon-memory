# Web Portal

**Document ID:** SAMJON-PORTAL-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Web Portal documentation for Samjon Memory Core V1.

## 2. Portal Features

### Read Access (HTTP Basic Auth)
- Dashboard (Overview) with metrics and quick actions
- Memory list/search with pagination and filters
- Memory detail view
- Collection list/search with pagination
- Collection detail with assembled memory preview
- Validation status display
- Audit log view (summary, filters, pagination)
- Administration page (forgotten/purged, retention, audit, schema/db status)

### Admin Access (HTTP Basic Auth)
- Standalone memory create
- Standalone memory edit (with expected_version)
- Standalone memory activate (draft -> active)
- Guarded supersede and forget
- Restore forgotten memory/collection (-> draft)
- Purge forgotten memory/collection (admin, 30-day retention, type PURGE)
- Collection create (draft state)
- Collection metadata edit (with expected_version)
- Collection memory reorder
- Collection validation
- Explicit collection activation
- Add Section to Collection (creates Memory ID automatically; the section inherits subject/scope from the Collection, and the form has no subject/scope fields)
- Move Up / Move Down for Collection sections

## 3. Authentication

- HTTP Basic Authentication for all Portal routes
- Exactly one configured household administrator account
- Configuration: `SAMJON_PORTAL_USERNAME`, `SAMJON_PORTAL_PASSWORD`, `SAMJON_PORTAL_ALLOWED_ORIGINS`
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
- Collection Memories are sorted by sequence_number ASC
- Collection subject/scope consistency: sections inherit Collection subject/scope, title is the section name, moving an existing Memory requires a matching subject/scope, and a Collection with sections cannot change its subject/scope

## 5. Boundary Rules

- Portal handlers use CoreService only
- No direct database access
- No Resolver/FTS5/embeddings/MCP code
- Read/write permission separation via single admin account
- HTTP Basic credentials never appear in HTML, JavaScript, URLs, logs, audit, or capabilities
