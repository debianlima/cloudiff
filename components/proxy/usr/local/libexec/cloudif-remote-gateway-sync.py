#!/usr/bin/env python3
"""Continuously cache active project leases from the Portal for local SSH authorization."""
import grp,json,os,time,urllib.request
from pathlib import Path
ENV=Path('/etc/cloudif/remote-gateway.env');CACHE=Path('/run/cloudif-remote/leases.json')
ALLOWED={'gateway_user','lease_id','project_slug','ssh_public_key','ssh_fingerprint','targets_json','expires_at'}
def cfg():
    out={}
    for line in ENV.read_text().splitlines():
        if not line or line.lstrip().startswith('#') or '=' not in line:continue
        k,v=line.split('=',1);out[k.strip()]=v.strip()
    return out
def fetch(c):
    req=urllib.request.Request(c['CLOUDIF_REMOTE_PORTAL_INTERNAL_URL'].rstrip('/')+'/cloudiff/portal/internal/remote-ssh/active-users',headers={'Authorization':'Bearer '+c['CLOUDIF_REMOTE_GATEWAY_TOKEN'],'Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=12) as r:d=json.load(r)
    if not isinstance(d,dict) or not d.get('ok') or d.get('secrets_exposed') is not False:raise RuntimeError('invalid_portal_feed')
    leases=[]
    for raw in d.get('leases') or []:
        row={k:raw.get(k) for k in ALLOWED};
        if not row.get('gateway_user') or not row.get('ssh_public_key') or not row.get('targets_json'):continue
        leases.append(row)
    return {'fetched_at':int(time.time()),'leases':leases}
def write_cache(data):
    CACHE.parent.mkdir(parents=True,exist_ok=True);tmp=CACHE.with_suffix('.tmp');tmp.write_text(json.dumps(data,separators=(',',':'))+'\n');os.chmod(tmp,0o640);os.chown(tmp,0,grp.getgrnam('cloudif-authz').gr_gid);os.replace(tmp,CACHE)
def main():
    c=cfg()
    while True:
        try:write_cache(fetch(c))
        except Exception as e:print('remote_gateway_sync_failed='+type(e).__name__,flush=True)
        time.sleep(2)
if __name__=='__main__':raise SystemExit(main())
