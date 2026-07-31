#!/usr/bin/env python3
import datetime as dt,json,os,sqlite3,tempfile,time,urllib.request,urllib.error
from pathlib import Path
APPROVAL_URL=os.environ.get('CLOUDIF_APPROVAL_URL','http://127.0.0.1:18204').rstrip('/')
TOKEN=os.environ.get('CLOUDIF_APPROVAL_TOKEN','')
APPROVAL_DB=Path(os.environ.get('CLOUDIF_APPROVAL_DB','/var/lib/cloudif/approvals/approvals.db'))
IDEM_DB=Path(os.environ.get('CLOUDIF_IDEMPOTENCY_DB','/var/lib/cloudif/portal/deployment-idempotency.db'))
OUT=Path(os.environ.get('CLOUDIF_TRANSACTION_RECONCILE_REPORT','/var/lib/cloudif/health/transaction-reconciler.json'))
STALE_SECONDS=int(os.environ.get('CLOUDIF_TRANSACTION_STALE_SECONDS','900'))
def api_get():
 q=urllib.request.Request(APPROVAL_URL+'/v1/approvals?status=all',headers={'Authorization':'Bearer '+TOKEN,'Accept':'application/json'})
 with urllib.request.urlopen(q,timeout=20) as r:return json.load(r)
def ro(path):
 c=sqlite3.connect(f'file:{path}?mode=ro&immutable=1',uri=True,timeout=8);c.row_factory=sqlite3.Row;return c
def iso_age(v):
 try:return max(0,time.time()-dt.datetime.fromisoformat(v).timestamp())
 except Exception:return None
def main():
 before=ro(APPROVAL_DB);pre_reserved=before.execute("select count(*) n from approvals where status='reserved'").fetchone()['n'];before.close()
 api=api_get();assert api.get('ok') is True
 a=ro(APPROVAL_DB)
 counts={r['status']:r['n'] for r in a.execute('select status,count(*) n from approvals group by status')}
 malformed=a.execute("select count(*) n from approvals where (status='reserved' and (reservation_id is null or reserved_by is null or reserved_at is null or reservation_expires_at is null or reservation_expires_at<=reserved_at or reservation_expires_at>expires_at)) or (status='consumed' and reservation_id is not null and (finalized_at is null or finalize_result not in ('success','completed'))) or (status in ('pending','approved','rejected','expired') and reservation_id is not null)").fetchone()['n']
 reserved=[dict(r) for r in a.execute("select approval_id,project_slug,action,reserved_at,reservation_expires_at,expires_at from approvals where status='reserved' order by reserved_at")];a.close()
 e=ro(IDEM_DB);running=[dict(r) for r in e.execute("select execution_id,operation,effect_started,created_at,updated_at from executions where state='running' order by created_at")];e.close()
 stale=[]
 for x in running:
  age=iso_age(x.get('updated_at') or x.get('created_at'))
  if age is not None and age>STALE_SECONDS:stale.append({'execution_id':x['execution_id'],'operation':x['operation'],'effect_started':bool(x['effect_started']),'age_seconds':int(age)})
 alerts=[]
 if malformed:alerts.append({'code':'approval_invariant_violation','severity':'critical','count':malformed})
 if stale:alerts.append({'code':'execution_stale','severity':'warning','count':len(stale)})
 report={'ok':malformed==0,'generated_at':int(time.time()),'mode':'observe-and-normalize-expiry-only','automatic_retry':False,'automatic_approval':False,'approval_counts':counts,'reserved_before_api_normalization':pre_reserved,'reserved_after':len(reserved),'running_executions':len(running),'stale_executions':stale,'malformed_approvals':malformed,'alerts':alerts}
 OUT.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.transaction-reconciler-',dir=OUT.parent);os.close(fd)
 Path(tmp).write_text(json.dumps(report,ensure_ascii=False,separators=(',',':'))+'\n');os.chmod(tmp,0o600);os.replace(tmp,OUT)
 print(json.dumps(report,ensure_ascii=False,separators=(',',':')))
 return 0 if report['ok'] else 2
if __name__=='__main__':raise SystemExit(main())
