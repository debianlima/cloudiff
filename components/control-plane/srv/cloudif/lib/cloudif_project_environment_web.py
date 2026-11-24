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

def _env_file_value(path:str,key:str)->str:
    try:
        for raw in Path(path).read_text(encoding='utf-8',errors='strict').splitlines():
            line=raw.strip()
            if not line or line.startswith('#') or '=' not in line:continue
            name,value=line.split('=',1)
            if name.strip()==key:return value.strip().strip('"').strip("'")
    except (OSError,UnicodeError):
        pass
    return ''


CONTROL_DB=Path(os.environ.get('CLOUDIF_PROJECT_SNAPSHOT_DB','/var/lib/cloudif/control-plane/control-plane.db'))
CONFIG_URL=os.environ.get('CLOUDIF_PROJECT_CONFIG_URL','http://127.0.0.1:18219').rstrip('/')
CONFIG_TOKEN=os.environ.get('CLOUDIF_PROJECT_CONFIG_TOKEN','') or _env_file_value('/etc/cloudif/project-config-controller.env','CLOUDIF_PROJECT_CONFIG_TOKEN')
APPROVAL_URL=os.environ.get('CLOUDIF_APPROVAL_URL','http://127.0.0.1:18204').rstrip('/')
APPROVAL_TOKEN=os.environ.get('CLOUDIF_APPROVAL_TOKEN','') or _env_file_value('/etc/cloudif/approval-service.env','CLOUDIF_APPROVAL_TOKEN')
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



def _secret_config(method:str,slug:str,suffix:str='',payload:dict[str,Any]|None=None,query:dict[str,Any]|None=None,timeout:int=45)->tuple[int,dict[str,Any]]:
    path=CONFIG_URL+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/environment/secrets'+suffix
    if query:path+='?'+urllib.parse.urlencode(query)
    return _json_call(method,path,CONFIG_TOKEN,payload,timeout)


def _raise_config_error(data:dict[str,Any],fallback:str)->None:
    error=data.get('error') or {}
    if isinstance(error,dict):raise RuntimeError(str(error.get('message') or error.get('code') or fallback))
    raise RuntimeError(str(error or fallback))


def _human_postgres_database_url(slug:str,environment:str,new_password:str)->str:
    import cloudif_project_publication_config as publication_config
    runtime=publication_config.execution_environment_services(slug,environment);values=runtime.get('valuesByService') or {}
    try:
        api=values.get('api') or {};db_values=values.get('db') or {};current_url=str(api.get('DATABASE_URL') or '')
        split=urllib.parse.urlsplit(current_url);old_password=urllib.parse.unquote(split.password or '')
        user=str(db_values.get('POSTGRES_USER') or '');database=str(db_values.get('POSTGRES_DB') or '')
        if not current_url or not split.hostname or not split.username or not old_password or not user or not database:raise RuntimeError('postgres_password_coupling_ambiguous')
        if urllib.parse.unquote(split.username or '')!=user or split.path.lstrip('/')!=database or old_password!=str(db_values.get('POSTGRES_PASSWORD') or ''):raise RuntimeError('postgres_password_coupling_ambiguous')
        user_part=urllib.parse.quote(urllib.parse.unquote(split.username or ''),safe='');password_part=urllib.parse.quote(str(new_password),safe='')
        host=split.hostname or '';host_part=('['+host+']') if ':' in host and not host.startswith('[') else host
        if split.port:host_part+=f':{split.port}'
        netloc=user_part+':'+password_part+'@'+host_part
        return urllib.parse.urlunsplit((split.scheme,netloc,split.path,split.query,split.fragment))
    finally:
        for service_values in values.values():
            if isinstance(service_values,dict):service_values.clear()
        runtime['valuesByService']={}


