#!/usr/bin/env python3
import datetime as dt, hashlib, json, subprocess, urllib.request
from pathlib import Path
from cloudif_machine_db import connect as db_connect, table_columns
ENV=Path('/etc/cloudif/certificate-alerting.env')
INTERVALS={'urgent':900,'critical':900,'warning':21600,'info':10**12}

def utcnow(): return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
def iso(t): return t.isoformat().replace('+00:00','Z')
def parse(v):
 if not v: return None
 try: return dt.datetime.fromisoformat(str(v).replace('Z','+00:00'))
 except Exception: return None
def env():
 d={}
 if ENV.exists():
  for raw in ENV.read_text(errors='ignore').splitlines():
   line=raw.strip()
   if line and not line.startswith('#') and '=' in line:
    k,v=line.split('=',1); d[k.strip()]=v.strip().strip('"').strip("'")
 return d

def should_dispatch(r,now):
 if r.get('state')!='open' or r.get('acknowledged_at'): return False,'suppressed'
 material=json.dumps({'severity':r.get('severity'),'state':r.get('state'),'message':r.get('message'),'detail_json':r.get('detail_json')},sort_keys=True,separators=(',',':'),ensure_ascii=False)
 current_hash=hashlib.sha256(material.encode()).hexdigest()
 if current_hash != (r.get('dispatch_hash') or ''): return True,current_hash
 severity=str(r.get('severity') or 'warning').lower()
 last=parse(r.get('last_notified_at'))
 if last is None: return True,current_hash
 if (now-last).total_seconds() >= INTERVALS.get(severity,21600): return True,current_hash
 return False,current_hash

def main():
 c=db_connect(); cols=table_columns(c,'certificate_alerts')
 if 'dispatch_hash' not in cols: c.execute("alter table certificate_alerts add column dispatch_hash text default ''")
 if 'last_notified_at' not in cols: c.execute('alter table certificate_alerts add column last_notified_at text')
 if 'notify_count' not in cols: c.execute('alter table certificate_alerts add column notify_count integer not null default 0')
 c.commit(); now=utcnow(); rows=[]; suppressed=0
 for row in c.execute("select * from certificate_alerts where state='open' order by updated_at desc"):
  r=dict(row); ok,h=should_dispatch(r,now)
  if ok: r['_dispatch_hash']=h; rows.append(r)
  else: suppressed+=1
 for r in rows:
  age=max(0,int((now-(parse(r.get('opened_at')) or now)).total_seconds()))
  msg=f"severity={r['severity']} alert_id={r['id']} notify_count={int(r.get('notify_count') or 0)+1} age_seconds={age} message={r['message']}"
  subprocess.run(['/usr/bin/logger','-t','cloudif-certificate-alert',msg],check=False)
 cfg=env(); url=cfg.get('CLOUDIF_CERT_ALERT_WEBHOOK_URL','').strip(); delivered=True
 if url and rows:
  body=json.dumps({'source':'cloudif-certificate-monitor','generated_at':iso(now),'alerts':[{k:v for k,v in r.items() if not k.startswith('_')} for r in rows]},ensure_ascii=False).encode()
  req=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json'},method='POST')
  try:
   with urllib.request.urlopen(req,timeout=20) as resp:
    print('webhook_status=',resp.status); delivered=200 <= resp.status < 300
  except Exception as e:
   delivered=False; print('webhook_error=',type(e).__name__)
 if delivered:
  for r in rows:
   c.execute('update certificate_alerts set dispatch_hash=?,last_notified_at=?,notify_count=notify_count+1 where id=?',(r['_dispatch_hash'],iso(now),r['id']))
  c.commit()
 print('open_alerts=',c.execute("select count(*) as n from certificate_alerts where state='open'").fetchone()['n'],'dispatched=',len(rows),'suppressed=',suppressed,'webhook_configured=',bool(url),'delivery_ok=',delivered)
 c.close()
if __name__=='__main__': main()
