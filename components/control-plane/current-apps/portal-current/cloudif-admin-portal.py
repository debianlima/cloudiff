#!/usr/bin/env python3
"""CloudIFF portal launcher with canonical authorization and UI normalization."""
from pathlib import Path
import re

_POLICY_OLD = "return bool(user.get('admin') or groups.intersection({'cloudif-tenants-admin','domain admins'}))"
_POLICY_NEW = "return bool(groups.intersection({'cloudif-tenants-admin','cloudif-professor'}))"
_MESSAGE_REPLACEMENTS = (
    ('Área restrita à administração global.', 'Área restrita a CloudIF-Professor ou CloudIF-Tenants-Admin.'),
    ('Acesso restrito à administração global.', 'Acesso restrito a CloudIF-Professor ou CloudIF-Tenants-Admin.'),
)

_ADMIN_LOOKUP_BOX = '''  <div class="box">
    <h3>Busca AD</h3>
    <p class="small">Use a aba Administração para pesquisar usuários/grupos reais no AD antes de vincular.</p>
    <a class="btn light" href="{url('?tab=admin')}">Ir para Administração</a>
  </div>
'''

_TENANT_DETAILS_OLD = '''  <details class="db96-details"><summary>Serviços detectados e permissões</summary><div class="container-grid">{''.join(chips) or '<div class="container-chip"><span class="container-name">sem serviços detectados</span><span class="pill muted">-</span></div>'}</div><div class="action-group"><button class="btn light" type="button" onclick="toggle__Panel('{acl_id}')">Permissões do banco</button><div id="{acl_id}" class="wizard-panel">{tenant_acl_html(tenant, user)}</div></div></details>
'''.replace('toggle__Panel', 'togglePanel')

_TENANT_DETAILS_NEW = '''  <div class="db96-compact-tools">
    <details class="db96-compact db96-services">
      <summary><span><b>Serviços detectados</b><small>Containers que compõem este banco</small></span><span class="db96-summary-count">{len(chips)} serviços</span></summary>
      <div class="db96-service-list">{''.join(chips) or '<div class="container-chip"><span class="container-name">sem serviços detectados</span><span class="pill muted">-</span></div>'}</div>
    </details>
    <details class="db96-compact db96-permissions" data-tenant-permissions="{h(tenant)}">
      <summary><span><b>Permissões do banco</b><small>Adicionar ou retirar usuários e grupos</small></span><span class="db96-summary-action">Gerenciar</span></summary>
      <div class="db96-permissions-content">{tenant_acl_html(tenant, user)}</div>
    </details>
  </div>
'''

