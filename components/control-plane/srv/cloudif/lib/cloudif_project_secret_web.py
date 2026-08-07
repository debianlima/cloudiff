#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any

try:
    from cloudif_project_environment_web import (
        APPROVAL_TOKEN, APPROVAL_URL, CONFIG_TOKEN, CONFIG_URL,
        _approval_get, _approval_transition, _json_call, _transaction_ids, authorization,
    )
except ModuleNotFoundError:
    path=Path(__file__).with_name('cloudif_project_environment_web.py')
    spec=importlib.util.spec_from_file_location('cloudif_project_environment_web',path)
    module=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(module)
    APPROVAL_TOKEN=module.APPROVAL_TOKEN;APPROVAL_URL=module.APPROVAL_URL
    CONFIG_TOKEN=module.CONFIG_TOKEN;CONFIG_URL=module.CONFIG_URL
    _approval_get=module._approval_get;_approval_transition=module._approval_transition
    _json_call=module._json_call;_transaction_ids=module._transaction_ids;authorization=module.authorization

ACTIONS={
    'rotate':'project.environment.secret.rotation',
    'revoke':'project.environment.secret.revocation',
    'promote':'project.environment.secret.promotion',
}
PLAN_RE=re.compile(r'^[a-f0-9]{64}$')
APPROVAL_RE=re.compile(r'^apr_[a-f0-9]{20}$')
STAGE_RE=re.compile(r'^stage_[a-f0-9]{24}$')
REFERENCE_RE=re.compile(r'^cloudiff-secret://[a-z0-9][A-Za-z0-9_.:/-]{2,255}$')


def _config(method:str,slug:str,suffix:str='',payload:dict[str,Any]|None=None,query:dict[str,Any]|None=None,timeout:int=45)->tuple[int,dict[str,Any]]:
    path=CONFIG_URL+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/environment/secrets'+suffix
    if query:path+='?'+urllib.parse.urlencode(query)
    return _json_call(method,path,CONFIG_TOKEN,payload,timeout)


def _plan(slug:str,plan_digest:str)->dict[str,Any]:
    if not PLAN_RE.fullmatch(str(plan_digest or '')):raise ValueError('invalid_secret_plan_digest')
    code,data=_config('GET',slug,'/plans/'+plan_digest)
    if code!=200 or not data.get('ok'):
        error=data.get('error') or {};raise LookupError(str(error.get('code') if isinstance(error,dict) else error or 'secret_plan_not_found'))
    if data.get('secretValueIncluded') is not False or data.get('ciphertextIncluded') is not False:raise RuntimeError('secret_plan_public_contract_invalid')
    return data


def _require_read(slug:str,username:str,groups:list[str]|set[str])->dict[str,Any]:
    auth=authorization(slug,username,groups)
    if not auth['canRead']:raise PermissionError('forbidden')
    return auth


def _require_write(slug:str,username:str,groups:list[str]|set[str])->dict[str,Any]:
    auth=authorization(slug,username,groups)
    if not auth['canWrite']:raise PermissionError('forbidden')
    return auth


def _approval_metadata(plan:dict[str,Any])->dict[str,Any]:
    return {
        'secret_plan_digest':plan['planDigest'],'secret_action':plan['action'],
        'environment':plan.get('environment'),'service':plan.get('service'),'name':plan.get('name'),
        'stage_id':plan.get('stageId'),'secret_reference':plan.get('secretReference'),'source_secret_reference':plan.get('sourceSecretReference'),
        'expected_revision':plan.get('expectedRevision'),'target_version':plan.get('targetVersion'),
        'content_stored':False,'secret_values_in_metadata':False,'ciphertext_in_metadata':False,
    }


def request_approval(slug:str,plan_digest:str,reason:str,username:str,groups:list[str]|set[str],ttl_seconds:int=900)->dict[str,Any]:
    auth=_require_write(slug,username,groups);plan=_plan(slug,plan_digest);action=ACTIONS.get(str(plan.get('action') or ''))
    if not action:raise ValueError('unsupported_secret_action')
    if plan.get('consumed') or str(plan.get('status') or '')!='planned' or int(plan.get('expiresAt') or 0)<=int(time.time()):raise RuntimeError('secret_plan_unavailable')
    requested_by='portal:'+str(username).strip().casefold();metadata=_approval_metadata(plan)
    payload={'project_slug':slug,'action':action,'requested_by':requested_by,'requester_role':auth['role'],'ttl_seconds':max(60,min(int(ttl_seconds),86400)),'reason':str(reason or '')[:500],'trace_id':'portal-secret-'+plan_digest[:20],'metadata':metadata}
    code,data=_json_call('POST',APPROVAL_URL+'/v1/approvals',APPROVAL_TOKEN,payload)
    if code not in {200,201} or not data.get('ok'):raise RuntimeError(str((data.get('error') or {}).get('message') or 'approval_create_failed'))
    return {'ok':True,'approvalId':data['approval_id'],'status':data['status'],'expiresAt':data['expires_at'],'projectSlug':slug,'action':action,'planDigest':plan_digest,'approvalUrl':'/cloudiff/portal/?tab=aprovacoes','policyApplied':bool(data.get('policy_applied')),'approvalPolicyId':data.get('approval_policy_id'),'secretValuesIncluded':False,'ciphertextIncluded':False}


