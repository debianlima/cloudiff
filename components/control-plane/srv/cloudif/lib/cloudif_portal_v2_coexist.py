"""CloudIFF Portal v2 coexistence and auto-recovery adapter.

Native v2 routes are dispatched first. Every remaining Portal HTML GET is
rendered by the legacy handler into an in-memory buffer and adapted to the
canonical v2 shell. APIs, downloads, redirects and all state-changing methods
remain untouched. Any adapter exception returns the exact legacy response.
"""
from __future__ import annotations

from io import BytesIO
import dataclasses
import os
import sys
import urllib.parse
import json
import html
import re
import subprocess
import datetime as dt
from pathlib import Path

LIB = "/srv/cloudif/lib"
DESIGN = LIB + "/portal/design"
ASSET_PREFIXES = ("/cloudiff/portal/assets/", "/cloudif/portal/assets/", "/assets/")
ASSET_ALLOW = {"tokens.css", "base.css", "components.css", "app.js"}
PORTAL_PATHS = {"/", "/cloudif/portal", "/cloudif/portal/", "/cloudiff/portal", "/cloudiff/portal/"}
NATIVE_READY = {
    ("/cloudiff/portal/api/reconciliation", "GET"),
    ("/api/reconciliation", "GET"),
    ("/cloudiff/portal", "GET"),
    ("/cloudiff/portal/", "GET"),
    ("/", "GET"),
}


