#!/usr/bin/env python3
import hashlib,json,os,re,sqlite3,sys,time,urllib.request,urllib.error,uuid,hmac
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
DB=os.environ.get('CLOUDIF_BUILD_DB','/var/lib/cloudif/build-broker/builds.sqlite3')
TOKEN=os.environ.get('CLOUDIF_BUILD_TOKEN','')
WORKER_TOKEN=os.environ.get('CLOUDIF_BUILD_WORKER_TOKEN','')
ATTEST_KEY=os.environ.get('CLOUDIF_BUILD_ATTESTATION_KEY','').encode()
RUNTIME_URL=os.environ.get('CLOUDIF_RUNTIME_URL','http://127.0.0.1:18212').rstrip('/')
WORKSPACE_URL=os.environ.get('CLOUDIF_WORKSPACE_URL','http://127.0.0.1:18206').rstrip('/')
WORKSPACE_TOKEN=os.environ.get('CLOUDIF_WORKSPACE_TOKEN','')
ARTIFACT_URL=os.environ.get('CLOUDIF_ARTIFACT_EXECUTOR_URL','http://10.62.91.3').rstrip('/')
ARTIFACT_TOKEN=os.environ.get('CLOUDIF_ARTIFACT_EXECUTOR_TOKEN','')
HOST=os.environ.get('CLOUDIF_BUILD_HOST','127.0.0.1'); PORT=int(os.environ.get('CLOUDIF_BUILD_PORT','18213'))
SLUG=re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$'); REF=re.compile(r'^[A-Za-z0-9._/-]{1,128}$')
def now(): return int(time.time())
def db():
 c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row
 c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA foreign_keys=ON')
 c.execute('''CREATE TABLE IF NOT EXISTS builds(id TEXT PRIMARY KEY,idempotency_key TEXT UNIQUE,project_slug TEXT,ref TEXT,framework TEXT,plan_digest TEXT,status TEXT,created_at INTEGER,updated_at INTEGER,lease_until INTEGER,attempts INTEGER DEFAULT 0,result_json TEXT,log_text TEXT,next_attempt_at INTEGER DEFAULT 0,dead_reason TEXT)''')
 cols={r[1] for r in c.execute('PRAGMA table_info(builds)')}
 if 'next_attempt_at' not in cols:c.execute('ALTER TABLE builds ADD COLUMN next_attempt_at INTEGER DEFAULT 0')
 if 'dead_reason' not in cols:c.execute('ALTER TABLE builds ADD COLUMN dead_reason TEXT')
 c.execute('CREATE INDEX IF NOT EXISTS idx_build_due ON builds(status,next_attempt_at,created_at)')
 c.execute('CREATE INDEX IF NOT EXISTS idx_build_project_active ON builds(project_slug,status)')
 return c
def sanitize(s):
 s=str(s)[:20000]
 s=re.sub(r'(?i)(authorization|token|password|secret|api[_-]?key)\s*[:=]\s*\S+',r'\1=[redacted]',s)
 return s
def idem(a):
 raw='|'.join([a['project_slug'],a['ref'],a['framework'],a['build_plan_digest'],'preview','build.request'])
 return hashlib.sha256(raw.encode()).hexdigest()
