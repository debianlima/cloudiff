"""Route registry for the incremental Portal v2 migration.

Routes are keyed by (path, method). An empty registry means every request falls
through to the immutable legacy adapter, so enabling this foundation changes no
user-visible route (REQUIREMENTS 1 invariant; A8 reversibility).
"""
from __future__ import annotations

from collections.abc import Callable

from portal.core.dispatch import Endpoint


class Registry:
    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], Endpoint] = {}

    def register(self, endpoint: Endpoint) -> None:
        key = (endpoint.path, endpoint.method.upper())
        if key in self._routes:
            raise ValueError(f"duplicate route: {endpoint.method} {endpoint.path}")
        self._routes[key] = endpoint

    def register_all(self, endpoints: tuple[Endpoint, ...]) -> None:
        for endpoint in endpoints:
            self.register(endpoint)

    def match(self, path: str, method: str) -> Endpoint | None:
        return self._routes.get((path, method.upper()))

    def routes(self) -> tuple[Endpoint, ...]:
        return tuple(self._routes.values())

    def navigation(self, allowed: Callable[[str], bool]) -> tuple[Endpoint, ...]:
        seen: dict[str, Endpoint] = {}
        for endpoint in self._routes.values():
            if endpoint.method.upper() == "GET" and allowed(endpoint.permission):
                seen.setdefault(endpoint.module, endpoint)
        return tuple(seen.values())


registry = Registry()
