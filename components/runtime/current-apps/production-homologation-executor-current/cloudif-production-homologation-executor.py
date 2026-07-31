#!/usr/bin/env python3
import hashlib,json,os,re,sqlite3,subprocess,time,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
DB='/var/lib/cloudif/production-homologation/state.sqlite3';TOKEN=os.environ.get('CLOUDIF_PRODUCTION_HOMOLOGATION_TOKEN','');HOST='10.62.91.2';PORT=18217;NETWORK='cloudif-publications';ALIAS='cloudif-prod-homologation';SLUG='atalhos-cloudif-iff1860746'
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('CREATE TABLE IF NOT EXISTS releases(id INTEGER PRIMARY KEY AUTOINCREMENT,execution_id TEXT UNIQUE,project_slug TEXT,image_id TEXT,container_name TEXT,status TEXT,created_at INTEGER,activated_at INTEGER,removed_at INTEGER,previous_release_id INTEGER,health_sha256 TEXT,result_json TEXT)');c.execute('CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT)');c.commit();return c
def auth(h):return bool(TOKEN) and h.get('Authorization','')=='Bearer '+TOKEN
def current(c):
 r=c.execute("select r.* from state s join releases r on r.id=cast(s.value as integer) where s.key='current_release_id'").fetchone();return dict(r) if r else None
def image_proof(image_id):
 if not re.fullmatch(r'sha256:[0-9a-f]{64}',image_id):raise ValueError('invalid_image_id')
 try:x=json.loads(subprocess.check_output(['docker','image','inspect',image_id],text=True))[0]
 except Exception:raise ValueError('image_not_found')
 user=str((x.get('Config') or {}).get('User') or '')
 if user.split(':')[0] in ('','0','root'):raise ValueError('image_not_rootless')
 return {'id':str(x.get('Id') or ''),'user':user}
def running(name):return subprocess.run(['docker','inspect','-f','{{.State.Running}}',name],capture_output=True,text=True).stdout.strip()=='true'
def smoke(name):
 x=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0];ip=str((((x.get('NetworkSettings') or {}).get('Networks') or {}).get('cloudif-publications') or {}).get('IPAddress') or '')
 if not ip:raise RuntimeError('candidate_ip_missing')
 with urllib.request.urlopen('http://'+ip+':8080/__cloudif_health',timeout=10) as r:
  body=r.read();code=r.status
 if code!=200:raise RuntimeError('candidate_smoke_failed')
 return {'status':code,'sha256':hashlib.sha256(body).hexdigest(),'size':len(body)}
