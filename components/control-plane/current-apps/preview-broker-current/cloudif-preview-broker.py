#!/usr/bin/env python3
import hashlib,json,os,re,sqlite3,sys,time,uuid,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
DB=os.environ.get('CLOUDIF_PREVIEW_DB','/var/lib/cloudif/preview-broker/previews.sqlite3');TOKEN=os.environ.get('CLOUDIF_PREVIEW_TOKEN','');CLEANUP_TOKEN=os.environ.get('CLOUDIF_PREVIEW_CLEANUP_TOKEN','');HOST='127.0.0.1';PORT=18214
BUILD_DB='/var/lib/cloudif/build-broker/builds.sqlite3';EXECUTOR_URL=os.environ.get('CLOUDIF_PREVIEW_EXECUTOR_URL','http://10.62.91.2:18215').rstrip('/');EXECUTOR_TOKEN=os.environ.get('CLOUDIF_PREVIEW_EXECUTOR_TOKEN','')
def now():return int(time.time())
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('CREATE TABLE IF NOT EXISTS previews(id TEXT PRIMARY KEY,project_slug TEXT,build_id TEXT,commit_ref TEXT,plan_digest TEXT,status TEXT,created_at INTEGER,expires_at INTEGER,removed_at INTEGER,url TEXT,result_json TEXT)');c.execute('CREATE INDEX IF NOT EXISTS idx_preview_expiry ON previews(status,expires_at)');return c
def auth(h):return bool(TOKEN) and h.get('Authorization','')=='Bearer '+TOKEN
def cleanup_auth(h):return bool(CLEANUP_TOKEN) and h.get('Authorization','')=='Bearer '+CLEANUP_TOKEN
def executor_call(path,payload=None):
 data=None if payload is None else json.dumps(payload,separators=(',',':')).encode();req=urllib.request.Request(EXECUTOR_URL+path,data=data,method='GET' if data is None else 'POST',headers={'Authorization':'Bearer '+EXECUTOR_TOKEN,'Content-Type':'application/json','Accept':'application/json','Host':'cloudif-preview-executor.internal'})
 with urllib.request.urlopen(req,timeout=90) as x:return json.load(x)
def artifact(project_slug,build_id,commit_ref):
 c=sqlite3.connect(BUILD_DB);c.row_factory=sqlite3.Row;r=c.execute('select project_slug,id,ref,status,result_json from builds where project_slug=? and id=?',(project_slug,build_id)).fetchone()
 if not r or r['status']!='succeeded' or r['ref']!=commit_ref:raise ValueError('build_not_ready')
 x=json.loads(r['result_json'] or '{}');att=x.get('attestation') or {};counts=x.get('scanner_counts') or {}
 ok=bool(x.get('attestation_verified') is True and att.get('algorithm')=='HMAC-SHA256' and len(str(att.get('signature') or ''))==64 and x.get('image_created') is True and re.fullmatch(r'sha256:[0-9a-f]{64}',str(x.get('artifact_image_id') or '')) and re.fullmatch(r'[0-9a-f]{64}',str(x.get('immutable_source_digest') or '')) and x.get('sbom_ready') is True and x.get('scanner_ready') is True and x.get('scanner_blocked') is False and counts.get('HIGH',0)==0 and counts.get('CRITICAL',0)==0 and x.get('production_ready') is True)
 if not ok:raise ValueError('artifact_not_attested')
 return {'artifact_image_id':x['artifact_image_id'],'immutable_source_digest':x['immutable_source_digest'],'sbom_sha256':x.get('sbom_sha256'),'scanner_sha256':x.get('scanner_sha256'),'attestation_signature':att['signature']}
def plan(a):
 for k in ('project_slug','build_id','commit_ref'):
  if not a.get(k):raise ValueError('missing_'+k)
 ttl=int(a.get('ttl_seconds') or 3600)
 if ttl<300 or ttl>86400:raise ValueError('ttl_not_allowed')
 art=artifact(a['project_slug'],a['build_id'],a['commit_ref'])
 canonical={'project_slug':a['project_slug'],'build_id':a['build_id'],'commit_ref':a['commit_ref'],'ttl_seconds':ttl,'operation_type':'deployment.preview','artifact_image_id':art['artifact_image_id'],'immutable_source_digest':art['immutable_source_digest'],'attestation_signature':art['attestation_signature'],'public_url_ready':False}
 d=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return {'ok':True,'side_effect_free':True,'preview_plan_digest':d,'operation':canonical,'artifact':art,'approval_required':True,'public_url_ready':False,'blockers':['approval_required'],'executor_ready':bool(EXECUTOR_TOKEN),'secrets_exposed':False}
def status(slug,pid):
 c=db();r=c.execute('select * from previews where project_slug=? and id=?',(slug,pid)).fetchone()
 if not r:return None
 x=dict(r);x['result']=json.loads(x.pop('result_json') or 'null');x['secrets_exposed']=False;return x
def cleanup():
 c=db();t=now();rows=c.execute("select id from previews where status in ('planned','validated','active') and expires_at<=?",(t,)).fetchall();removed=[];failed=[]
 for r in rows:
  pid=r['id']
  try:
   x=executor_call('/v1/previews/'+pid+'/remove',{})
   if x.get('ok'):removed.append(pid)
   else:failed.append(pid)
  except Exception:failed.append(pid)
 if removed:c.executemany("update previews set status='expired',removed_at=?,url=NULL where id=?",[(t,x) for x in removed]);c.commit()
 return {'ok':not failed,'expired':len(removed),'removed':len(removed),'cleanup_failed':len(failed),'secrets_exposed':False}