def human_save(slug:str,payload:dict[str,Any],username:str,groups:list[str]|set[str])->dict[str,Any]:
    auth=authorization(slug,username,groups)
    if not auth['canWrite']:raise PermissionError('forbidden')
    environment=str(payload.get('environment') or '').strip().lower()
    if environment not in {'preview','homologation','production'}:raise ValueError('invalid_environment')
    import cloudif_portal_publications as publications
    publications.environment_runtime_target(slug,environment)
    try:expected_revision=int(payload.get('expectedRevision',payload.get('expected_revision',-1)))
    except Exception:raise ValueError('invalid_expected_revision')
    public_changes=payload.get('changes') or [];secret_changes=payload.get('secretChanges',payload.get('secret_changes',[])) or []
    if not isinstance(public_changes,list) or not isinstance(secret_changes,list) or len(public_changes)>256 or len(secret_changes)>64:raise ValueError('invalid_environment_changes')
    actor=str(username).strip().casefold()
    code,state=_config('GET',slug,query={'environment':environment,'includeValues':'false'})
    if code!=200 or state.get('ok') is not True:_raise_config_error(state,'environment_state_unavailable')
    revision=int(state.get('revision') or 0)
    if revision!=expected_revision:raise ValueError('environment_revision_mismatch')
    entries=state.get('entries') or [];secret_entries={}
    for item in entries:
        if isinstance(item,dict) and item.get('secret') is True:
            secret_entries[(str(item.get('service') or ''),str(item.get('name') or ''))]=item
    normalized_secrets=[]
    for item in secret_changes:
        if not isinstance(item,dict):raise ValueError('invalid_secret_change')
        service=str(item.get('service') or '');name=str(item.get('name') or '').strip().upper();value=item.get('value')
        if not re.fullmatch(r'[A-Z_][A-Z0-9_]{0,127}',name) or not isinstance(value,str) or not value or '\x00' in value or len(value)>131072:raise ValueError('invalid_secret_change')
        entry=secret_entries.get((service,name))
        if not entry:raise ValueError('secret_not_configured:'+name)
        definition=dict(entry.get('metadata') or {});definition.update({'secret':True,'exposeToClient':False})
        normalized_secrets.append({'service':service,'name':name,'value':value,'definition':definition,'synthetic':False})
    keys={(x['service'],x['name']) for x in normalized_secrets}
    pg_change=next((x for x in normalized_secrets if x['service']=='db' and x['name']=='POSTGRES_PASSWORD'),None)
    if pg_change and ('api','DATABASE_URL') not in keys:
        entry=secret_entries.get(('api','DATABASE_URL'))
        if not entry:raise RuntimeError('postgres_database_url_secret_missing')
        normalized_secrets.append({'service':'api','name':'DATABASE_URL','value':_human_postgres_database_url(slug,environment,pg_change['value']),'definition':dict(entry.get('metadata') or {}),'synthetic':True})
    affected=set();secret_names=[]
    try:
        for item in normalized_secrets:
            value=item['value'];stage_payload={'environment':environment,'service':item['service'],'name':item['name'],'secretValue':value,'actor':actor,'ttlSeconds':900}
            try:code,staged=_secret_config('POST',slug,'/stage',stage_payload,timeout=30)
            finally:stage_payload.pop('secretValue',None);value='';item['value']=''
            if code not in {200,201} or staged.get('ok') is not True:_raise_config_error(staged,'secret_stage_failed')
            stage_id=str(staged.get('stageId') or '')
            code,plan=_secret_config('POST',slug,'/rotate/plan',{'stageId':stage_id,'expectedRevision':revision,'actor':actor,'reason':'Alteração humana autenticada no Portal','definition':item['definition'],'ttlSeconds':900})
            if code!=200 or plan.get('ok') is not True:_raise_config_error(plan,'secret_rotation_plan_failed')
            code,rotated=_secret_config('POST',slug,'/rotate/apply',{'planDigest':plan['planDigest'],'stageId':stage_id,'expectedRevision':revision,'approved':True,'actor':actor},timeout=120)
            if code!=200 or rotated.get('ok') is not True:_raise_config_error(rotated,'secret_rotation_apply_failed')
            revision=int(rotated.get('environmentRevision') or revision+1);affected.add(item['service']);secret_names.append(item['name'])
        public_result={}
        if public_changes:
            code,plan=_config('POST',slug,'/change/plan',{'environment':environment,'expectedRevision':revision,'changes':public_changes,'actor':actor,'ttlSeconds':900})
            if code!=200 or plan.get('ok') is not True:_raise_config_error(plan,'environment_plan_failed')
            code,public_result=_config('POST',slug,'/change/apply',{'planDigest':plan['planDigest'],'expectedRevision':revision,'approved':True,'actor':actor})
            if code!=200 or public_result.get('ok') is not True:_raise_config_error(public_result,'environment_apply_failed')
            revision=int(public_result.get('revision') or revision+1);affected.update(str(x) for x in (public_result.get('affectedServices') or []))
        code,latest=_config('GET',slug,query={'environment':environment,'includeValues':'false'})
        if code!=200 or latest.get('ok') is not True:_raise_config_error(latest,'environment_state_unavailable')
        revision=int(latest.get('revision') or revision);environment_digest=str(latest.get('environmentDigest') or public_result.get('environmentDigest') or '')
        try:runtime=publications.apply_environment_to_runtime(slug,environment,actor)
        except Exception as exc:runtime={'ok':False,'environment':environment,'error':type(exc).__name__,'message':str(exc)[:300],'secretValuesIncluded':False}
        result={'ok':True,'environment':environment,'revision':revision,'environmentDigest':environment_digest,'affectedServices':sorted(affected),'secretNamesChanged':sorted(set(secret_names)),'humanInteractive':True,'approvalRequired':False,'runtimeApply':runtime,'secretValuesIncluded':False}
        result['reconcile']=_enqueue_configuration_reconcile(slug,actor,result)
        try:
            import cloudif_portal_readmodel as readmodel
            readmodel.project_changed(slug,'environment-human-save')
        except Exception:
            pass
        return result
    finally:
        for item in normalized_secrets:
            item['value']=''


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
    return {'ok':True,'approvalId':data['approval_id'],'status':data['status'],'expiresAt':data['expires_at'],'projectSlug':slug,'planDigest':plan_digest,'approvalUrl':'/cloudiff/portal/?tab=aprovacoes','policyApplied':bool(data.get('policy_applied')),'approvalPolicyId':data.get('approval_policy_id'),'secretValuesIncluded':False}


