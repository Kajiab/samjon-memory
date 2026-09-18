"""Content checksum utilities."""
import hashlib
def content_checksum(content): return hashlib.sha256(content.encode("utf-8")).hexdigest()
def verify_checksum(content, expected): return content_checksum(content) == expected
