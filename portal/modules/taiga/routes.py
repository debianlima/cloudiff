"""Taiga module routes — read-only, project-scoped and authenticated."""
from __future__ import annotations

import json

from portal.core.dispatch import Endpoint
from portal.core.http import Request, Response
from portal.core.rbac import authenticated, is_global
from portal.modules.taiga import service, views

MODULE = "taiga"


def _page(request: Request) -> Response:
    from portal.ui import shell
    from portal.wiring import all_endpoints
    data = service.taiga_data(request.identity, request.q("project"))
    from portal.core.security import csrf_token
    data["csrf"] = csrf_token(request.identity)
    body = views.taiga_body(data)
    nav = sorted({endpoint.module for endpoint in all_endpoints() if endpoint.method == "GET" and endpoint.guard(request.identity)})
    return Response.html(shell.render(request.identity, nav, MODULE, "Taiga", body))


def _api(request: Request) -> Response:
    data = service.taiga_data(request.identity, request.q("project"))
    return Response.json_body(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode())


def _grant_access(request: Request) -> Response:
    result=service.grant_taiga_access(request.identity,request.f("project"))
    if result.get("ok") and result.get("redirect"):
        return Response.redirect(result["redirect"])
    return Response.json_body(json.dumps(result,ensure_ascii=False,separators=(",", ":")).encode(),int(result.get("status") or 400))


def endpoints() -> tuple[Endpoint, ...]:
    return (
        Endpoint("/cloudiff/portal/pagina/taiga", "GET", "taiga.view", authenticated, _page, MODULE),
        Endpoint("/cloudiff/portal/api/taiga", "GET", "taiga.view", authenticated, _api, MODULE),
        Endpoint("/cloudiff/portal/action/taiga-access", "POST", "taiga.manage", is_global, _grant_access, MODULE, csrf=True, origin=True),
    )
