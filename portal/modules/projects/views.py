"""projects.views — HTML da página de Projetos (cards fiéis à v1).

Só leitura aqui. As ações (check/sync, criar, publicar, reparar) são portadas
uma a uma no service/routes e ligadas aos formulários depois de verificadas.
"""
from __future__ import annotations

import html
import os

BASE = "/cloudiff/portal"


def _setting(key: str, default: str) -> str:
    return os.environ.get(key) or default


def _card(p: dict) -> str:
    forgejo = p.get("repo_url") or _setting("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git")
    komodo = _setting("CLOUDIF_KOMODO_URL", "https://komodoiff.duckdns.org/")
    tenant = p.get("tenant") or ""
    pill_cls = "pill ok" if tenant else "pill muted"
    pill_txt = html.escape(tenant or "sem banco")
    status = html.escape(p.get("komodo_status") or "not_configured")
    return f"""<article class="pj-card">
  <div class="pj-card-head">
    <div><h3>{html.escape(p.get('name') or p.get('slug') or '')}</h3>
      <p class="pj-slug">slug: {html.escape(p.get('slug') or '')}</p></div>
    <span class="{pill_cls}">{pill_txt}</span>
  </div>
  <p class="pj-owner">Responsável: {html.escape(p.get('owner') or '-')}</p>
  <p class="pj-links"><a href="{html.escape(forgejo)}" target="_blank" rel="noopener">Git</a>
    · <a href="{html.escape(komodo)}" target="_blank" rel="noopener">Komodo</a></p>
  <p class="pj-status">Status: {status}</p>
</article>"""


def projects_body(data: dict) -> str:
    projs = data["projects"]
    cards = "".join(_card(p) for p in projs) or \
        '<p class="ov-muted">Nenhum projeto visível para o seu perfil.</p>'
    return f"""
<section class="ov-section">
  <div class="ov-section-head"><h2>Meus projetos</h2>
    <div class="ov-aggs"><div class="ov-agg"><span>Visíveis</span><b>{data['count']}</b></div></div>
  </div>
  <p class="ov-muted">Projetos que você pode acessar, conforme suas permissões.</p>
  <div class="pj-grid">{cards}</div>
</section>
"""
