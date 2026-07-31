#!/usr/bin/env python3
import json,os,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
HOST='10.62.91.2';PORT=18218;SLUG='atalhos-cloudif-iff1860746'
STATE='/var/lib/cloudif/production-sealed-target/state.json'
def state():
 try:return json.load(open(STATE))
 except:return {'project_slug':SLUG,'sealed':True,'activation_allowed':False,'production_effects_enabled':False,'active_release_id':None,'artifact_alias_attached':False,'published_ports':[],'created_at':int(time.time())}
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def out(self,n,x):
  b=json.dumps(x,separators=(',',':')).encode();self.send_response(n);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  s=state()
  if self.path=='/health':return self.out(200,{'ok':True,'service':'production-sealed-target','project_slug':SLUG,'sealed':True,'activation_allowed':False,'secrets_exposed':False})
  if self.path=='/v1/status':return self.out(200,{'ok':True,'state':s,'secrets_exposed':False})
  return self.out(503,{'ok':False,'error':'production_target_sealed','project_slug':SLUG,'sealed':True,'activation_allowed':False,'retry_after_seconds':0,'secrets_exposed':False})
 def do_POST(self):return self.out(405,{'ok':False,'error':'effects_not_supported','sealed':True,'activation_allowed':False,'secrets_exposed':False})
if __name__=='__main__':ThreadingHTTPServer((HOST,PORT),H).serve_forever()
