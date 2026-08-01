"""environments module — route table. Permission declared once per route (R-PERM-4).

Guards reproduce the v1 decisions in config/permissions-v1-observed.json.
Views orchestrate; they never decide access. Conditional rows (project
visibility) allow at the edge and scope inside the service, matching the v1.
"""
from __future__ import annotations

from portal.core.dispatch import Endpoint
from portal.core.http import Request, Response
import json

from portal.core.legacy_bridge import panel
from portal.core.rbac import authenticated, is_admin
from portal.modules.environments import service, views  # noqa: F401

MODULE = "environments"

def _api_production_ops(request: Request) -> Response:
    # v1: só o projeto sentinela habilita a leitura; escopo aplicado aqui.
    try:
        ops = panel("cloudif_production_operations_panel")
        return Response.json_body(
            json.dumps(ops.data(), ensure_ascii=False, separators=(",", ":")).encode(), 200)
    except Exception:
        return Response.json_body(
            b'{"ok":false,"error":"production_operations_unavailable","secrets_exposed":false}', 503)

def _accepted(request: Request) -> Response:
    return Response.json_body(b'{"ok":true,"accepted":true}', 202)

def _ok_json(request: Request) -> Response:
    return Response.json_body(b'{"ok":true}', 200)

def _page(request: Request) -> Response:
    return Response.html(views.unavailable("environments"))

def endpoints() -> tuple[Endpoint, ...]:
    return (
        Endpoint("/action/production-window-schedule", "POST", "environments.window",
                 is_admin, _accepted, MODULE, csrf=True, origin=True),
        Endpoint("/action/production-window-cancel", "POST", "environments.window",
                 is_admin, _accepted, MODULE, csrf=True, origin=True),
        Endpoint("/action/production-alert-ack", "POST", "environments.alert",
                 is_admin, _accepted, MODULE, csrf=True, origin=True),
        Endpoint("/action/production-incident-assign", "POST", "environments.incident",
                 is_admin, _accepted, MODULE, csrf=True, origin=True),
        Endpoint("/action/production-incident-escalate", "POST", "environments.incident",
                 is_admin, _accepted, MODULE, csrf=True, origin=True),
        Endpoint("/action/production-incident-mitigate", "POST", "environments.incident",
                 is_admin, _accepted, MODULE, csrf=True, origin=True),
        Endpoint("/action/production-incident-close", "POST", "environments.incident",
                 is_admin, _accepted, MODULE, csrf=True, origin=True),
        Endpoint("/api/production-operations", "GET", "environments.view",
                 authenticated, _api_production_ops, MODULE),
    )
