#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from cloudif_project_environment_web import authorization, handle_get as environment_get
from cloudif_project_runtime_reconcile_web import handle_get as runtime_get

PORTAL_DB=Path('/var/lib/cloudif/portal/cloudif-portal.db')
PREVIEW_DB=Path('/var/lib/cloudif/preview-broker/previews.sqlite3')
ENVIRONMENTS=('preview','homologation','production')


def _config(slug:str,environment:str,username:str,groups:list[str]|set[str])->dict[str,Any]:
    try:
        code,data=environment_get(slug,'effective',{'environment':environment},username,groups)
        if code==200 and data.get('ok'):
            missing=data.get('missingRequired') or []
            return {
                'revision':int(data.get('environmentRevision') or 0),
                'configurationRevision':int(data.get('configurationRevision') or 0),
                'digest':str(data.get('environmentDigest') or ''),
                'valid':bool(data.get('valid')),
                'missingRequired':len(missing),
            }
    except Exception:
        pass
    return {'revision':0,'configurationRevision':0,'digest':'','valid':False,'missingRequired':0}


def _runtime(slug:str,environment:str,username:str,groups:list[str]|set[str])->dict[str,Any]:
    if environment not in {'homologation','production'}:return {}
    try:
        code,data=runtime_get(slug,'status',{'environment':environment},username,groups)
        states=data.get('states') or [] if code==200 and isinstance(data,dict) else []
        if states:
            state=dict(states[0])
            return {
                'status':str(state.get('status') or 'unknown'),
                'deploymentId':str(state.get('deploymentId') or ''),
                'buildJobId':str(state.get('buildJobId') or ''),
                'configRevision':int(state.get('configRevision') or 0),
                'environmentDigest':str(state.get('environmentDigest') or ''),
                'updatedAt':int(state.get('updatedAt') or 0),
            }
    except Exception:
        pass
    return {}


def _preview(slug:str)->dict[str,Any]:
    if not PREVIEW_DB.exists():return {}
    try:
        con=sqlite3.connect(f'file:{PREVIEW_DB}?mode=ro',uri=True,timeout=10);con.row_factory=sqlite3.Row
        row=con.execute("select id,build_id,commit_ref,status,created_at,expires_at,url,result_json from previews where project_slug=? and status in ('active','validated') order by created_at desc limit 1",(slug,)).fetchone();con.close()
        if not row:return {}
        now=int(time.time());status=str(row['status'] or '')
        if int(row['expires_at'] or 0) and int(row['expires_at'])<=now:status='expired'
        return {
            'status':status,'previewId':str(row['id'] or ''),'buildJobId':str(row['build_id'] or ''),
            'commit':str(row['commit_ref'] or ''),'createdAt':int(row['created_at'] or 0),'expiresAt':int(row['expires_at'] or 0),
            'url':('/cloudiff/portal/preview/'+str(row['id'])+'/' if status=='active' and row['id'] else ''),
        }
    except Exception:
        return {}


def _production(slug:str)->dict[str,Any]:
    if not PORTAL_DB.exists():return {}
    try:
        con=sqlite3.connect(f'file:{PORTAL_DB}?mode=ro',uri=True,timeout=10);con.row_factory=sqlite3.Row
        row=con.execute("select public_number,deploy_number,commit_sha,stable_hostname,version_hostname,published_at from project_publications where project_slug=? and status='published' and is_active=1 order by id desc limit 1",(slug,)).fetchone()
        alias=con.execute('select alias from project_publication_aliases where project_slug=?',(slug,)).fetchone();con.close()
        if not row:return {}
        host=(str(alias['alias'])+'.cloudiff.duckdns.org') if alias and alias['alias'] else str(row['stable_hostname'] or '')
        return {
            'status':'published','deployNumber':int(row['deploy_number'] or 0),'commit':str(row['commit_sha'] or ''),
            'url':('https://'+host+'/' if host else ''),'versionUrl':('https://'+str(row['version_hostname'])+'/' if row['version_hostname'] else ''),
            'publishedAt':str(row['published_at'] or ''),
        }
    except Exception:
        return {}


def overview(slug:str,username:str,groups:list[str]|set[str])->dict[str,Any]:
    auth=authorization(slug,username,groups)
    if not auth.get('canRead'):raise PermissionError('forbidden')
    preview=_preview(slug);production=_production(slug)
    environments=[]
    for environment in ENVIRONMENTS:
        config=_config(slug,environment,username,groups)
        runtime=_runtime(slug,environment,username,groups)
        data:dict[str,Any]={'name':environment,'configuration':config,'runtime':runtime,'url':'','artifact':'','status':'not_created'}
        if environment=='preview':
            data.update({'status':preview.get('status') or 'not_created','url':preview.get('url') or '', 'artifact':preview.get('commit') or preview.get('buildJobId') or '', 'expiresAt':int(preview.get('expiresAt') or 0),'previewId':preview.get('previewId') or ''})
        elif environment=='homologation':
            data.update({'status':runtime.get('status') or 'not_deployed','artifact':runtime.get('buildJobId') or ''})
        else:
            status=production.get('status') or runtime.get('status') or 'not_published'
            artifact=production.get('commit') or runtime.get('buildJobId') or ''
            data.update({'status':status,'url':production.get('url') or '', 'artifact':artifact,'deployNumber':int(production.get('deployNumber') or 0),'versionUrl':production.get('versionUrl') or ''})
        environments.append(data)
    return {
        'ok':True,'projectSlug':slug,'canWrite':bool(auth.get('canWrite')),'environments':environments,
        'effectsExecuted':False,'secretValuesIncluded':False,'secretReferencesIncluded':False,
    }


def handle_get(slug:str,username:str,groups:list[str]|set[str])->tuple[int,dict[str,Any]]:
    try:return 200,overview(slug,username,groups)
    except PermissionError:return 403,{'ok':False,'error':{'code':'forbidden','message':'Sem acesso ao projeto.'},'effectsExecuted':False,'secretValuesIncluded':False}
    except LookupError:return 404,{'ok':False,'error':{'code':'project_not_found'},'effectsExecuted':False,'secretValuesIncluded':False}
    except Exception as exc:return 503,{'ok':False,'error':{'code':'environment_overview_unavailable','detail':type(exc).__name__},'effectsExecuted':False,'secretValuesIncluded':False}