def effect(a):
 required={'project_slug','build_id','commit_ref','preview_plan_digest','approval_id','execution_id'}
 if set(a)!=required:raise ValueError('invalid_effect_arguments')
 pl=plan({'project_slug':a['project_slug'],'build_id':a['build_id'],'commit_ref':a['commit_ref'],'ttl_seconds':3600})
 if pl['preview_plan_digest']!=a['preview_plan_digest']:raise ValueError('preview_plan_digest_mismatch')
 art=pl['artifact'];payload={'project_slug':a['project_slug'],'ttl_seconds':3600,'artifact_image_id':art['artifact_image_id'],'immutable_source_digest':art['immutable_source_digest']}
 c=db();existing=c.execute('select * from previews where project_slug=? and plan_digest=?',(a['project_slug'],a['preview_plan_digest'])).fetchone()
 if existing:
  x=dict(existing);result=json.loads(x.get('result_json') or '{}')
  if result.get('artifact_image_id')!=art['artifact_image_id'] or result.get('immutable_source_digest')!=art['immutable_source_digest']:raise ValueError('preview_artifact_mismatch')
  if x['status'] in {'validated','planned'} or not x['url']:
   remote=executor_call('/v1/previews',{'preview_id':x['id'],**payload})
   if not remote.get('ok') or remote.get('status')!='active' or not remote.get('url'):raise ValueError('preview_executor_failed')
   t=now();expires=t+3600;result.update({'public_url_ready':True,'artifact_image_id':art['artifact_image_id'],'immutable_source_digest':art['immutable_source_digest'],'attestation_signature':art['attestation_signature'],'site_digest':remote.get('site_digest'),'published_ports':remote.get('published_ports',[]),'network':remote.get('network'),'secrets_exposed':False})
   c.execute("update previews set status='active',expires_at=?,removed_at=0,url=?,result_json=? where id=?",(expires,remote['url'],json.dumps(result,separators=(',',':')),x['id']));c.commit();return {'ok':True,'status':'active','preview_id':x['id'],'url':remote['url'],'expires_at':expires,'idempotent':True,'upgraded_from':x['status'],'public_url_ready':True,'effect_started':True,'artifact_image_id':art['artifact_image_id'],'immutable_source_digest':art['immutable_source_digest'],'published_ports':remote.get('published_ports',[]),'secrets_exposed':False}
  return {'ok':True,'status':x['status'],'preview_id':x['id'],'url':x['url'],'expires_at':x['expires_at'],'idempotent':True,'public_url_ready':bool(x['url']),'effect_started':True,'artifact_image_id':art['artifact_image_id'],'immutable_source_digest':art['immutable_source_digest'],'secrets_exposed':False}
 pid='prv_'+uuid.uuid4().hex[:20];t=now();expires=t+3600;remote=executor_call('/v1/previews',{'preview_id':pid,**payload})
 if not remote.get('ok') or remote.get('status')!='active' or not remote.get('url'):raise ValueError('preview_executor_failed')
 result={'workspace_validation_required':True,'approval_id':a['approval_id'],'execution_id':a['execution_id'],'public_url_ready':True,'artifact_image_id':art['artifact_image_id'],'immutable_source_digest':art['immutable_source_digest'],'attestation_signature':art['attestation_signature'],'sbom_sha256':art['sbom_sha256'],'scanner_sha256':art['scanner_sha256'],'site_digest':remote.get('site_digest'),'published_ports':remote.get('published_ports',[]),'network':remote.get('network'),'secrets_exposed':False}
 c.execute('insert into previews values(?,?,?,?,?,?,?,?,?,?,?)',(pid,a['project_slug'],a['build_id'],a['commit_ref'],a['preview_plan_digest'],'active',t,expires,0,remote['url'],json.dumps(result,separators=(',',':'))));c.commit()
 return {'ok':True,'status':'active','preview_id':pid,'url':remote['url'],'expires_at':expires,'public_url_ready':True,'effect_started':True,'idempotent':False,'artifact_image_id':art['artifact_image_id'],'immutable_source_digest':art['immutable_source_digest'],'published_ports':remote.get('published_ports',[]),'secrets_exposed':False}
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def sendj(self,n,x):
  b=json.dumps(x,separators=(',',':')).encode();self.send_response(n);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=='/health':return self.sendj(200,{'ok':True,'service':'preview-broker','public_url_ready':bool(EXECUTOR_TOKEN),'artifact_binding':True,'project_scoped_status':True,'secrets_exposed':False})
  if not auth(self.headers):return self.sendj(401,{'ok':False,'error':'unauthorized'})
  m=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/previews/(prv_[0-9a-f]{20})',self.path)
  if not m:return self.sendj(404,{'ok':False,'error':'not_found'})
  x=status(m.group(1),m.group(2));return self.sendj(200,{'ok':True,'preview':x}) if x else self.sendj(404,{'ok':False,'error':'preview_not_found'})
 def do_POST(self):
  if self.path=='/internal/cleanup':
   if not cleanup_auth(self.headers):return self.sendj(401,{'ok':False,'error':'cleanup_unauthorized'})
   return self.sendj(200,cleanup())
  if not auth(self.headers):return self.sendj(401,{'ok':False,'error':'unauthorized'})
  try:a=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
  except:return self.sendj(400,{'ok':False,'error':'invalid_json'})
  try:
   if self.path=='/v1/plan':return self.sendj(200,plan(a))
   if self.path=='/v1/effect':return self.sendj(200,effect(a))
   return self.sendj(404,{'ok':False,'error':'not_found'})
  except ValueError as e:return self.sendj(400,{'ok':False,'error':str(e)})
if __name__=='__main__':ThreadingHTTPServer((HOST,PORT),H).serve_forever()