def _execution_payload(plan:dict[str,Any],actor:str)->tuple[str,dict[str,Any]]:
    action=str(plan.get('action') or '')
    base={'planDigest':plan['planDigest'],'expectedRevision':int(plan['expectedRevision']),'approved':True,'actor':actor}
    if action=='rotate':
        stage=str(plan.get('stageId') or '')
        if not STAGE_RE.fullmatch(stage):raise ValueError('invalid_secret_stage_binding')
        base['stageId']=stage;return '/rotate/apply',base
    if action=='revoke':
        reference=str(plan.get('secretReference') or '')
        if not REFERENCE_RE.fullmatch(reference):raise ValueError('invalid_secret_reference')
        base['secretReference']=reference;return '/revoke/apply',base
    if action=='promote':
        source=str(plan.get('sourceSecretReference') or '')
        if not REFERENCE_RE.fullmatch(source):raise ValueError('invalid_source_secret_reference')
        base['sourceSecretReference']=source;return '/promote/apply',base
    raise ValueError('unsupported_secret_action')


def execute(slug:str,plan_digest:str,approval_id:str,binding:dict[str,Any],username:str,groups:list[str]|set[str])->dict[str,Any]:
    _require_write(slug,username,groups)
    if not PLAN_RE.fullmatch(plan_digest) or not APPROVAL_RE.fullmatch(approval_id):raise ValueError('invalid_secret_execution_binding')
    plan=_plan(slug,plan_digest);action_key=str(plan.get('action') or '');action=ACTIONS.get(action_key)
    if not action:raise ValueError('unsupported_secret_action')
    approval=_approval_get(approval_id)
    if not approval:raise LookupError('approval_not_found')
    try:metadata=json.loads(approval.get('metadata_json') or '{}')
    except Exception:raise ValueError('approval_metadata_invalid')
    requested_by='portal:'+str(username).strip().casefold();reservation_id,execution_id=_transaction_ids(action,approval_id,requested_by,plan_digest)
    valid_status=approval.get('status')=='approved' or (approval.get('status') in {'reserved','consumed'} and approval.get('reservation_id')==reservation_id)
    expected_metadata=_approval_metadata(plan)
    valid=bool(
        valid_status and approval.get('project_slug')==slug and approval.get('action')==action and
        approval.get('requested_by')==requested_by and approval.get('approved_by') and
        hmac.compare_digest(str(metadata.get('secret_plan_digest') or ''),plan_digest) and
        all(metadata.get(key)==value for key,value in expected_metadata.items() if key!='secret_plan_digest')
    )
    if not valid:raise PermissionError('approval_binding_mismatch')
    if approval.get('status')=='approved':
        code,reserved=_approval_transition(approval_id,'reserve',{'reservation_id':reservation_id,'reserved_by':requested_by,'ttl_seconds':900})
        if code!=200 or reserved.get('status')!='reserved':raise RuntimeError('approval_reserve_failed')
    suffix,payload=_execution_payload(plan,str(username).strip().casefold())
    if action_key=='promote':
        source=str(binding.get('sourceSecretReference',binding.get('source_secret_reference',plan.get('sourceSecretReference') or '')))
        if not REFERENCE_RE.fullmatch(source) or not hmac.compare_digest(source,str(plan.get('sourceSecretReference') or '')):raise ValueError('source_secret_reference_binding_mismatch')
        payload['sourceSecretReference']=source
    code,result=_config('POST',slug,suffix,payload,timeout=120)
    current=_approval_get(approval_id)
    if code==200 and result.get('ok'):
        if current and current.get('status')!='consumed':
            final_code,finalized=_approval_transition(approval_id,'finalize',{'reservation_id':reservation_id,'result':'success'})
            if final_code!=200 or finalized.get('status')!='consumed':raise RuntimeError('approval_finalize_failed')
        result['transaction']={'approvalId':approval_id,'reservationId':reservation_id,'executionId':execution_id,'approvalStatus':'consumed'};result['secretValuesIncluded']=False;result['ciphertextIncluded']=False;return result
    if current and current.get('status')=='reserved':_approval_transition(approval_id,'release',{'reservation_id':reservation_id})
    error=result.get('error') or {};raise RuntimeError(str(error.get('message') if isinstance(error,dict) else error or 'secret_apply_failed'))


def handle_get(slug:str,operation:str,query:dict[str,str],username:str,groups:list[str]|set[str])->tuple[int,dict[str,Any]]:
    _require_read(slug,username,groups)
    if operation=='history':return _config('GET',slug,'/history',query={'limit':query.get('limit','100')})
    if operation=='':
        params={key:query[key] for key in ('environment','service') if query.get(key)}
        return _config('GET',slug,query=params)
    return 404,{'ok':False,'error':{'code':'not_found'}}


def handle_post(slug:str,operation:str,payload:dict[str,Any],username:str,groups:list[str]|set[str])->tuple[int,dict[str,Any]]:
    _require_write(slug,username,groups);actor=str(username).strip().casefold();body=dict(payload);body['actor']=actor
    if operation=='stage':
        value=body.pop('secretValue',body.pop('secret_value',None))
        try:
            body['secretValue']=value;return _config('POST',slug,'/stage',body,timeout=30)
        finally:value=None;body.pop('secretValue',None)
    if operation in {'rotate/plan','revoke/plan','promote/plan'}:return _config('POST',slug,'/'+operation,body)
    if operation in {'rotate/approval/request','revoke/approval/request','promote/approval/request'}:
        return 201,request_approval(slug,str(body.get('planDigest',body.get('plan_digest',''))),str(body.get('reason') or ''),username,groups,int(body.get('ttlSeconds',body.get('ttl_seconds',900)) or 900))
    if operation in {'rotate/execute','revoke/execute','promote/execute'}:
        result=execute(slug,str(body.get('planDigest',body.get('plan_digest',''))),str(body.get('approvalId',body.get('approval_id',''))),body,username,groups);return 200,result
    return 404,{'ok':False,'error':{'code':'not_found'}}
