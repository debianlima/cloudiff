#!/usr/bin/env python3
from __future__ import annotations

import hmac
import importlib.util
import json
import os
import re
import urllib.parse
from typing import Any

try:
    from cloudif_project_environment_web import (
        APPROVAL_TOKEN, APPROVAL_URL, _approval_get, _approval_transition,
        _env_file_value, _json_call, _transaction_ids, authorization,
    )
except ModuleNotFoundError:
    _environment_path=__import__('pathlib').Path(__file__).with_name('cloudif_project_environment_web.py')
    _environment_spec=importlib.util.spec_from_file_location('cloudif_project_environment_web',_environment_path)
    _environment_module=importlib.util.module_from_spec(_environment_spec)
    assert _environment_spec.loader
    _environment_spec.loader.exec_module(_environment_module)
    APPROVAL_TOKEN=_environment_module.APPROVAL_TOKEN;APPROVAL_URL=_environment_module.APPROVAL_URL
    _approval_get=_environment_module._approval_get;_approval_transition=_environment_module._approval_transition
    _env_file_value=_environment_module._env_file_value;_json_call=_environment_module._json_call
    _transaction_ids=_environment_module._transaction_ids;authorization=_environment_module.authorization

BUILD_URL=os.environ.get('CLOUDIF_BUILD_BROKER_URL','http://127.0.0.1:18213').rstrip('/')
BUILD_TOKEN=os.environ.get('CLOUDIF_BUILD_BROKER_TOKEN','') or _env_file_value('/etc/cloudif/build-broker.env','CLOUDIF_BUILD_BROKER_TOKEN')


def _build(method:str,path:str,payload:dict[str,Any]|None=None,timeout:int=180)->tuple[int,dict[str,Any]]:
    return _json_call(method,BUILD_URL+path,BUILD_TOKEN,payload,timeout)


def _require_write(slug:str,username:str,groups:list[str]|set[str])->dict[str,Any]:
    auth=authorization(slug,username,groups)
    if not auth['canWrite']:raise PermissionError('forbidden')
    return auth


def _plan(slug:str,ref:str,expected_revision:int,validate:bool=False)->dict[str,Any]:
    path='/v1/toolchain/validate' if validate else '/v1/toolchain/plan'
    code,data=_build('POST',path,{'project_slug':slug,'ref':ref,'expected_revision':int(expected_revision),'trace_id':'portal-toolchain'},900 if validate else 180)
    if code!=200 or not data.get('ok'):
        error=data.get('error') or {};raise RuntimeError(str(error.get('message') if isinstance(error,dict) else error or 'toolchain_plan_failed'))
    return data


def _activation_plan(slug:str,environment:str,job_id:str,expected_revision:int)->dict[str,Any]:
    code,data=_build('POST','/v1/toolchain/activation/plan',{'project_slug':slug,'environment':environment,'job_id':job_id,'expected_revision':int(expected_revision),'trace_id':'portal-toolchain-activation'},180)
    if code!=200 or not data.get('ok'):
        error=data.get('error') or {};raise RuntimeError(str(error.get('message') if isinstance(error,dict) else error or 'toolchain_activation_plan_failed'))
    return data


