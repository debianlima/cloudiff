#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

STATE_DB=Path(os.environ.get('CLOUDIF_PROJECT_CONFIG_DB','/var/lib/cloudif/project-config/config.db'))
CONTROL_DB=Path(os.environ.get('CLOUDIF_PROJECT_SNAPSHOT_DB','/var/lib/cloudif/control-plane/control-plane.db'))
ENVIRONMENTS=('development','preview','homologation','production')
ENV_RE=re.compile(r'^[A-Z_][A-Z0-9_]{0,127}$')
SERVICE_RE=re.compile(r'^[a-z][a-z0-9-]{0,31}$')
REFERENCE_RE=re.compile(r'^[a-z][a-z0-9_.:/-]{2,255}$')
SECRET_NAME_RE=re.compile(r'(?i)(?:password|secret|token|private|jwt|service[_-]?role|api[_-]?key|access[_-]?key|smtp[_-]?pass|signing[_-]?key)')
SENSITIVE_VALUE_RE=re.compile(
    r'(?i)(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|'
    r'\bBearer\s+[A-Za-z0-9._~-]{12,}|'
    r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}|'
    r'[a-z][a-z0-9+.-]*://[^/@:]{1,128}:[^/@]{1,512}@)'
)


def now()->int:return int(time.time())
def canonical(value:Any)->bytes:return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()
def digest(value:Any)->str:return hashlib.sha256(canonical(value)).hexdigest()


def db()->sqlite3.Connection:
    STATE_DB.parent.mkdir(parents=True,exist_ok=True)
    connection=sqlite3.connect(STATE_DB,timeout=30)
    connection.row_factory=sqlite3.Row
    connection.execute('pragma busy_timeout=30000')
    return connection


def init_db()->None:
    connection=db()
    connection.executescript('''
    create table if not exists environment_state(
      project_slug text primary key,
      revision integer not null default 0,
      environment_digest text not null,
      updated_by text not null,
      updated_at integer not null
    );
    create table if not exists environment_entries(
      project_slug text not null,
      environment text not null,
      service text not null default '',
      name text not null,
      kind text not null,
      value_json text,
      secret_reference text,
      metadata_json text not null,
      entry_revision integer not null,
      created_by text not null,
      created_at integer not null,
      updated_by text not null,
      updated_at integer not null,
      primary key(project_slug,environment,service,name)
    );
    create table if not exists environment_plans(
      plan_digest text primary key,
      project_slug text not null,
      action text not null,
      source_environment text,
      target_environment text not null,
      expected_revision integer not null,
      operations_json text not null,
      summary_json text not null,
      created_by text not null,
      created_at integer not null,
      expires_at integer not null,
      consumed_at integer,
      consumed_by text
    );
    create table if not exists environment_history(
      event_id text primary key,
      plan_digest text not null,
      project_slug text not null,
      environment text not null,
      service text not null,
      name text not null,
      operation text not null,
      before_json text not null,
      after_json text not null,
      environment_revision integer not null,
      environment_digest text not null,
      actor text not null,
      created_at integer not null
    );
    create index if not exists idx_environment_entries_project on environment_entries(project_slug,environment,service,name);
    create index if not exists idx_environment_history_project on environment_history(project_slug,created_at desc);
    create index if not exists idx_environment_plans_project on environment_plans(project_slug,created_at desc);
    ''')
    connection.commit();connection.close()


def project_exists(slug:str)->dict[str,Any]:
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}',slug):raise ValueError('invalid_project_slug')
    connection=sqlite3.connect(f'file:{CONTROL_DB}?mode=ro',uri=True,timeout=20);connection.row_factory=sqlite3.Row
    row=connection.execute('select project_id,slug,name,owner,tenant,status from projects where slug=?',(slug,)).fetchone();connection.close()
    if not row:raise LookupError('project_not_found')
    return dict(row)


def project_configuration(slug:str)->dict[str,Any]:
    connection=db()
    row=connection.execute('select current_revision from projects where project_slug=?',(slug,)).fetchone()
    if not row or int(row['current_revision'] or 0)<1:
        connection.close();return {}
    revision=connection.execute('select effective_json from revisions where project_slug=? and revision=?',(slug,int(row['current_revision']))).fetchone();connection.close()
    return json.loads(revision['effective_json']) if revision else {}


def project_services(slug:str)->list[str]:
    configuration=project_configuration(slug)
    return sorted(str(name) for name in (configuration.get('services') or {}))


