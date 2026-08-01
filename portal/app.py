"""Thin coexistence entry point for Portal v2.

The registry starts empty. Unknown routes are delegated to the immutable legacy
adapter, so enabling this foundation changes no user-visible route.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from portal.registry import registry


class Request(Protocol):
    path: str


LegacyHandler = Callable[[Request], object]


def handle(request: Request, legacy_handler: LegacyHandler) -> object:
    route = registry.match(request.path)
    if route is None:
        return legacy_handler(request)
    return route.handler(request)
