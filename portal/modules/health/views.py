"""health module — HTML assembly via portal.ui only. No data access here."""
from __future__ import annotations

from html import escape

from portal.modules.health import service


def repair_dashboard_page(summary: dict[str, int]) -> str:
    pct = service.score(summary)
    return (
        '<section class="rd-wrap"><div class="rd-head">'
        '<h2>Verificação e reparação</h2></div>'
        '<div class="rd-summary">'
        f'<article><span>Saudáveis</span><strong>{summary.get("ok",0)}</strong></article>'
        f'<article><span>Atenção</span><strong>{summary.get("warn",0)}</strong></article>'
        f'<article><span>Críticos</span><strong>{summary.get("bad",0)}</strong></article>'
        f'<article><span>Total</span><strong>{summary.get("total",0)}</strong></article>'
        f'</div><div class="rd-chart"><div class="rd-ring"><span>{pct}%</span></div></div>'
        '</section>'
    )


def unavailable(title: str) -> str:
    return f'<section class="card"><h2>{escape(title)}</h2><p class="chip is-halt">Temporariamente indisponível.</p></section>'