def _enqueue_configuration_reconcile(slug:str,actor:str,result:dict[str,Any])->dict[str,Any]:
    try:
        from cloudif_reconcile_client import enqueue
        return enqueue(
            'project.configuration.changed', actor=actor or 'portal', username=actor or '', project=slug,
            payload={
                'source':'environment_wizard','operation':'environment_change','reason':'environment_changed',
                'environment':str(result.get('environment') or ''),'environment_revision':int(result.get('revision') or 0),
                'environment_digest':str(result.get('environmentDigest') or ''),
                'affected_services':[str(x) for x in (result.get('affectedServices') or [])],
                'required_action':str(result.get('requiredAction') or 'none'),
            }, dedupe_seconds=0,
        )
    except Exception as exc:
        return {'ok':False,'error':type(exc).__name__}


def execute(slug:str,plan_digest:str,approval_id:str,username:str,groups:list[str]|set[str])->dict[str,Any]:
    auth=authorization(slug,username,groups)
    if not auth['canWrite']:raise PermissionError('forbidden')
    if not re.fullmatch(r'[a-f0-9]{64}',plan_digest) or not re.fullmatch(r'apr_[a-f0-9]{20}',approval_id):raise ValueError('invalid_execution_binding')
    plan=_plan(slug,plan_digest)
    target_environment=str(plan.get('targetEnvironment') or plan.get('environment') or '')
    if target_environment in {'preview','homologation','production'}:
        import cloudif_portal_publications as publications
        publications.environment_runtime_target(slug,target_environment)
    approval=_approval_get(approval_id)
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
        data['transaction']={'approvalId':approval_id,'reservationId':reservation_id,'executionId':execution_id,'approvalStatus':'consumed'}
        environment=str(data.get('environment') or plan.get('targetEnvironment') or plan.get('environment') or '')
        try:
            import cloudif_portal_publications as publications
            data['runtimeApply']=publications.apply_environment_to_runtime(slug,environment,str(username).strip().casefold())
        except Exception as exc:
            data['runtimeApply']={'ok':False,'environment':environment,'error':type(exc).__name__,'message':str(exc)[:300],'secretValuesIncluded':False}
        data['reconcile']=_enqueue_configuration_reconcile(slug,str(username).strip().casefold(),data)
        data['secretValuesIncluded']=False
        try:
            import cloudif_portal_readmodel as readmodel
            readmodel.project_changed(slug,'environment-change-executed')
        except Exception:
            pass
        return data
    if current and current.get('status')=='reserved':_approval_transition(approval_id,'release',{'reservation_id':reservation_id})
    raise RuntimeError(str((data.get('error') or {}).get('message') or (data.get('error') or {}).get('code') or 'environment_apply_failed'))


