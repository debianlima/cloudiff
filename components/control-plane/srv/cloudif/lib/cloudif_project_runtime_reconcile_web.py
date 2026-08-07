#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from cloudif_project_environment_web import authorization

URL=os.environ.get('CLOUDIF_RUNTIME_RECONCILER_URL','http://127.0.0.1:18232').rstrip('/')
TOKEN=os.environ.get('CLOUDIF_RUNTIME_RECONCILER_TOKEN','')


def _call(method:str,path:str,payload:dict[str,Any]|None=None,timeout:int=45)->tuple[int,dict[str,Any]]:
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode() if payload is not None else None
    request=urllib.request.Request(URL+path,data=raw,method=method,headers={'Authorization':'Bearer '+TOKEN,'Accept':'application/json','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={'ok':False,'error':'runtime_reconciler_unavailable'}
        return error.code,data


def handle_get(slug:str,operation:str,query:dict[str,str],username:str,groups:list[str]|set[str])->tuple[int,dict[str,Any]]:
    auth=authorization(slug,username,groups)
    if not auth['canRead']:return 403,{'ok':False,'error':{'code':'forbidden','message':'Sem acesso ao projeto.'}}
    environment=str(query.get('environment') or '')
    path='/v1/projects/'+urllib.parse.quote(slug,safe='')+'/runtime-state'
    if environment:path+='?'+urllib.parse.urlencode({'environment':environment})
    code,data=_call('GET',path)
    if code!=200 or not data.get('ok'):return code,data
    states=data.get('states') or []
    if operation=='drift':states=[item for item in states if item.get('status')!='synchronized']
    return 200,{'ok':True,'projectSlug':slug,'environment':environment or None,'states':states,'count':len(states),'driftOnly':operation=='drift','effectsExecuted':False,'secretValuesIncluded':False,'secretReferencesIncluded':False}


def handle_post(slug:str,operation:str,payload:dict[str,Any],username:str,groups:list[str]|set[str])->tuple[int,dict[str,Any]]:
    auth=authorization(slug,username,groups)
    if not auth['canWrite']:return 403,{'ok':False,'error':{'code':'forbidden','message':'O planejamento de reconciliação exige permissão de manutenção do projeto.'}}
    if operation!='plan':return 404,{'ok':False,'error':{'code':'not_found'}}
    environment=str(payload.get('environment') or '')
    body={'environment':environment,'actor':str(username).strip().casefold(),'ttlSeconds':int(payload.get('ttlSeconds',payload.get('ttl_seconds',900)) or 900)}
    code,data=_call('POST','/v1/projects/'+urllib.parse.quote(slug,safe='')+'/reconcile-plan',body,timeout=90)
    if isinstance(data,dict):data['effectsExecuted']=False;data['secretValuesIncluded']=False;data['secretReferencesIncluded']=False
    return code,data
