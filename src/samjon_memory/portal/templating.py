"""Jinja2 template environment for the Core Portal.

Templates are resolved from ``Path(__file__).resolve().parent / "templates"`` so
they are always found regardless of the current working directory. HTML
autoescape is enabled by default. Templates never touch CoreService,
ResolverService, repositories, SQLite, the filesystem, or process environment --
every value they render is a presentation-ready view model supplied by the
router. No value is ever marked ``|safe``; user-controlled text is always
autoescaped plain text.
"""
from __future__ import annotations

from pathlib import Path

import jinja2

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
    keep_trailing_newline=True,
)

# Navigation links (presentation constant, mirrors the legacy navbar exactly).
_USER_LINKS = [
    ("library", "/portal/", "Library"),
    ("memories", "/portal/memories", "Memories"),
    ("collections", "/portal/collections", "Collections"),
    ("status", "/portal/status", "Status"),
]
_ADMIN_LINKS = [
    ("admin", "/portal/admin", "Administration"),
    ("audit", "/portal/audit", "Audit"),
    ("vocabulary", "/portal/vocabulary", "Vocabulary"),
    ("resolver", "/portal/resolver/", "Resolver Debug"),
]

_DEFAULT_TITLE = "Samjon Memory Portal"

# Controlled, self-contained error document when a template is missing at render
# time. Never exposes a stack trace or internal file path.
_NOT_FOUND_TEMPLATE = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>'
    '<meta name="viewport" content="width=device-width,initial-scale=1"/>'
    '<title>Portal unavailable</title></head><body>'
    '<main id="main"><h1>Portal temporarily unavailable</h1>'
    "<p>Please try again later.</p></main></body></html>"
)


def _navbar_vm(active: str = "") -> dict:
    def _links(entries):
        return [
            {
                "key": key,
                "href": href,
                "label": label,
                "active": key == active,
            }
            for key, href, label in entries
        ]

    return {
        "active": active,
        "user": _links(_USER_LINKS),
        "admin": _links(_ADMIN_LINKS),
    }


def render(template: str, *, active: str = "", **ctx) -> str:
    """Render ``template`` with ``ctx`` and a prebuilt navbar, autoescaped."""
    ctx.setdefault("navbar", _navbar_vm(active))
    ctx.setdefault("title", _DEFAULT_TITLE)
    try:
        return _env.get_template(template).render(**ctx)
    except jinja2.TemplateNotFound:
        # Controlled behavior: a safe, generic error body (no traceback/path).
        return _NOT_FOUND_TEMPLATE


def render_partial(template: str, **ctx) -> str:
    """Render a small component template (e.g. a card) in isolation."""
    try:
        return _env.get_template(template).render(**ctx)
    except jinja2.TemplateNotFound:
        return ""
    except jinja2.TemplateError:
        # A malformed component must fail loudly in tests rather than silently.
        raise


def validate_templates() -> list:
    """Return a list of (template_name, error) for any template that fails.

    Runs in CI/tests only. A clean environment returns []. This is the only
    eager template-loading path; normal requests use Jinja lazy loading.
    """
    problems = []
    for name in sorted(_env.list_templates()):
        try:
            _env.get_template(name)
        except jinja2.TemplateError as exc:
            problems.append((name, str(exc)))
    return problems