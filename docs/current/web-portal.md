# Web Portal

**Document ID:** SAMJON-PORTAL-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Web Portal documentation for Samjon Memory Core V1.

## 2. Portal Features

### Read Access (HTTP Basic Auth)
- **Library homepage** (`/portal/`) with: Search Hero, Browse by Subject, Discover, Recently Updated
- **Status** page (`/portal/status`) — former Overview/Dashboard with metrics, quick actions, recent activity, Core counts, Resolver status
- Search (`/portal/search`) — same Library search experience; `?q=` bookmarks stay valid
- Subject-category pages (`/portal/library/subjects/{category}`) — active Collections then active standalone Memories, cover-first cards, pagination
- Library Reader for Memory and Collection (`/portal/library/...`)
- Memory list/search with pagination and filters
- Memory detail view
- Collection list/search with pagination
- Collection detail with assembled memory preview
- Validation status display
- Audit log view (summary, filters, pagination)
- Administration page (forgotten/purged, retention, audit, schema/db status)

Navigation (one unified navbar, `aria-current="page"`): **Library**, Memories, Collections, **Status** (user nav, visually primary) · **Administration**, Audit, Resolver Debug (admin nav, visually secondary with a separator). A drawn book-spine brand mark leads every page. Library is the default Portal page.

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
## 6. Library Presentation (bookstore-style)

The Library is a calm, personal, cover-first reading surface, visually distinct
from the Administration/Status operational surfaces.

### Visual system
- Warm-paper page background with deep-teal primary action and warm-brass
  accent (CSS design tokens in `portal.css`).
- Thai-glyph-friendly font stack and generous line height (Thai descenders and
  combining marks).
- Unified 3:4 book-cover geometry for Memory, Collection, Section, Discover,
  Recently Updated, and category cards. Covers use the authenticated Portal
  thumbnail route only; placeholder covers are decorative (drawn book glyph +
  `ยังไม่มีภาพปก`) and stay hidden from assistive tech.

### Pages
- **Search Hero** — `Search the knowledge library` heading, Thai hint, large
  input + button, above the fold, stacks cleanly on mobile.
- **Browse by Subject** — responsive shelf of the 12 subject categories, each a
  tile with English name, Thai hint, active Collection/Memory counts and a
  representative cover when available.
- **Discover** and **Recently Updated** — bounded cover-first card rows.
- **Search results** — grouped Thai labels, 1-2 balanced cards per row on
  desktop, one card on tablet, cover-above-content on mobile.
- **Subject category pages** — breadcrumb, title + hint, Collections then
  Memories, cover-first cards, pagination, clear empty state.
- **Memory Reader** — hero (cover left, metadata right; cover above on mobile),
  comfortable reading column, gallery with captions, collapsed technical
  details, small Admin edit only. Read-only and side-effect free.
- **Collection Reader** — e-book detail: 3:4 cover, title/summary/type/status/
  language/chapter count, compact primary actions (start reading and table of
  contents) and a small Admin edit only. An ordered table of contents with
  anchors and thumbnails, then numbered chapters with their own covers,
  ordered illustration galleries and captions, and a back-to-contents link.
  `sequence_number ASC`. Collections with more than 100 Sections render correctly.

### Responsive & accessibility
- Validated breakpoints: 1440 / 1024 / 768 / 560 / 390 px — no horizontal page
  overflow, no cover distortion, ≥44px touch targets, Thai line spacing.
- One `H1` per page, logical heading order, visible focus states, meaningful
  alt text, decorative placeholders hidden, `prefers-reduced-motion` respected,
  forms retain labels, `<details>` stays keyboard accessible.

### Presentation constraints
- Portal uses `CoreService` / `ResolverService` only; no SQLite, repository, or
  media-filesystem access.
- No inline base64, no filesystem paths, no credentials in rendered HTML.
- Technical metadata stays collapsed inside `<details>`.
- Library rendering and Reader routes create no audit records and change no
  versions.