def connect_alias(name):subprocess.run(['docker','network','connect','--alias',ALIAS,NETWORK,name],check=True,stdout=subprocess.DEVNULL)
def disconnect(name):subprocess.run(['docker','network','disconnect',NETWORK,name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def connect_plain(name):
 x=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0];nets=((x.get('NetworkSettings') or {}).get('Networks') or {})
 if NETWORK not in nets:subprocess.run(['docker','network','connect',NETWORK,name],check=True,stdout=subprocess.DEVNULL)
def create_container(image_id,execution_id):
 name='cloudif-prod-h-'+execution_id[-12:]
 subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 subprocess.run(['docker','create','--name',name,'--read-only','--user','65532:65532','--tmpfs','/tmp:rw,noexec,nosuid,size=16m,mode=1777','--memory','128m','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',image_id],check=True,stdout=subprocess.DEVNULL)
 subprocess.run(['docker','network','connect',NETWORK,name],check=True,stdout=subprocess.DEVNULL);subprocess.run(['docker','start',name],check=True,stdout=subprocess.DEVNULL);time.sleep(2)
 if not running(name):raise RuntimeError('candidate_not_running')
 return name
def deploy(a):
 if set(a)!={'project_slug','artifact_image_id','execution_id'}:raise ValueError('invalid_request')
 if a['project_slug']!=SLUG:raise ValueError('project_not_allowed')
 eid=str(a['execution_id']);
 if not re.fullmatch(r'exe_[0-9a-f]{24}',eid):raise ValueError('invalid_execution_id')
 proof=image_proof(a['artifact_image_id']);c=db();existing=c.execute('select * from releases where execution_id=?',(eid,)).fetchone()
 if existing:
  x=dict(existing);x['result']=json.loads(x.pop('result_json') or '{}');x['idempotent']=True;x['secrets_exposed']=False;return x
 prev=current(c);name=create_container(proof['id'],eid);pre=smoke(name)
 if prev and running(prev['container_name']):disconnect(prev['container_name']);connect_plain(prev['container_name'])
 disconnect(name);connect_alias(name);time.sleep(1)
 post=smoke(name);t=int(time.time());result={'ok':True,'status':'active','project_slug':SLUG,'artifact_image_id':proof['id'],'container_name':name,'previous_release_id':prev['id'] if prev else None,'pre_switch_smoke':pre,'post_switch_smoke':post,'runtime':{'user':'65532:65532','read_only':True,'cap_drop':['ALL'],'published_ports':[],'network_alias':ALIAS},'atomic_switch':True,'rollback_ready':bool(prev),'secrets_exposed':False}
 cur=c.execute('insert into releases(execution_id,project_slug,image_id,container_name,status,created_at,activated_at,removed_at,previous_release_id,health_sha256,result_json) values(?,?,?,?,?,?,?,?,?,?,?)',(eid,SLUG,proof['id'],name,'active',t,t,0,prev['id'] if prev else None,post['sha256'],json.dumps(result,separators=(',',':')))).lastrowid
 if prev:c.execute("update releases set status='standby' where id=?",(prev['id'],))
 c.execute("insert into state(key,value) values('current_release_id',?) on conflict(key) do update set value=excluded.value",(str(cur),));c.commit();return result|{'release_id':cur,'idempotent':False}
def rollback(a):
 if set(a)!={'project_slug','execution_id'}:raise ValueError('invalid_request')
 if a['project_slug']!=SLUG:raise ValueError('project_not_allowed')
 eid=str(a['execution_id']);
 if not re.fullmatch(r'rbk_[0-9a-f]{24}',eid):raise ValueError('invalid_execution_id')
 c=db();cur=current(c)
 if not cur:raise ValueError('current_release_missing')
 old=c.execute('select * from releases where id=?',(cur['previous_release_id'],)).fetchone()
 if not old:raise ValueError('previous_release_missing')
 old=dict(old)
 if not running(old['container_name']):raise RuntimeError('previous_container_not_running')
 connect_plain(old['container_name']);before=smoke(old['container_name']);disconnect(cur['container_name']);connect_plain(cur['container_name']);disconnect(old['container_name']);connect_alias(old['container_name']);time.sleep(1);after=smoke(old['container_name']);t=int(time.time())
 c.execute("update releases set status='rolled_back',removed_at=? where id=?",(t,cur['id']));c.execute("update releases set status='active',activated_at=? where id=?",(t,old['id']));c.execute("update state set value=? where key='current_release_id'",(str(old['id']),));c.commit()
 return {'ok':True,'status':'rolled_back','project_slug':SLUG,'from_release_id':cur['id'],'to_release_id':old['id'],'artifact_image_id':old['image_id'],'pre_switch_smoke':before,'post_switch_smoke':after,'atomic_switch':True,'secrets_exposed':False}
def status():
 c=db();cur=current(c);hist=[dict(r) for r in c.execute('select id,execution_id,image_id,container_name,status,created_at,activated_at,previous_release_id,health_sha256 from releases order by id desc limit 10')]
 return {'ok':True,'project_slug':SLUG,'current':cur,'history':hist,'public_path':'/production-homologation/'+SLUG+'/','secrets_exposed':False}
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def sendj(self,n,x):
  b=json.dumps(x,separators=(',',':')).encode();self.send_response(n);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=='/health':return self.sendj(200,{'ok':True,'service':'production-homologation-executor','project_slug':SLUG,'atomic_switch':True,'secrets_exposed':False})
  if not auth(self.headers):return self.sendj(401,{'ok':False,'error':'unauthorized'})
  if self.path=='/v1/status':return self.sendj(200,status())
  return self.sendj(404,{'ok':False,'error':'not_found'})
 def do_POST(self):
  if not auth(self.headers):return self.sendj(401,{'ok':False,'error':'unauthorized'})
  try:a=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
  except:return self.sendj(400,{'ok':False,'error':'invalid_json'})
  try:
   if self.path=='/v1/deploy':return self.sendj(200,deploy(a))
   if self.path=='/v1/rollback':return self.sendj(200,rollback(a))
   return self.sendj(404,{'ok':False,'error':'not_found'})
  except ValueError as e:return self.sendj(400,{'ok':False,'error':str(e)})
  except Exception:return self.sendj(502,{'ok':False,'error':'operation_failed','secrets_exposed':False})
if __name__=='__main__':ThreadingHTTPServer((HOST,PORT),H).serve_forever()
