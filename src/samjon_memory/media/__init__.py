"""Media package for Samjon Memory Core.

Media files (JPEG/PNG/WebP) live outside SQLite under ``data/media/``. SQLite
stores metadata only. This package owns image decoding/validation, thumbnail
generation, filesystem-safe storage, the metadata repository, and the
orchestrating media manager.
"""