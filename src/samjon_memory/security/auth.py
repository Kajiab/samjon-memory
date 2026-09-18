"""Authentication and authorization for Samjon Memory Core."""

from fastapi import Header, HTTPException
from samjon_memory.config import config


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
