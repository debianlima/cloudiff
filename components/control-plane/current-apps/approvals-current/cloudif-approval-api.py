#!/usr/bin/env python3
import os,sqlite3,json,hmac,time,uuid
import cloudif_approval_policy as approval_policy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
DB=os.environ.get('CLOUDIF_APPROVAL_DB','/var/lib/cloudif/approvals/approvals.db');TOKEN=os.environ.get('CLOUDIF_APPROVAL_TOKEN','');HOST=os.environ.get('CLOUDIF_APPROVAL_HOST','127.0.0.1');PORT=int(os.environ.get('CLOUDIF_APPROVAL_PORT','18204'))
DUAL_APPROVAL_ACTIONS={'deployment.production.activate','project.environment.secret.read'}
def c():
 x=sqlite3.connect(DB,timeout=20);x.row_factory=sqlite3.Row;x.execute('pragma busy_timeout=20000');return x
def init():
 os.makedirs(os.path.dirname(DB),exist_ok=True);x=c();x.execute('pragma journal_mode=delete');x.executescript('''create table if not exists approvals(approval_id text primary key,project_slug text not null,action text not null,requested_by text not null,approved_by text,status text not null,reason text,created_at integer not null,expires_at integer not null,approved_at integer,consumed_at integer,trace_id text,metadata_json text not null default '{}');create index if not exists idx_approvals_status on approvals(status,expires_at);create unique index if not exists idx_approval_active on approvals(project_slug,action,requested_by) where status in ('pending','approved');''')
 cols={r[1] for r in x.execute('pragma table_info(approvals)')}
 for name,kind in [('rejected_by','text'),('rejected_at','integer'),('rejection_reason','text'),('cancelled_by','text'),('cancelled_at','integer'),('cancellation_reason','text'),('reservation_id','text'),('reserved_by','text'),('reserved_at','integer'),('reservation_expires_at','integer'),('finalized_at','integer'),('finalize_result','text'),('requester_role','text'),('approver_role','text'),('authorization_mode','text'),('second_approved_by','text'),('second_approved_at','integer'),('second_approver_role','text'),('two_approvers_required','integer'),('approval_policy_id','text')]:
  if name not in cols:x.execute(f'alter table approvals add column {name} {kind}')
 approval_policy.init_tables(x)
 x.execute('drop index if exists idx_approval_active')
 x.execute("create unique index if not exists idx_approval_active on approvals(project_slug,action,requested_by) where status in ('pending','pending_second')")
 x.execute('create unique index if not exists idx_approval_reservation on approvals(reservation_id) where reservation_id is not null')
 x.commit();x.close()
def auth(h):return bool(TOKEN) and hmac.compare_digest(h.get('Authorization',''),'Bearer '+TOKEN)
def expire_rows(x,now):
 x.execute("update approvals set status='approved',reservation_id=NULL,reserved_by=NULL,reserved_at=NULL,reservation_expires_at=NULL where status='reserved' and reservation_expires_at<=? and expires_at>?",(now,now))
 x.execute("update approvals set status='expired',reservation_id=NULL,reserved_by=NULL,reserved_at=NULL,reservation_expires_at=NULL where status in ('pending','pending_second','approved','reserved') and expires_at<=?",(now,))

