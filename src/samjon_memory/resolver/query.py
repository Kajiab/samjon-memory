"""Safe FTS5 query parsing for the Samjon Memory Resolver.

Raw user input is never passed directly into FTS MATCH syntax. The parser
extracts only normalized tokens (English letters/digits plus Thai characters),
then builds a safe matcher. Tokens of at least ``MIN_PREFIX_LENGTH`` characters
become a code-added prefix term ``"tok"*`` (which also matches the token itself,
so exact and prefix matches are both covered); shorter tokens are matched
exact-only. The FTS5 ``*`` wildcard is added only by this code after
validation, so quotes, parentheses, hyphens, colons, asterisks, Thai
punctuation, and FTS operators typed by the user are all neutralized and never
reach MATCH as raw syntax.
"""

from samjon_memory.errors import ValidationError
from samjon_memory.resolver.constants import (
    MAX_QUERY_LENGTH,
    MAX_QUERY_TOKENS,
    MIN_PREFIX_LENGTH,
)
from samjon_memory.resolver.normalize import normalize_text


def _token_matcher(token):
    """Build a safe FTS5 expression for a single normalized token.

    The token has already been normalized to only ``[0-9a-z<Thai>]`` characters,
    so it cannot smuggle FTS5 operators. For tokens of at least
    ``MIN_PREFIX_LENGTH`` we emit a prefix term ``"tok"*``; the FTS5 ``*``
    matches the token itself too (a token starts with itself), so the prefix term
    doubles as the exact-match term. The ``*`` is appended here in code, never
    taken from user input. Shorter tokens are matched exact-only.
    """
    wildcard = "*" if len(token) >= MIN_PREFIX_LENGTH else ""
    return f'"{token}"{wildcard}'


def parse_query(raw_query) -> tuple:
    """Parse a user query into a safe FTS5 matcher.

    Returns ``(matcher, tokens, reason)`` where ``matcher`` is a safe FTS5
    MATCH expression built from double-quoted terms plus code-added prefix
    terms (or ``None`` for an empty query) and ``tokens`` is the normalized
    token list.

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
    matcher = " ".join(_token_matcher(token) for token in tokens)
    return matcher, tokens, "ok"


def safe_match_expr(raw_query) -> str:
    """Return a safe FTS5 MATCH expression, or ``""`` when empty."""
    matcher, _, _ = parse_query(raw_query)
    return matcher or ""