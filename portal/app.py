"""Coexistence entry point for Portal v2.

The registry starts populated by ``portal.wiring.install()``. A request that
matches a registered (path, method) is served by the module after edge checks
(permission, CSRF, origin) run in ``dispatch.enforce``. Anything unmatched is
delegated to the immutable legacy adapter, so any route not yet migrated keeps
its exact v1 behaviour.
"""
from __future__ import annotations

from collections.abc import Callable

from portal.core.dispatch import enforce
from portal.core.http import Request, Response
from portal.registry import registry

LegacyHandler = Callable[[Request], Response]


def handle(request: Request, legacy_handler: LegacyHandler) -> Response:
    endpoint = registry.match(request.path, request.method)
    if endpoint is None:
        return legacy_handler(request)
    return enforce(endpoint, request)
