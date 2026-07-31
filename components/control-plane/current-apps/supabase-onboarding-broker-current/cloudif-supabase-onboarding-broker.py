#!/usr/bin/env python3
import hmac,json,os,re,sqlite3,subprocess,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
TOKEN=os.environ.get('CLOUDIF_SUPABASE_ONBOARDING_TOKEN','')
DB=Path(os.environ.get('CLOUDIF_PROJECT_SNAPSHOT_DB','/var/lib/cloudif/control-plane/control-plane.db'))
HOST=os.environ.get('CLOUDIF_SUPABASE_ONBOARDING_HOST','127.0.0.1');PORT=int(os.environ.get('CLOUDIF_SUPABASE_ONBOARDING_PORT','18209'))
ENSURE='/srv/cloudif/bin/cloudif-supabase-ensure-user-tenant.sh'
SLUG=re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
TENANT=re.compile(r'^[a-z0-9][a-z0-9_-]{0,62}$')
def send(h,c,d):
 b=json.dumps(d,ensure_ascii=False,separators=(',',':')).encode();h.send_response(c);h.send_header('Content-Type','application/json');h.send_header('Cache-Control','no-store');h.send_header('Content-Length',str(len(b)));h.end_headers();h.wfile.write(b)
def project(slug):
 c=sqlite3.connect(f'file:{DB}?mode=ro&immutable=1',uri=True);c.row_factory=sqlite3.Row;r=c.execute('select slug,tenant,status from projects where slug=?',(slug,)).fetchone();c.close();return dict(r) if r else None
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def auth(self):return bool(TOKEN) and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+TOKEN)
 def do_GET(self):
  if self.path=='/health':return send(self,200,{'ok':True,'service':'cloudif-supabase-onboarding-broker'})
  return send(self,404,{'ok':False,'error':'not_found'})
 def do_POST(self):
  if not self.auth():return send(self,401,{'ok':False,'error':'unauthorized'})
  if self.path!='/v1/ensure':return send(self,404,{'ok':False,'error':'not_found'})
  try:n=int(self.headers.get('Content-Length','0'));d=json.loads(self.rfile.read(n))
  except Exception:return send(self,400,{'ok':False,'error':'invalid_request'})
  if set(d)!={'project_slug','tenant'}:return send(self,400,{'ok':False,'error':'invalid_request'})
  slug=str(d['project_slug']).strip();tenant=str(d['tenant']).strip()
  if not SLUG.fullmatch(slug) or not TENANT.fullmatch(tenant):return send(self,400,{'ok':False,'error':'invalid_request'})
  p=project(slug)
  if not p:return send(self,404,{'ok':False,'error':'project_not_found'})
  if str(p.get('tenant') or '')!=tenant:return send(self,409,{'ok':False,'error':'tenant_mismatch'})
  started=time.time();r=subprocess.run([ENSURE,tenant],text=True,capture_output=True,timeout=900)
  if r.returncode!=0:return send(self,502,{'ok':False,'error':'tenant_ensure_failed','returncode':r.returncode,'duration_ms':int((time.time()-started)*1000)})
  return send(self,200,{'ok':True,'project_slug':slug,'tenant':tenant,'status':'ready','idempotent':True,'duration_ms':int((time.time()-started)*1000)})
if __name__=='__main__':
 if not TOKEN:raise SystemExit('missing token')
 ThreadingHTTPServer((HOST,PORT),H).serve_forever()
