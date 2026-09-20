"""Deterministic Resolver search, ranking, and result assembly (Foundation C1).

Search is pure and deterministic over the projection and FTS5 index: no
randomness, no AI, no recency boost, no embeddings. Freshness is computed
from the current Core version/checksum, never from a stored label.
"""

from samjon_memory.errors import ProjectionStale, ValidationError
from samjon_memory.resolver.constants import (
    AMBIGUOUS_EPSILON,
    BOOST_ALIAS,
    BOOST_EXACT_SUBJECT,
    BOOST_SUBJECT_TERM,
    BOOST_TAG,
    BOOST_TITLE,
    BOOST_VOCAB,
    DEFAULT_QUERY_LIMIT,
    MAX_QUERY_LIMIT,
    RESULT_AMBIGUOUS,
    RESULT_COLLECTION,
    RESULT_COLLECTION_MEMORY,
    RESULT_COLLECTION_WITH_SELECTED,
    RESULT_NO_MATCH,
    RESULT_STANDALONE,
    TARGET_AUTO,
    TARGET_COLLECTION,
    TARGET_MEMORY,
    TARGETS,
)
from samjon_memory.resolver.freshness import compute as compute_freshness, kind_of
from samjon_memory.resolver.normalize import normalize_text
from samjon_memory.resolver.query import parse_query


def _bounded(value, minimum, maximum):
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return minimum


def _matched_keys(conn, matcher):
    rows = conn.execute(
        "SELECT entity_type, entity_id FROM resolver_document_fts "
        "WHERE resolver_document_fts MATCH ?",
        (matcher,),
    ).fetchall()
    return [(r["entity_type"], r["entity_id"]) for r in rows]


def _doc_by_key(conn, entity_type, entity_id):
    return conn.execute(
        "SELECT * FROM resolver_document_snapshot WHERE entity_type=? AND entity_id=?",
        (entity_type, entity_id),
    ).fetchone()


def _collections_by_id(conn):
    result = {}
    for r in conn.execute(
        "SELECT * FROM resolver_document_snapshot WHERE entity_type='collection'"
    ).fetchall():
        result[r["entity_id"]] = dict(r)
    return result


def _load_expansions(conn):
    aliases = {}
    for r in conn.execute("SELECT subject, alias_term FROM resolver_alias_map").fetchall():
        term = normalize_text(r["alias_term"])
        if term:
            aliases.setdefault(r["subject"], set()).add(term)
    vocab = set()
    for r in conn.execute("SELECT term FROM resolver_vocab_map").fetchall():
        term = normalize_text(r["term"])
        if term:
            vocab.add(term)
    tags = {}
    for r in conn.execute("SELECT subject, tag FROM resolver_tag_map").fetchall():
        tag = normalize_text(r["tag"])
        if tag:
            tags.setdefault(r["subject"], set()).add(tag)
    return {"aliases": aliases, "vocab": vocab, "tags": tags}


def _score_doc(doc, tokens, expansions):
    reasons = []
    text_terms = set((doc.get("normalized_text") or "").split())
    token_set = set(tokens)
    matched = [t for t in tokens if t in text_terms]
    if not matched:
        return 0.0, ["no_text_match"]
    score = float(len(matched))
    reasons.append("token_match")

    query_norm = " ".join(tokens)
    subject_norm = normalize_text(doc.get("subject"))
    if subject_norm and subject_norm == query_norm:
        score += BOOST_EXACT_SUBJECT
        reasons.append("exact_subject_match")
    if set(subject_norm.split()) & token_set:
        score += BOOST_SUBJECT_TERM
        reasons.append("subject_match")
    if set(normalize_text(doc.get("title")).split()) & token_set:
        score += BOOST_TITLE
        reasons.append("title_match")
    if set(normalize_text(doc.get("section_path")).split()) & token_set:
        score += BOOST_TITLE * 0.5
        reasons.append("section_path_match")
    for alias in expansions["aliases"].get(doc.get("subject"), set()):
        if alias in token_set:
            score += BOOST_ALIAS
            reasons.append("alias_match")
    if expansions["vocab"] & token_set:
        score += BOOST_VOCAB
        reasons.append("vocabulary_match")
    for tag in expansions["tags"].get(doc.get("subject"), set()):
        if tag in token_set:
            score += BOOST_TAG
            reasons.append("tag_match")
    return score, reasons

