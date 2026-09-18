"""Sensitive data rejection tests."""

import pytest
from samjon_memory.shared.helpers import sanitize_for_audit


def test_sanitize_redacts_token():
    result = sanitize_for_audit("my password is secret123")
    assert result == "[REDACTED]"


def test_sanitize_redacts_api_key():
    result = sanitize_for_audit("api_key = sk-12345")
    assert result == "[REDACTED]"


def test_sanitize_preserves_normal():
    result = sanitize_for_audit("normal content here")
    assert result == "normal content here"