# Architecture

**Document ID:** SAMJON-ARCH-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Runtime architecture for Samjon Memory Core V1.

## 2. Architecture

```text
Xiaozhi / Web Chat / API Client
                    |
                    v
            Samjon Memory Core
           (FastAPI + SQLite)
                    |
                    v
         SQLite (samjon_core.sqlite)
```

## 3. Components

- **Core service** - Business logic
- **Database layer** - SQLite with WAL
- **API layer** - REST endpoints
- **Portal** - HTML web UI
- **Security** - Token auth
- **Audit** - Audit log

## 4. Boundaries

- Core owns durable memory.
- Core does not call OpenRouter, select models, or implement skills.
- Core does not access external databases.
- Core exposes REST only.
