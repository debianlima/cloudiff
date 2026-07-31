#!/usr/bin/env python3
import hashlib,json,os,re,sqlite3,subprocess,time,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
DB='/var/lib/cloudif/production-canary/state.sqlite3';TOKEN=os.environ.get('CLOUDIF_PRODUCTION_CANARY_TOKEN','');HOST='10.62.91.2';PORT=18219;NETWORK='cloudif-production-canary';ALIAS='cloudif-prod-canary';SLUG='atalhos-cloudif-iff1860746'
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('CREATE TABLE IF NOT EXISTS releases(id INTEGER PRIMARY KEY AUTOINCREMENT,execution_id TEXT UNIQUE,image_id TEXT,container_name TEXT,status TEXT,created_at INTEGER,previous_release_id INTEGER,body_sha256 TEXT,result_json TEXT)');c.execute('CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT)');c.commit();return c
def auth(h):return bool(TOKEN) and h.get('Authorization','')=='Bearer '+TOKEN
def cur(c):
 r=c.execute("select r.* from state s join releases r on r.id=cast(s.value as integer) where s.key='current_release_id'").fetchone();return dict(r) if r else None
def inspect_image(i):
 if not re.fullmatch(r'sha256:[0-9a-f]{64}',i):raise ValueError('invalid_image_id')
 x=json.loads(subprocess.check_output(['docker','image','inspect',i],text=True))[0];u=str((x.get('Config') or {}).get('User') or '')
 if u.split(':')[0] in ('','0','root'):raise ValueError('image_not_rootless')
 return str(x['Id'])
def ip(name):
 x=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0];return x['NetworkSettings']['Networks'][NETWORK]['IPAddress']
def smoke(name):
 with urllib.request.urlopen('http://'+ip(name)+':8080/',timeout=10) as r:b=r.read();code=r.status
 if code!=200:raise RuntimeError('smoke_failed')
 return {'status':code,'sha256':hashlib.sha256(b).hexdigest(),'size':len(b)}
def connect(name,alias=False):
 cmd=['docker','network','connect']+(['--alias',ALIAS] if alias else [])+[NETWORK,name];subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
def disconnect(name):subprocess.run(['docker','network','disconnect',NETWORK,name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def create(image,eid):
 n='cloudif-prod-canary-'+eid[-10:];subprocess.run(['docker','rm','-f',n],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 subprocess.run(['docker','create','--name',n,'--read-only','--user','65532:65532','--tmpfs','/tmp:rw,noexec,nosuid,size=16m,mode=1777','--memory','128m','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',image],check=True,stdout=subprocess.DEVNULL)
 connect(n);subprocess.run(['docker','start',n],check=True,stdout=subprocess.DEVNULL);time.sleep(2);return n
def deploy(a):
 if set(a)!={'project_slug','artifact_image_id','execution_id'} or a['project_slug']!=SLUG:raise ValueError('invalid_request')
 eid=str(a['execution_id']);
 if not re.fullmatch(r'can_[0-9a-f]{24}',eid):raise ValueError('invalid_execution_id')
 image=inspect_image(a['artifact_image_id']);c=db();e=c.execute('select * from releases where execution_id=?',(eid,)).fetchone()
 if e:return json.loads(e['result_json'])|{'idempotent':True}
 p=cur(c);n=create(image,eid);pre=smoke(n)
 if p:disconnect(p['container_name']);connect(p['container_name'])
 disconnect(n);connect(n,True);post=smoke(n);t=int(time.time())
 if p and pre['sha256']==p['body_sha256']:raise RuntimeError('canary_content_not_distinct')
 result={'ok':True,'status':'active','project_slug':SLUG,'artifact_image_id':image,'container_name':n,'previous_release_id':p['id'] if p else None,'pre_switch_smoke':pre,'post_switch_smoke':post,'body_sha256':post['sha256'],'atomic_switch':True,'network_internal':True,'published_ports':[],'public_traffic':False,'secrets_exposed':False}
 rid=c.execute('insert into releases(execution_id,image_id,container_name,status,created_at,previous_release_id,body_sha256,result_json) values(?,?,?,?,?,?,?,?)',(eid,image,n,'active',t,p['id'] if p else None,post['sha256'],json.dumps(result,separators=(',',':')))).lastrowid
 if p:c.execute("update releases set status='standby' where id=?",(p['id'],))
 c.execute("insert into state(key,value) values('current_release_id',?) on conflict(key) do update set value=excluded.value",(str(rid),));c.commit();return result|{'release_id':rid,'idempotent':False}
def rollback(a):
 if set(a)!={'project_slug','execution_id'} or a['project_slug']!=SLUG:raise ValueError('invalid_request')
 eid=str(a['execution_id']);
 if not re.fullmatch(r'crb_[0-9a-f]{24}',eid):raise ValueError('invalid_execution_id')
 c=db();p=cur(c)
 if not p:raise ValueError('current_missing')
 old=c.execute('select * from releases where id=?',(p['previous_release_id'],)).fetchone()
 if not old:raise ValueError('previous_missing')
 old=dict(old);before=smoke(old['container_name']);disconnect(p['container_name']);connect(p['container_name']);disconnect(old['container_name']);connect(old['container_name'],True);after=smoke(old['container_name'])
 if before['sha256']==p['body_sha256']:raise RuntimeError('rollback_content_not_distinct')
 c.execute("update releases set status='rolled_back' where id=?",(p['id'],));c.execute("update releases set status='active' where id=?",(old['id'],));c.execute("update state set value=? where key='current_release_id'",(str(old['id']),));c.commit()
 return {'ok':True,'status':'rolled_back','from_release_id':p['id'],'to_release_id':old['id'],'artifact_image_id':old['image_id'],'body_sha256':after['sha256'],'atomic_switch':True,'public_traffic':False,'secrets_exposed':False}
def status():
 c=db();return {'ok':True,'project_slug':SLUG,'current':cur(c),'history':[dict(r) for r in c.execute('select id,execution_id,image_id,container_name,status,created_at,previous_release_id,body_sha256 from releases order by id desc limit 10')],'network_internal':True,'public_traffic':False,'secrets_exposed':False}
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def out(self,n,x):b=json.dumps(x,separators=(',',':')).encode();self.send_response(n);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=='/health':return self.out(200,{'ok':True,'service':'production-canary-executor','internal_only':True,'public_traffic':False})
  if not auth(self.headers):return self.out(401,{'ok':False,'error':'unauthorized'})
  return self.out(200,status()) if self.path=='/v1/status' else self.out(404,{'ok':False,'error':'not_found'})
 def do_POST(self):
  if not auth(self.headers):return self.out(401,{'ok':False,'error':'unauthorized'})
  try:a=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}');x=deploy(a) if self.path=='/v1/deploy' else rollback(a) if self.path=='/v1/rollback' else None
  except ValueError as e:return self.out(400,{'ok':False,'error':str(e)})
  except Exception as e:return self.out(502,{'ok':False,'error':type(e).__name__,'secrets_exposed':False})
  return self.out(200,x) if x else self.out(404,{'ok':False,'error':'not_found'})
ThreadingHTTPServer((HOST,PORT),H).serve_forever()
