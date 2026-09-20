"""Projection freshness for the Samjon Memory Resolver.

Freshness is always computed by comparing the current active Core snapshot
(version and checksum) against the projected snapshot. A stored derived
freshness label is never trusted on its own.
"""

ENTITY_KIND = {
    "standalone_memory": "memory",
    "collection_memory": "memory",
    "collection": "collection",
}


def kind_of(entity_type: str) -> str:
    return ENTITY_KIND.get(entity_type, "memory")


def snapshot_current(core_service):
    """Return {('memory'|'collection', id): (version, checksum)} for active Core."""
    core = core_service.resolver_projection_snapshot()
    current = {}
    for m in core.get("memories", []):
        current[("memory", m["memory_id"])] = (m.get("version"), m.get("content_checksum"))
    for c in core.get("collections", []):
        current[("collection", c["collection_id"])] = (
            c.get("version"),
            c.get("content_checksum"),
        )
    return current


def projected_rows(conn):
    """Return projected (kind, entity_id, version, checksum) tuples."""
    rows = conn.execute(
        "SELECT entity_type, entity_id, core_version, core_checksum "
        "FROM resolver_document_snapshot"
    ).fetchall()
    return [
        (kind_of(r["entity_type"]), r["entity_id"], r["core_version"], r["core_checksum"])
        for r in rows
    ]


def classify(kind, entity_id, proj_version, proj_checksum, current) -> str:
    """Classify one projected entity as fresh / stale / orphaned."""
    cur = current.get((kind, entity_id))
    if cur is None:
        return "orphaned"
    if proj_version == cur[0] and proj_checksum == cur[1]:
        return "fresh"
    return "stale"


def compute(conn, core_service):
    """Return {identity -> freshness} for every projected and active entity."""
    current = snapshot_current(core_service)
    rows = projected_rows(conn)
    freshness = {
        (k, e): classify(k, e, v, c, current)
        for (k, e, v, c) in rows
    }
    projected_keys = {(k, e) for (k, e, _, _) in rows}
    for key in current:
        if key not in projected_keys:
            freshness[key] = "missing"
    return freshness