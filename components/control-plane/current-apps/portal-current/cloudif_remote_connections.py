#!/usr/bin/env python3
"""CloudIFF 443-only remote access broker.

Only TCP/443 is public. The browser activates a short project-scoped SSH gateway lease,
receives a one-time Ed25519 private key, and uses standard OpenSSH/DBeaver/IDE SSH
forwarding. Internal service ports never become public listeners.
"""
from __future__ import annotations
import hashlib, html, hmac, json, os, re, secrets, sqlite3, subprocess, tempfile, time, uuid
from pathlib import Path

FORGEJO_BASE='https://cloudiff.duckdns.org/git/'
KOMODO_URL='https://komodoiff.duckdns.org/auth/oidc/login'
MCP_URL='https://cloudiff.duckdns.org/cloudiff/mcp'
FORGEJO_SSH_TARGET=('10.62.91.2',2222)
POSTGRES_HOST='10.62.92.7'
TENANT_ROOT=Path('/srv/cloudif/tenants')
SAFE_TENANT=re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$')
POOL_PREFIX='cifremote'
POOL_SIZE=256

class BrokerError(RuntimeError):
    def __init__(self,code,status=400,message=''):
        super().__init__(message or code);self.code=code;self.status=status;self.message=message or code

def _read_env_value(path,key):
    try:
        for line in Path(path).read_text(errors='ignore').splitlines():
            if line.startswith(key+'='):
                return line.split('=',1)[1].strip().strip('"').strip("'")
    except Exception:pass
    return ''

def tenant_postgres_port(tenant):
    if not tenant or not SAFE_TENANT.fullmatch(str(tenant)):return None
    raw=_read_env_value(TENANT_ROOT/str(tenant)/'.env','POSTGRES_PORT')
    try:p=int(raw)
    except Exception:return None
    return p if 1024<=p<=65535 else None

def _fingerprint(public_key):
    parts=str(public_key).strip().split()
    if len(parts)<2:raise BrokerError('invalid_public_key',500,'Chave temporária inválida.')
    import base64
    try:blob=base64.b64decode(parts[1]+'===')
    except Exception as e:raise BrokerError('invalid_public_key',500,'Chave temporária inválida.') from e
    return 'SHA256:'+base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip('=')

def generate_ephemeral_key():
    with tempfile.TemporaryDirectory(prefix='cloudiff-remote-key-') as td:
        key=Path(td)/'id_ed25519'
        cp=subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-C','cloudiff-temporary-remote-access','-f',str(key)],capture_output=True,text=True,timeout=20)
        if cp.returncode!=0:raise BrokerError('key_generation_failed',503,'Não foi possível gerar a chave temporária.')
        private=key.read_text();public=key.with_suffix('.pub').read_text().strip()
    return private,public,_fingerprint(public)

