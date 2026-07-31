#!/usr/bin/env python3
import os,sqlite3,json,hmac,time,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
DB=os.environ.get('CLOUDIF_AUDIT_DB','/var/lib/cloudif/audit/audit.db');TOKEN=os.environ.get('CLOUDIF_AUDIT_TOKEN','');HOST=os.environ.get('CLOUDIF_AUDIT_HOST','127.0.0.1');PORT=int(os.environ.get('CLOUDIF_AUDIT_PORT','18201'))
def con():
 c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row;c.execute('pragma busy_timeout=20000');return c
def init():
 os.makedirs(os.path.dirname(DB),exist_ok=True);c=con();c.execute('pragma journal_mode=delete');c.executescript('''create table if not exists events(event_id text primary key,ts text not null,project_id text,project_slug text,actor_type text not null,actor_id text,delegated_user_id text,source text not null,action text not null,result text not null,duration_ms integer not null default 0,trace_id text,client_id text,attrs_json text not null default '{}');create index if not exists idx_events_project_ts on events(project_id,ts desc);create index if not exists idx_events_actor_ts on events(actor_id,ts desc);create index if not exists idx_events_source_action on events(source,action);''');c.commit();c.close()
def auth(h):return bool(TOKEN) and hmac.compare_digest(h.get('Authorization',''),'Bearer '+TOKEN)
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def sendj(self,code,d):
  b=json.dumps(d,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  p=urlparse(self.path)
  if p.path=='/health':
   try:c=con();n=c.execute('select count(*) from events').fetchone()[0];c.close();self.sendj(200,{'ok':True,'events':n})
   except Exception:self.sendj(503,{'ok':False,'error':'db_unavailable'})
   return
  if not auth(self.headers):self.sendj(401,{'ok':False,'error':'unauthorized'});return
  c=con()
  if p.path=='/v1/summary':
   r=dict(c.execute("select count(*) total,sum(case when source='mcp' then 1 else 0 end) mcp_calls,sum(case when actor_type='agent' then 1 else 0 end) agent_events,sum(case when result='error' then 1 else 0 end) errors,count(distinct actor_id) unique_actors,count(distinct project_slug) unique_projects,max(ts) last_event from events").fetchone());c.close();self.sendj(200,{'ok':True,'summary':r});return
  if p.path=='/v1/events':
   q=parse_qs(p.query);limit=max(1,min(int((q.get('limit')or['100'])[0]),500));slug=(q.get('project')or[''])[0]
   rows=[dict(x) for x in c.execute('select * from events where (?="" or project_slug=?) order by ts desc limit ?',(slug,slug,limit))];c.close();self.sendj(200,{'ok':True,'events':rows});return
  c.close();self.sendj(404,{'ok':False,'error':'not_found'})
 def do_POST(self):
  if urlparse(self.path).path!='/v1/events':self.sendj(404,{'ok':False,'error':'not_found'});return
  if not auth(self.headers):self.sendj(401,{'ok':False,'error':'unauthorized'});return
  try:
   n=int(self.headers.get('Content-Length','0'));assert 0<n<=262144;d=json.loads(self.rfile.read(n))
   for k in ('source','action','result'):assert str(d.get(k)or'').strip()
   eid=str(d.get('event_id')or uuid.uuid4().hex);ts=str(d.get('ts')or time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()));attrs=d.get('attrs')or{}
   row=(eid,ts,str(d.get('project_id')or''),str(d.get('project_slug')or''),str(d.get('actor_type')or'service'),str(d.get('actor_id')or''),str(d.get('delegated_user_id')or''),str(d['source']),str(d['action']),str(d['result']),int(d.get('duration_ms') or 0),str(d.get('trace_id')or''),str(d.get('client_id')or''),json.dumps(attrs,ensure_ascii=False,separators=(',',':')))
   c=con();c.execute('insert or ignore into events values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',row);c.commit();c.close();self.sendj(202,{'ok':True,'event_id':eid})
  except Exception as e:self.sendj(400,{'ok':False,'error':'invalid_event'})
init();ThreadingHTTPServer((HOST,PORT),H).serve_forever()