_ADMIN_OBSERVABILITY_INJECT = '# CloudIFF v34 environment administration BEGIN\nimport json as _envobs_json\nimport os as _envobs_os\nimport re as _envobs_re\nimport urllib.error as _envobs_urllib_error\nimport urllib.parse as _envobs_urllib_parse\nimport urllib.request as _envobs_urllib_request\n\n_ENVOBS_BACKEND=\'http://127.0.0.1:18260\'\n_ENVOBS_TOKEN=_envobs_os.environ.get(\'CLOUDIFF_ADMIN_OBSERVABILITY_TOKEN\',\'\')\n\ndef _envobs_groups(handler):\n    raw=handler.headers.get(\'X-authentik-groups\') or handler.headers.get(\'X-Authentik-Groups\') or \'\'\n    return {x.strip().lower() for x in raw.replace(\'|\',\',\').split(\',\') if x.strip()}\n\ndef _envobs_admin(handler):\n    return \'cloudif-tenants-admin\' in _envobs_groups(handler)\n\ndef _envobs_json_response(handler,status,payload):\n    body=_envobs_json.dumps(payload,ensure_ascii=False,separators=(\',\',\':\')).encode(\'utf-8\')\n    handler.send_response(status);handler.send_header(\'Content-Type\',\'application/json; charset=utf-8\');handler.send_header(\'Cache-Control\',\'no-store\');handler.send_header(\'X-Content-Type-Options\',\'nosniff\');handler.send_header(\'Content-Length\',str(len(body)));handler.end_headers();handler.wfile.write(body)\n\ndef _envobs_backend(method,path,payload=None):\n    if not _ENVOBS_TOKEN: return 503,{\'ok\':False,\'error\':\'admin_backend_unconfigured\'}\n    data=None if payload is None else _envobs_json.dumps(payload,separators=(\',\',\':\')).encode(\'utf-8\')\n    req=_envobs_urllib_request.Request(_ENVOBS_BACKEND+path,data=data,method=method,headers={\'Authorization\':\'Bearer \'+_ENVOBS_TOKEN,\'Accept\':\'application/json\',\'Content-Type\':\'application/json\'})\n    try:\n        with _envobs_urllib_request.urlopen(req,timeout=5) as r:\n            return int(r.status),_envobs_json.loads(r.read().decode(\'utf-8\'))\n    except _envobs_urllib_error.HTTPError as e:\n        try: payload=_envobs_json.loads(e.read().decode(\'utf-8\'))\n        except Exception: payload={\'ok\':False,\'error\':\'admin_backend_http_error\'}\n        return int(e.code),payload\n    except Exception:\n        return 503,{\'ok\':False,\'error\':\'admin_backend_unavailable\'}\n\ndef _envobs_page(handler,user):\n    if not _envobs_admin(handler):\n        return handler.send_html(page(user,\'admin\',\'<section class="card"><h1>Acesso negado</h1><p>Esta área é exclusiva do grupo CloudIF-Tenants-Admin.</p></section>\'),403)\n    csrf=_prod_csrf_token(user)\n    body=\'\'\'<section class="card env-admin"><div class="section-title"><div><span class="small">Administração do ambiente</span><h1>Saúde da CloudIFF</h1><p>Máquinas, containers e serviços reportados pelos agentes.</p></div><a class="btn light" href="/cloudiff/portal/?tab=admin">Administração de usuários e tenants</a></div><div id="env-admin-status" role="status">Carregando ambiente...</div><div id="env-admin-nodes" class="env-admin-nodes"></div></section>\n<style>.env-admin{display:grid;gap:24px}.env-admin-nodes{display:grid;gap:16px}.env-node{padding:18px;border:1px solid var(--rule);border-radius:14px;background:var(--surface)}.env-node-head{display:flex;justify-content:space-between;gap:16px;align-items:start}.env-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}.env-metrics>div{padding:12px;border:1px solid var(--rule);border-radius:10px}.env-metrics small,.env-metrics strong{display:block}.env-containers{margin-top:12px}.env-containers summary{cursor:pointer;min-height:44px;display:flex;align-items:center}.env-recovery{display:flex;align-items:center;gap:10px;min-height:44px}.env-recovery input{width:24px;height:24px}.env-table{width:100%;border-collapse:collapse}.env-table th,.env-table td{text-align:left;padding:9px;border-bottom:1px solid var(--rule)}@media(max-width:720px){.env-node-head{display:grid}.env-table{display:block;overflow:auto}}</style>\n<script>(()=>{const csrf=__CSRF__,root=document.getElementById(\'env-admin-nodes\'),status=document.getElementById(\'env-admin-status\');const esc=v=>String(v??\'\').replace(/[&<>"\']/g,c=>({\'&\':\'&amp;\',\'<\':\'&lt;\',\'>\':\'&gt;\',\'"\':\'&quot;\',"\'":\'&#39;\'}[c]));const bytes=n=>{n=Number(n||0);for(const u of [\'B\',\'KiB\',\'MiB\',\'GiB\',\'TiB\']){if(n<1024)return (u===\'B\'?Math.round(n):n.toFixed(1))+\' \'+u;n/=1024}return n.toFixed(1)+\' PiB\'};function containers(t){const items=(t?.containers?.items||[]);if(!items.length)return \'<p class="small">Containers: \'+esc(t?.containers?.status||\'sem dados\')+\'.</p>\';return \'<details class="env-containers"><summary>Containers (\'+items.length+\')</summary><div class="table-scroll"><table class="env-table"><thead><tr><th>Container</th><th>CPU</th><th>Memória</th><th>Rede RX/TX</th></tr></thead><tbody>\'+items.map(c=>\'<tr><td>\'+esc(c.name)+\'</td><td>\'+Number(c.cpu_usage_seconds||0).toFixed(1)+\' s</td><td>\'+bytes(c.memory_usage_bytes)+\'</td><td>\'+bytes(c.network_rx_bytes)+\' / \'+bytes(c.network_tx_bytes)+\'</td></tr>\').join(\'\')+\'</tbody></table></div></details>\'}function node(n){const h=n.telemetry?.host||{},available=Number(h.ram_available_bytes||0),total=Number(h.ram_total_bytes||0);return \'<article class="env-node" data-node="\'+esc(n.node_id)+\'"><div class="env-node-head"><div><h2>\'+esc(n.hostname)+\'</h2><p>\'+esc(n.role)+\' · agent \'+esc(h.agent_version||\'sem versão\')+\' · último heartbeat \'+esc(n.last_seen_at)+\'</p></div><label class="env-recovery"><input type="checkbox" \'+(n.automatic_reboot_enabled?\'checked\':\'\')+\'><span>Reboot automático de recuperação</span></label></div><div class="env-metrics"><div><small>CPU / carga 1m</small><strong>\'+esc(h.cpu_count||0)+\' / \'+Number(h.load1||0).toFixed(2)+\'</strong></div><div><small>RAM disponível</small><strong>\'+bytes(available)+\' / \'+bytes(total)+\'</strong></div><div><small>Disco livre</small><strong>\'+bytes(h.root_available_bytes)+\' / \'+bytes(h.root_capacity_bytes)+\'</strong></div><div><small>Uptime</small><strong>\'+Math.floor(Number(h.uptime_seconds||0)/3600)+\' h</strong></div></div>\'+containers(n.telemetry)+\'</article>\'}async function load(){status.textContent=\'Carregando ambiente...\';try{const r=await fetch(\'/cloudiff/portal/api/admin-observability\',{credentials:\'same-origin\',headers:{Accept:\'application/json\'}}),d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||(\'HTTP \'+r.status));root.innerHTML=(d.nodes||[]).map(node).join(\'\')||\'<p>Nenhum node observado.</p>\';root.querySelectorAll(\'.env-recovery input\').forEach(input=>input.onchange=async()=>{const article=input.closest(\'[data-node]\'),nodeId=article.dataset.node;input.disabled=true;status.textContent=\'Atualizando política de \'+article.querySelector(\'h2\').textContent+\'...\';try{const body=new URLSearchParams({csrf_token:csrf,node_id:nodeId,automatic_reboot_enabled:input.checked?\'1\':\'0\'});const rr=await fetch(\'/cloudiff/portal/action/node-recovery\',{method:\'POST\',credentials:\'same-origin\',headers:{\'Content-Type\':\'application/x-www-form-urlencoded;charset=UTF-8\',\'X-CSRF-Token\':csrf},body}),dd=await rr.json();if(!rr.ok||!dd.ok)throw new Error(dd.error||(\'HTTP \'+rr.status));status.textContent=\'Política atualizada. Revisão \'+dd.revision+\'.\'}catch(e){input.checked=!input.checked;status.textContent=\'Falha: \'+e.message}finally{input.disabled=false}});status.textContent=(d.nodes||[]).length+\' node(s) observado(s).\'}catch(e){root.innerHTML=\'\';status.textContent=\'Falha ao carregar ambiente: \'+e.message}}load()})();</script>\'\'\'.replace(\'__CSRF__\',_envobs_json.dumps(csrf))\n    return handler.send_html(page(user,\'admin\',body),200)\n\nif \'Portal\' in globals() and not globals().get(\'_envobs_wrapped\'):\n    _envobs_prev_get=Portal.do_GET;_envobs_prev_post=Portal.do_POST\n    def _envobs_get(self):\n        parsed=_envobs_urllib_parse.urlparse(self.path);path=parsed.path.rstrip(\'/\') or \'/\'\n        if path==\'/admin\': return _envobs_page(self,self.user())\n        if path in (\'/cloudiff/portal/api/admin-observability\',\'/cloudif/portal/api/admin-observability\'):\n            if not _envobs_admin(self): return _envobs_json_response(self,403,{\'ok\':False,\'error\':\'forbidden\'})\n            status,payload=_envobs_backend(\'GET\',\'/v1/environment\');return _envobs_json_response(self,status,payload)\n        if path in (\'/cloudiff/portal/api/node-recovery-policy\',\'/cloudif/portal/api/node-recovery-policy\'):\n            q=_envobs_urllib_parse.parse_qs(parsed.query);node=(q.get(\'node_id\') or [\'\'])[0].strip()\n            if not _envobs_re.fullmatch(r\'[0-9a-fA-F-]{36}\',node): return _envobs_json_response(self,400,{\'ok\':False,\'error\':\'invalid_node_id\'})\n            status,payload=_envobs_backend(\'GET\',\'/v1/nodes/\'+node+\'/policy\');return _envobs_json_response(self,status,payload)\n        return _envobs_prev_get(self)\n    def _envobs_post(self):\n        parsed=_envobs_urllib_parse.urlparse(self.path);path=parsed.path.rstrip(\'/\')\n        if path not in (\'/cloudiff/portal/action/node-recovery\',\'/cloudif/portal/action/node-recovery\'): return _envobs_prev_post(self)\n        if not _envobs_admin(self): return _envobs_json_response(self,403,{\'ok\':False,\'error\':\'forbidden\'})\n        if \'_cloudif_security_valid_origin\' in globals() and not _cloudif_security_valid_origin(self): return _envobs_json_response(self,403,{\'ok\':False,\'error\':\'invalid_origin\'})\n        length=int(self.headers.get(\'Content-Length\',\'0\') or 0)\n        if length<1 or length>65536:return _envobs_json_response(self,413,{\'ok\':False,\'error\':\'invalid_body\'})\n        form=_envobs_urllib_parse.parse_qs(self.rfile.read(length).decode(\'utf-8\',\'ignore\'));val=lambda k:(form.get(k) or [\'\'])[0].strip();user=self.user()\n        provided=val(\'csrf_token\') or (self.headers.get(\'X-CSRF-Token\') or \'\').strip()\n        if not _prod_csrf_equal(provided,_prod_csrf_token(user)): return _envobs_json_response(self,403,{\'ok\':False,\'error\':\'invalid_csrf\'})\n        node=val(\'node_id\');enabled=val(\'automatic_reboot_enabled\') in (\'1\',\'true\',\'on\',\'yes\')\n        if not _envobs_re.fullmatch(r\'[0-9a-fA-F-]{36}\',node):return _envobs_json_response(self,400,{\'ok\':False,\'error\':\'invalid_node_id\'})\n        status,payload=_envobs_backend(\'POST\',\'/v1/nodes/\'+node+\'/recovery\',{\'automatic_reboot_enabled\':enabled,\'actor\':str(user.get(\'username\') or \'admin\')[:128]});return _envobs_json_response(self,status,payload)\n    Portal.do_GET=_envobs_get;Portal.do_POST=_envobs_post;_envobs_wrapped=True\n# CloudIFF v34 environment administration END\n'


