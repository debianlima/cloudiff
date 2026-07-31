#!/usr/bin/env python3
import json,os,re,sqlite3,subprocess,time,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
DB='/var/lib/cloudif/production-public/state.sqlite3';TOKEN=os.environ['CLOUDIF_PRODUCTION_PUBLIC_TOKEN'];HOST='10.62.91.2';PORT=18220;NET='cloudif-publications';ALIAS='cloudif-production-active';SLUG='atalhos-cloudif-iff1860746'
def conn():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('CREATE TABLE IF NOT EXISTS releases(id INTEGER PRIMARY KEY AUTOINCREMENT,execution_id TEXT UNIQUE,image_id TEXT,container_name TEXT,status TEXT,created_at INTEGER,previous_release_id INTEGER,body_sha256 TEXT,result_json TEXT)');c.execute('CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT)');c.commit();return c
def auth(h):return h.get('Authorization','')=='Bearer '+TOKEN
def current(c):
 r=c.execute("select r.* from state s join releases r on r.id=cast(s.value as integer) where s.key='current_release_id'").fetchone();return dict(r) if r else None
def run(cmd,**kw):return subprocess.run(cmd,check=True,text=True,capture_output=True,**kw)
def inspect_image(i):
 if not re.fullmatch(r'sha256:[0-9a-f]{64}',str(i)):raise ValueError('invalid_image_id')
 x=json.loads(run(['docker','image','inspect',i]).stdout)[0];u=str((x.get('Config') or {}).get('User') or '')
 if u.split(':')[0] in ('','0','root'):raise ValueError('image_not_rootless')
 return x['Id']
def netinfo(name):
 x=json.loads(run(['docker','inspect',name]).stdout)[0];return x['NetworkSettings']['Networks'].get(NET)
