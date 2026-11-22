#!/usr/bin/env python3
import os,re,subprocess,sys,tempfile
from pathlib import Path
from urllib.parse import urlparse

KEY_ID=os.environ.get('CLOUDIF_PGH_ATLAS_KEY_ID','pgh-atlas-access-admin-v1')
CRED=Path(os.environ.get('CLOUDIF_PGH_ATLAS_CREDENTIAL',f'/var/lib/cloudif/credentials/{KEY_ID}.cred'))
KNOWN=Path(os.environ.get('CLOUDIF_PGH_CORE_RELAY_KNOWN_HOSTS','/etc/cloudif/pgh-core-relay-known_hosts'))
TARGET=os.environ.get('CLOUDIF_PGH_CORE_RELAY_TARGET','pgh-vault-admin@127.0.0.1')
PORT=int(os.environ.get('CLOUDIF_PGH_CORE_RELAY_PORT','22220'))
BASE=os.environ.get('CLOUDIF_PGH_CORE_BASE_URL','').strip().rstrip('/')

def extract_bootstrap_url(text,base):
    expected=urlparse(base)
    if expected.scheme!='https' or not expected.hostname:
        raise ValueError('invalid_core_base')
    for raw in re.findall(r'https://[^\s<>"\']+',text or ''):
        u=urlparse(raw.rstrip('.,;'))
        if u.scheme!='https': continue
        if u.hostname!=expected.hostname: continue
        if (u.port or 443)!=(expected.port or 443): continue
        if not u.path.startswith('/dashboard/bootstrap'): continue
        return raw.rstrip('.,;')
    raise ValueError('bootstrap_url_not_found')

def main():
    if not BASE or not CRED.is_file() or not KNOWN.is_file():
        print('PGH_DASHBOARD_SESSION_NOT_CONFIGURED',file=sys.stderr); return 20
    with tempfile.TemporaryDirectory(prefix='pgh-atlas-session.',dir='/run') as td:
        key=Path(td)/'key'
        dec=subprocess.run(['systemd-creds','decrypt','--name='+KEY_ID,str(CRED),str(key)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8)
        if dec.returncode!=0:
            print('PGH_DASHBOARD_SESSION_CREDENTIAL_ERROR',file=sys.stderr); return 21
        key.chmod(0o600)
        cmd=['ssh','-F','/dev/null','-p',str(PORT),'-i',str(key),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(KNOWN),'-o','ConnectTimeout=7',TARGET,'dashboard-session']
        try:r=subprocess.run(cmd,text=True,capture_output=True,timeout=12)
        except subprocess.TimeoutExpired:
            print('PGH_DASHBOARD_SESSION_TIMEOUT',file=sys.stderr); return 22
        if r.returncode!=0:
            print('PGH_DASHBOARD_SESSION_SSH_DENIED',file=sys.stderr); return 23
        try:url=extract_bootstrap_url(r.stdout,BASE)
        except ValueError:
            print('PGH_DASHBOARD_SESSION_INVALID_RESPONSE',file=sys.stderr); return 24
        print(url)
        return 0
if __name__=='__main__': raise SystemExit(main())
