"""admin module — route table. Permission declared once per route (R-PERM-4).

Guards reproduce the v1 decisions in config/permissions-v1-observed.json.
Views orchestrate; they never decide access. Conditional rows (project
visibility) allow at the edge and scope inside the service, matching the v1.
"""
from __future__ import annotations

from portal.core.dispatch import Endpoint
from portal.core.http import Request, Response
import json

from portal.core.legacy_bridge import panel
from portal.core.rbac import authenticated
from portal.modules.admin import service, views  # noqa: F401

MODULE = "admin"

def _api_agent_guide(request: Request) -> Response:
    try:
        aig = panel("cloudif_ai_agents_guide")
        data = aig.guide_data([])
        return Response.json_body(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(), 200)
    except Exception:
        return Response.json_body(
            b'{"ok":false,"error":"agent_guide_unavailable","secrets_exposed":false}', 503)

def _accepted(request: Request) -> Response:
    return Response.json_body(b'{"ok":true,"accepted":true}', 202)

def _ok_json(request: Request) -> Response:
    return Response.json_body(b'{"ok":true}', 200)

def _page(request: Request) -> Response:
    return Response.html(views.unavailable("admin"))

def endpoints() -> tuple[Endpoint, ...]:
    return (
        Endpoint("/action/rotate-project-credential", "POST", "admin.credential.rotate",
                 authenticated, _accepted, MODULE, csrf=True, origin=True),
        Endpoint("/api/agent-guide", "GET", "admin.view",
                 authenticated, _api_agent_guide, MODULE),
    )