def disconnect(name):subprocess.run(['docker','network','disconnect',NET,name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def connect(name,alias=False):
 cmd=['docker','network','connect']+(['--alias',ALIAS] if alias else [])+[NET,name];subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
def smoke(name):
 ni=netinfo(name)
 if not ni:raise RuntimeError('candidate_not_connected')
 with urllib.request.urlopen('http://'+ni['IPAddress']+':8080/',timeout=12) as r:b=r.read();code=r.status
 import hashlib
 if code!=200:raise RuntimeError('health_failed')
 return {'status':code,'sha256':hashlib.sha256(b).hexdigest(),'size':len(b)}
def external():
 with urllib.request.urlopen('http://10.62.91.2:18150/production/atalhos-cloudif-iff1860746/',timeout=15) as r:b=r.read();code=r.status
 import hashlib
 return {'status':code,'sha256':hashlib.sha256(b).hexdigest(),'size':len(b)}
def create(image,eid):
 n='cloudif-prod-public-'+eid[-12:];subprocess.run(['docker','rm','-f',n],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 subprocess.run(['docker','create','--name',n,'--read-only','--user','65532:65532','--tmpfs','/tmp:rw,noexec,nosuid,size=16m,mode=1777','--memory','192m','--pids-limit','160','--cap-drop','ALL','--security-opt','no-new-privileges',image],check=True,stdout=subprocess.DEVNULL)
 connect(n);subprocess.run(['docker','start',n],check=True,stdout=subprocess.DEVNULL);time.sleep(2);return n
def deploy(a):
 if set(a)!={'project_slug','artifact_image_id','execution_id'} or a['project_slug']!=SLUG:raise ValueError('invalid_request')
 eid=str(a['execution_id'])
 if not re.fullmatch(r'prd_[0-9a-f]{24}',eid):raise ValueError('invalid_execution_id')
 image=inspect_image(a['artifact_image_id']);c=conn();old=c.execute('select * from releases where execution_id=?',(eid,)).fetchone()
 if old:return json.loads(old['result_json'])|{'idempotent':True}
 prev=current(c);n=create(image,eid);pre=smoke(n)
 if prev and netinfo(prev['container_name']):disconnect(prev['container_name']);connect(prev['container_name'])
 disconnect(n);connect(n,True);time.sleep(1)
 try:post=external()
 except Exception:
  disconnect(n);connect(n)
  if prev:disconnect(prev['container_name']);connect(prev['container_name'],True)
  raise
 if post['status']!=200 or post['sha256']!=pre['sha256']:
  disconnect(n);connect(n)
  if prev:disconnect(prev['container_name']);connect(prev['container_name'],True)
  raise RuntimeError('external_health_mismatch')
 t=int(time.time());result={'ok':True,'status':'active','project_slug':SLUG,'artifact_image_id':image,'container_name':n,'previous_release_id':prev['id'] if prev else None,'internal_health':pre,'external_health':post,'body_sha256':post['sha256'],'atomic_switch':True,'public_traffic':True,'rollback_ready':bool(prev),'secrets_exposed':False}
 rid=c.execute('insert into releases(execution_id,image_id,container_name,status,created_at,previous_release_id,body_sha256,result_json) values(?,?,?,?,?,?,?,?)',(eid,image,n,'active',t,prev['id'] if prev else None,post['sha256'],json.dumps(result,separators=(',',':')))).lastrowid
 if prev:c.execute("update releases set status='standby' where id=?",(prev['id'],))
 c.execute("insert into state(key,value) values('current_release_id',?) on conflict(key) do update set value=excluded.value",(str(rid),));c.commit();return result|{'release_id':rid,'idempotent':False}
def rollback(a):
 if set(a)!={'project_slug','execution_id'} or a['project_slug']!=SLUG:raise ValueError('invalid_request')
 eid=str(a['execution_id'])
 if not re.fullmatch(r'prb_[0-9a-f]{24}',eid):raise ValueError('invalid_execution_id')
 c=conn();cur=current(c)
 if not cur or not cur['previous_release_id']:raise ValueError('previous_missing')
 old=dict(c.execute('select * from releases where id=?',(cur['previous_release_id'],)).fetchone())
 if not netinfo(old['container_name']):connect(old['container_name'])
 before=smoke(old['container_name']);disconnect(cur['container_name']);connect(cur['container_name']);disconnect(old['container_name']);connect(old['container_name'],True);time.sleep(1);after=external()
 if after['sha256']!=before['sha256']:raise RuntimeError('rollback_health_mismatch')
 c.execute("update releases set status='rolled_back' where id=?",(cur['id'],));c.execute("update releases set status='active' where id=?",(old['id'],));c.execute("update state set value=? where key='current_release_id'",(str(old['id']),));c.commit()
 return {'ok':True,'status':'rolled_back','from_release_id':cur['id'],'to_release_id':old['id'],'artifact_image_id':old['image_id'],'external_health':after,'atomic_switch':True,'public_traffic':True,'secrets_exposed':False}
def status():
 c=conn();return {'ok':True,'project_slug':SLUG,'current':current(c),'history':[dict(r) for r in c.execute('select id,execution_id,image_id,container_name,status,created_at,previous_release_id,body_sha256 from releases order by id desc limit 20')],'public_url':'https://cloudiff.duckdns.org/production/atalhos-cloudif-iff1860746/','public_traffic':current(c) is not None,'secrets_exposed':False}
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def out(self,n,x):b=json.dumps(x,separators=(',',':')).encode();self.send_response(n);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=='/health':return self.out(200,{'ok':True,'service':'production-public-executor'})
  if not auth(self.headers):return self.out(401,{'ok':False,'error':'unauthorized'})
  return self.out(200,status()) if self.path=='/v1/status' else self.out(404,{'ok':False,'error':'not_found'})
 def do_POST(self):
  if not auth(self.headers):return self.out(401,{'ok':False,'error':'unauthorized'})
  try:a=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}');x=deploy(a) if self.path=='/v1/deploy' else rollback(a) if self.path=='/v1/rollback' else None
  except ValueError as e:return self.out(400,{'ok':False,'error':str(e)})
  except Exception as e:return self.out(502,{'ok':False,'error':type(e).__name__,'secrets_exposed':False})
  return self.out(200,x) if x else self.out(404,{'ok':False,'error':'not_found'})
ThreadingHTTPServer((HOST,PORT),H).serve_forever()