class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def out(self,code,d):
  b=json.dumps(d,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  p=urlparse(self.path)
  if p.path=='/health':
   try:x=c();n=x.execute('select count(*) from approvals').fetchone()[0];x.close();self.out(200,{'ok':True,'approvals':n})
   except Exception:self.out(503,{'ok':False})
   return
  if not auth(self.headers):self.out(401,{'ok':False,'error':'unauthorized'});return
  if p.path=='/v1/approvals':
   q=parse_qs(p.query);status=(q.get('status')or['all'])[0];x=c();expire_rows(x,int(time.time()));x.commit();rows=[dict(r) for r in x.execute('select * from approvals where (?="all" or status=?) order by created_at desc',(status,status))];x.close();self.out(200,{'ok':True,'approvals':rows});return
  if p.path=='/v1/approval-policies':
   q=parse_qs(p.query);status=(q.get('status')or['active'])[0];x=c();rows=approval_policy.list_policies(x,status if status in {'active','all'} else 'active');x.close();self.out(200,{'ok':True,'policies':rows,'persistent':True});return
  self.out(404,{'ok':False})
 def do_POST(self):
  if not auth(self.headers):self.out(401,{'ok':False,'error':'unauthorized'});return
  try:n=int(self.headers.get('Content-Length','0'));d=json.loads(self.rfile.read(n) if n else b'{}')
  except Exception:self.out(400,{'ok':False,'error':'invalid_json'});return
  p=urlparse(self.path).path;now=int(time.time())
  try:
   x=c();x.execute('begin immediate');expire_rows(x,now)
   if p=='/v1/approvals':
    slug=str(d.get('project_slug')or'').strip();action=str(d.get('action')or'').strip();user=str(d.get('requested_by')or'').strip();ttl=max(60,min(int(d.get('ttl_seconds') or 900),86400));assert slug and action and user
    requester_role=str(d.get('requester_role') or 'agent').strip().lower();self_authorize=bool(d.get('self_authorize'));production=action.startswith('deployment.production');dual=action in DUAL_APPROVAL_ACTIONS
    privileged=requester_role in {'admin','professor'};policy=approval_policy.active_policy(x,slug,action,user)
    policy_applied=bool(policy)
    status='approved' if policy_applied or (production and self_authorize and privileged and not dual) else 'pending'
    mode='persistent_policy' if policy_applied else ('dual_admin_or_professor' if dual else ('single_privileged_requester' if status=='approved' else ('single_admin_or_professor' if production else 'standard_single_decider')))
    aid='apr_'+uuid.uuid4().hex[:20]
    approved_by=(str(policy.get('created_by')) if policy_applied else user) if status=='approved' else None
    approved_at=now if status=='approved' else None
    approver_role=(str(policy.get('creator_role')) if policy_applied else requester_role) if status=='approved' else None
    policy_id=str(policy.get('policy_id')) if policy_applied else None
    x.execute('insert into approvals(approval_id,project_slug,action,requested_by,approved_by,status,reason,created_at,expires_at,approved_at,trace_id,metadata_json,requester_role,approver_role,authorization_mode,two_approvers_required,approval_policy_id) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,slug,action,user,approved_by,status,str(d.get('reason')or''),now,now+ttl,approved_at,str(d.get('trace_id')or''),json.dumps(d.get('metadata')or{},separators=(',',':')),requester_role,approver_role,mode,1 if dual else 0,policy_id));x.commit();x.close();self.out(201,{'ok':True,'approval_id':aid,'status':status,'expires_at':now+ttl,'authorization_mode':mode,'two_approvers_required':dual,'policy_applied':policy_applied,'approval_policy_id':policy_id});return
   if p.endswith('/approve'):
    aid=p.split('/')[-2];approver=str(d.get('approved_by')or'').strip();approver_role=str(d.get('approver_role') or '').strip().lower();always_allow=bool(d.get('always_allow'));assert approver
    r=x.execute('select * from approvals where approval_id=?',(aid,)).fetchone();assert r
    if always_allow:approval_policy.request_persistent(x,aid,approver,approver_role or 'human',now)
    if str(r['action']).startswith('deployment.production') and approver_role not in {'admin','professor'}:raise ValueError('production_approver_role_required')
    if str(r['action']) in DUAL_APPROVAL_ACTIONS and not str(r['action']).startswith('deployment.production') and approver_role not in {'admin','professor'}:raise ValueError('critical_approver_role_required')
    if r['expires_at']<=now:raise ValueError('expired')
    if int(r['two_approvers_required'] or 0)==1:
     if approver==r['requested_by']:raise ValueError('requester_cannot_approve_activation')
     if r['status']=='pending':
      x.execute("update approvals set status='pending_second',approved_by=?,approved_at=?,approver_role=? where approval_id=? and status='pending'",(approver,now,approver_role,aid));policy_requested=bool(approval_policy.pending_request(x,aid));x.commit();x.close();self.out(200,{'ok':True,'approval_id':aid,'status':'pending_second','first_approved_by':approver,'two_approvers_required':True,'persistent_policy_requested':policy_requested});return
     if r['status']=='pending_second':
      if approver==r['approved_by']:raise ValueError('distinct_second_approver_required')
      x.execute("update approvals set status='approved',second_approved_by=?,second_approved_at=?,second_approver_role=? where approval_id=? and status='pending_second'",(approver,now,approver_role,aid));approved=x.execute('select * from approvals where approval_id=?',(aid,)).fetchone();policy=approval_policy.activate_from_approval(x,approved,now);x.commit();x.close();self.out(200,{'ok':True,'approval_id':aid,'status':'approved','two_approvers_required':True,'persistent_policy_created':bool(policy),'approval_policy_id':policy.get('policy_id') if policy else None});return
     raise ValueError('not_pending_or_expired')
    if r['status']!='pending':raise ValueError('not_pending_or_expired')
    x.execute("update approvals set status='approved',approved_by=?,approved_at=?,approver_role=?,authorization_mode=case when action like 'deployment.production%' then 'single_admin_or_professor' else coalesce(authorization_mode,'standard_single_decider') end where approval_id=?",(approver,now,approver_role,aid));approved=x.execute('select * from approvals where approval_id=?',(aid,)).fetchone();policy=approval_policy.activate_from_approval(x,approved,now);x.commit();x.close();self.out(200,{'ok':True,'approval_id':aid,'status':'approved','persistent_policy_created':bool(policy),'approval_policy_id':policy.get('policy_id') if policy else None});return
   if p.endswith('/reserve'):
    aid=p.split('/')[-2];reservation_id=str(d.get('reservation_id')or'').strip();reserved_by=str(d.get('reserved_by')or'').strip();ttl=int(d.get('ttl_seconds') or 300)
    assert reservation_id and reserved_by and 30<=ttl<=900
    r=x.execute('select * from approvals where approval_id=?',(aid,)).fetchone();assert r
    if r['status']=='reserved' and r['reservation_id']==reservation_id:
     x.commit();x.close();self.out(200,{'ok':True,'approval_id':aid,'status':'reserved','reservation_id':reservation_id,'idempotent':True});return
    if r['status']!='approved':raise ValueError('not_approved')
    until=min(now+ttl,int(r['expires_at']))
    if until<=now:raise ValueError('expired')
    x.execute("update approvals set status='reserved',reservation_id=?,reserved_by=?,reserved_at=?,reservation_expires_at=? where approval_id=? and status='approved'",(reservation_id,reserved_by,now,until,aid));assert x.total_changes==1;x.commit();x.close();self.out(200,{'ok':True,'approval_id':aid,'status':'reserved','reservation_id':reservation_id,'reservation_expires_at':until,'idempotent':False});return
   if p.endswith('/release'):
    aid=p.split('/')[-2];reservation_id=str(d.get('reservation_id')or'').strip();assert reservation_id
    r=x.execute('select * from approvals where approval_id=?',(aid,)).fetchone();assert r
    if r['status']=='approved' and not r['reservation_id']:
     x.commit();x.close();self.out(200,{'ok':True,'approval_id':aid,'status':'approved','released':True,'idempotent':True});return
    if r['status']!='reserved' or r['reservation_id']!=reservation_id:raise ValueError('reservation_mismatch')
    x.execute("update approvals set status='approved',reservation_id=NULL,reserved_by=NULL,reserved_at=NULL,reservation_expires_at=NULL where approval_id=? and status='reserved' and reservation_id=?",(aid,reservation_id));assert x.total_changes==1;x.commit();x.close();self.out(200,{'ok':True,'approval_id':aid,'status':'approved','released':True,'idempotent':False});return
   if p.endswith('/finalize'):
    aid=p.split('/')[-2];reservation_id=str(d.get('reservation_id')or'').strip();result=str(d.get('result')or'success').strip();assert reservation_id and result in ('success','completed')
    r=x.execute('select * from approvals where approval_id=?',(aid,)).fetchone();assert r
    if r['status']=='consumed' and r['reservation_id']==reservation_id:
     x.commit();x.close();self.out(200,{'ok':True,'approval_id':aid,'status':'consumed','idempotent':True});return
    if r['status']!='reserved' or r['reservation_id']!=reservation_id:raise ValueError('reservation_mismatch')
    x.execute("update approvals set status='consumed',consumed_at=?,finalized_at=?,finalize_result=? where approval_id=? and status='reserved' and reservation_id=?",(now,now,result,aid,reservation_id));assert x.total_changes==1;x.commit();x.close();self.out(200,{'ok':True,'approval_id':aid,'status':'consumed','idempotent':False});return
   if p.endswith('/cancel'):
    aid=p.split('/')[-2];requester=str(d.get('requested_by')or'').strip();reason=str(d.get('cancellation_reason')or'').strip();assert requester and 4<=len(reason)<=500
    r=x.execute('select * from approvals where approval_id=?',(aid,)).fetchone();assert r
    if r['requested_by']!=requester:raise ValueError('approval_requester_mismatch')
    if r['status']=='cancelled':
     x.commit();x.close();self.out(200,{'ok':True,'approval_id':aid,'status':'cancelled','cancelled':True,'idempotent':True,'cancelled_at':r['cancelled_at']});return
    if r['status'] not in ('pending','pending_second'):raise ValueError('approval_not_cancellable')
    x.execute("update approvals set status='cancelled',cancelled_by=?,cancelled_at=?,cancellation_reason=? where approval_id=? and status in ('pending','pending_second')",(requester,now,reason,aid));assert x.total_changes==1
    x.execute('delete from approval_policy_requests where approval_id=?',(aid,));x.commit();x.close();self.out(200,{'ok':True,'approval_id':aid,'status':'cancelled','cancelled':True,'idempotent':False,'cancelled_at':now});return
   if p.endswith('/reject'):
    aid=p.split('/')[-2];rejector=str(d.get('rejected_by')or'').strip();reason=str(d.get('rejection_reason')or'').strip();assert rejector and 4<=len(reason)<=500
    r=x.execute('select * from approvals where approval_id=?',(aid,)).fetchone();assert r
    if r['status']!='pending':raise ValueError('not_pending')
    x.execute("update approvals set status='rejected',rejected_by=?,rejected_at=?,rejection_reason=? where approval_id=? and status='pending'",(rejector,now,reason,aid));assert x.total_changes==1;x.commit();x.close();self.out(200,{'ok':True,'approval_id':aid,'status':'rejected'});return
   if p.endswith('/consume'):
    aid=p.split('/')[-2];r=x.execute('select * from approvals where approval_id=?',(aid,)).fetchone();assert r
    if r['status']!='approved' or r['expires_at']<=now:raise ValueError('not_approved_or_expired')
    x.execute("update approvals set status='consumed',consumed_at=? where approval_id=? and status='approved'",(now,aid));assert x.total_changes==1;x.commit();x.close();self.out(200,{'ok':True,'approval_id':aid,'status':'consumed'});return
   if p.startswith('/v1/approval-policies/') and p.endswith('/revoke'):
    policy_id=p.split('/')[-2];revoked_by=str(d.get('revoked_by') or '').strip();reason=str(d.get('reason') or '').strip();assert revoked_by
    result=approval_policy.revoke(x,policy_id,revoked_by,reason,now);x.commit();x.close();self.out(200,result);return
   x.rollback();x.close();self.out(404,{'ok':False});return
  except sqlite3.IntegrityError:
   try:x.rollback();x.close()
   except Exception:pass
   self.out(409,{'ok':False,'error':'active_approval_exists'})
  except Exception as e:
   try:x.rollback();x.close()
   except Exception:pass
   self.out(409,{'ok':False,'error':str(e)[:120]})
init()
if __name__=='__main__':
 ThreadingHTTPServer((HOST,PORT),H).serve_forever()
