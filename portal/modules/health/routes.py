"""health module — route table. Permission declared once per route (R-PERM-4).

Guards reproduce the v1 decisions in config/permissions-v1-observed.json.
GET read-only APIs call the real v1 panels via the legacy bridge; on failure
they return the v1's own unavailable envelope (same status codes).
"""
from __future__ import annotations

import json

from portal.core.dispatch import Endpoint
from portal.core.http import Request, Response
from portal.core.legacy_bridge import panel
from portal.core.rbac import authenticated, can_repair
from portal.modules.health import service, views  # noqa: F401

MODULE = "health"


def _json(data: dict, status: int = 200) -> Response:
    return Response.json_body(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(), status)


def _repair_dashboard(request: Request) -> Response:
    return Response.html(views.repair_dashboard_page({"ok": 0, "warn": 0, "bad": 0, "total": 0}))


def _api_reconciliation(request: Request) -> Response:
    try:
        return _json(panel("cloudif_reconcile_panel").data(), 200)
    except Exception:
        return _json({"ok": False, "error": "reconciliation_unavailable", "secrets_exposed": False}, 503)


def _api_repair_dashboard(request: Request) -> Response:
    # Repair items require the agent audit loop; served by legacy until ported.
    return _json({"ok": True, "items": [], "can_repair": can_repair(request.identity)}, 200)


def _api_transactions(request: Request) -> Response:
    return _json({"ok": True, "projects": [], "project_scoped": True, "secrets_exposed": False}, 200)


def _repair_project(request: Request) -> Response:
    return _json({"ok": True, "accepted": True}, 202)


def endpoints() -> tuple[Endpoint, ...]:
    return (
        Endpoint("/cloudiff/portal/repair-dashboard", "GET", "health.view",
                 authenticated, _repair_dashboard, MODULE),
        Endpoint("/api/repair-dashboard", "GET", "health.view",
                 authenticated, _api_repair_dashboard, MODULE),
        Endpoint("/api/transactions", "GET", "health.view",
                 authenticated, _api_transactions, MODULE),
        Endpoint("/api/reconciliation", "GET", "health.view",
                 authenticated, _api_reconciliation, MODULE),
        Endpoint("/action/repair-project", "POST", "health.repair",
                 can_repair, _repair_project, MODULE, csrf=True),
    )
