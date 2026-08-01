"""Edge security primitives: CSRF and same-origin, reproduced from the v1.

The v1 derives a per-user CSRF token and rejects cross-origin form posts. These
functions centralize both so every ``/action/`` route in the v2 satisfies A3
(CSRF preserved) without copying the check into each module.
"""
from __future__ import annotations

import hashlib
import hmac
import os

from portal.core.auth import Identity

_SECRET_ENV = "CLOUDIF_CSRF_SECRET"


def csrf_token(identity: Identity) -> str:
    """Deterministic per-user token; mirrors the v1 _prod_csrf_token contract."""
    secret = os.environ.get(_SECRET_ENV, "cloudif-portal-csrf")
    msg = identity.username.strip().lower().encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def csrf_valid(identity: Identity, presented: str) -> bool:
    if not presented:
        return False
    return hmac.compare_digest(presented, csrf_token(identity))


def same_origin(headers: dict[str, str], host: str) -> bool:
    """Reject a form post whose Origin/Referer host differs from the request host.

    Reproduces v1 _cloudif_security_valid_origin: a missing Origin AND Referer is
    treated as same-origin (non-browser client); a present one must match host.
    """
    target = (host or "").split(":", 1)[0].strip().lower().rstrip(".")
    for name in ("Origin", "Referer"):
        raw = (headers.get(name) or headers.get(name.lower()) or "").strip()
        if not raw:
            continue
        rest = raw.split("://", 1)[-1]
        source = rest.split("/", 1)[0].split(":", 1)[0].strip().lower().rstrip(".")
        if source and target and source != target:
            return False
    return True
