# Memory Lifecycle

**Document ID:** SAMJON-MLC-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Memory lifecycle for Samjon Memory Core V1.

## 2. Lifecycle

1. Create: draft, status=draft
2. Update: version increment, optimistic concurrency
3. Supersede: status=superseded, supersedes_memory_id set
4. Forget: status=forgotten

## 3. Rules

- Update requires expected_version
- Supersede sets supersedes_memory_id
- Forget sets status=forgotten
- Content checksum on create
