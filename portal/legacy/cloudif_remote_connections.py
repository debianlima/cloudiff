#!/usr/bin/env python3
"""Project-scoped remote connection inventory and short-lived FRP leases.

The module intentionally does not own authentication. The Portal passes only rows that its
existing ACL already made visible to the authenticated actor. Raw TCP exposure is fail-closed:
a service is activatable only when an edge driver is configured and the service-specific
security precondition is satisfied.
"""
from __future__ import annotations
import base64, html, json, os, random, re, sqlite3, time, urllib.error, urllib.request, uuid
from pathlib import Path

FORGEJO_BASE='https://cloudiff.duckdns.org/git/'
KOMODO_URL='https://komodoiff.duckdns.org/auth/oidc/login'
MCP_URL='https://cloudiff.duckdns.org/cloudiff/mcp'
LEASE_STATES=('reserving','active','released','expired','failed')
SERVICE_DEFS={
 'forgejo_ssh':{'label':'Forgejo · Git por SSH','kind':'tcp','client':'cloudiff-broker.c.forja','local_ip':'127.0.0.1','local_port':2222,'secure_transport':True},
 'postgres':{'label':'PostgreSQL / Supabase','kind':'tcp','client':'cloudiff-broker.c.hospedagem','local_ip':'127.0.0.1','local_port':54400,'secure_transport':False},
}
SAFE_SLUG=re.compile(r'^[a-z0-9][a-z0-9-]{0,79}$')

class BrokerError(RuntimeError):
    def __init__(self, code, status=400, message=''):
        super().__init__(message or code);self.code=code;self.status=status;self.message=message or code

