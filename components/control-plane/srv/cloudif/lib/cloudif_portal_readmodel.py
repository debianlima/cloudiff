#!/usr/bin/env python3
import json,sqlite3,time,subprocess
DB='/var/lib/cloudif/portal/cloudif-portal-readmodel.db'

def _con():
    con=sqlite3.connect(DB,timeout=30)
    con.execute('pragma busy_timeout=30000')
    con.execute('''create table if not exists portal_readmodel_cache(
      namespace text not null,
      cache_key text not null,
      payload_json text not null,
      source_version text not null default '',
      updated_at real not null,
      primary key(namespace,cache_key)
    )''')
    con.execute('''create table if not exists portal_readmodel_events(
      id integer primary key autoincrement,
      event_type text not null,
      project_slug text not null default '',
      namespaces_json text not null default '[]',
      detail_json text not null default '{}',
      created_at real not null
    )''')
    con.execute('''create table if not exists portal_readmodel_audit_runs(
      id integer primary key autoincrement,
      started_at text not null,
      finished_at text not null,
      status text not null,
      project_count integer not null default 0,
      issue_count integer not null default 0,
      report_json text not null default '{}'
    )''')
    return con

def get(namespace,key,ttl_seconds):
    now=time.time();con=_con()
    try:r=con.execute('select payload_json,updated_at from portal_readmodel_cache where namespace=? and cache_key=?',(str(namespace),str(key))).fetchone()
    finally:con.close()
    if not r or now-float(r[1] or 0)>float(ttl_seconds):return None
    try:return json.loads(r[0])
    except Exception:return None

def put(namespace,key,payload,source_version=''):
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':'));now=time.time();con=_con()
    try:
        con.execute('insert into portal_readmodel_cache(namespace,cache_key,payload_json,source_version,updated_at) values(?,?,?,?,?) on conflict(namespace,cache_key) do update set payload_json=excluded.payload_json,source_version=excluded.source_version,updated_at=excluded.updated_at',(str(namespace),str(key),raw,str(source_version or ''),now));con.commit()
    finally:con.close()
    return payload

def invalidate(namespace='',key=''):
    con=_con()
    try:
        if namespace and key:con.execute('delete from portal_readmodel_cache where namespace=? and cache_key=?',(str(namespace),str(key)))
        elif namespace:con.execute('delete from portal_readmodel_cache where namespace=?',(str(namespace),))
        else:con.execute('delete from portal_readmodel_cache')
        con.commit()
    finally:con.close()

def cached(namespace,key,ttl_seconds,loader,source_version=''):
    value=get(namespace,key,ttl_seconds)
    if value is not None:return value
    return put(namespace,key,loader(),source_version)

def get_stale(namespace,key,max_age_seconds=3600):
    now=time.time();con=_con()
    try:r=con.execute('select payload_json,updated_at from portal_readmodel_cache where namespace=? and cache_key=?',(str(namespace),str(key))).fetchone()
    finally:con.close()
    if not r or now-float(r[1] or 0)>float(max_age_seconds):return None
    try:return json.loads(r[0])
    except Exception:return None

def stale_while_revalidate(namespace,key,ttl_seconds,max_stale_seconds,loader,source_version=''):
    value=get(namespace,key,ttl_seconds)
    if value is not None:return value
    stale=get_stale(namespace,key,max_stale_seconds)
    if stale is not None:
        trigger_refresh();return stale
    return put(namespace,key,loader(),source_version)

def invalidate_prefix(namespace,prefix):
    con=_con()
    try:
        con.execute('delete from portal_readmodel_cache where namespace=? and cache_key like ?',(str(namespace),str(prefix)+'%'));con.commit()
    finally:con.close()

def record_event(event_type,project_slug='',namespaces=(),detail=None):
    con=_con();now=time.time()
    try:
        con.execute('insert into portal_readmodel_events(event_type,project_slug,namespaces_json,detail_json,created_at) values(?,?,?,?,?)',(str(event_type),str(project_slug or ''),json.dumps(list(namespaces or []),ensure_ascii=False,separators=(',',':')),json.dumps(detail or {},ensure_ascii=False,separators=(',',':')),now))
        con.execute('delete from portal_readmodel_events where id not in (select id from portal_readmodel_events order by id desc limit 10000)')
        con.commit()
    finally:con.close()

def project_changed(slug,reason='mutation',include_projects=False,include_connectors=False):
    slug=str(slug or '').strip();namespaces=['publication-project-context','project-runtime-state','project-runtime-job','project-job-state']
    if slug:
        invalidate_prefix('publication-project-context',slug+'|')
        for namespace in ('project-runtime-state','project-runtime-job','project-job-state'):invalidate(namespace,slug)
    if include_projects:
        invalidate('projects');namespaces.append('projects')
    if include_connectors:
        invalidate('connectors');namespaces.append('connectors')
    record_event(reason,slug,namespaces)
    trigger_refresh();return True

def trigger_refresh():
    try:
        result=subprocess.run(['/usr/bin/systemctl','--no-block','start','cloudif-portal-refresh-cache.service'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3)
        return result.returncode==0
    except Exception:
        return False
