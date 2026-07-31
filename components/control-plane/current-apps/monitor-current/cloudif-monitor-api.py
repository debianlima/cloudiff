#!/usr/bin/env python3
import os,sqlite3,json,hmac,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
DB=os.environ.get('CLOUDIF_MONITOR_DB','/var/lib/cloudif/monitoring/monitor.db')
APPROVAL_DB=os.environ.get('CLOUDIF_APPROVAL_READ_DB','/var/lib/cloudif/approvals/approvals.db')
IDEM_DB=os.environ.get('CLOUDIF_IDEMPOTENCY_READ_DB','/var/lib/cloudif/portal/deployment-idempotency.db')
PORTAL_DB=os.environ.get('CLOUDIF_PORTAL_READ_DB','/var/lib/cloudif/portal/cloudif-portal.db')
TOKEN=os.environ.get('CLOUDIF_MONITOR_TOKEN','');HOST=os.environ.get('CLOUDIF_MONITOR_HOST','127.0.0.1');PORT=int(os.environ.get('CLOUDIF_MONITOR_PORT','18199'))
def rows(path,sql,args=()):
 uri=f'file:{path}?mode=ro'+('&immutable=1' if path!=DB else '')
 c=sqlite3.connect(uri,uri=True,timeout=8);c.row_factory=sqlite3.Row
 try:return [dict(r) for r in c.execute(sql,args)]
 finally:c.close()
def q(sql,args=()):return rows(DB,sql,args)
def transactions(project=''):
 now=int(time.time());where=' where project_slug=?' if project else '';args=(project,) if project else ()
 approval_counts=rows(APPROVAL_DB,'select status,count(*) count from approvals'+where+' group by status order by status',args)
 action_counts=rows(APPROVAL_DB,'select action,status,count(*) count from approvals'+where+' group by action,status order by action,status',args)
 active=rows(APPROVAL_DB,"select approval_id,project_slug,action,requested_by,reserved_by,reserved_at,reservation_expires_at,expires_at from approvals where status='reserved'"+(' and project_slug=?' if project else '')+' order by reserved_at desc limit 50',args)
 recent=rows(APPROVAL_DB,"select approval_id,project_slug,action,requested_by,approved_by,rejected_by,status,created_at,approved_at,rejected_at,consumed_at,finalized_at,finalize_result from approvals"+where+' order by created_at desc limit 100',args)
 malformed=rows(APPROVAL_DB,"select count(*) count from approvals where (status='reserved' and (reservation_id is null or reserved_by is null or reservation_expires_at is null or reservation_expires_at<=reserved_at or reservation_expires_at>expires_at)) or (status='consumed' and reservation_id is not null and (finalized_at is null or finalize_result not in ('success','completed'))) or (status in ('pending','approved','rejected','expired') and reservation_id is not null)")[0]['count']
 overdue=sum(1 for x in active if int(x.get('reservation_expires_at') or 0)<=now)
 if project:
  exec_counts=[];executions=[];running_stale=0;effect_errors=0
 else:
  exec_counts=rows(IDEM_DB,'select operation,state,effect_started,count(*) count from executions group by operation,state,effect_started order by operation,state,effect_started')
  executions=rows(IDEM_DB,'select execution_id,operation,state,http_code,effect_started,created_at,updated_at from executions order by created_at desc limit 100')
  running_stale=sum(1 for x in executions if x['state']=='running' and x['created_at'] and (time.time()-__import__('datetime').datetime.fromisoformat(x['created_at']).timestamp())>900)
  effect_errors=sum(1 for x in executions if x['state']=='finished' and x.get('effect_started') and int(x.get('http_code') or 0)>=400)
 alerts=[]
 if malformed:alerts.append({'code':'approval_invariant_violation','severity':'critical','count':malformed})
 if overdue:alerts.append({'code':'reservation_overdue','severity':'warning','count':overdue})
 if running_stale:alerts.append({'code':'execution_stale','severity':'warning','count':running_stale})
 if effect_errors:alerts.append({'code':'effect_started_error','severity':'warning','count':effect_errors})
 return {'ok':True,'generated_at':now,'project_slug':project or None,'summary':{'approval_counts':approval_counts,'execution_counts':exec_counts,'active_reservations':len(active),'recent_approvals':len(recent),'recent_executions':len(executions),'alerts':len(alerts)},'active_reservations':active,'recent_approvals':recent,'recent_executions':executions,'alerts':alerts,'sanitized':True,'secrets_exposed':False}
