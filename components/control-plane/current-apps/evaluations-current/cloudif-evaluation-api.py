#!/usr/bin/env python3
import os,json,sqlite3,hmac,time,uuid,urllib.request,urllib.parse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
DB=os.environ.get('CLOUDIF_EVAL_DB','/var/lib/cloudif/evaluations/evaluations.db');TOKEN=os.environ.get('CLOUDIF_EVAL_TOKEN','');HOST=os.environ.get('CLOUDIF_EVAL_HOST','127.0.0.1');PORT=int(os.environ.get('CLOUDIF_EVAL_PORT','18206'));AU=os.environ.get('CLOUDIF_AUDIT_URL','http://127.0.0.1:18201');AT=os.environ.get('CLOUDIF_AUDIT_TOKEN','')
def c():
 x=sqlite3.connect(DB,timeout=20);x.row_factory=sqlite3.Row;x.execute('pragma busy_timeout=20000');return x
def init():
 os.makedirs(os.path.dirname(DB),exist_ok=True);x=c();x.execute('pragma journal_mode=delete');x.executescript('''create table if not exists rubrics(rubric_id text primary key,name text not null,version integer not null,status text not null,criteria_json text not null,created_by text not null,created_at text not null);create table if not exists evaluations(evaluation_id text primary key,rubric_id text not null,project_slug text not null,student_user text not null,status text not null,score real not null,evidence_json text not null,explanation_json text not null,created_at text not null,reviewed_by text,reviewed_at text,final_score real);create index if not exists idx_eval_student on evaluations(student_user,created_at desc);''');x.commit();x.close()
def auth(h):return bool(TOKEN) and hmac.compare_digest(h.get('Authorization',''),'Bearer '+TOKEN)
def audit_events(slug):
 r=urllib.request.Request(AU+'/v1/events?project='+urllib.parse.quote(slug,safe='')+'&limit=500',headers={'Authorization':'Bearer '+AT})
 with urllib.request.urlopen(r,timeout=10) as x:return json.load(x).get('events') or []
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def out(self,code,d):
  b=json.dumps(d,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  p=urlparse(self.path).path
  if p=='/health':
   try:x=c();n=x.execute('select count(*) from evaluations').fetchone()[0];x.close();self.out(200,{'ok':True,'evaluations':n})
   except Exception:self.out(503,{'ok':False})
   return
  if not auth(self.headers):self.out(401,{'ok':False,'error':'unauthorized'});return
  x=c()
  if p=='/v1/rubrics':rows=[dict(r) for r in x.execute('select * from rubrics order by created_at desc')];x.close();self.out(200,{'ok':True,'rubrics':rows});return
  if p=='/v1/evaluations':rows=[dict(r) for r in x.execute('select * from evaluations order by created_at desc limit 200')];x.close();self.out(200,{'ok':True,'evaluations':rows});return
  x.close();self.out(404,{'ok':False})
 def do_POST(self):
  if not auth(self.headers):self.out(401,{'ok':False,'error':'unauthorized'});return
  try:n=int(self.headers.get('Content-Length','0'));d=json.loads(self.rfile.read(n) if n else b'{}')
  except Exception:self.out(400,{'ok':False,'error':'invalid_json'});return
  p=urlparse(self.path).path;now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
  if p=='/v1/rubrics':
   rid=str(d.get('rubric_id') or 'rub_'+uuid.uuid4().hex[:18]);criteria=d.get('criteria') or {'activity_weight':40,'success_weight':35,'independence_weight':25};x=c();x.execute('insert into rubrics values(?,?,?,?,?,?,?)',(rid,str(d.get('name') or rid),int(d.get('version') or 1),'active',json.dumps(criteria,separators=(',',':')),str(d.get('created_by') or 'system'),now));x.commit();x.close();self.out(201,{'ok':True,'rubric_id':rid});return
  if p=='/v1/evaluations/run':
   rid=str(d.get('rubric_id') or '');slug=str(d.get('project_slug') or '');student=str(d.get('student_user') or '');
   try:
    x=c();r=x.execute('select * from rubrics where rubric_id=? and status="active"',(rid,)).fetchone();assert r and slug and student;criteria=json.loads(r['criteria_json']);events=audit_events(slug)
    total=len(events);success=sum(e.get('result')=='success' for e in events);errors=sum(e.get('result')=='error' for e in events);mcp=sum(e.get('source')=='mcp' for e in events);direct=max(0,total-mcp)
    activity=min(100,total*5);success_rate=(success/total*100) if total else 0;independence=(direct/total*100) if total else 0
    score=(activity*float(criteria.get('activity_weight',40))+success_rate*float(criteria.get('success_weight',35))+independence*float(criteria.get('independence_weight',25)))/100
    eid='eva_'+uuid.uuid4().hex[:18];evidence={'total_events':total,'successful_events':success,'errors':errors,'mcp_events':mcp,'direct_events':direct};explanation={'activity_score':round(activity,2),'success_score':round(success_rate,2),'independence_score':round(independence,2),'note':'Rascunho automático sujeito à revisão docente.'}
    x.execute('insert into evaluations(evaluation_id,rubric_id,project_slug,student_user,status,score,evidence_json,explanation_json,created_at) values(?,?,?,?,?,?,?,?,?)',(eid,rid,slug,student,'draft',round(score,2),json.dumps(evidence,separators=(',',':')),json.dumps(explanation,ensure_ascii=False,separators=(',',':')),now));x.commit();x.close();self.out(201,{'ok':True,'evaluation_id':eid,'status':'draft','score':round(score,2),'evidence':evidence,'explanation':explanation});return
   except Exception:self.out(400,{'ok':False,'error':'evaluation_failed'});return
  if p.endswith('/review'):
   eid=p.split('/')[-2];reviewer=str(d.get('reviewed_by') or '');final=float(d.get('final_score'));assert reviewer and 0<=final<=100;x=c();cur=x.execute('update evaluations set status="reviewed",reviewed_by=?,reviewed_at=?,final_score=? where evaluation_id=? and status="draft"',(reviewer,now,final,eid));x.commit();x.close();self.out(200 if cur.rowcount else 409,{'ok':bool(cur.rowcount),'evaluation_id':eid,'status':'reviewed' if cur.rowcount else 'not_reviewable','final_score':final if cur.rowcount else None});return
  self.out(404,{'ok':False})
init();ThreadingHTTPServer((HOST,PORT),H).serve_forever()