def handle_get(slug:str,operation:str,query:dict[str,str],username:str,groups:list[str]|set[str])->tuple[int,dict[str,Any]]:
    auth=authorization(slug,username,groups)
    if not auth['canRead']:return 403,{'ok':False,'error':{'code':'forbidden','message':'Sem acesso ao projeto.'}}
    suffix='';params={}
    if operation=='history':suffix='/history';params={'limit':query.get('limit','100')}
    elif operation=='missing':suffix='/missing';params={'environment':query.get('environment','')}
    elif operation=='effective':suffix='/effective';params={'environment':query.get('environment','development')}
    elif operation=='export':suffix='/export';params={key:query[key] for key in ('environment','service') if query.get(key)}
    elif operation=='approval/status':
        approval_id=str(query.get('approvalId',query.get('approval_id','')) or '')
        if not re.fullmatch(r'apr_[a-f0-9]{20}',approval_id):return 400,{'ok':False,'error':{'code':'invalid_approval_id'}}
        approval=_approval_get(approval_id)
        if not approval or approval.get('project_slug')!=slug:return 404,{'ok':False,'error':{'code':'approval_not_found'}}
        return 200,{'ok':True,'approvalId':approval_id,'status':approval.get('status'),'expiresAt':approval.get('expires_at'),'approvedBy':approval.get('approved_by'),'secondApprovedBy':approval.get('second_approved_by'),'twoApproversRequired':bool(approval.get('two_approvers_required')),'approvalPolicyId':approval.get('approval_policy_id')}
    else:
        params={key:query[key] for key in ('environment','service') if query.get(key)}
        if query.get('includePublicValues','').lower() in {'1','true','yes','on'}:params['includeValues']='true'
    code,data=_config('GET',slug,suffix,query=params)
    return code,data


def handle_post(slug:str,operation:str,payload:dict[str,Any],username:str,groups:list[str]|set[str])->tuple[int,dict[str,Any]]:
    auth=authorization(slug,username,groups)
    if not auth['canWrite']:return 403,{'ok':False,'error':{'code':'forbidden','message':'A função exige proprietário, maintainer, professor ou administrador.'}}
    actor=str(username).strip().casefold();body=dict(payload);body['actor']=actor
    if operation=='human/save':
        return 200,human_save(slug,body,username,groups)
    if operation=='approval/request':
        result=request_approval(slug,str(body.get('planDigest',body.get('plan_digest',''))),str(body.get('reason') or ''),username,groups,int(body.get('ttlSeconds',body.get('ttl_seconds',900)) or 900));return 201,result
    if operation in {'change/execute','promote/execute'}:
        result=execute(slug,str(body.get('planDigest',body.get('plan_digest',''))),str(body.get('approvalId',body.get('approval_id',''))),username,groups);return 200,result
    mapping={'validate':'/validate','change/plan':'/change/plan','promote/plan':'/promote/plan','import/plan':'/import/plan'}
    if operation not in mapping:return 404,{'ok':False,'error':{'code':'not_found'}}
    code,data=_config('POST',slug,mapping[operation],body)
    return code,data
