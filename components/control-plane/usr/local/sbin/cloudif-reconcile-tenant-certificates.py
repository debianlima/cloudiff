#!/usr/bin/env python3
from pathlib import Path
import sqlite3, subprocess, json, datetime, re, sys
BASE=Path('/srv/cloudif')
DB=Path('/var/lib/cloudif/portal/cloudif-portal.db')
HELPER=BASE/'bin/cloudif-ensure-tenant-certificate.sh'
LOG=Path('/var/log/cloudif/tenant-certificate-reconcile.log')
VALID=re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')

def tenants():
    out=set()
    for root in (BASE/'tenants', BASE/'data/tenants'):
        if root.exists():
            out.update(p.name.lower() for p in root.iterdir() if p.is_dir())
    if DB.exists():
        con=sqlite3.connect(DB)
        for query in ('select tenant from tenant_policy','select tenant from tenant_acl','select distinct tenant from projects where tenant is not null'):
            try: out.update(str(r[0]).lower() for r in con.execute(query) if r[0])
            except sqlite3.DatabaseError: pass
        con.close()
    return sorted(t for t in out if VALID.fullmatch(t))

def main():
    LOG.parent.mkdir(parents=True,exist_ok=True)
    results=[]
    for tenant in tenants():
        p=subprocess.run([str(HELPER),tenant],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=420)
        results.append({'tenant':tenant,'ok':p.returncode==0,'output':p.stdout[-1000:]})
    stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with LOG.open('a') as f: f.write(json.dumps({'at':stamp,'results':results},ensure_ascii=False)+'\n')
    failed=[r for r in results if not r['ok']]
    print(json.dumps({'ok':not failed,'checked':len(results),'failed':[r['tenant'] for r in failed]},ensure_ascii=False))
    return 1 if failed else 0
if __name__=='__main__': raise SystemExit(main())