def _install() -> None:
    if os.environ.get("CLOUDIF_PORTAL_V2") != "1":
        return
    if LIB not in sys.path:
        sys.path.insert(0, LIB)

    from portal.app import handle
    from portal.core.auth import Identity
    from portal.core.http import Request
    from portal.core.legacy_shell import transform
    from portal.ui.shell import render_legacy
    from portal.registry import registry
    from portal.wiring import install as wire

    if not registry.routes():
        wire()

    def identity(headers) -> Identity:
        username = (headers.get("X-authentik-username") or headers.get("X-Authentik-Username") or "unknown").strip().lower()
        email = (headers.get("X-authentik-email") or headers.get("X-Authentik-Email") or "").strip().lower()
        raw = headers.get("X-authentik-groups") or headers.get("X-Authentik-Groups") or ""
        for separator in (";", "|"):
            raw = raw.replace(separator, ",")
        return Identity(username, email, frozenset(group.strip() for group in raw.split(",") if group.strip()))

    def request_for(handler, method: str) -> Request:
        parsed = urllib.parse.urlparse(handler.path)
        query = {key: values[0] for key, values in urllib.parse.parse_qs(parsed.query).items()}
        return Request(
            parsed.path,
            method,
            identity(handler.headers),
            query,
            {},
            {key: value for key, value in handler.headers.items()},
            getattr(handler, "client_address", ("", 0))[0],
        )

    def send(handler, status: int, content_type: str, body: bytes, headers=()) -> None:
        handler.send_response(status)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Cache-Control", "no-store")
        for key, value in headers:
            if key.lower() not in {"content-length", "content-type", "cache-control", "transfer-encoding"}:
                handler.send_header(key, value)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        if body:
            handler.wfile.write(body)

    def send_response_object(handler, response) -> None:
        send(handler, response.status, response.content_type, response.body, response.headers)

    def send_json(handler, status: int, payload) -> None:
        send(handler, status, "application/json; charset=utf-8", json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def try_asset(handler, path: str) -> bool:
        name = None
        for prefix in ASSET_PREFIXES:
            if path.startswith(prefix):
                name = path[len(prefix) :]
                break
        if name is None or name not in ASSET_ALLOW:
            return False
        file_path = os.path.join(DESIGN, name)
        if not os.path.isfile(file_path):
            return False
        with open(file_path, "rb") as stream:
            data = stream.read()
        content_type = "text/css; charset=utf-8" if name.endswith(".css") else "application/javascript; charset=utf-8"
        send(handler, 200, content_type, data)
        return True

    def capture_legacy(handler, previous_get):
        original = {
            "wfile": handler.wfile,
            "send_response": handler.send_response,
            "send_header": handler.send_header,
            "end_headers": handler.end_headers,
        }
        buffer = BytesIO()
        status = {"code": 200}
        headers: list[tuple[str, str]] = []
        handler.wfile = buffer
        handler.send_response = lambda code, message=None: status.__setitem__("code", code)
        handler.send_header = lambda key, value: headers.append((str(key), str(value)))
        handler.end_headers = lambda: None
        try:
            previous_get(handler)
            return status["code"], tuple(headers), buffer.getvalue()
        finally:
            handler.wfile = original["wfile"]
            handler.send_response = original["send_response"]
            handler.send_header = original["send_header"]
            handler.end_headers = original["end_headers"]

    def header_value(headers, name: str, default: str = "") -> str:
        wanted = name.lower()
        for key, value in headers:
            if key.lower() == wanted:
                return value
        return default

    def tenant_admin_allowed(handler) -> bool:
        groups = {group.strip().lower() for group in identity(handler.headers).groups}
        return "cloudif-tenants-admin" in groups

    def admin_ad_body() -> str:
        return r"""
<section class="card admin-ad-console">
  <div class="section-title"><div><h2>Pesquisa no Active Directory</h2><p>Localize usuários e grupos reais enquanto digita.</p></div><span class="pill ok">Consulta em tempo real</span></div>
  <div class="help">Digite pelo menos dois caracteres. A consulta usa o Samba/Winbind configurado na plataforma e não cria dados simulados.</div>
  <div class="admin-ad-form">
    <label>Tipo<select id="admin-ad-type"><option value="all">Usuários e grupos</option><option value="user">Usuários</option><option value="group">Grupos</option></select></label>
    <label>Usuário ou grupo<input id="admin-ad-query" autocomplete="off" placeholder="Nome, matrícula, login ou grupo" aria-autocomplete="list" aria-controls="admin-ad-results"></label>
  </div>
  <div id="admin-ad-status" class="small" role="status">Aguardando pesquisa.</div>
  <div id="admin-ad-results" class="admin-ad-results" role="listbox"></div>
  <div id="admin-ad-selected" class="admin-ad-selected" hidden></div>
</section>
<style>
.admin-tools-layout{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:18px;align-items:start}.admin-tools-layout>.card{margin:0;min-width:0}.admin-ad-console{display:grid;gap:14px;min-width:0}.admin-ad-form{display:grid;grid-template-columns:minmax(180px,240px) minmax(260px,1fr);gap:12px;align-items:end}.admin-ad-form label{display:grid;gap:6px}.admin-ad-results{display:grid;gap:6px;max-height:360px;overflow:auto}.admin-ad-result{display:flex;align-items:center;justify-content:space-between;gap:14px;width:100%;padding:11px 12px;border:1px solid var(--ui141-border,var(--cif-border,#dce3ed));border-radius:10px;background:var(--ui141-surface,var(--cif-surface,#fff));text-align:left;cursor:pointer}.admin-ad-result:hover,.admin-ad-result[aria-selected="true"]{border-color:#176b35;background:var(--c-surface-2,#f3f8f4)}.admin-ad-result small{color:var(--ui141-muted,var(--cif-muted,#64748b))}.admin-ad-selected{padding:14px;border:1px solid var(--ui141-border,var(--cif-border,#dce3ed));border-radius:10px;background:#f8fafc}@media(max-width:720px){.admin-ad-form{grid-template-columns:1fr}}
</style>
<script>
(()=>{const input=document.getElementById('admin-ad-query'),type=document.getElementById('admin-ad-type'),results=document.getElementById('admin-ad-results'),status=document.getElementById('admin-ad-status'),selected=document.getElementById('admin-ad-selected');if(!input)return;let timer=0,controller=null,items=[];const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));function choose(item){input.value=item.principal;selected.hidden=false;selected.innerHTML=`<div class="section-title"><div><small>${item.type==='group'?'Grupo':'Usuário'} selecionado</small><h3>${esc(item.principal)}</h3></div><button class="btn light" type="button" id="admin-ad-copy">Copiar</button></div>`;document.getElementById('admin-ad-copy').onclick=()=>navigator.clipboard.writeText(item.principal);results.innerHTML='';status.textContent='Principal selecionado.'}function draw(data){items=data.items||[];status.textContent=items.length?`${items.length} resultado(s). Use as setas e Enter para selecionar.`:'Nenhum resultado encontrado.';results.innerHTML=items.map((x,i)=>`<button type="button" class="admin-ad-result" role="option" data-index="${i}" aria-selected="false"><span><strong>${esc(x.label)}</strong><small>${x.type==='group'?'Grupo do AD':'Usuário do AD'}</small></span><span class="pill">Selecionar</span></button>`).join('');results.querySelectorAll('button').forEach(b=>b.onclick=()=>choose(items[Number(b.dataset.index)]))}async function search(){const q=input.value.trim();selected.hidden=true;if(q.length<2){results.innerHTML='';status.textContent='Digite pelo menos dois caracteres.';return}if(controller)controller.abort();controller=new AbortController();status.textContent='Consultando Active Directory…';try{const r=await fetch(`/cloudiff/portal/api/admin-ad-search?q=${encodeURIComponent(q)}&type=${encodeURIComponent(type.value)}`,{credentials:'same-origin',headers:{Accept:'application/json'},signal:controller.signal});const content=(r.headers.get('content-type')||'').toLowerCase();if(!content.includes('application/json'))throw new Error(`Resposta inválida (HTTP ${r.status})`);const data=await r.json();if(!r.ok||!data.ok)throw new Error(data.error||`HTTP ${r.status}`);draw(data)}catch(e){if(e.name==='AbortError')return;results.innerHTML='';status.textContent=`Falha na consulta: ${e.message}`}}function schedule(){clearTimeout(timer);timer=setTimeout(search,280)}input.addEventListener('input',schedule);type.addEventListener('change',search);input.addEventListener('keydown',e=>{const buttons=[...results.querySelectorAll('button')];if(!buttons.length)return;let index=buttons.findIndex(b=>b.getAttribute('aria-selected')==='true');if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();buttons.forEach(b=>b.setAttribute('aria-selected','false'));index=e.key==='ArrowDown'?Math.min(index+1,buttons.length-1):Math.max(index-1,0);buttons[index].setAttribute('aria-selected','true');buttons[index].scrollIntoView({block:'nearest'})}else if(e.key==='Enter'&&index>=0){e.preventDefault();choose(items[index])}})})();
</script>
"""

    def admin_wizard_body(owner, user, csrf_token: str, delete_panel: str) -> str:
        try:
            tenants = sorted({str(row.get("tenant") or "").strip() for row in owner.tenants_registry() if str(row.get("tenant") or "").strip()})
        except Exception:
            tenants = []
        options = "".join(f'<option value="{html.escape(tenant)}">{html.escape(tenant)}</option>' for tenant in tenants)
        ad_panel = admin_ad_body().replace('<section class="card admin-ad-console">', '<div class="admin-ad-console">', 1).replace('</section>\n<style>', '</div>\n<style>', 1)
        delete_panel = delete_panel.replace('<section class="card tenant-delete-tool">', '<div class="tenant-delete-tool">', 1).replace('</section>\n<style>', '</div>\n<style>', 1).replace('#eef2ff', '#edf7f0').replace('#4f46e5', '#176b35').replace('#818cf8', '#67a875').replace('#3730a3', '#0f5132')
        return f'''<section class="card admin-operation-center">
  <div class="section-title"><div><span class="admin-eyebrow">Administração do AD e tenants</span><h2>Operações administrativas</h2><p>Escolha uma operação. Cada guia usa os serviços reais da plataforma.</p></div><span class="pill warn">Acesso restrito</span></div>
  <div class="admin-wizard-tabs" role="tablist" aria-label="Operações administrativas">
    <button type="button" role="tab" aria-selected="true" aria-controls="admin-step-tenant" id="admin-tab-tenant" data-admin-step="tenant"><span>1</span><strong>Ações avançadas</strong><small>Sync roles, router e restore</small></button>
    <button type="button" role="tab" aria-selected="false" aria-controls="admin-step-delete" id="admin-tab-delete" data-admin-step="delete"><span>2</span><strong>Remover banco</strong><small>Prévia, backup e exclusão</small></button>
    <button type="button" role="tab" aria-selected="false" aria-controls="admin-step-ad" id="admin-tab-ad" data-admin-step="ad"><span>3</span><strong>Consultar usuários</strong><small>Pesquisa interativa no AD</small></button>
  </div>
  <div class="admin-wizard-panels">
    <section id="admin-step-tenant" class="admin-wizard-panel active" role="tabpanel" aria-labelledby="admin-tab-tenant">
      <div class="admin-panel-heading"><div><span>Etapa 1</span><h3>Ações avançadas do tenant</h3></div><p>Sincronize papéis, regenere o roteador ou restaure a estrutura do tenant.</p></div>
      <form method="post" action="/cloudiff/portal/?action=admin-tenant-advanced" class="admin-tenant-actions" id="admin-tenant-actions">
        <input type="hidden" name="csrf_token" value="{html.escape(csrf_token)}">
        <label>Tenant<select name="tenant" required><option value="">Selecione</option>{options}</select></label>
        <div class="admin-action-cards">
          <button class="admin-action-card" name="op" value="sync_roles"><span>Sync roles</span><small>Sincroniza usuários, papéis e credenciais do banco.</small></button>
          <button class="admin-action-card" name="op" value="render_router"><span>Render router</span><small>Recria as rotas e o SSO dos tenants registrados.</small></button>
          <button class="admin-action-card" name="op" value="ensure"><span>Ensure/restore</span><small>Valida e restaura a estrutura operacional do tenant.</small></button>
        </div>
        <div id="admin-tenant-action-status" class="admin-action-status" role="status">Selecione um tenant e uma ação.</div>
      </form>
    </section>
    <section id="admin-step-delete" class="admin-wizard-panel" role="tabpanel" aria-labelledby="admin-tab-delete" hidden>{delete_panel}</section>
    <section id="admin-step-ad" class="admin-wizard-panel" role="tabpanel" aria-labelledby="admin-tab-ad" hidden>{ad_panel}</section>
  </div>
</section>
<style>
.admin-operation-center{{--c-primary:#6b742f;--c-primary-hover:#4f5720;--c-primary-soft:#eef0df;--c-primary-border:#9aa35b;--c-accent:#6b742f;--c-accent-soft:#eef0df;display:grid;gap:18px;margin:18px 0 24px!important;overflow:hidden;background:#fff!important;border-color:#d9ddbd!important;color:#111111!important}}.admin-operation-center .btn:not(.danger):not(.red),.admin-operation-center button:not(.danger):not(.red){{--c-primary:#6b742f;--c-primary-hover:#4f5720}}.admin-eyebrow{{display:block;margin-bottom:5px;font-size:.72rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:#111}}.admin-wizard-tabs{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}}.admin-wizard-tabs button{{display:grid;grid-template-columns:34px 1fr;gap:2px 10px;align-items:center;min-height:82px;padding:13px;border:1px solid var(--c-border,#dce3ed);border-radius:12px;background:#fff;color:#111!important;text-align:left;box-shadow:none!important}}.admin-wizard-tabs button>span{{grid-row:1/3;width:32px;height:32px;display:grid;place-items:center;border-radius:10px;background:#cdd39a;color:#111;font-weight:850}}.admin-wizard-tabs button strong{{font-size:.9rem}}.admin-wizard-tabs button small{{color:#111!important;line-height:1.25}}.admin-wizard-tabs button[aria-selected="true"]{{border-color:#9aa35b;background:#eef0df;color:#111}}.admin-wizard-tabs button[aria-selected="true"]>span{{background:#9aa35b;color:#111}}.admin-wizard-panels{{border:1px solid #d9ddbd;border-radius:14px;background:#fff;overflow:hidden}}.admin-wizard-panel{{display:none;padding:20px;background:#fff;color:#111111}}.admin-wizard-panel.active{{display:grid;gap:16px}}.admin-panel-heading{{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}}.admin-panel-heading span{{font-size:.72rem;font-weight:850;text-transform:uppercase;color:#111}}.admin-panel-heading h3,.admin-panel-heading p{{margin:3px 0 0}}.admin-panel-heading p{{max-width:580px;color:#111!important}}.admin-tenant-actions{{display:grid;gap:14px}}.admin-tenant-actions>label{{display:grid;gap:6px;max-width:520px}}.admin-action-cards{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}}.admin-action-card{{display:grid;gap:5px;min-height:112px;padding:16px!important;border:1px solid var(--c-border,#dce3ed)!important;border-radius:12px!important;background:#fff!important;color:#111!important!important;text-align:left!important}}.admin-action-card:hover{{border-color:#9aa35b!important;background:#f4f5e9!important}}.admin-action-card span{{font-weight:850}}.admin-action-card small{{color:#111!important;line-height:1.4}}.admin-action-status{{padding:13px 14px;border:1px solid var(--c-border,#dce3ed);border-radius:10px;background:#fff;color:#111111;white-space:pre-wrap}}.admin-action-status.running{{border-color:#9aa35b;background:#eef0df;color:#111}}.admin-action-status.ok{{border-color:#aeb66f;background:#f7f8ed;color:#111111}}.admin-action-status.bad{{border-color:#fecaca;background:#fef2f2;color:#991b1b}}.admin-wizard-panel .admin-ad-console,.admin-wizard-panel .tenant-delete-tool{{display:grid;gap:16px;min-width:0}}.admin-wizard-panel .admin-ad-console>.section-title,.admin-wizard-panel .tenant-delete-tool>.section-title{{padding-bottom:12px;border-bottom:1px solid var(--c-border,#dce3ed)}}@media(max-width:860px){{.admin-wizard-tabs,.admin-action-cards{{grid-template-columns:1fr}}.admin-wizard-tabs button{{min-height:68px}}.admin-panel-heading{{display:grid}}}}
</style>
<script>(()=>{{const tabs=[...document.querySelectorAll('[data-admin-step]')],panels=[...document.querySelectorAll('.admin-wizard-panel')];if(!tabs.length)return;function open(name,focus=false){{tabs.forEach(tab=>{{const active=tab.dataset.adminStep===name;tab.setAttribute('aria-selected',active?'true':'false');tab.tabIndex=active?0:-1;if(active&&focus)tab.focus()}});panels.forEach(panel=>{{const active=panel.id===`admin-step-${{name}}`;panel.hidden=!active;panel.classList.toggle('active',active)}})}}tabs.forEach((tab,index)=>{{tab.onclick=()=>open(tab.dataset.adminStep);tab.onkeydown=e=>{{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();let target=index;if(e.key==='ArrowRight')target=(index+1)%tabs.length;if(e.key==='ArrowLeft')target=(index-1+tabs.length)%tabs.length;if(e.key==='Home')target=0;if(e.key==='End')target=tabs.length-1;open(tabs[target].dataset.adminStep,true)}}}});const form=document.getElementById('admin-tenant-actions'),status=document.getElementById('admin-tenant-action-status');if(form)form.addEventListener('submit',async e=>{{e.preventDefault();const submitter=e.submitter;if(!submitter)return;const fd=new FormData(form),tenant=String(fd.get('tenant')||'').trim(),op=String(submitter.value||'');if(!tenant){{status.className='admin-action-status bad';status.textContent='Selecione um tenant.';return}}const csrf=String(fd.get('csrf_token')||'');const body=new URLSearchParams({{tenant,op,csrf_token:csrf}});form.querySelectorAll('button').forEach(b=>b.disabled=true);status.className='admin-action-status running';status.textContent='Executando '+submitter.querySelector('span').textContent+' em '+tenant+'…';try{{const r=await fetch(form.action,{{method:'POST',credentials:'same-origin',headers:{{Accept:'application/json','Content-Type':'application/x-www-form-urlencoded;charset=UTF-8','X-CSRF-Token':csrf}},body}});if(r.type==='opaqueredirect'||r.status===0)throw new Error('A sessão do Portal expirou. Atualize a página e tente novamente.');const type=(r.headers.get('content-type')||'').toLowerCase();const text=await r.text();if(!type.includes('application/json'))throw new Error('A operação não chegou ao serviço administrativo. Atualize a página e tente novamente.');const data=JSON.parse(text);if(!r.ok||!data.ok)throw new Error(data.error||data.stderr||('HTTP '+r.status));status.className='admin-action-status ok';status.textContent='Concluído: '+data.label+'\\n'+(data.stdout||data.message||'Operação executada com sucesso.')}}catch(err){{status.className='admin-action-status bad';status.textContent='Falha: '+err.message}}finally{{form.querySelectorAll('button').forEach(b=>b.disabled=false)}}}});open('tenant') }})();</script>'''

    def global_services_body(owner, user: dict) -> str:
        try:
            projects = [dict(row) for row in owner.user_visible_projects(user.get("username") or "", user.get("groups") or [])]
        except Exception:
            projects = []
        try:
            runtime = list(owner._rd_projects(user))
        except Exception:
            runtime = []
        try:
            tenants = sorted({str(row.get("tenant") or "").strip() for row in owner.tenants_registry() if str(row.get("tenant") or "").strip()})
        except Exception:
            tenants = []
        runtime_by_slug = {str(row.get("slug") or ""): row for row in runtime}
        repo_cards, container_cards, tenant_cards = [], [], []
        for project in projects:
            slug = str(project.get("slug") or "")
            name = str(project.get("name") or slug)
            repo = str(project.get("repo_url") or "")
            owner_name = str(project.get("owner") or "")
            rt = runtime_by_slug.get(slug) or {}
            if repo:
                repo_cards.append(
                    '<article class="global-resource"><div><span class="global-resource-type">Repositório</span>'
                    f'<h3>{html.escape(name)}</h3><p>{html.escape(owner_name or "Sem proprietário")}</p></div>'
                    f'<a class="btn light" target="_blank" rel="noopener" href="{html.escape(repo, quote=True)}">Abrir Forgejo</a></article>'
                )
            container_cards.append(
                '<article class="global-resource"><div><span class="global-resource-type">Container do projeto</span>'
                f'<h3>{html.escape(name)}</h3><p>Stack: <code>{html.escape(str(rt.get("stack_id") or "não vinculada"))}</code> · '
                f'serviço {html.escape(str(rt.get("service") or "web"))}</p></div>'
                '<a class="btn light" target="_blank" rel="noopener" href="https://komodoiff.duckdns.org/containers">Abrir no Komodo</a></article>'
            )
        for tenant in tenants:
            try:
                services = list(owner.compose_services(tenant))
            except Exception:
                services = []
            running = sum(1 for item in services if any(word in str(item.get("status") or "").lower() for word in ("running", "healthy", "up")))
            service_rows = ''.join(
                '<li><span>' + html.escape(str(item.get("service") or "serviço")) + '</span>' + owner.status_badge(str(item.get("status") or "")) + '</li>'
                for item in services
            ) or '<li>Nenhum serviço detectado.</li>'
            status_class = 'ok' if running else 'warn'
            status_text = 'operacional' if running else 'verificar'
            tenant_cards.append(
                '<details class="global-tenant"><summary><span>'
                f'<strong>{html.escape(tenant)}</strong><small>{len(services)} serviços · {running} ativos</small></span>'
                f'<span class="pill {status_class}">{status_text}</span></summary><div class="global-tenant-body"><ul>{service_rows}</ul>'
                '<div class="global-resource-actions">'
                f'<a class="btn" target="_blank" rel="noopener" href="https://{html.escape(tenant)}.cloudiff.duckdns.org/project/default">Abrir Studio</a>'
                f'<a class="btn light" target="_blank" rel="noopener" href="https://{html.escape(tenant)}.cloudiff.duckdns.org/">Abrir tenant</a>'
                '</div></div></details>'
            )
        return (
            '<section class="global-admin-hub">'
            '<div class="global-admin-hero"><div><span class="global-admin-kicker">Administração global</span><h1>Serviços globais</h1>'
            '<p>Visão consolidada de containers, repositórios e tenants autorizados, sem executar manutenção automática.</p></div><span class="pill ok">Acesso global</span></div>'
            f'<div class="global-admin-summary"><article><small>Projetos</small><strong>{len(projects)}</strong></article><article><small>Containers de projeto</small><strong>{len(container_cards)}</strong></article><article><small>Repositórios</small><strong>{len(repo_cards)}</strong></article><article><small>Tenants</small><strong>{len(tenants)}</strong></article></div>'
            '<nav class="global-admin-shortcuts" aria-label="Atalhos globais"><a class="btn" target="_blank" rel="noopener" href="https://komodoiff.duckdns.org/servers">Servidores</a><a class="btn light" target="_blank" rel="noopener" href="https://komodoiff.duckdns.org/containers">Todos os containers</a><a class="btn light" target="_blank" rel="noopener" href="https://cloudiff.duckdns.org/git/explore/repos">Todos os repositórios</a></nav>'
            f'<section class="global-admin-section"><div class="section-title"><div><h2>Containers e stacks</h2><p>Projetos visíveis e seus vínculos no Komodo.</p></div><span class="pill">{len(container_cards)}</span></div><div class="global-resource-grid">{"".join(container_cards) or "<div class=\"empty-state\">Nenhum container de projeto registrado.</div>"}</div></section>'
            f'<section class="global-admin-section"><div class="section-title"><div><h2>Repositórios por usuário</h2><p>Repositórios Forgejo vinculados aos projetos autorizados.</p></div><span class="pill">{len(repo_cards)}</span></div><div class="global-resource-grid">{"".join(repo_cards) or "<div class=\"empty-state\">Nenhum repositório vinculado.</div>"}</div></section>'
            f'<section class="global-admin-section"><div class="section-title"><div><h2>Tenants Supabase</h2><p>Abra um tenant para conferir os serviços que compõem o banco.</p></div><span class="pill">{len(tenant_cards)}</span></div><div class="global-tenant-list">{"".join(tenant_cards) or "<div class=\"empty-state\">Nenhum tenant provisionado.</div>"}</div></section>'
            '</section>'
            '<style>.global-admin-hub{display:grid;gap:20px}.global-admin-hero{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:24px;border:1px solid #cfe5d5;border-radius:18px;background:#fff}.global-admin-hero h1{margin:4px 0 7px}.global-admin-hero p{margin:0;color:var(--muted)}.global-admin-kicker,.global-resource-type{font-size:.7rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:#176b35}.global-admin-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.global-admin-summary article{padding:16px;border:1px solid var(--border);border-radius:13px;background:#fff}.global-admin-summary small{display:block;color:var(--muted)}.global-admin-summary strong{font-size:1.8rem}.global-admin-shortcuts{display:flex;gap:8px;flex-wrap:wrap}.global-admin-section{display:grid;gap:13px}.global-resource-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:10px}.global-resource{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:16px;border:1px solid var(--border);border-radius:13px;background:#fff}.global-resource h3,.global-resource p{margin:3px 0}.global-resource p{color:var(--muted)}.global-resource-actions{display:flex;gap:8px;flex-wrap:wrap}.global-tenant-list{display:grid;gap:9px}.global-tenant{border:1px solid var(--border);border-radius:13px;background:#fff;overflow:hidden}.global-tenant>summary{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:15px;cursor:pointer;list-style:none}.global-tenant>summary::-webkit-details-marker{display:none}.global-tenant>summary span:first-child{display:grid;gap:3px}.global-tenant>summary small{color:var(--muted)}.global-tenant-body{display:grid;gap:13px;padding:15px;border-top:1px solid var(--border);background:#f8fafc}.global-tenant-body ul{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:7px;margin:0;padding:0;list-style:none}.global-tenant-body li{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px;border-radius:9px;background:#fff}@media(max-width:760px){.global-admin-summary{grid-template-columns:repeat(2,1fr)}.global-admin-hero,.global-resource{align-items:flex-start;display:grid}}</style>'
        )

    def help_body() -> str:
        return r"""
<section class="card platform-guide">
  <div class="section-title"><div><h1>Guia da plataforma</h1><p>Como usar cada área operacional da CloudIFF.</p></div><span class="pill ok">Ambiente real</span></div>
  <nav class="guide-index" aria-label="Seções do guia"><a href="#guia-publicacoes">Publicações</a><a href="#guia-projetos">Projetos</a><a href="#guia-bancos">Bancos</a><a href="#guia-backup">Backup</a><a href="#guia-conectores">Conectores</a><a href="#guia-ad">Administração</a><a href="#guia-grupos">Grupos</a><a href="#guia-regras">Regras</a></nav>
  <div class="guide-grid">
    <article id="guia-publicacoes"><span>01</span><h2>Publicações</h2><p>Acompanhe releases, endereços publicados, saúde e rollback. Uma publicação só aparece quando foi registrada pelos agentes.</p><ol><li>Abra o projeto.</li><li>Confira a release e o endereço.</li><li>Use rollback apenas quando houver release anterior homologada.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=publicacao">Abrir Publicações</a></article>
    <article id="guia-projetos"><span>02</span><h2>Projetos</h2><p>Crie projetos pelo wizard. O fluxo provisiona repositório Forgejo, stack Komodo, ACL e, quando solicitado, tenant Supabase.</p><ol><li>Informe nome e finalidade.</li><li>Escolha banco existente, novo ou sem banco.</li><li>Selecione a tecnologia.</li><li>Acompanhe o provisionamento até concluir.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=projetos">Abrir Projetos</a></article>
    <article id="guia-bancos"><span>03</span><h2>Bancos e tenants</h2><p>Consulte disponibilidade, serviços e permissões. Banco é independente de projeto e pode ser compartilhado.</p><ol><li>Use Iniciar/Parar somente para operação do tenant.</li><li>Abra o Studio pelo endereço exibido.</li><li>Exclua banco apenas em Administração, após remover vínculos de projetos.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=bancos">Abrir Bancos</a></article>
    <article id="guia-backup"><span>04</span><h2>Backup</h2><p>Consulte backups de aplicação e dumps lógicos. A exclusão de projeto não apaga o banco nem seus backups.</p><ol><li>Confira data, tamanho e hash.</li><li>Gere backup antes de mudanças sensíveis.</li><li>Na exclusão de tenant, o dump final é obrigatório.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=backup">Abrir Backup</a></article>
    <article id="guia-conectores"><span>05</span><h2>Conectores</h2><p>Gere credenciais e consulte ferramentas disponíveis para clientes, agentes e integrações MCP autorizadas.</p><ol><li>Escolha o projeto autorizado.</li><li>Gere ou rotacione o token.</li><li>Copie a configuração mostrada pela plataforma.</li><li>Nunca compartilhe o token em repositório ou mensagem.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=agentes">Abrir Conectores</a></article>
    <article id="guia-ad"><span>06</span><h2>Administração</h2><p>Área restrita. Administração do AD localiza usuários e grupos reais; Serviços globais abre Forgejo, Komodo e tenants; exclusões possuem wizard e auditoria.</p><ol><li>Pesquise o principal no AD e selecione a sugestão.</li><li>Use ações avançadas somente no tenant correto.</li><li>Leia a prévia antes de confirmar uma exclusão.</li><li>Reporte a etapa e a mensagem exibidas quando houver falha.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=admin">Abrir Administração</a></article>
    <article id="guia-grupos"><span>07</span><h2>Grupos e permissões</h2><p>O acesso vem dos grupos entregues pelo Authentik e das ACLs de cada projeto.</p><ul><li><strong>CloudIF-Aluno:</strong> consulta recursos autorizados.</li><li><strong>CloudIF-Professor:</strong> cria, administra e exclui projetos autorizados.</li><li><strong>CloudIF-Tenants-Admin:</strong> administra AD, tenants, serviços globais e exclusões.</li></ul><p>Adicionar alguém a um grupo não substitui a ACL específica quando o projeto exige autorização individual.</p></article>
    <article id="guia-regras"><span>08</span><h2>Regras de negócio</h2><ul><li>Projeto e banco possuem ciclos de vida independentes.</li><li>Excluir projeto nunca apaga banco ou backup de banco.</li><li>Tenant vinculado a projeto não pode ser excluído.</li><li>Exclusões exigem confirmação textual e geram auditoria.</li><li>Tokens são exibidos uma única vez após rotação.</li><li>Produção e ações sensíveis exigem as aprovações configuradas.</li><li>Recursos não disponíveis devem aparecer como indisponíveis, nunca como simulados.</li></ul></article>
  </div>
  <div class="help"><strong>Perfis:</strong> Aluno visualiza apenas recursos autorizados. Professor administra projetos e serviços globais permitidos. Administrador de tenants também opera AD e bancos.</div>
</section>
<style>.platform-guide{display:grid;gap:20px}.guide-index{display:flex;flex-wrap:wrap;gap:8px}.guide-index a{padding:8px 11px;border:1px solid var(--ui141-border,var(--cif-border,#dce3ed));border-radius:999px;text-decoration:none}.guide-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}.guide-grid article{display:grid;align-content:start;gap:10px;padding:18px;border:1px solid var(--ui141-border,var(--cif-border,#dce3ed));border-radius:14px;background:var(--ui141-surface,var(--cif-surface,#fff))}.guide-grid article>span{font-size:.75rem;font-weight:800;color:#176b35}.guide-grid h2,.guide-grid p{margin:0}.guide-grid ol{margin:0;padding-left:20px;display:grid;gap:6px}.guide-grid .btn{justify-self:start}</style>
"""

    BACKUP_ROOT = Path("/srv/cloudif/managed-backups/projects")
    BACKUP_STATE = Path("/var/lib/cloudif/portal/project-backup-settings.json")
    BACKUP_REMOTE_ENV = Path("/etc/cloudif/project-backup-remote.env")

    def _backup_owner(filename: str, slug: str) -> str:
        name = filename or ""
        if "__" in name:
            return name.split("__", 1)[0].strip()
        parts = slug.rsplit("-", 1)
        return parts[-1] if len(parts) == 2 and parts[-1].lower().startswith("iff") else ""

    def _backup_items(slug: str) -> list[dict]:
        root = (BACKUP_ROOT / slug)
        items = []
        if not root.is_dir():
            return items
        for f in sorted(root.glob("*.tar.gz"), key=lambda x: x.stat().st_mtime, reverse=True):
            meta = {}
            side = Path(str(f) + ".json")
            try:
                meta = json.loads(side.read_text())
            except Exception:
                pass
            items.append({
                "filename": f.name,
                "size": f.stat().st_size,
                "modified": dt.datetime.fromtimestamp(f.stat().st_mtime, dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
                "type": meta.get("type") or ("database" if "database" in f.name and "application" not in f.name else "application"),
                "sha256": meta.get("sha256") or "",
                "owner": meta.get("owner") or _backup_owner(f.name, slug),
                "tenant": meta.get("tenant") or "",
                "container": meta.get("container") or meta.get("container_scope") or "",
            })
        return items

    def _backup_schedule(unit: str, label: str) -> dict:
        try:
            out = subprocess.check_output(
                ["systemctl", "show", unit, "-p", "ActiveState", "-p", "UnitFileState", "-p", "NextElapseUSecRealtime", "--value"],
                text=True, timeout=8,
            ).splitlines()
            values = (out + ["", "", ""])[:3]
            return {"unit": unit, "label": label, "active": values[0], "enabled": values[1], "next": values[2]}
        except Exception as exc:
            return {"unit": unit, "label": label, "active": "unknown", "enabled": "unknown", "next": "", "error": str(exc)[:120]}

    def _backup_remote_status() -> dict:
        env = {}
        try:
            for raw in BACKUP_REMOTE_ENV.read_text().splitlines():
                line = raw.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1); env[k.strip()] = v.strip().strip('"\'')
        except Exception:
            pass
        host = env.get("REMOTE_HOST") or ""
        port = int(env.get("REMOTE_PORT") or 22)
        enabled = env.get("REMOTE_ENABLED") == "1"
        ready = env.get("REMOTE_READY") == "1"
        reachable = False
        if host and enabled and ready:
            try:
                reachable = subprocess.run(["nc", "-z", "-w", "3", host, str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5).returncode == 0
            except Exception:
                reachable = False
        status = "online" if reachable else ("aguardando destino" if enabled and not ready else ("offline" if enabled else "desativado"))
        return {"configured": bool(host), "enabled": enabled, "ready": ready, "reachable": reachable, "status": status, "host": host, "port": port}

    def backup_inventory(owner, user: dict) -> dict:
        active = []
        active_slugs = set()
        try:
            for project in getattr(owner, "_cpx_allowed_projects")(user):
                slug = project["slug"]
                active_slugs.add(slug)
                try:
                    settings, items = getattr(owner, "_pb_status")(slug)
                except Exception as exc:
                    settings, items = {"enabled": False, "error": str(exc)[:160]}, []
                active.append({"slug": slug, "name": project.get("name") or slug, "owner": project.get("owner") or "", "settings": settings, "items": items, "can_manage": bool(getattr(owner, "_pb_manage")(user, project))})
        except Exception:
            pass
        username = (user.get("username") or "").lower()
        groups = set(user.get("groups") or [])
        global_access = bool(user.get("admin") or groups.intersection({"CloudIF-Tenants-Admin", "CloudIF-Professor", "cloudif-tenants-admin", "cloudif-professor"}))
        history = []
        if BACKUP_ROOT.is_dir():
            for directory in sorted((x for x in BACKUP_ROOT.iterdir() if x.is_dir()), key=lambda x: x.name):
                if directory.name in active_slugs:
                    continue
                items = _backup_items(directory.name)
                owner_name = next((x.get("owner") for x in items if x.get("owner")), "")
                if not global_access and owner_name.lower() != username:
                    continue
                history.append({
                    "slug": directory.name,
                    "owner": owner_name,
                    "items": items[:12],
                    "total_files": len(items),
                    "total_size": sum(int(x.get("size") or 0) for x in items),
                    "last_backup": items[0]["modified"] if items else None,
                    "database_files": sum(1 for x in items if x.get("type") == "database"),
                    "application_files": sum(1 for x in items if x.get("type") == "application"),
                })
        return {
            "ok": True,
            "active": active,
            "history": history,
            "history_total": len(history),
            "remote": _backup_remote_status(),
            "schedules": [
                _backup_schedule("cloudif-project-backup-auto.timer", "Backup automático dos projetos"),
                _backup_schedule("cloudif-tenant-db-backup-v2.timer", "Backup dos bancos e tenants"),
                _backup_schedule("cloudif-config-backup.timer", "Backup da configuração da plataforma"),
            ],
            "retention_days": 14,
        }

    def backup_body(csrf_token: str) -> str:
        return r"""
<section class="card backup-console">
  <div class="section-title"><div><h2>Backup</h2><p>Agenda, servidor remoto, projetos ativos e acervo histórico do mecanismo já configurado.</p></div><button class="btn light" id="backup-refresh" type="button">Atualizar</button></div>
  <div class="ai-disclaimer" role="note"><strong>Aviso de testes e homologação:</strong> a plataforma está em desenvolvimento e homologação. Mantenha cópias próprias das informações importantes, mesmo quando o backup automático estiver ativo.</div>
  <div class="help"><strong>Separação de dados:</strong> backup de aplicação reúne publicações, configuração e metadados. Backup de banco contém dumps lógicos. Segredos e arquivos <code>.env</code> não são incluídos.</div>
  <div id="backup-console-list"><p>Consultando agenda e arquivos de backup…</p></div>
</section>
<style>.backup-console{display:grid;gap:16px}.backup-overview-grid,.backup-console-meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}.backup-overview-grid>div,.backup-console-meta>div{padding:12px;border:1px solid var(--border,#dce3ed);border-radius:11px;background:#f8fafc}.backup-overview-grid small,.backup-console-meta small{display:block;color:var(--muted,#64748b)}.backup-section{display:grid;gap:12px}.backup-section-head{display:flex;align-items:end;justify-content:space-between;gap:14px}.backup-console-grid{display:grid;gap:12px}.backup-console-card{display:grid;gap:14px;padding:17px;border:1px solid var(--border,#dce3ed);border-radius:14px;background:#fff}.backup-console-actions{display:flex;gap:8px;flex-wrap:wrap}.backup-history-card>summary{display:flex;align-items:center;justify-content:space-between;gap:12px;cursor:pointer;list-style:none}.backup-history-card>summary::-webkit-details-marker{display:none}.backup-history-body{display:grid;gap:12px;padding-top:14px}.backup-file-list{display:grid;gap:7px}.backup-file{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;padding:10px;border:1px solid var(--border,#dce3ed);border-radius:10px}.backup-file small{display:block;color:var(--muted,#64748b)}.backup-schedule-list{display:grid;gap:7px}.backup-schedule{display:flex;justify-content:space-between;gap:12px;padding:10px;border-bottom:1px solid var(--border,#dce3ed)}@media(max-width:680px){.backup-file{grid-template-columns:1fr}.backup-history-card>summary,.backup-section-head{align-items:flex-start;display:grid}}</style>
<script>(()=>{const root=document.getElementById('backup-console-list'),refresh=document.getElementById('backup-refresh'),csrf=__CSRF__;const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const bytes=n=>{n=Number(n||0);for(const u of ['B','KB','MB','GB','TB']){if(n<1024)return `${n.toFixed(n<10&&u!=='B'?1:0)} ${u}`;n/=1024}return `${n.toFixed(1)} PB`};async function request(url,options={}){const r=await fetch(url,{credentials:'same-origin',...options});const type=(r.headers.get('content-type')||'').toLowerCase(),text=await r.text();if(!type.includes('application/json'))throw new Error(`Resposta inválida do serviço de backup (HTTP ${r.status})`);const d=JSON.parse(text);if(!r.ok||!d.ok)throw new Error(d.error||`HTTP ${r.status}`);return d}async function action(slug,op,extra={}){const body=new URLSearchParams({csrf_token:csrf,slug,op,...extra});await request('/cloudif/portal/action/project-backup',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8','X-CSRF-Token':csrf},body});await load()}function file(x,slug,historical=false){const url=historical?`/cloudiff/portal/download/backup-history?slug=${encodeURIComponent(slug)}&file=${encodeURIComponent(x.filename)}`:`/cloudif/portal/download/project-backup?slug=${encodeURIComponent(slug)}&file=${encodeURIComponent(x.filename)}`;return `<div class="backup-file"><div><strong>${x.type==='database'?'Banco de dados':'Aplicação e containers'}</strong><small>${esc(x.modified||'')} · ${bytes(x.size)}${x.sha256?` · SHA-256 ${esc(x.sha256.slice(0,12))}…`:''}</small></div><a class="btn light" href="${url}">Baixar</a></div>`}function activeCard(p){const c=p.settings||{},r=c.remote||{},items=p.items||[];return `<article class="backup-console-card"><div class="section-title"><div><h3>${esc(p.name||p.slug)}</h3><small>${esc(p.slug)}</small></div><span class="pill ${c.last_result?'ok':'muted'}">${c.last_result?'com execução':'sem execução'}</span></div><div class="backup-console-meta"><div><small>Automático local</small><strong>${c.enabled?'Ativado':'Desativado'}</strong></div><div><small>Última execução</small><strong>${esc(c.last_run||'Ainda não executado')}</strong></div><div><small>Retenção</small><strong>${Number(c.retention||14)} dias</strong></div><div><small>Servidor remoto</small><strong>${esc(r.status||'não configurado')}</strong></div><div><small>Arquivos</small><strong>${items.length}</strong></div></div>${p.can_manage?`<div class="backup-console-actions"><button class="btn" data-op="backup_now" data-slug="${esc(p.slug)}">Gerar backup agora</button><button class="btn light" data-op="set_auto" data-slug="${esc(p.slug)}" data-enabled="${c.enabled?'0':'1'}" data-remote="${c.remote_requested?'1':'0'}">${c.enabled?'Desativar automático':'Ativar automático'}</button><button class="btn light" data-op="set_remote" data-slug="${esc(p.slug)}" data-enabled="${c.enabled?'1':'0'}" data-remote="${c.remote_requested?'0':'1'}">${c.remote_requested?'Desativar sincronização':'Ativar sincronização'}</button></div>`:''}<div class="backup-file-list">${items.length?items.slice(0,8).map(x=>file(x,p.slug)).join(''):'<div class="empty-state">Nenhum arquivo disponível.</div>'}</div></article>`}function historyCard(p){return `<details class="backup-console-card backup-history-card"><summary><span><strong>${esc(p.slug)}</strong><small>${esc(p.owner||'proprietário não identificado')} · última cópia ${esc(p.last_backup||'—')}</small></span><span class="pill warn">Projeto removido · ${p.total_files} arquivos</span></summary><div class="backup-history-body"><div class="backup-console-meta"><div><small>Banco</small><strong>${p.database_files}</strong></div><div><small>Aplicação</small><strong>${p.application_files}</strong></div><div><small>Espaço preservado</small><strong>${bytes(p.total_size)}</strong></div><div><small>Retenção</small><strong>Preservado para revisão</strong></div></div><div class="backup-file-list">${p.items.map(x=>file(x,p.slug,true)).join('')}</div>${p.total_files>p.items.length?`<p class="small">Exibindo os ${p.items.length} arquivos mais recentes de ${p.total_files}.</p>`:''}</div></details>`}async function load(){refresh.disabled=true;root.innerHTML='<p>Consultando agenda e arquivos de backup…</p>';try{const d=await request('/cloudiff/portal/api/backup-overview',{headers:{Accept:'application/json'}}),r=d.remote||{},s=d.schedules||[],a=d.active||[],h=d.history||[];root.innerHTML=`<div class="backup-overview-grid"><div><small>Backup automático</small><strong>${s.some(x=>x.active==='active')?'Ativo':'Verificar serviço'}</strong></div><div><small>Servidor remoto</small><strong>${esc(r.status||'não configurado')}</strong>${r.host?`<small>${esc(r.host)}:${r.port}</small>`:''}</div><div><small>Retenção padrão</small><strong>${d.retention_days} dias</strong></div><div><small>Projetos históricos</small><strong>${d.history_total}</strong></div></div><section class="backup-section"><div class="backup-section-head"><div><h3>Agendamentos</h3><p class="small">Timers reais configurados no servidor.</p></div></div><div class="backup-console-card backup-schedule-list">${s.map(x=>`<div class="backup-schedule"><span><strong>${esc(x.label)}</strong><small>${esc(x.unit)}</small></span><span class="pill ${x.active==='active'?'ok':'warn'}">${esc(x.active)}${x.next?` · ${esc(x.next)}`:''}</span></div>`).join('')}</div></section><section class="backup-section"><div class="backup-section-head"><div><h3>Projetos ativos</h3><p class="small">Controles de geração, agenda e sincronização.</p></div><span class="pill">${a.length}</span></div><div class="backup-console-grid">${a.length?a.map(activeCard).join(''):'<div class="empty-state"><h3>Nenhum projeto ativo</h3><p>Novos projetos aparecerão aqui automaticamente.</p></div>'}</div></section><section class="backup-section"><div class="backup-section-head"><div><h3>Backups históricos</h3><p class="small">Arquivos preservados de projetos removidos. Somente leitura.</p></div><span class="pill warn">${h.length} projetos</span></div><div class="backup-console-grid">${h.length?h.map(historyCard).join(''):'<div class="empty-state">Nenhum backup histórico autorizado.</div>'}</div></section>`;root.querySelectorAll('[data-op]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{const op=b.dataset.op==='set_remote'?'set_auto':b.dataset.op;await action(b.dataset.slug,op,{enabled:b.dataset.enabled||'0',remote_requested:b.dataset.remote||'0'})}catch(e){alert(e.message)}finally{b.disabled=false}})}catch(e){root.innerHTML=`<p class="pill bad">${esc(e.message)}</p>`}finally{refresh.disabled=false}}refresh.onclick=load;load()})();</script>
""".replace('__CSRF__', json.dumps(csrf_token))


    def wrap(handler_class) -> None:
        if getattr(handler_class, "_v2_coexist_wrapped", False):
            return
        previous_get = handler_class.do_GET

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            try:
                if path in {"/cloudif/portal/api/admin-delete-project-status", "/cloudiff/portal/api/admin-delete-project-status"}:
                    owner = sys.modules.get(handler_class.__module__)
                    user = self.user()
                    allowed = bool(getattr(owner, "_admin_project_delete_global")(user))
                    if not allowed:
                        return send_json(self, 403, {"ok": False, "error": "forbidden"})
                    from cloudif_admin_project_delete import job_status
                    query = urllib.parse.parse_qs(parsed.query)
                    payload = job_status((query.get("job_id") or [""])[0])
                    return send_json(self, 200 if payload.get("ok") else 404, payload)
                if path in {"/cloudif/portal/api/admin-ad-search", "/cloudiff/portal/api/admin-ad-search"}:
                    if not tenant_admin_allowed(self):
                        return send_json(self, 403, {"ok": False, "error": "forbidden", "items": []})
                    query = urllib.parse.parse_qs(parsed.query)
                    q = (query.get("q") or [""])[0].strip()
                    stype = (query.get("type") or ["all"])[0].strip().lower()
                    if len(q) < 2:
                        return send_json(self, 200, {"ok": True, "query": q, "type": stype, "count": 0, "items": []})
                    try:
                        import cloudif_ad_directory_module as directory
                        user = directory.user_from_headers(self.headers)
                        payload = directory.search(q, stype, user=user, diagnostics=False)
                        payload["query"] = q
                        payload["type"] = stype
                        payload["count"] = len(payload.get("items") or [])
                        return send_json(self, 200, payload)
                    except Exception as exc:
                        return send_json(self, 500, {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:300], "items": []})
                if path in {"/cloudif/portal/api/admin-delete-tenant-preview", "/cloudiff/portal/api/admin-delete-tenant-preview"}:
                    if not tenant_admin_allowed(self):
                        return send_json(self, 403, {"ok": False, "error": "forbidden"})
                    from cloudif_admin_tenant_delete import preview
                    query = urllib.parse.parse_qs(parsed.query)
                    payload = preview((query.get("tenant") or [""])[0])
                    return send_json(self, 200, payload)
                if path in {"/cloudif/portal/api/admin-delete-tenant-status", "/cloudiff/portal/api/admin-delete-tenant-status"}:
                    if not tenant_admin_allowed(self):
                        return send_json(self, 403, {"ok": False, "error": "forbidden"})
                    from cloudif_admin_tenant_delete import job_status as tenant_job_status
                    query = urllib.parse.parse_qs(parsed.query)
                    payload = tenant_job_status((query.get("job_id") or [""])[0])
                    return send_json(self, 200 if payload.get("ok") else 404, payload)
                if path in {"/cloudif/portal/api/backup-overview", "/cloudiff/portal/api/backup-overview"}:
                    owner = sys.modules.get(handler_class.__module__)
                    user = self.user()
                    return send_json(self, 200, backup_inventory(owner, user))
                if path in {"/cloudif/portal/download/backup-history", "/cloudiff/portal/download/backup-history"}:
                    owner = sys.modules.get(handler_class.__module__)
                    user = self.user()
                    q = urllib.parse.parse_qs(parsed.query)
                    slug = (q.get("slug") or [""])[0].strip()
                    filename = (q.get("file") or [""])[0].strip()
                    if not re.fullmatch(r"[A-Za-z0-9_.-]+", slug or "") or filename != Path(filename).name or not filename.endswith(".tar.gz"):
                        return send_json(self, 400, {"ok": False, "error": "invalid_file"})
                    file_path = (BACKUP_ROOT / slug / filename).resolve()
                    root_path = (BACKUP_ROOT / slug).resolve()
                    if root_path not in file_path.parents or not file_path.is_file():
                        return send_json(self, 404, {"ok": False, "error": "not_found"})
                    items = _backup_items(slug)
                    item = next((x for x in items if x.get("filename") == filename), None)
                    groups = set(user.get("groups") or [])
                    global_access = bool(user.get("admin") or groups.intersection({"CloudIF-Tenants-Admin", "CloudIF-Professor", "cloudif-tenants-admin", "cloudif-professor"}))
                    if not item or (not global_access and (item.get("owner") or "").lower() != (user.get("username") or "").lower()):
                        return send_json(self, 403, {"ok": False, "error": "forbidden"})
                    self.send_response(200)
                    self.send_header("Content-Type", "application/gzip")
                    self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                    self.send_header("Content-Length", str(file_path.stat().st_size))
                    self.send_header("Cache-Control", "private, no-store")
                    self.end_headers()
                    with file_path.open("rb") as src:
                        while True:
                            chunk = src.read(1024 * 1024)
                            if not chunk: break
                            self.wfile.write(chunk)
                    try: getattr(owner, "log_action")(user.get("username") or "portal", "download_historical_backup", slug, 0, filename, "")
                    except Exception: pass
                    return
                if try_asset(self, path):
                    return

                query = urllib.parse.parse_qs(parsed.query)
                tab = (query.get("tab") or [""])[0]
                if path in PORTAL_PATHS and tab in {"resumo", "visao-geral", "visão-geral"}:
                    owner = sys.modules.get(handler_class.__module__)
                    body = '<section class="overview-canonical"><div class="section-title"><div><h1>Visão geral</h1><p>Projetos, bancos, perfil e infraestrutura autorizados para sua sessão.</p></div></div>' + getattr(owner, "render_resumo")(self.user()) + '</section>'
                    markup = render_legacy(identity(self.headers), "resumo", "Visão geral", body, "", "")
                    return send(self, 200, "text/html; charset=utf-8", markup.encode("utf-8"))
                if path in PORTAL_PATHS and tab == "publicacao" and not (query.get("project") or [""])[0].strip():
                    from portal.modules.overview import service as overview_service, views as overview_views
                    data = overview_service.overview_data(identity(self.headers))
                    body = overview_views.overview_body(data)
                    markup = render_legacy(identity(self.headers), "publicacao", "Publicações", body, "", "")
                    return send(self, 200, "text/html; charset=utf-8", markup.encode("utf-8"))
                if path in PORTAL_PATHS and tab == "admin-manutencao":
                    if not tenant_admin_allowed(self):
                        denied = render_legacy(identity(self.headers), tab, "Serviços globais", '<section class="card"><h1>Acesso negado</h1></section>', "", "")
                        return send(self, 403, "text/html; charset=utf-8", denied.encode("utf-8"))
                    owner = sys.modules.get(handler_class.__module__)
                    markup = render_legacy(identity(self.headers), tab, "Serviços globais", global_services_body(owner, self.user()), "", "")
                    return send(self, 200, "text/html; charset=utf-8", markup.encode("utf-8"))
                if path in PORTAL_PATHS and tab == "backup":
                    owner = sys.modules.get(handler_class.__module__); user = self.user(); markup = render_legacy(identity(self.headers), "backup", "Backup", backup_body(getattr(owner, "_prod_csrf_token")(user)), "", "")
                    return send(self, 200, "text/html; charset=utf-8", markup.encode("utf-8"))
                if path in PORTAL_PATHS and tab == "ajuda":
                    markup = render_legacy(identity(self.headers), "ajuda", "Guia da plataforma", help_body(), "", "")
                    return send(self, 200, "text/html; charset=utf-8", markup.encode("utf-8"))
                native_home = path in PORTAL_PATHS and tab in ("", "inicio", "início", "overview")
                match_path = "/cloudiff/portal" if path == "/" else path
                native_nonportal = (path, "GET") in NATIVE_READY and path not in PORTAL_PATHS
                if native_home or native_nonportal:
                    if registry.match(match_path, "GET") is None:
                        wire()
                    if registry.match(match_path, "GET") is not None:
                        request = request_for(self, "GET")
                        if path == "/":
                            request = dataclasses.replace(request, path=match_path)
                        response = handle(request, lambda _request: None)
                        if response is not None:
                            return send_response_object(self, response)

                if path in PORTAL_PATHS:
                    status, captured_headers, body = capture_legacy(self, previous_get)
                    content_type = header_value(captured_headers, "Content-Type", "text/html; charset=utf-8")
                    if status == 200 and content_type.lower().startswith("text/html"):
                        try:
                            markup = body.decode("utf-8")
                            selected_project = (query.get("project") or [""])[0]
                            owner = sys.modules.get(handler_class.__module__)
                            adapted_markup = transform(markup, identity(self.headers), tab or "publicacao", selected_project)
                            if tab == "admin" and tenant_admin_allowed(self):
                                from cloudif_admin_tenant_delete import render_panel
                                owner = sys.modules.get(handler_class.__module__)
                                user = self.user()
                                csrf_token = getattr(owner, "_prod_csrf_token")(user)
                                panel = render_panel(csrf_token, (query.get("tenant") or [""])[0])
                                adapted_markup = re.sub(
                                    r'<div class="grid2">\s*<div class="box">\s*<h3>Pesquisar usuário/grupo no AD</h3>.*?<h3>Parâmetros de política</h3>',
                                    '<h3>Parâmetros de política</h3>', adapted_markup, count=1, flags=re.DOTALL,
                                )
                                wizard = admin_wizard_body(owner, user, csrf_token, panel)
                                adapted_markup = adapted_markup.replace('<h3>Parâmetros de política</h3>', wizard + '<h3>Parâmetros de política</h3>', 1)
                            adapted = adapted_markup.encode("utf-8")
                            return send(self, 200, "text/html; charset=utf-8", adapted, captured_headers)
                        except Exception:
                            # Auto-recovery: return byte-identical legacy output.
                            return send(self, status, content_type, body, captured_headers)
                    return send(self, status, content_type, body, captured_headers)
            except Exception:
                # Fail-open before capture: the original handler still owns the request.
                return previous_get(self)
            return previous_get(self)

        handler_class.do_GET = do_GET

        previous_post = getattr(handler_class, "do_POST", None)
        if previous_post is not None:
            def do_POST(self):
                parsed = urllib.parse.urlparse(self.path)
                query_action = (urllib.parse.parse_qs(parsed.query).get("action") or [""])[0].strip()
                query_routed = parsed.path in PORTAL_PATHS and query_action in {
                    "admin-delete-project", "admin-delete-tenant", "admin-tenant-advanced"
                }
                if not query_routed and parsed.path not in {
                    "/cloudif/portal/action/admin-delete-project",
                    "/cloudiff/portal/action/admin-delete-project",
                    "/cloudif/portal/action/admin-delete-tenant",
                    "/cloudiff/portal/action/admin-delete-tenant",
                    "/cloudif/portal/action/admin-tenant-advanced",
                    "/cloudiff/portal/action/admin-tenant-advanced",
                }:
                    return previous_post(self)
                content_length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(content_length)
                form = urllib.parse.parse_qs(raw.decode("utf-8", "ignore"))
                value = lambda key: (form.get(key) or [""])[0].strip()
                if parsed.path.endswith("/action/admin-tenant-advanced") or query_action == "admin-tenant-advanced":
                    try:
                        if not tenant_admin_allowed(self):
                            return send_json(self, 403, {"ok": False, "error": "forbidden"})
                        owner = sys.modules.get(handler_class.__module__)
                        user = self.user()
                        token_ok = getattr(owner, "_prod_csrf_equal")(
                            value("csrf_token"), getattr(owner, "_prod_csrf_token")(user)
                        )
                        if not token_ok:
                            return send_json(self, 403, {"ok": False, "error": "invalid_csrf"})
                        tenant = getattr(owner, "slugify")(value("tenant"))
                        op = value("op")
                        labels = {"sync_roles": "Sync roles", "render_router": "Render router", "ensure": "Ensure/restore"}
                        if not tenant or op not in labels:
                            return send_json(self, 400, {"ok": False, "error": "invalid_operation"})
                        if op == "sync_roles":
                            command = ["bash", "-lc", f"/srv/cloudif/bin/cloudif-sync-db-passwords.sh {tenant!r}"]
                            timeout = 240
                        elif op == "render_router":
                            command = ["bash", "-lc", "/srv/cloudif/bin/cloudif-render-router-sso.sh"]
                            timeout = 240
                        else:
                            command = ["bash", "-lc", f"/usr/local/sbin/cloudif-tenant-ensure-bg.sh {tenant!r} restore {(user.get('username') or 'admin')!r}"]
                            timeout = 30
                        rc, out, err = getattr(owner, "run")(command, timeout)
                        getattr(owner, "log_action")(user.get("username") or "admin", f"admin_{op}", tenant, rc, out, err)
                        payload = {"ok": rc == 0, "tenant": tenant, "operation": op, "label": labels[op], "rc": rc, "stdout": (out or "")[-4000:], "stderr": (err or "")[-2000:]}
                        return send_json(self, 200 if rc == 0 else 422, payload)
                    except Exception as exc:
                        return send_json(self, 500, {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:300]})
                if parsed.path.endswith("/action/admin-delete-tenant") or query_action == "admin-delete-tenant":
                    try:
                        if not tenant_admin_allowed(self):
                            return send_json(self, 403, {"ok": False, "error": "forbidden"})
                        owner = sys.modules.get(handler_class.__module__)
                        user = self.user()
                        token_ok = getattr(owner, "_prod_csrf_equal")(
                            value("csrf_token"), getattr(owner, "_prod_csrf_token")(user)
                        )
                        if not token_ok:
                            return send_json(self, 403, {"ok": False, "error": "invalid_csrf"})
                        from cloudif_admin_tenant_delete import start_job as start_tenant_job
                        job = start_tenant_job(value("tenant"), value("confirmation"), user.get("username") or "admin")
                        return send_json(self, 202 if job.get("ok") else 409, job)
                    except Exception as exc:
                        return send_json(self, 500, {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:300]})
                if value("async") == "1":
                    try:
                        owner = sys.modules.get(handler_class.__module__)
                        user = self.user()
                        if not getattr(owner, "_admin_project_delete_global")(user):
                            return send_json(self, 403, {"ok": False, "error": "forbidden"})
                        token_ok = getattr(owner, "_prod_csrf_equal")(
                            value("csrf_token"), getattr(owner, "_prod_csrf_token")(user)
                        )
                        if not token_ok:
                            return send_json(self, 403, {"ok": False, "error": "invalid_csrf"})
                        from cloudif_admin_project_delete import start_job
                        job = start_job(value("slug"), value("confirm_text"), user.get("username") or "admin")
                        return send_json(self, 202, job)
                    except Exception as exc:
                        return send_json(self, 500, {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:300]})
                self.rfile = BytesIO(raw)
                try:
                    status, captured_headers, body = capture_legacy(self, previous_post)
                    content_type = header_value(captured_headers, "Content-Type", "text/html; charset=utf-8")
                    if status in {200, 409} and content_type.lower().startswith("text/html"):
                        try:
                            adapted = transform(
                                body.decode("utf-8"),
                                identity(self.headers),
                                "admin-excluir-projeto",
                            ).encode("utf-8")
                            return send(self, status, "text/html; charset=utf-8", adapted, captured_headers)
                        except Exception:
                            return send(self, status, content_type, body, captured_headers)
                    return send(self, status, content_type, body, captured_headers)
                except Exception:
                    self.rfile = BytesIO(raw)
                    return previous_post(self)

            handler_class.do_POST = do_POST

        handler_class._v2_coexist_wrapped = True

    import http.server as http_server

    if not getattr(http_server, "_v2_server_hooked", False):
        original_server = http_server.ThreadingHTTPServer

        class V2Server(original_server):
            def __init__(self, address, handler, *args, **kwargs):
                try:
                    wrap(handler)
                except Exception:
                    pass
                super().__init__(address, handler, *args, **kwargs)

        http_server.ThreadingHTTPServer = V2Server
        http_server._v2_server_hooked = True


try:
    _install()
except Exception:
    pass
