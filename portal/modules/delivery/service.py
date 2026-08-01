"""delivery — dados de entrega. Sem HTML, sem decisão de acesso."""
from __future__ import annotations

SENTINEL_PROMOTIONS = "sistema-de-biblioteca-teste"


def can_see_promotions(visible_slugs: set[str]) -> bool:
    """v1: promotions visible only if the sentinel project is visible."""
    return SENTINEL_PROMOTIONS in visible_slugs
