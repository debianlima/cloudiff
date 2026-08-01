"""Edge dispatcher: resolve route, enforce permission once, then call the view.

This is the only place a permission is checked (R-PERM-4). A route carries a
``guard`` callable ``(Identity) -> bool``; if it returns False the dispatcher
answers 403 and the module's handler never runs. CSRF/origin for ``/action/``
routes are enforced here too, before the handler, so no module reimplements them.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from portal.core.auth import Identity
from portal.core.http import Request, Response
from portal.core.security import csrf_valid, same_origin

Guard = Callable[[Identity], bool]
View = Callable[[Request], Response]


@dataclass(frozen=True, slots=True)
class Endpoint:
    path: str
    method: str
    permission: str
    guard: Guard
    view: View
    module: str
    csrf: bool = False
    origin: bool = False


def _forbidden(message: str = "Acesso negado.") -> Response:
    return Response.html(f"<h1>403</h1><p>{message}</p>", 403)


def enforce(endpoint: Endpoint, request: Request) -> Response:
    """Run edge checks in the v1 order: origin -> csrf -> permission -> view."""
    if endpoint.origin and not same_origin(request.headers, request.headers.get("Host", "")):
        return _forbidden("Origem da requisição não autorizada.")
    if endpoint.csrf and not csrf_valid(request.identity, request.f("csrf_token")):
        return _forbidden("Token CSRF inválido ou ausente.")
    if not endpoint.guard(request.identity):
        return _forbidden("Restrito ao seu perfil de acesso.")
    return endpoint.view(request)
