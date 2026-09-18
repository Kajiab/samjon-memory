# Migration Policy

**Document ID:** SAMJON-MIG-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Schema migration policy for Samjon Memory Core V1.

## 2. Policy

- Schema version stored in schema_metadata
- Migrations run on startup via ensure_schema()
- Versioned migrations in migration.py
- No down migrations (only forward)
