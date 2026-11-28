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
        if not namespace or namespace=='approvals':
            _approval_index_schema(con)
            con.execute('delete from approval_index')
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

# T-046: normalized approval index; canonical records stay in the approval service.
APPROVAL_LIVE_STATUSES=('pending','pending_second','approved')

def _approval_index_schema(con):
    con.execute('''create table if not exists approval_index(
      approval_id text primary key,
      project_slug text not null default '',
      status text not null default '',
      created_at real not null default 0,
      payload_json text not null
    )''')
    con.execute('create index if not exists approval_index_slug_status_created on approval_index(project_slug,status,created_at desc)')
    con.execute('create index if not exists approval_index_status_created on approval_index(status,created_at desc)')

def approval_index_replace(rows):
    con=_con()
    try:
        _approval_index_schema(con)
        con.execute('delete from approval_index')
        for row in rows or []:
            aid=str(row.get('approval_id') or '')
            if not aid:continue
            con.execute('insert or replace into approval_index(approval_id,project_slug,status,created_at,payload_json) values(?,?,?,?,?)',
              (aid,str(row.get('project_slug') or ''),str(row.get('status') or ''),float(row.get('created_at') or 0),json.dumps(row,ensure_ascii=False,separators=(',',':'))))
        con.commit()
    finally:con.close()

def approval_index_available():
    con=_con()
    try:
        _approval_index_schema(con)
        return bool(con.execute('select 1 from approval_index limit 1').fetchone())
    finally:con.close()

def _approval_slug_filter(slugs):
    slugs=[str(s) for s in slugs or []]
    if not slugs:return "1=0",[]
    return 'project_slug in ('+','.join('?'*len(slugs))+')',slugs

def approval_index_counts(slugs):
    where,args=_approval_slug_filter(slugs)
    live=APPROVAL_LIVE_STATUSES
    con=_con()
    try:
        _approval_index_schema(con)
        pending=con.execute("select count(*) from approval_index where "+where+" and status in ('pending','pending_second')",args).fetchone()[0]
        approved=con.execute("select count(*) from approval_index where "+where+" and status='approved'",args).fetchone()[0]
        history=con.execute("select count(*) from approval_index where "+where+" and status not in ('pending','pending_second','approved')",args).fetchone()[0]
        return {'pending':pending,'approved':approved,'history':history}
    finally:con.close()

def approval_index_page(slugs,statuses=None,exclude_statuses=None,limit=50,offset=0):
    where,args=_approval_slug_filter(slugs)
    clauses=[where];params=list(args)
    if statuses:
        clauses.append('status in ('+','.join('?'*len(statuses))+')');params.extend(statuses)
    if exclude_statuses:
        clauses.append('status not in ('+','.join('?'*len(exclude_statuses))+')');params.extend(exclude_statuses)
    limit=max(1,min(int(limit or 50),200));offset=max(0,int(offset or 0))
    con=_con()
    try:
        _approval_index_schema(con)
        rows=con.execute('select payload_json from approval_index where '+' and '.join(clauses)+' order by created_at desc,approval_id limit ? offset ?',params+[limit,offset]).fetchall()
        return [json.loads(r[0]) for r in rows]
    finally:con.close()
