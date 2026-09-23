# Samjon Memory Media Foundation

**Document ID:** SAMJON-MEDIA-001
**Status:** CANONICAL (from executable evidence)
**Owner:** Samjon Memory Engineering

## 1. Purpose

Adds image support to Core Memory: cover images, illustrations for Memories,
Collections, and Collection Sections, search-result thumbnails, and a read-only
Library Reader cover/gallery. Binary files live outside SQLite; SQLite stores
metadata only.

## 2. Storage layout

```
data/media/
├── originals/     # original JPEG/PNG/WebP files
└── thumbnails/    # derived, normalized, aspect-preserving thumbnails
```

- Only **relative paths** are stored in SQLite, always server-generated.
- Absolute paths, `..` traversal, and user-supplied paths are rejected.
- Binary bytes, base64 images, and absolute filesystem paths are never stored in
  SQLite, HTML, logs, or audit records.

## 3. Schema and migration

One additive Core migration `1.2.0` adds the `media` table (metadata only) with
indexes on `(entity_type, entity_id)`, `(entity_type, entity_id, is_cover)`, and
`display_order`. Only one `is_cover=1` row may exist per entity (enforced in the
service). Existing Memory, Collection, Resolver, and lifecycle tables are
unchanged.

## 4. Configuration and limits

Typed `CoreConfig` fields (env overrides):

| Config | Env | Default |
|---|---|---|
| `media_root` | `SAMJON_MEDIA_ROOT` | `./data/media` |
| `media_max_upload_bytes` | `SAMJON_MEDIA_MAX_UPLOAD_BYTES` | `10485760` |
| `media_max_width` / `media_max_height` | `SAMJON_MEDIA_MAX_WIDTH/HEIGHT` | `8192` |
| `media_thumb_width` / `media_thumb_height` | `SAMJON_MEDIA_THUMB_WIDTH/HEIGHT` | `400` |
| `media_max_per_entity` | `SAMJON_MEDIA_MAX_PER_ENTITY` | `20` |
| `media_max_alt_text` / `media_max_caption` | `SAMJON_MEDIA_MAX_ALT_TEXT/CAPTION` | `500` / `2000` |

Supported formats: JPEG, PNG, WebP only. SVG and other formats are rejected.
Actual file content and MIME are validated with Pillow; the filename extension is
never trusted.

## 5. Upload security

- Server-generated random filenames (`med-<hex>`).
- Normalized extension derived from validated MIME.
- Path traversal prevention; atomic writes (temp file + `os.replace`).
- Image decoding/dimension validation; thumbnail generated before any DB commit.
- Partial files and metadata are removed (rolled back) on failure.
- Checksum (SHA-256) stored per media row.
- Thumbnails preserve aspect ratio, never enlarge, and normalize EXIF orientation.

## 6. CoreService media operations

- `upload_media`, `list_media`, `get_media`, `get_media_cover`, `set_media_cover`
- `update_media_metadata` (alt text + caption), `reorder_media`
- `replace_media`, `remove_media`, `read_media_original`, `read_media_thumbnail`
- `media_integrity_check`
- `media_create_backup`, `media_check_backup`, `media_restore_backup`

Portal and API handlers use CoreService only; they never touch media
repositories or the filesystem directly.

## 7. Portal routes

All require Portal HTTP Basic auth. Mutations additionally validate exact Origin.
Image-serving routes return the stored bytes with the correct MIME.

- `POST /portal/media/upload`
- `POST /portal/media/{id}/cover` (set cover)
- `POST /portal/media/{id}/metadata` (alt/caption)
- `POST /portal/media/{id}/move-left` / `move-right` (reorder)
- `POST /portal/media/{id}/replace`
- `POST /portal/media/{id}/remove`
- `GET /portal/media/{id}/original`, `GET /portal/media/{id}/thumb`

Admin Memory/Collection detail pages render an upload + gallery with controls
(set cover, edit alt/caption, move, replace, remove). Collection Admin detail
adds an expandable inline Section media manager per Section
(`จัดการรูปภาพของบท`) that reuses the same routes against the Section Memory
(`entity_type=memory`, `entity_id=<section memory_id>`); after a mutation the
service redirects back to the same Collection detail page and the Section
anchor. Mutations accept a validated internal `back` target restricted to
`/portal/memories/...` and `/portal/collections/...`; absolute, protocol-relative,
or traversal URLs are ignored (open-redirect safe). The Library Reader shows a
read-only cover + gallery per Chapter (each Section's own media, ordered by
`display_order`), with captions and accessible alt text. Search results show a
cover thumbnail, or a placeholder when no cover exists; a Section result first
uses its own Section cover and may fall back to the parent Collection cover
(marked `cover_thumb_source=collection_cover_fallback`) when it has none.

## 8. Lifecycle

- **Forget:** preserves media files and metadata, hides media from normal views.
- **Restore:** reuses the same media (no duplication).
- **Purge:** removes originals + thumbnails, erases alt text and captions,
  drops searchable media text from the Resolver, and keeps only safe tombstone
  evidence (`lifecycle_status='purged'`). Irreversible.
- **Supersede:** does not copy media automatically.

## 9. Backup and restore

`media_create_backup` copies originals + thumbnails and writes a
`media_manifest.json` with checksums. `media_check_backup` detects missing
files, orphaned files, checksum/size mismatches, invalid relative paths, and
invalid MIME content. `media_restore_backup` copies missing files back,
idempotently (never duplicates).

## 10. Resolver integration

The Resolver indexes only validated alt text and captions for active media; it
never indexes binary data or filesystem paths. Changing alt/caption text
changes the projected `normalized_text`, so a selective rebuild of the entity
picks up the change. Purged media text disappears from the projection.

## 11. Not in scope

No remote downloads, SVG, video/audio, face recognition, AI analysis, OCR,
embeddings, cloud storage, MCP integration, or major Library visual redesign.