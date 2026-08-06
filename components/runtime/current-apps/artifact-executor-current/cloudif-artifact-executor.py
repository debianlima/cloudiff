#!/usr/bin/env python3
import hashlib,json,os,re,sqlite3,subprocess,tempfile,time,urllib.parse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from cloudif_multiservice_artifact import ArtifactError, build_multiservice
DB='/var/lib/cloudif/artifact-executor/artifacts.sqlite3';TOKEN=os.environ.get('CLOUDIF_ARTIFACT_EXECUTOR_TOKEN','');HOST='10.62.91.2';PORT=18216
BASE='cgr.dev/chainguard/nginx@sha256:e4ff957080737c90a9ecfeaa40e3d19ea9d687e9cacda2f2a031c75ffcdd72b7'
SYFT=os.environ['SYFT_IMAGE'];TRIVY=os.environ['TRIVY_IMAGE'];CACHE='/srv/cloudif/scanners/trivy-cache'
SITES={'atalhos-cloudif-iff1860746':'/etc/komodo/stacks/cloudif-atalhos-cloudif-iff1860746/site','primeiros-passos-cloudif-iff1860746':'/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site','validacao-botao-cloudif-iff1860746':'/etc/komodo/stacks/cloudif-validacao-botao-cloudif-iff1860746/site'}
NGINX='''worker_processes auto;\npid /tmp/nginx.pid;\nevents { worker_connections 1024; }\nhttp { include /etc/nginx/mime.types; default_type application/octet-stream; access_log off; error_log /dev/stderr warn; sendfile on; client_body_temp_path /tmp/client_temp; proxy_temp_path /tmp/proxy_temp; fastcgi_temp_path /tmp/fastcgi_temp; uwsgi_temp_path /tmp/uwsgi_temp; scgi_temp_path /tmp/scgi_temp; server { listen 8080; server_name _; root /usr/share/nginx/html; index index.html; location = /__cloudif_health { default_type application/json; return 200 '{"ok":true,"service":"cloudif-static-artifact"}'; } location / { try_files $uri $uri/ /index.html =404; } } }\n'''
def db():
 c=sqlite3.connect(DB,timeout=30);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('CREATE TABLE IF NOT EXISTS artifacts(build_id TEXT PRIMARY KEY,project_slug TEXT,status TEXT,created_at INTEGER,updated_at INTEGER,result_json TEXT,log_text TEXT)');return c
def auth(h):return bool(TOKEN) and h.get('Authorization','')=='Bearer '+TOKEN
def sanitize(x):return re.sub(r'(?i)(token|password|secret|authorization|api[_-]?key)\s*[:=]\s*\S+',r'\1=[redacted]',str(x))[:20000]
def run(cmd,log,timeout=900):
 p=subprocess.run(cmd,text=True,capture_output=True,timeout=timeout);log.append('$ '+' '.join(cmd[:4])+' ...\n'+sanitize(p.stdout)+sanitize(p.stderr));
 if p.returncode:raise RuntimeError('command_failed')
