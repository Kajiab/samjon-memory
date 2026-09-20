# Memory Lifecycle

**Document ID:** SAMJON-MLC-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Memory lifecycle for Samjon Memory Core V1.

## 2. Lifecycle

1. Create: draft, status=draft
2. Update: version increment, optimistic concurrency
3. Activate: status=draft -> active, version increment, audit
4. Supersede: status=superseded, supersedes_memory_id set
5. Forget: status=forgotten (soft delete), forgotten_at set
6. Restore: status=forgotten -> draft, version increment, audit, forgotten_at cleared
7. Purge: status=forgotten >= 30 days, admin + "PURGE" confirmation, hard-erase content -> tombstone (irreversible)

## 3. Rules

- Update requires expected_version
- Activate requires status=draft; rejects superseded/forgotten (including purged)
- Supersede sets supersedes_memory_id
- Forget sets status=forgotten and forgotten_at; rejects purged
- Restore only for forgotten (not purged); returns to draft
- Purge only for forgotten, >= 30 days, admin actor, confirmation "PURGE"; erases content, keeps tombstone
- Purged entities cannot be restored, edited, activated, or reused
- A restored or purged Collection section increments the parent Collection version
- Collection sections inherit subject/scope from the Collection; title is the section name only (never a fallback subject)
- Moving an existing Memory into a Collection requires matching subject/scope, else rejected without changing Memory or Collection
- A Collection with existing sections cannot change its subject or scope
- Content checksum on create
