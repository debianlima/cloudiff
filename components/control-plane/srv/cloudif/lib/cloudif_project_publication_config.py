#!/usr/bin/env python3
from __future__ import annotations
import json, re, urllib.error, urllib.parse, urllib.request
from pathlib import Path

CONFIG_ENV=Path('/etc/cloudif/project-config-controller.env')
KOMODO_ENV=Path('/etc/cloudif/komodo-publication-client.env')
CONFIG_URL='http://127.0.0.1:18219'
KOMODO_URL='http://10.62.91.2:18098'
SHA256_RE=re.compile(r'^[a-f0-9]{64}$')
IMAGE_ID_RE=re.compile(r'^sha256:[a-f0-9]{64}$')

def _env(path:Path)->dict[str,str]:
    out={}
    try:
        for raw in path.read_text(encoding='utf-8',errors='ignore').splitlines():
            line=raw.strip()
            if line and not line.startswith('#') and '=' in line:
                key,value=line.split('=',1);out[key.strip()]=value.strip().strip('"').strip("'")
    except FileNotFoundError:pass
    return out

def _json(method:str,url:str,headers:dict[str,str]|None=None,payload:dict|None=None,timeout:int=60)->tuple[int,dict]:
    data=None if payload is None else json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
    request=urllib.request.Request(url,data=data,method=method,headers={'Accept':'application/json',**(headers or {}),**({'Content-Type':'application/json'} if data is not None else {})})
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:body=json.load(error)
        except Exception:body={'ok':False,'error':{'code':'http_error'}}
        return error.code,body

def _config_headers(extra:dict[str,str]|None=None)->dict[str,str]:
    token=_env(CONFIG_ENV).get('CLOUDIF_PROJECT_CONFIG_TOKEN','')
    if not token:raise RuntimeError('project_config_token_missing')
    return {'Authorization':'Bearer '+token,**(extra or {})}

def _komodo_headers()->dict[str,str]:
    token=_env(KOMODO_ENV).get('KOMODO_PUBLICATION_TOKEN','')
    if not token:raise RuntimeError('komodo_publication_token_missing')
    return {'X-CloudIF-Token':token,'Authorization':'Bearer '+token}

def _environment_name(environment:str)->str:
    environment=str(environment or '').strip().lower()
    if environment not in {'preview','homologation','production'}:raise ValueError('invalid_publication_environment')
    return environment