class RemoteBroker:
    def __init__(self,db_path,cfg=None,clock=None):
        self.db_path=str(db_path);self.cfg=dict(cfg or {});self.clock=clock or time.time
        self.gateway_host=self.cfg.get('gateway_host') or 'cloudiff.duckdns.org'
        self.gateway_port=int(self.cfg.get('gateway_port') or 443)
        self.default_ttl=int(self.cfg.get('default_ttl') or 1800);self.max_ttl=int(self.cfg.get('max_ttl') or 7200)
        self.enabled=bool(self.cfg.get('gateway_enabled',True))
        self._init_db()
    def _conn(self):
        c=sqlite3.connect(self.db_path,timeout=20);c.row_factory=sqlite3.Row;c.execute('pragma busy_timeout=20000');return c
    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True,exist_ok=True)
        c=self._conn();c.executescript('''
        create table if not exists remote_gateway_leases(
          lease_id text primary key, project_slug text not null, actor text not null,
          gateway_user text not null, ssh_public_key text not null, ssh_fingerprint text not null unique,
          targets_json text not null, status text not null,
          created_at integer not null, expires_at integer not null, updated_at integer not null,
          check(status in ('active','released','expired','failed'))
        );
        create unique index if not exists idx_remote_gateway_user_active
          on remote_gateway_leases(gateway_user) where status='active';
        create index if not exists idx_remote_gateway_actor
          on remote_gateway_leases(actor,project_slug,status,expires_at);
        create index if not exists idx_remote_gateway_expiry
          on remote_gateway_leases(status,expires_at);
        ''');c.commit();c.close()
    @staticmethod
    def _row_map(rows):return {str(x.get('project_slug') or ''):dict(x) for x in rows or [] if x.get('project_slug')}
    def _cleanup(self):
        now=int(self.clock());c=self._conn();cur=c.execute("update remote_gateway_leases set status='expired',updated_at=? where status='active' and expires_at<=?",(now,now));c.commit();n=cur.rowcount;c.close();return n
    def _targets(self,row):
        out=[{'id':'forgejo_ssh','label':'Forgejo · Git por SSH','connector':'direct','gateway_host':FORGEJO_SSH_TARGET[0],'gateway_port':FORGEJO_SSH_TARGET[1],'upstream_host':FORGEJO_SSH_TARGET[0],'upstream_port':FORGEJO_SSH_TARGET[1],'local_port':12222,'auth':'Chave SSH cadastrada no Forgejo'}]
        tenant=str(row.get('tenant') or '')
        p=tenant_postgres_port(tenant)
        if p:
            # Hospedagem opens this relay only on Mauricio loopback, over its outbound SSH/443 connector.
            out.append({'id':'postgres','label':'PostgreSQL / Supabase','connector':'hospedagem','gateway_host':'127.0.0.1','gateway_port':p,'upstream_host':'127.0.0.1','upstream_port':p,'local_port':15432,'auth':'Credencial PostgreSQL do projeto'})
        return out
    @staticmethod
    def _public_targets(targets):
        return [{k:t.get(k) for k in ('id','label','local_port','auth')} for t in targets]
    def web_services(self,row):
        slug=str(row.get('project_slug') or '');owner=str(row.get('owner_user') or '');tenant=str(row.get('tenant') or '')
        out=[{'id':'mcp','label':'Agente MCP','type':'https','state':'available','url':(row.get('instructions') or {}).get('mcp_endpoint') or MCP_URL,'hint':'OAuth pelo CloudIFF; usa HTTPS/443.'},
             {'id':'forgejo_https','label':'Forgejo · HTTPS','type':'https','state':'available','url':FORGEJO_BASE+owner+'/cloudif-'+slug+'.git' if owner else FORGEJO_BASE,'hint':'Clone/push por HTTPS.'},
             {'id':'komodo','label':'Komodo','type':'https','state':'available','url':KOMODO_URL,'hint':'Operação web autenticada.'}]
        if tenant:out.append({'id':'supabase_studio','label':'Supabase Studio','type':'https','state':'available','url':'https://'+tenant+'.cloudiff.duckdns.org/project/default','hint':'Studio web do tenant.'})
        return out
    def inventory(self,rows,actor):
        self._cleanup();now=int(self.clock());rm=self._row_map(rows);c=self._conn();active=c.execute("select * from remote_gateway_leases where actor=? and status='active' and expires_at>? order by expires_at",(actor,now)).fetchall();c.close();by={r['project_slug']:dict(r) for r in active}
        projects=[]
        for slug,row in rm.items():
            lease=by.get(slug);targets=self._targets(row);access={'state':'active' if lease else ('ready' if self.enabled else 'disabled'),'activatable':bool(self.enabled and not lease),'gateway_host':self.gateway_host,'gateway_port':self.gateway_port,'targets':self._public_targets(targets),'requires_key':True}
            if lease:access.update({'lease_id':lease['lease_id'],'gateway_user':lease['gateway_user'],'expires_at':lease['expires_at'],'remaining_seconds':max(0,lease['expires_at']-now),'private_key_available':False})
            projects.append({'project_slug':slug,'tenant':row.get('tenant') or '','web':self.web_services(row),'remote_access':access})
        return {'ok':True,'projects':projects,'gateway':{'enabled':self.enabled,'host':self.gateway_host if self.enabled else None,'port':self.gateway_port if self.enabled else None,'public_ports':[443] if self.enabled else []},'warning':'A única porta pública é 443. Os destinos do projeto permanecem internos e só podem ser alcançados pelo túnel SSH temporário. A chave é exibida uma única vez na ativação.','secrets_exposed':False}
    def _free_gateway_user(self,c,now):
        used={r[0] for r in c.execute("select gateway_user from remote_gateway_leases where status='active' and expires_at>?",(now,))}
        start=secrets.randbelow(POOL_SIZE)
        for i in range(POOL_SIZE):
            u=f'{POOL_PREFIX}{((start+i)%POOL_SIZE)+1:03d}'
            if u not in used:return u
        raise BrokerError('gateway_pool_exhausted',503,'Não há sessões remotas livres no momento.')
    def create_lease(self,rows,actor,slug,ttl=None,rotate=False):
        if not self.enabled:raise BrokerError('gateway_disabled',503,'Gateway remoto indisponível.')
        row=self._row_map(rows).get(slug)
        if not row:raise BrokerError('project_denied',403,'Projeto não autorizado.')
        targets=self._targets(row)
        if not targets:raise BrokerError('no_remote_targets',409,'Este projeto não possui destinos remotos disponíveis.')
        self._cleanup();now=int(self.clock());ttl=max(300,min(int(ttl or self.default_ttl),self.max_ttl));expires=now+ttl
        c=self._conn();existing=c.execute("select * from remote_gateway_leases where actor=? and project_slug=? and status='active' and expires_at>?",(actor,slug,now)).fetchone()
        if existing and not rotate:
            out=dict(existing);out.update({'existing':True,'private_key':None,'key_filename':None});c.close();return out
        if existing and rotate:c.execute("update remote_gateway_leases set status='released',updated_at=? where lease_id=?",(now,existing['lease_id']));c.commit()
        private,public,fingerprint=generate_ephemeral_key();c.execute('begin immediate');gateway_user=self._free_gateway_user(c,now);lease_id='rga_'+uuid.uuid4().hex[:24]
        c.execute('insert into remote_gateway_leases values(?,?,?,?,?,?,?,?,?,?,?)',(lease_id,slug,actor,gateway_user,public,fingerprint,json.dumps(targets,separators=(',',':')),'active',now,expires,now));c.commit();c.close()
        return {'lease_id':lease_id,'project_slug':slug,'actor':actor,'gateway_user':gateway_user,'ssh_public_key':public,'ssh_fingerprint':fingerprint,'targets_json':json.dumps(targets,separators=(',',':')),'status':'active','created_at':now,'expires_at':expires,'updated_at':now,'existing':False,'private_key':private,'key_filename':f'cloudiff-{slug}-{lease_id[-6:]}.key','gateway_host':self.gateway_host,'gateway_port':self.gateway_port,'targets':targets}
    def release(self,rows,actor,lease_id):
        allowed=set(self._row_map(rows));c=self._conn();r=c.execute('select * from remote_gateway_leases where lease_id=?',(lease_id,)).fetchone()
        if not r or r['actor']!=actor or r['project_slug'] not in allowed:c.close();raise BrokerError('lease_denied',403,'Conexão não autorizada.')
        if r['status']!='active':out={'ok':True,'lease_id':lease_id,'status':r['status'],'existing':True};c.close();return out
        now=int(self.clock());c.execute("update remote_gateway_leases set status='released',updated_at=? where lease_id=?",(now,lease_id));c.commit();c.close();return {'ok':True,'lease_id':lease_id,'status':'released','existing':False}
    def authorize_gateway_key(self,gateway_user,key_type,key_blob):
        self._cleanup();now=int(self.clock());offered=f'{key_type} {key_blob}'.strip()
        try:fp=_fingerprint(offered)
        except BrokerError:return None
        c=self._conn();r=c.execute("select * from remote_gateway_leases where gateway_user=? and ssh_fingerprint=? and status='active' and expires_at>?",(gateway_user,fp,now)).fetchone();c.close()
        if not r:return None
        targets=json.loads(r['targets_json']);opts=['no-agent-forwarding','no-X11-forwarding','no-pty','no-user-rc']
        for t in targets:opts.append(f'permitopen="{t["gateway_host"]}:{int(t["gateway_port"])}"')
        return ','.join(opts)+' '+r['ssh_public_key']
    def active_gateway_users(self):
        # Read-only feed for the gateway cache. Avoid cleanup writes on the SSH auth path.
        now=int(self.clock());c=self._conn();rows=c.execute("select gateway_user,lease_id,project_slug,ssh_public_key,ssh_fingerprint,targets_json,expires_at from remote_gateway_leases where status='active' and expires_at>? order by gateway_user",(now,)).fetchall();c.close();return [dict(r) for r in rows]

