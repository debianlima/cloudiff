#!/usr/bin/env python3
import os,sqlite3,json,hmac,time,secrets,hashlib,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
SUPABASE_BASIC_SCOPES=['supabase:database-read','supabase:auth-read','supabase:storage-read']
SUPABASE_ADMIN_SCOPES=['supabase:admin-read','supabase:change-plan','approval:request-supabase','supabase:change-execute']
SUPABASE_ALL_SCOPES=SUPABASE_BASIC_SCOPES+SUPABASE_ADMIN_SCOPES
PROJECT_DISCOVERY_SCOPES=['workspace:detect-multiservice','project:configuration-read']
PROJECT_CHANGE_SET_SCOPES=['workspace:change-set-plan','approval:request-change-set','forgejo:propose-change-set']
PROJECT_BUILD_READ_SCOPES=['build:multiservice-plan']
PROJECT_BUILD_WRITE_SCOPES=['approval:request-multiservice-build','build:multiservice-execute']
PROJECT_PREVIEW_READ_SCOPES=['preview:multiservice-plan']
PROJECT_DEPLOYMENT_READ_SCOPES=['deployment:multiservice-plan']
PROJECT_DEPLOYMENT_WRITE_SCOPES=['approval:request-multiservice-deployment','deployment:multiservice-execute']
PROJECT_PREVIEW_WRITE_SCOPES=['approval:request-multiservice-preview','preview:multiservice-execute','preview:multiservice-delete']
PROJECT_ENVIRONMENT_READ_SCOPES=['project:environment-read']
PROJECT_ENVIRONMENT_WRITE_SCOPES=['project:environment-plan','approval:request-environment-change','project:environment-execute','approval:request-environment-promotion','project:environment-promote']
PROJECT_TOOLCHAIN_READ_SCOPES=['project:toolchain-read']
PROJECT_TOOLCHAIN_WRITE_SCOPES=['project:toolchain-plan','approval:request-toolchain-build','project:toolchain-build-execute','project:toolchain-activate-plan','approval:request-toolchain-activation','project:toolchain-activate-execute']
PROJECT_ADMIN_SCOPES=['project:read','deployment:production-plan','supabase:migration-inspect','workspace:probe','workspace:prepare','workspace:validate','workspace:test-static','workspace:preview-static','workspace:edit-preview','forgejo:plan-edit','approval:request-proposal','approval:read-own','forgejo:propose-edit','forgejo:proposal-read','forgejo:proposal-close','forgejo:proposal-delete-branch','forgejo:proposal-merge-plan','approval:request-merge','forgejo:proposal-merge','deployment:plan','approval:request-deploy','deployment:validate','approval:request-preview','deployment:preview']+SUPABASE_ALL_SCOPES+PROJECT_DISCOVERY_SCOPES+PROJECT_CHANGE_SET_SCOPES+PROJECT_BUILD_READ_SCOPES+PROJECT_BUILD_WRITE_SCOPES+PROJECT_PREVIEW_READ_SCOPES+PROJECT_PREVIEW_WRITE_SCOPES+PROJECT_DEPLOYMENT_READ_SCOPES+PROJECT_DEPLOYMENT_WRITE_SCOPES+PROJECT_ENVIRONMENT_READ_SCOPES+PROJECT_ENVIRONMENT_WRITE_SCOPES+PROJECT_TOOLCHAIN_READ_SCOPES+PROJECT_TOOLCHAIN_WRITE_SCOPES
ROLE_SCOPES={
 'viewer':['project:read','workspace:probe','approval:read-own','forgejo:proposal-read']+SUPABASE_BASIC_SCOPES+PROJECT_DISCOVERY_SCOPES+PROJECT_BUILD_READ_SCOPES+PROJECT_PREVIEW_READ_SCOPES+PROJECT_DEPLOYMENT_READ_SCOPES+PROJECT_ENVIRONMENT_READ_SCOPES+PROJECT_TOOLCHAIN_READ_SCOPES,
 'developer':['project:read','workspace:probe','workspace:prepare','workspace:validate','workspace:test-static','workspace:preview-static','workspace:edit-preview','forgejo:plan-edit','approval:request-proposal','approval:read-own','forgejo:propose-edit','forgejo:proposal-read']+SUPABASE_ALL_SCOPES+PROJECT_DISCOVERY_SCOPES+PROJECT_CHANGE_SET_SCOPES+PROJECT_BUILD_READ_SCOPES+PROJECT_BUILD_WRITE_SCOPES+PROJECT_PREVIEW_READ_SCOPES+PROJECT_PREVIEW_WRITE_SCOPES+PROJECT_DEPLOYMENT_READ_SCOPES+PROJECT_DEPLOYMENT_WRITE_SCOPES+PROJECT_ENVIRONMENT_READ_SCOPES+PROJECT_ENVIRONMENT_WRITE_SCOPES+PROJECT_TOOLCHAIN_READ_SCOPES+PROJECT_TOOLCHAIN_WRITE_SCOPES,
 'maintainer':['project:read','workspace:probe','workspace:prepare','workspace:validate','workspace:test-static','workspace:preview-static','workspace:edit-preview','forgejo:plan-edit','approval:request-proposal','approval:read-own','forgejo:propose-edit','forgejo:proposal-read','forgejo:proposal-close','forgejo:proposal-delete-branch','forgejo:proposal-merge-plan','approval:request-merge','forgejo:proposal-merge']+SUPABASE_ALL_SCOPES+PROJECT_DISCOVERY_SCOPES+PROJECT_CHANGE_SET_SCOPES+PROJECT_BUILD_READ_SCOPES+PROJECT_BUILD_WRITE_SCOPES+PROJECT_PREVIEW_READ_SCOPES+PROJECT_PREVIEW_WRITE_SCOPES+PROJECT_DEPLOYMENT_READ_SCOPES+PROJECT_DEPLOYMENT_WRITE_SCOPES+PROJECT_ENVIRONMENT_READ_SCOPES+PROJECT_ENVIRONMENT_WRITE_SCOPES+PROJECT_TOOLCHAIN_READ_SCOPES+PROJECT_TOOLCHAIN_WRITE_SCOPES,
 'release-manager':['project:read','approval:read-own','deployment:production-plan','deployment:plan','approval:request-deploy','deployment:validate']+SUPABASE_BASIC_SCOPES+PROJECT_DISCOVERY_SCOPES+PROJECT_BUILD_READ_SCOPES+PROJECT_PREVIEW_READ_SCOPES+PROJECT_DEPLOYMENT_READ_SCOPES+PROJECT_DEPLOYMENT_WRITE_SCOPES+PROJECT_ENVIRONMENT_READ_SCOPES+PROJECT_ENVIRONMENT_WRITE_SCOPES+PROJECT_TOOLCHAIN_READ_SCOPES+PROJECT_TOOLCHAIN_WRITE_SCOPES,
 'project-admin':PROJECT_ADMIN_SCOPES,
 'test-operator':PROJECT_ADMIN_SCOPES+['supabase:migration-plan','deployment:promote-test-plan','approval:request-promote-test','deployment:promote-test','deployment:promote-test-status','deployment:rollback-test-plan','approval:request-rollback-test','deployment:rollback-test'],
}
ROLE_ENVIRONMENTS={'viewer':'project','developer':'project','maintainer':'project','release-manager':'project','project-admin':'project','test-operator':'isolated-test'}
ROLE_DESCRIPTIONS={'viewer':'Consulta projeto, propostas e estado básico.','developer':'Prepara workspace, testa, edita preview, cria propostas e usa o Supabase conforme a ACL do projeto.','maintainer':'Inclui gestão e merge controlado de propostas.','release-manager':'Planeja e valida deploy dry-run; não promove produção.','project-admin':'Conjunto completo do projeto, incluindo operações Supabase aprovadas, sem promoção de produção.','test-operator':'Inclui promoção somente no ambiente isolado de teste.'}
DB=os.environ.get('CLOUDIF_AGENT_DB','/var/lib/cloudif/agents/agents.db');TOKEN=os.environ.get('CLOUDIF_AGENT_ADMIN_TOKEN','');HOST=os.environ.get('CLOUDIF_AGENT_HOST','127.0.0.1');PORT=int(os.environ.get('CLOUDIF_AGENT_PORT','18203'))
def c():
 x=sqlite3.connect(DB,timeout=20);x.row_factory=sqlite3.Row;x.execute('pragma busy_timeout=20000');return x
