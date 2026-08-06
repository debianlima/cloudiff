#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CONTROL_DB=Path(os.environ.get('CLOUDIF_PROJECT_SNAPSHOT_DB','/var/lib/cloudif/control-plane/control-plane.db'))
CONFIG_URL=os.environ.get('CLOUDIF_PROJECT_CONFIG_URL','http://127.0.0.1:18219').rstrip('/')
CONFIG_TOKEN=os.environ.get('CLOUDIF_PROJECT_CONFIG_TOKEN','')
APPROVAL_URL=os.environ.get('CLOUDIF_APPROVAL_URL','http://127.0.0.1:18204').rstrip('/')
APPROVAL_TOKEN=os.environ.get('CLOUDIF_APPROVAL_TOKEN','')
ROLE_RANK={'none':0,'viewer':10,'member':40,'developer':60,'editor':65,'maintainer':80,'admin':90,'administrator':90,'owner':100}
GLOBAL_GROUPS={'cloudif-tenants-admin','cloudif-professor'}


def _json_call(method:str,url:str,token:str,payload:dict[str,Any]|None=None,timeout:int=45)->tuple[int,dict[str,Any]]:
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode() if payload is not None else None
    request=urllib.request.Request(url,data=raw,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/json','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={'ok':False,'error':{'code':'upstream_error','message':'Serviço interno indisponível.'}}
        return error.code,data


def _control_project(slug:str)->tuple[dict[str,Any],list[dict[str,Any]]]:
    connection=sqlite3.connect(f'file:{CONTROL_DB}?mode=ro',uri=True,timeout=20);connection.row_factory=sqlite3.Row
    project=connection.execute('select project_id,slug,name,owner,tenant,status from projects where slug=?',(slug,)).fetchone()
    if not project:connection.close();raise LookupError('project_not_found')
    acl=[dict(row) for row in connection.execute('select subject_type,subject,role from project_acl where project_id=?',(project['project_id'],)).fetchall()]
    connection.close();return dict(project),acl


def authorization(slug:str,username:str,groups:list[str]|set[str])->dict[str,Any]:
    project,acl=_control_project(slug);user=str(username or '').strip().casefold();group_set={str(item).strip().casefold() for item in groups if str(item).strip()}
    role='none';reason='no_access'
    if group_set.intersection(GLOBAL_GROUPS):role='administrator';reason='global_group'
    elif user==str(project.get('owner') or '').strip().casefold():role='owner';reason='owner'
    else:
        for item in acl:
            kind=str(item.get('subject_type') or '').casefold();subject=str(item.get('subject') or '').strip().casefold();candidate=str(item.get('role') or 'viewer').casefold()
            matched=(kind=='user' and subject==user) or (kind=='group' and subject in group_set)
            if matched and ROLE_RANK.get(candidate,0)>ROLE_RANK.get(role,0):role=candidate;reason='acl'
    return {'project':project,'role':role,'rank':ROLE_RANK.get(role,0),'canRead':ROLE_RANK.get(role,0)>=10,'canWrite':ROLE_RANK.get(role,0)>=60,'reason':reason}


def _config_path(slug:str,suffix:str='',query:dict[str,Any]|None=None)->str:
    path=CONFIG_URL+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/environment'+suffix
    if query:path+='?'+urllib.parse.urlencode(query)
    return path


def _config(method:str,slug:str,suffix:str='',payload:dict[str,Any]|None=None,query:dict[str,Any]|None=None)->tuple[int,dict[str,Any]]:
    return _json_call(method,_config_path(slug,suffix,query),CONFIG_TOKEN,payload)


def _approval_get(approval_id:str)->dict[str,Any]|None:
    code,data=_json_call('GET',APPROVAL_URL+'/v1/approvals?status=all',APPROVAL_TOKEN)
    if code!=200:return None
    return next((item for item in data.get('approvals') or [] if item.get('approval_id')==approval_id),None)


def _approval_transition(approval_id:str,operation:str,payload:dict[str,Any])->tuple[int,dict[str,Any]]:
    return _json_call('POST',APPROVAL_URL+'/v1/approvals/'+urllib.parse.quote(approval_id,safe='')+'/'+operation,APPROVAL_TOKEN,payload)


def _plan(slug:str,plan_digest:str)->dict[str,Any]:
    code,data=_config('GET',slug,'/plans/'+urllib.parse.quote(plan_digest,safe=''))
    if code!=200 or not data.get('ok'):raise LookupError('environment_plan_not_found')
    return data


def _transaction_ids(action:str,approval_id:str,actor:str,digest:str)->tuple[str,str]:
    raw=json.dumps({'action':action,'approval_id':approval_id,'actor':actor,'digest':digest},sort_keys=True,separators=(',',':')).encode();value=hashlib.sha256(raw).hexdigest()
    return 'res_'+value[:32],'exec_'+value[32:64]


def request_approval(slug:str,plan_digest:str,reason:str,username:str,groups:list[str]|set[str],ttl_seconds:int=900)->dict[str,Any]:
    auth=authorization(slug,username,groups)
    if not auth['canWrite']:raise PermissionError('forbidden')
    plan=_plan(slug,plan_digest)
    if plan.get('consumed') or int(plan.get('expiresAt') or 0)<=int(time.time()):raise RuntimeError('environment_plan_unavailable')
    action='project.environment.promotion' if plan.get('action')=='promotion' else 'project.environment.change'
    requested_by='portal:'+str(username).strip().casefold()
    metadata={
      'environment_plan_digest':plan['planDigest'],'environment_action':plan['action'],
      'source_environment':plan.get('sourceEnvironment'),'target_environment':plan.get('targetEnvironment'),
      'expected_revision':plan['expectedRevision'],'summary':plan.get('summary') or {},
      'content_stored':False,'secret_values_in_metadata':False,
    }
    payload={'project_slug':slug,'action':action,'requested_by':requested_by,'requester_role':auth['role'],'ttl_seconds':max(60,min(int(ttl_seconds),86400)),'reason':str(reason)[:500],'trace_id':'portal-environment-'+hashlib.sha256((slug+plan_digest).encode()).hexdigest()[:20],'metadata':metadata}
    code,data=_json_call('POST',APPROVAL_URL+'/v1/approvals',APPROVAL_TOKEN,payload)
    if code not in {200,201} or not data.get('ok'):raise RuntimeError(str((data.get('error') or {}).get('message') or 'approval_create_failed'))
    return {'ok':True,'approvalId':data['approval_id'],'status':data['status'],'expiresAt':data['expires_at'],'projectSlug':slug,'planDigest':plan_digest,'approvalUrl':'/cloudiff/portal/?tab=aprovacoes','secretValuesIncluded':False}


def execute(slug:str,plan_digest:str,approval_id:str,username:str,groups:list[str]|set[str])->dict[str,Any]:
    auth=authorization(slug,username,groups)
    if not auth['canWrite']:raise PermissionError('forbidden')
    if not re.fullmatch(r'[a-f0-9]{64}',plan_digest) or not re.fullmatch(r'apr_[a-f0-9]{20}',approval_id):raise ValueError('invalid_execution_binding')
    plan=_plan(slug,plan_digest);approval=_approval_get(approval_id)
    if not approval:raise LookupError('approval_not_found')
    try:metadata=json.loads(approval.get('metadata_json') or '{}')
    except Exception:raise ValueError('approval_metadata_invalid')
    action='project.environment.promotion' if plan.get('action')=='promotion' else 'project.environment.change';requested_by='portal:'+str(username).strip().casefold()
    reservation_id,execution_id=_transaction_ids(action,approval_id,requested_by,plan_digest)
    valid_status=approval.get('status')=='approved' or (approval.get('status') in {'reserved','consumed'} and approval.get('reservation_id')==reservation_id)
    valid=bool(valid_status and approval.get('project_slug')==slug and approval.get('action')==action and approval.get('requested_by')==requested_by and approval.get('approved_by') and hmac.compare_digest(str(metadata.get('environment_plan_digest') or ''),plan_digest) and metadata.get('environment_action')==plan.get('action') and int(metadata.get('expected_revision') or 0)==int(plan.get('expectedRevision') or 0) and metadata.get('source_environment')==plan.get('sourceEnvironment') and metadata.get('target_environment')==plan.get('targetEnvironment') and metadata.get('content_stored') is False and metadata.get('secret_values_in_metadata') is False)
    if not valid:raise PermissionError('approval_binding_mismatch')
    if approval.get('status')=='approved':
        code,reserved=_approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':requested_by,'ttl_seconds':900})
        if code!=200 or reserved.get('status')!='reserved':raise RuntimeError('approval_reserve_failed')
    suffix='/promote/apply' if plan.get('action')=='promotion' else '/change/apply'
    code,data=_config('POST',slug,suffix,{'planDigest':plan_digest,'expectedRevision':plan['expectedRevision'],'approved':True,'actor':str(username).strip().casefold(),'executionId':execution_id})
    current=_approval_get(approval_id)
    if code==200 and data.get('ok'):
        if current and current.get('status')!='consumed':
            final_code,finalized=_approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
            if final_code!=200 or finalized.get('status')!='consumed':raise RuntimeError('approval_finalize_failed')
        data['transaction']={'approvalId':approval_id,'reservationId':reservation_id,'executionId':execution_id,'approvalStatus':'consumed'};data['secretValuesIncluded']=False;return data
    if current and current.get('status')=='reserved':_approval_transition(approval_id,'release',{'reservation_id':reservation_id})
    raise RuntimeError(str((data.get('error') or {}).get('message') or (data.get('error') or {}).get('code') or 'environment_apply_failed'))


def handle_get(slug:str,operation:str,query:dict[str,str],username:str,groups:list[str]|set[str])->tuple[int,dict[str,Any]]:
    auth=authorization(slug,username,groups)
    if not auth['canRead']:return 403,{'ok':False,'error':{'code':'forbidden','message':'Sem acesso ao projeto.'}}
    suffix='';params={}
    if operation=='history':suffix='/history';params={'limit':query.get('limit','100')}
    elif operation=='missing':suffix='/missing';params={'environment':query.get('environment','')}
    else:
        params={key:query[key] for key in ('environment','service') if query.get(key)}
        if query.get('includePublicValues','').lower() in {'1','true','yes','on'}:params['includeValues']='true'
    code,data=_config('GET',slug,suffix,query=params)
    return code,data


def handle_post(slug:str,operation:str,payload:dict[str,Any],username:str,groups:list[str]|set[str])->tuple[int,dict[str,Any]]:
    auth=authorization(slug,username,groups)
    if not auth['canWrite']:return 403,{'ok':False,'error':{'code':'forbidden','message':'A função exige proprietário, maintainer, professor ou administrador.'}}
    actor=str(username).strip().casefold();body=dict(payload);body['actor']=actor
    if operation=='approval/request':
        result=request_approval(slug,str(body.get('planDigest',body.get('plan_digest',''))),str(body.get('reason') or ''),username,groups,int(body.get('ttlSeconds',body.get('ttl_seconds',900)) or 900));return 201,result
    if operation in {'change/execute','promote/execute'}:
        result=execute(slug,str(body.get('planDigest',body.get('plan_digest',''))),str(body.get('approvalId',body.get('approval_id',''))),username,groups);return 200,result
    mapping={'validate':'/validate','change/plan':'/change/plan','promote/plan':'/promote/plan'}
    if operation not in mapping:return 404,{'ok':False,'error':{'code':'not_found'}}
    code,data=_config('POST',slug,mapping[operation],body)
    return code,data
