# Data Ownership

**Document ID:** SAMJON-DATA-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Data ownership and privacy for Samjon Memory Core V1.

## 2. Ownership

- Samjon Memory owns durable household knowledge.
- Core does not share data with other projects.
- Core does not call OpenRouter.

## 3. Privacy

- Sensitive data is rejected.
- Audit records redact credentials and never store full content, request bodies, passwords, or tokens.
- Audit is append-only (no automatic deletion).
- Purge hard-erases content; only an identity tombstone (ID, final version, checksum, purge actor/time) and lifecycle audit are retained.
- No production data in fixtures.
