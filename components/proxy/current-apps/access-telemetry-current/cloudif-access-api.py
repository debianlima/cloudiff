#!/usr/bin/env python3
import os,sqlite3,json,hmac,ipaddress
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
DB=os.environ.get('CLOUDIF_ACCESS_DB','/var/lib/cloudif/access-telemetry/access.db');TOKEN=os.environ['CLOUDIF_ACCESS_TOKEN'];HOST=os.environ.get('CLOUDIF_ACCESS_HOST','10.62.91.3');PORT=int(os.environ.get('CLOUDIF_ACCESS_PORT','18210'));ALLOWED={x.strip() for x in os.environ.get('CLOUDIF_ACCESS_ALLOWED','127.0.0.1,10.62.92.7').split(',') if x.strip()}
def q(sql,args=()):
 c=sqlite3.connect(f'file:{DB}?mode=ro',uri=True,timeout=10);c.row_factory=sqlite3.Row
 try:return [dict(r) for r in c.execute(sql,args)]
 finally:c.close()
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def out(self,code,d):
  b=json.dumps(d,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def allowed(self):return self.client_address[0] in ALLOWED
 def auth(self):return self.allowed() and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+TOKEN)
 def do_GET(self):
  p=urlparse(self.path)
  if p.path=='/health':
   if not self.allowed():self.out(403,{'ok':False,'error':'source_denied'});return
   try:m={r['key']:r['value'] for r in q('select key,value from collector_meta')};self.out(200,{'ok':True,'service':'cloudif-access-telemetry','last_run':m.get('last_run'),'last_parsed':int(m.get('last_parsed','0'))})
   except Exception:self.out(503,{'ok':False,'error':'db_unavailable'})
   return
  if not self.auth():self.out(401 if self.allowed() else 403,{'ok':False,'error':'unauthorized' if self.allowed() else 'source_denied'});return
  days=max(1,min(int((parse_qs(p.query).get('days') or ['7'])[0]),90))
  if p.path=='/v1/summary':
   r=q("select coalesce(sum(requests),0) requests,count(distinct visitor_hash) unique_visitors,coalesce(sum(bytes),0) bytes,count(distinct host) hosts,sum(case when source='public' then requests else 0 end) public_requests,sum(case when source='internal' then requests else 0 end) internal_requests from access_daily where day>=date('now',?)",(f'-{days-1} days',))[0];self.out(200,{'ok':True,'days':days,'summary':r});return
  if p.path=='/v1/hosts':
   rows=q("select host,sum(requests) requests,count(distinct visitor_hash) unique_visitors,sum(bytes) bytes,sum(case when status_class like '4%' or status_class like '5%' then requests else 0 end) errors,max(last_seen) last_seen from access_daily where day>=date('now',?) group by host order by requests desc",(f'-{days-1} days',));self.out(200,{'ok':True,'days':days,'hosts':rows});return
  if p.path=='/v1/routes':
   host=(parse_qs(p.query).get('host') or [''])[0];rows=q("select host,route,sum(requests) requests,count(distinct visitor_hash) unique_visitors,sum(bytes) bytes,max(last_seen) last_seen from access_daily where day>=date('now',?) and (?='' or host=?) group by host,route order by requests desc limit 200",(f'-{days-1} days',host,host));self.out(200,{'ok':True,'days':days,'routes':rows});return
  self.out(404,{'ok':False,'error':'not_found'})
ThreadingHTTPServer((HOST,PORT),H).serve_forever()
