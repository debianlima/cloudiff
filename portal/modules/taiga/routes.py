"""Taiga module routes — read-only, project-scoped and authenticated."""
from __future__ import annotations

import json

from portal.core.dispatch import Endpoint
from portal.core.http import Request, Response
from portal.core.rbac import authenticated
from portal.modules.taiga import service, views

MODULE = "taiga"


def _page(request: Request) -> Response:
    from portal.ui import shell
    from portal.wiring import all_endpoints
    data = service.taiga_data(request.identity, request.q("project"))
    body = views.taiga_body(data)
    nav = sorted({endpoint.module for endpoint in all_endpoints() if endpoint.method == "GET" and endpoint.guard(request.identity)})
    return Response.html(shell.render(request.identity, nav, MODULE, "Taiga", body))


def _api(request: Request) -> Response:
    data = service.taiga_data(request.identity, request.q("project"))
    return Response.json_body(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode())


def endpoints() -> tuple[Endpoint, ...]:
    return (
        Endpoint("/cloudiff/portal/pagina/taiga", "GET", "taiga.view", authenticated, _page, MODULE),
        Endpoint("/cloudiff/portal/api/taiga", "GET", "taiga.view", authenticated, _api, MODULE),
    )