def config_from_env(getter=None):
    g=getter or os.environ.get
    def val(k,d=''):return g(k,d) if getter is None else (g(k,d) or d)
    return {'gateway_host':val('CLOUDIF_REMOTE_GATEWAY_HOST','cloudiff.duckdns.org'),'gateway_port':int(val('CLOUDIF_REMOTE_GATEWAY_PORT','443')),'gateway_enabled':str(val('CLOUDIF_REMOTE_GATEWAY_ENABLED','true')).lower() in ('1','true','yes','on'),'default_ttl':int(val('CLOUDIF_REMOTE_DEFAULT_TTL','1800')),'max_ttl':int(val('CLOUDIF_REMOTE_MAX_TTL','7200'))}

def verify_internal_request(client_ip,authorization,cfg_getter=None):
    g=cfg_getter or os.environ.get;allowed={x.strip() for x in str(g('CLOUDIF_REMOTE_GATEWAY_ALLOWED_IPS','10.62.91.3')).split(',') if x.strip()};token=str(g('CLOUDIF_REMOTE_GATEWAY_TOKEN',''))
    return bool(token and client_ip in allowed and hmac.compare_digest(str(authorization or ''),'Bearer '+token))

def _commands(lease):
    targets=lease.get('targets') or json.loads(lease.get('targets_json') or '[]');user=lease['gateway_user'];host=lease.get('gateway_host') or 'cloudiff.duckdns.org';port=int(lease.get('gateway_port') or 443);key=lease.get('key_filename') or 'cloudiff-remote.key'
    forwards=' '.join(f'-L {int(t["local_port"])}:{t["gateway_host"]}:{int(t["gateway_port"])}' for t in targets)
    return {'linux':f'chmod 600 {key} && ssh -N -p {port} -i ./{key} {forwards} {user}@{host}','windows':f'ssh -N -p {port} -i .\\{key} {forwards} {user}@{host}'}

