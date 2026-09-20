# Samjon Memory Status

**Document ID:** SAMJON-MEMORY-STATUS-001
**Version:** 2.0.0
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering
**Last reviewed:** 2026-09-19

## Current Phase

- Project status: Portal V1 complete, Core V1 verified
- Current phase: Portal reconstruction complete
- Core database schema: V1 frozen
- Core REST API: V1 frozen
- CoreService: Implemented
- Core Portal: Reconstructed and verified
- Core Freeze overall: Portal V1 verified
- Resolver: Not started
- MCP readiness: Not ready

## Core Baseline

- Core schema and API are the existing baseline
- Core migrations, repositories, CoreService, and API contracts are NOT modified
- Portal is reconstructed with HTTP Basic auth and exact Origin validation

## Portal Implementation

The Core Portal has been reconstructed with:

- one server-rendered Portal
- FastAPI HTTP Basic Authentication
- exactly one configured administrator
- no users table
- no user registration
- no custom login page
- no Portal session cookie
- no login nonce
- no multiple Portal users or roles
- exact Origin validation for mutations
- no-side-effect Cancel behavior

Required configuration:

- `SAMJON_PORTAL_USERNAME`
- `SAMJON_PORTAL_PASSWORD`
- `SAMJON_PORTAL_ALLOWED_ORIGINS`

## Portal Status

- Server-rendered Portal: Implemented (18 routes)
- HTTP Basic authentication: Verified by tests
- Exact Origin validation: Verified by tests
- Memory Portal workflow: Verified by tests
- Collection Portal workflow: Verified by tests
- Cancel behavior: Verified by tests
- Portal security tests: All passing
- Capability reporting: Verified by tests

## Resolver

- Status: Not started
- Resolver database created: No
- FTS5: Not implemented
- Semantic search: Not implemented
- AI enrichment: Not implemented
- Embeddings: Not implemented
- MCP implementation: Not implemented

## Test Evidence

All tests pass with executable evidence:

- Command: `python -m pytest tests/ -v --tb=short`
- Passed: 70
- Failed: 0
- Skipped: 0
- Verified commit: 2026-09-19

### Portal Security Tests (11)
- test_missing_credentials_return_401
- test_www_authenticate_basic_present
- test_invalid_username_rejected
- test_invalid_password_rejected
- test_valid_credentials_allow_access
- test_authenticated_routes_require_credentials (4 routes)
- test_unapproved_origin_rejected_on_mutation
- test_approved_origin_succeeds_on_mutation
- test_credentials_absent_from_html
- test_credentials_absent_from_capabilities
- test_cancel_create_memory_no_mutation
- test_xss_safe_rendering

### Portal Functional Tests (27)
- test_memory_list_empty
- test_memory_list_shows_created
- test_memory_detail
- test_memory_detail_not_found
- test_memory_create_form
- test_memory_create_submission
- test_memory_edit_form
- test_memory_edit_submission
- test_memory_supersede
- test_memory_forget
- test_collection_list_empty
- test_collection_create_form
- test_collection_create_submission
- test_collection_detail
- test_collection_edit_form
- test_collection_edit_submission
- test_collection_add_memory
- test_collection_reorder
- test_collection_activate
- test_audit_log
- test_edit_version_conflict_shown
- test_cancel_create_memory_link
- test_independent_collection_memory_edit