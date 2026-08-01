"""Route registry for the incremental Portal v2 migration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


class Handler(Protocol):
    def __call__(self, request: object) -> object: ...


@dataclass(frozen=True, slots=True)
class Route:
    path: str
    permission: str
    handler: Handler
    module: str

    def __post_init__(self) -> None:
        if not self.path.startswith("/"):
            raise ValueError("route path must start with '/'")
        if not self.permission.strip():
            raise ValueError("every route must declare a permission")
        if not self.module.strip():
            raise ValueError("every route must declare its module")


class Registry:
    def __init__(self) -> None:
        self._routes: dict[str, Route] = {}

    def register(self, route: Route) -> None:
        if route.path in self._routes:
            raise ValueError(f"duplicate route: {route.path}")
        self._routes[route.path] = route

    def match(self, path: str) -> Route | None:
        return self._routes.get(path)

    def routes(self) -> tuple[Route, ...]:
        return tuple(self._routes.values())

    def navigation(self, allowed: Callable[[str], bool]) -> tuple[Route, ...]:
        return tuple(route for route in self._routes.values() if allowed(route.permission))


registry = Registry()
