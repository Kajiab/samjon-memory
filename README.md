# samjon-memory

Durable text and structured-memory backend with SQLite, aliases, tags, vocabulary.

## Core V1 Status

- Core uses `samjon_core.sqlite`
- Resolver is not started
- `samjon_resolver.sqlite` is not created
- FTS5 is planned for Resolver, not implemented in Core
- AI, embeddings, vector search, MCP, and Numchoke integration are not implemented

## Running Tests

```bash
python -m pytest tests/ -v
```
