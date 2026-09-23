"""Synthetic Resolver acceptance dataset.

Deterministic synthetic facts used by the Resolver Portal acceptance tests.
Everything here is test-only data; no production facts.
"""

from samjon_memory.core.service import CoreService
from samjon_memory.resolver.service import ResolverService


def seed_acceptance_core(path):
    """Seed a Core database with the Resolver acceptance dataset."""
    core = CoreService(database_path=path)

    plants = core.create_memory(
        {"subject": "plants", "title": "Basil", "raw_content": "basil grows fast in the sunny balcony",
         "source": "t", "memory_type": "fact", "scope": "household", "language": "en"})
    core.activate_memory(plants["memory_id"])

    thai = core.create_memory(
        {"subject": "สมุนไพร", "title": "สมุนไพรไทย", "raw_content": "โหระพา ใช้ทำอาหาร",
         "source": "t", "memory_type": "fact", "scope": "household", "language": "th"})
    core.activate_memory(thai["memory_id"])

    core.create_memory(  # draft, excluded
        {"subject": "notes", "raw_content": "draft alpha beta", "source": "t", "scope": "household"})

    recipes = core.create_collection(
        {"subject": "recipes", "collection_type": "fact", "scope": "household",
         "title": "Recipes", "summary": "family cooking", "language": "en", "source": "t"})
    section_content = {1: "soup recipe chicken", 2: "curry recipe warm", 3: "stew recipe slow"}
    section_ids = {}
    for seq, content in sorted(section_content.items()):
        m = core.create_memory({"subject": "recipes", "raw_content": content,
                                "source": "t", "scope": "household"})
        core.add_memory_to_collection(recipes["collection_id"], m["memory_id"], seq)
        core.activate_memory(m["memory_id"])
        section_ids[seq] = m["memory_id"]
    core.activate_collection(recipes["collection_id"])

    legacy_old = core.create_memory({"subject": "legacy", "raw_content": "superseded old value",
                                     "source": "t", "scope": "household"})
    core.activate_memory(legacy_old["memory_id"])
    legacy_new = core.create_memory({"subject": "legacy", "raw_content": "legacy new active",
                                     "source": "t", "scope": "household"})
    core.supersede_memory(legacy_old["memory_id"], legacy_new["memory_id"])
    core.activate_memory(legacy_new["memory_id"])

    obsolete = core.create_memory({"subject": "obsolete", "raw_content": "forgotten content",
                                   "source": "t", "scope": "household"})
    core.forget_memory(obsolete["memory_id"])

    secret = core.create_memory({"subject": "secret", "raw_content": "PURGED-SECRET-CONTENT",
                                 "source": "t", "scope": "household"})
    core.forget_memory(secret["memory_id"])
    core.conn.execute(
        "UPDATE memory SET purged_at=?, purged_by='admin' WHERE memory_id=?",
        ("2026-01-01T00:00:00.000000Z", secret["memory_id"]))
    core.conn.commit()

    dup_standalone = core.create_memory({"subject": "dup", "raw_content": "duplicate alpha",
                                         "source": "t", "scope": "household"})
    core.activate_memory(dup_standalone["memory_id"])
    dup_coll = core.create_collection({"subject": "dup", "title": "Dupe Catalog", "source": "t",
                            "scope": "household"})
    core.activate_collection(dup_coll["collection_id"])

    # durable metadata: multiple names + Thai vocabulary
    core.conn.execute(
        "INSERT INTO durable_alias (alias_id, subject, alias, language, source) VALUES (?,?,?,?,?)",
        ("alias-greens", "plants", "greens", "en", "t"))
    core.conn.execute(
        "INSERT INTO durable_alias (alias_id, subject, alias, language, source) VALUES (?,?,?,?,?)",
        ("alias-herbs", "plants", "herbs", "en", "t"))
    core.conn.execute(
        "INSERT INTO durable_vocabulary (vocabulary_id, term, definition, language, source) "
        "VALUES (?,?,?,?,?)", ("vocab-basil", "basil", "a fragrant herb", "en", "t"))
    core.conn.execute(
        "INSERT INTO durable_vocabulary (vocabulary_id, term, definition, language, source) "
        "VALUES (?,?,?,?,?)", ("vocab-thai", "โหระพา", "Thai basil", "th", "t"))
    core.conn.execute(
        "INSERT INTO durable_user_tag (tag_id, subject, tag, language, source) VALUES (?,?,?,?,?)",
        ("tag-garden", "plants", "garden", "en", "t"))
    core.conn.commit()
    return core


def seed_and_build_resolver(temp_db, temp_resolver_db):
    core = seed_acceptance_core(temp_db)
    rsvc = ResolverService(database_path=temp_resolver_db)
    rsvc.full_rebuild(core)
    return core, rsvc