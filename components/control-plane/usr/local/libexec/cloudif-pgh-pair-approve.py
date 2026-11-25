#!/usr/bin/env python3
import json,os,re,subprocess,sys,tempfile,urllib.error,urllib.request
from pathlib import Path
KEY_ID=os.environ.get('CLOUDIF_PGH_PAIR_KEY_ID','pgh-atlas-pairing-recovery-v1')
CRED=Path(os.environ.get('CLOUDIF_PGH_PAIR_CREDENTIAL',f'/var/lib/cloudif/credentials/{KEY_ID}.cred'))
KNOWN=Path(os.environ.get('CLOUDIF_PGH_CORE_RELAY_KNOWN_HOSTS','/etc/cloudif/pgh-core-relay-known_hosts'))
TARGET=os.environ.get('CLOUDIF_PGH_CORE_RELAY_TARGET','pgh-vault-admin@127.0.0.1')
PORT=int(os.environ.get('CLOUDIF_PGH_CORE_RELAY_PORT','22220'))
APPROVAL_URL=os.environ.get('CLOUDIF_APPROVAL_URL','http://127.0.0.1:18204').strip().rstrip('/')
APPROVAL_TOKEN=os.environ.get('CLOUDIF_APPROVAL_TOKEN','').strip()
SLUG='pghd_server_vps'
CODE_RE=re.compile(r'^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{8}$')
POLICY_RE=re.compile(r'^[A-Za-z0-9._:-]{8,128}$')
PASS_RE=re.compile(r'^PAIR_APPROVE=PASS principal=principal:mobile\.pghd_server_vps approver=principal:service\.atlas\.pairing-recovery access_manage=no$')

def policy_allowed(policy_id):
    if not APPROVAL_TOKEN or not APPROVAL_URL:return False,'approval_not_configured'
    req=urllib.request.Request(APPROVAL_URL+'/v1/approval-policies?status=active',headers={'Authorization':'Bearer '+APPROVAL_TOKEN,'Accept':'application/json'},method='GET')
    try:
        with urllib.request.urlopen(req,timeout=8) as r:data=json.load(r)
    except (urllib.error.URLError,urllib.error.HTTPError,TimeoutError,OSError,ValueError):
        return False,'approval_unavailable'
    if not isinstance(data,dict) or not data.get('ok'):return False,'approval_invalid_response'
    for p in data.get('policies') or []:
        if str(p.get('policy_id') or '')!=policy_id:continue
        if p.get('revoked_at'):return False,'policy_revoked'
        if p.get('project_slug')!='pghd-contexto':return False,'project_not_allowed'
        if p.get('action')!='pgh.device.pair':return False,'action_not_allowed'
        if p.get('requested_by')!='principal:mobile.pghd_server_vps':return False,'requester_not_allowed'
        return True,'policy_match'
    return False,'policy_not_found'

def main(argv=None):
    argv=list(sys.argv if argv is None else argv)
    if len(argv)!=3:
        print('PGH_PAIR_APPROVE_USAGE_ERROR',file=sys.stderr);return 19
    policy_id=str(argv[1] or '').strip();code=str(argv[2] or '').strip().upper()
    if not POLICY_RE.fullmatch(policy_id):
        print('PGH_PAIR_APPROVE_POLICY_INVALID',file=sys.stderr);return 12
    if not CODE_RE.fullmatch(code):
        print('PGH_PAIR_APPROVE_CODE_INVALID',file=sys.stderr);return 13
    allowed,reason=policy_allowed(policy_id)
    if not allowed:
        print('PGH_PAIR_APPROVE_POLICY_DENIED reason='+reason,file=sys.stderr);return 14
    if not CRED.is_file() or not KNOWN.is_file():
        print('PGH_PAIR_APPROVE_NOT_CONFIGURED',file=sys.stderr);return 20
    with tempfile.TemporaryDirectory(prefix='pgh-atlas-pair.',dir='/run') as td:
        key=Path(td)/'key'
        dec=subprocess.run(['systemd-creds','decrypt','--name='+KEY_ID,str(CRED),str(key)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8)
        if dec.returncode!=0:
            print('PGH_PAIR_APPROVE_CREDENTIAL_ERROR',file=sys.stderr);return 21
        key.chmod(0o600)
        remote='pair-approve '+code+' '+SLUG
        cmd=['ssh','-F','/dev/null','-p',str(PORT),'-i',str(key),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(KNOWN),'-o','ConnectTimeout=7',TARGET,remote]
        try:r=subprocess.run(cmd,text=True,capture_output=True,timeout=12)
        except subprocess.TimeoutExpired:
            print('PGH_PAIR_APPROVE_TIMEOUT',file=sys.stderr);return 22
        if r.returncode!=0:
            if r.returncode in (13,64,65,66):
                print('PGH_PAIR_APPROVE_DENIED',file=sys.stderr);return 13
            print('PGH_PAIR_APPROVE_SSH_ERROR',file=sys.stderr);return 23
        line=(r.stdout or '').strip().splitlines()[-1] if (r.stdout or '').strip() else ''
        if not PASS_RE.fullmatch(line):
            print('PGH_PAIR_APPROVE_INVALID_RESPONSE',file=sys.stderr);return 24
        print('PGH_PAIR_APPROVE=PASS principal=principal:mobile.pghd_server_vps access_manage=no')
        return 0
if __name__=='__main__': raise SystemExit(main())