def init():
 os.makedirs(os.path.dirname(DB),exist_ok=True);x=c();x.execute('pragma journal_mode=delete');x.executescript('''create table if not exists clients(client_id text primary key,name text not null,owner_user text,tenant text,status text not null default 'active',token_hash text not null,scopes_json text not null,project_slugs_json text not null,rate_per_minute integer not null default 60,daily_quota integer not null default 1000,created_at text not null,updated_at text not null,last_used_at text);create table if not exists usage(client_id text not null,window_key text not null,calls integer not null default 0,primary key(client_id,window_key));''')
 cols={r[1] for r in x.execute('pragma table_info(clients)')}
 if 'role_profile' not in cols:x.execute("alter table clients add column role_profile text not null default 'custom'")
 if 'environment' not in cols:x.execute("alter table clients add column environment text not null default 'project'")
 target=json.dumps(PROJECT_ADMIN_SCOPES,separators=(',',':'))
 x.execute("update clients set role_profile='project-admin',environment='project' where client_id like 'project-%' and scopes_json=? and role_profile='custom'",(target,))
 for role,scopes in ROLE_SCOPES.items():
  x.execute('update clients set scopes_json=?,environment=? where role_profile=?',(json.dumps(scopes,separators=(',',':')),ROLE_ENVIRONMENTS[role],role))
 x.commit();x.close()