def _entry_from_doc(doc, score, reasons):
    entity_type = doc["entity_type"]
    if entity_type in (RESULT_STANDALONE, RESULT_COLLECTION_MEMORY):
        identity = {"memory_id": doc["entity_id"], "collection_id": doc.get("collection_id")}
        memory_id = doc["entity_id"]
        collection_id = doc.get("collection_id")
    else:
        identity = {"collection_id": doc["entity_id"]}
        memory_id = None
        collection_id = doc["entity_id"]
    return {
        "result_type": entity_type,
        "identity": identity,
        "core_version": doc.get("core_version"),
        "projected_core_version": doc.get("core_version"),
        "score": round(score, 6),
        "match_reasons": reasons,
        "conflicts": [],
        "subject": doc.get("subject"),
        "memory_id": memory_id,
        "collection_id": collection_id,
        "sequence_number": doc.get("sequence_number"),
    }


def _section_entry(doc, score, reasons):
    return {
        "memory_id": doc["entity_id"],
        "section_path": doc.get("section_path"),
        "sequence_number": doc.get("sequence_number"),
        "score": round(score, 6),
        "match_reasons": reasons,
    }


def _agg_reasons(collection_reasons, sections):
    out = []
    seen = set()
    for rsn in collection_reasons:
        if rsn not in seen:
            seen.add(rsn)
            out.append(rsn)
    for (_sc, rs, _d) in sections:
        for rsn in rs:
            if rsn not in seen:
                seen.add(rsn)
                out.append(rsn)
    return out[:6]


def _sort_key(entry):
    return (
        -entry["score"],
        entry["result_type"],
        entry.get("collection_id") or "",
        entry.get("memory_id") or "",
        entry.get("sequence_number") if entry.get("sequence_number") is not None else -1,
    )


def _assemble(scored, target, conn):
    collection_docs = _collections_by_id(conn)
    entries = []
    sections_by_coll = {}
    collection_scores = {}
    collection_reasons = {}
    doc_matched_colls = set()

    for (score, reasons, doc) in scored:
        et = doc["entity_type"]
        if et == RESULT_STANDALONE:
            if target in (TARGET_MEMORY, TARGET_AUTO):
                entries.append(_entry_from_doc(doc, score, reasons))
        elif et == RESULT_COLLECTION_MEMORY:
            sections_by_coll.setdefault(doc.get("collection_id"), []).append(
                (score, reasons, doc))
            if target in (TARGET_MEMORY, TARGET_AUTO):
                entries.append(_entry_from_doc(doc, score, reasons))
        elif et == RESULT_COLLECTION:
            collection_scores[doc["entity_id"]] = max(
                score, collection_scores.get(doc["entity_id"], 0.0))
            collection_reasons[doc["entity_id"]] = reasons
            doc_matched_colls.add(doc["entity_id"])

    if target in (TARGET_COLLECTION, TARGET_AUTO):
        all_colls = doc_matched_colls | set(sections_by_coll.keys())
        for cid in sorted(all_colls):
            cdoc = collection_docs.get(cid)
            if cdoc is None:
                continue
            is_doc = cid in doc_matched_colls
            sections = sections_by_coll.get(cid, [])
            score = max([collection_scores.get(cid, 0.0)] + [s[0] for s in sections])
            selected = [
                _section_entry(d, sc, rs)
                for (sc, rs, d) in sorted(
                    sections,
                    key=lambda s: (
                        s[2].get("sequence_number") if s[2].get("sequence_number") is not None else -1,
                        s[2]["entity_id"],
                    ),
                )
            ]
            entries.append({
                "result_type": RESULT_COLLECTION if is_doc else RESULT_COLLECTION_WITH_SELECTED,
                "identity": {"collection_id": cid},
                "core_version": cdoc.get("core_version"),
                "projected_core_version": cdoc.get("core_version"),
                "score": round(score, 6),
                "match_reasons": _agg_reasons(collection_reasons.get(cid, []), sections),
                "conflicts": [],
                "selected_sections": selected,
                "subject": cdoc.get("subject"),
                "memory_id": None,
                "collection_id": cid,
                "sequence_number": None,
            })

    entries.sort(key=_sort_key)
    return entries
