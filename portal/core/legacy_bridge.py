"""Bridge to the v1 panel modules that carry real business logic.

The v2 modules own routing, permission and shape; the heavy data/render logic
already lives in the ``cloudif_*_panel`` modules shipped next to the portal
release. Rather than duplicate it (and risk drift), the v2 handlers call these
panels through this single, lazily-imported bridge. If a panel is unavailable
the bridge raises, and the handler returns the v1's own unavailable envelope.

The panels dir is discovered at runtime; nothing here is hard-coded to a release.
"""
from __future__ import annotations

import importlib
import os
import sys

_PANELS_ENV = "CLOUDIF_PORTAL_PANELS_DIR"
_DEFAULT_DIRS = (
    "/srv/cloudif/app-pointers/portal-current",
    "/srv/cloudif/lib",
)


def _ensure_path() -> None:
    candidates = []
    env = os.environ.get(_PANELS_ENV)
    if env:
        candidates.append(env)
    candidates.extend(_DEFAULT_DIRS)
    for path in candidates:
        if path and os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)


def panel(name: str):
    """Import a cloudif_* panel module by name, e.g. 'cloudif_reconcile_panel'."""
    _ensure_path()
    return importlib.import_module(name)
