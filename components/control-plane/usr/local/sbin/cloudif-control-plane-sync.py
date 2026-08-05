#!/usr/bin/env python3
import sqlite3, json, os, tempfile, time
SRC='/var/lib/cloudif/portal/cloudif-portal.db'
DST='/var/lib/cloudif/control-plane/control-plane.db'
os.makedirs(os.path.dirname(DST),exist_ok=True)
src=sqlite3.connect(f'file:{SRC}?mode=ro',uri=True,timeout=10); src.row_factory=sqlite3.Row
projects={r['slug']:dict(r) for r in src.execute('select * from projects')}
ints={r['project']:dict(r) for r in src.execute('select * from project_integrations')}
tenant_acl={}
for r in src.execute("select tenant,subject_type,subject from tenant_acl"):
    tenant_acl.setdefault(r['tenant'],[]).append({'type':r['subject_type'],'subject':r['subject']})
project_acl={}
for r in src.execute("select slug,subject_type,subject from project_acl"):
    project_acl.setdefault(r['slug'],[]).append({'type':r['subject_type'],'subject':r['subject']})
fd,tmp=tempfile.mkstemp(prefix='control-plane-',suffix='.db',dir=os.path.dirname(DST)); os.close(fd)
try:
    db=sqlite3.connect(tmp)
    db.executescript('''
    pragma journal_mode=delete;
    create table registry_meta(key text primary key,value text not null);
    create table projects(project_id text primary key,slug text unique not null,name text,tenant text,owner text,status text,repo_url text,stack_id text,stack_name text,forgejo_status text,supabase_status text,komodo_status text,updated_at text);
    create table project_connectors(project_id text not null,connector text not null,enabled integer not null,status text,config_json text not null default '{}',primary key(project_id,connector));
    create table project_acl(project_id text not null,subject_type text not null,subject text not null,role text not null default 'viewer',primary key(project_id,subject_type,subject));
    ''')
    now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    db.execute('insert into registry_meta values(?,?)',('synced_at',now))
    for slug,p in projects.items():
        i=ints.get(slug,{})
        pid='prj_'+__import__('hashlib').sha256(slug.encode()).hexdigest()[:20]
        repo=i.get('forgejo_repo_url') or i.get('repo_url') or p.get('repo_url') or ''
        stack_id=i.get('komodo_stack_id') or i.get('stack_id') or ''
        stack_name=i.get('komodo_stack_name') or i.get('stack_name') or p.get('stack_name') or ''
        db.execute('insert into projects values(?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,slug,p.get('name') or slug,p.get('tenant') or p.get('tenant_default') or '',p.get('owner') or '',p.get('status') or 'unknown',repo,stack_id,stack_name,i.get('forgejo_status') or ('configured' if repo else 'missing'),i.get('supabase_status') or 'unknown',i.get('komodo_status') or p.get('komodo_status') or 'unknown',now))
        for connector,enabled,status in [('forgejo',bool(repo),i.get('forgejo_status') or ('configured' if repo else 'missing')),('supabase',True,i.get('supabase_status') or 'unknown'),('publication',bool(stack_id),i.get('komodo_status') or 'unknown'),('ai',False,'disabled')]:
            db.execute('insert into project_connectors values(?,?,?,?,?)',(pid,connector,1 if enabled else 0,status,'{}'))
        subjects=list(project_acl.get(slug,[]))+list(tenant_acl.get(p.get('tenant') or '',[]))
        if p.get('owner'): subjects.append({'type':'user','subject':p['owner']})
        seen=set()
        for a in subjects:
            key=(a['type'],a['subject'])
            if key in seen: continue
            seen.add(key)
            db.execute('insert into project_acl values(?,?,?,?)',(pid,a['type'],a['subject'],'owner' if a['subject']==p.get('owner') else 'viewer'))
    db.commit(); assert db.execute('pragma integrity_check').fetchone()[0]=='ok'; db.close()
    os.chmod(tmp,0o640); os.replace(tmp,DST)
    try:
        import pwd, grp
        os.chown(DST,pwd.getpwnam('cloudif-control').pw_uid,grp.getgrnam('cloudif-control').gr_gid)
    except KeyError:
        pass
finally:
    src.close()
    if os.path.exists(tmp): os.unlink(tmp)
print(json.dumps({'ok':True,'projects':len(projects),'destination':DST}))
