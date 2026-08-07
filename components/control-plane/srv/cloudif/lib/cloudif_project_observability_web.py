#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from cloudif_project_environment_web import authorization

URL=os.environ.get('CLOUDIF_PROJECT_OBSERVABILITY_URL','http://127.0.0.1:18233').rstrip('/')
TOKEN=os.environ.get('CLOUDIF_PROJECT_OBSERVABILITY_TOKEN','')


def _call(path:str,query:dict[str,Any]|None=None)->tuple[int,dict[str,Any]]:
    url=URL+path
    if query:url+='?'+urllib.parse.urlencode(query)
    request=urllib.request.Request(url,headers={'Authorization':'Bearer '+TOKEN,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=30) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={'ok':False,'error':'observability_unavailable'}
        return error.code,data


def handle_get(slug:str,operation:str,username:str,groups:list[str]|set[str])->tuple[int,dict[str,Any]]:
    auth=authorization(slug,username,groups)
    if not auth['canRead']:return 403,{'ok':False,'error':{'code':'forbidden','message':'Sem acesso ao projeto.'}}
    path='/v1/alerts' if operation=='alerts' else '/v1/snapshot'
    code,data=_call(path,{'slug':slug})
    if isinstance(data,dict):
        data['effectsExecuted']=False;data['secretValuesIncluded']=False;data['secretReferencesIncluded']=False
    return code,data
