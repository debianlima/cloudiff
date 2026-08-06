#!/usr/bin/env python3
import hashlib,hmac,json,os,re,sqlite3,time,urllib.request,urllib.error
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
PORTAL_DB=Path(os.environ.get('CLOUDIF_PROJECT_SNAPSHOT_DB','/var/lib/cloudif/control-plane/control-plane.db'))
STATE_DB=Path(os.environ.get('CLOUDIF_ONBOARDING_DB','/var/lib/cloudif/onboarding/onboarding.db'))
SECRET_DIR=Path(os.environ.get('CLOUDIF_ONBOARDING_SECRET_DIR','/var/lib/cloudif/onboarding/secrets'))
AGENT_URL=os.environ.get('CLOUDIF_AGENT_REGISTRY_URL','http://127.0.0.1:18203').rstrip('/')
AGENT_TOKEN=os.environ.get('CLOUDIF_AGENT_ADMIN_TOKEN','')
FORJA_URL=os.environ.get('CLOUDIF_FORJA_AGENT_URL','http://10.62.91.2:18095').rstrip('/')
FORJA_TOKEN=os.environ.get('CLOUDIF_FORJA_AGENT_TOKEN','')
KOMODO_URL=os.environ.get('CLOUDIF_KOMODO_AGENT_URL','http://10.62.91.2:18098').rstrip('/')
KOMODO_TOKEN=os.environ.get('CLOUDIF_KOMODO_AGENT_TOKEN','')
SUPABASE_URL=os.environ.get('CLOUDIF_SUPABASE_AGENT_URL','http://10.62.92.7:18096').rstrip('/')
SUPABASE_TOKEN=os.environ.get('CLOUDIF_SUPABASE_AGENT_TOKEN','')
SUPABASE_ONBOARDING_URL=os.environ.get('CLOUDIF_SUPABASE_ONBOARDING_URL','http://127.0.0.1:18209').rstrip('/')
SUPABASE_ONBOARDING_TOKEN=os.environ.get('CLOUDIF_SUPABASE_ONBOARDING_TOKEN','')
API_TOKEN=os.environ.get('CLOUDIF_ONBOARDING_API_TOKEN','')
HOST=os.environ.get('CLOUDIF_ONBOARDING_HOST','127.0.0.1');PORT=int(os.environ.get('CLOUDIF_ONBOARDING_PORT','18208'))
SLUG_RE=re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
DEFAULT_ROLE=os.environ.get('CLOUDIF_DEFAULT_PROJECT_ROLE','developer').strip()
BASE_SCOPES=['project:read','workspace:probe','workspace:prepare','workspace:validate','workspace:test-static','workspace:preview-static','workspace:edit-preview','forgejo:plan-edit','approval:request-proposal','approval:read-own','forgejo:propose-edit','forgejo:proposal-read','forgejo:proposal-close','forgejo:proposal-delete-branch','forgejo:proposal-merge-plan','approval:request-merge','forgejo:proposal-merge','deployment:plan','approval:request-deploy','deployment:validate','approval:request-preview','deployment:preview']

def now():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def cid(slug):return 'project-'+hashlib.sha256(slug.encode()).hexdigest()[:20]
def conn():
 STATE_DB.parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(STATE_DB,timeout=20);c.row_factory=sqlite3.Row;c.execute('pragma busy_timeout=20000');return c
def init():
 SECRET_DIR.mkdir(parents=True,exist_ok=True);os.chmod(SECRET_DIR,0o700)
 c=conn();os.chmod(STATE_DB,0o600);c.executescript('''create table if not exists project_onboarding(project_slug text primary key,client_id text not null,owner_user text,tenant text,status text not null,identity_status text not null,secret_stored integer not null default 0,scopes_json text not null,connectors_json text not null default '{}',instructions_json text not null default '{}',last_error text,created_at text not null,updated_at text not null,last_reconciled_at text not null);create table if not exists onboarding_events(id integer primary key autoincrement,at text not null,project_slug text,event text not null,detail_json text not null);''')
 cols={r[1] for r in c.execute('pragma table_info(project_onboarding)')}
 if 'role_profile' not in cols:c.execute("alter table project_onboarding add column role_profile text not null default 'project-admin'")
 if 'environment' not in cols:c.execute("alter table project_onboarding add column environment text not null default 'project'")
 if 'rate_per_minute' not in cols:c.execute("alter table project_onboarding add column rate_per_minute integer not null default 60")
 if 'daily_quota' not in cols:c.execute("alter table project_onboarding add column daily_quota integer not null default 3000")
 c.execute("update project_onboarding set role_profile='project-admin' where role_profile is null or role_profile=''")
 c.execute("update project_onboarding set environment='project' where environment is null or environment=''")
 c.execute('''create table if not exists credential_rotations(rotation_id text primary key,project_slug text not null,client_id text not null,requested_by text not null,reason text not null,created_at integer not null,delivered_at integer not null,status text not null)''')
 c.execute('create index if not exists idx_credential_rotations_project on credential_rotations(project_slug,created_at desc)')
 c.commit();c.close()