class FrpPanelDriver:
    def __init__(self, base_url, token, server_id='default', timeout=12):
        self.base_url=(base_url or '').rstrip('/');self.token=token or '';self.server_id=server_id or 'default';self.timeout=timeout
    @property
    def configured(self): return bool(self.base_url and self.token and self.server_id)
    def _request(self,path,payload=None,method='POST'):
        if not self.configured: raise BrokerError('edge_unpublished',503,'Edge remoto ainda não configurado.')
        data=None if payload is None else json.dumps(payload,separators=(',',':')).encode()
        req=urllib.request.Request(self.base_url+path,data=data,method=method,headers={'Authorization':'Bearer '+self.token,'Accept':'application/json','Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as r: out=json.load(r)
        except urllib.error.HTTPError as e:
            raise BrokerError('edge_driver_rejected',502,'O edge recusou a configuração.') from e
        except Exception as e:
            raise BrokerError('edge_unavailable',503,'O edge remoto está indisponível.') from e
        if not isinstance(out,dict) or int(out.get('code') or 0)!=200:
            raise BrokerError('edge_driver_failed',502,'O edge não confirmou a operação.')
        body=out.get('body') or {};status=body.get('status') or {}
        if status and int(status.get('code') or 0)!=1:
            raise BrokerError('edge_driver_failed',502,'O edge não confirmou a operação.')
        return body
    def health(self):
        try:
            self._request('/api/v1/platform/baseinfo',None,'GET');return True
        except BrokerError:return False
    def create_tcp(self,name,client_id,local_ip,local_port,remote_port):
        cfg={'proxies':[{'name':name,'type':'tcp','localIP':local_ip,'localPort':int(local_port),'remotePort':int(remote_port)}]}
        encoded=base64.b64encode(json.dumps(cfg,separators=(',',':')).encode()).decode()
        self._request('/api/v1/proxy/create_config',{'clientId':client_id,'serverId':self.server_id,'config':encoded,'overwrite':True})
        return name
    def delete(self,name,client_id):
        self._request('/api/v1/proxy/delete_config',{'clientId':client_id,'serverId':self.server_id,'name':name})
        return True

class RemoteBroker:
    def __init__(self, db_path, cfg=None, driver=None, clock=None):
        self.db_path=str(db_path);self.cfg=dict(cfg or {});self.clock=clock or time.time
        self.edge_host=self.cfg.get('edge_host') or ''
        self.port_start=int(self.cfg.get('port_start') or 24000);self.port_end=int(self.cfg.get('port_end') or 24999)
        self.default_ttl=int(self.cfg.get('default_ttl') or 1800);self.max_ttl=int(self.cfg.get('max_ttl') or 7200)
        self.postgres_tls=bool(self.cfg.get('postgres_tls'))
        self.driver=driver or FrpPanelDriver(self.cfg.get('panel_url',''),self.cfg.get('panel_token',''),self.cfg.get('server_id','default'))
        self._init_db()
    def _conn(self):
        c=sqlite3.connect(self.db_path,timeout=20);c.row_factory=sqlite3.Row;c.execute('pragma busy_timeout=20000');return c
    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True,exist_ok=True)
        c=self._conn();c.executescript('''
        create table if not exists remote_connection_leases(
          lease_id text primary key, project_slug text not null, actor text not null, service text not null,
          driver text not null, driver_ref text not null, client_id text not null,
          edge_host text not null, edge_port integer not null unique, status text not null,
          created_at integer not null, expires_at integer not null, updated_at integer not null,
          check(status in ('reserving','active','released','expired','failed'))
        );
        create index if not exists idx_remote_lease_actor on remote_connection_leases(actor,project_slug,status,expires_at);
        create index if not exists idx_remote_lease_expiry on remote_connection_leases(status,expires_at);
        ''');c.commit();c.close()
    @staticmethod
    def _row_map(rows): return {str(x.get('project_slug') or ''):dict(x) for x in rows or [] if x.get('project_slug')}
    def _ready(self, service, row):
        d=SERVICE_DEFS[service]
        if not self.driver.configured or not self.edge_host:return False,'edge_unpublished'
        if service=='postgres' and not self.postgres_tls:return False,'tls_required'
        if service=='postgres' and not row.get('tenant'):return False,'no_database'
        return True,'ready'
    def _cleanup(self):
        now=int(self.clock());c=self._conn();rows=c.execute("select * from remote_connection_leases where status='active' and expires_at<=?",(now,)).fetchall();c.close();count=0
        for r in rows:
            try:self.driver.delete(r['driver_ref'],r['client_id'])
            except Exception:pass
            c=self._conn();cur=c.execute("update remote_connection_leases set status='expired',updated_at=? where lease_id=? and status='active'",(now,r['lease_id']));c.commit();count+=cur.rowcount;c.close()
        return count
    def web_services(self,row):
        slug=str(row.get('project_slug') or '');owner=str(row.get('owner_user') or '');tenant=str(row.get('tenant') or '')
        out=[{'id':'mcp','label':'Agente MCP','type':'https','state':'available','url':(row.get('instructions') or {}).get('mcp_endpoint') or MCP_URL,'hint':'OAuth pelo CloudIFF; não precisa de porta TCP extra.'},
             {'id':'forgejo_https','label':'Forgejo · HTTPS','type':'https','state':'available','url':FORGEJO_BASE+owner+'/cloudif-'+slug+'.git' if owner else FORGEJO_BASE,'hint':'Clone/push por HTTPS.'},
             {'id':'komodo','label':'Komodo','type':'https','state':'available','url':KOMODO_URL,'hint':'Operação web autenticada.'}]
        if tenant:out.append({'id':'supabase_studio','label':'Supabase Studio','type':'https','state':'available','url':'https://'+tenant+'.cloudiff.duckdns.org/project/default','hint':'Studio web do tenant.'})
        return out
    def inventory(self,rows,actor):
        self._cleanup();projects=[];now=int(self.clock());rm=self._row_map(rows)
        c=self._conn();leases=c.execute("select * from remote_connection_leases where actor=? and status='active' and expires_at>? order by expires_at",(actor,now)).fetchall();c.close();by={(r['project_slug'],r['service']):dict(r) for r in leases}
        for slug,row in rm.items():
            raw=[]
            for sid,d in SERVICE_DEFS.items():
                ready,reason=self._ready(sid,row);lease=by.get((slug,sid))
                item={'id':sid,'label':d['label'],'type':'tcp','state':'active' if lease else ('ready' if ready else reason),'activatable':bool(ready and not lease),'requires_refresh':True}
                if lease:item.update({'lease_id':lease['lease_id'],'host':lease['edge_host'],'port':lease['edge_port'],'expires_at':lease['expires_at'],'remaining_seconds':max(0,lease['expires_at']-now)})
                raw.append(item)
            projects.append({'project_slug':slug,'tenant':row.get('tenant') or '','web':self.web_services(row),'raw':raw})
        return {'ok':True,'projects':projects,'edge':{'configured':bool(self.driver.configured and self.edge_host),'healthy':self.driver.health() if self.driver.configured else False,'host':self.edge_host or None,'port_range':[self.port_start,self.port_end] if self.edge_host else None},'warning':'Conexões remotas são temporárias. A porta pública pode mudar quando a conexão expirar ou for recriada. Antes de conectar, confirme novamente neste painel.','secrets_exposed':False}
    def create_lease(self,rows,actor,slug,service,ttl=None):
        rm=self._row_map(rows);row=rm.get(slug)
        if not row:raise BrokerError('project_denied',403,'Projeto não autorizado.')
        if service not in SERVICE_DEFS:raise BrokerError('service_not_supported',400,'Serviço não suportado.')
        ready,reason=self._ready(service,row)
        if not ready:
            msg={'edge_unpublished':'O edge remoto ainda não está publicado.','tls_required':'PostgreSQL direto permanece bloqueado até o gateway TLS estar ativo.','no_database':'Este projeto não possui banco vinculado.'}.get(reason,reason)
            raise BrokerError(reason,503 if reason=='edge_unpublished' else 409,msg)
        self._cleanup();now=int(self.clock());ttl=max(300,min(int(ttl or self.default_ttl),self.max_ttl));expires=now+ttl
        c=self._conn();existing=c.execute("select * from remote_connection_leases where actor=? and project_slug=? and service=? and status='active' and expires_at>?",(actor,slug,service,now)).fetchone()
        if existing:c.close();return dict(existing)|{'existing':True}
        lease_id='rcl_'+uuid.uuid4().hex[:24];name=('cloudiff-'+slug+'-'+service+'-'+lease_id[-8:])[:64];d=SERVICE_DEFS[service]
        # BEGIN IMMEDIATE + unique edge_port makes concurrent allocation safe.
        c.execute('begin immediate');used={r[0] for r in c.execute("select edge_port from remote_connection_leases where status in ('reserving','active') and expires_at>?",(now,))};span=self.port_end-self.port_start+1;start=random.randrange(span);port=None
        for i in range(span):
            candidate=self.port_start+((start+i)%span)
            if candidate not in used:port=candidate;break
        if port is None:c.rollback();c.close();raise BrokerError('port_pool_exhausted',503,'Não há portas remotas livres.')
        c.execute('insert into remote_connection_leases values(?,?,?,?,?,?,?,?,?,?,?,?,?)',(lease_id,slug,actor,service,'frp-panel',name,d['client'],self.edge_host,port,'reserving',now,expires,now));c.commit();c.close()
        try:self.driver.create_tcp(name,d['client'],d['local_ip'],d['local_port'],port)
        except Exception:
            c=self._conn();c.execute("update remote_connection_leases set status='failed',updated_at=? where lease_id=?",(int(self.clock()),lease_id));c.commit();c.close();raise
        c=self._conn();c.execute("update remote_connection_leases set status='active',updated_at=? where lease_id=? and status='reserving'",(int(self.clock()),lease_id));c.commit();r=c.execute('select * from remote_connection_leases where lease_id=?',(lease_id,)).fetchone();c.close();return dict(r)|{'existing':False}
    def release(self,rows,actor,lease_id):
        allowed=set(self._row_map(rows));c=self._conn();r=c.execute('select * from remote_connection_leases where lease_id=?',(lease_id,)).fetchone();c.close()
        if not r or r['actor']!=actor or r['project_slug'] not in allowed:raise BrokerError('lease_denied',403,'Conexão não autorizada.')
        if r['status']!='active':return {'ok':True,'lease_id':lease_id,'status':r['status'],'existing':True}
        self.driver.delete(r['driver_ref'],r['client_id']);now=int(self.clock());c=self._conn();c.execute("update remote_connection_leases set status='released',updated_at=? where lease_id=?",(now,lease_id));c.commit();c.close();return {'ok':True,'lease_id':lease_id,'status':'released','existing':False}

def config_from_env(getter=None):
    g=getter or os.environ.get
    def val(k,d=''):return g(k,d) if getter is None else (g(k,d) or d)
    return {'panel_url':val('CLOUDIF_REMOTE_FRP_PANEL_URL'),'panel_token':val('CLOUDIF_REMOTE_FRP_PANEL_TOKEN'),'server_id':val('CLOUDIF_REMOTE_FRP_SERVER_ID','default'),'edge_host':val('CLOUDIF_REMOTE_EDGE_HOST'),'port_start':int(val('CLOUDIF_REMOTE_PORT_START','24000')),'port_end':int(val('CLOUDIF_REMOTE_PORT_END','24999')),'default_ttl':int(val('CLOUDIF_REMOTE_DEFAULT_TTL','1800')),'max_ttl':int(val('CLOUDIF_REMOTE_MAX_TTL','7200')),'postgres_tls':str(val('CLOUDIF_REMOTE_POSTGRES_TLS','false')).lower() in ('1','true','yes','on')}

def render_dialog(csrf_token=''):
    # Content is loaded from the project-scoped API; no service secret is embedded in HTML.
    c=html.escape(str(csrf_token),quote=True)
    return f'''<dialog id="remote-connections-dialog" class="remote-connections-dialog" aria-labelledby="remote-connections-title"><div class="remote-connections-head"><div><span class="agent-kicker">Conectividade externa</span><h2 id="remote-connections-title">Conexões remotas</h2><p>Use os endpoints abaixo em Git, IDEs e clientes de banco.</p></div><form method="dialog"><button class="btn light" type="submit">Fechar</button></form></div><div class="remote-connections-body"><div class="remote-warning" data-remote-warning>Carregando política de conexão…</div><div class="remote-project-tabs" data-remote-tabs></div><div data-remote-content><div class="box">Carregando conexões autorizadas…</div></div></div></dialog><script>(()=>{{const d=document.getElementById('remote-connections-dialog'),tabs=d.querySelector('[data-remote-tabs]'),content=d.querySelector('[data-remote-content]'),warn=d.querySelector('[data-remote-warning]');let model=null,active='';const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));const stateLabel=s=>({{active:'Ativa',ready:'Disponível',edge_unpublished:'Edge indisponível',tls_required:'Aguardando TLS',no_database:'Sem banco'}}[s]||s);function draw(){{if(!model)return;warn.textContent=model.warning||'';const ps=model.projects||[];if(!active&&ps[0])active=ps[0].project_slug;tabs.innerHTML=ps.map(p=>`<button type="button" class="btn ${{p.project_slug===active?'':'light'}}" data-project="${{esc(p.project_slug)}}">${{esc(p.project_slug)}}</button>`).join('');tabs.querySelectorAll('button').forEach(b=>b.onclick=()=>{{active=b.dataset.project;draw()}});const p=ps.find(x=>x.project_slug===active);if(!p){{content.innerHTML='<div class="box">Nenhum projeto disponível.</div>';return}};const web=(p.web||[]).map(x=>`<article class="remote-service"><div><span class="pill ok">HTTPS</span><h3>${{esc(x.label)}}</h3><p>${{esc(x.hint)}}</p></div><a class="btn light" target="_blank" rel="noopener" href="${{esc(x.url)}}">Abrir</a></article>`).join('');const raw=(p.raw||[]).map(x=>{{let action='';if(x.state==='active')action=`<div class="remote-endpoint"><code>${{esc(x.host)}}:${{esc(x.port)}}</code><small>Expira em ${{Math.ceil((x.remaining_seconds||0)/60)}} min</small><button class="btn light" type="button" data-copy="${{esc(x.host)}}:${{esc(x.port)}}">Copiar</button><button class="btn light" type="button" data-release="${{esc(x.lease_id)}}">Encerrar</button></div>`;else if(x.activatable)action=`<button class="btn" type="button" data-activate="${{esc(x.id)}}">Ativar por 30 min</button>`;else action=`<span class="pill muted">${{esc(stateLabel(x.state))}}</span>`;let help=x.id==='forgejo_ssh'?'Use este host e porta no Git/SSH. A autenticação continua sendo sua chave SSH do Forgejo.':(x.id==='postgres'?'Use um cliente PostgreSQL com TLS e a credencial do próprio projeto. A senha nunca é exibida neste painel.':'');return `<article class="remote-service"><div><span class="pill">TCP</span><h3>${{esc(x.label)}}</h3><p>${{esc(help)}}</p></div>${{action}}</article>`}}).join('');content.innerHTML=`<section><h3>Web e APIs</h3><div class="remote-service-list">${{web}}</div></section><section><h3>Portas temporárias</h3><div class="remote-service-list">${{raw}}</div></section>`;content.querySelectorAll('[data-copy]').forEach(b=>b.onclick=async()=>{{await navigator.clipboard.writeText(b.dataset.copy);b.textContent='Copiado'}});content.querySelectorAll('[data-activate]').forEach(b=>b.onclick=()=>post('create',{{project_slug:active,service:b.dataset.activate,ttl_seconds:1800}}));content.querySelectorAll('[data-release]').forEach(b=>b.onclick=()=>post('release',{{lease_id:b.dataset.release}}))}}async function load(){{content.innerHTML='<div class="box">Consultando projetos e edge…</div>';const r=await fetch('/cloudiff/portal/api/remote-connections',{{credentials:'same-origin',cache:'no-store',headers:{{Accept:'application/json'}}}});model=await r.json();if(!r.ok||!model.ok)throw new Error(model.message||model.error||'Conexões indisponíveis');draw()}}async function post(op,payload){{const r=await fetch('/cloudiff/portal/api/remote-connections/'+op,{{method:'POST',credentials:'same-origin',headers:{{'Content-Type':'application/json','X-CSRF-Token':'{c}',Accept:'application/json'}},body:JSON.stringify(payload)}}),x=await r.json().catch(()=>({{}}));if(!r.ok){{alert(x.message||x.error||'Operação não concluída');return}}await load()}}window.cloudifRemoteConnectionsLoad=()=>load().catch(e=>{{content.innerHTML='<div class="box"><span class="pill bad">Indisponível</span><p>'+esc(e.message)+'</p></div>'}})}})();</script>'''


def cleanup_cli(argv=None):
    import argparse
    ap=argparse.ArgumentParser(description='Revoke expired CloudIFF remote connection leases')
    ap.add_argument('--db',default=os.environ.get('CLOUDIF_PORTAL_DB','/var/lib/cloudif/portal/cloudif-portal.db'))
    ns=ap.parse_args(argv);broker=RemoteBroker(ns.db,config_from_env());count=broker._cleanup();print('expired_revoked='+str(count));return 0

if __name__=='__main__':
    raise SystemExit(cleanup_cli())