def _create_approval(slug:str,action:str,plan:dict[str,Any],reason:str,username:str,groups:list[str]|set[str],ttl_seconds:int)->dict[str,Any]:
    auth=_require_write(slug,username,groups);requested_by='portal:'+str(username).strip().casefold()
    if action=='project.toolchain.build':
        metadata={
          'toolchain_plan_digest':plan.get('plan_digest'),'config_revision':plan.get('config_revision'),
          'config_digest':plan.get('config_digest'),'requested_toolchain_digest':plan.get('requested_toolchain_digest'),
          'archive_sha256':plan.get('archive_sha256'),'ref':plan.get('ref'),
          'services':[{'service':item.get('service'),'toolchainDigest':item.get('toolchainDigest')} for item in plan.get('services') or []],
          'summary':plan.get('summary') or {},'content_stored':False,'secret_values_in_metadata':False,
        }
    else:
        metadata={
          'activation_plan_digest':plan.get('plan_digest'),'environment':plan.get('environment'),
          'job_id':plan.get('job_id'),'expected_revision':plan.get('expected_revision'),
          'after':plan.get('after') or [],'content_stored':False,'secret_values_in_metadata':False,
        }
    payload={'project_slug':slug,'action':action,'requested_by':requested_by,'requester_role':auth['role'],'ttl_seconds':max(60,min(int(ttl_seconds),86400)),'reason':str(reason)[:500],'trace_id':'portal-toolchain-'+plan.get('plan_digest','')[:20],'metadata':metadata}
    code,data=_json_call('POST',APPROVAL_URL+'/v1/approvals',APPROVAL_TOKEN,payload)
    if code not in {200,201} or not data.get('ok'):raise RuntimeError(str((data.get('error') or {}).get('message') or 'approval_create_failed'))
    return {'ok':True,'approvalId':data['approval_id'],'status':data['status'],'expiresAt':data['expires_at'],'projectSlug':slug,'action':action,'planDigest':plan.get('plan_digest'),'approvalUrl':'/cloudiff/portal/?tab=aprovacoes','contentStoredInApproval':False,'secretValuesInMetadata':False}


def request_build_approval(slug:str,payload:dict[str,Any],username:str,groups:list[str]|set[str])->dict[str,Any]:
    _require_write(slug,username,groups);ref=str(payload.get('ref') or 'main');expected=int(payload.get('expectedRevision',payload.get('expected_revision',0)) or 0);provided=str(payload.get('planDigest',payload.get('plan_digest',''))).lower();reason=str(payload.get('reason') or '')
    if expected<1 or not re.fullmatch(r'[a-f0-9]{64}',provided) or len(reason)<4:raise ValueError('invalid_build_approval_request')
    plan=_plan(slug,ref,expected,True)
    if plan.get('blocked') or not plan.get('valid') or not hmac.compare_digest(str(plan.get('plan_digest') or ''),provided):raise RuntimeError('toolchain_plan_mismatch_or_blocked')
    return _create_approval(slug,'project.toolchain.build',plan,reason,username,groups,int(payload.get('ttlSeconds',payload.get('ttl_seconds',900)) or 900))


