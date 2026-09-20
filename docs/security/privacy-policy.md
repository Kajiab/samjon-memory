# Privacy Policy

**Document ID:** SAMJON-SEC-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Privacy policy for Samjon Memory Core V1.

## 2. Rules

- Sensitive data is rejected at the API boundary.
- Audit records redact credentials and never store full content, request bodies, passwords, or tokens.
- Audit is append-only (no automatic deletion).
- Purge hard-erases content; only an identity tombstone (ID, final version, checksum, purge actor/time) and lifecycle audit are retained.
- No production data in fixtures.
- No external database access.
- No OpenRouter calls from Core.