def _state_row(connection:sqlite3.Connection,slug:str)->sqlite3.Row|None:
    return connection.execute('select * from environment_state where project_slug=?',(slug,)).fetchone()


def state(slug:str)->dict[str,Any]:
    project_exists(slug);connection=db();row=_state_row(connection,slug);connection.close()
    return {'revision':int(row['revision']) if row else 0,'environmentDigest':str(row['environment_digest']) if row else digest([]),'updatedBy':str(row['updated_by']) if row else '', 'updatedAt':int(row['updated_at']) if row else 0}


def _entry_material(row:sqlite3.Row|dict[str,Any],include_value:bool=False)->dict[str,Any]:
    get=row.__getitem__ if isinstance(row,sqlite3.Row) else row.get
    metadata=json.loads(get('metadata_json') or '{}') if isinstance(get('metadata_json'),str) else dict(get('metadata_json') or {})
    kind=str(get('kind') or '')
    value=None
    if kind=='public' and include_value:
        value=json.loads(get('value_json')) if get('value_json') is not None else None
    reference=str(get('secret_reference') or '')
    result={
      'environment':str(get('environment') or ''),'service':str(get('service') or ''),
      'name':str(get('name') or ''),'kind':kind,'secret':kind=='secret',
      'configured':bool(reference) if kind=='secret' else get('value_json') is not None,
      'value':value,'referenceConfigured':bool(reference),'metadata':metadata,
      'entryRevision':int(get('entry_revision') or 0),'updatedBy':str(get('updated_by') or ''),'updatedAt':int(get('updated_at') or 0),
    }
    return result


def _effective_digest(connection:sqlite3.Connection,slug:str)->str:
    rows=connection.execute('select * from environment_entries where project_slug=? order by environment,service,name',(slug,)).fetchall()
    material=[]
    for row in rows:
        material.append({
          'environment':row['environment'],'service':row['service'],'name':row['name'],'kind':row['kind'],
          'value':json.loads(row['value_json']) if row['value_json'] is not None else None,
          'secretReference':row['secret_reference'],'metadata':json.loads(row['metadata_json'] or '{}'),
          'entryRevision':int(row['entry_revision']),
        })
    return digest(material)


def _validate_environment(environment:str)->str:
    value=str(environment or '').strip().lower()
    if value not in ENVIRONMENTS:raise ValueError('invalid_environment')
    return value


def _validate_service(slug:str,service:Any)->str:
    value=str(service or '').strip().lower()
    if not value:return ''
    if not SERVICE_RE.fullmatch(value):raise ValueError('invalid_service')
    services=project_services(slug)
    if not services:raise ValueError('project_configuration_required_for_service_scope')
    if value not in services:raise ValueError('service_not_found')
    return value


def _aliases(raw:dict[str,Any])->dict[str,Any]:
    value=dict(raw)
    mapping={
      'secretRef':'secret_reference','secretReference':'secret_reference',
      'expose_to_client':'exposeToClient','restart_required':'restartRequired',
      'build_time':'buildTime','allowed_values':'allowedValues',
    }
    for alias,canonical_name in mapping.items():
        if canonical_name not in value and alias in value:value[canonical_name]=value.pop(alias)
    return value


def _normalize_metadata(raw:dict[str,Any])->dict[str,Any]:
    allowed={'required','secret','description','scope','exposeToClient','immutable','restartRequired','buildTime','runtime','validation','allowedValues','pattern'}
    metadata={key:raw[key] for key in allowed if key in raw}
    metadata.setdefault('required',False);metadata.setdefault('secret',False);metadata.setdefault('description','')
    metadata.setdefault('scope','service' if raw.get('service') else 'environment')
    metadata.setdefault('exposeToClient',False);metadata.setdefault('immutable',False)
    metadata.setdefault('restartRequired',True);metadata.setdefault('buildTime',False);metadata.setdefault('runtime',True)
    metadata.setdefault('validation',{});metadata.setdefault('allowedValues',[]);metadata.setdefault('pattern','')
    return metadata


