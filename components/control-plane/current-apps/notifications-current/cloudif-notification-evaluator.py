#!/usr/bin/env python3
import os,json,sqlite3,time,urllib.request
DB=os.environ.get('CLOUDIF_NOTIFY_DB','/var/lib/cloudif/notifications/notifications.db');MU=os.environ['CLOUDIF_MONITOR_URL'];MT=os.environ['CLOUDIF_MONITOR_TOKEN']
def get():
 r=urllib.request.Request(MU+'/v1/projects',headers={'Authorization':'Bearer '+MT});
 with urllib.request.urlopen(r,timeout=15) as x:return json.load(x)['projects']
os.makedirs(os.path.dirname(DB),exist_ok=True);c=sqlite3.connect(DB,timeout=20);c.execute('pragma journal_mode=delete');c.execute('pragma busy_timeout=20000');c.executescript('''create table if not exists notifications(id integer primary key autoincrement,dedup_key text unique not null,project_slug text,severity text not null,title text not null,message text not null,status text not null default 'open',first_seen text not null,last_seen text not null,resolved_at text,channels_json text not null default '["in_app"]');create index if not exists idx_notify_status on notifications(status,severity,last_seen desc);''')
now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());seen=set()
for p in get():
 issues=json.loads(p.get('issues_json') or '[]');bad=not bool(p.get('healthy')) or bool(issues)
 key='project-health:'+p['slug']
 if bad:
  seen.add(key);severity='critical' if not p.get('running') else 'warning';title='Projeto requer atenção';message=f"{p['slug']}: {', '.join(issues) if issues else p.get('state','estado desconhecido')}"
  c.execute("insert into notifications(dedup_key,project_slug,severity,title,message,status,first_seen,last_seen) values(?,?,?,?,?,'open',?,?) on conflict(dedup_key) do update set severity=excluded.severity,title=excluded.title,message=excluded.message,status='open',last_seen=excluded.last_seen,resolved_at=null",(key,p['slug'],severity,title,message,now,now))
 else:c.execute("update notifications set status='resolved',resolved_at=?,last_seen=? where dedup_key=? and status='open'",(now,now,key))
c.commit();print(json.dumps({'ok':True,'open':c.execute("select count(*) from notifications where status='open'").fetchone()[0],'seen':len(seen)}));c.close()
