#!/usr/bin/env python3
import argparse,datetime as dt,hashlib,json,os,stat,sys
from pathlib import Path
BASELINE=Path('/etc/cloudif/control-plane-integrity-baseline.json')
RESULT=Path('/var/lib/cloudif-machine-admin/control-plane-integrity-result.json')
PATHS=[
'/usr/local/sbin/cloudif-machine-controller.py',
'/usr/local/sbin/cloudif-machine-harvester.py',
'/usr/local/sbin/cloudif-machine-guardian.py',
'/usr/local/sbin/cloudif-machine-executor.py',
'/usr/local/sbin/cloudif-agent-pki.py',
'/usr/local/sbin/cloudif-machine-admin-db-backup.sh',
'/usr/local/sbin/cloudif-machine-admin-dr-backup.sh',
'/usr/local/sbin/cloudif-machine-admin-dr-restore-test.sh',
'/usr/local/sbin/cloudif-controller-certificate-renew.sh',
'/usr/local/sbin/cloudif-certificate-alert-dispatcher.py',
'/usr/local/sbin/cloudif-healthcheck.sh',
'/srv/cloudif/router/conf.d/default.conf',
'/srv/cloudif/router/docker-compose.yml',
'/srv/cloudif/machine-admin/docker-compose.yml',
'/etc/systemd/system/cloudif-machine-controller.service',
'/etc/systemd/system/cloudif-machine-admin-db-backup.service',
'/etc/systemd/system/cloudif-machine-admin-db-backup.timer',
'/etc/systemd/system/cloudif-machine-admin-dr-backup.service',
'/etc/systemd/system/cloudif-machine-admin-dr-backup.timer',
'/etc/systemd/system/cloudif-machine-admin-dr-restore-test.service',
'/etc/systemd/system/cloudif-machine-admin-dr-restore-test.timer',
'/etc/systemd/system/cloudif-controller-certificate-renew.service',
'/etc/systemd/system/cloudif-controller-certificate-renew.timer',
'/etc/systemd/system/cloudif-certificate-alert-dispatcher.service',
'/etc/systemd/system/cloudif-certificate-alert-dispatcher.timer',
'/etc/systemd/system/cloudif-healthcheck.service',
'/etc/systemd/system/cloudif-healthcheck.timer',
'/etc/rsyslog.d/50-cloudif-certificate-alerts.conf',
'/etc/logrotate.d/cloudif-certificate-alerts',
'/etc/cloudif/machine-policy-signing.pub',
'/var/lib/cloudif-agent-pki/root/certs/root-ca.pem',
'/var/lib/cloudif-agent-pki/issuing/certs/issuing-ca.pem',
'/var/lib/cloudif-agent-pki/issuing/certs/ca-chain.pem',
]
SENSITIVE=[
'/etc/cloudif/machine-controller-db.env','/etc/cloudif/machine-admin-security.env','/etc/cloudif/machine-policy-signing.key','/etc/cloudif/certificate-alerting.env','/etc/cloudif/machine-agent.env','/var/lib/cloudif-agent-pki/issued/controller-server.key','/var/lib/cloudif-agent-pki/issued/hospedagem.key','/srv/cloudif/router/mtls/controller-server.key']

def now(): return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def digest(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def metadata(path):
 p=Path(path); st=p.stat()
 return {'path':path,'sha256':digest(path),'mode':format(stat.S_IMODE(st.st_mode),'04o'),'uid':st.st_uid,'gid':st.st_gid,'size':st.st_size}
def generate():
 missing=[p for p in PATHS if not Path(p).is_file()]
 if missing: raise SystemExit('missing_baseline_paths:'+','.join(missing))
 data={'schema':1,'generated_at':now(),'entries':[metadata(p) for p in PATHS],'sensitive_permissions':{p:{'mode':format(stat.S_IMODE(Path(p).stat().st_mode),'04o'),'uid':Path(p).stat().st_uid,'gid':Path(p).stat().st_gid} for p in SENSITIVE if Path(p).exists()}}
 BASELINE.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n'); os.chmod(BASELINE,0o600)
 print(json.dumps({'baseline':'generated','entries':len(data['entries']),'sensitive':len(data['sensitive_permissions'])}))
def check():
 if not BASELINE.exists(): raise SystemExit('baseline_missing')
 b=json.loads(BASELINE.read_text()); changed=[]; missing=[]; permission_violations=[]
 for e in b['entries']:
  p=Path(e['path'])
  if not p.is_file(): missing.append(e['path']); continue
  cur=metadata(e['path'])
  diffs={k:{'expected':e[k],'actual':cur[k]} for k in ('sha256','mode','uid','gid') if cur[k]!=e[k]}
  if diffs: changed.append({'path':e['path'],'differences':diffs})
 for p in SENSITIVE:
  x=Path(p)
  if not x.exists(): continue
  st=x.stat(); mode=stat.S_IMODE(st.st_mode)
  if mode & 0o077 or st.st_uid!=0 or st.st_gid!=0: permission_violations.append({'path':p,'mode':format(mode,'04o'),'uid':st.st_uid,'gid':st.st_gid})
 result={'checked_at':now(),'baseline_generated_at':b.get('generated_at'),'result':'ok' if not changed and not missing and not permission_violations else 'failed','changed':changed,'missing':missing,'permission_violations':permission_violations}
 RESULT.parent.mkdir(parents=True,exist_ok=True); RESULT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n'); os.chmod(RESULT,0o600)
 print(json.dumps({'result':result['result'],'changed':len(changed),'missing':len(missing),'permission_violations':len(permission_violations)}))
 if result['result']!='ok': raise SystemExit(1)
if __name__=='__main__':
 ap=argparse.ArgumentParser(); ap.add_argument('action',choices=['generate','check']); a=ap.parse_args(); generate() if a.action=='generate' else check()
