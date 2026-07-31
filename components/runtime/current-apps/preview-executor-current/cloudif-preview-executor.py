#!/usr/bin/env python3
import json,os,re,sqlite3,subprocess,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
DB='/var/lib/cloudif/preview-executor/previews.sqlite3';TOKEN=os.environ.get('CLOUDIF_PREVIEW_EXECUTOR_TOKEN','');HOST='10.62.91.2';PORT=18215;NETWORK='cloudif-publications'
PROJECTS={'atalhos-cloudif-iff1860746','primeiros-passos-cloudif-iff1860746','validacao-botao-cloudif-iff1860746'}
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('CREATE TABLE IF NOT EXISTS previews(id TEXT PRIMARY KEY,project_slug TEXT,container_name TEXT,url TEXT,created_at INTEGER,expires_at INTEGER,status TEXT,site_digest TEXT)')
 cols={r[1] for r in c.execute('pragma table_info(previews)')}
 if 'artifact_image_id' not in cols:c.execute('alter table previews add column artifact_image_id TEXT')
 if 'immutable_source_digest' not in cols:c.execute('alter table previews add column immutable_source_digest TEXT')
 c.commit();return c
def auth(h):return bool(TOKEN) and h.get('Authorization','')=='Bearer '+TOKEN
def image_proof(image_id):
 if not re.fullmatch(r'sha256:[0-9a-f]{64}',image_id):raise ValueError('invalid_artifact_image_id')
 try:x=json.loads(subprocess.check_output(['docker','image','inspect',image_id],text=True))[0]
 except Exception:raise ValueError('artifact_image_not_found')
 user=str((x.get('Config') or {}).get('User') or '')
 if user.split(':')[0] in ('','0','root'):raise ValueError('artifact_image_not_rootless')
 return {'user':user,'image_id':str(x.get('Id') or '')}
def create(a):
 pid=a.get('preview_id','');slug=a.get('project_slug','');ttl=int(a.get('ttl_seconds') or 3600);image_id=str(a.get('artifact_image_id') or '');source_digest=str(a.get('immutable_source_digest') or '')
 if not re.fullmatch(r'prv_[0-9a-f]{20}',pid):raise ValueError('invalid_preview_id')
 if slug not in PROJECTS:raise ValueError('project_not_allowed')
 if ttl<300 or ttl>86400:raise ValueError('ttl_not_allowed')
 if not re.fullmatch(r'[0-9a-f]{64}',source_digest):raise ValueError('invalid_immutable_source_digest')
 proof=image_proof(image_id);host='prv-'+pid[4:];name='cloudif-'+host;url='https://cloudiff.duckdns.org/preview/'+pid+'/'
 c=db();r=c.execute('select * from previews where id=?',(pid,)).fetchone()
 if r:
  if (r['artifact_image_id'] or '')!=image_id or (r['immutable_source_digest'] or '')!=source_digest:raise ValueError('preview_artifact_mismatch')
  return {'ok':True,'idempotent':True,'preview_id':pid,'url':r['url'],'status':r['status'],'expires_at':r['expires_at'],'artifact_image_id':r['artifact_image_id'],'immutable_source_digest':r['immutable_source_digest'],'secrets_exposed':False}
 subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 subprocess.run(['docker','run','-d','--name',name,'--network',NETWORK,'--read-only','--user','65532:65532','--tmpfs','/tmp:rw,noexec,nosuid,size=16m,mode=1777','--memory','128m','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',image_id],check=True,stdout=subprocess.DEVNULL)
 t=int(time.time());c.execute('insert into previews(id,project_slug,container_name,url,created_at,expires_at,status,site_digest,artifact_image_id,immutable_source_digest) values(?,?,?,?,?,?,?,?,?,?)',(pid,slug,name,url,t,t+ttl,'active',source_digest,image_id,source_digest));c.commit()
 return {'ok':True,'idempotent':False,'preview_id':pid,'url':url,'status':'active','expires_at':t+ttl,'site_digest':source_digest,'artifact_image_id':image_id,'immutable_source_digest':source_digest,'image_user':proof['user'],'published_ports':[],'network':NETWORK,'secrets_exposed':False}
def get(pid):
 c=db();r=c.execute('select * from previews where id=?',(pid,)).fetchone()
 if not r:return None
 x=dict(r);x['container_running']=subprocess.run(['docker','inspect','-f','{{.State.Running}}',x['container_name']],capture_output=True,text=True).stdout.strip()=='true';x['secrets_exposed']=False;return x
def remove(pid):
 c=db();r=c.execute('select * from previews where id=?',(pid,)).fetchone()
 if not r:return {'ok':True,'removed':False,'idempotent':True,'secrets_exposed':False}
 subprocess.run(['docker','rm','-f',r['container_name']],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);c.execute("update previews set status='removed' where id=?",(pid,));c.commit();return {'ok':True,'removed':True,'preview_id':pid,'secrets_exposed':False}
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def sendj(self,n,x):
  b=json.dumps(x,separators=(',',':')).encode();self.send_response(n);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=='/health':return self.sendj(200,{'ok':True,'service':'preview-executor','mode':'immutable-artifact','listen_port':8080,'secrets_exposed':False})
  if not auth(self.headers):return self.sendj(401,{'ok':False,'error':'unauthorized'})
  m=re.fullmatch(r'/v1/previews/(prv_[0-9a-f]{20})',self.path)
  if not m:return self.sendj(404,{'ok':False,'error':'not_found'})
  x=get(m.group(1));return self.sendj(200,{'ok':True,'preview':x}) if x else self.sendj(404,{'ok':False,'error':'preview_not_found'})
 def do_POST(self):
  if not auth(self.headers):return self.sendj(401,{'ok':False,'error':'unauthorized'})
  try:a=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
  except:return self.sendj(400,{'ok':False,'error':'invalid_json'})
  try:
   if self.path=='/v1/previews':return self.sendj(201,create(a))
   m=re.fullmatch(r'/v1/previews/(prv_[0-9a-f]{20})/remove',self.path)
   if m:return self.sendj(200,remove(m.group(1)))
   return self.sendj(404,{'ok':False,'error':'not_found'})
  except ValueError as e:return self.sendj(400,{'ok':False,'error':str(e)})
  except subprocess.CalledProcessError:return self.sendj(500,{'ok':False,'error':'container_create_failed'})
if __name__=='__main__':ThreadingHTTPServer((HOST,PORT),H).serve_forever()
