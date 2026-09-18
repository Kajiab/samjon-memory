# Home Assistant Smoke Test

**Document ID:** SAMJON-HA-SM-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Home Assistant smoke test for Samjon Memory Core V1.

## 2. Steps

1. Start Samjon Memory Core service
2. Verify /health returns 200
3. Verify /api/v1/capabilities returns service info
4. Create a memory via POST /api/v1/core/memories
5. Get the memory via GET /api/v1/core/memories/{id}
6. Update the memory via PATCH /api/v1/core/memories/{id}
7. Verify collection CRUD via collection endpoints
8. Verify audit log has records
9. Verify portal /portal/ returns HTML

## 3. Expected Results

- All endpoints return 200
- Memory CRUD works
- Collection lifecycle works
- Audit records are created
- Portal returns HTML
