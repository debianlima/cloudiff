#!/usr/bin/env python3
import grp,json,pwd,subprocess,time
from pathlib import Path
CACHE=Path('/run/cloudif-remote/leases.json');MAX_CACHE_AGE=30
def group_users(name):
    g=grp.getgrnam(name);users=set(g.gr_mem)
    for p in pwd.getpwall():
        if p.pw_gid==g.gr_gid:users.add(p.pw_name)
    return {u for u in users if u.startswith('cifremote')}
def active():
    try:d=json.loads(CACHE.read_text());now=int(time.time());fetched=int(d.get('fetched_at') or 0)
    except Exception:return set()
    if fetched<=0 or now-fetched>MAX_CACHE_AGE:return set()
    return {str(x.get('gateway_user') or '') for x in d.get('leases') or [] if int(x.get('expires_at') or 0)>now}
def terminate_user(user):
    # OpenSSH on current Debian names authenticated children sshd-session; older releases use sshd.
    pids=set()
    for name in ('sshd-session','sshd'):
        cp=subprocess.run(['/usr/bin/pgrep','-u',user,'-x',name],capture_output=True,text=True)
        pids.update(x for x in cp.stdout.split() if x.isdigit())
    if not pids:return 0
    for name in ('sshd-session','sshd'):
        subprocess.run(['/usr/bin/pkill','-TERM','-u',user,'-x',name],check=False)
    time.sleep(.4)
    for name in ('sshd-session','sshd'):
        subprocess.run(['/usr/bin/pkill','-KILL','-u',user,'-x',name],check=False)
    return len(pids)
def main():
    live=active();killed=0
    for u in sorted(group_users('cloudif-remote')-live):killed+=terminate_user(u)
    print('inactive_gateway_sessions_terminated='+str(killed));return 0
if __name__=='__main__':raise SystemExit(main())
