#!/usr/bin/env python3
"""Maintain project DB reverse relays from Hospedagem to Mauricio over outbound SSH/443."""
import json,subprocess,time,urllib.request
from pathlib import Path
ENV=Path('/etc/cloudif/remote-access.env')
SOCK='/run/cloudif-remote-connector/master.sock'
DEST='cifconn-hosp@cloudiff.duckdns.org'

def cfg():
    out={}
    for line in ENV.read_text().splitlines():
        if not line or line.lstrip().startswith('#') or '=' not in line:continue
        k,v=line.split('=',1);out[k.strip()]=v.strip()
    return out

def feed(c):
    base=c.get('CLOUDIF_REMOTE_PORTAL_INTERNAL_URL','http://127.0.0.1:18094').rstrip('/')
    tok=c.get('CLOUDIF_REMOTE_GATEWAY_TOKEN','')
    req=urllib.request.Request(base+'/cloudiff/portal/internal/remote-ssh/active-users',headers={'Authorization':'Bearer '+tok,'Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=12) as r:d=json.load(r)
    if not isinstance(d,dict) or not d.get('ok') or d.get('secrets_exposed') is not False:raise RuntimeError('invalid_portal_feed')
    return d.get('leases') or []

def desired_relays(leases):
    out=set();now=int(time.time())
    for lease in leases:
        if int(lease.get('expires_at') or 0)<=now:continue
        try:targets=json.loads(lease.get('targets_json') or '[]')
        except Exception:continue
        for t in targets:
            if t.get('connector')!='hospedagem':continue
            relay=int(t.get('gateway_port') or 0);up_host=str(t.get('upstream_host') or '');up_port=int(t.get('upstream_port') or 0)
            if relay<1024 or relay>65535 or not up_host or up_port<1 or up_port>65535:continue
            out.add((relay,up_host,up_port))
    return out

def control(op,spec):
    relay,host,port=spec;arg=f'127.0.0.1:{relay}:{host}:{port}'
    cp=subprocess.run(['/usr/bin/ssh','-S',SOCK,'-p','443','-O',op,'-R',arg,DEST],capture_output=True,text=True,timeout=15)
    return cp.returncode==0

def master_ready():
    return subprocess.run(['/usr/bin/ssh','-S',SOCK,'-p','443','-O','check',DEST],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5).returncode==0

def main():
    current=set();c=cfg()
    while True:
        try:
            if not master_ready():
                current.clear();time.sleep(2);continue
            wanted=desired_relays(feed(c))
            for spec in sorted(current-wanted):
                control('cancel',spec);current.discard(spec)
            for spec in sorted(wanted-current):
                if control('forward',spec):current.add(spec)
        except Exception as e:
            print('remote_connector_sync_failed='+type(e).__name__,flush=True)
        time.sleep(2)
if __name__=='__main__':raise SystemExit(main())