def public_lease_payload(lease):
    targets=lease.get('targets') or json.loads(lease.get('targets_json') or '[]');out={k:lease.get(k) for k in ('lease_id','project_slug','gateway_user','status','expires_at','existing','gateway_host','gateway_port','key_filename')};out['targets']=RemoteBroker._public_targets(targets);out['commands']=_commands(lease)
    if lease.get('private_key'):out['private_key']=lease['private_key'];out['one_time_key_delivery']=True
    else:out['private_key']=None;out['one_time_key_delivery']=False
    return out

def render_dialog(csrf_token=''):
    c=html.escape(str(csrf_token),quote=True)
    return f'''<dialog id="remote-connections-dialog" class="remote-connections-dialog" aria-labelledby="remote-connections-title"><div class="remote-connections-head"><div><span class="agent-kicker">Acesso remoto · 443</span><h2 id="remote-connections-title">Conexões remotas</h2><p>HTTPS e túnel SSH compartilham somente a porta pública 443.</p></div><form method="dialog"><button class="btn light" type="submit">Fechar</button></form></div><div class="remote-connections-body"><div class="remote-warning" data-remote-warning>Carregando política de conexão…</div><div class="remote-project-tabs" data-remote-tabs></div><div data-remote-content><div class="box">Carregando conexões autorizadas…</div></div></div></dialog><script>(()=>{{const d=document.getElementById('remote-connections-dialog'),tabs=d.querySelector('[data-remote-tabs]'),content=d.querySelector('[data-remote-content]'),warn=d.querySelector('[data-remote-warning]');let model=null,active='',lastKey=null;const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));const copy=async v=>navigator.clipboard.writeText(v);function downloadKey(name,text){{const b=new Blob([text],{{type:'application/octet-stream'}}),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}}function targetHelp(t){{if(t.id==='postgres')return `DBeaver/psql: após abrir o túnel, conecte em 127.0.0.1:${{t.local_port}}. O destino interno permanece privado.`;if(t.id==='forgejo_ssh')return `Git SSH: após abrir o túnel, use 127.0.0.1:${{t.local_port}} e sua chave normal do Forgejo.`;return ''}}function draw(){{if(!model)return;warn.textContent=model.warning||'';const ps=model.projects||[];if(!active&&ps[0])active=ps[0].project_slug;tabs.innerHTML=ps.map(p=>`<button type="button" class="btn ${{p.project_slug===active?'':'light'}}" data-project="${{esc(p.project_slug)}}">${{esc(p.project_slug)}}</button>`).join('');tabs.querySelectorAll('button').forEach(b=>b.onclick=()=>{{active=b.dataset.project;lastKey=null;draw()}});const p=ps.find(x=>x.project_slug===active);if(!p){{content.innerHTML='<div class="box">Nenhum projeto disponível.</div>';return}};const web=(p.web||[]).map(x=>`<article class="remote-service"><div><span class="pill ok">HTTPS · 443</span><h3>${{esc(x.label)}}</h3><p>${{esc(x.hint)}}</p></div><a class="btn light" target="_blank" rel="noopener" href="${{esc(x.url)}}">Abrir</a></article>`).join('');const a=p.remote_access||{{}},targets=(a.targets||[]).map(t=>`<article class="remote-service"><div><span class="pill">Túnel SSH</span><h3>${{esc(t.label)}}</h3><p>${{esc(targetHelp(t))}}</p></div><div class="remote-endpoint"><code>127.0.0.1:${{esc(t.local_port)}}</code><small>Gateway externo: ${{esc(a.gateway_host)}}:${{esc(a.gateway_port)}}</small></div></article>`).join('');let gate='';if(a.state==='active'){{gate=`<article class="remote-access-card"><div><span class="pill ok">Ativo</span><h3>Gateway ${{esc(a.gateway_host)}}:${{esc(a.gateway_port)}}</h3><p>Usuário temporário: <code>${{esc(a.gateway_user)}}</code> · expira em ${{Math.ceil((a.remaining_seconds||0)/60)}} min.</p><p class="small">A chave privada é entregue somente no momento da ativação. Se você recarregou a página e perdeu a chave, gere uma nova.</p></div><div class="remote-access-actions"><button class="btn light" data-rotate>Gerar nova chave</button><button class="btn light" data-release="${{esc(a.lease_id)}}">Encerrar</button></div></article>`}}else if(a.activatable)gate=`<article class="remote-access-card"><div><span class="pill info">443 somente</span><h3>Ativar túnel por 30 minutos</h3><p>Será gerada uma chave SSH temporária. Nenhuma porta adicional será aberta no firewall.</p></div><button class="btn" data-activate>Ativar acesso</button></article>`;else gate='<div class="box"><span class="pill bad">Indisponível</span><p>Gateway remoto desabilitado.</p></div>';content.innerHTML=`<section><h3>Acesso temporário</h3>${{gate}}<div data-key-delivery></div></section><section><h3>Serviços pelo túnel</h3><div class="remote-service-list">${{targets}}</div></section><section><h3>Web e APIs</h3><div class="remote-service-list">${{web}}</div></section>`;const kd=content.querySelector('[data-key-delivery]');if(lastKey&&lastKey.project_slug===active){{kd.innerHTML=`<article class="remote-key-delivery"><span class="pill warn">Entrega única da chave</span><h3>Salve a chave agora</h3><p>Arquivo sugerido: <code>${{esc(lastKey.key_filename)}}</code></p><div class="remote-access-actions"><button class="btn" data-download>Baixar chave</button><button class="btn light" data-copy-linux>Copiar comando Linux/macOS</button><button class="btn light" data-copy-win>Copiar comando Windows</button></div><pre>${{esc(lastKey.commands.linux)}}</pre></article>`;kd.querySelector('[data-download]').onclick=()=>downloadKey(lastKey.key_filename,lastKey.private_key);kd.querySelector('[data-copy-linux]').onclick=()=>copy(lastKey.commands.linux);kd.querySelector('[data-copy-win]').onclick=()=>copy(lastKey.commands.windows)}}content.querySelector('[data-activate]')?.addEventListener('click',()=>post('create',{{project_slug:active,ttl_seconds:1800}}));content.querySelector('[data-rotate]')?.addEventListener('click',()=>post('create',{{project_slug:active,ttl_seconds:1800,rotate:true}}));content.querySelectorAll('[data-release]').forEach(b=>b.onclick=()=>post('release',{{lease_id:b.dataset.release}}))}}async function load(){{content.innerHTML='<div class="box">Consultando projetos e gateway…</div>';const r=await fetch('/cloudiff/portal/api/remote-connections',{{credentials:'same-origin',cache:'no-store',headers:{{Accept:'application/json'}}}});model=await r.json();if(!r.ok||!model.ok)throw new Error(model.message||model.error||'Conexões indisponíveis');draw()}}async function post(op,payload){{const r=await fetch('/cloudiff/portal/api/remote-connections/'+op,{{method:'POST',credentials:'same-origin',headers:{{'Content-Type':'application/json','X-CSRF-Token':'{c}',Accept:'application/json'}},body:JSON.stringify(payload)}}),x=await r.json().catch(()=>({{}}));if(!r.ok){{alert(x.message||x.error||'Operação não concluída');return}}if(op==='create'&&x.lease?.private_key)lastKey=x.lease;else if(op==='release')lastKey=null;await load();if(op==='create'&&x.lease?.private_key){{lastKey=x.lease;draw()}}}}window.cloudifRemoteConnectionsLoad=()=>load().catch(e=>{{content.innerHTML='<div class="box"><span class="pill bad">Indisponível</span><p>'+esc(e.message)+'</p></div>'}})}})();</script>'''

def cleanup_cli(argv=None):
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--db',default=os.environ.get('CLOUDIF_PORTAL_DB','/var/lib/cloudif/portal/cloudif-portal.db'));ns=ap.parse_args(argv);print('expired_revoked='+str(RemoteBroker(ns.db,config_from_env())._cleanup()));return 0

if __name__=='__main__':raise SystemExit(cleanup_cli())
