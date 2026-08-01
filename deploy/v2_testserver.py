"""Servidor de teste isolado do Portal v2 (porta 18120).

Não toca a produção: sobe a app v2 num processo próprio para inspeção visual e
funcional. Seletor de perfil por querystring ?perfil=admin|professor|aluno, que
fabrica os headers do Authentik correspondentes. Índice honesto: marca cada rota
como "dados reais" ou "aguarda extração".

Túnel: ssh -L 18120:127.0.0.1:18120 cti@10.62.92.7 e abrir
http://localhost:18120/cloudiff/portal/
"""
from __future__ import annotations

import os
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, "/srv/cloudif/lib")

from portal import wiring
from portal.app import handle
from portal.core.auth import Identity

wiring.install()

_PERFIS = {
    "admin": ("akadmin", "akadmin@cloudiff", frozenset({"CloudIF-Tenants-Admin"})),
    "professor": ("iff1742962", "iff1742962@cloudiff",
                  frozenset({"CloudIF-Tenants", "CloudIF-Professor"})),
    "aluno": ("iff1860746", "iff1860746@cloudiff", frozenset({"CloudIF-Tenants"})),
}

_READY_REAIS = {
    "/cloudiff/portal": "dados reais (home)",
    "/cloudiff/portal/": "dados reais (home)",
    "/cloudiff/portal/pagina/projetos": "dados reais (visibilidade por perfil)",
    "/api/reconciliation": "dados reais",
}


def _identity(perfil):
    u, e, g = _PERFIS.get(perfil, _PERFIS["admin"])
    return Identity(u, e, g)


def _index(perfil):
    ident = _identity(perfil)
    linhas = []
    for path, nota in _READY_REAIS.items():
        linhas.append(
            f'<li><a href="{path}?perfil={perfil}">{path}</a> '
            f'<span style="color:#6b7371">— {nota}</span></li>')
    outros = ("perfil atual: <b>%s</b> (%s) · troque com "
              "?perfil=admin|professor|aluno") % (ident.username, perfil)
    return (
        "<!doctype html><meta charset=utf-8><title>Portal v2 — teste</title>"
        "<div style='font-family:system-ui;max-width:720px;margin:40px auto'>"
        "<h1>Portal v2 — servidor de teste</h1>"
        f"<p>{outros}</p><ul>" + "".join(linhas) + "</ul>"
        "<p style='color:#6b7371'>Isolado da produção. Somente rotas já "
        "portadas mostram dados reais.</p></div>"
    )


class H(BaseHTTPRequestHandler):
    def _perfil(self):
        q = self.path.find("?")
        if q >= 0:
            for kv in self.path[q + 1:].split("&"):
                if kv.startswith("perfil="):
                    return kv[7:]
        return "admin"

    def do_GET(self):
        perfil = self._perfil()
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index", "/cloudiff/portal/teste"):
            body = _index(perfil).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        ident = _identity(perfil)
        try:
            status, headers, body = handle("GET", path, ident, {}, b"")
        except Exception as e:
            body = ("erro: %r" % e).encode()
            status, headers = 500, {"Content-Type": "text/plain; charset=utf-8"}
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("V2_TEST_PORT", "18120"))
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
