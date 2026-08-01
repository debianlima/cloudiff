"""delivery module — route table. Permission declared once per route (R-PERM-4).

Guards reproduce the v1 decisions in config/permissions-v1-observed.json.
Views orchestrate; they never decide access. Conditional rows (project
visibility) allow at the edge and scope inside the service, matching the v1.
"""
from __future__ import annotations

from portal.core.dispatch import Endpoint
from portal.core.http import Request, Response
import json
import os

from portal.core.legacy_bridge import panel
from portal.core.rbac import authenticated
from portal.modules.delivery import service, views  # noqa: F401

MODULE = "delivery"

def _api_promotions(request: Request) -> Response:
    try:
        ph = panel("cloudif_promotion_panel")
        data = ph.fetch(os.environ.get("CLOUDIF_MONITOR_URL", "http://127.0.0.1:18199"),
                        os.environ.get("CLOUDIF_MONITOR_TOKEN", ""))
        return Response.json_body(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(), 200)
    except Exception:
        return Response.json_body(b'{"ok":false,"error":"promotion_monitor_unavailable"}', 503)

def _accepted(request: Request) -> Response:
    return Response.json_body(b'{"ok":true,"accepted":true}', 202)

def _ok_json(request: Request) -> Response:
    return Response.json_body(b'{"ok":true}', 200)

def _page(request: Request) -> Response:
    return Response.html(views.unavailable("delivery"))

def endpoints() -> tuple[Endpoint, ...]:
    return (
        Endpoint("/action/open-project-terminal", "GET", "delivery.terminal",
                 authenticated, _page, MODULE),
        Endpoint("/api/promotions", "GET", "delivery.view",
                 authenticated, _api_promotions, MODULE),
    )
