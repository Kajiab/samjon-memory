"""Image decoding, validation, and thumbnail generation (JPEG/PNG/WebP).

Actual file content is validated with Pillow - the filename extension is never
trusted. SVG and other formats are rejected. Thumbnails preserve the source
orientation (EXIF transpose), keep the aspect ratio, and are never enlarged.
"""

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from samjon_memory.constants import MEDIA_FORMAT_MIME, MEDIA_MIME_TYPES
from samjon_memory.errors import ValidationError

_TAGS = {"svg", "image/svg+xml"}
_PIL_SAVE_FORMAT = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
_THUMB_QUALITY = 82


def inspect_image(data: bytes):
    """Validate actual image content and return ``(mime_type, width, height)``.

    Raises ValidationError for malformed, unsupported, or deceptive content.
    """
    if not data:
        raise ValidationError("Empty image payload")
    probe = _sniff_format(data)
    if probe in _TAGS:
        raise ValidationError("SVG images are not supported")
    try:
        img = Image.open(BytesIO(data))
        img.load()
        fmt = (img.format or "").upper()
        fmt = "SVG" if fmt == "SVG" else fmt
        mime = MEDIA_FORMAT_MIME.get(fmt)
        if mime not in MEDIA_MIME_TYPES:
            raise ValidationError(f"Unsupported image format: {fmt or 'unknown'}")
        if probe and probe != mime and not _compatible(probe, mime):
            raise ValidationError("Image content does not match declared type")
        width, height = img.size
        if width <= 0 or height <= 0:
            raise ValidationError("Image has invalid dimensions")
        return mime, width, height
    except UnidentifiedImageError:
        raise ValidationError("Malformed or unrecognized image content")
    except ValidationError:
        raise
    except Exception:
        raise ValidationError("Malformed image content")


def _compatible(sniff_mime, declared_mime):
    """Allow benign aliases (e.g. image/jpg vs image/jpeg)."""
    norm = {"image/jpg": "image/jpeg", "image/jpeg": "image/jpeg",
            "image/png": "image/png", "image/webp": "image/webp"}
    return norm.get(sniff_mime) == norm.get(declared_mime)


def _sniff_format(data: bytes) -> str:
    """Best-effort MIME sniff from magic bytes (used to reject deceptive files)."""
    if data[:5] == b"\x89PNG\r":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    # WebP begins 'RIFF' + size + 'WEBP'
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    # SVG is plain text
    head = data[:256].lstrip().lower()
    if head.startswith(b"<?xml") or head.startswith(b"<svg") or b"<svg" in head[:128]:
        return "image/svg+xml"
    return ""


def build_thumbnail(data: bytes, mime: str, thumb_width: int, thumb_height: int) -> bytes:
    """Return thumbnail bytes for ``data``.

    - Applies EXIF orientation transpose (``ImageOps.exif_transpose``).
    - ``Image.thumbnail`` preserves the aspect ratio and never enlarges.
    - Re-saves using the same format (JPEG/PNG/WebP).
    Raises ValidationError on decode failure so callers never commit a partial
    file.
    """
    try:
        img = Image.open(BytesIO(data))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGBA" if _has_alpha(img) else "RGB")
        img.thumbnail((int(thumb_width), int(thumb_height)), Image.LANCZOS)
        out = BytesIO()
        save_fmt = _PIL_SAVE_FORMAT.get(mime, "JPEG")
        kwargs = {"format": save_fmt}
        if save_fmt in ("JPEG", "WEBP"):
            kwargs["quality"] = _THUMB_QUALITY
        img.save(out, **kwargs)
        thumb = out.getvalue()
        if not thumb:
            raise ValidationError("Thumbnail generation produced no data")
        return thumb
    except ValidationError:
        raise
    except Exception:
        raise ValidationError("Failed to generate thumbnail")


def _has_alpha(img) -> bool:
    return img.mode in ("RGBA", "LA", "P") or (img.mode == "P" and "transparency" in img.info)


def atomic_write_bytes(path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically (temp file + os.replace)."""
    import os
    tmp = f"{path}.tmp-{os.getpid()}"
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def sha256_bytes(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()