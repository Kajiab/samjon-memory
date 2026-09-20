"""Deterministic text normalization for the Resolver (Thai + English).

Normalization is intentionally deterministic and does not use AI, embeddings,
or vector search. It also enforces that sensitive manual-override content is
never indexed.
"""

import re
import unicodedata

_THAI_RANGE = "\u0e00-\u0e7f"
_NON_TOKEN_RE = re.compile(r"[^0-9a-z" + _THAI_RANGE + r"\s]")
_WS_RE = re.compile(r"\s+")

# Sensitive markers that must never be indexed (mirrors Core sensitive policy).
_SENSITIVE_MARKERS = [
    "password",
    "passwd",
    "token",
    "secret",
    "private key",
    "private_key",
    "recovery_key",
    "recovery key",
    "security_code",
    "security code",
    "api_key",
    "api key",
    "apikey",
    "credential",
    "biometric",
    "password_hash",
]


def normalize_text(value) -> str:
    """Return a normalized searchable token string (Thai + English)."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).lower()
    text = _NON_TOKEN_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def is_sensitive_text(value) -> bool:
    """Return True when a value looks sensitive (never index it)."""
    if not value:
        return False
    lowered = str(value).lower()
    return any(marker in lowered for marker in _SENSITIVE_MARKERS)


def safe_override_searchable(key, value_json) -> str:
    """Return a sanitized, approved searchable snippet for a manual override.

    Only the override field `key` is always kept. The raw payload is included
    only when it is non-sensitive and bounded; sensitive payloads are never
    persisted.
    """
    key_clean = normalize_text(key)
    if is_sensitive_text(key) or is_sensitive_text(value_json):
        return ""
    value_norm = normalize_text(value_json)[:120]
    if key_clean and value_norm:
        return f"{key_clean} {value_norm}".strip()
    return key_clean or value_norm