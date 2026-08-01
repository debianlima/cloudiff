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
    """Deterministic per-user token; mirrors the v1 _prod_csrf_token contract.

    Usa o MESMO segredo da v1 (CLOUDIF_CSRF_SECRET). Sem default fraco: se o
    segredo faltar, levanta — exatamente como o monólito, para nunca emitir um
    token fraco em produção. Fora de produção (testes) usa um valor de teste
    apenas quando CLOUDIF_PORTAL_TESTING=1.
    """
    secret = os.environ.get(_SECRET_ENV)
    if not secret:
        if os.environ.get("CLOUDIF_PORTAL_TESTING") == "1":
            secret = "cloudif-portal-csrf-testing"
        else:
            raise RuntimeError("CLOUDIF_CSRF_SECRET ausente")
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
