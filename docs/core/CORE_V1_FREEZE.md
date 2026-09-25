# Core V1 Freeze Record

**Document ID:** SAMJON-CORE-V1-FREEZE-001
**Version:** 1.0.0
**Status:** FROZEN BASELINE (historical record; Core has since moved to schema 1.2.0)
**Owner:** Samjon Memory Engineering
**Approved by:** Jeab
**Freeze approval date:** 2026-09-18
**Verified commit SHA:** 9ca5d57
**Exact test command:** `.venv\Scripts\python -m pytest tests/ -v --tb=short`
**Test result:** 84 passed, 0 failed
**OpenAPI drift result:** PASS
**Backup and isolated restore result:** PASS
**Resolver status:** Not started

---

## Freeze Scope

- Core database schema
- Core migration version 1
- memory and collection identity model
- memory and collection lifecycle
- collection draft and activation behavior
- collection ordering by `collection_id` and `sequence_number`
- section-level memory editing
- optimistic concurrency behavior
- idempotency behavior
- durable manual metadata ownership
- Core API request and response contracts
- stable Core errors
- authentication and authorization behavior
- Core Portal administration boundary
- Core backup and restore contract

## Freeze Does Not Prohibit

- bug fixes
- security fixes
- test improvements
- documentation corrections
- backward-compatible optional additions with an approved minor version

## Incompatible Change Requirements

Any incompatible change to the frozen Core schema or API requires:

- explicit impact review
- new contract version
- migration
- regression tests
- documentation update
- owner approval
