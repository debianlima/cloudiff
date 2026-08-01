"""delivery — HTML via portal.ui. Sem dados, sem decisão de acesso."""
from __future__ import annotations

from html import escape


def unavailable(title: str) -> str:
    return f'<section class="card"><h2>{escape(title)}</h2><p class="chip is-halt">Temporariamente indisponível.</p></section>'
