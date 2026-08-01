"""admin — dados administrativos. Sem HTML, sem decisão de acesso."""
from __future__ import annotations


def can_rotate(is_admin: bool, is_owner: bool, is_global: bool) -> bool:
    """v1 _oi_can_rotate: visible AND (admin | owner | Tenants-Admin | Professor).

    Visibility is checked before this call; here we combine the actor flags.
    """
    return bool(is_admin or is_owner or is_global)