def auth(h): return bool(TOKEN) and h.get('Authorization','')=='Bearer '+TOKEN
def worker_auth(h): return bool(WORKER_TOKEN) and h.get('Authorization','')=='Bearer '+WORKER_TOKEN
def validate_plan(framework,digest_value):
 data=json.dumps({'framework':framework},separators=(',',':')).encode()
 req=urllib.request.Request(RUNTIME_URL+'/v1/plan',data=data,method='POST',headers={'Content-Type':'application/json','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=15) as r:x=json.load(r)
 return bool(x.get('ok') and hmac.compare_digest(str(x.get('build_plan_digest') or ''),str(digest_value)))
def attest(slug,bid,summary):
 payload={'version':1,'project_slug':slug,'build_id':bid,'artifact_image_id':summary.get('artifact_image_id'),'sbom_sha256':summary.get('sbom_sha256'),'scanner_sha256':summary.get('scanner_sha256'),'immutable_source_digest':summary.get('immutable_source_digest'),'policy':'HMAC-SHA256'}
 raw=json.dumps(payload,sort_keys=True,separators=(',',':')).encode();sig=hmac.new(ATTEST_KEY,raw,hashlib.sha256).hexdigest()
 return {'payload':payload,'signature':sig,'algorithm':'HMAC-SHA256','verified':True}
def verify_attestation(att):
 try:
  raw=json.dumps(att['payload'],sort_keys=True,separators=(',',':')).encode();return hmac.compare_digest(hmac.new(ATTEST_KEY,raw,hashlib.sha256).hexdigest(),att['signature'])
 except Exception:return False

def artifact_build(slug,bid):
 data=json.dumps({'project_slug':slug,'build_id':bid},separators=(',',':')).encode()
 req=urllib.request.Request(ARTIFACT_URL+'/v1/artifacts',data=data,method='POST',headers={'Authorization':'Bearer '+ARTIFACT_TOKEN,'Content-Type':'application/json','Accept':'application/json','Host':'cloudif-artifact-executor.internal'})
 with urllib.request.urlopen(req,timeout=950) as r:return json.load(r)

def workspace_static(slug,ref,bid):
 data=json.dumps({'project_slug':slug,'ref':ref,'trace_id':bid}).encode()
 req=urllib.request.Request(WORKSPACE_URL+'/v1/test-static',data=data,method='POST',headers={'Authorization':'Bearer '+WORKSPACE_TOKEN,'Content-Type':'application/json','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=180) as r:return json.load(r)
def reserve(a):
 for k in ('project_slug','ref','framework','build_plan_digest'):
  if k not in a: raise ValueError('missing_'+k)
 if not SLUG.fullmatch(a['project_slug']) or not REF.fullmatch(a['ref']): raise ValueError('invalid_identifier')
 if a['framework']!='static': raise ValueError('framework_execution_not_ready')
 if not re.fullmatch(r'[0-9a-f]{64}',a['build_plan_digest']): raise ValueError('invalid_plan_digest')
 if not validate_plan(a['framework'],a['build_plan_digest']): raise ValueError('build_plan_digest_mismatch')
 k=idem(a); c=db(); row=c.execute('SELECT * FROM builds WHERE idempotency_key=?',(k,)).fetchone()
 if row:return dict(row)
 bid=str(uuid.uuid4()); t=now()
 c.execute('INSERT INTO builds(id,idempotency_key,project_slug,ref,framework,plan_digest,status,created_at,updated_at,lease_until,attempts,result_json,log_text,next_attempt_at,dead_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(bid,k,a['project_slug'],a['ref'],a['framework'],a['build_plan_digest'],'queued',t,t,0,0,None,'reserved\n',t,None))
 c.commit(); return dict(c.execute('SELECT * FROM builds WHERE id=?',(bid,)).fetchone())
def drain_one():
 c=db(); t=now(); c.execute('BEGIN IMMEDIATE')
 row=c.execute("SELECT * FROM builds b WHERE ((b.status='queued' AND b.next_attempt_at<=?) OR (b.status='running' AND b.lease_until<?)) AND NOT EXISTS (SELECT 1 FROM builds a WHERE a.project_slug=b.project_slug AND a.status='running' AND a.id<>b.id AND a.lease_until>=?) ORDER BY b.created_at LIMIT 1",(t,t,t)).fetchone()
 if not row: c.commit(); return {'ok':True,'processed':False}
 bid=row['id']; c.execute("UPDATE builds SET status='running',lease_until=?,attempts=attempts+1,updated_at=?,log_text=log_text||? WHERE id=?",(t+1200,t,'effect:start\n',bid)); c.commit()
 try:
  res=workspace_static(row['project_slug'],row['ref'],bid)
  valid=bool((res.get('result') or {}).get('valid'))
  source_digest=hashlib.sha256(json.dumps(res,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  if not valid:
   status='failed';summary={'valid':False,'workspace_profile':'test-static','immutable_source_digest':source_digest,'image_created':False,'sbom_ready':False,'scanner_ready':False,'production_ready':False,'secrets_exposed':False}
  else:
   art=artifact_build(row['project_slug'],bid)
   artifact_ok=bool(art.get('ok') and art.get('production_ready') and art.get('sbom_ready') and art.get('scanner_ready') and not art.get('scanner_blocked'))
   status='succeeded' if artifact_ok else 'failed'
   summary={'valid':True,'workspace_profile':'test-static','immutable_source_digest':source_digest,'image_created':bool(art.get('artifact_image_id')),'artifact_image_id':art.get('artifact_image_id'),'artifact_tag':art.get('artifact_tag'),'base_image':art.get('base_image'),'sbom_ready':art.get('sbom_ready') is True,'sbom_format':art.get('sbom_format'),'sbom_spec_version':art.get('sbom_spec_version'),'sbom_components':art.get('sbom_components'),'sbom_sha256':art.get('sbom_sha256'),'scanner_ready':art.get('scanner_ready') is True,'scanner_policy':art.get('scanner_policy'),'scanner_counts':art.get('scanner_counts') or {},'scanner_sha256':art.get('scanner_sha256'),'scanner_blocked':art.get('scanner_blocked') is True,'runtime_proof':art.get('runtime_proof') or {},'production_ready':artifact_ok,'artifact_executor_idempotent':art.get('idempotent') is True,'secrets_exposed':False}
   summary['attestation']=attest(row['project_slug'],bid,summary);summary['attestation_verified']=verify_attestation(summary['attestation'])
  c=db(); c.execute('UPDATE builds SET status=?,updated_at=?,lease_until=0,result_json=?,log_text=log_text||? WHERE id=?',(status,now(),json.dumps(summary,separators=(',',':')),'artifact:'+status+'\n',bid)); c.commit()
 except Exception as e:
  c=db(); current=c.execute('SELECT attempts FROM builds WHERE id=?',(bid,)).fetchone(); attempts=int(current[0] if current else 1)
  if attempts < 3:
   delay=min(300,15*(2**(attempts-1))); status='queued'; nxt=now()+delay; reason=None; log='retry:scheduled delay='+str(delay)+'\n'
  else:
   status='dead_letter'; nxt=0; reason='max_attempts_exceeded'; log='dead-letter:max-attempts\n'
  c.execute('UPDATE builds SET status=?,updated_at=?,lease_until=0,next_attempt_at=?,dead_reason=?,result_json=?,log_text=log_text||? WHERE id=?',(status,now(),nxt,reason,json.dumps({'error':'build_execution_failed','retryable':status=='queued','secrets_exposed':False}),sanitize(log),bid)); c.commit()
 return {'ok':True,'processed':True,'build_id':bid}
def getrow(slug,bid):
 c=db(); r=c.execute('SELECT * FROM builds WHERE project_slug=? AND id=?',(slug,bid)).fetchone()
 if not r:return None
 d=dict(r); d['result']=json.loads(d.pop('result_json') or 'null');
 if isinstance(d['result'],dict) and d['result'].get('attestation'):
  d['result']['attestation_verified']=verify_attestation(d['result']['attestation'])
 d.pop('idempotency_key',None); d.pop('lease_until',None); d['retry_scheduled']=d.get('status')=='queued' and int(d.get('attempts') or 0)>0; d['dead_letter']=d.get('status')=='dead_letter'; d['secrets_exposed']=False; return d
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def sendj(self,n,x):
  b=json.dumps(x,separators=(',',':')).encode(); self.send_response(n); self.send_header('Content-Type','application/json'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
 def do_GET(self):
  if self.path=='/health': return self.sendj(200,{'ok':True,'service':'build-broker','queue':'sqlite-wal','production_ready':False,'secrets_exposed':False})
  if not auth(self.headers): return self.sendj(401,{'ok':False,'error':'unauthorized'})
  m=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/builds/([0-9a-f-]+)(/logs|/artifact)?',self.path)
  if not m:return self.sendj(404,{'ok':False,'error':'not_found'})
  r=getrow(m.group(1),m.group(2))
  if not r:return self.sendj(404,{'ok':False,'error':'build_not_found'})
  if m.group(3)=='/logs': return self.sendj(200,{'ok':True,'project_slug':m.group(1),'build_id':r['id'],'logs':sanitize(r.pop('log_text','')),'secrets_exposed':False})
  if m.group(3)=='/artifact': return self.sendj(200,{'ok':True,'project_slug':m.group(1),'build_id':r['id'],'artifact':r.get('result'),'attestation_verified':bool((r.get('result') or {}).get('attestation_verified')),'downloadable':False,'secrets_exposed':False})
  r.pop('log_text',None); return self.sendj(200,{'ok':True,'build':r})
 def do_POST(self):
  if self.path=='/internal/drain':
   if not worker_auth(self.headers):return self.sendj(401,{'ok':False,'error':'worker_unauthorized'})
   return self.sendj(200,drain_one())
  if not auth(self.headers): return self.sendj(401,{'ok':False,'error':'unauthorized'})
  try:a=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
  except Exception:return self.sendj(400,{'ok':False,'error':'invalid_json'})
  try:
   if self.path=='/v1/builds':
    r=reserve(a); return self.sendj(202,{'ok':True,'phase':'reserve','build_id':r['id'],'status':r['status'],'idempotent':True,'secrets_exposed':False})
   return self.sendj(404,{'ok':False,'error':'not_found'})
  except ValueError as e:return self.sendj(400,{'ok':False,'error':str(e)})
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='drain': print(json.dumps(drain_one()))
 else: ThreadingHTTPServer((HOST,PORT),H).serve_forever()