def execute_build(slug:str,payload:dict[str,Any],username:str,groups:list[str]|set[str])->dict[str,Any]:
    _require_write(slug,username,groups);ref=str(payload.get('ref') or 'main');expected=int(payload.get('expectedRevision',payload.get('expected_revision',0)) or 0);provided=str(payload.get('planDigest',payload.get('plan_digest',''))).lower();approval_id=str(payload.get('approvalId',payload.get('approval_id','')))
    plan=_plan(slug,ref,expected,True)
    if plan.get('blocked') or not plan.get('valid') or not hmac.compare_digest(str(plan.get('plan_digest') or ''),provided):raise RuntimeError('toolchain_plan_mismatch_or_blocked')
    approval=_approval_get(approval_id)
    if not approval:raise LookupError('approval_not_found')
    try:metadata=json.loads(approval.get('metadata_json') or '{}')
    except Exception:raise ValueError('approval_metadata_invalid')
    requested_by='portal:'+str(username).strip().casefold();reservation_id,execution_id=_transaction_ids('project.toolchain.build',approval_id,requested_by,provided)
    expected_services=[{'service':item.get('service'),'toolchainDigest':item.get('toolchainDigest')} for item in plan.get('services') or []]
    valid_status=approval.get('status')=='approved' or (approval.get('status') in {'reserved','consumed'} and approval.get('reservation_id')==reservation_id)
    valid=bool(valid_status and approval.get('project_slug')==slug and approval.get('action')=='project.toolchain.build' and approval.get('requested_by')==requested_by and approval.get('approved_by') and hmac.compare_digest(str(metadata.get('toolchain_plan_digest') or ''),provided) and int(metadata.get('config_revision') or 0)==expected and metadata.get('config_digest')==plan.get('config_digest') and metadata.get('requested_toolchain_digest')==plan.get('requested_toolchain_digest') and metadata.get('archive_sha256')==plan.get('archive_sha256') and metadata.get('ref')==ref and metadata.get('services')==expected_services and metadata.get('content_stored') is False and metadata.get('secret_values_in_metadata') is False)
    if not valid:raise PermissionError('approval_binding_mismatch')
    if approval.get('status')=='approved':
        code,reserved=_approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':requested_by,'ttl_seconds':900})
        if code!=200 or reserved.get('status')!='reserved':raise RuntimeError('approval_reserve_failed')
    code,result=_build('POST','/v1/toolchain/build',{'project_slug':slug,'ref':ref,'expected_revision':expected,'plan_digest':provided,'approved':True,'trace_id':'txn-'+reservation_id},900)
    current=_approval_get(approval_id)
    if code in {200,202} and result.get('ok'):
        if current and current.get('status')!='consumed':
            final_code,finalized=_approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
            if final_code!=200 or finalized.get('status')!='consumed':raise RuntimeError('approval_finalize_failed')
        result['transaction']={'approvalId':approval_id,'reservationId':reservation_id,'executionId':execution_id,'approvalStatus':'consumed'};result['imagesActivated']=False;result['containersChanged']=False;return result
    if current and current.get('status')=='reserved':_approval_transition(approval_id,'release',{'reservation_id':reservation_id})
    raise RuntimeError(str((result.get('error') or {}).get('message') or 'toolchain_build_queue_failed'))


def request_activation_approval(slug:str,payload:dict[str,Any],username:str,groups:list[str]|set[str])->dict[str,Any]:
    _require_write(slug,username,groups);environment=str(payload.get('environment') or '');job_id=str(payload.get('jobId',payload.get('job_id','')));expected=int(payload.get('expectedRevision',payload.get('expected_revision',0)) or 0);provided=str(payload.get('planDigest',payload.get('plan_digest',''))).lower();reason=str(payload.get('reason') or '')
    plan=_activation_plan(slug,environment,job_id,expected)
    if not hmac.compare_digest(str(plan.get('plan_digest') or ''),provided) or len(reason)<4:raise RuntimeError('activation_plan_mismatch')
    return _create_approval(slug,'project.toolchain.activation',plan,reason,username,groups,int(payload.get('ttlSeconds',payload.get('ttl_seconds',900)) or 900))


