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

def trigger_refresh():
    try:
        result=subprocess.run(['/usr/bin/systemctl','--no-block','start','cloudif-portal-refresh-cache.service'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3)
        return result.returncode==0
    except Exception:
        return False
