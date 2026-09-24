"""Startup validation for the containerized deployment.

Runs only in a production-like environment (Docker sets SAMJON_CORE_ENV=production)
at application startup. Ensures the data directories exist and are writable, so
the container fails clearly instead of looping silently when a host bind mount is
unwritable. Creation uses only trusted application configuration; this never
chowns arbitrary host paths.
"""
from __future__ import annotations

import os
from pathlib import Path


def ensure_data_writeable(database_path: str, media_root: str) -> bool:
    """Ensure the data root dirs exist and are writable; fail clearly otherwise.

    Checks and creates the parent of ``database_path`` (e.g. /app/data) and the
    ``media_root`` (e.g. /app/data/media). Returns True on success, raises
    ``RuntimeError`` with an operator-facing message when a directory is missing
    or not writable by the current (non-root) user.
    """
    targets = (
        ("Core database directory", Path(database_path).parent),
        ("media root", Path(media_root)),
    )
    for label, path in targets:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"Samjon cannot create the {label}: {path} ({exc})"
            ) from exc
        if not os.access(path, os.W_OK):
            raise RuntimeError(
                f"Samjon data directory is not writable ({label}): {path}. "
                "Ensure the bind-mounted data directory is writable by the "
                "container user (uid/gid 10001). On Linux set ownership with: "
                "sudo chown -R 10001:10001 <host-data-dir>"
            )
    return True