#!/usr/bin/env python3
from __future__ import annotations
import json,os,urllib.error,urllib.parse,urllib.request
from pathlib import Path

ENV=Path(os.environ.get('CLOUDIF_PROJECT_CONFIG_ENV','/etc/cloudif/project-config-controller.env'))
URL=os.environ.get('CLOUDIF_PROJECT_CONFIG_URL','http://127.0.0.1:18219').rstrip('/')

def _env():
    values={}
    try:
        for raw in ENV.read_text(encoding='utf-8',errors='ignore').splitlines():
            line=raw.strip()
            if line and not line.startswith('#') and '=' in line:
                key,value=line.split('=',1);values[key.strip()]=value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return values

def _safe_details(details):
    allowed={'source','operation','principal','principal_type','targets','publication_id','deploy_number','commit_sha','action','create_repo','setup_komodo','db_mode','runtime_template','runtime_layout','environment','environment_revision','environment_digest','affected_services','required_action','reason'}
    source=details if isinstance(details,dict) else {}
    return {key:source[key] for key in allowed if key in source and isinstance(source[key],(str,int,float,bool,list,type(None)))}

def event_for_reconcile(event_type,payload):
    payload=payload if isinstance(payload,dict) else {}
    if event_type=='project.created':return 'project.created'
    if event_type=='project.configuration.changed':return 'configuration.changed'
    if event_type=='project.membership.changed':
        if payload.get('source') in {'publication_activation','initial_publication'}:return 'publication.created'
        operation=str(payload.get('operation') or '').lower()
        if operation=='add':return 'project.member.added'
        if operation=='remove':return 'project.member.removed'
        return 'project.membership.reconciled'
    return 'project.updated'

def notify(project_slug,event_type,details=None,timeout=20):
    token=_env().get('CLOUDIF_PROJECT_CONFIG_TOKEN','')
    if not token:raise RuntimeError('project_config_token_missing')
    mapped=event_for_reconcile(event_type,details or {})
    payload={'eventType':mapped,'details':_safe_details(details or {})}
    request=urllib.request.Request(URL+'/v1/projects/'+urllib.parse.quote(project_slug,safe='')+'/events',data=json.dumps(payload,separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:
            data=json.load(response)
            if response.status!=200 or not data.get('ok'):raise RuntimeError('project_config_event_rejected')
            return data
    except urllib.error.HTTPError as error:
        raise RuntimeError('project_config_event_http_'+str(error.code)) from error
