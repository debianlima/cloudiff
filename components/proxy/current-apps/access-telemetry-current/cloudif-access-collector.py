#!/usr/bin/env python3
import os,re,sqlite3,hashlib,hmac,time,json,ipaddress
from pathlib import Path
DB=os.environ.get('CLOUDIF_ACCESS_DB','/var/lib/cloudif/access-telemetry/access.db')
LOGDIR=Path(os.environ.get('CLOUDIF_ACCESS_LOGDIR','/srv/cloudif/proxy/npm/data/logs'))
SALT=os.environ['CLOUDIF_ACCESS_SALT'].encode()
PAT=re.compile(r'^\[(?P<ts>[^]]+)\]\s+-\s+(?P<upstream>\S+)\s+(?P<status>\d{3}|-)\s+-\s+(?P<method>\S+)\s+(?P<scheme>\S+)\s+(?P<host>\S+)\s+"(?P<uri>[^"]*)"\s+\[Client\s+(?P<ip>[^]]+)\]\s+\[Length\s+(?P<length>\d+|-)\].*?"(?P<ua>[^"]*)"\s+"(?P<ref>[^"]*)"$')

def conn():
 c=sqlite3.connect(DB,timeout=30);c.execute('pragma busy_timeout=30000');return c

def init(c):
 c.execute('pragma journal_mode=delete')
 c.executescript('''
 create table if not exists offsets(path text primary key,inode integer not null,offset integer not null,updated_at text not null);
 create table if not exists access_daily(day text not null,host text not null,route text not null,status_class text not null,source text not null,client_class text not null,visitor_hash text not null,requests integer not null default 0,bytes integer not null default 0,last_seen text not null,primary key(day,host,route,status_class,source,client_class,visitor_hash));
 create index if not exists idx_access_day_host on access_daily(day,host);
 create table if not exists collector_meta(key text primary key,value text not null);
 ''')

def route_of(uri):
 path=uri.split('?',1)[0] or '/'
 parts=[x for x in path.split('/') if x]
 if not parts:return '/'
 if parts[0] in {'api','rest','auth','storage','realtime','functions'}:return '/'+parts[0]
 if parts[0] in {'cloudiff','cloudif','supabase','git','project'}:
  return '/'+ '/'.join(parts[:3])
 return '/'+parts[0]

def client_class(ua):
 u=ua.lower()
 if any(x in u for x in ('bot','crawler','spider','slurp')):return 'bot'
 if any(x in u for x in ('python-urllib','curl/','wget/','postman','insomnia')):return 'api'
 if any(x in u for x in ('android','iphone','ipad','mobile')):return 'mobile'
 return 'browser'

def source_of(ip):
 try:return 'internal' if ipaddress.ip_address(ip).is_private else 'public'
 except Exception:return 'unknown'

def parse_ts(s):
 try:return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.strptime(s.split()[0],'%d/%b/%Y:%H:%M:%S'))
 except Exception:return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())

def visitor(day,ip):return hmac.new(SALT,(day+'|'+ip).encode(),hashlib.sha256).hexdigest()[:32]

def process_file(c,p):
 st=p.stat();row=c.execute('select inode,offset from offsets where path=?',(str(p),)).fetchone();off=0
 if row and row[0]==st.st_ino and row[1]<=st.st_size:off=row[1]
 parsed=skipped=0
 with p.open('r',encoding='utf-8',errors='replace') as f:
  f.seek(off)
  for line in f:
   m=PAT.match(line.rstrip('\n'))
   if not m:skipped+=1;continue
   d=m.groupdict();ts=parse_ts(d['ts']);day=ts[:10];status=d['status'];sc=(status[0]+'xx') if status!='-' else 'unknown';length=int(d['length']) if d['length'].isdigit() else 0
   vals=(day,d['host'].lower(),route_of(d['uri']),sc,source_of(d['ip']),client_class(d['ua']),visitor(day,d['ip']),1,length,ts)
   c.execute('insert into access_daily values(?,?,?,?,?,?,?,?,?,?) on conflict(day,host,route,status_class,source,client_class,visitor_hash) do update set requests=requests+1,bytes=bytes+excluded.bytes,last_seen=excluded.last_seen',vals);parsed+=1
  newoff=f.tell()
 c.execute('insert into offsets values(?,?,?,?) on conflict(path) do update set inode=excluded.inode,offset=excluded.offset,updated_at=excluded.updated_at',(str(p),st.st_ino,newoff,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
 return parsed,skipped

def main():
 os.makedirs(os.path.dirname(DB),exist_ok=True);c=conn();init(c);total=skip=files=0
 for p in sorted(LOGDIR.glob('*access.log')):
  if not p.is_file():continue
  a,b=process_file(c,p);total+=a;skip+=b;files+=1
 c.execute("delete from access_daily where day < date('now','-90 days')")
 c.execute('insert into collector_meta values("retention_days",?) on conflict(key) do update set value=excluded.value',('90',))
 c.execute('insert into collector_meta values("last_run",?) on conflict(key) do update set value=excluded.value',(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),))
 c.execute('insert into collector_meta values("last_parsed",?) on conflict(key) do update set value=excluded.value',(str(total),))
 c.execute('insert into collector_meta values("last_skipped",?) on conflict(key) do update set value=excluded.value',(str(skip),))
 c.commit();assert c.execute('pragma integrity_check').fetchone()[0]=='ok';c.close();print(json.dumps({'ok':True,'files':files,'parsed':total,'skipped':skip}))
if __name__=='__main__':main()
