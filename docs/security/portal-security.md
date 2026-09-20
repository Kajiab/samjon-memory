# Portal Security

**Document ID:** SAMJON-PS-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Portal security for Samjon Memory Core V1.

## 2. Authentication Model

- Exactly one configured household administrator account
- Configuration: `SAMJON_PORTAL_USERNAME`, `SAMJON_PORTAL_PASSWORD`
- HTTP Basic Authentication for all Portal routes
- Missing/invalid credentials return 401 with `WWW-Authenticate: Basic`
- No users table, no registration, no custom login page
- No session cookies, no login nonce, no logout tracking
- No multiple Portal users or roles

## 3. Origin Validation

- All Portal mutations validate Origin against `SAMJON_PORTAL_ALLOWED_ORIGINS`
- Exact scheme+host+port matching
- Unapproved Origin returns 403

## 4. Credential Handling

- Credentials come from trusted configuration
- Never appear in HTML, JavaScript, URLs, logs, audit, or capabilities
- Synthetic values in tests

## 5. Portal Security Tests

- Missing credentials return 401
- WWW-Authenticate Basic present
- Invalid username rejected
- Invalid password rejected
- Valid credentials allow access
- All authenticated routes require credentials
- Unapproved Origin rejected on mutations
- Approved Origin succeeds on mutations
- Credentials absent from HTML and capabilities
- Cancel creates no mutation or audit event
