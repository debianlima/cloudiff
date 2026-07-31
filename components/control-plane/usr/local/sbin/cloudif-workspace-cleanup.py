#!/usr/bin/env python3
import json,subprocess,time,datetime,os,shutil
LABEL='cloudif.managed=true';MAX_AGE=900
def run(*args):
 p=subprocess.run(['/usr/bin/docker',*args],text=True,capture_output=True,timeout=20)
 if p.returncode!=0:raise RuntimeError((p.stderr or p.stdout)[:300])
 return p.stdout
ids=[x for x in run('ps','-aq','--filter','label='+LABEL).split() if x]
removed=[];kept=[];now=time.time()
for cid in ids:
 d=json.loads(run('inspect',cid))[0];created=d['Created'];ts=datetime.datetime.fromisoformat(created.replace('Z','+00:00')).timestamp();age=max(0,now-ts);state=d['State']['Status']
 if state!='running' or age>MAX_AGE:
  run('rm','-f',cid);removed.append({'id':cid[:12],'state':state,'age_seconds':round(age)})
 else:kept.append({'id':cid[:12],'state':state,'age_seconds':round(age)})
workspace_root='/var/lib/cloudif/workspaces';removed_dirs=[];kept_dirs=[]
active_managed=bool(ids)
if os.path.isdir(workspace_root):
 for entry in os.scandir(workspace_root):
  if not entry.is_dir(follow_symlinks=False):
   kept_dirs.append({'name':entry.name,'reason':'not_directory'});continue
  try:age=max(0,now-entry.stat(follow_symlinks=False).st_mtime)
  except FileNotFoundError:continue
  if active_managed:
   kept_dirs.append({'name':entry.name,'age_seconds':round(age),'reason':'managed_container_exists'})
  elif age>MAX_AGE:
   shutil.rmtree(entry.path,ignore_errors=False);removed_dirs.append({'name':entry.name,'age_seconds':round(age)})
  else:kept_dirs.append({'name':entry.name,'age_seconds':round(age),'reason':'fresh'})
print(json.dumps({'ok':True,'removed':removed,'kept':kept,'removed_dirs':removed_dirs,'kept_dirs':kept_dirs,'max_age_seconds':MAX_AGE},separators=(',',':')))
