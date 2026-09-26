"""File-backed Portal vocabulary word bank (Portal-only, no Core changes).

The Portal keeps a small, curated word bank for the fields that appear in
Memory / Collection create and edit forms:

- ``subject``        -> Subject field of both Memories and Collections
- ``memory_type``    -> Type field of Memories (incl. Collection Sections)
- ``collection_type``-> Type field of Collections
- ``scope``          -> Scope field of both Memories and Collections

The store is a JSON file, never the Core or Resolver SQLite databases. Words
are advisory suggestions surfaced as native HTML ``<datalist>`` options; Core
never enforces them. Words are remembered automatically whenever a successful
Portal mutation uses a new subject/type/scope (``collect``), and can be
curated by the administrator on ``/portal/vocabulary``.

The default seed comes from the canonical subject/type/scope baseline
catalogs in ``docs/core/subject-type-guidelines.md``.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from pathlib import Path

# Canonical field keys used by the store.
VOCAB_LISTS = ("subject", "memory_type", "collection_type", "scope")

MAX_WORDS_PER_LIST = 200
MAX_WORD_LENGTH = 200

# Seed vocabulary from the baseline catalogs in
# docs/core/subject-type-guidelines.md (sections 8-9).
DEFAULT_VOCABULARY = {
    "subject": [
        "person", "household", "location", "device", "equipment", "plant",
        "pet", "music", "playlist", "routine", "activity", "inventory",
        "item", "supply", "service", "system", "integration", "automation",
        "topic", "policy", "project", "test",
    ],
    "memory_type": [
        "fact", "attribute", "relationship", "configuration", "preference",
        "habit", "instruction", "care_instruction", "operating_instruction",
        "maintenance_instruction", "procedure", "note", "device_note",
        "location_note", "maintenance_note", "observation", "warning",
        "restriction", "safety_note", "storage_location", "inventory_note",
        "schedule", "maintenance_schedule", "decision", "change_note",
        "known_issue", "test_note",
    ],
    "collection_type": [
        "guide", "care_guide", "operating_guide", "maintenance_guide",
        "troubleshooting_guide", "reference", "profile", "inventory",
        "checklist", "procedure", "policy", "configuration_guide",
        "preference_profile", "location_guide", "test_guide",
    ],
    "scope": ["personal", "household", "property", "system", "system_test"],
}

_WRITE_LOCK = threading.Lock()


def vocabulary_path() -> Path:
    """Path of the store file; override with SAMJON_PORTAL_VOCABULARY_PATH."""
    return Path(os.environ.get(
        "SAMJON_PORTAL_VOCABULARY_PATH", "./data/portal_vocabulary.json"))


def empty_vocabulary() -> dict:
    """Fresh vocabulary with the seeded baseline (used when no file exists)."""
    return {key: list(words) for key, words in DEFAULT_VOCABULARY.items()}


def _bounded_words(words) -> list:
    """Clean, de-duplicated, bounded list (defensive against manual edits)."""
    seen = set()
    out = []
    for w in words or []:
        w = (w or "").strip()
        if not w or len(w) > MAX_WORD_LENGTH:
            continue
        folded = w.lower()
        if folded in seen:
            continue
        seen.add(folded)
        out.append(w)
        if len(out) >= MAX_WORDS_PER_LIST:
            break
    return out


def load_vocabulary() -> dict:
    """Load stored words; fall back to the seeded baseline on any problem."""
    vocab = empty_vocabulary()
    raw = None
    try:
        with vocabulary_path().open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        raw = None
    if isinstance(raw, dict):
        for key in VOCAB_LISTS:
            if isinstance(raw.get(key), list):
                vocab[key] = _bounded_words(raw[key])
    return vocab


def _write(vocab: dict) -> None:
    """Atomic JSON write (temp file + os.replace)."""
    path = vocabulary_path()
    payload = {key: list(vocab.get(key) or []) for key in VOCAB_LISTS}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".vocab-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_vocabulary(vocab: dict) -> None:
    """Persist ``vocab`` to the store file (used by tests/operations)."""
    with _WRITE_LOCK:
        _write(vocab)


def normalize_words(raw) -> list:
    """Split raw text into clean, unique words (commas and newlines split)."""
    words = []
    seen = set()
    for part in re.split(r"[,\n\r]+", str(raw or "")):
        part = part.strip()
        if not part or len(part) > MAX_WORD_LENGTH:
            continue
        folded = part.lower()
        if folded in seen:
            continue
        seen.add(folded)
        words.append(part)
    return words


def add_words(vocab: dict, list_name: str, words) -> int:
    """Add words to a list in place; returns the number of new words added.

    ``words`` may be a raw string (commas/newlines separate words) or an
    iterable of word strings.
    """
    if list_name not in VOCAB_LISTS:
        return 0
    if isinstance(words, (list, tuple)):
        candidates = normalize_words("\n".join(str(w) for w in words))
    else:
        candidates = normalize_words(words)
    existing = vocab.setdefault(list_name, [])
    seen = {w.lower() for w in existing}
    added = 0
    for w in candidates:
        if len(existing) >= MAX_WORDS_PER_LIST:
            break
        if w.lower() in seen:
            continue
        seen.add(w.lower())
        existing.append(w)
        added += 1
    return added


def remove_word(vocab: dict, list_name: str, word: str) -> bool:
    """Remove a word (case-insensitive) in place; True when removed."""
    if list_name not in VOCAB_LISTS:
        return False
    target = (word or "").strip().lower()
    if not target:
        return False
    words = vocab.get(list_name, [])
    for i, w in enumerate(words):
        if w.lower() == target:
            del words[i]
            return True
    return False


def collect(*, subject="", memory_type="", collection_type="", scope=""):
    """Remember words used by a successful Portal mutation (non-blocking).

    Only genuinely new words trigger a write, so unchanged values are cheap
    no-ops.
    """
    vocab = load_vocabulary()
    changed = 0
    changed += add_words(vocab, "subject", [subject] if subject else [])
    changed += add_words(vocab, "memory_type", [memory_type] if memory_type else [])
    changed += add_words(vocab, "collection_type", [collection_type] if collection_type else [])
    changed += add_words(vocab, "scope", [scope] if scope else [])
    if changed:
        _write(vocab)


def add_words_and_save(list_name: str, raw_words) -> int:
    """Load-modify-save for the admin page; returns the number added."""
    with _WRITE_LOCK:
        vocab = load_vocabulary()
        added = add_words(vocab, list_name, raw_words)
        if added:
            _write(vocab)
        return added


def remove_word_and_save(list_name: str, word: str) -> bool:
    """Load-modify-save for the admin page; True when a word was removed."""
    with _WRITE_LOCK:
        vocab = load_vocabulary()
        removed = remove_word(vocab, list_name, word)
        if removed:
            _write(vocab)
        return removed