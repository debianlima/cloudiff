#!/usr/bin/env python3
import sqlite3,time,json,os,pathlib,shutil
NOW=int(time.time()); result={'ok':True,'deleted':{},'errors':[]}

def clean_db(path, statements):
    try:
        c=sqlite3.connect(path,timeout=30); c.execute('pragma busy_timeout=30000'); c.execute('begin immediate')
        counts={}
        for name,sql,args in statements:
            cur=c.execute(sql,args); counts[name]=cur.rowcount if cur.rowcount!=-1 else 0
        c.commit(); assert c.execute('pragma integrity_check').fetchone()[0]=='ok'; c.execute('vacuum'); c.close(); result['deleted'][path]=counts
    except Exception as e:
        result['ok']=False; result['errors'].append({'path':path,'error':type(e).__name__})

clean_db('/var/lib/cloudif/monitoring/monitor.db',[
 ('samples_older_30d','delete from samples where ts < datetime("now","-30 days")',()),
])
clean_db('/var/lib/cloudif/audit/audit.db',[
 ('events_older_180d','delete from events where ts < datetime("now","-180 days")',()),
])
clean_db('/var/lib/cloudif/notifications/notifications.db',[
 ('resolved_older_30d','delete from notifications where status="resolved" and resolved_at < datetime("now","-30 days")',()),
])
# Remove only known temporary custom clients, preserving every identity referenced by configuration.
def protected_clients():
    out=set()
    for f in pathlib.Path('/etc/cloudif').glob('*.env'):
        try:
            for line in f.read_text().splitlines():
                if '=' not in line:continue
                k,v=line.split('=',1)
                if 'CLIENT' in k and v.strip():out.add(v.strip())
        except Exception:pass
    return out

def cleanup_temp_clients():
    path='/var/lib/cloudif/agents/agents.db';protected=protected_clients();prefixes=('validation-','quota-','rate-','mcp-rate-test-','lifecycle-','workspace-read-','workspace-probe-','prepare-read-','prepare-client-','validate-read-','validate-client-','static-read-','static-client-','preview-read-','preview-client-','edit-read-','edit-client-','edit-preview-','proposal-client-','proposal60b-','plan-client-','plan-read-','read-client-','read-other-','read-deny-','lifecycle-deny-','proposal-action-','merge-client-','merge-deny-','deploy-validate-','deploy-deny-','promote-test-','promote-test-deny-','validate-txn-','promote-tx-','role-test-','status-testop-','status-admin-')
    c=sqlite3.connect(path,timeout=30);c.row_factory=sqlite3.Row;c.execute('pragma busy_timeout=30000');c.execute('begin immediate')
    rows=c.execute("select client_id,role_profile,created_at,last_used_at from clients where role_profile='custom'").fetchall();removed=[];cut_created=NOW-6*3600;cut_used=NOW-3*3600
    def epoch(v):
        if not v:return 0
        try:return int(time.mktime(time.strptime(v,'%Y-%m-%dT%H:%M:%SZ')))
        except Exception:return NOW
    for r in rows:
        cid=r['client_id']
        if cid in protected or cid.startswith('project-') or not cid.startswith(prefixes):continue
        if epoch(r['created_at'])>cut_created:continue
        if r['last_used_at'] and epoch(r['last_used_at'])>cut_used:continue
        c.execute('delete from usage where client_id=?',(cid,));c.execute('delete from clients where client_id=?',(cid,));removed.append(cid)
    c.commit();assert c.execute('pragma integrity_check').fetchone()[0]=='ok';c.close();result['deleted']['temporary_clients']={'count':len(removed),'client_ids':removed,'protected_count':len(protected)}

cleanup_temp_clients()

clean_db('/var/lib/cloudif/agents/agents.db',[
 ('usage_older_35d','delete from usage where substr(window_key,1,2)="d:" and substr(window_key,3) < strftime("%Y%m%d","now","-35 days")',()),
 ('minute_usage_older_2d','delete from usage where substr(window_key,1,2)="m:" and substr(window_key,3) < strftime("%Y%m%d%H%M","now","-2 days")',()),
])
clean_db('/var/lib/cloudif/approvals/approvals.db',[
 ('mark_expired','update approvals set status="expired" where status in ("pending","approved") and expires_at < ?', (NOW,)),
 ('expired_older_90d','delete from approvals where status="expired" and expires_at < ?', (NOW-90*86400,)),
 ('consumed_older_180d','delete from approvals where status="consumed" and consumed_at < ?', (NOW-180*86400,)),
])
clean_db('/var/lib/cloudif/evaluations/evaluations.db',[
 ('drafts_older_180d','delete from evaluations where status="draft" and created_at < datetime("now","-180 days")',()),
])
clean_db('/var/lib/cloudif/access-ingest/access.db',[
 ('snapshots_older_180d','delete from snapshots where received_at < datetime("now","-180 days")',()),
])
# Release retention: keep active, previous, last 5, and anything younger than 14 days.
base=pathlib.Path('/srv/cloudif/releases'); protected=set()
for n in ('active','previous','candidate'):
    p=base/'pointers'/n
    try: protected.add(p.resolve())
    except Exception: pass
rows=[]
for d in base.iterdir():
    if not d.is_dir() or d.name=='pointers': continue
    rows.append((d.stat().st_mtime,d))
rows.sort(reverse=True); protected |= {d for _,d in rows[:5]}
removed=[]
for mtime,d in rows[5:]:
    if d in protected or NOW-mtime < 14*86400: continue
    shutil.rmtree(d); removed.append(str(d))
result['deleted']['releases']=removed
out='/var/lib/cloudif/health/data-retention.json'; pathlib.Path(out).write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')))
print(json.dumps(result,ensure_ascii=False)); raise SystemExit(0 if result['ok'] else 1)
