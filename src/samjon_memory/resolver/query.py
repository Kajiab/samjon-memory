"""Safe FTS5 query parsing for the Samjon Memory Resolver.

Raw user input is never passed directly into FTS MATCH syntax. The parser
extracts only normalized tokens (English letters/digits plus Thai characters)
and builds a safe quoted-term AND matcher, so quotes, parentheses, hyphens,
colons, asterisks, Thai punctuation, and FTS operators are all neutralized.
"""

from samjon_memory.errors import ValidationError
from samjon_memory.resolver.constants import MAX_QUERY_LENGTH, MAX_QUERY_TOKENS
from samjon_memory.resolver.normalize import normalize_text


def parse_query(raw_query) -> tuple:
    """Parse a user query into a safe FTS5 matcher.

    Returns ``(matcher, tokens, reason)`` where ``matcher`` is a safe FTS5
    MATCH expression built from double-quoted terms (or ``None`` for an empty
    query) and ``tokens`` is the normalized token list.

    Raises ValidationError for missing or oversized input.
    """
    if raw_query is None:
        raise ValidationError("query is required")
    text = str(raw_query)
    if len(text) > MAX_QUERY_LENGTH:
        raise ValidationError("query too long")
    stripped = text.strip()
    if not stripped:
        return None, [], "empty"
    normalized = normalize_text(stripped)
    tokens = normalized.split()
    if not tokens:
        return None, [], "empty_after_normalize"
    if len(tokens) > MAX_QUERY_TOKENS:
        tokens = tokens[:MAX_QUERY_TOKENS]
    matcher = " ".join(f'"{token}"' for token in tokens)
    return matcher, tokens, "ok"


def safe_match_expr(raw_query) -> str:
    """Return a safe FTS5 MATCH expression, or ``""`` when empty."""
    matcher, _, _ = parse_query(raw_query)
    return matcher or ""