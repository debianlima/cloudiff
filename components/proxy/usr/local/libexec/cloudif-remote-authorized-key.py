#!/usr/bin/env python3
"""Fail-closed local AuthorizedKeysCommand for the CloudIFF 443 gateway."""
import base64,hashlib,json,re,sys,time
from pathlib import Path
USER_RE=re.compile(r'^cifremote\d{3}$')
CACHE=Path('/run/cloudif-remote/leases.json')
MAX_CACHE_AGE=30

def fingerprint(key_type,key_blob):
    try:blob=base64.b64decode(key_blob+'===')
    except Exception:return ''
    return 'SHA256:'+base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip('=')

def main():
    if len(sys.argv)!=4:return 0
    user,key_type,key_blob=sys.argv[1:]
    if not USER_RE.fullmatch(user) or key_type not in ('ssh-ed25519','ssh-rsa','ecdsa-sha2-nistp256','ecdsa-sha2-nistp384','ecdsa-sha2-nistp521'):return 0
    try:d=json.loads(CACHE.read_text());now=int(time.time());fetched=int(d.get('fetched_at') or 0)
    except Exception:return 0
    if fetched<=0 or now-fetched>MAX_CACHE_AGE:return 0
    fp=fingerprint(key_type,key_blob)
    for r in d.get('leases') or []:
        if str(r.get('gateway_user') or '')!=user or int(r.get('expires_at') or 0)<=now or str(r.get('ssh_fingerprint') or '')!=fp:continue
        try:targets=json.loads(r.get('targets_json') or '[]')
        except Exception:return 0
        opts=['no-agent-forwarding','no-X11-forwarding','no-pty','no-user-rc']
        for t in targets:
            host=str(t.get('gateway_host') or '');port=int(t.get('gateway_port') or 0)
            if not host or port<1 or port>65535:return 0
            opts.append(f'permitopen="{host}:{port}"')
        key=str(r.get('ssh_public_key') or '').strip()
        if key.startswith(key_type+' '):print(','.join(opts)+' '+key)
        return 0
    return 0
if __name__=='__main__':raise SystemExit(main())