def _effective(slug:str,internal:bool=False,environment:str='production')->dict:
    suffix='/effective-internal' if internal else '/effective';environment=_environment_name(environment)
    code,data=_json('GET',CONFIG_URL+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/environment'+suffix+'?'+urllib.parse.urlencode({'environment':environment}),_config_headers(),timeout=30)
    if code!=200 or not data.get('ok'):raise RuntimeError('publication_environment_unavailable')
    return data

def environment_summary(slug:str,environment:str='production')->dict:
    environment=_environment_name(environment);data=_effective(slug,False,environment)
    return {'environment':environment,'environmentRevision':int(data.get('environmentRevision') or 0),'environmentDigest':str(data.get('environmentDigest') or ''),'valid':bool(data.get('valid')),'missingRequired':data.get('missingRequired') or [],'publicNames':data.get('publicRuntimeNames') or {},'secretNames':data.get('secretRuntimeNames') or {},'secretValuesIncluded':False,'secretReferencesIncluded':False}

def base_status(slug:str,public_number:int)->dict:
    code,data=_json('POST',KOMODO_URL+'/komodo/project/base/status',_komodo_headers(),{'project':slug,'public_number':int(public_number)},30)
    if code//100!=2 or not data.get('ok'):raise RuntimeError(str(data.get('error') or 'project_base_status_failed'))
    return data

def ensure_base(slug:str,public_number:int,actor:str)->dict:
    code,data=_json('POST',KOMODO_URL+'/komodo/project/base/ensure',_komodo_headers(),{'project':slug,'public_number':int(public_number),'actor':actor},180)
    if code//100!=2 or not data.get('ok'):raise RuntimeError(str(data.get('error') or 'project_base_ensure_failed'))
    return data

def snapshot_base(slug:str,public_number:int,actor:str)->dict:
    code,data=_json('POST',KOMODO_URL+'/komodo/project/base/snapshot',_komodo_headers(),{'project':slug,'public_number':int(public_number),'actor':actor},360)
    if code//100!=2 or not data.get('ok'):raise RuntimeError(str(data.get('error') or 'project_base_snapshot_failed'))
    if int(data.get('base_revision') or 0)<1 or not IMAGE_ID_RE.fullmatch(str(data.get('base_image_id') or '')):raise RuntimeError('project_base_snapshot_contract_invalid')
    return data

def capture_snapshot(slug:str,public_number:int,actor:str,environment:str='production')->dict:
    environment=_environment_name(environment);environment_state=environment_summary(slug,environment)
    if not environment_state.get('valid'):raise RuntimeError('publication_environment_missing_required')
    base=snapshot_base(slug,public_number,actor)
    digest=str(environment_state.get('environmentDigest') or '')
    if digest and not SHA256_RE.fullmatch(digest):raise RuntimeError('publication_environment_digest_invalid')
    return {'baseRevision':int(base['base_revision']),'baseImage':str(base.get('base_image') or ''),'baseImageId':str(base['base_image_id']),'environment':environment,'environmentRevision':int(environment_state['environmentRevision']),'environmentDigest':digest,'secretValuesIncluded':False,'secretReferencesIncluded':False}

def _flatten(named:dict)->dict[str,str]:
    if not isinstance(named,dict):raise RuntimeError('publication_environment_contract_invalid')
    out={}
    priority=sorted(named,key=lambda service:(service not in {'','web'},service))
    for service in priority:
        values=named.get(service) or {}
        if not isinstance(values,dict):raise RuntimeError('publication_environment_contract_invalid')
        for name,value in values.items():
            name=str(name)
            value=str(value)
            if name in out and out[name]!=value:raise RuntimeError('publication_environment_service_conflict:'+name)
            out[name]=value
    return out

def execution_environment(slug:str,expected_revision:int,expected_digest:str,environment:str='production')->dict:
    environment=_environment_name(environment);data=_effective(slug,True,environment)
    revision=int(data.get('environmentRevision') or 0);digest=str(data.get('environmentDigest') or '')
    if revision!=int(expected_revision) or digest!=str(expected_digest or ''):raise RuntimeError('publication_environment_changed')
    if not data.get('valid'):raise RuntimeError('publication_environment_missing_required')
    public=_flatten(data.get('publicRuntimeEnvironment') or {})
    references=data.get('secretRuntimeReferences') or {}
    resolved={}
    if any(bool(v) for v in references.values() if isinstance(v,dict)):
        cfg=_env(CONFIG_ENV);resolver=cfg.get('CLOUDIF_SECRET_RESOLVER_TOKEN','')
        if not resolver:raise RuntimeError('secret_resolver_unavailable')
        code,secret_data=_json('POST',CONFIG_URL+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/environment/secrets/resolve-internal',_config_headers({'X-CloudIF-Secret-Resolver-Token':resolver}),{'environment':environment,'references':references,'actor':'portal-publication'},30)
        if code!=200 or secret_data.get('ok') is not True or secret_data.get('internal') is not True or secret_data.get('secretValuesIncluded') is not True:raise RuntimeError('publication_secret_resolution_failed')
        raw_resolved=secret_data.get('resolvedSecrets')
        if not isinstance(raw_resolved,dict) or set(raw_resolved)!=set(references):raise RuntimeError('publication_secret_resolution_scope_mismatch')
        for service,expected in references.items():
            values=raw_resolved.get(service)
            if not isinstance(expected,dict) or not isinstance(values,dict) or set(values)!=set(expected) or not all(isinstance(value,str) for value in values.values()):raise RuntimeError('publication_secret_resolution_scope_mismatch')
        resolved=_flatten(raw_resolved)
    conflict=set(public).intersection(resolved)
    if conflict:raise RuntimeError('publication_environment_public_secret_conflict:'+sorted(conflict)[0])
    values={**public,**resolved}
    return {'environment':environment,'environmentRevision':revision,'environmentDigest':digest,'values':values,'variableNames':sorted(values),'secretValuesIncluded':True,'metadataSafe':False}