def normalize_operation(slug:str,environment:str,raw:Any,index:int)->dict[str,Any]:
    if not isinstance(raw,dict):raise ValueError(f'invalid_operation:{index}')
    item=_aliases(raw);operation=str(item.get('operation') or 'upsert').strip().lower()
    if operation not in {'upsert','delete'}:raise ValueError(f'invalid_operation:{index}')
    name=str(item.get('name') or '').strip().upper()
    if not ENV_RE.fullmatch(name):raise ValueError(f'invalid_environment_name:{index}')
    service=_validate_service(slug,item.get('service'))
    if operation=='delete':
        return {'operation':'delete','environment':environment,'service':service,'name':name}
    definition=item.get('definition') if isinstance(item.get('definition'),dict) else {}
    merged=_aliases({**definition,**{key:value for key,value in item.items() if key not in {'definition','operation','name','service'}}})
    metadata=_normalize_metadata({**merged,'service':service})
    secret=bool(metadata.get('secret'))
    value_present='value' in merged
    value=merged.get('value')
    reference=str(merged.get('secret_reference') or '').strip()
    if secret:
        if value_present:raise ValueError(f'secret_value_not_allowed:{name}')
        if not reference:raise ValueError(f'secret_reference_required:{name}')
        if not REFERENCE_RE.fullmatch(reference):raise ValueError(f'invalid_secret_reference:{name}')
        if metadata.get('exposeToClient'):raise ValueError(f'secret_client_exposure_forbidden:{name}')
        kind='secret';stored_value=None
    else:
        if reference:raise ValueError(f'secret_reference_for_public_variable:{name}')
        if not value_present and metadata.get('required'):raise ValueError(f'public_value_required:{name}')
        if SECRET_NAME_RE.search(name):raise ValueError(f'sensitive_name_requires_secret:{name}')
        if isinstance(value,str) and SENSITIVE_VALUE_RE.search(value):raise ValueError(f'sensitive_value_not_allowed:{name}')
        if value_present and metadata.get('allowedValues') and value not in metadata['allowedValues']:raise ValueError(f'value_not_allowed:{name}')
        if value_present and metadata.get('pattern'):
            try:valid=bool(re.fullmatch(str(metadata['pattern']),str(value)))
            except re.error:raise ValueError(f'invalid_validation_pattern:{name}')
            if not valid:raise ValueError(f'value_pattern_mismatch:{name}')
        kind='public';stored_value=value if value_present else None
    if metadata.get('buildTime') is False and metadata.get('runtime') is False:raise ValueError(f'environment_variable_unused:{name}')
    return {'operation':'upsert','environment':environment,'service':service,'name':name,'kind':kind,'value':stored_value,'secret_reference':reference,'metadata':metadata}


def _impact(operations:list[dict[str,Any]],services:list[str])->dict[str,Any]:
    action='none';affected=set();reasons=[]
    for item in operations:
        metadata=item.get('metadata') or {}
        targets=[item['service']] if item.get('service') else services
        affected.update(targets)
        if item['operation']=='delete' or metadata.get('buildTime'):
            action='rebuild';reasons.append(f"{item['name']}:build")
        elif action!='rebuild' and (metadata.get('runtime',True) or metadata.get('restartRequired',True)):
            action='restart';reasons.append(f"{item['name']}:runtime")
    return {'requiredAction':action,'affectedServices':sorted(affected),'reasons':sorted(set(reasons))}


def validate_changes(slug:str,environment:str,changes:Any)->dict[str,Any]:
    project_exists(slug);environment=_validate_environment(environment)
    if not isinstance(changes,list) or not changes or len(changes)>256:raise ValueError('changes_must_be_nonempty_list')
    operations=[normalize_operation(slug,environment,item,index) for index,item in enumerate(changes)]
    keys=[(item['environment'],item['service'],item['name']) for item in operations]
    if len(keys)!=len(set(keys)):raise ValueError('duplicate_environment_operation')
    services=project_services(slug)
    impact=_impact(operations,services)
    return {'ok':True,'projectSlug':slug,'environment':environment,'operations':operations,'impact':impact,'secretValuesIncluded':False}


def _operation_summary(item:dict[str,Any])->dict[str,Any]:
    metadata=item.get('metadata') or {}
    return {'operation':item['operation'],'environment':item['environment'],'service':item.get('service') or '', 'name':item['name'],'secret':item.get('kind')=='secret','configured':bool(item.get('secret_reference')) if item.get('kind')=='secret' else 'value' in item,'required':bool(metadata.get('required')),'buildTime':bool(metadata.get('buildTime')),'runtime':bool(metadata.get('runtime',True))}


