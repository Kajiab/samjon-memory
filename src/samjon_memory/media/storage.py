"""Filesystem-safe media storage.

All paths stored in SQLite are **relative** and are always constructed by the
media manager (never taken from user input). This module resolves them against
the configured media root, rejecting absolute paths and any traversal that would
escape the root. Reads/writes/removals go through this module only.
"""

import os

from samjon_memory.errors import NotFound, ValidationError

_ORIGINALS_DIR = "originals"
_THUMBNAILS_DIR = "thumbnails"


class MediaStore:
    def __init__(self, root: str):
        self.root = os.path.abspath(os.path.realpath(root))
        os.makedirs(os.path.join(self.root, _ORIGINALS_DIR), exist_ok=True)
        os.makedirs(os.path.join(self.root, _THUMBNAILS_DIR), exist_ok=True)

    # -- path safety ---------------------------------------------------------

    def _resolve(self, relative_path: str) -> str:
        if not relative_path:
            raise ValidationError("Missing relative path")
        # Reject absolute paths and traversal attempts.
        if os.path.isabs(relative_path):
            raise ValidationError("Absolute paths are not allowed")
        parts = relative_path.replace("\\", "/").split("/")
        if any(part in ("", "..", ".") for part in parts):
            raise ValidationError("Invalid media path")
        full = os.path.abspath(os.path.realpath(os.path.join(self.root, *parts)))
        if not full.startswith(self.root + os.sep):
            raise ValidationError("Media path escapes the media root")
        return full

    def originals_subdir(self) -> str:
        return os.path.join(self.root, _ORIGINALS_DIR)

    def thumbnails_subdir(self) -> str:
        return os.path.join(self.root, _THUMBNAILS_DIR)

    def build_original_relative(self, media_id: str, ext: str) -> str:
        return f"{_ORIGINALS_DIR}/{media_id}.{ext}"

    def build_thumbnail_relative(self, media_id: str, ext: str) -> str:
        return f"{_THUMBNAILS_DIR}/{media_id}.{ext}"

    def original_abspath(self, relative_path: str) -> str:
        return self._resolve(relative_path)

    def thumbnail_abspath(self, relative_path: str) -> str:
        return self._resolve(relative_path)

    # -- read / write / delete -----------------------------------------------

    def read_original(self, relative_path: str) -> bytes:
        path = self.original_abspath(relative_path)
        try:
            with open(path, "rb") as fh:
                return fh.read()
        except FileNotFoundError:
            raise NotFound("Media original file missing")

    def read_thumbnail(self, relative_path: str) -> bytes:
        path = self.thumbnail_abspath(relative_path)
        try:
            with open(path, "rb") as fh:
                return fh.read()
        except FileNotFoundError:
            raise NotFound("Media thumbnail file missing")

    def write_original(self, relative_path: str, data: bytes) -> None:
        from samjon_memory.media.images import atomic_write_bytes
        path = self.original_abspath(relative_path)
        try:
            atomic_write_bytes(path, data)
        except Exception:
            self._remove_stale(path)
            raise ValidationError("Failed to write media original")

    def write_thumbnail(self, relative_path: str, data: bytes) -> None:
        from samjon_memory.media.images import atomic_write_bytes
        path = self.thumbnail_abspath(relative_path)
        try:
            atomic_write_bytes(path, data)
        except Exception:
            self._remove_stale(path)
            raise ValidationError("Failed to write media thumbnail")

    def remove_original(self, relative_path: str) -> None:
        self._remove(self._resolve(relative_path))

    def remove_thumbnail(self, relative_path: str) -> None:
        self._remove(self._resolve(relative_path))

    def _remove(self, path: str) -> None:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    def _remove_stale(self, path: str) -> None:
        for candidate in (path, f"{path}.tmp-{os.getpid()}"):
            try:
                if os.path.exists(candidate):
                    os.remove(candidate)
            except OSError:
                pass

    def file_exists(self, relative_path: str) -> bool:
        return os.path.exists(self._resolve(relative_path))

    def list_original_files(self):
        directory = os.path.join(self.root, _ORIGINALS_DIR)
        if not os.path.isdir(directory):
            return []
        return [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]

    def list_thumbnail_files(self):
        directory = os.path.join(self.root, _THUMBNAILS_DIR)
        if not os.path.isdir(directory):
            return []
        return [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]