def hash_token(v):return hashlib.sha256(v.encode()).hexdigest()
def role_coherent(row,scopes,projects):
 role=str(row['role_profile'] or 'custom');env=str(row['environment'] or 'project')
 if env=='production':return False,'production_disabled'
 if role=='custom':return True,'custom'
 if role not in ROLE_SCOPES:return False,'invalid_role_profile'
 if scopes!=ROLE_SCOPES[role]:return False,'role_scope_drift'
 if env!=ROLE_ENVIRONMENTS[role]:return False,'environment_role_drift'
 if role=='test-operator' and projects!=['sistema-de-biblioteca-teste']:return False,'test_operator_project_mismatch'
 return True,'coherent'
def admin(h):return bool(TOKEN) and hmac.compare_digest(h.get('Authorization',''),'Bearer '+TOKEN)
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def out(self,code,d):
  b=json.dumps(d,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  p=urlparse(self.path).path
  if p=='/health':
   try:x=c();n=x.execute('select count(*) from clients').fetchone()[0];x.close();self.out(200,{'ok':True,'clients':n})
   except Exception:self.out(503,{'ok':False});
   return
  if not admin(self.headers):self.out(401,{'ok':False,'error':'unauthorized'});return
  if p=='/v1/roles':
   self.out(200,{'ok':True,'roles':[{'role_profile':k,'description':ROLE_DESCRIPTIONS[k],'environment':ROLE_ENVIRONMENTS[k],'scopes':v,'production':False} for k,v in ROLE_SCOPES.items()],'production_enabled':False,'automatic_approval':False,'arbitrary_terminal':False});return
  if p=='/v1/clients':
   x=c();rows=[dict(r) for r in x.execute('select client_id,name,owner_user,tenant,status,role_profile,environment,scopes_json,project_slugs_json,rate_per_minute,daily_quota,created_at,updated_at,last_used_at from clients order by name')];x.close();self.out(200,{'ok':True,'clients':rows});return
  self.out(404,{'ok':False})
 def do_POST(self):
  p=urlparse(self.path).path
  if not admin(self.headers):self.out(401,{'ok':False,'error':'unauthorized'});return
  try:n=int(self.headers.get('Content-Length','0'));d=json.loads(self.rfile.read(n) if n else b'{}')
  except Exception:self.out(400,{'ok':False,'error':'invalid_json'});return
  if p.startswith('/v1/clients/') and p.endswith('/rotate'):
   cid=p.split('/')[-2];raw=secrets.token_urlsafe(32);now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());x=c();r=x.execute('select client_id from clients where client_id=?',(cid,)).fetchone()
   if not r:x.close();self.out(404,{'ok':False,'error':'not_found'});return
   x.execute('update clients set token_hash=?,updated_at=?,status="active" where client_id=?',(hash_token(raw),now,cid));x.execute('delete from usage where client_id=?',(cid,));x.commit();x.close();self.out(200,{'ok':True,'client_id':cid,'token':raw,'status':'active'});return
  if p.startswith('/v1/clients/') and p.endswith('/revoke'):
   cid=p.split('/')[-2];now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());x=c();cur=x.execute('update clients set status="revoked",updated_at=? where client_id=?',(now,cid));x.commit();x.close();self.out(200 if cur.rowcount else 404,{'ok':bool(cur.rowcount),'client_id':cid,'status':'revoked' if cur.rowcount else 'not_found'});return
  if p.startswith('/v1/clients/') and p.endswith('/activate'):
   cid=p.split('/')[-2];now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());x=c();cur=x.execute('update clients set status="active",updated_at=? where client_id=?',(now,cid));x.commit();x.close();self.out(200 if cur.rowcount else 404,{'ok':bool(cur.rowcount),'client_id':cid,'status':'active' if cur.rowcount else 'not_found'});return
  if p.startswith('/v1/clients/') and p.endswith('/rotate'):
   cid=p.split('/')[-2];x=c();r=x.execute('select client_id from clients where client_id=?',(cid,)).fetchone()
   if not r:x.close();self.out(404,{'ok':False,'error':'not_found'});return
   raw=secrets.token_urlsafe(32);now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());x.execute('update clients set token_hash=?,updated_at=? where client_id=?',(hash_token(raw),now,cid));x.commit();x.close();self.out(200,{'ok':True,'client_id':cid,'token':raw});return
  if p.startswith('/v1/clients/') and p.endswith('/status'):
   cid=p.split('/')[-2];status=str(d.get('status') or '')
   if status not in {'active','suspended','revoked'}:self.out(400,{'ok':False,'error':'invalid_status'});return
   x=c();r=x.execute('select client_id from clients where client_id=?',(cid,)).fetchone()
   if not r:x.close();self.out(404,{'ok':False,'error':'not_found'});return
   now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());x.execute('update clients set status=?,updated_at=? where client_id=?',(status,now,cid));x.commit();x.close();self.out(200,{'ok':True,'client_id':cid,'status':status});return
  if p.startswith('/v1/clients/') and p.endswith('/reconcile'):
   cid=p.split('/')[-2];role=str(d.get('role_profile') or '').strip();environment=str(d.get('environment') or '').strip();projects=d.get('project_slugs') or []
   if role not in ROLE_SCOPES:self.out(400,{'ok':False,'error':'invalid_role_profile'});return
   if environment!=ROLE_ENVIRONMENTS[role]:self.out(400,{'ok':False,'error':'environment_role_mismatch'});return
   if role=='test-operator' and projects!=['sistema-de-biblioteca-teste']:self.out(400,{'ok':False,'error':'test_operator_project_mismatch'});return
   if not isinstance(projects,list) or any(not isinstance(x,str) or not x for x in projects):self.out(400,{'ok':False,'error':'invalid_projects'});return
   rpm=max(1,min(int(d.get('rate_per_minute') or 60),600));quota=max(1,min(int(d.get('daily_quota') or 1000),100000));now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());x=c();r=x.execute('select token_hash,status,created_at from clients where client_id=?',(cid,)).fetchone()
   if not r:x.close();self.out(404,{'ok':False,'error':'not_found'});return
   before_hash=r['token_hash'];before_status=r['status'];before_created=r['created_at']
   x.execute('update clients set name=?,owner_user=?,tenant=?,role_profile=?,environment=?,scopes_json=?,project_slugs_json=?,rate_per_minute=?,daily_quota=?,updated_at=? where client_id=?',(str(d.get('name') or cid),str(d.get('owner_user') or ''),str(d.get('tenant') or ''),role,environment,json.dumps(ROLE_SCOPES[role],separators=(',',':')),json.dumps(projects,separators=(',',':')),rpm,quota,now,cid));x.commit();after=x.execute('select token_hash,status,created_at from clients where client_id=?',(cid,)).fetchone();x.close()
   preserved=before_hash==after['token_hash'] and before_status==after['status'] and before_created==after['created_at']
   self.out(200,{'ok':True,'client_id':cid,'role_profile':role,'environment':environment,'scopes':ROLE_SCOPES[role],'project_slugs':projects,'rate_per_minute':rpm,'daily_quota':quota,'token_hash_preserved':preserved,'status_preserved':before_status==after['status'],'created_at_preserved':before_created==after['created_at'],'token_returned':False});return
  if p.startswith('/v1/clients/') and p.endswith('/role'):
   cid=p.split('/')[-2];role=str(d.get('role_profile') or '').strip()
   if role not in ROLE_SCOPES:self.out(400,{'ok':False,'error':'invalid_role_profile'});return
   environment=str(d.get('environment') or ROLE_ENVIRONMENTS[role]).strip()
   if environment!=ROLE_ENVIRONMENTS[role]:self.out(400,{'ok':False,'error':'environment_role_mismatch'});return
   now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());x=c();existing=x.execute('select project_slugs_json from clients where client_id=?',(cid,)).fetchone()
   if not existing:x.close();self.out(404,{'ok':False,'error':'not_found'});return
   projects=json.loads(existing['project_slugs_json'])
   if role=='test-operator' and projects!=['sistema-de-biblioteca-teste']:x.close();self.out(400,{'ok':False,'error':'test_operator_project_mismatch'});return
   cur=x.execute('update clients set role_profile=?,environment=?,scopes_json=?,updated_at=? where client_id=?',(role,environment,json.dumps(ROLE_SCOPES[role],separators=(',',':')),now,cid));x.commit();x.close();self.out(200,{'ok':True,'client_id':cid,'role_profile':role,'environment':environment,'scopes':ROLE_SCOPES[role]});return
  if p=='/v1/clients':
   cid=str(d.get('client_id') or ('cli_'+uuid.uuid4().hex[:18]));raw=secrets.token_urlsafe(32);now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
   role=str(d.get('role_profile') or 'custom');scopes=d.get('scopes') or (ROLE_SCOPES.get(role) if role!='custom' else ['project:read']);projects=d.get('project_slugs') or [];environment=str(d.get('environment') or (ROLE_ENVIRONMENTS.get(role) if role!='custom' else 'project'))
   if role!='custom' and role not in ROLE_SCOPES:self.out(400,{'ok':False,'error':'invalid_role_profile'});return
   if role!='custom' and scopes!=ROLE_SCOPES[role]:self.out(409,{'ok':False,'error':'role_scope_mismatch'});return
   if role!='custom' and environment!=ROLE_ENVIRONMENTS[role]:self.out(400,{'ok':False,'error':'environment_role_mismatch'});return
   if environment=='production':self.out(403,{'ok':False,'error':'production_disabled'});return
   if role=='test-operator' and projects!=['sistema-de-biblioteca-teste']:self.out(400,{'ok':False,'error':'test_operator_project_mismatch'});return
   x=c();x.execute('insert into clients(client_id,name,owner_user,tenant,status,token_hash,role_profile,environment,scopes_json,project_slugs_json,rate_per_minute,daily_quota,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,str(d.get('name')or cid),str(d.get('owner_user')or''),str(d.get('tenant')or''),'active',hash_token(raw),role,environment,json.dumps(scopes,separators=(',',':')),json.dumps(projects,separators=(',',':')),max(1,min(int(d.get('rate_per_minute') or 60),600)),max(1,min(int(d.get('daily_quota') or 1000),100000)),now,now));x.commit();x.close();self.out(201,{'ok':True,'client_id':cid,'token':raw,'role_profile':role,'environment':environment,'scopes':scopes});return
  if p=='/v1/authorize-public':
   cid=str(d.get('client_id') or '');scope=str(d.get('scope') or 'project:read');slug=str(d.get('project_slug') or '');authorized_user=str(d.get('authorized_user') or '')
   now=time.gmtime();minute=time.strftime('%Y%m%d%H%M',now);day=time.strftime('%Y%m%d',now)
   x=c();x.execute('begin immediate');r=x.execute('select * from clients where client_id=?',(cid,)).fetchone();allowed=False;reason='invalid_client';minute_calls=day_calls=0;projects=[]
   if r and r['status']=='active' and authorized_user:
    scopes=json.loads(r['scopes_json']);projects=json.loads(r['project_slugs_json']);coherent,coherence_reason=role_coherent(r,scopes,projects)
    if not coherent:reason=coherence_reason
    elif not (scope in scopes or '*' in scopes):reason='scope_denied'
    elif projects and slug and slug not in projects:reason='project_denied'
    else:
     minute_calls=(x.execute('select calls from usage where client_id=? and window_key=?',(cid,'m:'+minute)).fetchone() or [0])[0]
     day_calls=(x.execute('select calls from usage where client_id=? and window_key=?',(cid,'d:'+day)).fetchone() or [0])[0]
     if minute_calls>=r['rate_per_minute']:reason='rate_limit'
     elif day_calls>=r['daily_quota']:reason='daily_quota'
     else:
      x.execute('insert into usage values(?,?,1) on conflict(client_id,window_key) do update set calls=calls+1',(cid,'m:'+minute));x.execute('insert into usage values(?,?,1) on conflict(client_id,window_key) do update set calls=calls+1',(cid,'d:'+day));x.execute('update clients set last_used_at=? where client_id=?',(time.strftime('%Y-%m-%dT%H:%M:%SZ',now),cid));allowed=True;reason='allowed';minute_calls+=1;day_calls+=1
   x.commit();x.close();self.out(200,{'ok':allowed,'reason':reason,'client_id':cid,'owner_user':r['owner_user'] if r else '','authorized_user':authorized_user if allowed else '','tenant':r['tenant'] if r else '','role_profile':r['role_profile'] if r else '','environment':r['environment'] if r else '','project_slugs':projects,'minute_calls':minute_calls,'daily_calls':day_calls,'rate_per_minute':r['rate_per_minute'] if r else 0,'daily_quota':r['daily_quota'] if r else 0,'public_client':True});return
  if p=='/v1/authorize':
   cid=str(d.get('client_id') or '');raw=str(d.get('token') or '');scope=str(d.get('scope') or 'project:read');slug=str(d.get('project_slug') or '')
   now=time.gmtime();minute=time.strftime('%Y%m%d%H%M',now);day=time.strftime('%Y%m%d',now)
   x=c();x.execute('begin immediate');r=x.execute('select * from clients where client_id=?',(cid,)).fetchone();allowed=False;reason='invalid_client';minute_calls=day_calls=0
   if r and r['status']=='active' and hmac.compare_digest(r['token_hash'],hash_token(raw)):
    scopes=json.loads(r['scopes_json']);projects=json.loads(r['project_slugs_json']);coherent,coherence_reason=role_coherent(r,scopes,projects)
    if not coherent:reason=coherence_reason
    elif not (scope in scopes or '*' in scopes):reason='scope_denied'
    elif projects and slug and slug not in projects:reason='project_denied'
    else:
     minute_calls=(x.execute('select calls from usage where client_id=? and window_key=?',(cid,'m:'+minute)).fetchone() or [0])[0]
     day_calls=(x.execute('select calls from usage where client_id=? and window_key=?',(cid,'d:'+day)).fetchone() or [0])[0]
     if minute_calls>=r['rate_per_minute']:reason='rate_limit'
     elif day_calls>=r['daily_quota']:reason='daily_quota'
     else:
      x.execute('insert into usage values(?,?,1) on conflict(client_id,window_key) do update set calls=calls+1',(cid,'m:'+minute));x.execute('insert into usage values(?,?,1) on conflict(client_id,window_key) do update set calls=calls+1',(cid,'d:'+day));x.execute('update clients set last_used_at=? where client_id=?',(time.strftime('%Y-%m-%dT%H:%M:%SZ',now),cid));allowed=True;reason='allowed';minute_calls+=1;day_calls+=1
   x.commit();x.close();self.out(200,{'ok':allowed,'reason':reason,'client_id':cid,'owner_user':r['owner_user'] if r else '','tenant':r['tenant'] if r else '','role_profile':r['role_profile'] if r else '','environment':r['environment'] if r else '','project_slugs':json.loads(r['project_slugs_json']) if r else [],'minute_calls':minute_calls,'daily_calls':day_calls,'rate_per_minute':r['rate_per_minute'] if r else 0,'daily_quota':r['daily_quota'] if r else 0});return
  if p=='/v1/validate':
   cid=str(d.get('client_id')or'');raw=str(d.get('token')or'');scope=str(d.get('scope')or'project:read');slug=str(d.get('project_slug')or'')
   x=c();r=x.execute('select * from clients where client_id=?',(cid,)).fetchone()
   ok=bool(r) and r['status']=='active' and hmac.compare_digest(r['token_hash'],hash_token(raw))
   reason='invalid_client'
   if ok:
    scopes=json.loads(r['scopes_json']);projects=json.loads(r['project_slugs_json']);coherent,reason=role_coherent(r,scopes,projects);ok=coherent and (scope in scopes or '*' in scopes) and (not projects or slug in projects or not slug)
    if coherent and not (scope in scopes or '*' in scopes):reason='scope_denied'
    elif coherent and projects and slug and slug not in projects:reason='project_denied'
    elif ok:reason='allowed'
   x.close();self.out(200,{'ok':bool(ok),'reason':reason,'client_id':cid,'owner_user':r['owner_user'] if r else '', 'tenant':r['tenant'] if r else '', 'role_profile':r['role_profile'] if r else '','environment':r['environment'] if r else '', 'rate_per_minute':r['rate_per_minute'] if r else 0,'daily_quota':r['daily_quota'] if r else 0});return
  self.out(404,{'ok':False})
init();ThreadingHTTPServer((HOST,PORT),H).serve_forever()
