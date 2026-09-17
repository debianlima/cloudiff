"""Read-only adapter for anonymized public production access telemetry."""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

ACCESS_DB=os.environ.get('CLOUDIF_ACCESS_INGEST_DB','/var/lib/cloudif/access-ingest/access.db')
PROJECT_DB=os.environ.get('CLOUDIF_PORTAL_DB','/var/lib/cloudif/portal/cloudif-portal.db')
PUBLIC_DOMAIN=os.environ.get('CLOUDIF_PUBLIC_HOST','cloudiff.duckdns.org').strip().lower()


def _ro(path:str):
    c=sqlite3.connect('file:'+path+'?mode=ro',uri=True,timeout=8);c.row_factory=sqlite3.Row;return c


def _publication_hosts(slug:str)->list[str]:
    try:c=_ro(PROJECT_DB)
    except Exception:return []
    try:
        aliases=[str(r['alias']).strip().lower()+'.'+PUBLIC_DOMAIN for r in c.execute('select alias from project_publication_aliases where project_slug=? order by alias',(slug,)) if str(r['alias'] or '').strip()]
        row=c.execute("select stable_hostname,public_number from project_publications where project_slug=? and is_active=1 and lower(status)='published' order by id desc limit 1",(slug,)).fetchone()
        stable=''
        if row:
            stable=str(row['stable_hostname'] or '').strip().lower()
            if not stable and row['public_number']:stable=str(int(row['public_number']))+'.'+PUBLIC_DOMAIN
        if not stable:
            pid=c.execute('select public_number from project_public_ids where project_slug=?',(slug,)).fetchone()
            if pid and pid['public_number']:stable=str(int(pid['public_number']))+'.'+PUBLIC_DOMAIN
        out=[]
        for host in aliases+([stable] if stable else []):
            if host and host not in out:out.append(host)
        return out
    except Exception:return []
    finally:c.close()


def _latest_snapshot()->dict[str,Any] | None:
    try:c=_ro(ACCESS_DB)
    except Exception:return None
    try:r=c.execute('select received_at,source_host,window_days,hosts_json from snapshots order by id desc limit 1').fetchone()
    except Exception:r=None
    finally:c.close()
    if not r:return None
    try:hosts=json.loads(r['hosts_json'] or '[]')
    except Exception:hosts=[]
    return {'received_at':str(r['received_at'] or ''),'source_host':str(r['source_host'] or ''),'window_days':int(r['window_days'] or 0),'hosts':hosts if isinstance(hosts,list) else []}


def project_production_access(slug:str)->dict[str,Any]:
    slug=str(slug or '').strip()
    hosts=_publication_hosts(slug) if slug else []
    snapshot=_latest_snapshot()
    if not slug or not hosts:
        return {'ok':False,'instrumented':bool(snapshot),'published':False,'hosts':hosts,'error':'publication_not_mapped'}
    if not snapshot:
        return {'ok':False,'instrumented':False,'published':True,'hosts':hosts,'error':'access_snapshot_unavailable'}
    by_host={str(item.get('host') or '').strip().lower():item for item in snapshot['hosts'] if isinstance(item,dict)}
    rows=[by_host[h] for h in hosts if h in by_host]
    split_available=bool(snapshot['hosts']) and all('public_requests' in item for item in snapshot['hosts'][:10] if isinstance(item,dict))
    public_requests=sum(int(item.get('public_requests') or 0) for item in rows) if split_available else None
    internal_requests=sum(int(item.get('internal_requests') or 0) for item in rows) if split_available else None
    # Per-host visitor hashes cannot be deduplicated across aliases; max avoids double counting the same visitor across entrypoints.
    public_visitors=max([int(item.get('public_unique_visitors') or 0) for item in rows],default=0) if split_available else None
    return {
        'ok':True,
        'instrumented':True,
        'published':True,
        'slug':slug,
        'primary_host':hosts[0],
        'hosts':hosts,
        'matched_hosts':[str(item.get('host') or '') for item in rows],
        'window_days':int(snapshot.get('window_days') or 0),
        'snapshot_received_at':snapshot.get('received_at') or '',
        'split_available':split_available,
        'requests':sum(int(item.get('requests') or 0) for item in rows),
        'public_requests':public_requests,
        'internal_requests':internal_requests,
        'public_unique_visitors':public_visitors,
        'errors':sum(int(item.get('public_errors') or 0) for item in rows) if split_available else sum(int(item.get('errors') or 0) for item in rows),
        'last_seen':max([str(item.get('last_seen') or '') for item in rows],default=''),
    }
