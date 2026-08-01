"""overview module — route table. Permission declared once per route (R-PERM-4).

Guards reproduce the v1 decisions in config/permissions-v1-observed.json.
Views orchestrate; they never decide access. Conditional rows (project
visibility) allow at the edge and scope inside the service, matching the v1.
"""
from __future__ import annotations

from portal.core.dispatch import Endpoint
from portal.core.http import Request, Response
from portal.core.rbac import authenticated
from portal.modules.overview import service, views  # noqa: F401

MODULE = "overview"

def _accepted(request: Request) -> Response:
    return Response.json_body(b'{"ok":true,"accepted":true}', 202)

def _ok_json(request: Request) -> Response:
    return Response.json_body(b'{"ok":true}', 200)

def _page(request: Request) -> Response:
    from portal.ui import shell
    from portal.wiring import all_endpoints
    data = service.overview_data(request.identity)
    body = views.overview_body(data)
    nav = sorted({e.module for e in all_endpoints()})
    html = shell.render(request.identity, nav, "overview", "Visão geral", body)
    return Response.html(html)

def endpoints() -> tuple[Endpoint, ...]:
    return (
        Endpoint("/cloudiff/portal", "GET", "overview.view",
                 authenticated, _page, MODULE),
        Endpoint("/cloudiff/portal/", "GET", "overview.view",
                 authenticated, _page, MODULE),
    )
