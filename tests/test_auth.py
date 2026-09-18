"""Authentication tests."""

import pytest
from samjon_memory.security.auth import get_current_token, get_admin_token, require_admin, require_read
from samjon_memory.errors import AuthenticationRequired, PermissionDenied
from fastapi import HTTPException


def test_read_token_valid():
    assert require_read(x_service_token="test-token") is True


def test_admin_token_valid():
    assert require_admin(x_admin_token="test-admin-token") is True


def test_missing_token_in_dev_mode():
    # In dev mode without auth configured, missing token returns default
    result = require_read(x_service_token=None)
    assert result is True