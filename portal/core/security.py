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
    """Validate browser form origin while preserving the hardened v1 contract.

    Missing Origin/Referer remains accepted for non-browser/internal clients;
    CSRF and authorization are enforced independently by dispatch.  Mobile
    Chrome can send ``Origin: null`` for a top-level form navigation, so that
    case is accepted only when Fetch Metadata confirms a same-site/origin
    browser context on the CloudIFF public host.
    """
    def header(name: str) -> str:
        return (headers.get(name) or headers.get(name.lower()) or "").strip()

    target = (host or "").split(",", 1)[0].split(":", 1)[0].strip().lower().rstrip(".")
    forwarded = header("X-Forwarded-Host").split(",", 1)[0].split(":", 1)[0].strip().lower().rstrip(".")
    public = os.environ.get("CLOUDIF_PUBLIC_HOST", "cloudiff.duckdns.org").split(":", 1)[0].strip().lower().rstrip(".")
    origin = header("Origin")
    referer = header("Referer")
    candidate = origin or referer
    if not candidate:
        return True

    fetch_site = header("Sec-Fetch-Site").lower()
    fetch_mode = header("Sec-Fetch-Mode").lower()
    request_host_ok = (
        target == public or target.endswith("." + public)
        or forwarded == public or forwarded.endswith("." + public)
    )
    if candidate.lower() == "null":
        return (
            request_host_ok
            and fetch_site in {"same-origin", "same-site"}
            and fetch_mode in {"navigate", "same-origin", "cors", "no-cors"}
        )

    try:
        from urllib.parse import urlparse
        parsed = urlparse(candidate)
        source = (parsed.hostname or "").strip().lower().rstrip(".")
        if not source or parsed.username or parsed.password:
            return False
        same_cloudif_site = source == public or source.endswith("." + public)
        if parsed.scheme.lower() == "https" and same_cloudif_site and parsed.port in (None, 443):
            return True
        exact_internal = {x for x in (target, forwarded, "127.0.0.1", "localhost") if x}
        return parsed.scheme.lower() == "http" and source in exact_internal
    except Exception:
        return False