def api(method,path,payload=None,timeout=20):
 data=None if payload is None else json.dumps(payload,separators=(',',':')).encode();req=urllib.request.Request(AGENT_URL+path,data=data,method=method,headers={'Authorization':'Bearer '+AGENT_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=timeout) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:
  try:b=json.load(e)
  except Exception:b={}
  return e.code,b
def external(method,base,path,token,payload=None,timeout=120):
 data=None if payload is None else json.dumps(payload,separators=(',',':')).encode();req=urllib.request.Request(base+path,data=data,method=method,headers={'Authorization':'Bearer '+token,'X-CloudIF-Token':token,'Content-Type':'application/json','Accept':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=timeout) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:
  try:b=json.load(e)
  except Exception:b={}
  return e.code,b
def connector_reconcile(p):
 slug=str(p.get('slug') or '');name=str(p.get('name') or slug);tenant=str(p.get('tenant') or '');owner=str(p.get('owner') or '');lifecycle=str(p.get('status') or 'draft')
 payload={'project_slug':slug,'project':slug,'slug':slug,'name':name,'tenant':tenant,'owner_user':owner,'forgejo_owner':owner,'actor':'cloudif-project-onboarding','repo_url':str(p.get('repo_url') or ''),'action':'integrate','source':'cloudif-onboarding'}
 connectors={}
 fc,fd=external('POST',FORJA_URL,'/forgejo/ensure-repo',FORJA_TOKEN,payload,120)
 connectors['forgejo']={'status':'ready' if fc in (200,201,202) and fd.get('ok') else 'error','http':fc,'managed':True}
 if lifecycle in ('active','published'):
  kc,kd=external('POST',KOMODO_URL,'/komodo/project/ensure',KOMODO_TOKEN,payload,180)
  connectors['komodo']={'status':'ready' if kc in (200,201,202) and kd.get('ok') else 'error','http':kc,'managed':True}
 else:connectors['komodo']={'status':'planned','managed':True,'reason':'project_not_active'}
 if tenant:
  sc,sd=external('POST',SUPABASE_URL,'/supabase/release/inspect',SUPABASE_TOKEN,{'project':slug,'tenant':tenant,'version':'v0.0.0-onboarding'},30)
  supa_status='ready' if sc==200 and sd.get('ok') and sd.get('available') else ('pending_creation' if sc==200 and sd.get('ok') else 'error')
  if supa_status=='pending_creation':
   ec,ed=external('POST',SUPABASE_ONBOARDING_URL,'/v1/ensure',SUPABASE_ONBOARDING_TOKEN,{'project_slug':slug,'tenant':tenant},900)
   if ec==200 and ed.get('ok'):supa_status='ready'
  connectors['supabase']={'status':supa_status,'http':sc,'managed':True,'tenant':tenant}
 else:connectors['supabase']={'status':'not_applicable','managed':False,'reason':'tenant_missing'}
 connectors['workspace']={'status':'ready','managed':True};connectors['mcp']={'status':'ready','managed':True}
 return connectors
def projects():
 c=sqlite3.connect(f'file:{PORTAL_DB}?mode=ro&immutable=1',uri=True,timeout=10);c.row_factory=sqlite3.Row;rows=[dict(r) for r in c.execute('select slug,name,tenant,owner,status,repo_url,komodo_status from projects order by slug')];c.close();return rows
def existing_clients():
 code,d=api('GET','/v1/clients');
 if code!=200 or not d.get('ok'):raise RuntimeError('agent_registry_unavailable')
 return {x['client_id']:x for x in d['clients']}
def role_catalog():
 code,d=api('GET','/v1/roles')
 if code!=200 or not d.get('ok'):raise RuntimeError('role_catalog_unavailable')
 roles={x['role_profile']:x for x in d.get('roles') or []}
 if DEFAULT_ROLE not in roles or roles[DEFAULT_ROLE].get('production') is not False:raise RuntimeError('default_role_invalid')
 return roles
def secret_path(slug):return SECRET_DIR/(slug+'.json')
def instructions(slug,client_id,role_profile,environment):
 tools={'viewer':['project.get','forgejo.proposal.list'],'developer':['project.get','workspace.prepare','workspace.validate','forgejo.propose-edit.plan'],'maintainer':['project.get','forgejo.proposal.list','forgejo.proposal.merge.plan'],'release-manager':['project.get','deployment.plan','deployment.validate'],'project-admin':['project.get','workspace.prepare','workspace.validate','forgejo.propose-edit.plan','forgejo.proposal.merge.plan','deployment.plan'],'test-operator':['project.get','deployment.promote-test.plan']}.get(role_profile,['project.get'])
 return {'mcp_endpoint':'https://cloudiff.duckdns.org/cloudiff/mcp','client_id':client_id,'project_slug':slug,'role_profile':role_profile,'environment':environment,'authentication':'OAuth 2.1 público com PKCE (token_endpoint_auth_method=none)','openapi_schema_url':'https://cloudiff.duckdns.org/cloudiff/mcp/openapi/'+client_id+'.json','privacy_policy_url':'https://cloudiff.duckdns.org/cloudiff/mcp/privacy','chatgpt_actions_oauth':{'client_secret':'','pkce':False,'callback_policy':'official_chat_openai_aip_callback','authorization_code_ttl_seconds':180},'oauth':{'issuer':'https://cloudiff.duckdns.org','authorization_url':'https://cloudiff.duckdns.org/cloudiff/mcp/oauth/authorize','token_url':'https://cloudiff.duckdns.org/cloudiff/mcp/oauth/token','revoke_url':'https://cloudiff.duckdns.org/cloudiff/mcp/oauth/revoke','client_secret':'','token_endpoint_auth_method':'none','code_challenge_method':'S256','scopes':['mcp','offline_access'],'callbacks':{'claude':'https://claude.ai/api/mcp/auth_callback','chatgpt':'Copie a URL exata exibida pelo ChatGPT: https://chatgpt.com/connector/oauth/<callback_id>','llama_ollama':'Use a callback local do cliente, por exemplo http://127.0.0.1:<porta>/callback'}},'legacy_bearer':{'enabled':True,'delivery':'Somente por rotação autenticada e exibição única no Portal.','headers':{'Authorization':'Bearer <TOKEN_DO_PROJETO>','X-CloudIF-Client':client_id}},'first_tools':tools,'production':False}
def write_secret(slug,client_id,token):
 p=secret_path(slug);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps({'project_slug':slug,'client_id':client_id,'token':token,'created_at':now()},separators=(',',':'))+'\n');os.chmod(tmp,0o600);os.replace(tmp,p)
def event(slug,name,detail):
 c=conn();c.execute('insert into onboarding_events(at,project_slug,event,detail_json) values(?,?,?,?)',(now(),slug,name,json.dumps(detail,separators=(',',':'))));c.commit();c.close()
def reconcile_one(p,clients,roles):
 slug=str(p.get('slug') or '').strip();assert SLUG_RE.fullmatch(slug)
 client_id=cid(slug);owner=str(p.get('owner') or '');tenant=str(p.get('tenant') or '');created=False
 row=clients.get(client_id)
 if not row:
  role=roles[DEFAULT_ROLE];payload={'client_id':client_id,'name':'Projeto CloudIFF: '+slug,'owner_user':owner,'tenant':tenant,'role_profile':DEFAULT_ROLE,'environment':role['environment'],'project_slugs':[slug],'rate_per_minute':60,'daily_quota':3000}
  code,d=api('POST','/v1/clients',payload)
  if code!=201 or not d.get('ok') or not d.get('token') or d.get('role_profile')!=DEFAULT_ROLE or d.get('environment')!=role['environment']:raise RuntimeError('client_create_failed')
  scopes=role['scopes'];write_secret(slug,client_id,d['token']);created=True;row={'status':'active','role_profile':DEFAULT_ROLE,'environment':role['environment'],'scopes_json':json.dumps(scopes,separators=(',',':')),'project_slugs_json':json.dumps([slug],separators=(',',':')),'rate_per_minute':60,'daily_quota':3000};clients[client_id]=row;event(slug,'identity_created',{'client_id':client_id,'role_profile':DEFAULT_ROLE,'environment':role['environment'],'scopes':scopes})
 secret_ok=secret_path(slug).is_file() and (secret_path(slug).stat().st_mode & 0o077)==0
 status='ready' if row.get('status')=='active' and secret_ok else 'degraded'
 connectors=connector_reconcile(p)
 connector_required=[connectors['forgejo']['status']]
 if str(p.get('status') or '') in ('active','published'):connector_required.append(connectors['komodo']['status'])
 connector_ok=all(x=='ready' for x in connector_required)
 status='ready' if status=='ready' and connector_ok else 'degraded'
 role_profile=str(row.get('role_profile') or 'custom');environment=str(row.get('environment') or 'project');scopes=json.loads(row.get('scopes_json') or '[]')
 if role_profile not in roles or roles[role_profile]['scopes']!=scopes or roles[role_profile]['environment']!=environment:raise RuntimeError('registry_role_incoherent')
 ins=instructions(slug,client_id,role_profile,environment);t=now();c=conn();old=c.execute('select created_at from project_onboarding where project_slug=?',(slug,)).fetchone();ca=old['created_at'] if old else t
 c.execute('''insert into project_onboarding(project_slug,client_id,owner_user,tenant,status,identity_status,secret_stored,role_profile,environment,rate_per_minute,daily_quota,scopes_json,connectors_json,instructions_json,last_error,created_at,updated_at,last_reconciled_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) on conflict(project_slug) do update set client_id=excluded.client_id,owner_user=excluded.owner_user,tenant=excluded.tenant,status=excluded.status,identity_status=excluded.identity_status,secret_stored=excluded.secret_stored,role_profile=excluded.role_profile,environment=excluded.environment,rate_per_minute=excluded.rate_per_minute,daily_quota=excluded.daily_quota,scopes_json=excluded.scopes_json,connectors_json=excluded.connectors_json,instructions_json=excluded.instructions_json,last_error=NULL,updated_at=excluded.updated_at,last_reconciled_at=excluded.last_reconciled_at''',(slug,client_id,owner,tenant,status,row.get('status') or 'unknown',1 if secret_ok else 0,role_profile,environment,int(row.get('rate_per_minute') or 60),int(row.get('daily_quota') or 3000),json.dumps(scopes,separators=(',',':')),json.dumps(connectors,separators=(',',':')),json.dumps(ins,separators=(',',':')),None,ca,t,t));c.commit();c.close();return {'slug':slug,'client_id':client_id,'status':status,'created':created,'secret_stored':secret_ok,'role_profile':role_profile,'environment':environment}
def rotate_credential(slug,requested_by,reason):
 if not SLUG_RE.fullmatch(slug) or not requested_by or not (4<=len(reason)<=500):raise ValueError('invalid_request')
 c=conn();row=c.execute('select project_slug,client_id,status from project_onboarding where project_slug=?',(slug,)).fetchone()
 if not row:c.close();raise LookupError('project_not_onboarded')
 last=c.execute('select created_at from credential_rotations where project_slug=? order by created_at desc limit 1',(slug,)).fetchone();now_epoch=int(time.time())
 if last and now_epoch-int(last['created_at'])<300:c.close();raise RuntimeError('rotation_cooldown')
 client_id=row['client_id'];c.close()
 code,data=api('POST','/v1/clients/'+urllib.parse.quote(client_id,safe='')+'/rotate',{},30)
 if code!=200 or not data.get('ok') or data.get('client_id')!=client_id or not data.get('token'):raise RuntimeError('registry_rotation_failed')
 token=str(data['token']);write_secret(slug,client_id,token);rotation_id='rot_'+hashlib.sha256((slug+'|'+client_id+'|'+str(now_epoch)+'|'+os.urandom(16).hex()).encode()).hexdigest()[:20]
 c=conn();c.execute('insert into credential_rotations(rotation_id,project_slug,client_id,requested_by,reason,created_at,delivered_at,status) values(?,?,?,?,?,?,?,?)',(rotation_id,slug,client_id,requested_by,reason,now_epoch,now_epoch,'delivered_once'));c.commit();c.close()
 event(slug,'credential_rotated',{'rotation_id':rotation_id,'client_id':client_id,'requested_by':requested_by,'delivery':'one_time','token_logged':False})
 return {'ok':True,'project_slug':slug,'client_id':client_id,'rotation_id':rotation_id,'token':token,'one_time_delivery':True,'delivered_at':now_epoch,'status':'active','secrets_persisted_in_response':False}

def credential_rotation_summary(slug):
 c=conn();r=c.execute('select rotation_id,requested_by,reason,created_at,delivered_at,status from credential_rotations where project_slug=? order by created_at desc limit 10',(slug,)).fetchall();c.close()
 return [dict(x) for x in r]

def reconcile_all():
 ps=projects();clients=existing_clients();roles=role_catalog();out=[];errors=[]
 for p in ps:
  try:out.append(reconcile_one(p,clients,roles))
  except Exception as e:
   slug=str(p.get('slug') or '');errors.append({'slug':slug,'error':type(e).__name__});t=now();c=conn();c.execute('''insert into project_onboarding(project_slug,client_id,owner_user,tenant,status,identity_status,secret_stored,role_profile,environment,rate_per_minute,daily_quota,scopes_json,connectors_json,instructions_json,last_error,created_at,updated_at,last_reconciled_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) on conflict(project_slug) do update set status='error',last_error=excluded.last_error,updated_at=excluded.updated_at,last_reconciled_at=excluded.last_reconciled_at''',(slug,cid(slug) if slug else '',str(p.get('owner') or ''),str(p.get('tenant') or ''),'error','unknown',0,DEFAULT_ROLE,'project',60,3000,'[]','{}','{}',type(e).__name__,t,t,t));c.commit();c.close()
 return {'ok':not errors,'projects':len(ps),'ready':sum(1 for x in out if x['status']=='ready'),'created':sum(1 for x in out if x['created']),'errors':errors,'at':now()}
def safe_rows():
 c=conn();rows=[]
 for r in c.execute('select project_slug,client_id,owner_user,tenant,status,identity_status,secret_stored,role_profile,environment,rate_per_minute,daily_quota,scopes_json,connectors_json,instructions_json,last_error,created_at,updated_at,last_reconciled_at from project_onboarding order by project_slug'):
  x=dict(r);x['secret_stored']=bool(x['secret_stored']);x['scopes']=json.loads(x.pop('scopes_json'));x['connectors']=json.loads(x.pop('connectors_json'));x['instructions']=json.loads(x.pop('instructions_json'));rows.append(x)
 c.close();return rows
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def out(self,code,d):
  b=json.dumps(d,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def authed(self):return bool(API_TOKEN) and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+API_TOKEN)
 def do_GET(self):
  if self.path=='/health':
   rows=safe_rows();return self.out(200,{'ok':True,'service':'cloudif-project-onboarding','projects':len(rows),'ready':sum(1 for x in rows if x['status']=='ready')})
  if not self.authed():return self.out(401,{'ok':False,'error':'unauthorized'})
  if self.path=='/v1/projects':return self.out(200,{'ok':True,'projects':safe_rows(),'count':len(safe_rows()),'secrets_exposed':False})
  return self.out(404,{'ok':False,'error':'not_found'})
 def do_POST(self):
  if not self.authed():return self.out(401,{'ok':False,'error':'unauthorized'})
  if self.path=='/v1/reconcile':return self.out(200 if (r:=reconcile_all())['ok'] else 207,r)
  m=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/rotate-credential',self.path)
  if m:
   try:n=int(self.headers.get('Content-Length','0') or '0');d=json.loads(self.rfile.read(n) if n else b'{}')
   except Exception:return self.out(400,{'ok':False,'error':'invalid_request'})
   if set(d)!={'requested_by','reason'}:return self.out(400,{'ok':False,'error':'invalid_request'})
   try:r=rotate_credential(m.group(1),str(d['requested_by']).strip(),str(d['reason']).strip())
   except LookupError as e:return self.out(404,{'ok':False,'error':str(e)})
   except RuntimeError as e:return self.out(409 if str(e)=='rotation_cooldown' else 502,{'ok':False,'error':str(e)})
   except ValueError:return self.out(400,{'ok':False,'error':'invalid_request'})
   return self.out(200,r)
  return self.out(404,{'ok':False,'error':'not_found'})
if __name__=='__main__':
 init();reconcile_all();ThreadingHTTPServer((HOST,PORT),H).serve_forever()