def plan_change(slug:str,environment:str,changes:Any,expected_revision:int,actor:str,ttl_seconds:int=900,action:str='change',source_environment:str='')->dict[str,Any]:
    current=state(slug)
    if int(expected_revision)!=int(current['revision']):raise RuntimeError(f'environment_revision_conflict:{current["revision"]}')
    validated=validate_changes(slug,environment,changes)
    operations=validated['operations'];impact=validated['impact']
    material={'projectSlug':slug,'action':action,'sourceEnvironment':source_environment,'targetEnvironment':environment,'expectedRevision':expected_revision,'operations':operations}
    plan_digest=digest(material);created=now();expires=created+max(60,min(int(ttl_seconds),86400))
    summary={'changeCount':len(operations),'changes':[_operation_summary(item) for item in operations],'impact':impact,'secretChanges':sum(1 for item in operations if item.get('kind')=='secret'),'publicChanges':sum(1 for item in operations if item.get('kind')=='public'),'secretValuesIncluded':False}
    connection=db();connection.execute('''insert or replace into environment_plans(plan_digest,project_slug,action,source_environment,target_environment,expected_revision,operations_json,summary_json,created_by,created_at,expires_at,consumed_at,consumed_by)
      values(?,?,?,?,?,?,?,?,?,?,?,null,null)''',(plan_digest,slug,action,source_environment or None,environment,int(expected_revision),json.dumps(operations,ensure_ascii=False,separators=(',',':')),json.dumps(summary,ensure_ascii=False,separators=(',',':')),actor,created,expires));connection.commit();connection.close()
    return {'ok':True,'sideEffectFree':True,'projectSlug':slug,'environment':environment,'expectedRevision':expected_revision,'nextRevision':expected_revision+1,'planDigest':plan_digest,'expiresAt':expires,'summary':summary,'approvalRequired':True,'secretValuesIncluded':False}


def plan_promotion(slug:str,source_environment:str,target_environment:str,service:str,expected_revision:int,actor:str,ttl_seconds:int=900)->dict[str,Any]:
    project_exists(slug);source=_validate_environment(source_environment);target=_validate_environment(target_environment)
    if source==target:raise ValueError('promotion_source_equals_target')
    service_value=_validate_service(slug,service)
    connection=db();query='select * from environment_entries where project_slug=? and environment=?';args:[Any]=[slug,source]
    if service_value:query+=' and service=?';args.append(service_value)
    rows=connection.execute(query,tuple(args)).fetchall();connection.close()
    if not rows:raise LookupError('promotion_source_empty')
    changes=[]
    for row in rows:
        metadata=json.loads(row['metadata_json'] or '{}')
        item={'operation':'upsert','name':row['name'],'service':row['service'],'definition':metadata}
        if row['kind']=='secret':item['definition']['secret']=True;item['secret_reference']=row['secret_reference']
        else:item['definition']['secret']=False;item['value']=json.loads(row['value_json']) if row['value_json'] is not None else None
        changes.append(item)
    return plan_change(slug,target,changes,expected_revision,actor,ttl_seconds,'promotion',source)


def _snapshot(row:sqlite3.Row|None)->dict[str,Any]:
    if not row:return {}
    return {'environment':row['environment'],'service':row['service'],'name':row['name'],'kind':row['kind'],'value':json.loads(row['value_json']) if row['value_json'] is not None and row['kind']=='public' else None,'referenceConfigured':bool(row['secret_reference']),'metadata':json.loads(row['metadata_json'] or '{}'),'entryRevision':int(row['entry_revision'])}


