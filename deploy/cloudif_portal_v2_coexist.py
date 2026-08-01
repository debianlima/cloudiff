"""Camada de coexistência v1/v2 para o cloudif-admin-portal.

Ativa SOMENTE quando o ambiente define CLOUDIF_PORTAL_V2=1 (escopo do processo
do portal, via drop-in de systemd). Sem essa variável, este módulo não faz nada
— o monólito segue intacto.

Estratégia: fazer patch de ThreadingHTTPServer.__init__ para embrulhar o do_GET
do handler do portal. Para cada requisição, se o caminho estiver na lista branca
READY (rotas já verificadas idênticas à v1) ou for um asset do v2, responde pela
v2; caso contrário, delega ao handler original (legado). Fail-open: qualquer erro
na preparação deixa o portal subir normalmente no legado.

O nginx reescreve /cloudiff/portal/?(.*) -> /$1, então o portal recebe a home
como "/" e os assets como "/assets/..."; por isso interceptamos ambos os prefixos.
"""
from __future__ import annotations

import os
import sys

_ENABLED = os.environ.get("CLOUDIF_PORTAL_V2") == "1"

# Rotas já verificadas idênticas à v1 e promovidas para a v2. (path_sem_prefixo, metodo)
# O nginx tira o prefixo /cloudiff/portal, então a home chega como "/".
READY = {
    ("/", "GET"),
    ("", "GET"),
}

_V2_DIR = "/srv/cloudif/lib/portal"
_DESIGN_DIR = _V2_DIR + "/design"


def _install():
    if not _ENABLED:
        return
    try:
        import http.server as _hs
        from portal import wiring as _wiring
        from portal.core.http import Request as _Req
        from portal.core.auth import Identity as _Ident
    except Exception:
        return  # fail-open: sem v2, segue o legado

    _registry = {"wired": False}

    def _wire():
        if not _registry["wired"]:
            _wiring.install()
            _registry["wired"] = True

    _ASSET_CT = {
        "tokens.css": "text/css", "base.css": "text/css", "components.css": "text/css",
    }

    def _identity_from_headers(handler):
        h = handler.headers
        user = h.get("X-authentik-username") or h.get("X-Authentik-Username") or ""
        groups_raw = h.get("X-authentik-groups") or h.get("X-Authentik-Groups") or ""
        groups = frozenset(g.strip() for g in groups_raw.replace("|", ",").split(",") if g.strip())
        email = h.get("X-authentik-email") or ""
        return _Ident(user, email, groups)

    def _try_asset(handler, path):
        name = path.rsplit("/", 1)[-1]
        if name not in _ASSET_CT:
            return False
        for base in (_DESIGN_DIR,):
            fp = os.path.join(base, name)
            if os.path.isfile(fp):
                try:
                    data = open(fp, "rb").read()
                except Exception:
                    return False
                handler.send_response(200)
                handler.send_header("Content-Type", _ASSET_CT[name])
                handler.send_header("Content-Length", str(len(data)))
                handler.end_headers()
                handler.wfile.write(data)
                return True
        return False

    def _norm(path):
        # remove querystring e o prefixo do portal, se presente
        q = path.find("?")
        tab = ""
        if q >= 0:
            qs = path[q + 1:]
            path = path[:q]
            for kv in qs.split("&"):
                if kv.startswith("tab="):
                    tab = kv[4:]
        if path.startswith("/cloudiff/portal"):
            path = path[len("/cloudiff/portal"):] or "/"
        return path, tab

    def _wrap(original_do_GET):
        def do_GET(handler):
            try:
                raw = handler.path
                path, tab = _norm(raw)
                # assets do v2 (em qualquer prefixo)
                if "/assets/" in raw or path.startswith("/assets/"):
                    if _try_asset(handler, raw):
                        return
                # home v2: só sem aba (ou aba=resumo), para não roubar outras telas
                if (path, "GET") in READY and tab in ("", "resumo"):
                    _wire()
                    ident = _identity_from_headers(handler)
                    from portal.app import handle as _handle
                    status, headers, body = _handle("GET", "/cloudiff/portal", ident, {}, b"")
                    handler.send_response(status)
                    for k, v in headers.items():
                        handler.send_header(k, v)
                    handler.send_header("Content-Length", str(len(body)))
                    handler.end_headers()
                    handler.wfile.write(body)
                    return
            except Exception:
                pass  # fail-open para o legado
            return original_do_GET(handler)
        return do_GET

    _orig_init = _hs.ThreadingHTTPServer.__init__

    def _patched_init(self, *a, **k):
        _orig_init(self, *a, **k)
        cls = self.RequestHandlerClass
        if getattr(cls, "_v2_wrapped", False):
            return
        if hasattr(cls, "do_GET"):
            cls.do_GET = _wrap(cls.do_GET)
            cls._v2_wrapped = True

    _hs.ThreadingHTTPServer.__init__ = _patched_init


_install()