def execute_activation(slug:str,payload:dict[str,Any],username:str,groups:list[str]|set[str])->dict[str,Any]:
    _require_write(slug,username,groups);environment=str(payload.get('environment') or '');job_id=str(payload.get('jobId',payload.get('job_id','')));expected=int(payload.get('expectedRevision',payload.get('expected_revision',0)) or 0);provided=str(payload.get('planDigest',payload.get('plan_digest',''))).lower();approval_id=str(payload.get('approvalId',payload.get('approval_id','')))
    plan=_activation_plan(slug,environment,job_id,expected)
    if not hmac.compare_digest(str(plan.get('plan_digest') or ''),provided):raise RuntimeError('activation_plan_digest_mismatch')
    approval=_approval_get(approval_id)
    if not approval:raise LookupError('approval_not_found')
    try:metadata=json.loads(approval.get('metadata_json') or '{}')
    except Exception:raise ValueError('approval_metadata_invalid')
    requested_by='portal:'+str(username).strip().casefold();reservation_id,execution_id=_transaction_ids('project.toolchain.activation',approval_id,requested_by,provided)
    valid_status=approval.get('status')=='approved' or (approval.get('status') in {'reserved','consumed'} and approval.get('reservation_id')==reservation_id)
    valid=bool(valid_status and approval.get('project_slug')==slug and approval.get('action')=='project.toolchain.activation' and approval.get('requested_by')==requested_by and approval.get('approved_by') and hmac.compare_digest(str(metadata.get('activation_plan_digest') or ''),provided) and metadata.get('environment')==environment and metadata.get('job_id')==job_id and int(metadata.get('expected_revision') or 0)==expected and metadata.get('after')==(plan.get('after') or []) and metadata.get('content_stored') is False and metadata.get('secret_values_in_metadata') is False)
    if not valid:raise PermissionError('approval_binding_mismatch')
    if approval.get('status')=='approved':
        code,reserved=_approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':requested_by,'ttl_seconds':900})
        if code!=200 or reserved.get('status')!='reserved':raise RuntimeError('approval_reserve_failed')
    code,result=_build('POST','/v1/toolchain/activation/apply',{'project_slug':slug,'environment':environment,'job_id':job_id,'expected_revision':expected,'plan_digest':provided,'approval_id':approval_id,'approved':True,'actor':str(username).strip().casefold()},180)
    current=_approval_get(approval_id)
    if code==200 and result.get('ok'):
        if current and current.get('status')!='consumed':
            final_code,finalized=_approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
            if final_code!=200 or finalized.get('status')!='consumed':raise RuntimeError('approval_finalize_failed')
        result['transaction']={'approvalId':approval_id,'reservationId':reservation_id,'executionId':execution_id,'approvalStatus':'consumed'};result['containersChanged']=False;return result
    if current and current.get('status')=='reserved':_approval_transition(approval_id,'release',{'reservation_id':reservation_id})
    raise RuntimeError(str((result.get('error') or {}).get('message') or 'toolchain_activation_failed'))


def handle_get(slug:str,operation:str,query:dict[str,str],username:str,groups:list[str]|set[str])->tuple[int,dict[str,Any]]:
    auth=authorization(slug,username,groups)
    if not auth['canRead']:return 403,{'ok':False,'error':{'code':'forbidden','message':'Sem acesso ao projeto.'}}
    if operation=='':path='/v1/projects/'+urllib.parse.quote(slug,safe='')+'/toolchain?'+urllib.parse.urlencode({'ref':query.get('ref','main')})
    elif operation=='images':path='/v1/projects/'+urllib.parse.quote(slug,safe='')+'/toolchain/images'+(('?'+urllib.parse.urlencode({'service':query['service']})) if query.get('service') else '')
    elif operation.startswith('images/'):
        image_id=operation.split('/',1)[1];path='/v1/projects/'+urllib.parse.quote(slug,safe='')+'/toolchain/images/'+urllib.parse.quote(image_id,safe='')
    elif operation.startswith('builds/'):
        parts=operation.split('/');job_id=parts[1];path='/v1/toolchain/jobs/'+urllib.parse.quote(job_id,safe='')+('/logs' if len(parts)>2 and parts[2]=='logs' else '')
    else:return 404,{'ok':False,'error':{'code':'not_found'}}
    return _build('GET',path,timeout=180)


def handle_post(slug:str,operation:str,payload:dict[str,Any],username:str,groups:list[str]|set[str])->tuple[int,dict[str,Any]]:
    _require_write(slug,username,groups)
    ref=str(payload.get('ref') or 'main');expected=int(payload.get('expectedRevision',payload.get('expected_revision',0)) or 0)
    if operation=='validate':return 200,_plan(slug,ref,expected,True)
    if operation=='build/plan':return 200,_plan(slug,ref,expected,False)
    if operation=='build/approval/request':return 201,request_build_approval(slug,payload,username,groups)
    if operation=='build/execute':return 202,execute_build(slug,payload,username,groups)
    if operation=='activation/plan':return 200,_activation_plan(slug,str(payload.get('environment') or ''),str(payload.get('jobId',payload.get('job_id',''))),expected)
    if operation=='activation/approval/request':return 201,request_activation_approval(slug,payload,username,groups)
    if operation=='activation/execute':return 200,execute_activation(slug,payload,username,groups)
    return 404,{'ok':False,'error':{'code':'not_found'}}