def apply_plan(slug:str,plan_digest_value:str,expected_revision:int,actor:str)->dict[str,Any]:
    project_exists(slug);connection=db();connection.execute('begin immediate')
    plan=connection.execute('select * from environment_plans where plan_digest=? and project_slug=?',(plan_digest_value,slug)).fetchone()
    if not plan:connection.rollback();connection.close();raise LookupError('environment_plan_not_found')
    current=_state_row(connection,slug);actual=int(current['revision']) if current else 0
    if plan['consumed_at']:
        connection.commit();connection.close();return {'ok':True,'idempotent':True,'projectSlug':slug,'revision':actual,'planDigest':plan_digest_value,'secretValuesIncluded':False}
    if int(plan['expires_at'])<now():connection.rollback();connection.close();raise RuntimeError('environment_plan_expired')
    if int(expected_revision)!=actual or int(plan['expected_revision'])!=actual:connection.rollback();connection.close();raise RuntimeError(f'environment_revision_conflict:{actual}')
    operations=json.loads(plan['operations_json']);timestamp=now();revision=actual+1;events=[]
    for item in operations:
        before=connection.execute('select * from environment_entries where project_slug=? and environment=? and service=? and name=?',(slug,item['environment'],item.get('service') or '',item['name'])).fetchone()
        before_snapshot=_snapshot(before)
        if item['operation']=='delete':
            if before and (json.loads(before['metadata_json'] or '{}').get('immutable')):
                connection.rollback();connection.close();raise RuntimeError(f'immutable_environment_variable:{item["name"]}')
            connection.execute('delete from environment_entries where project_slug=? and environment=? and service=? and name=?',(slug,item['environment'],item.get('service') or '',item['name']))
            after_snapshot={}
        else:
            if before and (json.loads(before['metadata_json'] or '{}').get('immutable')):
                same=(before['kind']==item['kind'] and before['secret_reference']==(item.get('secret_reference') or None) and (json.loads(before['value_json']) if before['value_json'] is not None else None)==item.get('value') and json.loads(before['metadata_json'] or '{}')==(item.get('metadata') or {}))
                if not same:connection.rollback();connection.close();raise RuntimeError(f'immutable_environment_variable:{item["name"]}')
            created_by=before['created_by'] if before else actor;created_at=int(before['created_at']) if before else timestamp;entry_revision=(int(before['entry_revision'])+1) if before else 1
            connection.execute('''insert into environment_entries(project_slug,environment,service,name,kind,value_json,secret_reference,metadata_json,entry_revision,created_by,created_at,updated_by,updated_at)
              values(?,?,?,?,?,?,?,?,?,?,?,?,?) on conflict(project_slug,environment,service,name) do update set kind=excluded.kind,value_json=excluded.value_json,secret_reference=excluded.secret_reference,metadata_json=excluded.metadata_json,entry_revision=excluded.entry_revision,updated_by=excluded.updated_by,updated_at=excluded.updated_at''',(
              slug,item['environment'],item.get('service') or '',item['name'],item['kind'],json.dumps(item.get('value'),ensure_ascii=False,separators=(',',':')) if item['kind']=='public' else None,item.get('secret_reference') or None,json.dumps(item.get('metadata') or {},ensure_ascii=False,separators=(',',':')),entry_revision,created_by,created_at,actor,timestamp))
            after=connection.execute('select * from environment_entries where project_slug=? and environment=? and service=? and name=?',(slug,item['environment'],item.get('service') or '',item['name'])).fetchone();after_snapshot=_snapshot(after)
        events.append((item,before_snapshot,after_snapshot))
    environment_digest=_effective_digest(connection,slug)
    connection.execute('''insert into environment_state(project_slug,revision,environment_digest,updated_by,updated_at) values(?,?,?,?,?) on conflict(project_slug) do update set revision=excluded.revision,environment_digest=excluded.environment_digest,updated_by=excluded.updated_by,updated_at=excluded.updated_at''',(slug,revision,environment_digest,actor,timestamp))
    for item,before_snapshot,after_snapshot in events:
        connection.execute('insert into environment_history(event_id,plan_digest,project_slug,environment,service,name,operation,before_json,after_json,environment_revision,environment_digest,actor,created_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,plan_digest_value,slug,item['environment'],item.get('service') or '',item['name'],item['operation'],json.dumps(before_snapshot,ensure_ascii=False,separators=(',',':')),json.dumps(after_snapshot,ensure_ascii=False,separators=(',',':')),revision,environment_digest,actor,timestamp))
    connection.execute('update environment_plans set consumed_at=?,consumed_by=? where plan_digest=?',(timestamp,actor,plan_digest_value));connection.commit();connection.close()
    summary=json.loads(plan['summary_json'])
    return {'ok':True,'idempotent':False,'projectSlug':slug,'environment':plan['target_environment'],'revision':revision,'environmentDigest':environment_digest,'planDigest':plan_digest_value,'summary':summary,'requiredAction':summary['impact']['requiredAction'],'affectedServices':summary['impact']['affectedServices'],'reconciliationPending':summary['impact']['requiredAction']!='none','runtimeChanged':False,'containersChanged':False,'secretValuesIncluded':False}


def list_environment(slug:str,environment:str='',service:str='',include_values:bool=False)->dict[str,Any]:
    project_exists(slug);environment_value=_validate_environment(environment) if environment else '';service_value=_validate_service(slug,service) if service else ''
    connection=db();query='select * from environment_entries where project_slug=?';args:[Any]=[slug]
    if environment_value:query+=' and environment=?';args.append(environment_value)
    if service_value:query+=' and service=?';args.append(service_value)
    query+=' order by environment,service,name';rows=connection.execute(query,tuple(args)).fetchall();state_row=_state_row(connection,slug);connection.close()
    entries=[_entry_material(row,include_values) for row in rows]
    return {'ok':True,'projectSlug':slug,'environment':environment_value or None,'service':service_value or None,'revision':int(state_row['revision']) if state_row else 0,'environmentDigest':str(state_row['environment_digest']) if state_row else digest([]),'entries':entries,'count':len(entries),'includePublicValues':bool(include_values),'secretValuesIncluded':False}


def history(slug:str,limit:int=100)->dict[str,Any]:
    project_exists(slug);limit=max(1,min(int(limit),500));connection=db();rows=connection.execute('select * from environment_history where project_slug=? order by created_at desc limit ?',(slug,limit)).fetchall();connection.close()
    events=[]
    for row in rows:
        before=json.loads(row['before_json'] or '{}');after=json.loads(row['after_json'] or '{}')
        for snapshot in (before,after):
            if snapshot.get('kind')=='secret':snapshot['value']=None;snapshot['referenceConfigured']=bool(snapshot.get('referenceConfigured'))
        events.append({'eventId':row['event_id'],'planDigest':row['plan_digest'],'environment':row['environment'],'service':row['service'],'name':row['name'],'operation':row['operation'],'before':before,'after':after,'revision':int(row['environment_revision']),'environmentDigest':row['environment_digest'],'actor':row['actor'],'createdAt':int(row['created_at'])})
    return {'ok':True,'projectSlug':slug,'events':events,'count':len(events),'secretValuesIncluded':False}


def missing_variables(slug:str,environment:str)->dict[str,Any]:
    environment_value=_validate_environment(environment);configuration=project_configuration(slug);services=configuration.get('services') or {}
    persisted=list_environment(slug,environment_value,include_values=False)['entries'];configured={(item['service'],item['name']) for item in persisted if item['configured']}
    missing=[]
    global_defs=((configuration.get('environment') or {}).get('definitions') or {})
    overlay=((configuration.get('environments') or {}).get(environment_value) or {})
    overlay_defs=((overlay.get('environment') or {}).get('definitions') or {})
    for name,spec in {**global_defs,**overlay_defs}.items():
        if spec.get('required') and ('',name) not in configured:missing.append({'name':name,'service':'','secret':bool(spec.get('secret')),'source':'manifest'})
    for service_name,service in services.items():
        definitions=((service.get('environment') or {}).get('definitions') or {})
        overlay_service=(((overlay.get('services') or {}).get(service_name) or {}).get('environment') or {}).get('definitions') or {}
        for name,spec in {**definitions,**overlay_service}.items():
            if spec.get('required') and (service_name,name) not in configured and ('',name) not in configured:missing.append({'name':name,'service':service_name,'secret':bool(spec.get('secret')),'source':'manifest'})
    return {'ok':True,'projectSlug':slug,'environment':environment_value,'missing':sorted(missing,key=lambda item:(item['service'],item['name'])),'count':len(missing),'valid':not missing,'secretValuesIncluded':False}


def get_plan(slug:str,plan_digest_value:str)->dict[str,Any]:
    project_exists(slug)
    if not re.fullmatch(r'[a-f0-9]{64}',str(plan_digest_value or '')):raise ValueError('invalid_environment_plan_digest')
    connection=db();row=connection.execute('select * from environment_plans where plan_digest=? and project_slug=?',(plan_digest_value,slug)).fetchone();connection.close()
    if not row:raise LookupError('environment_plan_not_found')
    summary=json.loads(row['summary_json'] or '{}')
    return {
      'ok':True,'projectSlug':slug,'planDigest':row['plan_digest'],'action':row['action'],
      'sourceEnvironment':row['source_environment'],'targetEnvironment':row['target_environment'],
      'expectedRevision':int(row['expected_revision']),'summary':summary,
      'createdBy':row['created_by'],'createdAt':int(row['created_at']),'expiresAt':int(row['expires_at']),
      'consumed':bool(row['consumed_at']),'secretValuesIncluded':False,
    }
