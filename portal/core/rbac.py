"""Permission decisions for Portal v2 - the single place access is decided.

Modules declare a permission string per route in ``routes.py``. No view or
service decides access (REQUIREMENTS R-PERM-4). The observed v1 decisions live
in ``config/permissions-v1-observed.json`` and are the acceptance target (A2).

Two admin semantics coexist, faithfully reproduced from the v1 (R-PERM-2):

* ``is_admin`` - canonical: exact membership in the admin group.
* ``is_admin_legacy`` - permissive substring match; used ONLY by git-komodo
  routes in the v1. Unifying them is a separate policy decision (REQUIREMENTS 10).
"""
from __future__ import annotations

from collections.abc import Callable

from portal.core.auth import Identity

PermissionCheck = Callable[[str], bool]

ADMIN_GROUP = "cloudif-tenants-admin"
PROFESSOR_GROUP = "cloudif-professor"
TENANT_GROUP = "cloudif-tenants"
_LEGACY_ADMIN_USERS = frozenset({"admin", "akadmin"})


def _lower_groups(identity: Identity) -> frozenset[str]:
    return frozenset(g.strip().lower() for g in identity.groups if g.strip())


def is_admin(identity: Identity) -> bool:
    """Canonical admin: exact membership in the admin group or Domain Admins."""
    groups = _lower_groups(identity)
    return ADMIN_GROUP in groups or "domain admins" in groups


def is_admin_legacy(identity: Identity) -> bool:
    """v54/v56 semantics: substring 'admin' in any group, or a legacy username.

    Reproduced verbatim from the v1 for the git-komodo routes only.
    """
    groups = _lower_groups(identity)
    if any("admin" in g for g in groups):
        return True
    return identity.username.strip().lower() in _LEGACY_ADMIN_USERS


def is_professor(identity: Identity) -> bool:
    return PROFESSOR_GROUP in _lower_groups(identity)


def is_global(identity: Identity) -> bool:
    """v1 'global' actor: admin, tenant-admin or professor (project_action, etc.)."""
    groups = _lower_groups(identity)
    return is_admin(identity) or ADMIN_GROUP in groups or PROFESSOR_GROUP in groups


def can_repair(identity: Identity) -> bool:
    """v1 _rd_can_repair: admin | Tenants-Admin | Professor."""
    return is_admin(identity) or is_professor(identity)


def internal_only(_identity: Identity) -> bool:
    """Internal token routes are never authorized by group; the edge denies all.

    The real check is IP allowlist + bearer token, performed by the legacy
    ingest handler. In the module boundary these routes stay closed to any
    interactive identity (aluno/professor/admin all deny), matching the v1.
    """
    return False


def authenticated(_identity: Identity) -> bool:
    """Any signed-in identity. Per-object scope (project visibility) is applied
    inside the service, not at the edge."""
    return True