def build(a):
 slug=a.get('project_slug','');bid=a.get('build_id','')
 if slug not in SITES:raise ValueError('project_not_allowed')
 if not re.fullmatch(r'[0-9a-f-]{36}',bid):raise ValueError('invalid_build_id')
 c=db();r=c.execute('select * from artifacts where build_id=?',(bid,)).fetchone()
 if r and r['status']=='succeeded':return json.loads(r['result_json'])|{'idempotent':True}
 t=int(time.time());c.execute('insert or replace into artifacts values(?,?,?,?,?,?,?)',(bid,slug,'running',t,t,None,'reserved\n'));c.commit();log=[]
 out=f'/srv/cloudif/artifacts/{slug}/{bid}';ctx=f'{out}/context';os.makedirs(ctx+'/site',exist_ok=True)
 subprocess.run(['rm','-rf',ctx+'/site'],check=True);subprocess.run(['mkdir','-p',ctx+'/site'],check=True);subprocess.run(['cp','-a',SITES[slug]+'/.',ctx+'/site/'],check=True)
 open(ctx+'/nginx.conf','w').write(NGINX);open(ctx+'/Dockerfile','w').write(f'FROM {BASE}\nCOPY --chown=65532:65532 site/ /usr/share/nginx/html/\nCOPY --chown=65532:65532 nginx.conf /etc/nginx/nginx.conf\nEXPOSE 8080\n')
 tag=f'cloudif-static/{slug}:build-{bid[:12]}'
 try:
  run(['docker','build','--pull=false','--network=none','-t',tag,ctx],log)
  iid=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip()
  name='cloudif-artifact-proof-'+bid[:8];subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  run(['docker','run','-d','--name',name,'--network','none','--read-only','--user','65532:65532','--tmpfs','/tmp:rw,noexec,nosuid,size=16m,mode=1777','--memory','128m','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',tag],log,120);time.sleep(2)
  running=subprocess.check_output(['docker','inspect','-f','{{.State.Running}}',name],text=True).strip()=='true';subprocess.run(['docker','rm','-f',name],check=True,stdout=subprocess.DEVNULL);assert running
  os.makedirs(out,exist_ok=True)
  run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=256m,mode=1777','--tmpfs','/.cache:rw,noexec,nosuid,size=64m,mode=1777','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','768m','--pids-limit','256','-e','SYFT_CHECK_FOR_APP_UPDATE=false','-v','/var/run/docker.sock:/var/run/docker.sock:ro','-v',out+':/out',SYFT,tag,'-o','cyclonedx-json=/out/sbom.cdx.json'],log)
  run(['docker','run','--rm','--network','none','--tmpfs','/tmp:rw,noexec,nosuid,size=256m,mode=1777','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','1g','--pids-limit','256','-v','/var/run/docker.sock:/var/run/docker.sock:ro','-v',CACHE+':/root/.cache/trivy','-v',out+':/out',TRIVY,'image','--skip-db-update','--format','json','--output','/out/trivy.json',tag],log)
  sb=json.load(open(out+'/sbom.cdx.json'));sc=json.load(open(out+'/trivy.json'));counts={}
  for rr in sc.get('Results') or []:
   for v in rr.get('Vulnerabilities') or []:counts[v.get('Severity','UNKNOWN').upper()]=counts.get(v.get('Severity','UNKNOWN').upper(),0)+1
  blocked=counts.get('HIGH',0)+counts.get('CRITICAL',0)>0
  res={'ok':not blocked,'build_id':bid,'project_slug':slug,'artifact_tag':tag,'artifact_image_id':iid,'base_image':BASE,'sbom_ready':True,'sbom_format':sb.get('bomFormat'),'sbom_spec_version':sb.get('specVersion'),'sbom_components':len(sb.get('components') or []),'sbom_sha256':hashlib.sha256(open(out+'/sbom.cdx.json','rb').read()).hexdigest(),'scanner_ready':True,'scanner_policy':'block HIGH/CRITICAL','scanner_counts':counts,'scanner_sha256':hashlib.sha256(open(out+'/trivy.json','rb').read()).hexdigest(),'scanner_blocked':blocked,'runtime_proof':{'user':'65532:65532','read_only':True,'cap_drop':['ALL'],'published_ports':[],'listen_port':8080},'production_ready':not blocked,'secrets_exposed':False,'idempotent':False}
  c=db();c.execute('update artifacts set status=?,updated_at=?,result_json=?,log_text=? where build_id=?',('succeeded' if not blocked else 'blocked',int(time.time()),json.dumps(res,separators=(',',':')),sanitize(''.join(log)),bid));c.commit();return res
 except Exception as e:
  c=db();c.execute('update artifacts set status=?,updated_at=?,result_json=?,log_text=? where build_id=?',('failed',int(time.time()),json.dumps({'ok':False,'error':'artifact_pipeline_failed','secrets_exposed':False}),sanitize(''.join(log)+'\n'+type(e).__name__),bid));c.commit();raise
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def sendj(self,n,x):
  b=json.dumps(x,separators=(',',':')).encode();self.send_response(n);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=='/health':return self.sendj(200,{'ok':True,'service':'artifact-executor','base_image':BASE,'secrets_exposed':False})
  if not auth(self.headers):return self.sendj(401,{'ok':False,'error':'unauthorized'})
  m=re.fullmatch(r'/v1/artifacts/([0-9a-f-]{36})',self.path)
  if not m:return self.sendj(404,{'ok':False,'error':'not_found'})
  r=db().execute('select status,result_json from artifacts where build_id=?',(m.group(1),)).fetchone();return self.sendj(200,{'ok':True,'status':r['status'],'artifact':json.loads(r['result_json'] or 'null')}) if r else self.sendj(404,{'ok':False,'error':'artifact_not_found'})
 def do_POST(self):
  if not auth(self.headers):return self.sendj(401,{'ok':False,'error':'unauthorized'})
  try:a=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
  except:return self.sendj(400,{'ok':False,'error':'invalid_json'})
  try:
   if self.path=='/v1/artifacts':return self.sendj(200,build(a))
   if self.path in {'/v1/build', '/v1/multiservice/build'}:
    profile=str(a.get('profile') or ('multiservice-v1' if self.path.endswith('/multiservice/build') else ''))
    if profile not in {'static-v1', 'multiservice-v1'}:return self.sendj(422,{'ok':False,'error':{'code':'invalid_profile','message':'profile deve ser static-v1 ou multiservice-v1.'}})
    if profile=='multiservice-v1':
     payload=a
     return self.sendj(200,build_multiservice(payload))
    return self.sendj(200,build(a))
   return self.sendj(404,{'ok':False,'error':'not_found'})
  except ArtifactError as exc:return self.sendj(exc.http_status,{'ok':False,'error':exc.as_dict(),'secrets_exposed':False})
  except ValueError as e:return self.sendj(400,{'ok':False,'error':str(e)})
  except Exception:return self.sendj(500,{'ok':False,'error':'artifact_pipeline_failed','secrets_exposed':False})
SCANNER_POLICY={'scannerOfflineCache':True,'network':'none','block':['HIGH','CRITICAL']}
if __name__=='__main__':ThreadingHTTPServer((HOST,PORT),H).serve_forever()
