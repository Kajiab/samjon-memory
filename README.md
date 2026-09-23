# samjon-memory

Durable text and structured-memory backend with SQLite, aliases, tags, vocabulary.

## Core V1 Status

- Core schema version: 1.1.0
- Core uses `samjon_core.sqlite`
- Resolver is not started
- `samjon_resolver.sqlite` is not created
- FTS5 is planned for Resolver, not implemented in Core
- AI, embeddings, vector search, MCP, and Numchoke integration are not implemented
- Core Portal V1 is complete and verified
- Server-rendered Portal with HTTP Basic Authentication
- Exactly one configured Admin account from environment (HTTP Basic)
- Exact Origin validation for all mutations
- Lifecycle implemented: activate, forget, restore (-> draft), purge (irreversible, 30-day retention)
- Administration page, Dashboard metrics, audit summary + filters + pagination: implemented

## Running Tests

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\test-local.ps1
```

## Running Locally

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1
```
