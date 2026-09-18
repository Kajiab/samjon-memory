"""Shared utility helpers."""
import hashlib, uuid
from datetime import datetime, timezone

def generate_id(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:24]}"

def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def compute_checksum(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def sanitize_for_audit(value, max_len=500):
    if len(value) > max_len:
        value = value[:max_len] + "...(truncated)"
    lower = value.lower()
    if any(kw in lower for kw in ["password", "token", "secret", "key", "api_key"]):
        return "[REDACTED]"
    return value
