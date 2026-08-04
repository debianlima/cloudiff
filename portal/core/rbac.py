"""Permission decisions for Portal v2.

CloudIFF authorization is based only on canonical CloudIF groups delivered by
the identity provider. Operating-system/domain administrator groups and legacy
usernames do not grant Portal privileges.
"""
from __future__ import annotations

from collections.abc import Callable

from portal.core.auth import Identity

PermissionCheck = Callable[[str], bool]

ADMIN_GROUP = "cloudif-tenants-admin"
PROFESSOR_GROUP = "cloudif-professor"
STUDENT_GROUP = "cloudif-aluno"
TENANT_GROUP = "cloudif-tenants"


def _lower_groups(identity: Identity) -> frozenset[str]:
    return frozenset(g.strip().lower() for g in identity.groups if g.strip())


def is_admin(identity: Identity) -> bool:
    """Administrator only through exact CloudIF-Tenants-Admin membership."""
    return ADMIN_GROUP in _lower_groups(identity)


def is_admin_legacy(identity: Identity) -> bool:
    """Compatibility entry point using the same canonical CloudIF policy."""
    return is_admin(identity)


def is_professor(identity: Identity) -> bool:
    return PROFESSOR_GROUP in _lower_groups(identity)


def is_student(identity: Identity) -> bool:
    return STUDENT_GROUP in _lower_groups(identity)


def is_global(identity: Identity) -> bool:
    """Global Portal actor: CloudIF administrator or CloudIF professor."""
    return is_admin(identity) or is_professor(identity)


def can_repair(identity: Identity) -> bool:
    return is_admin(identity) or is_professor(identity)


def internal_only(_identity: Identity) -> bool:
    """Interactive identities never authorize internal token routes."""
    return False


def authenticated(_identity: Identity) -> bool:
    """Any signed-in identity; object scope is applied inside each service."""
    return True
