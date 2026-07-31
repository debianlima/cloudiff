#!/usr/bin/env python3
import os,json,sqlite3,hmac,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
DB=os.environ.get('CLOUDIF_NOTIFY_DB','/var/lib/cloudif/notifications/notifications.db')
TOKEN=os.environ.get('CLOUDIF_NOTIFY_TOKEN','');HOST=os.environ.get('CLOUDIF_NOTIFY_HOST','127.0.0.1');PORT=int(os.environ.get('CLOUDIF_NOTIFY_PORT','18202'))
def connect(readonly=False):
 uri=f'file:{DB}?mode=ro' if readonly else DB
 c=sqlite3.connect(uri,uri=readonly,timeout=20);c.row_factory=sqlite3.Row;c.execute('pragma busy_timeout=20000');return c
def init():
 c=connect();c.execute('pragma journal_mode=delete');c.execute('''create table if not exists preferences(user_id text primary key,channels_json text not null default '["in_app"]',min_severity text not null default 'warning',quiet_start text not null default '',quiet_end text not null default '',timezone text not null default 'America/Sao_Paulo',updated_at text not null)''');c.commit();c.close()
def rows(sql,args=()):
 c=connect(True)
 try:return [dict(r) for r in c.execute(sql,args)]
 finally:c.close()
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def out(self,code,d):
  b=json.dumps(d,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def auth(self):return bool(TOKEN) and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+TOKEN)
 def do_GET(self):
  p=urlparse(self.path)
  if p.path=='/health':
   try:self.out(200,{'ok':True,'total':rows('select count(*) n from notifications')[0]['n']})
   except Exception:self.out(503,{'ok':False,'error':'db_unavailable'})
   return
  if not self.auth():self.out(401,{'ok':False,'error':'unauthorized'});return
  if p.path=='/v1/summary':self.out(200,{'ok':True,'summary':rows("select count(*) total,sum(case when status='open' then 1 else 0 end) open,sum(case when status='open' and severity='critical' then 1 else 0 end) critical,sum(case when status='open' and severity='warning' then 1 else 0 end) warning,max(last_seen) last_seen from notifications")[0]});return
  if p.path=='/v1/notifications':
   status=(parse_qs(p.query).get('status')or['open'])[0];self.out(200,{'ok':True,'notifications':rows('select * from notifications where (?="all" or status=?) order by case severity when "critical" then 0 else 1 end,last_seen desc',(status,status))});return
  if p.path.startswith('/v1/preferences/'):
   uid=p.path.split('/',3)[3];r=rows('select * from preferences where user_id=?',(uid,));self.out(200,{'ok':True,'preference':r[0] if r else {'user_id':uid,'channels_json':'["in_app"]','min_severity':'warning','quiet_start':'','quiet_end':'','timezone':'America/Sao_Paulo'}});return
  self.out(404,{'ok':False,'error':'not_found'})
 def do_POST(self):
  p=urlparse(self.path).path
  if not self.auth():self.out(401,{'ok':False,'error':'unauthorized'});return
  if not p.startswith('/v1/preferences/'):self.out(404,{'ok':False,'error':'not_found'});return
  try:
   n=int(self.headers.get('Content-Length','0'));d=json.loads(self.rfile.read(n) if n else b'{}');uid=p.split('/',3)[3]
   channels=d.get('channels') or ['in_app'];allowed={'in_app','email','web_push'};assert all(x in allowed for x in channels);channels=list(dict.fromkeys(channels)) or ['in_app']
   sev=str(d.get('min_severity') or 'warning');assert sev in {'info','warning','critical'}
   qs=str(d.get('quiet_start') or '');qe=str(d.get('quiet_end') or '');tz=str(d.get('timezone') or 'America/Sao_Paulo')
   c=connect();c.execute('insert into preferences values(?,?,?,?,?,?,?) on conflict(user_id) do update set channels_json=excluded.channels_json,min_severity=excluded.min_severity,quiet_start=excluded.quiet_start,quiet_end=excluded.quiet_end,timezone=excluded.timezone,updated_at=excluded.updated_at',(uid,json.dumps(channels,separators=(',',':')),sev,qs,qe,tz,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())));c.commit();c.close();self.out(200,{'ok':True,'user_id':uid,'channels':channels,'min_severity':sev,'quiet_start':qs,'quiet_end':qe,'timezone':tz})
  except Exception:self.out(400,{'ok':False,'error':'invalid_preference'})
init();ThreadingHTTPServer((HOST,PORT),H).serve_forever()