def _replace_all(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise RuntimeError(f'Contrato visual não encontrado: {label}')
    return source.replace(old, new)


def _load_patched_portal():
    candidates = (
        Path(__file__).with_name('cloudif-admin-portal-base.py'),
        Path('/srv/cloudif/portal/cloudif-admin-portal-base.py'),
        Path('/srv/cloudif/current-apps/portal-current/cloudif-admin-portal-base.py'),
    )
    source_path = next((path for path in candidates if path.is_file()), None)
    if source_path is None:
        raise RuntimeError('Arquivo-base do Portal CloudIFF não encontrado.')

    source = source_path.read_text(encoding='utf-8')
    if _POLICY_OLD in source:
        source = source.replace(_POLICY_OLD, _POLICY_NEW, 1)
    elif _POLICY_NEW not in source:
        raise RuntimeError('Contrato de autorização da exclusão divergiu do esperado.')
    for old, new in _MESSAGE_REPLACEMENTS:
        if old in source:
            source = source.replace(old, new)
    source = _replace_all(source, _ADMIN_LOOKUP_BOX, '', 'atalho de administração do AD no banco')
    source, removed_ad_boxes = re.subn(
        r'  <div class="box">\s*<h3>Busca AD</h3>.*?</div>\n?',
        '',
        source,
        flags=re.DOTALL,
    )
    if '<h3>Busca AD</h3>' in source or 'Ir para Administração</a>' in source:
        raise RuntimeError('Atalhos residuais de Administração do AD encontrados no banco.')
    source = _replace_all(source, _TENANT_DETAILS_OLD, _TENANT_DETAILS_NEW, 'serviços e permissões do tenant')
    owner_remove_old = '''        elif op == "remove":
            rid = val("id")
            row = con.execute("SELECT * FROM tenant_acl WHERE id=?", (rid,)).fetchone()
            con.execute("DELETE FROM tenant_acl WHERE id=?", (rid,))
            con.commit()
            log_action(user["username"], "tenant_acl_remove", row["tenant"] if row else rid, 0, str(dict(row)) if row else "", "")
'''
    owner_remove_new = '''        elif op == "remove":
            rid = val("id")
            row = con.execute("SELECT * FROM tenant_acl WHERE id=?", (rid,)).fetchone()
            if row and row["subject_type"] == "user" and norm(row["subject"]) == norm(row["tenant"]):
                con.close()
                log_action(user["username"], "tenant_acl_remove_owner_blocked", row["tenant"], 1, str(dict(row)), "proprietário imutável")
                return self.send_html(page(user, "bancos", '<div class="card"><p class="pill bad">O proprietário do banco não pode ser removido.</p><a class="btn light" href="/?tab=bancos">Voltar</a></div>'), 409)
            con.execute("DELETE FROM tenant_acl WHERE id=?", (rid,))
            con.commit()
            log_action(user["username"], "tenant_acl_remove", row["tenant"] if row else rid, 0, str(dict(row)) if row else "", "")
'''
    source = _replace_all(source, owner_remove_old, owner_remove_new, 'proteção do proprietário do tenant')
    marker='\nif __name__ == \"__main__\":\n'
    if marker not in source:
        raise RuntimeError('Contrato de inicialização do Portal divergiu do esperado.')
    source=source.replace(marker,'\n'+_ADMIN_OBSERVABILITY_INJECT+marker,1)
    return source, source_path


_source, _source_path = _load_patched_portal()
globals()['__file__'] = str(_source_path)
exec(compile(_source, str(_source_path), 'exec'), globals(), globals())


def tenant_acl_html(tenant, user):
    """Renderiza o proprietário natural como vínculo obrigatório e ACLs adicionais removíveis."""
    rows = tenant_acl_rows(tenant)
    owner = (tenant or '').strip()
    extra_rows = [
        row for row in rows
        if not (row['subject_type'] == 'user' and norm(row['subject']) == norm(owner))
    ]
    owner_row = (
        f'<tr class="tenant-owner-row"><td>Proprietário</td><td><strong>{h(owner)}</strong>'
        '<span class="pill ok tenant-owner-badge">Dono do banco</span></td>'
        '<td><span class="tenant-owner-lock" title="O proprietário não pode ser removido">Protegido</span></td></tr>'
    )
    trs = owner_row
    for row in extra_rows:
        remove = ''
        if user['admin']:
            remove = f'''<form method="post" action="{url('/action/tenant_acl')}" style="display:inline">
  <input type="hidden" name="op" value="remove">
  <input type="hidden" name="id" value="{h(row['id'])}">
  <button class="btn red" type="submit">Remover</button>
</form>'''
        kind = 'Usuário' if row['subject_type'] == 'user' else 'Grupo'
        trs += f'<tr><td>{h(kind)}</td><td>{h(row["subject"])}</td><td>{remove}</td></tr>'
    table = f'<table class="tenant-acl-table"><tr><th>Vínculo</th><th>Usuário/Grupo</th><th>Ação</th></tr>{trs}</table>'
    if not user['admin']:
        return table
    return table + f'''<div class="grid2">
  <div class="box">
    <h3>Adicionar permissão ao banco</h3>
    <form method="post" action="{url('/action/tenant_acl')}">
      <input type="hidden" name="op" value="add">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      <label>Tipo</label>
      <select name="subject_type"><option value="user">Usuário</option><option value="group">Grupo</option></select>
      <label>Usuário ou grupo</label>
      <input name="subject" placeholder="Digite para pesquisar no AD">
      <button class="btn" type="submit">Adicionar</button>
    </form>
  </div>
</div>'''