def promotions(project=''):
 if project!='sistema-de-biblioteca-teste':return {'ok':False,'error':'project_not_allowed'}
 jobs=rows(PORTAL_DB,"select id,created_at,scheduled_at,started_at,finished_at,version,commit_sha,status,dry_run,migration_count,migration_applied,release_id,release_url,message from release_jobs where project=? and dry_run=0 order by id desc limit 50",(project,))
 counts={};manual=0
 for j in jobs:
  counts[j['status']]=counts.get(j['status'],0)+1
  msg=str(j.get('message') or '')
  if msg.startswith('Manual rollback to job '):
   manual+=1;j['operation']='manual_rollback'
   try:j['target_job_id']=int(msg.split('Manual rollback to job ',1)[1].split(' ',1)[0])
   except Exception:j['target_job_id']=None
  else:j['operation']='promotion'
 return {'ok':True,'project_slug':project,'summary':{'total':len(jobs),'published':counts.get('published',0),'rolled_back':counts.get('rolled_back',0),'failed':counts.get('failed',0),'manual_rollbacks':manual},'jobs':jobs,'sanitized':True,'secrets_exposed':False,'read_only':True,'automatic_retry':False,'automatic_rollback_triggered':False}
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def sendj(self,code,d):
  b=json.dumps(d,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def auth(self):return bool(TOKEN) and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+TOKEN)
 def do_GET(self):
  u=urlparse(self.path);p=u.path
  if p=='/health':
   try:self.sendj(200,{'ok':True,'service':'cloudif-monitor-api','samples':q('select count(*) n from samples')[0]['n']})
   except Exception:self.sendj(503,{'ok':False,'error':'db_unavailable'})
   return
  if not self.auth():self.sendj(401,{'ok':False,'error':'unauthorized'});return
  try:
   if p=='/v1/summary':
    r=q('select count(*) total,sum(running) running,sum(healthy) healthy,round(avg(cpu_pct),3) avg_cpu_pct,round(avg(mem_pct),3) avg_mem_pct,max(ts) collected_at from latest')[0];self.sendj(200,{'ok':True,'summary':r});return
   if p=='/v1/projects':self.sendj(200,{'ok':True,'projects':q('select * from latest order by slug')});return
   if p.startswith('/v1/projects/'):
    slug=p.split('/',3)[3];r=q('select * from latest where slug=?',(slug,));self.sendj(200,{'ok':True,'project':r[0]} if r else {'ok':False,'error':'not_found'});return
   if p=='/v1/transactions':
    project=str((parse_qs(u.query).get('project') or [''])[0]).strip();
    if project and (len(project)>63 or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in project)):self.sendj(400,{'ok':False,'error':'invalid_project'});return
    self.sendj(200,transactions(project));return
   if p=='/v1/promotions':
    project=str((parse_qs(u.query).get('project') or [''])[0]).strip()
    if project!='sistema-de-biblioteca-teste':self.sendj(403,{'ok':False,'error':'project_not_allowed'});return
    self.sendj(200,promotions(project));return
   self.sendj(404,{'ok':False,'error':'not_found'})
  except Exception as e:self.sendj(503,{'ok':False,'error':'data_unavailable','error_type':type(e).__name__})
ThreadingHTTPServer((HOST,PORT),H).serve_forever()
