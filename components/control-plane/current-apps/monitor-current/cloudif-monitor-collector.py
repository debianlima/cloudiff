#!/usr/bin/env python3
from pathlib import Path
import urllib.request,urllib.error,json,sqlite3,time,os,re,tempfile

def env(path):
 d={}
 for raw in Path(path).read_text().splitlines():
  line=raw.strip()
  if not line or line.startswith('#') or '=' not in line:continue
  k,v=line.split('=',1);d[k.strip()]=v.strip().strip('"').strip("'")
 return d
C=env('/etc/cloudif/control-plane.env');K=env('/etc/cloudif/komodo-agent-client.env')
def req(method,url,payload=None,headers=None,timeout=35):
 data=None if payload is None else json.dumps(payload).encode();r=urllib.request.Request(url,data=data,method=method,headers=headers or {})
 with urllib.request.urlopen(r,timeout=timeout) as x:return json.load(x)
projects=req('GET','http://127.0.0.1:18197/v1/projects',headers={'Authorization':'Bearer '+C['CLOUDIF_CONTROL_TOKEN']})['projects']
DB='/var/lib/cloudif/monitoring/monitor.db';os.makedirs(os.path.dirname(DB),exist_ok=True)
con=sqlite3.connect(DB,timeout=30);con.execute('pragma journal_mode=delete');con.execute('pragma busy_timeout=30000')
con.executescript('''
create table if not exists samples(id integer primary key autoincrement,ts text not null,project_id text not null,slug text not null,state text,running integer,healthy integer,cpu_pct real,mem_pct real,mem_usage text,net_io text,block_io text,pids integer,container_name text,container_image text,issues_json text,raw_json text);
create index if not exists idx_samples_project_ts on samples(project_id,ts desc);
create table if not exists latest(project_id text primary key,ts text not null,slug text not null,state text,running integer,healthy integer,cpu_pct real,mem_pct real,mem_usage text,net_io text,block_io text,pids integer,container_name text,container_image text,issues_json text,raw_json text);
''')
now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());ok=0;failed=[]
for p in projects:
 payload={'project':p['slug'],'stack_id':p.get('stack_id') or '','service':'web','terminal':'cloudif-'+p['slug'],'shell':'sh'}
 try:
  d=req('POST',K['KOMODO_AGENT_URL'].rstrip('/')+'/komodo/project/audit',payload,{'Content-Type':'application/json','X-CloudIF-Token':K['KOMODO_AGENT_TOKEN'],'Authorization':'Bearer '+K['KOMODO_AGENT_TOKEN']})
  st=d.get('container_stats') or {}
  num=lambda x: float(re.sub(r'[^0-9.]','',str(x or '0')) or 0)
  vals=(now,p['project_id'],p['slug'],d.get('state') or 'unknown',1 if d.get('running') else 0,1 if d.get('healthy') else 0,num(st.get('cpu_perc')),num(st.get('mem_perc')),st.get('mem_usage') or '',st.get('net_io') or '',st.get('block_io') or '',int(re.sub(r'\D','',str(st.get('pids') or '0')) or 0),d.get('container_name') or '',d.get('container_image') or '',json.dumps(d.get('issues') or [],ensure_ascii=False),json.dumps(d,ensure_ascii=False,separators=(',',':')))
  con.execute('insert into samples(ts,project_id,slug,state,running,healthy,cpu_pct,mem_pct,mem_usage,net_io,block_io,pids,container_name,container_image,issues_json,raw_json) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',vals)
  con.execute('insert into latest(project_id,ts,slug,state,running,healthy,cpu_pct,mem_pct,mem_usage,net_io,block_io,pids,container_name,container_image,issues_json,raw_json) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) on conflict(project_id) do update set ts=excluded.ts,slug=excluded.slug,state=excluded.state,running=excluded.running,healthy=excluded.healthy,cpu_pct=excluded.cpu_pct,mem_pct=excluded.mem_pct,mem_usage=excluded.mem_usage,net_io=excluded.net_io,block_io=excluded.block_io,pids=excluded.pids,container_name=excluded.container_name,container_image=excluded.container_image,issues_json=excluded.issues_json,raw_json=excluded.raw_json', (p['project_id'],now,p['slug'])+vals[3:])
  ok+=1
 except Exception as e:failed.append({'slug':p['slug'],'error':type(e).__name__})
con.commit();assert con.execute('pragma integrity_check').fetchone()[0]=='ok';con.close()
try:
 import pwd,grp;os.chown(DB,pwd.getpwnam('cloudif-control').pw_uid,grp.getgrnam('cloudif-control').gr_gid);os.chmod(DB,0o640)
except Exception:pass
print(json.dumps({'ok':len(failed)==0,'collected':ok,'failed':failed},ensure_ascii=False))
