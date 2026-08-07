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
import sqlite3
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
    from cloudif_multiservice_preview_portal import handle_preview_request

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
    <button type="button" role="tab" aria-selected="true" aria-controls="admin-step-tenant" id="admin-tab-tenant" data-admin-step="tenant"><span>1</span><strong>Ações avançadas</strong><small>Sync roles e restore</small></button>
    <button type="button" role="tab" aria-selected="false" aria-controls="admin-step-delete" id="admin-tab-delete" data-admin-step="delete"><span>2</span><strong>Remover banco</strong><small>Prévia, backup e exclusão</small></button>
    <button type="button" role="tab" aria-selected="false" aria-controls="admin-step-ad" id="admin-tab-ad" data-admin-step="ad"><span>3</span><strong>Consultar usuários</strong><small>Pesquisa interativa no AD</small></button>
  </div>
  <div class="admin-wizard-panels">
    <section id="admin-step-tenant" class="admin-wizard-panel active" role="tabpanel" aria-labelledby="admin-tab-tenant">
      <div class="admin-panel-heading"><div><span>Etapa 1</span><h3>Ações avançadas do tenant</h3></div><p>Sincronize papéis ou valide e restaure a estrutura operacional do tenant.</p></div>
      <form method="post" action="/cloudiff/portal/" class="admin-tenant-actions" id="admin-tenant-actions">
        <input type="hidden" name="csrf_token" value="{html.escape(csrf_token)}">
        <label>Tenant<select name="tenant" required><option value="">Selecione</option>{options}</select></label>
        <div class="admin-action-cards">
          <button class="admin-action-card" name="op" value="sync_roles"><span>Sync roles</span><small>Sincroniza usuários, papéis e credenciais do banco.</small></button>
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
.admin-operation-center{{--c-primary:#8fb8e8;--c-primary-hover:#6f9fd6;--c-primary-soft:#edf6ff;--c-primary-border:#b7d5f5;--c-accent:#8fb8e8;--c-accent-soft:#edf6ff;display:grid;gap:18px;margin:18px 0 24px!important;overflow:hidden;background:#fff!important;border-color:#cfe3f8!important;color:#111111!important}}.admin-operation-center .btn:not(.danger):not(.red),.admin-operation-center button:not(.danger):not(.red){{--c-primary:#8fb8e8;--c-primary-hover:#6f9fd6}}.admin-eyebrow{{display:block;margin-bottom:5px;font-size:.72rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:#111}}.admin-wizard-tabs{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}}.admin-wizard-tabs button{{display:grid;grid-template-columns:34px 1fr;gap:2px 10px;align-items:center;min-height:82px;padding:13px;border:1px solid var(--c-border,#dce3ed);border-radius:12px;background:#fff;color:#111!important;text-align:left;box-shadow:none!important}}.admin-wizard-tabs button>span{{grid-row:1/3;width:32px;height:32px;display:grid;place-items:center;border-radius:10px;background:#d7eaff;color:#111;font-weight:850}}.admin-wizard-tabs button strong{{font-size:.9rem}}.admin-wizard-tabs button small{{color:#111!important;line-height:1.25}}.admin-wizard-tabs button[aria-selected="true"]{{border-color:#b7d5f5;background:#edf6ff;color:#111}}.admin-wizard-tabs button[aria-selected="true"]>span{{background:#b7d5f5;color:#111}}.admin-wizard-panels{{border:1px solid #cfe3f8;border-radius:14px;background:#fff;overflow:hidden}}.admin-wizard-panel{{display:none;padding:20px;background:#fff;color:#111111}}.admin-wizard-panel.active{{display:grid;gap:16px}}.admin-panel-heading{{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}}.admin-panel-heading span{{font-size:.72rem;font-weight:850;text-transform:uppercase;color:#111}}.admin-panel-heading h3,.admin-panel-heading p{{margin:3px 0 0}}.admin-panel-heading p{{max-width:580px;color:#111!important}}.admin-tenant-actions{{display:grid;gap:14px}}.admin-tenant-actions>label{{display:grid;gap:6px;max-width:520px}}.admin-action-cards{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.admin-action-card{{display:grid;gap:5px;min-height:112px;padding:16px!important;border:1px solid var(--c-border,#dce3ed)!important;border-radius:12px!important;background:#fff!important;color:#111!important;text-align:left!important}}.admin-action-card:hover{{border-color:#b7d5f5!important;background:#f5faff!important}}.admin-action-card span{{font-weight:850}}.admin-action-card small{{color:#111!important;line-height:1.4}}.admin-action-status{{padding:13px 14px;border:1px solid var(--c-border,#dce3ed);border-radius:10px;background:#fff;color:#111111;white-space:pre-wrap}}.admin-action-status.running{{border-color:#b7d5f5;background:#edf6ff;color:#111}}.admin-action-status.ok{{border-color:#a9ccef;background:#f2f8ff;color:#111111}}.admin-action-status.bad{{border-color:#fecaca;background:#fef2f2;color:#111}}.admin-wizard-panel .admin-ad-console,.admin-wizard-panel .tenant-delete-tool{{display:grid;gap:16px;min-width:0}}.admin-wizard-panel .admin-ad-console>.section-title,.admin-wizard-panel .tenant-delete-tool>.section-title{{padding-bottom:12px;border-bottom:1px solid var(--c-border,#dce3ed)}}@media(max-width:860px){{.admin-wizard-tabs,.admin-action-cards{{grid-template-columns:1fr}}.admin-wizard-tabs button{{min-height:68px}}.admin-panel-heading{{display:grid}}}}
</style>
<script>(()=>{{const tabs=[...document.querySelectorAll('[data-admin-step]')],panels=[...document.querySelectorAll('.admin-wizard-panel')];if(!tabs.length)return;function open(name,focus=false){{tabs.forEach(tab=>{{const active=tab.dataset.adminStep===name;tab.setAttribute('aria-selected',active?'true':'false');tab.tabIndex=active?0:-1;if(active&&focus)tab.focus()}});panels.forEach(panel=>{{const active=panel.id===`admin-step-${{name}}`;panel.hidden=!active;panel.classList.toggle('active',active)}})}}tabs.forEach((tab,index)=>{{tab.onclick=()=>open(tab.dataset.adminStep);tab.onkeydown=e=>{{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();let target=index;if(e.key==='ArrowRight')target=(index+1)%tabs.length;if(e.key==='ArrowLeft')target=(index-1+tabs.length)%tabs.length;if(e.key==='Home')target=0;if(e.key==='End')target=tabs.length-1;open(tabs[target].dataset.adminStep,true)}}}});const form=document.getElementById('admin-tenant-actions'),status=document.getElementById('admin-tenant-action-status');if(form)form.addEventListener('submit',async e=>{{e.preventDefault();const submitter=e.submitter;if(!submitter)return;const fd=new FormData(form),tenant=String(fd.get('tenant')||'').trim(),op=String(submitter.value||'');if(!tenant){{status.className='admin-action-status bad';status.textContent='Selecione um tenant.';return}}const csrf=String(fd.get('csrf_token')||'');const body=new URLSearchParams({{tenant,op,csrf_token:csrf}});form.querySelectorAll('button').forEach(b=>b.disabled=true);status.className='admin-action-status running';status.textContent='Executando '+submitter.querySelector('span').textContent+' em '+tenant+'…';try{{const r=await fetch(form.action,{{method:'POST',credentials:'same-origin',headers:{{Accept:'application/json','Content-Type':'application/x-www-form-urlencoded;charset=UTF-8','X-CSRF-Token':csrf,'X-CloudIF-Action':'admin-tenant-advanced'}},body}});if(r.type==='opaqueredirect'||r.status===0)throw new Error('A sessão do Portal expirou. Atualize a página e tente novamente.');const type=(r.headers.get('content-type')||'').toLowerCase();const text=await r.text();if(!type.includes('application/json'))throw new Error('A operação não chegou ao serviço administrativo. Atualize a página e tente novamente.');const data=JSON.parse(text);if(!r.ok||!data.ok)throw new Error(data.error||data.stderr||('HTTP '+r.status));status.className='admin-action-status ok';status.textContent='Concluído: '+data.label+'\\n'+(data.stdout||data.message||'Operação executada com sucesso.')}}catch(err){{status.className='admin-action-status bad';status.textContent='Falha: '+err.message}}finally{{form.querySelectorAll('button').forEach(b=>b.disabled=false)}}}});open('tenant') }})();</script>'''

    def _backup_remote_env_values() -> dict:
        env={}
        try:
            for raw in BACKUP_REMOTE_ENV.read_text().splitlines():
                line=raw.strip()
                if line and not line.startswith('#') and '=' in line:
                    k,v=line.split('=',1);env[k.strip()]=v.strip().strip('"\'')
        except Exception:
            pass
        return {
            'enabled': env.get('REMOTE_ENABLED','1') == '1',
            'host': env.get('REMOTE_HOST','10.68.128.250'),
            'port': int(env.get('REMOTE_PORT') or 22),
            'user': env.get('REMOTE_USER','cloudifbackup'),
            'path': env.get('REMOTE_PATH','.'),
            'key': env.get('REMOTE_KEY','/etc/cloudif/backup_ed25519'),
        }

    def _backup_remote_admin_card(owner, user: dict) -> str:
        if not user.get('admin'):
            return ''
        cfg=_backup_remote_env_values(); status=_backup_remote_status(); token=getattr(owner,'_prod_csrf_token')(user)
        badge='ok' if status.get('reachable') else 'bad'; state='online' if status.get('reachable') else 'offline'; checked=' checked' if cfg['enabled'] else ''
        return f"""<section class="global-admin-section backup-remote-admin"><div class="section-title"><div><h2>Servidor remoto de backup</h2><p>Configuração global usada pelos backups de projetos e da plataforma.</p></div><span class="pill {badge}">{state}</span></div><form method="post" action="/cloudiff/portal/" id="backup-remote-config-form" class="backup-remote-config-form"><input type="hidden" name="csrf_token" value="{html.escape(token)}"><input type="hidden" name="op" value="backup_remote_config"><label class="backup-toggle"><input type="checkbox" name="remote_enabled" value="1"{checked}><span>Sincronização remota habilitada</span></label><div class="backup-remote-fields"><label>Servidor ou IP<input name="remote_host" required value="{html.escape(str(cfg['host']))}" placeholder="10.68.128.250"></label><label>Porta SSH<input name="remote_port" type="number" min="1" max="65535" required value="{cfg['port']}"></label><label>Usuário SSH<input name="remote_user" required value="{html.escape(str(cfg['user']))}"></label><label>Caminho remoto<input name="remote_path" required value="{html.escape(str(cfg['path']))}" placeholder="."></label><label class="backup-key-field">Chave privada<input name="remote_key" required value="{html.escape(str(cfg['key']))}"></label></div><div class="global-resource-actions"><button class="btn" type="submit">Testar e salvar</button><span id="backup-remote-config-status" class="small">Conectividade atual: {html.escape(str(status.get('host') or cfg['host']))}:{status.get('port') or cfg['port']} - {state}</span></div></form></section><script>(()=>{{const f=document.getElementById('backup-remote-config-form'),s=document.getElementById('backup-remote-config-status');if(!f)return;f.addEventListener('submit',async e=>{{e.preventDefault();const fd=new FormData(f),csrf=String(fd.get('csrf_token')||'');s.textContent='Testando e salvando...';try{{const r=await fetch(f.action,{{method:'POST',credentials:'same-origin',headers:{{Accept:'application/json','X-CSRF-Token':csrf,'X-CloudIF-Action':'backup-remote-config'}},body:fd}});const d=await r.json();if(!r.ok||!d.ok)throw new Error(d.detail||d.error||('HTTP '+r.status));s.textContent='Salvo. '+d.host+':'+d.port+' está '+(d.reachable?'online':'offline')+'.';s.className='small '+(d.reachable?'ok':'bad')}}catch(err){{s.textContent='Falha: '+err.message;s.className='small bad'}}}})}})();</script>"""

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
            + _backup_remote_admin_card(owner, user) +
            f'<section class="global-admin-section"><div class="section-title"><div><h2>Containers e stacks</h2><p>Projetos visíveis e seus vínculos no Komodo.</p></div><span class="pill">{len(container_cards)}</span></div><div class="global-resource-grid">{"".join(container_cards) or "<div class=\"empty-state\">Nenhum container de projeto registrado.</div>"}</div></section>'
            f'<section class="global-admin-section"><div class="section-title"><div><h2>Repositórios por usuário</h2><p>Repositórios Forgejo vinculados aos projetos autorizados.</p></div><span class="pill">{len(repo_cards)}</span></div><div class="global-resource-grid">{"".join(repo_cards) or "<div class=\"empty-state\">Nenhum repositório vinculado.</div>"}</div></section>'
            f'<section class="global-admin-section"><div class="section-title"><div><h2>Tenants Supabase</h2><p>Abra um tenant para conferir os serviços que compõem o banco.</p></div><span class="pill">{len(tenant_cards)}</span></div><div class="global-tenant-list">{"".join(tenant_cards) or "<div class=\"empty-state\">Nenhum tenant provisionado.</div>"}</div></section>'
            '</section>'
            '<style>.global-admin-hub{display:grid;gap:20px}.global-admin-hero{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:24px;border:1px solid #cfe5d5;border-radius:18px;background:#fff}.global-admin-hero h1{margin:4px 0 7px}.global-admin-hero p{margin:0;color:var(--muted)}.global-admin-kicker,.global-resource-type{font-size:.7rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:#176b35}.global-admin-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.global-admin-summary article{padding:16px;border:1px solid var(--border);border-radius:13px;background:#fff}.global-admin-summary small{display:block;color:var(--muted)}.global-admin-summary strong{font-size:1.8rem}.global-admin-shortcuts{display:flex;gap:8px;flex-wrap:wrap}.global-admin-section{display:grid;gap:13px}.global-resource-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:10px}.global-resource{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:16px;border:1px solid var(--border);border-radius:13px;background:#fff}.global-resource h3,.global-resource p{margin:3px 0}.global-resource p{color:var(--muted)}.global-resource-actions{display:flex;gap:8px;flex-wrap:wrap}.global-tenant-list{display:grid;gap:9px}.global-tenant{border:1px solid var(--border);border-radius:13px;background:#fff;overflow:hidden}.global-tenant>summary{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:15px;cursor:pointer;list-style:none}.global-tenant>summary::-webkit-details-marker{display:none}.global-tenant>summary span:first-child{display:grid;gap:3px}.global-tenant>summary small{color:var(--muted)}.global-tenant-body{display:grid;gap:13px;padding:15px;border-top:1px solid var(--border);background:#f8fafc}.global-tenant-body ul{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:7px;margin:0;padding:0;list-style:none}.global-tenant-body li{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px;border-radius:9px;background:#fff}.backup-remote-config-form{display:grid;gap:14px;padding:18px;border:1px solid var(--border);border-radius:13px;background:#fff}.backup-remote-fields{display:grid;grid-template-columns:2fr .7fr 1fr 1.5fr;gap:10px}.backup-remote-fields label,.backup-key-field,.backup-toggle{display:grid;gap:6px}.backup-key-field{grid-column:1/-1}.backup-toggle{display:flex;align-items:center;gap:8px}.backup-toggle input{min-height:auto!important;width:auto}@media(max-width:900px){.backup-remote-fields{grid-template-columns:1fr 1fr}}@media(max-width:760px){.backup-remote-fields{grid-template-columns:1fr}.global-admin-summary{grid-template-columns:repeat(2,1fr)}.global-admin-hero,.global-resource{align-items:flex-start;display:grid}}</style>'
        )

    def help_body() -> str:
        return r"""
<section class="card platform-guide">
  <div class="section-title"><div><h1>Guia da plataforma</h1><p>Como usar cada área operacional da CloudIFF.</p></div><span class="pill ok">Ambiente real</span></div>
  <section class="guide-videos" aria-labelledby="guide-videos-title"><div class="section-title"><div><span class="guide-repository-kicker">Tutoriais em vídeo</span><h2 id="guide-videos-title">Vídeos rápidos</h2><p>Apresentações curtas para conhecer a plataforma e acompanhar o fluxo de uso.</p></div></div><div class="guide-video-grid"><article><h3>Apresentação rápida da CloudIFF</h3><p>Visão breve da plataforma, seus recursos e a experiência de uso.</p><a class="btn" href="https://youtu.be/cxH3K8s1R9M" target="_blank" rel="noopener noreferrer">Assistir no YouTube</a></article><article><h3>Demonstração prática da plataforma</h3><p>Vídeo curto mostrando o uso da CloudIFF e o fluxo de trabalho.</p><a class="btn" href="https://youtu.be/pJ7mx3VZuWU" target="_blank" rel="noopener noreferrer">Assistir no YouTube</a></article></div></section>
  <article class="guide-repository"><div><span class="guide-repository-kicker">Código e documentação</span><h2>GitHub e manual técnico</h2><p>O repositório documenta arquitetura, fluxogramas, agentes e funções, protocolos de reconciliação, modelo de dados, runtime unificado, serviços, rotas e a finalidade de cada pasta e arquivo.</p></div><a class="btn" href="https://github.com/debianlima/cloudiff" target="_blank" rel="noopener noreferrer">Abrir GitHub do projeto</a></article>
  <nav class="guide-index" aria-label="Seções do guia"><a href="#guia-runtime">Código e runtime</a><a href="#guia-publicacoes">Publicações</a><a href="#guia-projetos">Projetos</a><a href="#guia-bancos">Bancos</a><a href="#guia-backup">Backup</a><a href="#guia-conexoes">Conexões externas</a><a href="#guia-conectores">Conectores</a><a href="#guia-ad">Administração</a><a href="#guia-grupos">Grupos</a><a href="#guia-membros">Membros e acessos</a><a href="#guia-regras">Regras</a></nav>
  <div class="guide-grid">
    <article id="guia-runtime"><span>00</span><h2>Ambiente do projeto</h2><p>Todo projeto novo recebe Apache, PHP e Node.js em runtimes isolados. A raiz do repositório é a raiz da aplicação publicada.</p><ul><li><strong>PHP:</strong> <code>index.php</code> e demais arquivos da raiz são interpretados pelo Apache.</li><li><strong>Node:</strong> APIs ficam em <code>api/</code> e são publicadas em <code>/api/</code>.</li><li><strong>HTTPS:</strong> portas públicas 80 e 443 ficam no proxy; os containers atendem internamente na porta 80.</li><li><strong>Infraestrutura:</strong> Compose, Dockerfile, Apache, Supervisor, healthcheck e metadados são gerados fora do Git.</li><li><strong>Tema:</strong> o botão Tema no cabeçalho alterna entre Claro, Escuro e Sistema e salva a preferência no navegador.</li></ul><p>O repositório contém somente código-fonte e documentação do projeto. Cada publicação <code>d1</code>, <code>d2</code> e seguintes recebe stack, imagem, container e terminal próprios.</p></article>
    <article id="guia-publicacoes"><span>01</span><h2>Publicações independentes</h2><p>Cada versão <code>d1</code>, <code>d2</code> e seguinte possui stack, imagem, container e terminais próprios. Ativar uma versão troca somente o alias estável depois do healthcheck.</p><h3>Conclusão real do provisionamento</h3><p>O job permanece em execução até os serviços críticos do tenant, o certificado e a rota HTTPS, a política inicial de disponibilidade, a política de backup, os timers automáticos, o container da <code>d1</code>, o terminal e as duas URLs públicas estarem prontos. Um container apenas criado ainda não é considerado concluído.</p><ol><li>A página padrão da <code>d1</code> ensina Git HTTPS no Linux e Windows, publicação pelo Portal e Supabase em aplicações desktop por SDK ou REST HTTPS.</li><li>Publique um commit para criar uma nova <code>dN</code>.</li><li>Teste a URL versionada antes de ativar.</li><li>Ao ativar, a plataforma reconstrói o runtime ausente e só promove uma versão saudável.</li><li>Use rollback para retornar ao container da versão anterior.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=publicacao">Abrir Publicações</a></article>
    <article id="guia-projetos"><span>02</span><h2>Projetos</h2><p>Crie projetos pelo wizard. O Forgejo recebe somente o código-fonte da aplicação, com a antiga pasta <code>site/</code> transformada na raiz do repositório.</p><ol><li>Informe nome e finalidade.</li><li>Escolha banco existente, novo ou sem banco.</li><li>Escolha as versões de Node.js e PHP; Apache é fixo.</li><li>A plataforma cria a publicação inicial <code>d1</code> em container próprio.</li><li>Compose, Dockerfile, healthcheck e configurações ficam fora do Git.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=projetos">Abrir Projetos</a></article>
    <article id="guia-bancos"><span>03</span><h2>Bancos e tenants</h2><p>Consulte disponibilidade, serviços e permissões. Banco é independente de projeto e pode ser compartilhado.</p><ol><li>Ao criar um tenant, escolha o tempo inicial ligado; o prazo começa somente depois da prontidão do banco e do HTTPS.</li><li>Use Iniciar/Parar somente para operação do tenant.</li><li>Abra o Studio pelo endereço exibido.</li><li>Adicionar ou remover uma pessoa dispara a reconciliação do acesso ao tenant.</li><li>Exclua banco apenas em Administração, após remover vínculos de projetos.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=bancos">Abrir Bancos</a></article>
    <article id="guia-backup"><span>04</span><h2>Backup</h2><p>Consulte backups de aplicação e dumps lógicos. A exclusão de projeto não apaga o banco nem seus backups.</p><ol><li>O provisionamento cria e relê a política automática do projeto antes de concluir.</li><li>Os timers de projeto e banco precisam estar habilitados e ativos.</li><li>Confira data, tamanho e hash.</li><li>Gere backup antes de mudanças sensíveis.</li><li>Na exclusão de tenant, o dump final é obrigatório.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=backup">Abrir Backup</a></article>
    <article id="guia-conexoes" class="guide-connections"><span>05</span><h2>Conectar aplicações e ferramentas</h2><p class="guide-connections-intro">Use somente as opções abaixo para acesso externo. Todas funcionam pelos endereços HTTPS publicados pela CloudIFF.</p><div class="guide-connection-layout"><section class="guide-connection-options" aria-label="Opções disponíveis"><div class="guide-connection-item"><h3>Supabase</h3><p>Use com <code>supabase-js</code>, aplicações web e mobile, REST/PostgREST, Auth, Storage, Realtime, Edge Functions e Supabase Studio.</p><code class="guide-connection-url">https://&lt;tenant&gt;.cloudiff.duckdns.org</code></div><div class="guide-connection-item"><h3>Forgejo por HTTPS</h3><p>Use com Git CLI, VS Code e IDEs para clone, pull e push autenticados.</p><code class="guide-connection-url">https://cloudiff.duckdns.org/git/&lt;usuario&gt;/cloudif-&lt;projeto&gt;.git</code></div><div class="guide-connection-item"><h3>Komodo por HTTPS</h3><p>Use para acessar o painel web e as integrações HTTPS autorizadas.</p><code class="guide-connection-url">https://komodoiff.duckdns.org/</code></div><div class="guide-connection-item"><h3>MCP por HTTPS</h3><p>Use com Claude, Claude Code, ChatGPT e outros clientes MCP HTTP autorizados.</p><code class="guide-connection-url">https://cloudiff.duckdns.org/cloudiff/mcp</code></div></section><aside class="guide-connection-project" aria-label="Conexões do Laboratório de Hardware"><span class="guide-repository-kicker">Exemplo provisionado</span><h3>Laboratório de Hardware</h3><dl><div><dt>Supabase</dt><dd><code>https://iff1742962-laboratoriodehardware.cloudiff.duckdns.org</code></dd></div><div><dt>Forgejo HTTPS</dt><dd><code>https://cloudiff.duckdns.org/git/iff1742962/cloudif-laboratorio-de-hardware.git</code></dd></div><div><dt>Komodo</dt><dd><code>https://komodoiff.duckdns.org/</code></dd></div><div><dt>MCP</dt><dd><code>https://cloudiff.duckdns.org/cloudiff/mcp</code></dd></div></dl><p class="guide-connection-note"><strong>Outras formas de conexão:</strong> verifique com a TI a compatibilidade e a liberação necessária.</p><p class="guide-connection-warning">Não publique senhas ou tokens.</p></aside></div></article>
    <article id="guia-conectores"><span>06</span><h2>Conectores</h2><p>Gere credenciais e consulte ferramentas disponíveis para clientes, agentes e integrações MCP autorizadas.</p><ol><li>Escolha o projeto autorizado.</li><li>Gere ou rotacione o token.</li><li>Copie a configuração mostrada pela plataforma.</li><li>Nunca compartilhe o token em repositório ou mensagem.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=agentes">Abrir Conectores</a></article>
    <article id="guia-ad"><span>07</span><h2>Administração</h2><p>Área restrita. Administração do AD localiza usuários e grupos reais; Serviços globais abre Forgejo, Komodo e tenants; exclusões possuem wizard e auditoria.</p><ol><li>Pesquise o principal no AD e selecione a sugestão.</li><li>Use ações avançadas somente no tenant correto.</li><li>Leia a prévia antes de confirmar uma exclusão.</li><li>Reporte a etapa e a mensagem exibidas quando houver falha.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=admin">Abrir Administração</a></article>
    <article id="guia-grupos"><span>08</span><h2>Grupos e permissões</h2><p>O acesso vem dos grupos entregues pelo Authentik e das ACLs de cada projeto.</p><ul><li><strong>CloudIF-Aluno:</strong> consulta recursos autorizados.</li><li><strong>CloudIF-Professor:</strong> cria, administra e exclui projetos autorizados.</li><li><strong>CloudIF-Tenants-Admin:</strong> administra AD, tenants, serviços globais e exclusões.</li></ul><p>Adicionar alguém a um grupo não substitui a ACL específica quando o projeto exige autorização individual.</p></article>
    <article id="guia-membros"><span>09</span><h2>Membros e reconciliação de acessos</h2><p>Qualquer inclusão ou remoção em um projeto ou banco gera um evento de reconciliação. O worker reaplica o estado completo para evitar permissões parciais ou recursos órfãos.</p><ul><li><strong>Projeto:</strong> colaboradores do Forgejo, permissões do Komodo, terminais das publicações e integrações MCP.</li><li><strong>Banco:</strong> listas de acesso e permissões do tenant Supabase.</li><li><strong>Remoção:</strong> elimina somente os recursos individuais gerenciados pela CloudIFF e preserva o proprietário.</li><li><strong>Fila:</strong> se um serviço estiver indisponível, a alteração permanece registrada e é tentada novamente até convergir.</li></ul></article>
    <article id="guia-regras"><span>10</span><h2>Regras de negócio</h2><ul><li>Projeto e banco possuem ciclos de vida independentes.</li><li>Excluir projeto nunca apaga banco ou backup de banco.</li><li>Tenant vinculado a projeto não pode ser excluído.</li><li>Exclusões exigem confirmação textual e geram auditoria.</li><li>Tokens são exibidos uma única vez após rotação.</li><li>Produção e ações sensíveis exigem as aprovações configuradas.</li><li>Recursos não disponíveis devem aparecer como indisponíveis, nunca como simulados.</li></ul></article>
  </div>
  <div class="help"><strong>Perfis:</strong> Aluno visualiza apenas recursos autorizados. Professor administra projetos e serviços globais permitidos. Administrador de tenants também opera AD e bancos.</div>
</section>
<style>.platform-guide{display:grid;gap:20px}.guide-videos{display:grid;gap:14px}.guide-video-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.guide-video-grid article{display:grid;align-content:start;gap:10px;padding:18px;border:1px solid var(--ui141-border,var(--cif-border,#dce3ed));border-radius:14px;background:var(--ui141-surface,var(--cif-surface,#fff))}.guide-video-grid h3,.guide-video-grid p{margin:0}.guide-video-grid p{color:var(--muted,#64748b)}.guide-video-grid .btn{justify-self:start}.guide-repository{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:20px;border:1px solid var(--ui141-border,var(--cif-border,#dce3ed));border-radius:14px;background:var(--ui141-surface,var(--cif-surface,#fff))}.guide-repository h2,.guide-repository p{margin:4px 0}.guide-repository p{max-width:820px;color:var(--muted,#64748b)}.guide-repository-kicker{font-size:.72rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:#176b35}.guide-index{display:flex;flex-wrap:wrap;gap:8px}.guide-index a{padding:8px 11px;border:1px solid var(--ui141-border,var(--cif-border,#dce3ed));border-radius:999px;text-decoration:none}.guide-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px}.guide-grid>article{grid-column:span 4;display:grid;align-content:start;gap:10px;min-width:0;padding:18px;border:1px solid var(--ui141-border,var(--cif-border,#dce3ed));border-radius:14px;background:var(--ui141-surface,var(--cif-surface,#fff))}.guide-grid>article>span{font-size:.75rem;font-weight:800;color:#176b35}.guide-grid h2,.guide-grid p{margin:0}.guide-grid ol{margin:0;padding-left:20px;display:grid;gap:6px}.guide-grid .btn{justify-self:start}#guia-bancos,#guia-backup{grid-column:span 6}#guia-conexoes,#guia-membros,#guia-regras{grid-column:1/-1}.guide-connections-intro{max-width:760px}.guide-connection-layout{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(320px,.85fr);gap:22px;align-items:start;margin-top:4px}.guide-connection-options{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 20px;min-width:0}.guide-connection-item{display:grid;align-content:start;gap:7px;min-width:0;padding:15px 0;border-top:1px solid var(--ui141-border,var(--cif-border,#dce3ed))}.guide-connection-item h3,.guide-connection-project h3{margin:0}.guide-connection-item p{line-height:1.55}.guide-connection-url,.guide-connection-project dd code{display:block;max-width:100%;padding:8px 10px;border-radius:8px;background:var(--rule-soft,#edf1eb);color:var(--ink,#0f1f14);font-size:.86rem;line-height:1.45;white-space:normal;overflow-wrap:anywhere;word-break:break-word}.guide-connection-project{display:grid;gap:13px;min-width:0;padding:18px;border-radius:12px;background:var(--paper,#f6f7f3);border:1px solid var(--rule,#dce3da);color:var(--ink,#0f1f14)}.guide-connection-project dl{display:grid;gap:11px;margin:0}.guide-connection-project dl>div{display:grid;gap:5px;min-width:0}.guide-connection-project dt{font-size:.78rem;font-weight:800;color:var(--muted,#64748b)}.guide-connection-project dd{min-width:0;margin:0}.guide-connection-note{padding:12px 14px;border-left:3px solid #176b35;border-radius:8px;background:var(--surface,#fff);color:var(--ink,#0f1f14);line-height:1.5}.guide-connection-warning{font-size:.86rem;color:var(--muted,#64748b)}@media(max-width:1100px){.guide-grid>article{grid-column:span 6}#guia-conexoes,#guia-membros,#guia-regras{grid-column:1/-1}.guide-connection-layout{grid-template-columns:1fr}}@media(max-width:680px){.guide-video-grid,.guide-connection-options{grid-template-columns:1fr}.guide-repository{align-items:flex-start;display:grid}.guide-grid>article,#guia-bancos,#guia-backup,#guia-conexoes,#guia-membros,#guia-regras{grid-column:1/-1}.guide-connection-project{padding:15px}}</style>
"""

    BACKUP_ROOT = Path("/srv/cloudif/managed-backups/projects")
    BACKUP_STATE = Path("/var/lib/cloudif/portal/project-backup-settings.json")
    BACKUP_REMOTE_ENV = Path("/etc/cloudif/project-backup-remote.env")
    PLATFORM_BACKUP_ROOT = Path("/srv/cloudif/managed-backups/config")
    TENANT_BACKUP_ROOT = Path("/srv/cloudif/managed-backups/databases-v2")

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
        host = env.get("REMOTE_HOST") or "10.68.128.250"
        port = int(env.get("REMOTE_PORT") or 22)
        enabled = env.get("REMOTE_ENABLED", "1") == "1"
        ready = bool(env.get("REMOTE_USER") and env.get("REMOTE_PATH") and env.get("REMOTE_KEY"))
        reachable = False
        if host and enabled:
            try:
                reachable = subprocess.run(["nc", "-z", "-w", "3", host, str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5).returncode == 0
            except Exception:
                reachable = False
        status = ("online" if reachable and ready else "online, aguardando credenciais" if reachable else "offline" if enabled else "desativado")
        return {"configured": bool(host), "enabled": enabled, "ready": ready, "reachable": reachable, "status": status, "host": host, "port": port}

    def _platform_backup_items() -> list[dict]:
        items=[]
        if PLATFORM_BACKUP_ROOT.is_dir():
            for f in sorted(PLATFORM_BACKUP_ROOT.glob('*.tar.gz'),key=lambda x:x.stat().st_mtime,reverse=True):
                items.append({'filename':f.name,'size':f.stat().st_size,'modified':dt.datetime.fromtimestamp(f.stat().st_mtime,dt.timezone.utc).astimezone().isoformat(timespec='seconds')})
        return items

    def _tenant_backup_items() -> list[dict]:
        items=[]
        if not TENANT_BACKUP_ROOT.is_dir():
            return items
        for f in sorted(TENANT_BACKUP_ROOT.glob('*.tar.gz'),key=lambda x:x.stat().st_mtime,reverse=True):
            tenants=[]
            try:
                listed=subprocess.check_output(['tar','-tzf',str(f)],text=True,timeout=20).splitlines()
                for entry in listed:
                    parts=entry.strip('/').split('/')
                    if len(parts)>2 and parts[1] and parts[1] not in tenants:
                        tenants.append(parts[1])
            except Exception:
                pass
            items.append({'filename':f.name,'size':f.stat().st_size,'modified':dt.datetime.fromtimestamp(f.stat().st_mtime,dt.timezone.utc).astimezone().isoformat(timespec='seconds'),'tenants':tenants,'tenant_count':len(tenants)})
        return items

    def backup_inventory(owner, user: dict) -> dict:
        active = []
        active_slugs = set()
        is_admin = bool(getattr(owner, "_pb_is_platform_admin")(user))
        is_professor = bool(getattr(owner, "_pb_is_professor")(user))
        try:
            for project in getattr(owner, "_pb_all_projects")(user):
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
        global_access = bool(is_admin or is_professor)
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
        payload = {
            "ok": True,
            "active": active,
            "history": history,
            "history_total": len(history),
            "remote": _backup_remote_status() if is_admin else {"status":"gerenciado pela plataforma"},
            "schedules": [_backup_schedule("cloudif-project-backup-auto.timer", "Backup automático dos projetos")],
            "retention_days": 14,
            "is_admin": is_admin,
            "is_professor": is_professor,
        }
        if is_admin:
            payload["platform"] = {"items": _platform_backup_items(), "can_manage": True}
            payload["tenants"] = {"items": _tenant_backup_items(), "can_download": True, "schedule": _backup_schedule("cloudif-tenant-db-backup-v2.timer", "Backup global de todos os bancos")}
            payload["schedules"].extend([
                _backup_schedule("cloudif-tenant-db-backup-v2.timer", "Backup global de todos os bancos"),
                _backup_schedule("cloudif-config-backup.timer", "Backup da configuração da plataforma"),
            ])
        return payload

    def backup_body(csrf_token: str) -> str:
        return r"""
<section class="card backup-console">
  <div class="section-title"><div><h2>Backup</h2><p>Agenda, servidor remoto, projetos ativos e acervo histórico do mecanismo já configurado.</p></div><button class="btn light" id="backup-refresh" type="button">Atualizar</button></div>
  <div class="ai-disclaimer" role="note"><strong>Aviso de testes e homologação:</strong> a plataforma está em desenvolvimento e homologação. Mantenha cópias próprias das informações importantes, mesmo quando o backup automático estiver ativo.</div>
  <div class="help"><strong>Separação de dados:</strong> backup de aplicação reúne publicações, configuração e metadados. Backup de banco contém dumps lógicos. Segredos e arquivos <code>.env</code> não são incluídos.</div>
  <div id="backup-console-list"><p>Consultando agenda e arquivos de backup…</p></div>
</section>
<div class="backup-progress-layer" id="backup-progress-layer" hidden>
  <section class="backup-progress-modal" role="dialog" aria-modal="true" aria-labelledby="backup-progress-title">
    <header><div><small id="backup-progress-kind">BACKUP DO PROJETO</small><h2 id="backup-progress-title">Preparando backup</h2><p id="backup-progress-subtitle">Aguarde enquanto a plataforma acompanha a geração do arquivo.</p></div><button class="btn light" id="backup-progress-close" type="button" hidden>Fechar</button></header>
    <div class="backup-progress-track"><span id="backup-progress-bar"></span></div>
    <p class="backup-progress-percent" id="backup-progress-percent">10% concluído</p>
    <div class="backup-progress-steps" id="backup-progress-steps"></div>
    <div class="backup-progress-result" id="backup-progress-result" hidden></div>
  </section>
</div>
<style>.backup-console{display:grid;gap:16px}.backup-overview-grid,.backup-console-meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}.backup-overview-grid>div,.backup-console-meta>div{padding:12px;border:1px solid var(--border,#dce3ed);border-radius:11px;background:#f8fafc}.backup-overview-grid small,.backup-console-meta small{display:block;color:var(--muted,#64748b)}.backup-section{display:grid;gap:12px;padding-top:4px}.backup-section+.backup-section{padding-top:18px;border-top:1px solid var(--border,#dce3ed)}.backup-section-number{display:inline-grid;place-items:center;width:28px;height:28px;border-radius:8px;background:#e9f6ed;color:#176b35;font-weight:850}.backup-section-title{display:flex;align-items:center;gap:10px}.backup-section-head{display:flex;align-items:end;justify-content:space-between;gap:14px}.backup-console-grid{display:grid;gap:12px}.backup-console-card{display:grid;gap:14px;padding:17px;border:1px solid var(--border,#dce3ed);border-radius:14px;background:#fff}.backup-console-actions{display:flex;gap:8px;flex-wrap:wrap}.backup-history-card>summary{display:flex;align-items:center;justify-content:space-between;gap:12px;cursor:pointer;list-style:none}.backup-history-card>summary::-webkit-details-marker{display:none}.backup-history-body{display:grid;gap:12px;padding-top:14px}.backup-file-list{display:grid;gap:7px}.backup-file{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;padding:10px;border:1px solid var(--border,#dce3ed);border-radius:10px}.backup-file small{display:block;color:var(--muted,#64748b)}.backup-schedule-list{display:grid;gap:7px}.backup-schedule{display:flex;justify-content:space-between;gap:12px;padding:10px;border-bottom:1px solid var(--border,#dce3ed)}@media(max-width:680px){.backup-file{grid-template-columns:1fr}.backup-history-card>summary,.backup-section-head{align-items:flex-start;display:grid}}.backup-progress-layer[hidden]{display:none}.backup-progress-layer{position:fixed;inset:0;z-index:9000;display:grid;place-items:center;padding:24px;background:rgba(15,23,42,.58);backdrop-filter:blur(2px)}.backup-progress-modal{width:min(680px,100%);max-height:calc(100vh - 48px);overflow:auto;padding:22px;border-radius:18px;background:#fff;box-shadow:0 24px 70px rgba(15,23,42,.24);display:grid;gap:18px}.backup-progress-modal header{display:flex;align-items:flex-start;justify-content:space-between;gap:18px}.backup-progress-modal header small{font-weight:850;letter-spacing:.08em;color:#176b35}.backup-progress-modal h2,.backup-progress-modal p{margin:4px 0 0}.backup-progress-track{height:7px;border-radius:999px;background:#e5e7eb;overflow:hidden}.backup-progress-track span{display:block;width:10%;height:100%;border-radius:inherit;background:#16883f;transition:width .35s ease}.backup-progress-percent{font-size:.86rem;color:#64748b}.backup-progress-steps{display:grid;gap:9px}.backup-progress-step{display:grid;grid-template-columns:30px 1fr auto;align-items:center;gap:11px;padding:12px;border:1px solid #dce3ed;border-radius:12px}.backup-progress-step strong,.backup-progress-step small{display:block}.backup-progress-step small{color:#64748b}.backup-progress-step .icon{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#eef2f7;font-weight:850}.backup-progress-step.done{border-color:#b7e4c7;background:#f0fff5}.backup-progress-step.done .icon{background:#20bf6b;color:#fff}.backup-progress-step.active{border-color:#93c5fd;background:#eff6ff}.backup-progress-step.active .icon{background:#2563eb;color:#fff}.backup-progress-step.failed{border-color:#fecaca;background:#fff1f2}.backup-progress-step.failed .icon{background:#dc2626;color:#fff}.backup-progress-result{padding:13px;border-radius:12px;background:#f0fff5;border:1px solid #b7e4c7}.backup-progress-result.bad{background:#fff1f2;border-color:#fecaca;color:#991b1b}@media(max-width:680px){.backup-progress-modal{padding:18px}.backup-progress-step{grid-template-columns:28px 1fr}.backup-progress-step>span:last-child{grid-column:2}}</style>
<script>(()=>{const root=document.getElementById('backup-console-list'),refresh=document.getElementById('backup-refresh'),csrf=__CSRF__,progressLayer=document.getElementById('backup-progress-layer'),progressKind=document.getElementById('backup-progress-kind'),progressTitle=document.getElementById('backup-progress-title'),progressSubtitle=document.getElementById('backup-progress-subtitle'),progressBar=document.getElementById('backup-progress-bar'),progressPercent=document.getElementById('backup-progress-percent'),progressSteps=document.getElementById('backup-progress-steps'),progressResult=document.getElementById('backup-progress-result'),progressClose=document.getElementById('backup-progress-close');const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const bytes=n=>{n=Number(n||0);for(const u of ['B','KB','MB','GB','TB']){if(n<1024)return `${n.toFixed(n<10&&u!=='B'?1:0)} ${u}`;n/=1024}return `${n.toFixed(1)} PB`};async function request(url,options={}){const r=await fetch(url,{credentials:'same-origin',...options});const type=(r.headers.get('content-type')||'').toLowerCase(),text=await r.text();if(!type.includes('application/json'))throw new Error(`Resposta inválida do serviço de backup (HTTP ${r.status})`);const d=JSON.parse(text);if(!r.ok||!d.ok)throw new Error(d.error||`HTTP ${r.status}`);return d}async function action(slug,op,extra={}){const body=new URLSearchParams({csrf_token:csrf,slug,op,...extra});const response=await request('/cloudiff/portal/action/project-backup',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8','X-CSRF-Token':csrf},body});if(!['backup_now','platform_backup'].includes(op))await load();return response}let progressModel=[['Solicitação','Pedido recebido pelo Portal'],['Coleta','Aplicação, publicações e metadados'],['Validação','Verificando integridade e novo arquivo'],['Conclusão','Atualizando o histórico da página']];function drawProgress(active,failed=-1){progressSteps.innerHTML=progressModel.map((x,i)=>{const state=i<active?'done':i===active?'active':i===failed?'failed':'';const icon=state==='done'?'✓':state==='failed'?'!':String(i+1);const label=state==='done'?'Concluído':state==='active'?'Executando':state==='failed'?'Falhou':'Aguardando';return `<div class="backup-progress-step ${state}"><span class="icon">${icon}</span><span><strong>${x[0]}</strong><small>${x[1]}</small></span><span>${label}</span></div>`}).join('')}function showProgress(label,kind='BACKUP DO PROJETO',model=null){progressModel=model||[['Solicitação','Pedido recebido pelo Portal'],['Coleta','Aplicação, publicações e metadados'],['Validação','Verificando integridade e novo arquivo'],['Conclusão','Atualizando o histórico do projeto']];progressLayer.hidden=false;progressClose.hidden=true;progressResult.hidden=true;progressResult.className='backup-progress-result';progressKind.textContent=kind;progressTitle.textContent='Gerando backup';progressSubtitle.textContent=label;progressBar.style.width='10%';progressPercent.textContent='10% concluído';drawProgress(0)}function setProgress(step,percent,title,subtitle){drawProgress(step);progressBar.style.width=`${percent}%`;progressPercent.textContent=`${percent}% concluído`;if(title)progressTitle.textContent=title;if(subtitle)progressSubtitle.textContent=subtitle}function finishProgress(ok,message){progressBar.style.width='100%';progressPercent.textContent='100% concluído';progressClose.hidden=false;progressResult.hidden=false;progressResult.textContent=message;progressResult.className='backup-progress-result'+(ok?'':' bad');if(ok){drawProgress(4);progressTitle.textContent='Backup concluído';progressSubtitle.textContent='O novo arquivo já aparece no histórico.'}else{drawProgress(-1,2);progressTitle.textContent='Não foi possível concluir';progressSubtitle.textContent='A operação foi interrompida com segurança.'}}progressClose.onclick=()=>{progressLayer.hidden=true};async function projectState(slug){const d=await request('/cloudiff/portal/api/backup-overview',{headers:{Accept:'application/json'}});return (d.active||[]).find(x=>x.slug===slug)||null}async function runProjectBackup(button){const slug=button.dataset.slug;button.disabled=true;showProgress(slug,'BACKUP DO PROJETO');let before='';try{const current=await projectState(slug);before=((current&&current.items)||[])[0]?.filename||'';await action(slug,'backup_now');setProgress(0,18,'Solicitação enviada','O Portal confirmou o pedido de backup.');setProgress(1,38,'Backup em execução','Coletando aplicação, containers, publicações e metadados.');const started=Date.now();let observed=false;while(Date.now()-started<240000){await new Promise(r=>setTimeout(r,2500));const state=await projectState(slug),latest=((state&&state.items)||[])[0];if(Date.now()-started>7000)setProgress(2,72,'Validando arquivo','Aguardando a nova cópia aparecer no inventário.');if(latest&&latest.filename&&latest.filename!==before){observed=true;setProgress(3,92,'Atualizando histórico',`${latest.filename} · ${bytes(latest.size)}`);await load();finishProgress(true,`Backup criado com sucesso: ${latest.filename}`);break}}if(!observed)throw new Error('O backup continua em processamento além do tempo esperado. Atualize a página em alguns instantes.')}catch(e){finishProgress(false,e.message||'Falha inesperada no backup.')}finally{button.disabled=false}}async function platformState(){const d=await request('/cloudiff/portal/api/backup-overview',{headers:{Accept:'application/json'}});return d.platform||{items:[]}}async function runPlatformBackup(button){button.disabled=true;showProgress('Configuração central da CloudIFF','BACKUP DA PLATAFORMA',[['Solicitação','Pedido recebido pelo Portal'],['Coleta','Portal, configurações, unidades e metadados'],['Validação','Verificando integridade e novo arquivo'],['Conclusão','Atualizando o histórico da plataforma']]);let before='';try{const current=await platformState();before=(current.items||[])[0]?.filename||'';await action('','platform_backup');setProgress(0,18,'Solicitação enviada','O Portal confirmou o pedido de backup da plataforma.');setProgress(1,42,'Coletando configurações','Portal, unidades, metadados e configurações centrais.');const started=Date.now();let observed=false;while(Date.now()-started<240000){await new Promise(r=>setTimeout(r,2500));const state=await platformState(),latest=(state.items||[])[0];if(Date.now()-started>7000)setProgress(2,74,'Validando arquivo','Compactando e verificando a nova cópia da plataforma.');if(latest&&latest.filename&&latest.filename!==before){observed=true;setProgress(3,92,'Atualizando histórico',`${latest.filename} · ${bytes(latest.size)}`);await load();finishProgress(true,`Backup da plataforma criado com sucesso: ${latest.filename}`);break}}if(!observed)throw new Error('O backup da plataforma continua em processamento além do tempo esperado. Atualize a página em alguns instantes.')}catch(e){finishProgress(false,e.message||'Falha inesperada no backup da plataforma.')}finally{button.disabled=false}}function file(x,slug,historical=false){const url=historical?`/cloudiff/portal/download/backup-history?slug=${encodeURIComponent(slug)}&file=${encodeURIComponent(x.filename)}`:`/cloudiff/portal/download/project-backup?slug=${encodeURIComponent(slug)}&file=${encodeURIComponent(x.filename)}`;return `<div class="backup-file"><div><strong>${x.type==='database'?'Banco de dados':'Aplicação e containers'}</strong><small>${esc(x.modified||'')} · ${bytes(x.size)}${x.sha256?` · SHA-256 ${esc(x.sha256.slice(0,12))}…`:''}</small></div><a class="btn light" href="${url}">Baixar</a></div>`}function activeCard(p){const c=p.settings||{},r=c.remote||{},items=p.items||[];return `<article class="backup-console-card"><div class="section-title"><div><h3>${esc(p.name||p.slug)}</h3><small>${esc(p.slug)} · aplicação e banco vinculado</small></div><span class="pill ${c.last_result?'ok':'muted'}">${c.last_result?'com execução':'sem execução'}</span></div><div class="backup-console-meta"><div><small>Automático local</small><strong>${c.enabled?'Ativado':'Desativado'}</strong></div><div><small>Última execução</small><strong>${esc(c.last_run||'Ainda não executado')}</strong></div><div><small>Retenção</small><strong>${Number(c.retention||14)} dias</strong></div><div><small>Servidor remoto</small><strong>${esc(r.status||'não configurado')}</strong></div><div><small>Arquivos</small><strong>${items.length}</strong></div></div>${p.can_manage?`<div class="backup-console-actions"><button class="btn" data-op="backup_now" data-slug="${esc(p.slug)}">Gerar backup agora</button><button class="btn light" data-op="set_auto" data-slug="${esc(p.slug)}" data-enabled="${c.enabled?'0':'1'}" data-remote="${c.remote_requested?'1':'0'}">${c.enabled?'Desativar automático':'Ativar automático'}</button><button class="btn light" data-op="set_remote" data-slug="${esc(p.slug)}" data-enabled="${c.enabled?'1':'0'}" data-remote="${c.remote_requested?'0':'1'}">${c.remote_requested?'Desativar sincronização':'Ativar sincronização'}</button></div>`:''}<div class="backup-file-list">${items.length?items.slice(0,8).map(x=>file(x,p.slug)).join(''):'<div class="empty-state">Nenhum arquivo disponível.</div>'}</div></article>`}function platformCard(p){const items=p.items||[];return `<article class="backup-console-card"><div class="section-title"><div><h3>Backup da plataforma</h3><small>Portal, configurações, unidades e metadados.</small></div><span class="pill ${items.length?'ok':'muted'}">${items.length} arquivo(s)</span></div>${p.can_manage?'<div class="backup-console-actions"><button class="btn" data-platform-backup>Gerar backup da plataforma</button></div>':''}<div class="backup-file-list">${items.length?items.slice(0,10).map(x=>`<div class="backup-file"><div><strong>Configuração da plataforma</strong><small>${esc(x.modified)} · ${bytes(x.size)}</small></div><a class="btn light" href="/cloudiff/portal/download/platform-backup?file=${encodeURIComponent(x.filename)}">Baixar</a></div>`).join(''):'<div class="empty-state">Nenhum backup da plataforma disponível.</div>'}</div></article>`}function tenantBackupCard(p){const items=p.items||[],schedule=p.schedule||{};return `<article class="backup-console-card"><div class="section-title"><div><h3>Backup global de todos os bancos</h3><small>Dumps lógicos PostgreSQL agrupados por execução. Segredos e arquivos .env não são incluídos.</small></div><span class="pill ${schedule.active==='active'?'ok':'warn'}">${esc(schedule.active||'unknown')}${schedule.next?` · ${esc(schedule.next)}`:''}</span></div><div class="backup-console-meta"><div><small>Agendamento</small><strong>${schedule.active==='active'?'Ativo':'Inativo'}</strong></div><div><small>Retenção</small><strong>14 dias</strong></div><div><small>Última execução</small><strong>${items.length?esc(items[0].modified):'Ainda não executado'}</strong></div><div><small>Pacotes</small><strong>${items.length}</strong></div></div><div class="backup-file-list">${items.length?items.slice(0,10).map(x=>`<div class="backup-file"><div><strong>Pacote global de bancos</strong><small>${esc(x.modified)} · ${bytes(x.size)} · ${Number(x.tenant_count||0)} tenant(s)${(x.tenants||[]).length?` · ${esc(x.tenants.join(', '))}`:''}</small></div>${p.can_download?`<a class="btn light" href="/cloudiff/portal/download/tenant-backup?file=${encodeURIComponent(x.filename)}">Baixar</a>`:''}</div>`).join(''):'<div class="empty-state">Nenhum backup de banco disponível.</div>'}</div></article>`}function historyCard(p){return `<details class="backup-console-card backup-history-card"><summary><span><strong>${esc(p.slug)}</strong><small>${esc(p.owner||'proprietário não identificado')} · última cópia ${esc(p.last_backup||'—')}</small></span><span class="pill warn">Projeto removido · ${p.total_files} arquivos</span></summary><div class="backup-history-body"><div class="backup-console-meta"><div><small>Banco</small><strong>${p.database_files}</strong></div><div><small>Aplicação</small><strong>${p.application_files}</strong></div><div><small>Espaço preservado</small><strong>${bytes(p.total_size)}</strong></div><div><small>Retenção</small><strong>Preservado para revisão</strong></div></div><div class="backup-file-list">${p.items.map(x=>file(x,p.slug,true)).join('')}</div>${p.total_files>p.items.length?`<p class="small">Exibindo os ${p.items.length} arquivos mais recentes de ${p.total_files}.</p>`:''}</div></details>`}async function load(){refresh.disabled=true;root.innerHTML='<p>Consultando agenda e arquivos de backup…</p>';try{const d=await request('/cloudiff/portal/api/backup-overview',{headers:{Accept:'application/json'}}),r=d.remote||{},s=d.schedules||[],a=d.active||[],h=d.history||[];root.innerHTML=`<div class="backup-overview-grid"><div><small>Backup automático</small><strong>${s.some(x=>x.active==='active')?'Ativo':'Verificar serviço'}</strong></div><div><small>Servidor remoto</small><strong>${esc(r.status||'não configurado')}</strong>${r.host?`<small>${esc(r.host)}:${r.port}</small>`:''}</div><div><small>Retenção padrão</small><strong>${d.retention_days} dias</strong></div><div><small>Projetos históricos</small><strong>${d.history_total}</strong></div></div><section class="backup-section"><div class="backup-section-head"><div><h3>Agendamentos</h3><p class="small">Timers reais configurados no servidor.</p></div></div><div class="backup-console-card backup-schedule-list">${s.map(x=>`<div class="backup-schedule"><span><strong>${esc(x.label)}</strong><small>${esc(x.unit)}</small></span><span class="pill ${x.active==='active'?'ok':'warn'}">${esc(x.active)}${x.next?` · ${esc(x.next)}`:''}</span></div>`).join('')}</div></section>${d.platform?`<section class="backup-section"><div class="backup-section-head"><div class="backup-section-title"><span class="backup-section-number">1</span><div><h3>Backup da plataforma</h3><p class="small">Portal, configurações centrais, unidades e metadados. Exclusivo para administradores.</p></div></div></div><div class="backup-console-grid">${platformCard(d.platform)}</div></section>`:''}<section class="backup-section"><div class="backup-section-head"><div class="backup-section-title"><span class="backup-section-number">2</span><div><h3>Backup dos projetos e bancos vinculados</h3><p class="small">Cada projeto reúne cópias da aplicação, publicações, configurações e do tenant associado.</p></div></div><span class="pill">${a.length}</span></div><div class="backup-console-grid">${a.length?a.map(activeCard).join(''):'<div class="empty-state"><h3>Nenhum projeto ativo</h3><p>Novos projetos aparecerão aqui automaticamente.</p></div>'}</div></section>${d.tenants?`<section class="backup-section"><div class="backup-section-head"><div class="backup-section-title"><span class="backup-section-number">3</span><div><h3>Backup global de todos os bancos</h3><p class="small">Pacote administrativo com todos os tenants. Exclusivo para administradores.</p></div></div></div><div class="backup-console-grid">${tenantBackupCard(d.tenants)}</div></section>`:''}<section class="backup-section"><div class="backup-section-head"><div><h3>Backups históricos</h3><p class="small">Arquivos preservados de projetos removidos. Somente leitura.</p></div><span class="pill warn">${h.length} projetos</span></div><div class="backup-console-grid">${h.length?h.map(historyCard).join(''):'<div class="empty-state">Nenhum backup histórico autorizado.</div>'}</div></section>`;const pb=root.querySelector('[data-platform-backup]');if(pb)pb.onclick=()=>runPlatformBackup(pb);root.querySelectorAll('[data-op]').forEach(b=>b.onclick=async()=>{if(b.dataset.op==='backup_now')return runProjectBackup(b);b.disabled=true;try{const op=b.dataset.op==='set_remote'?'set_auto':b.dataset.op;await action(b.dataset.slug,op,{enabled:b.dataset.enabled||'0',remote_requested:b.dataset.remote||'0'})}catch(e){alert(e.message)}finally{b.disabled=false}})}catch(e){root.innerHTML=`<p class="pill bad">${esc(e.message)}</p>`}finally{refresh.disabled=false}}refresh.onclick=load;load()})();</script>
""".replace('__CSRF__', json.dumps(csrf_token))


    def wrap(handler_class) -> None:
        if getattr(handler_class, "_v2_coexist_wrapped", False):
            return
        previous_get = handler_class.do_GET

        def do_GET(self):
            if handle_preview_request(self):
                return
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            route_query = urllib.parse.parse_qs(parsed.query)
            query_api = (route_query.get("api") or [""])[0].strip()
            try:
                toolchain_match = re.fullmatch(r'/cloudiff?/portal/api/projects/([a-z0-9][a-z0-9-]{0,62})/toolchain(?:/(builds/toolchain_[a-f0-9]{24}(?:/logs)?|images(?:/img_[a-f0-9]{24})?))?', path)
                if toolchain_match:
                    try:
                        from cloudif_project_toolchain_web import handle_get as handle_toolchain_get
                        actor=identity(self.headers);query={key:(values or [''])[0] for key,values in route_query.items()}
                        status,payload=handle_toolchain_get(toolchain_match.group(1),toolchain_match.group(2) or '',query,actor.username,list(actor.groups))
                        return send_json(self,status,payload)
                    except LookupError as exc:
                        return send_json(self,404,{"ok":False,"error":{"code":str(exc),"message":"Toolchain, imagem ou job não encontrado."}})
                    except PermissionError as exc:
                        return send_json(self,403,{"ok":False,"error":{"code":str(exc),"message":"Acesso negado."}})
                    except ValueError as exc:
                        return send_json(self,400,{"ok":False,"error":{"code":str(exc),"message":"Parâmetros inválidos."}})
                    except RuntimeError as exc:
                        return send_json(self,409,{"ok":False,"error":{"code":str(exc),"message":"A operação não pode ser concluída neste estado."}})
                    except Exception as exc:
                        return send_json(self,503,{"ok":False,"error":{"code":"toolchain_api_unavailable","message":"A API de toolchain está temporariamente indisponível.","detail":type(exc).__name__}})
                observability_match = re.fullmatch(r'/cloudiff?/portal/api/projects/([a-z0-9][a-z0-9-]{0,62})/observability(?:/(alerts))?', path)
                if observability_match:
                    try:
                        from cloudif_project_observability_web import handle_get as handle_observability_get
                        actor=identity(self.headers);status,payload=handle_observability_get(observability_match.group(1),observability_match.group(2) or 'snapshot',actor.username,list(actor.groups));return send_json(self,status,payload)
                    except PermissionError as exc:return send_json(self,403,{"ok":False,"error":{"code":str(exc)}})
                    except Exception as exc:return send_json(self,503,{"ok":False,"error":{"code":"observability_unavailable","detail":type(exc).__name__}})
                runtime_match = re.fullmatch(r'/cloudiff?/portal/api/projects/([a-z0-9][a-z0-9-]{0,62})/(runtime-state|runtime-drift)', path)
                if runtime_match:
                    try:
                        from cloudif_project_runtime_reconcile_web import handle_get as handle_runtime_get
                        actor=identity(self.headers);query={key:(values or [''])[0] for key,values in route_query.items()}
                        status,payload=handle_runtime_get(runtime_match.group(1),'drift' if runtime_match.group(2)=='runtime-drift' else 'status',query,actor.username,list(actor.groups))
                        return send_json(self,status,payload)
                    except PermissionError as exc:return send_json(self,403,{"ok":False,"error":{"code":str(exc)}})
                    except Exception as exc:return send_json(self,503,{"ok":False,"error":{"code":"runtime_reconciler_unavailable","detail":type(exc).__name__}})
                secret_match = re.fullmatch(r'/cloudiff?/portal/api/projects/([a-z0-9][a-z0-9-]{0,62})/environment/secrets(?:/(history))?', path)
                if secret_match:
                    try:
                        from cloudif_project_secret_web import handle_get as handle_secret_get
                        actor=identity(self.headers);query={key:(values or [''])[0] for key,values in route_query.items()}
                        status,payload=handle_secret_get(secret_match.group(1),secret_match.group(2) or '',query,actor.username,list(actor.groups))
                        return send_json(self,status,payload)
                    except LookupError as exc:
                        return send_json(self,404,{"ok":False,"error":{"code":str(exc),"message":"Projeto ou segredo não encontrado."}})
                    except PermissionError as exc:
                        return send_json(self,403,{"ok":False,"error":{"code":str(exc),"message":"Acesso negado."}})
                    except ValueError as exc:
                        return send_json(self,400,{"ok":False,"error":{"code":str(exc),"message":"Parâmetros inválidos."}})
                    except RuntimeError as exc:
                        return send_json(self,409,{"ok":False,"error":{"code":str(exc),"message":"A operação não pode ser concluída neste estado."}})
                    except Exception as exc:
                        return send_json(self,503,{"ok":False,"error":{"code":"secret_api_unavailable","message":"A API de segredos está temporariamente indisponível.","detail":type(exc).__name__}})
                environment_match = re.fullmatch(r'/cloudiff?/portal/api/projects/([a-z0-9][a-z0-9-]{0,62})/environment(?:/(history|missing|effective|export))?', path)
                if environment_match:
                    try:
                        from cloudif_project_environment_web import handle_get
                        actor=identity(self.headers);query={key:(values or [''])[0] for key,values in route_query.items()}
                        status,payload=handle_get(environment_match.group(1),environment_match.group(2) or '',query,actor.username,list(actor.groups))
                        return send_json(self,status,payload)
                    except LookupError as exc:
                        return send_json(self,404,{"ok":False,"error":{"code":str(exc),"message":"Projeto ou recurso não encontrado."}})
                    except PermissionError as exc:
                        return send_json(self,403,{"ok":False,"error":{"code":str(exc),"message":"Acesso negado."}})
                    except ValueError as exc:
                        return send_json(self,400,{"ok":False,"error":{"code":str(exc),"message":"Parâmetros inválidos."}})
                    except Exception as exc:
                        return send_json(self,503,{"ok":False,"error":{"code":"environment_api_unavailable","message":"A API de ambiente está temporariamente indisponível.","detail":type(exc).__name__}})
                if path in {"/cloudif/portal/api/admin-delete-project-status", "/cloudiff/portal/api/admin-delete-project-status"}:
                    try:
                        actor = identity(self.headers)
                        groups = {str(group).strip().lower() for group in actor.groups if str(group).strip()}
                        global_access = bool(groups.intersection({"cloudif-tenants-admin", "cloudif-professor"}))
                        from cloudif_admin_project_delete import can_read_job
                        query = urllib.parse.parse_qs(parsed.query);job_id=(query.get("job_id") or [""])[0]
                        allowed,payload=can_read_job(job_id,actor.username,global_access)
                        if not payload.get("ok"):
                            return send_json(self, 404, payload)
                        if not allowed:
                            return send_json(self, 403, {"ok": False, "error": "forbidden"})
                        return send_json(self, 200, payload)
                    except Exception as exc:
                        return send_json(self, 503, {"ok": False, "error": "delete_status_unavailable", "detail": type(exc).__name__})
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
                if path in {"/cloudif/portal/api/admin-delete-tenant-preview", "/cloudiff/portal/api/admin-delete-tenant-preview"} or (path in PORTAL_PATHS and query_api == "admin-delete-tenant-preview"):
                    if not tenant_admin_allowed(self):
                        return send_json(self, 403, {"ok": False, "error": "forbidden"})
                    from cloudif_admin_tenant_delete import preview
                    payload = preview((route_query.get("tenant") or [""])[0])
                    return send_json(self, 200, payload)
                if path in {"/cloudif/portal/api/admin-delete-tenant-status", "/cloudiff/portal/api/admin-delete-tenant-status"} or (path in PORTAL_PATHS and query_api == "admin-delete-tenant-status"):
                    if not tenant_admin_allowed(self):
                        return send_json(self, 403, {"ok": False, "error": "forbidden"})
                    from cloudif_admin_tenant_delete import job_status as tenant_job_status
                    payload = tenant_job_status((route_query.get("job_id") or [""])[0])
                    return send_json(self, 200 if payload.get("ok") else 404, payload)
                if path in {"/cloudif/portal/api/backup-overview", "/cloudiff/portal/api/backup-overview"}:
                    owner = sys.modules.get(handler_class.__module__)
                    user = self.user()
                    return send_json(self, 200, backup_inventory(owner, user))
                if path in {"/cloudif/portal/download/tenant-backup", "/cloudiff/portal/download/tenant-backup"}:
                    user=self.user(); q=urllib.parse.parse_qs(parsed.query); filename=(q.get("file") or [""])[0].strip()
                    if not getattr(sys.modules.get(handler_class.__module__),"_pb_is_platform_admin")(user) or filename != Path(filename).name or not filename.endswith('.tar.gz'):
                        return send_json(self,403,{"ok":False,"error":"forbidden"})
                    file_path=(TENANT_BACKUP_ROOT/filename).resolve(); root_path=TENANT_BACKUP_ROOT.resolve()
                    if root_path not in file_path.parents or not file_path.is_file():
                        return send_json(self,404,{"ok":False,"error":"not_found"})
                    self.send_response(200);self.send_header('Content-Type','application/gzip');self.send_header('Content-Disposition',f'attachment; filename="{filename}"');self.send_header('Content-Length',str(file_path.stat().st_size));self.send_header('Cache-Control','private, no-store');self.end_headers()
                    with file_path.open('rb') as src:
                        while True:
                            chunk=src.read(1024*1024)
                            if not chunk:break
                            self.wfile.write(chunk)
                    return
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
                    global_access = bool(getattr(owner,"_pb_is_platform_admin")(user) or getattr(owner,"_pb_is_professor")(user))
                    project_access = bool(getattr(owner,"_pb_project")(user,slug))
                    owner_access = (item.get("owner") or "").lower() == (user.get("username") or "").lower() if item else False
                    if not item or (not global_access and not project_access and not owner_access):
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
                            resource_scope = (query.get("scope") or [""])[0].strip().lower()
                            owner = sys.modules.get(handler_class.__module__)
                            adapted_markup = transform(markup, identity(self.headers), tab or "publicacao", selected_project, resource_scope)
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
            except sqlite3.Error:
                body = (
                    '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
                    '<meta name="viewport" content="width=device-width,initial-scale=1">'
                    '<title>Portal temporariamente ocupado · CloudIFF</title></head>'
                    '<body style="font-family:Arial,sans-serif;margin:0;padding:48px;background:#f7f7f5;color:#17201a">'
                    '<main style="max-width:640px;margin:auto"><h1>Portal temporariamente ocupado</h1>'
                    '<p>Uma atualização de projeto está sendo finalizada. Tente novamente em alguns segundos.</p>'
                    '</main></body></html>'
                ).encode('utf-8')
                return send(self, 503, 'text/html; charset=utf-8', body, [('Retry-After', '3')])
            except Exception:
                # Non-database adapter failures may still use the legacy renderer.
                return previous_get(self)
            return previous_get(self)

        handler_class.do_GET = do_GET

        previous_post = getattr(handler_class, "do_POST", None)
        if previous_post is not None:
            def do_POST(self):
                if handle_preview_request(self):
                    return
                parsed = urllib.parse.urlparse(self.path)
                toolchain_match = re.fullmatch(r'/cloudiff?/portal/api/projects/([a-z0-9][a-z0-9-]{0,62})/toolchain/(validate|build/plan|build/approval/request|build/execute|activation/plan|activation/approval/request|activation/execute)', parsed.path)
                if toolchain_match:
                    try:
                        content_length=int(self.headers.get('Content-Length','0') or 0)
                        if content_length<0 or content_length>2_097_152:
                            return send_json(self,413,{"ok":False,"error":{"code":"payload_too_large"}})
                        raw=self.rfile.read(content_length)
                        if 'application/json' not in (self.headers.get('Content-Type') or '').lower():
                            return send_json(self,415,{"ok":False,"error":{"code":"json_required","message":"Use Content-Type application/json."}})
                        payload=json.loads(raw or b'{}')
                        if not isinstance(payload,dict):
                            return send_json(self,400,{"ok":False,"error":{"code":"invalid_json_object"}})
                        actor=identity(self.headers);groups=[str(group) for group in actor.groups]
                        user={"username":actor.username,"email":actor.email,"groups":groups,"admin":"cloudif-tenants-admin" in {group.lower() for group in groups}}
                        owner=sys.modules.get(handler_class.__module__)
                        provided=str(self.headers.get('X-CSRF-Token') or payload.pop('csrfToken',payload.pop('csrf_token','')))
                        if not getattr(owner,'_prod_csrf_equal')(provided,getattr(owner,'_prod_csrf_token')(user)):
                            return send_json(self,403,{"ok":False,"error":{"code":"invalid_csrf","message":"Token CSRF inválido ou ausente."}})
                        from cloudif_project_toolchain_web import handle_post as handle_toolchain_post
                        status,response=handle_toolchain_post(toolchain_match.group(1),toolchain_match.group(2),payload,actor.username,groups)
                        return send_json(self,status,response)
                    except json.JSONDecodeError:
                        return send_json(self,400,{"ok":False,"error":{"code":"invalid_json","message":"O corpo JSON é inválido."}})
                    except LookupError as exc:
                        return send_json(self,404,{"ok":False,"error":{"code":str(exc),"message":"Projeto, job, imagem ou aprovação não encontrado."}})
                    except PermissionError as exc:
                        return send_json(self,403,{"ok":False,"error":{"code":str(exc),"message":"Acesso negado."}})
                    except ValueError as exc:
                        return send_json(self,400,{"ok":False,"error":{"code":str(exc),"message":"Parâmetros inválidos."}})
                    except RuntimeError as exc:
                        return send_json(self,409,{"ok":False,"error":{"code":str(exc),"message":"A operação não pode ser concluída neste estado."}})
                    except Exception as exc:
                        return send_json(self,503,{"ok":False,"error":{"code":"toolchain_api_unavailable","message":"A API de toolchain está temporariamente indisponível.","detail":type(exc).__name__}})
                runtime_match = re.fullmatch(r'/cloudiff?/portal/api/projects/([a-z0-9][a-z0-9-]{0,62})/runtime-reconcile/(plan)', parsed.path)
                if runtime_match:
                    try:
                        content_length=int(self.headers.get('Content-Length','0') or 0)
                        if content_length<0 or content_length>262144:return send_json(self,413,{"ok":False,"error":{"code":"payload_too_large"}})
                        raw=self.rfile.read(content_length)
                        if 'application/json' not in (self.headers.get('Content-Type') or '').lower():return send_json(self,415,{"ok":False,"error":{"code":"json_required"}})
                        payload=json.loads(raw or b'{}');actor=identity(self.headers);groups=[str(group) for group in actor.groups]
                        user={"username":actor.username,"email":actor.email,"groups":groups,"admin":"cloudif-tenants-admin" in {group.lower() for group in groups}}
                        owner=sys.modules.get(handler_class.__module__);provided=str(self.headers.get('X-CSRF-Token') or payload.pop('csrfToken',payload.pop('csrf_token','')))
                        if not getattr(owner,'_prod_csrf_equal')(provided,getattr(owner,'_prod_csrf_token')(user)):return send_json(self,403,{"ok":False,"error":{"code":"invalid_csrf"}})
                        from cloudif_project_runtime_reconcile_web import handle_post as handle_runtime_post
                        status,response=handle_runtime_post(runtime_match.group(1),runtime_match.group(2),payload,actor.username,groups);return send_json(self,status,response)
                    except json.JSONDecodeError:return send_json(self,400,{"ok":False,"error":{"code":"invalid_json"}})
                    except Exception as exc:return send_json(self,503,{"ok":False,"error":{"code":"runtime_reconciler_unavailable","detail":type(exc).__name__}})
                secret_match = re.fullmatch(r'/cloudiff?/portal/api/projects/([a-z0-9][a-z0-9-]{0,62})/environment/secrets/(stage|rotate/plan|rotate/approval/request|rotate/execute|revoke/plan|revoke/approval/request|revoke/execute|promote/plan|promote/approval/request|promote/execute|read/plan|read/approval/request|read/execute)', parsed.path)
                if secret_match:
                    try:
                        content_length=int(self.headers.get('Content-Length','0') or 0)
                        if content_length<0 or content_length>2_097_152:
                            return send_json(self,413,{"ok":False,"error":{"code":"payload_too_large"}})
                        raw=self.rfile.read(content_length)
                        if 'application/json' not in (self.headers.get('Content-Type') or '').lower():
                            return send_json(self,415,{"ok":False,"error":{"code":"json_required","message":"Use Content-Type application/json."}})
                        payload=json.loads(raw or b'{}')
                        if not isinstance(payload,dict):
                            return send_json(self,400,{"ok":False,"error":{"code":"invalid_json_object"}})
                        actor=identity(self.headers);groups=[str(group) for group in actor.groups]
                        user={"username":actor.username,"email":actor.email,"groups":groups,"admin":"cloudif-tenants-admin" in {group.lower() for group in groups}}
                        owner=sys.modules.get(handler_class.__module__)
                        provided=str(self.headers.get('X-CSRF-Token') or payload.pop('csrfToken',payload.pop('csrf_token','')))
                        if not getattr(owner,'_prod_csrf_equal')(provided,getattr(owner,'_prod_csrf_token')(user)):
                            return send_json(self,403,{"ok":False,"error":{"code":"invalid_csrf","message":"Token CSRF inválido ou ausente."}})
                        from cloudif_project_secret_web import handle_post as handle_secret_post
                        operation=secret_match.group(2)
                        status,response=handle_secret_post(secret_match.group(1),operation,payload,actor.username,groups)
                        if operation=='read/execute':
                            body=json.dumps(response,ensure_ascii=False,separators=(',',':')).encode('utf-8')
                            return send(self,status,'application/json; charset=utf-8',body,[('Cache-Control','no-store, max-age=0'),('Pragma','no-cache'),('Expires','0')])
                        return send_json(self,status,response)
                    except json.JSONDecodeError:
                        return send_json(self,400,{"ok":False,"error":{"code":"invalid_json","message":"O corpo JSON é inválido."}})
                    except LookupError as exc:
                        return send_json(self,404,{"ok":False,"error":{"code":str(exc),"message":"Projeto, segredo, plano ou aprovação não encontrado."}})
                    except PermissionError as exc:
                        return send_json(self,403,{"ok":False,"error":{"code":str(exc),"message":"Acesso negado."}})
                    except ValueError as exc:
                        return send_json(self,400,{"ok":False,"error":{"code":str(exc),"message":"Parâmetros inválidos."}})
                    except RuntimeError as exc:
                        return send_json(self,409,{"ok":False,"error":{"code":str(exc),"message":"A operação não pode ser concluída neste estado."}})
                    except Exception as exc:
                        return send_json(self,503,{"ok":False,"error":{"code":"secret_api_unavailable","message":"A API de segredos está temporariamente indisponível.","detail":type(exc).__name__}})
                environment_match = re.fullmatch(r'/cloudiff?/portal/api/projects/([a-z0-9][a-z0-9-]{0,62})/environment/(validate|change/plan|promote/plan|import/plan|approval/request|change/execute|promote/execute)', parsed.path)
                if environment_match:
                    try:
                        content_length=int(self.headers.get('Content-Length','0') or 0)
                        if content_length<0 or content_length>2_097_152:
                            return send_json(self,413,{"ok":False,"error":{"code":"payload_too_large"}})
                        raw=self.rfile.read(content_length)
                        if 'application/json' not in (self.headers.get('Content-Type') or '').lower():
                            return send_json(self,415,{"ok":False,"error":{"code":"json_required","message":"Use Content-Type application/json."}})
                        payload=json.loads(raw or b'{}')
                        if not isinstance(payload,dict):
                            return send_json(self,400,{"ok":False,"error":{"code":"invalid_json_object"}})
                        actor=identity(self.headers);groups=[str(group) for group in actor.groups]
                        user={"username":actor.username,"email":actor.email,"groups":groups,"admin":"cloudif-tenants-admin" in {group.lower() for group in groups}}
                        owner=sys.modules.get(handler_class.__module__)
                        provided=str(self.headers.get('X-CSRF-Token') or payload.pop('csrfToken',payload.pop('csrf_token','')))
                        if not getattr(owner,'_prod_csrf_equal')(provided,getattr(owner,'_prod_csrf_token')(user)):
                            return send_json(self,403,{"ok":False,"error":{"code":"invalid_csrf","message":"Token CSRF inválido ou ausente."}})
                        from cloudif_project_environment_web import handle_post
                        status,response=handle_post(environment_match.group(1),environment_match.group(2),payload,actor.username,groups)
                        return send_json(self,status,response)
                    except json.JSONDecodeError:
                        return send_json(self,400,{"ok":False,"error":{"code":"invalid_json","message":"O corpo JSON é inválido."}})
                    except LookupError as exc:
                        return send_json(self,404,{"ok":False,"error":{"code":str(exc),"message":"Projeto, plano ou aprovação não encontrado."}})
                    except PermissionError as exc:
                        return send_json(self,403,{"ok":False,"error":{"code":str(exc),"message":"Acesso negado."}})
                    except ValueError as exc:
                        return send_json(self,400,{"ok":False,"error":{"code":str(exc),"message":"Parâmetros inválidos."}})
                    except RuntimeError as exc:
                        return send_json(self,409,{"ok":False,"error":{"code":str(exc),"message":"A operação não pode ser concluída neste estado."}})
                    except Exception as exc:
                        return send_json(self,503,{"ok":False,"error":{"code":"environment_api_unavailable","message":"A API de ambiente está temporariamente indisponível.","detail":type(exc).__name__}})
                query_action = (self.headers.get("X-CloudIF-Action") or (urllib.parse.parse_qs(parsed.query).get("action") or [""])[0]).strip()
                query_routed = parsed.path in PORTAL_PATHS and query_action in {
                    "admin-delete-project", "admin-delete-tenant", "admin-tenant-advanced", "backup-remote-config", "project-backup"
                }
                if not query_routed and parsed.path not in {
                    "/cloudif/portal/action/admin-delete-project",
                    "/cloudiff/portal/action/admin-delete-project",
                    "/cloudif/portal/action/admin-delete-tenant",
                    "/cloudiff/portal/action/admin-delete-tenant",
                    "/cloudif/portal/action/admin-tenant-advanced",
                    "/cloudiff/portal/action/admin-tenant-advanced",
                    "/cloudif/portal/action/backup-remote-config",
                    "/cloudiff/portal/action/backup-remote-config",
                    "/cloudif/portal/action/project-backup",
                    "/cloudiff/portal/action/project-backup",
                }:
                    return previous_post(self)
                content_length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(content_length)
                form = urllib.parse.parse_qs(raw.decode("utf-8", "ignore"))
                value = lambda key: (form.get(key) or [""])[0].strip()
                if parsed.path.endswith("/action/project-backup") or query_action == "project-backup":
                    try:
                        owner=sys.modules.get(handler_class.__module__);user=self.user()
                        if not getattr(owner,"_prod_csrf_equal")(value("csrf_token"),getattr(owner,"_prod_csrf_token")(user)):
                            return send_json(self,403,{"ok":False,"error":"invalid_csrf"})
                        slug=value("slug");op=value("op")
                        if op=='platform_backup':
                            if not getattr(owner,'_pb_is_platform_admin')(user):return send_json(self,403,{"ok":False,"error":"forbidden"})
                            subprocess.Popen(['/usr/local/sbin/cloudif-config-backup.sh'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
                            return send_json(self,202,{"ok":True,"result":{"accepted":True}})
                        project=getattr(owner,'_pb_project')(user,slug)
                        if not getattr(owner,'_pb_manage')(user,project):return send_json(self,403,{"ok":False,"error":"forbidden"})
                        if op in ('backup_now','backup'):
                            subprocess.Popen(['/usr/local/sbin/cloudif-project-backup.py','backup','--slug',slug],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);result={'accepted':True}
                            code=202
                        elif op=='set_auto':
                            result=getattr(owner,'_pb_call')('set-auto','--slug',slug,'--enabled',value('enabled') or '0','--remote-requested',value('remote_requested') or '0');code=200
                        else:return send_json(self,400,{"ok":False,"error":"invalid_operation"})
                        try:getattr(owner,'log_action')(user.get('username') or 'portal','project_backup_'+op,slug,0,'backup','')
                        except Exception:pass
                        return send_json(self,code,{"ok":True,"result":result})
                    except Exception as exc:
                        return send_json(self,500,{"ok":False,"error":type(exc).__name__,"detail":str(exc)[:300]})
                if parsed.path.endswith("/action/backup-remote-config") or query_action == "backup-remote-config":
                    try:
                        owner=sys.modules.get(handler_class.__module__); user=self.user()
                        if not user.get("admin"):
                            return send_json(self,403,{"ok":False,"error":"forbidden"})
                        if not getattr(owner,"_prod_csrf_equal")(value("csrf_token"),getattr(owner,"_prod_csrf_token")(user)):
                            return send_json(self,403,{"ok":False,"error":"invalid_csrf"})
                        host=value("remote_host"); port_text=value("remote_port"); remote_user=value("remote_user"); remote_path=value("remote_path"); remote_key=value("remote_key"); enabled=value("remote_enabled")=="1"
                        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,253}",host):
                            return send_json(self,400,{"ok":False,"error":"invalid_host"})
                        try: port=int(port_text)
                        except Exception: port=0
                        if port<1 or port>65535:
                            return send_json(self,400,{"ok":False,"error":"invalid_port"})
                        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}",remote_user):
                            return send_json(self,400,{"ok":False,"error":"invalid_user"})
                        if not remote_path or len(remote_path)>512 or any(x in remote_path for x in ("\n","\r","\x00")):
                            return send_json(self,400,{"ok":False,"error":"invalid_path"})
                        key_path=Path(remote_key)
                        allowed_key=key_path.is_absolute() and (str(key_path).startswith('/etc/cloudif/') or str(key_path).startswith('/root/.ssh/'))
                        if not allowed_key or not key_path.is_file():
                            return send_json(self,400,{"ok":False,"error":"invalid_key_path"})
                        reachable=False
                        if enabled:
                            try: reachable=subprocess.run(["nc","-z","-w","3",host,str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5).returncode==0
                            except Exception: reachable=False
                        env_text=(f"REMOTE_ENABLED={'1' if enabled else '0'}\nREMOTE_READY=1\nREMOTE_HOST={host}\nREMOTE_PORT={port}\nREMOTE_USER={remote_user}\nREMOTE_PATH={remote_path}\nREMOTE_KEY={remote_key}\n")
                        target=Path('/etc/cloudif/project-backup-remote.env'); tmp=target.with_name(target.name+'.tmp')
                        tmp.write_text(env_text,encoding='utf-8'); os.chmod(tmp,0o600); os.replace(tmp,target)
                        getattr(owner,"log_action")(user.get("username") or "admin","backup_remote_config",host,0,f"port={port} path={remote_path} reachable={reachable}","")
                        return send_json(self,200,{"ok":True,"host":host,"port":port,"path":remote_path,"enabled":enabled,"reachable":reachable})
                    except Exception as exc:
                        return send_json(self,500,{"ok":False,"error":type(exc).__name__,"detail":str(exc)[:300]})
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
                        owner = sys.modules.get(handler_class.__module__);actor = identity(self.headers);slug=value("slug")
                        groups = [str(group).strip() for group in actor.groups if str(group).strip()]
                        normalized_groups = {group.lower() for group in groups}
                        user = {
                            "username": actor.username,
                            "email": actor.email,
                            "groups": groups,
                            "admin": "cloudif-tenants-admin" in normalized_groups,
                        }
                        token_ok = getattr(owner, "_prod_csrf_equal")(
                            value("csrf_token"), getattr(owner, "_prod_csrf_token")(user)
                        )
                        if not token_ok:
                            return send_json(self, 403, {"ok": False, "error": "invalid_csrf"})
                        if not getattr(owner,"_admin_project_delete_allowed")(user,slug):
                            return send_json(self, 403, {"ok": False, "error": "forbidden"})
                        from cloudif_admin_project_delete import consume_wizard_token,start_job
                        if not consume_wizard_token(slug,value("wizard_token")):
                            return send_json(self, 409, {"ok": False, "error": "wizard_required"})
                        job = start_job(slug, value("confirm_text"), actor.username or "admin")
                        return send_json(self, 202 if job.get("ok") else 409, job)
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

        for method_name in ('do_HEAD','do_PUT','do_PATCH','do_DELETE'):
            previous_method=getattr(handler_class,method_name,None)
            if previous_method is None:
                continue
            def preview_method(self,_previous=previous_method):
                if handle_preview_request(self):
                    return
                return _previous(self)
            setattr(handler_class,method_name,preview_method)

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
