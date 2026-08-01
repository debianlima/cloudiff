"""projects.views — HTML da página de Projetos (fiel à v1, com formulários reais).

Ações portadas e verificadas (habilitadas): Checar/Sincronizar e Editar
(edit_save), além de Criar/registrar projeto (create_project). Ações ainda não
portadas (Integrar, Publicar, Terminal, Reparo) aparecem desabilitadas com marca
"em breve" e um link para a interface legada, para nunca falharem em silêncio.
"""
from __future__ import annotations

import html
import os

BASE = "/cloudiff/portal"


def _setting(key: str, default: str) -> str:
    return os.environ.get(key) or default


def h(s) -> str:
    return html.escape(str(s or ""), quote=True)


def _card(p: dict, csrf: str) -> str:
    forgejo = p.get("repo_url") or _setting("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git")
    komodo = _setting("CLOUDIF_KOMODO_URL", "https://komodoiff.duckdns.org/")
    tenant = p.get("tenant") or ""
    pill_cls = "pill ok" if tenant else "pill muted"
    pill_txt = h(tenant or "sem banco")
    status = h(p.get("komodo_status") or "not_configured")
    slug = h(p.get("slug"))
    edit_id = "edit_" + (p.get("slug") or "").replace(".", "_").replace("-", "_")
    legacy = f"{BASE}/?tab=projetos"
    return f"""<article class="pj-card">
  <div class="pj-card-head">
    <div><h3>{h(p.get('name') or p.get('slug'))}</h3>
      <p class="pj-slug">slug: {slug}</p></div>
    <span class="{pill_cls}">{pill_txt}</span>
  </div>
  <p class="pj-owner">Responsável: {h(p.get('owner') or '-')}</p>
  <p class="pj-links"><a href="{h(forgejo)}" target="_blank" rel="noopener">Git</a>
    · <a href="{h(komodo)}" target="_blank" rel="noopener">Komodo</a></p>
  <p class="pj-status">Status: {status}</p>
  <form method="post" action="{BASE}/action/project_action" class="pj-actions">
    <input type="hidden" name="csrf_token" value="{csrf}">
    <input type="hidden" name="slug" value="{slug}">
    <button class="pj-btn" name="op" value="check">Checar</button>
    <button class="pj-btn pj-btn-blue" name="op" value="sync">Sincronizar</button>
    <span class="pj-btn pj-btn-soon" aria-disabled="true" title="Em migração">Integrar<span class="nav-soon">em breve</span></span>
  </form>
  <details class="pj-edit">
    <summary>Editar</summary>
    <form method="post" action="{BASE}/action/project_action" class="pj-form">
      <input type="hidden" name="csrf_token" value="{csrf}">
      <input type="hidden" name="slug" value="{slug}">
      <input type="hidden" name="op" value="edit_save">
      <label>Nome</label>
      <input name="name" value="{h(p.get('name'))}">
      <label>URL do Git/Forgejo</label>
      <input name="repo_url" value="{h(p.get('repo_url'))}">
      <label>Descrição</label>
      <textarea name="description">{h(p.get('description'))}</textarea>
      <input type="hidden" name="komodo_status" value="{status}">
      <button class="pj-btn pj-btn-blue" type="submit">Salvar</button>
    </form>
  </details>
  <p class="pj-legacy"><a href="{legacy}">Publicar, terminal e reparo na interface atual →</a></p>
</article>"""


def _create_form(tenant_opts: str, csrf: str) -> str:
    return f"""<details class="pj-new">
  <summary>Criar / registrar projeto</summary>
  <p class="ov-muted">O projeto pode começar sem banco (só Git/Komodo). O banco pode ser vinculado depois.</p>
  <form method="post" action="{BASE}/action/create_project" class="pj-form">
    <input type="hidden" name="csrf_token" value="{csrf}">
    <label>Nome do projeto</label>
    <input name="name" required placeholder="Ex: Sistema de Biblioteca">
    <label>Descrição</label>
    <textarea name="description" placeholder="Objetivo, turma, disciplina ou grupo responsável"></textarea>
    <label>Banco/Tenant Supabase</label>
    <select name="tenant">{tenant_opts}</select>
    <button class="pj-btn pj-btn-blue" type="submit">Criar / registrar projeto</button>
  </form>
</details>"""


def projects_body(data: dict) -> str:
    csrf = data.get("csrf", "")
    projs = data["projects"]
    tenant_opts = data.get("tenant_opts", '<option value="">— sem banco —</option>')
    cards = "".join(_card(p, csrf) for p in projs) or \
        '<p class="ov-muted">Nenhum projeto visível para o seu perfil.</p>'
    return f"""
<section class="ov-section">
  <div class="ov-section-head"><h2>Meus projetos</h2>
    <div class="ov-aggs"><div class="ov-agg"><span>Visíveis</span><b>{data['count']}</b></div></div>
  </div>
  <p class="ov-muted">Projetos que você pode acessar, conforme suas permissões. As ações Checar, Sincronizar, Editar e Criar já operam pela nova interface; Publicar, Integrar, terminal e reparo seguem na interface atual por enquanto.</p>
  {_create_form(tenant_opts, csrf)}
  <div class="pj-grid">{cards}</div>
</section>
"""
