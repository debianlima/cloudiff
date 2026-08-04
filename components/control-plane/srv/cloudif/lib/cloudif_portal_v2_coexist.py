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
import re

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

    def help_body() -> str:
        return r"""
<section class="card platform-guide">
  <div class="section-title"><div><h1>Guia da plataforma</h1><p>Como usar cada área operacional da CloudIFF.</p></div><span class="pill ok">Ambiente real</span></div>
  <nav class="guide-index" aria-label="Seções do guia"><a href="#guia-publicacoes">Publicações</a><a href="#guia-projetos">Projetos</a><a href="#guia-bancos">Bancos</a><a href="#guia-backup">Backup</a><a href="#guia-conectores">Conectores</a><a href="#guia-ad">Administração</a></nav>
  <div class="guide-grid">
    <article id="guia-publicacoes"><span>01</span><h2>Publicações</h2><p>Acompanhe releases, endereços publicados, saúde e rollback. Uma publicação só aparece quando foi registrada pelos agentes.</p><ol><li>Abra o projeto.</li><li>Confira a release e o endereço.</li><li>Use rollback apenas quando houver release anterior homologada.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=publicacao">Abrir Publicações</a></article>
    <article id="guia-projetos"><span>02</span><h2>Projetos</h2><p>Crie projetos pelo wizard. O fluxo provisiona repositório Forgejo, stack Komodo, ACL e, quando solicitado, tenant Supabase.</p><ol><li>Informe nome e finalidade.</li><li>Escolha banco existente, novo ou sem banco.</li><li>Selecione a tecnologia.</li><li>Acompanhe o provisionamento até concluir.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=projetos">Abrir Projetos</a></article>
    <article id="guia-bancos"><span>03</span><h2>Bancos e tenants</h2><p>Consulte disponibilidade, serviços e permissões. Banco é independente de projeto e pode ser compartilhado.</p><ol><li>Use Iniciar/Parar somente para operação do tenant.</li><li>Abra o Studio pelo endereço exibido.</li><li>Exclua banco apenas em Administração, após remover vínculos de projetos.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=bancos">Abrir Bancos</a></article>
    <article id="guia-backup"><span>04</span><h2>Backup</h2><p>Consulte backups de aplicação e dumps lógicos. A exclusão de projeto não apaga o banco nem seus backups.</p><ol><li>Confira data, tamanho e hash.</li><li>Gere backup antes de mudanças sensíveis.</li><li>Na exclusão de tenant, o dump final é obrigatório.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=backup">Abrir Backup</a></article>
    <article id="guia-conectores"><span>05</span><h2>Conectores</h2><p>Gere credenciais e consulte ferramentas disponíveis para clientes, agentes e integrações MCP autorizadas.</p><ol><li>Escolha o projeto autorizado.</li><li>Gere ou rotacione o token.</li><li>Copie a configuração mostrada pela plataforma.</li><li>Nunca compartilhe o token em repositório ou mensagem.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=agentes">Abrir Conectores</a></article>
    <article id="guia-ad"><span>06</span><h2>Administração</h2><p>Área restrita. Administração do AD localiza usuários e grupos reais; Serviços globais abre Forgejo, Komodo e tenants; exclusões possuem wizard e auditoria.</p><ol><li>Pesquise o principal no AD e selecione a sugestão.</li><li>Use ações avançadas somente no tenant correto.</li><li>Leia a prévia antes de confirmar uma exclusão.</li><li>Reporte a etapa e a mensagem exibidas quando houver falha.</li></ol><a class="btn light" href="/cloudiff/portal/?tab=admin">Abrir Administração</a></article>
  </div>
  <div class="help"><strong>Perfis:</strong> Aluno visualiza apenas recursos autorizados. Professor administra projetos e serviços globais permitidos. Administrador de tenants também opera AD e bancos.</div>
</section>
<style>.platform-guide{display:grid;gap:20px}.guide-index{display:flex;flex-wrap:wrap;gap:8px}.guide-index a{padding:8px 11px;border:1px solid var(--ui141-border,var(--cif-border,#dce3ed));border-radius:999px;text-decoration:none}.guide-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}.guide-grid article{display:grid;align-content:start;gap:10px;padding:18px;border:1px solid var(--ui141-border,var(--cif-border,#dce3ed));border-radius:14px;background:var(--ui141-surface,var(--cif-surface,#fff))}.guide-grid article>span{font-size:.75rem;font-weight:800;color:#176b35}.guide-grid h2,.guide-grid p{margin:0}.guide-grid ol{margin:0;padding-left:20px;display:grid;gap:6px}.guide-grid .btn{justify-self:start}</style>
"""

    def backup_body(csrf_token: str) -> str:
        return r"""
<section class="card backup-console">
  <div class="section-title"><div><h2>Backup dos projetos</h2><p>Sincronização, estágio, retenção e arquivos reais do mecanismo já configurado.</p></div><button class="btn light" id="backup-refresh" type="button">Atualizar</button></div>
  <div class="help"><strong>Separação de dados:</strong> backup de aplicação reúne publicações, configuração e metadados. Backup de banco contém dumps lógicos. Segredos e arquivos <code>.env</code> não são incluídos.</div>
  <div id="backup-console-list"><p>Consultando o estágio de backup…</p></div>
</section>
<style>.backup-console{display:grid;gap:16px}.backup-console-grid{display:grid;gap:14px}.backup-console-card{display:grid;gap:14px;padding:18px;border:1px solid var(--ui141-border,var(--cif-border,#dce3ed));border-radius:14px;background:var(--ui141-surface,var(--cif-surface,#fff))}.backup-console-card h3{margin:0}.backup-console-meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:9px}.backup-console-meta div{padding:11px;background:#f8fafc;border-radius:9px}.backup-console-meta small{display:block;color:var(--ui141-muted,var(--cif-muted,#64748b))}.backup-console-actions{display:flex;gap:8px;flex-wrap:wrap}.backup-file-list{display:grid;gap:8px}.backup-file{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;padding:11px;border:1px solid var(--ui141-border,var(--cif-border,#dce3ed));border-radius:10px}.backup-file small{display:block;color:var(--ui141-muted,var(--cif-muted,#64748b))}@media(max-width:680px){.backup-file{grid-template-columns:1fr}}</style>
<script>(()=>{const root=document.getElementById('backup-console-list'),refresh=document.getElementById('backup-refresh'),csrf=__CSRF__;const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const bytes=n=>{n=Number(n||0);for(const u of ['B','KB','MB','GB','TB']){if(n<1024)return `${n.toFixed(n<10&&u!=='B'?1:0)} ${u}`;n/=1024}return `${n.toFixed(1)} PB`};async function request(url,options={}){const r=await fetch(url,{credentials:'same-origin',...options});const type=(r.headers.get('content-type')||'').toLowerCase();const text=await r.text();if(!type.includes('application/json'))throw new Error(`O servidor retornou uma página em vez de JSON (HTTP ${r.status})`);let d;try{d=JSON.parse(text)}catch(_){throw new Error('Resposta JSON inválida do serviço de backup')}if(!r.ok||!d.ok)throw new Error(d.error||`HTTP ${r.status}`);return d}async function action(slug,op,extra={}){const body=new URLSearchParams({csrf_token:csrf,slug,op,...extra});await request('/cloudif/portal/action/project-backup',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8','X-CSRF-Token':csrf},body});await load()}function file(x,slug){return `<div class="backup-file"><div><strong>${x.type==='database'?'Banco de dados':'Aplicação e containers'}</strong><small>${esc(x.modified||'')} · ${bytes(x.size)} · SHA-256 ${esc((x.sha256||'').slice(0,12))}… · estágio ${esc(x.remote||'local')}</small></div><a class="btn light" href="/cloudif/portal/download/project-backup?slug=${encodeURIComponent(slug)}&file=${encodeURIComponent(x.filename)}">Baixar</a></div>`}async function load(){refresh.disabled=true;root.innerHTML='<p>Consultando o estágio de backup…</p>';try{const d=await request('/cloudif/portal/api/project-backups',{headers:{Accept:'application/json'}});const projects=d.projects||[];root.innerHTML=projects.length?'<div class="backup-console-grid">'+projects.map(p=>{const c=p.settings||{},remote=c.remote||{},items=p.items||[];const can=!!p.can_manage;return `<article class="backup-console-card"><div class="section-title"><div><h3>${esc(p.name||p.slug)}</h3><small>${esc(p.slug)}</small></div><span class="pill ${c.last_result==='ok'?'ok':c.last_result?'bad':'muted'}">${esc(c.last_result||'sem execução')}</span></div><div class="backup-console-meta"><div><small>Automático local</small><strong>${c.enabled?'Ativado':'Desativado'}</strong></div><div><small>Última execução</small><strong>${esc(c.last_run||'Ainda não executado')}</strong></div><div><small>Retenção</small><strong>${Number(c.retention||14)} dias</strong></div><div><small>Servidor remoto</small><strong>${esc(remote.status||'não configurado')}</strong></div><div><small>Sincronização remota</small><strong>${c.remote_requested?'Solicitada':'Desativada'}</strong></div><div><small>Arquivos disponíveis</small><strong>${items.length}</strong></div></div>${can?`<div class="backup-console-actions"><button class="btn" data-op="backup_now" data-slug="${esc(p.slug)}">Gerar backup agora</button><button class="btn light" data-op="set_auto" data-slug="${esc(p.slug)}" data-enabled="${c.enabled?'0':'1'}" data-remote="${c.remote_requested?'1':'0'}">${c.enabled?'Desativar automático':'Ativar automático'}</button><button class="btn light" data-op="set_remote" data-slug="${esc(p.slug)}" data-enabled="${c.enabled?'1':'0'}" data-remote="${c.remote_requested?'0':'1'}">${c.remote_requested?'Desativar sincronização':'Ativar sincronização'}</button></div>`:''}<div class="backup-file-list">${items.length?items.map(x=>file(x,p.slug)).join(''):'<div class="empty-state">Nenhum arquivo disponível.</div>'}</div></article>`}).join('')+'</div>':'<div class="empty-state"><h3>Nenhum projeto ativo</h3><p>Os backups históricos continuam preservados no servidor. Novos projetos aparecerão aqui após a criação.</p></div>';root.querySelectorAll('[data-op]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{const op=b.dataset.op==='set_remote'?'set_auto':b.dataset.op;await action(b.dataset.slug,op,{enabled:b.dataset.enabled||'0',remote_requested:b.dataset.remote||'0'})}catch(e){alert(e.message)}finally{b.disabled=false}})}catch(e){root.innerHTML=`<p class="pill bad">${esc(e.message)}</p>`}finally{refresh.disabled=false}}refresh.onclick=load;load()})();</script>
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
                if try_asset(self, path):
                    return

                query = urllib.parse.parse_qs(parsed.query)
                tab = (query.get("tab") or [""])[0]
                if path in PORTAL_PATHS and tab == "backup":
                    owner = sys.modules.get(handler_class.__module__); user = self.user(); markup = render_legacy(identity(self.headers), "backup", "Backup", backup_body(getattr(owner, "_prod_csrf_token")(user)), "", "")
                    return send(self, 200, "text/html; charset=utf-8", markup.encode("utf-8"))
                if path in PORTAL_PATHS and tab == "ajuda":
                    markup = render_legacy(identity(self.headers), "ajuda", "Guia da plataforma", help_body(), "", "")
                    return send(self, 200, "text/html; charset=utf-8", markup.encode("utf-8"))
                native_home = path in PORTAL_PATHS and tab in ("", "resumo", "inicio", "início", "overview")
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
                            if tab == "publicacao":
                                summary = getattr(owner, "render_resumo")(self.user())
                                adapted_markup = adapted_markup.replace("</main>", '<section class="publication-summary card"><div class="section-title"><div><h2>Painel geral</h2><p>Resumo de projetos, bancos e infraestrutura autorizada.</p></div></div>' + summary + "</section></main>", 1)
                            if tab == "agentes":
                                try:
                                    identities = getattr(owner, "_oi_panel")(self.user())
                                    adapted_markup = adapted_markup.replace("</main>", identities + "</main>", 1)
                                except Exception:
                                    pass
                            if tab == "admin" and tenant_admin_allowed(self):
                                from cloudif_admin_tenant_delete import render_panel
                                owner = sys.modules.get(handler_class.__module__)
                                user = self.user()
                                panel = render_panel(getattr(owner, "_prod_csrf_token")(user), (query.get("tenant") or [""])[0])
                                adapted_markup = re.sub(
                                    r'<div class="box">\s*<h3>Pesquisar usuário/grupo no AD</h3>.*?</form>\s*</div>',
                                    '', adapted_markup, count=1, flags=re.DOTALL,
                                )
                                adapted_markup = adapted_markup.replace("</main>", '<section class="admin-tools-layout">' + admin_ad_body() + panel + '</section></main>', 1)
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
                if parsed.path not in {
                    "/cloudif/portal/action/admin-delete-project",
                    "/cloudiff/portal/action/admin-delete-project",
                    "/cloudif/portal/action/admin-delete-tenant",
                    "/cloudiff/portal/action/admin-delete-tenant",
                }:
                    return previous_post(self)
                content_length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(content_length)
                form = urllib.parse.parse_qs(raw.decode("utf-8", "ignore"))
                value = lambda key: (form.get(key) or [""])[0].strip()
                if parsed.path.endswith("/action/admin-delete-tenant"):
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
