#!/usr/bin/env python3
import argparse,datetime as dt,hashlib,json,os,tempfile,time,urllib.error,urllib.request
from pathlib import Path
DEFAULT='/etc/cloudif/production-targets.json';OUT=Path('/var/lib/cloudif/production-window-guard');SLUG='atalhos-cloudif-iff1860746'
def utc(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def atomic_json(path,x):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(prefix=path.name+'.',dir=str(path.parent));
 with os.fdopen(fd,'w') as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
def alert(kind,severity,detail,cfg,now):
 aid=hashlib.sha256(json.dumps({'at':int(now),'kind':kind,'project_slug':SLUG,'detail':detail},sort_keys=True,separators=(',',':')).encode()).hexdigest()[:24]
 x={'at':int(now),'alert_id':aid,'kind':kind,'severity':severity,'project_slug':SLUG,'detail':detail,'owner':cfg.get('change_owner'),'escalation':cfg.get('change_escalation'),'ack_required':severity in {'high','critical'},'secrets_exposed':False}
 OUT.mkdir(parents=True,exist_ok=True);open(OUT/'alerts.jsonl','a').write(json.dumps(x,separators=(',',':'))+'\n');atomic_json(OUT/'latest-alert.json',x);return x
def reseal(allcfg,cfg,reason,source,now):
 changed=any(cfg.get(k) is True for k in ('change_window_open','activation_allowed','enabled','production_effects_enabled'))
 cfg.update({'change_window_open':False,'activation_allowed':False,'enabled':False,'production_effects_enabled':False,'last_resealed_at':int(now),'last_reseal_reason':reason,'last_reseal_source':source})
 return changed
def check(path=DEFAULT,now=None,write=True,probe=True,source='timer'):
 now=time.time() if now is None else now;allcfg=json.load(open(path));cfg=allcfg[SLUG];w=cfg.get('change_window') or {};issues=[]
 required=('id','start_at','end_at','timezone','max_duration_seconds','auto_reseal','digest_sha256')
 if not all(k in w for k in required):issues.append('window_metadata_incomplete')
 else:
  try:
   st,en=utc(w['start_at']),utc(w['end_at']);dur=en-st
   if not (0<dur<=int(w['max_duration_seconds'])<=7200):issues.append('window_duration_invalid')
   canon={k:w[k] for k in ('id','start_at','end_at','timezone','max_duration_seconds','auto_reseal','owner','escalation') if k in w};dig=hashlib.sha256(json.dumps(canon,sort_keys=True,separators=(',',':')).encode()).hexdigest()
   if dig!=w['digest_sha256']:issues.append('window_digest_mismatch')
   inside=st<=now<en
  except Exception:issues.append('window_timestamp_invalid');inside=False
 if w.get('auto_reseal') is not True:issues.append('auto_reseal_disabled')
 if issues:reason=issues[0]
 elif not inside and w.get('status') in {'not-scheduled','cancelled'}:reason='window_not_scheduled'
 elif not inside and w.get('status')=='scheduled' and now<st:reason='window_scheduled_future'
 elif not inside:reason='window_expired_or_not_started'
 elif cfg.get('dual_approval_required') is not True:reason='dual_approval_not_required'
 elif cfg.get('snapshot_signature_verified') is not True or cfg.get('change_dossier_signed') is not True:reason='signed_evidence_missing'
 else:reason='gates_closed_by_policy'
 changed=reseal(allcfg,cfg,reason,source,now)
 ext_code=None;sealed=None
 if probe:
  try:urllib.request.urlopen(cfg['real_target_url'],timeout=15);ext_code=200
  except urllib.error.HTTPError as e:
   ext_code=e.code
   try:sealed=json.load(e).get('sealed')
   except Exception:sealed=None
  except Exception:ext_code=0
  expected=200 if cfg.get('public_production_active') is True else 503
  endpoint_ok=(ext_code==200) if expected==200 else (ext_code==503 and sealed is True)
  if not endpoint_ok:
   issues.append('production_endpoint_divergence');changed=reseal(allcfg,cfg,'production_endpoint_divergence',source,now) or changed
 if write:atomic_json(path,allcfg)
 severity='critical' if 'production_endpoint_divergence' in issues else ('high' if issues or changed else 'info')
 if reason in {'window_not_scheduled','window_scheduled_future'} and not issues and not changed:severity='info'
 al=None
 if severity!='info':al=alert(reason if not issues else issues[0],severity,{'issues':issues,'changed':changed,'external_code':ext_code},cfg,now)
 result={'ok':not issues,'project_slug':SLUG,'window_open':False,'activation_allowed':False,'production_enabled':False,'production_effects_enabled':False,'resealed':changed,'reason':reason,'external_code':ext_code,'sealed':sealed,'alert_emitted':al is not None,'severity':severity,'secrets_exposed':False}
 atomic_json(OUT/'latest.json',result);return result
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--config',default=DEFAULT);a.add_argument('--now',type=float);a.add_argument('--no-probe',action='store_true');a.add_argument('--source',default='timer');x=a.parse_args();r=check(x.config,x.now,True,not x.no_probe,x.source);print(json.dumps(r,separators=(',',':')))
