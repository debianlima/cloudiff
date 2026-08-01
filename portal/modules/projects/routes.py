"""projects module — route table. Permission declared once per route (R-PERM-4).

Guards reproduce the v1 decisions in config/permissions-v1-observed.json.
Views orchestrate; they never decide access. Conditional rows (project
visibility) allow at the edge and scope inside the service, matching the v1.
"""
from __future__ import annotations

from portal.core.dispatch import Endpoint
from portal.core.http import Request, Response
import json

from portal.core.rbac import authenticated
from portal.modules.projects import service, views  # noqa: F401

MODULE = "projects"

def _project_action(request: Request) -> Response:
    slug = (request.form.get("slug") or "").strip()
    op = (request.form.get("op") or "").strip()
    result = service.project_action(request.identity, slug, op)
    if result.get("redirect"):
        return Response.redirect(result["redirect"])
    return Response.json_body(json.dumps(result, ensure_ascii=False).encode(),
                              200 if result.get("ok") else 400)

def _page_projetos(request: Request) -> Response:
    from portal.ui import shell
    from portal.wiring import all_endpoints
    data = service.projects_data(request.identity)
    body = views.projects_body(data)
    nav = sorted({e.module for e in all_endpoints()})
    return Response.html(shell.render(request.identity, nav, "projects", "Projetos", body))

def _accepted(request: Request) -> Response:
    return Response.json_body(b'{"ok":true,"accepted":true}', 202)

def _api_agia(request: Request) -> Response:
    try:
        src = json.load(open("/var/lib/cloudif/health/project-state-reconcile.json"))
        keys = ("ok", "generated_at", "last_success_at", "changed", "execution_mode",
                "projects_count", "projects_ready", "agents_aligned", "capabilities_aligned",
                "catalog_tools", "projects", "tokens_rotated", "tokens_returned",
                "effects_executed", "secrets_exposed")
        data = {k: src.get(k) for k in keys}
        data["ok"] = data.get("ok") is True
        data["secrets_exposed"] = False
        status = 200 if data["ok"] else 503
    except Exception:
        data = {"ok": False, "error": "agia_lifecycle_unavailable", "secrets_exposed": False}
        status = 503
    return Response.json_body(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(), status)

def _ok_json(request: Request) -> Response:
    return Response.json_body(b'{"ok":true}', 200)

def endpoints() -> tuple[Endpoint, ...]:
    return (
        Endpoint("/cloudiff/portal/pagina/projetos", "GET", "project.view",
                 authenticated, _page_projetos, MODULE),
        Endpoint("/action/project_action", "POST", "project.manage",
                 authenticated, _project_action, MODULE, csrf=True),
        Endpoint("/action/publication", "POST", "project.publish",
                 authenticated, _accepted, MODULE, csrf=True),
        Endpoint("/api/approvals", "GET", "project.view",
                 authenticated, _ok_json, MODULE),
        Endpoint("/api/publication", "GET", "project.view",
                 authenticated, _ok_json, MODULE),
        Endpoint("/api/project-capabilities", "GET", "project.view",
                 authenticated, _ok_json, MODULE),
        Endpoint("/api/project-identities", "GET", "project.view",
                 authenticated, _ok_json, MODULE),
        Endpoint("/api/agia-lifecycle", "GET", "project.view",
                 authenticated, _api_agia, MODULE),
    )
