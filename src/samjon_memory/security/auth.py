"""Authentication and authorization for Samjon Memory Core."""

import hashlib
import hmac
import secrets
import time
from typing import Optional

from fastapi import Header, HTTPException
from samjon_memory.config import config

PORTAL_SESSION_COOKIE = "portal_session"
PORTAL_LOGIN_NONCE_COOKIE = "portal_login_nonce"
SESSION_TTL_SECONDS = 3600  # 1 hour
LOGIN_NONCE_TTL_SECONDS = 300  # 5 minutes

# In-memory login nonce store: nonce -> created_at
_login_nonces: dict[str, float] = {}


def _session_secret() -> str:
    """Dedicated Portal session-signing secret from SAMJON_PORTAL_SESSION_SECRET."""
    secret = config.portal_session_secret
    if not secret:
        raise RuntimeError("SAMJON_PORTAL_SESSION_SECRET is required when Portal authentication is enabled")
    return secret


def create_portal_session(role: str) -> str:
    """Create a signed stateless session cookie containing only bounded metadata."""
    issued_at = time.time()
    expires_at = issued_at + SESSION_TTL_SECONDS
    session_id = secrets.token_urlsafe(32)
    csrf_nonce = secrets.token_urlsafe(32)
    payload = f"{session_id}:{role}:{issued_at}:{expires_at}:{csrf_nonce}"
    signature = hmac.new(
        _session_secret().encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{signature}"


def verify_portal_session(cookie_value: str) -> Optional[dict]:
    """Verify a session cookie value and return session data, or None."""
    if not cookie_value or cookie_value.count(":") < 5:
        return None
    parts = cookie_value.rsplit(":", 1)
    if len(parts) != 2:
        return None
    payload, signature = parts
    expected = hmac.new(
        _session_secret().encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    tokens = payload.split(":")
    if len(tokens) != 5:
        return None
    session_id, role, issued_at_str, expires_at_str, csrf_nonce = tokens
    if role not in ("read", "admin"):
        return None
    try:
        issued_at = float(issued_at_str)
        expires_at = float(expires_at_str)
    except ValueError:
        return None
    if time.time() > expires_at:
        return None
    return {
        "session_id": session_id,
        "role": role,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "csrf_nonce": csrf_nonce,
    }


def invalidate_portal_session(cookie_value: str) -> None:
    """Placeholder for stateless session invalidation (cookie expires naturally)."""
    pass


def generate_login_nonce() -> str:
    """Generate a short-lived login nonce."""
    nonce = secrets.token_urlsafe(32)
    _login_nonces[nonce] = time.time()
    return nonce


def verify_login_nonce(nonce: str) -> bool:
    """Verify and consume a login nonce."""
    if not nonce or nonce not in _login_nonces:
        return False
    if time.time() - _login_nonces[nonce] > LOGIN_NONCE_TTL_SECONDS:
        del _login_nonces[nonce]
        return False
    del _login_nonces[nonce]
    return True


def get_current_token(x_service_token: str = Header(None)):
    if not config.has_auth:
        return x_service_token or "dev-token"
    if x_service_token != config.service_token:
        raise HTTPException(status_code=401, detail="AUTHENTICATION_REQUIRED")
    return x_service_token


def get_admin_token(x_admin_token: str = Header(None)):
    if not config.has_auth:
        return x_admin_token or "dev-admin-token"
    if x_admin_token != config.admin_token:
        raise HTTPException(status_code=403, detail="PERMISSION_DENIED")
    return x_admin_token


def require_admin(x_admin_token: str = Header(None)):
    get_admin_token(x_admin_token)
    return True


def require_read(x_service_token: str = Header(None)):
    get_current_token(x_service_token)
    return True
