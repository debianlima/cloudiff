#!/usr/bin/env python3
import os,json,time,shutil,pathlib,subprocess
BASE=pathlib.Path('/srv/cloudif/releases');OUT=pathlib.Path('/var/lib/cloudif/health/storage-guard.json')
THRESHOLD=int(os.environ.get('CLOUDIF_STORAGE_THRESHOLD','82'));KEEP=int(os.environ.get('CLOUDIF_STORAGE_KEEP','5'));AGE_DAYS=int(os.environ.get('CLOUDIF_STORAGE_AGE_DAYS','14'))
def usage():
 u=shutil.disk_usage('/');return round(u.used/u.total*100,2),u.free
pct,free=usage();protected=set()
for n in ('active','previous','candidate'):
 p=BASE/'pointers'/n
 try: protected.add(p.resolve())
 except Exception: pass
rows=[]
for d in BASE.iterdir() if BASE.exists() else []:
 if not d.is_dir() or d.name=='pointers':continue
 status='unknown';at=d.stat().st_mtime
 try:
  j=json.loads((d/'result.json').read_text());status=j.get('status','unknown')
 except Exception:pass
 rows.append((at,d,status))
rows.sort(reverse=True);protected.update(d for _,d,_ in rows[:KEEP])
cut=time.time()-AGE_DAYS*86400
candidates=[]
for at,d,status in rows:
 if d in protected or at>=cut:continue
 if status in {'failed_before_install','failed_candidate','failed_and_reverted','rolled_back','unknown'}:candidates.append(d)
deleted=[]
if pct>=THRESHOLD:
 for d in candidates:
  shutil.rmtree(d);deleted.append(str(d))
pct2,free2=usage();result={'ok':True,'before_pct':pct,'after_pct':pct2,'free_bytes':free2,'threshold_pct':THRESHOLD,'protected':[str(x) for x in sorted(protected)],'candidates':[str(x) for x in candidates],'deleted':deleted,'action':'pruned' if deleted else 'none','at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
OUT.parent.mkdir(parents=True,exist_ok=True);tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')));os.replace(tmp,OUT);print(json.dumps(result,ensure_ascii=False))
