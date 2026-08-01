"""overview.views — HTML da Visão geral (fiel à v1, sem !important, tokens v2)."""
from __future__ import annotations

import html

BASE = "/cloudiff/portal"


def _bar(pct: int) -> str:
    pct = max(0, min(100, int(pct or 0)))
    return (f'<div class="ov-bar"><div class="ov-bar-fill" style="width:{pct}%"></div></div>')


def _server_card(n: dict) -> str:
    badge = ('<span class="ov-badge ov-badge-ok">online</span>' if n["online"]
             else '<span class="ov-badge ov-badge-bad">falha</span>')
    fmt = _server_card.fmt
    return f"""<div class="ov-card">
  <div class="ov-card-head"><h3>{html.escape(n['node'])}</h3>{badge}</div>
  <div class="ov-metric"><span>RAM</span><b>{fmt(n['mem_used'])} / {fmt(n['mem_total'])}</b></div>
  {_bar(n['mem_pct'])}
  <div class="ov-metric"><span>Disco</span><b>{fmt(n['disk_used'])} / {fmt(n['disk_total'])}</b></div>
  {_bar(n['disk_pct'])}
  <p class="ov-updated">Atualizado: {html.escape(n['updated_at'] or '-')}</p>
</div>"""


def overview_body(data: dict) -> str:
    m = data["metrics"]
    _server_card.fmt = m["fmt"]
    u = html.escape(data["username"] or "usuário")
    cards = "".join(_server_card(n) for n in m["nodes"]) or \
        '<div class="ov-card">Sem métricas em cache.</div>'
    shortcuts = "".join(
        f'<a class="ov-quick" href="{href}">{label}</a>' for label, href in (
            ("Projetos", f"{BASE}/?tab=projetos"),
            ("Aprovações", f"{BASE}/?tab=aprovacoes"),
            ("Bancos", f"{BASE}/?tab=bancos"),
            ("Git + Komodo", f"{BASE}/?tab=git"),
            ("Monitor", f"{BASE}/control"),
        ))
    return f"""
<section class="ov-hero">
  <div class="ov-hero-main">
    <p class="ov-eyebrow">Ambiente acadêmico integrado</p>
    <h2>Olá, {u}.</h2>
    <p>Use este painel para {html.escape(data['role_text'])}, acompanhar bancos, versões publicadas e a saúde dos serviços.</p>
  </div>
  <aside class="ov-quicks"><h3>Atalhos rápidos</h3><div class="ov-quick-grid">{shortcuts}</div></aside>
</section>

<section class="ov-section">
  <div class="ov-section-head"><h2>Servidores CloudIF</h2>
    <div class="ov-aggs"><div class="ov-agg"><span>RAM agregada</span><b>{html.escape(m['agg_mem'])}</b></div>
    <div class="ov-agg"><span>Disco agregado</span><b>{html.escape(m['agg_disk'])}</b></div></div>
  </div>
  <p class="ov-muted">Visão agregada dos agentes das máquinas que compõem a plataforma.</p>
  <div class="ov-grid">{cards}</div>
</section>

<section class="ov-section">
  <h2>Informações da Plataforma</h2>
  <p class="ov-muted">Estado do portal, frontend, deploy, router/proxy e scripts de integração.</p>
  <a class="ov-btn" href="{BASE}/?tab=info">Abrir Informações da Plataforma</a>
</section>
"""
