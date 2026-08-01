"""Inline SVG registry; add icons only when a migrated module needs them."""
from __future__ import annotations

_USER_TIE = (
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" '
    'stroke="currentColor" stroke-width="1.8" aria-hidden="true">'
    '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-6 8-6s8 2 8 6"/>'
    '<path d="M11 12l1 3 1-3"/></svg>'
)

ICONS: dict[str, str] = {"user-tie": _USER_TIE}


def icon(name: str) -> str:
    return ICONS.get(name, "")