def _annotate_freshness(entries, freshness):
    for entry in entries:
        if entry["result_type"] in (RESULT_STANDALONE, RESULT_COLLECTION_MEMORY):
            key = ("memory", entry.get("memory_id"))
        else:
            key = ("collection", entry.get("collection_id"))
        entry["projection_freshness"] = freshness.get(key, "orphaned")
        for section in entry.get("selected_sections", []):
            section["projection_freshness"] = freshness.get(
                ("memory", section["memory_id"]), "orphaned")


def _overall(entries):
    if not entries:
        return "fresh"
    return "fresh" if all(e.get("projection_freshness") == "fresh" for e in entries) else "stale"


def _empty(query, target):
    return {
        "result_type": RESULT_NO_MATCH,
        "resolved_target": target,
        "query": query,
        "count": 0,
        "total": 0,
        "incomplete": False,
        "projection_freshness": None,
        "bounded": True,
        "offset": 0,
        "limit_used": 0,
        "results": [],
    }


def search(conn, core_service, query, target=TARGET_AUTO, collection_id=None,
           scope=None, limit=DEFAULT_QUERY_LIMIT, offset=0, allow_stale=False,
           epsilon=AMBIGUOUS_EPSILON):
    """Deterministic search over the Resolver projection.

    Raises the modelled PROJECTION_STALE error when the match set is stale and
    ``allow_stale`` is false.
    """
    if target not in TARGETS:
        raise ValidationError("invalid target")
    limit = _bounded(limit, 1, MAX_QUERY_LIMIT)
    offset = max(0, _bounded(offset, 0, 2 ** 31 - 1))
    matcher, tokens, _reason = parse_query(query)
    if matcher is None:
        return _empty(query, target)
    keys = _matched_keys(conn, matcher)
    if not keys:
        return _empty(query, target)
    docs = []
    for (et, eid) in keys:
        row = _doc_by_key(conn, et, eid)
        if row is not None:
            docs.append(dict(row))
    expansions = _load_expansions(conn)
    scored = []
    for doc in docs:
        if scope and (doc.get("scope") or "") != scope:
            continue
        if collection_id:
            cid = doc.get("collection_id")
            matches_coll = (
                cid == collection_id
                or (doc["entity_type"] == RESULT_COLLECTION and doc["entity_id"] == collection_id)
            )
            if not matches_coll:
                continue
        score, reasons = _score_doc(doc, tokens, expansions)
        if score > 0.0:
            scored.append((score, reasons, doc))
    if not scored:
        return _empty(query, target)
    entries = _assemble(scored, target, conn)
    if not entries:
        return _empty(query, target)
    freshness = compute_freshness(conn, core_service)
    _annotate_freshness(entries, freshness)
    any_not_fresh = any(e.get("projection_freshness") != "fresh" for e in entries)
    if any_not_fresh and not allow_stale:
        raise ProjectionStale()
    incomplete = bool(any_not_fresh)
    overall = _overall(entries)

    if len(entries) >= 2:
        top = entries[0]
        tied = [
            e for e in entries[1:]
            if (top["score"] - e["score"]) <= epsilon
            and e["result_type"] != top["result_type"]
        ]
        if tied:
            results = ([top] + tied)[:limit]
            return {
                "result_type": RESULT_AMBIGUOUS,
                "resolved_target": target,
                "query": query,
                "count": len(results),
                "total": len(results),
                "incomplete": incomplete,
                "projection_freshness": overall,
                "bounded": True,
                "offset": 0,
                "limit_used": len(results),
                "epsilon_applied": epsilon,
                "results": results,
            }

    total = len(entries)
    page = entries[offset:offset + limit]
    return {
        "result_type": page[0]["result_type"],
        "resolved_target": target,
        "query": query,
        "count": len(page),
        "total": total,
        "incomplete": incomplete,
        "projection_freshness": overall,
        "bounded": True,
        "offset": offset,
        "limit_used": len(page),
        "results": page,
    }