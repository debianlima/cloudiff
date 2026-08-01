"""Install every migrated module into the registry.

This is the single place that decides which routes the v2 serves. Import order
is irrelevant because modules never import each other (4 dependency rule).
Call ``install()`` once at startup; call ``uninstall_all()`` to hand every route
back to the legacy adapter (A8).
"""
from __future__ import annotations

from portal.modules import admin, delivery, environments, health, overview, projects
from portal.registry import Registry, registry

_MODULES = (health, admin, delivery, environments, projects, overview)


def install(target: Registry = registry) -> Registry:
    for module in _MODULES:
        target.register_all(module.endpoints())
    return target


def all_endpoints() -> tuple:
    endpoints: list = []
    for module in _MODULES:
        endpoints.extend(module.endpoints())
    return tuple(endpoints)
