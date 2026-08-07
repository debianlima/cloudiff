#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import json
import os
import re
import secrets
import sqlite3
import stat
import time
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    import cloudif_project_environment as environment_store
except ModuleNotFoundError:
    _path=Path(__file__).with_name('cloudif_project_environment.py')
    _spec=importlib.util.spec_from_file_location('cloudif_project_environment',_path)
    environment_store=importlib.util.module_from_spec(_spec);assert _spec.loader;_spec.loader.exec_module(environment_store)

DB=Path(os.environ.get('CLOUDIF_PROJECT_CONFIG_DB','/var/lib/cloudif/project-config/config.db'))
KEY_FILE=Path(os.environ.get('CLOUDIF_ENVIRONMENT_SECRET_KEY_FILE','/etc/cloudif/environment-secrets.key'))
NAME_RE=re.compile(r'^[A-Z][A-Z0-9_]{0,127}$')
SLUG_RE=re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
SERVICE_RE=re.compile(r'^[a-z][a-z0-9-]{0,62}$')
STAGE_RE=re.compile(r'^stage_[a-f0-9]{24}$')
PLAN_RE=re.compile(r'^[a-f0-9]{64}$')
REFERENCE_RE=re.compile(r'^cloudiff-secret://([a-z0-9][a-z0-9-]{0,62})/(development|preview|homologation|production)/([a-z][a-z0-9-]{0,62}|project)/([A-Z][A-Z0-9_]{0,127})/v([1-9][0-9]*)$')
ENVIRONMENTS={'development','preview','homologation','production'}


def now()->int:return int(time.time())


def canonical(value:Any)->bytes:return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()


def digest(value:Any)->str:return hashlib.sha256(canonical(value)).hexdigest()


def db()->sqlite3.Connection:
    connection=sqlite3.connect(DB,timeout=30)
    connection.row_factory=sqlite3.Row
    connection.execute('pragma busy_timeout=30000')
    return connection


def init_db()->None:
    DB.parent.mkdir(parents=True,exist_ok=True)
    connection=db()
    connection.executescript('''
      create table if not exists environment_secret_materials(
        stage_id text primary key,
        project_slug text not null,
        environment text not null,
        service text not null,
        name text not null,
        version integer not null default 0,
        secret_reference text,
        nonce_b64 text not null,
        ciphertext_b64 text not null,
        aad_json text not null,
        material_digest text not null,
        status text not null,
        created_by text not null,
        created_at integer not null,
        expires_at integer not null,
        activated_at integer,
        revoked_at integer,
        superseded_at integer
      );
      create unique index if not exists environment_secret_reference_unique
        on environment_secret_materials(secret_reference) where secret_reference is not null;
      create index if not exists environment_secret_lookup
        on environment_secret_materials(project_slug,environment,service,name,status,version);
      create table if not exists environment_secret_plans(
        plan_digest text primary key,
        action text not null,
        project_slug text not null,
        environment text not null,
        service text not null,
        name text not null,
        stage_id text,
        secret_reference text,
        expected_revision integer not null,
        target_version integer not null,
        definition_json text not null,
        reason text not null,
        status text not null,
        requested_by text not null,
        created_at integer not null,
        expires_at integer not null,
        applied_at integer
      );
      create table if not exists environment_secret_events(
        event_id text primary key,
        project_slug text not null,
        environment text not null,
        service text not null,
        name text not null,
        action text not null,
        secret_reference text,
        version integer not null,
        actor text not null,
        details_json text not null,
        created_at integer not null
      );
    ''')
    connection.commit();connection.close()


def _secure_key()->bytes:
    KEY_FILE.parent.mkdir(parents=True,exist_ok=True)
    if not KEY_FILE.exists():
        flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
        descriptor=os.open(KEY_FILE,flags,0o600)
        try:
            material=AESGCM.generate_key(bit_length=256)
            os.write(descriptor,material);os.fsync(descriptor)
        finally:os.close(descriptor)
    info=KEY_FILE.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):raise PermissionError('secret_key_file_invalid')
    if info.st_mode & 0o077:raise PermissionError('secret_key_permissions_too_open')
    material=KEY_FILE.read_bytes()
    if len(material)!=32:raise ValueError('secret_key_length_invalid')
    return material


def _validate_scope(slug:str,environment:str,service:str,name:str)->tuple[str,str,str,str]:
    slug=str(slug or '').strip().lower();environment=str(environment or '').strip().lower();service=str(service or '').strip().lower();name=str(name or '').strip().upper()
    if not SLUG_RE.fullmatch(slug):raise ValueError('invalid_project_slug')
    if environment not in ENVIRONMENTS:raise ValueError('invalid_environment')
    if service and not SERVICE_RE.fullmatch(service):raise ValueError('invalid_service')
    if not NAME_RE.fullmatch(name):raise ValueError('invalid_environment_name')
    return slug,environment,service,name


def _event(connection:sqlite3.Connection,row:dict[str,Any],action:str,actor:str,details:dict[str,Any]|None=None)->None:
    connection.execute('insert into environment_secret_events values(?,?,?,?,?,?,?,?,?,?,?)',(
        secrets.token_hex(16),row['project_slug'],row['environment'],row['service'],row['name'],action,
        row.get('secret_reference'),int(row.get('version') or 0),str(actor)[:128],
        json.dumps(details or {},ensure_ascii=False,separators=(',',':')),now(),
    ))


def stage_secret(slug:str,environment:str,service:str,name:str,value:str|bytes,actor:str,ttl_seconds:int=900)->dict[str,Any]:
    init_db();slug,environment,service,name=_validate_scope(slug,environment,service,name)
    if isinstance(value,str):material=value.encode()
    elif isinstance(value,(bytes,bytearray)):material=bytes(value)
    else:raise ValueError('secret_value_must_be_string')
    if not material or len(material)>65536:raise ValueError('secret_value_size_invalid')
    ttl=max(60,min(int(ttl_seconds),1800));stage_id='stage_'+secrets.token_hex(12);created=now();expires=created+ttl
    aad={'stageId':stage_id,'projectSlug':slug,'environment':environment,'service':service,'name':name,'createdAt':created}
    aad_bytes=canonical(aad);key=_secure_key();nonce=os.urandom(12);ciphertext=AESGCM(key).encrypt(nonce,material,aad_bytes)
    material_digest=hmac.new(key,aad_bytes+b'\x00'+material,hashlib.sha256).hexdigest()
    connection=db();connection.execute('begin immediate')
    connection.execute('insert into environment_secret_materials(stage_id,project_slug,environment,service,name,nonce_b64,ciphertext_b64,aad_json,material_digest,status,created_by,created_at,expires_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?)',(
        stage_id,slug,environment,service,name,base64.b64encode(nonce).decode(),base64.b64encode(ciphertext).decode(),aad_bytes.decode(),material_digest,'staged',str(actor)[:128],created,expires,
    ))
    row={'project_slug':slug,'environment':environment,'service':service,'name':name,'version':0,'secret_reference':None}
    _event(connection,row,'staged',actor,{'stageId':stage_id,'expiresAt':expires,'materialDigest':material_digest})
    connection.commit();connection.close()
    return {'ok':True,'stageId':stage_id,'projectSlug':slug,'environment':environment,'service':service,'name':name,'status':'staged','expiresAt':expires,'materialDigest':material_digest,'secretValueIncluded':False,'ciphertextIncluded':False}


def _stage(stage_id:str)->dict[str,Any]:
    if not STAGE_RE.fullmatch(str(stage_id or '')):raise ValueError('invalid_stage_id')
    connection=db();row=connection.execute('select * from environment_secret_materials where stage_id=?',(stage_id,)).fetchone();connection.close()
    if not row:raise LookupError('secret_stage_not_found')
    return dict(row)


def _current_environment_revision(slug:str)->int:
    connection=db();row=connection.execute('select revision from environment_state where project_slug=?',(slug,)).fetchone();connection.close()
    return int(row['revision']) if row else 0


def _next_version(connection:sqlite3.Connection,slug:str,environment:str,service:str,name:str)->int:
    row=connection.execute('select max(version) as version from environment_secret_materials where project_slug=? and environment=? and service=? and name=?',(slug,environment,service,name)).fetchone()
    return int((row['version'] if row else 0) or 0)+1


def rotation_plan(slug:str,stage_id:str,expected_revision:int,actor:str,reason:str,definition:dict[str,Any]|None=None,ttl_seconds:int=900,active_ttl_seconds:int=0)->dict[str,Any]:
    init_db();row=_stage(stage_id);slug=str(slug or '').strip().lower()
    if row['project_slug']!=slug:raise PermissionError('secret_stage_project_mismatch')
    if row['status']!='staged' or int(row['expires_at'])<=now():raise ValueError('secret_stage_expired_or_unavailable')
    actual=_current_environment_revision(slug)
    if int(expected_revision)!=actual:raise ValueError('environment_revision_mismatch')
    connection=db();version=_next_version(connection,row['project_slug'],row['environment'],row['service'],row['name']);connection.close()
    reference=f"cloudiff-secret://{row['project_slug']}/{row['environment']}/{row['service'] or 'project'}/{row['name']}/v{version}"
    definition=dict(definition or {});definition.update({'secret':True});definition.pop('value',None);definition.pop('default',None);definition['exposeToClient']=False
    created=now();expires=created+max(60,min(int(ttl_seconds),86400));active_ttl=max(0,min(int(active_ttl_seconds or 0),31536000));active_expires_at=(created+active_ttl) if active_ttl else 2147483647;definition['_cloudiffSecretExpiresAt']=active_expires_at
    material={'kind':'secret-rotation-v1','projectSlug':slug,'environment':row['environment'],'service':row['service'],'name':row['name'],'stageId':stage_id,'materialDigest':row['material_digest'],'expectedRevision':actual,'targetVersion':version,'secretReference':reference,'definition':definition}
    plan_digest=digest(material)
    connection=db();connection.execute('insert or ignore into environment_secret_plans values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
        plan_digest,'rotate',slug,row['environment'],row['service'],row['name'],stage_id,reference,actual,version,json.dumps(definition,ensure_ascii=False,separators=(',',':')),str(reason)[:500],'planned',str(actor)[:128],created,expires,None,
    ));connection.commit();connection.close()
    return {'ok':True,'sideEffectFree':True,'action':'rotate','projectSlug':slug,'environment':row['environment'],'service':row['service'],'name':row['name'],'stageId':stage_id,'expectedRevision':actual,'targetVersion':version,'secretReference':reference,'planDigest':plan_digest,'expiresAt':expires,'activeExpiresAt':active_expires_at,'approvalRequired':True,'restartRequired':bool(definition.get('restartRequired',definition.get('runtime',True))),'rebuildRequired':bool(definition.get('buildTime')),'secretValueIncluded':False,'ciphertextIncluded':False}


def _plan(plan_digest:str)->dict[str,Any]:
    if not PLAN_RE.fullmatch(str(plan_digest or '')):raise ValueError('invalid_secret_plan_digest')
    connection=db();row=connection.execute('select * from environment_secret_plans where plan_digest=?',(plan_digest,)).fetchone();connection.close()
    if not row:raise LookupError('secret_plan_not_found')
    return dict(row)


def get_plan(slug:str,plan_digest:str)->dict[str,Any]:
    plan=_plan(plan_digest);slug=str(slug or '').strip().lower()
    if plan['project_slug']!=slug:raise LookupError('secret_plan_not_found')
    definition=json.loads(plan['definition_json'] or '{}');source_secret_reference=str(definition.get('_cloudiffSourceSecretReference') or '')
    for key in tuple(definition):
        if str(key).startswith('_cloudiff'):definition.pop(key,None)
    return {
      'ok':True,'projectSlug':slug,'planDigest':plan['plan_digest'],'action':plan['action'],
      'environment':plan['environment'],'service':plan['service'],'name':plan['name'],
      'stageId':plan['stage_id'],'secretReference':plan['secret_reference'],'sourceSecretReference':source_secret_reference or None,
      'expectedRevision':int(plan['expected_revision']),'targetVersion':int(plan['target_version']),
      'definition':definition,'reason':plan['reason'],'status':plan['status'],
      'createdBy':plan['created_by'],'createdAt':int(plan['created_at']),'expiresAt':int(plan['expires_at']),
      'consumed':plan['status']=='applied','secretValueIncluded':False,'ciphertextIncluded':False,
    }


def _entry_matches_reference(plan:dict[str,Any])->bool:
    connection=db();row=connection.execute('select secret_reference from environment_entries where project_slug=? and environment=? and service=? and name=?',(plan['project_slug'],plan['environment'],plan['service'],plan['name'])).fetchone();connection.close()
    return bool(row and str(row['secret_reference'] or '')==str(plan['secret_reference']))


def apply_rotation(slug:str,plan_digest:str,stage_id:str,expected_revision:int,actor:str)->dict[str,Any]:
    init_db();plan=_plan(plan_digest);stage=_stage(stage_id);slug=str(slug or '').strip().lower()
    if plan['action']!='rotate' or plan['project_slug']!=slug or plan['stage_id']!=stage_id or int(plan['expected_revision'])!=int(expected_revision):raise PermissionError('secret_plan_binding_mismatch')
    if plan['status']=='applied' and stage['status']=='active':return {'ok':True,'idempotent':True,'projectSlug':slug,'secretReference':plan['secret_reference'],'version':plan['target_version'],'secretValueIncluded':False}
    if plan['status']!='planned' or int(plan['expires_at'])<=now():raise ValueError('secret_plan_expired_or_unavailable')
    if stage['status']!='staged' or int(stage['expires_at'])<=now():raise ValueError('secret_stage_expired_or_unavailable')
    if stage['project_slug']!=slug or stage['environment']!=plan['environment'] or stage['service']!=plan['service'] or stage['name']!=plan['name']:raise PermissionError('secret_stage_binding_mismatch')
    definition=json.loads(plan['definition_json'] or '{}');active_expires_at=int(definition.pop('_cloudiffSecretExpiresAt',2147483647) or 2147483647)
    change={'name':plan['name'],'service':plan['service'],'secret_reference':plan['secret_reference'],'definition':definition}
    applied_environment=False
    try:
        environment_plan=environment_store.plan_change(slug,plan['environment'],[change],int(expected_revision),actor,900)
        environment_store.apply_plan(slug,environment_plan['planDigest'],int(expected_revision),actor)
        applied_environment=True
    except ValueError as error:
        if str(error)!='environment_revision_mismatch' or not _entry_matches_reference(plan):raise
        applied_environment=True
    if not applied_environment:raise RuntimeError('secret_environment_binding_failed')
    timestamp=now();connection=db();connection.execute('begin immediate')
    current=connection.execute('select status from environment_secret_materials where stage_id=?',(stage_id,)).fetchone()
    if not current:connection.rollback();connection.close();raise LookupError('secret_stage_not_found')
    connection.execute("update environment_secret_materials set status='superseded',superseded_at=? where project_slug=? and environment=? and service=? and name=? and status='active'",(timestamp,slug,plan['environment'],plan['service'],plan['name']))
    connection.execute("update environment_secret_materials set status='active',version=?,secret_reference=?,activated_at=?,expires_at=? where stage_id=?",(int(plan['target_version']),plan['secret_reference'],timestamp,active_expires_at,stage_id))
    connection.execute("update environment_secret_plans set status='applied',applied_at=? where plan_digest=?",(timestamp,plan_digest))
    event_row={'project_slug':slug,'environment':plan['environment'],'service':plan['service'],'name':plan['name'],'version':int(plan['target_version']),'secret_reference':plan['secret_reference']}
    _event(connection,event_row,'rotated',actor,{'planDigest':plan_digest,'stageId':stage_id,'environmentRevision':_current_environment_revision(slug)})
    connection.commit();connection.close()
    return {'ok':True,'idempotent':False,'projectSlug':slug,'environment':plan['environment'],'service':plan['service'],'name':plan['name'],'secretReference':plan['secret_reference'],'version':int(plan['target_version']),'activeExpiresAt':active_expires_at,'environmentRevision':_current_environment_revision(slug),'restartRequired':bool(definition.get('restartRequired',definition.get('runtime',True))),'rebuildRequired':bool(definition.get('buildTime')),'secretValueIncluded':False,'ciphertextIncluded':False}


def promotion_plan(slug:str,source_secret_reference:str,target_environment:str,expected_revision:int,actor:str,reason:str,definition:dict[str,Any]|None=None,ttl_seconds:int=900,active_ttl_seconds:int=0)->dict[str,Any]:
    init_db();slug=str(slug or '').strip().lower();target_environment=str(target_environment or '').strip().lower();match=REFERENCE_RE.fullmatch(str(source_secret_reference or ''))
    if not match or match.group(1)!=slug:raise ValueError('invalid_secret_reference')
    if target_environment not in ENVIRONMENTS or target_environment==match.group(2):raise ValueError('invalid_target_environment')
    actual=_current_environment_revision(slug)
    if int(expected_revision)!=actual:raise ValueError('environment_revision_mismatch')
    connection=db();source=connection.execute("select * from environment_secret_materials where secret_reference=? and status='active' and expires_at>?",(source_secret_reference,now())).fetchone()
    if not source:connection.close();raise LookupError('active_secret_not_found')
    source=dict(source);version=_next_version(connection,slug,target_environment,source['service'],source['name']);connection.close()
    target_reference=f"cloudiff-secret://{slug}/{target_environment}/{source['service'] or 'project'}/{source['name']}/v{version}"
    created=now();expires=created+max(60,min(int(ttl_seconds),86400));active_ttl=max(0,min(int(active_ttl_seconds or 0),31536000));active_expires_at=(created+active_ttl) if active_ttl else 2147483647
    definition=dict(definition or {});definition.update({'secret':True,'exposeToClient':False});definition.pop('value',None);definition.pop('default',None);definition['_cloudiffSourceSecretReference']=source_secret_reference;definition['_cloudiffSourceMaterialDigest']=source['material_digest'];definition['_cloudiffSecretExpiresAt']=active_expires_at
    material={'kind':'secret-promotion-v1','projectSlug':slug,'sourceSecretReference':source_secret_reference,'sourceMaterialDigest':source['material_digest'],'sourceEnvironment':source['environment'],'targetEnvironment':target_environment,'service':source['service'],'name':source['name'],'expectedRevision':actual,'targetVersion':version,'targetSecretReference':target_reference,'activeExpiresAt':active_expires_at}
    plan_digest=digest(material)
    connection=db();connection.execute('insert or ignore into environment_secret_plans values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
        plan_digest,'promote',slug,target_environment,source['service'],source['name'],None,target_reference,actual,version,json.dumps(definition,ensure_ascii=False,separators=(',',':')),str(reason)[:500],'planned',str(actor)[:128],created,expires,None,
    ));connection.commit();connection.close()
    return {'ok':True,'sideEffectFree':True,'action':'promote','projectSlug':slug,'sourceEnvironment':source['environment'],'targetEnvironment':target_environment,'service':source['service'],'name':source['name'],'sourceSecretReference':source_secret_reference,'targetSecretReference':target_reference,'targetVersion':version,'expectedRevision':actual,'planDigest':plan_digest,'expiresAt':expires,'activeExpiresAt':active_expires_at,'approvalRequired':True,'secretValueIncluded':False,'ciphertextIncluded':False}


def apply_promotion(slug:str,plan_digest:str,source_secret_reference:str,expected_revision:int,actor:str)->dict[str,Any]:
    init_db();plan=_plan(plan_digest);slug=str(slug or '').strip().lower()
    if plan['action']!='promote' or plan['project_slug']!=slug or int(plan['expected_revision'])!=int(expected_revision):raise PermissionError('secret_plan_binding_mismatch')
    definition=json.loads(plan['definition_json'] or '{}');bound_source=str(definition.pop('_cloudiffSourceSecretReference',''));bound_digest=str(definition.pop('_cloudiffSourceMaterialDigest',''));active_expires_at=int(definition.pop('_cloudiffSecretExpiresAt',2147483647) or 2147483647)
    if not hmac.compare_digest(bound_source,str(source_secret_reference or '')):raise PermissionError('secret_plan_binding_mismatch')
    if plan['status']=='applied':return {'ok':True,'idempotent':True,'projectSlug':slug,'secretReference':plan['secret_reference'],'version':int(plan['target_version']),'secretValueIncluded':False}
    if plan['status']!='planned' or int(plan['expires_at'])<=now():raise ValueError('secret_plan_expired_or_unavailable')
    connection=db();source=connection.execute("select * from environment_secret_materials where secret_reference=? and project_slug=? and status='active' and expires_at>?",(source_secret_reference,slug,now())).fetchone();connection.close()
    if not source:raise LookupError('active_secret_not_found')
    source=dict(source)
    if not hmac.compare_digest(str(source['material_digest']),bound_digest):raise PermissionError('secret_source_changed')
    plaintext=_decrypt(source).encode();stage_id='stage_'+plan_digest[:24];created=now();aad={'stageId':stage_id,'projectSlug':slug,'environment':plan['environment'],'service':plan['service'],'name':plan['name'],'createdAt':created};aad_bytes=canonical(aad);key=_secure_key();nonce=os.urandom(12);ciphertext=AESGCM(key).encrypt(nonce,plaintext,aad_bytes);material_digest=hmac.new(key,aad_bytes+b'\x00'+plaintext,hashlib.sha256).hexdigest();plaintext=b''
    connection=db();connection.execute('begin immediate');existing=connection.execute('select * from environment_secret_materials where stage_id=?',(stage_id,)).fetchone()
    if not existing:
        connection.execute('insert into environment_secret_materials(stage_id,project_slug,environment,service,name,version,secret_reference,nonce_b64,ciphertext_b64,aad_json,material_digest,status,created_by,created_at,expires_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(stage_id,slug,plan['environment'],plan['service'],plan['name'],int(plan['target_version']),plan['secret_reference'],base64.b64encode(nonce).decode(),base64.b64encode(ciphertext).decode(),aad_bytes.decode(),material_digest,'staged',str(actor)[:128],created,int(plan['expires_at'])));connection.commit()
    else:connection.rollback()
    connection.close();definition.update({'secret':True,'exposeToClient':False})
    change={'name':plan['name'],'service':plan['service'],'secret_reference':plan['secret_reference'],'definition':definition}
    environment_plan=environment_store.plan_change(slug,plan['environment'],[change],int(expected_revision),actor,900);environment_store.apply_plan(slug,environment_plan['planDigest'],int(expected_revision),actor)
    timestamp=now();connection=db();connection.execute('begin immediate');connection.execute("update environment_secret_materials set status='superseded',superseded_at=? where project_slug=? and environment=? and service=? and name=? and status='active'",(timestamp,slug,plan['environment'],plan['service'],plan['name']));connection.execute("update environment_secret_materials set status='active',activated_at=?,expires_at=? where stage_id=?",(timestamp,active_expires_at,stage_id));connection.execute("update environment_secret_plans set status='applied',applied_at=? where plan_digest=?",(timestamp,plan_digest));row=connection.execute('select * from environment_secret_materials where stage_id=?',(stage_id,)).fetchone();_event(connection,dict(row),'promoted',actor,{'planDigest':plan_digest,'sourceSecretReference':source_secret_reference,'sourceEnvironment':source['environment'],'targetEnvironment':plan['environment']});connection.commit();connection.close()
    return {'ok':True,'idempotent':False,'projectSlug':slug,'sourceEnvironment':source['environment'],'targetEnvironment':plan['environment'],'service':plan['service'],'name':plan['name'],'secretReference':plan['secret_reference'],'version':int(plan['target_version']),'activeExpiresAt':active_expires_at,'environmentRevision':_current_environment_revision(slug),'secretValueIncluded':False,'ciphertextIncluded':False}


def read_plan(slug:str,secret_reference:str,actor:str,reason:str,ttl_seconds:int=300)->dict[str,Any]:
    init_db();slug=str(slug or '').strip().lower();match=REFERENCE_RE.fullmatch(str(secret_reference or ''))
    if not match or match.group(1)!=slug:raise ValueError('invalid_secret_reference')
    connection=db();row=connection.execute("select * from environment_secret_materials where secret_reference=? and project_slug=? and status='active' and expires_at>?",(secret_reference,slug,now())).fetchone();connection.close()
    if not row:raise LookupError('active_secret_not_found')
    row=dict(row);revision=_current_environment_revision(slug);created=now();expires=created+max(60,min(int(ttl_seconds),900))
    definition={'_cloudiffReadMaterialDigest':row['material_digest']}
    material={'kind':'secret-read-v1','projectSlug':slug,'environment':row['environment'],'service':row['service'],'name':row['name'],'secretReference':secret_reference,'materialDigest':row['material_digest'],'environmentRevision':revision}
    plan_digest=digest(material)
    connection=db();connection.execute('insert or ignore into environment_secret_plans values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
        plan_digest,'read',slug,row['environment'],row['service'],row['name'],None,secret_reference,revision,int(row['version']),json.dumps(definition,separators=(',',':')),str(reason)[:500],'planned',str(actor)[:128],created,expires,None,
    ));connection.commit();connection.close()
    return {'ok':True,'sideEffectFree':True,'action':'read','projectSlug':slug,'environment':row['environment'],'service':row['service'],'name':row['name'],'secretReference':secret_reference,'version':int(row['version']),'expectedRevision':revision,'planDigest':plan_digest,'expiresAt':expires,'approvalRequired':True,'criticalApproval':True,'oneTime':True,'secretValueIncluded':False,'ciphertextIncluded':False}


def read_once(slug:str,plan_digest:str,secret_reference:str,actor:str)->dict[str,Any]:
    init_db();plan=_plan(plan_digest);slug=str(slug or '').strip().lower()
    if plan['action']!='read' or plan['project_slug']!=slug or not hmac.compare_digest(str(plan['secret_reference'] or ''),str(secret_reference or '')):raise PermissionError('secret_plan_binding_mismatch')
    if plan['status']=='applied':raise PermissionError('secret_read_already_consumed')
    if plan['status']!='planned' or int(plan['expires_at'])<=now():raise ValueError('secret_plan_expired_or_unavailable')
    definition=json.loads(plan['definition_json'] or '{}');bound_digest=str(definition.get('_cloudiffReadMaterialDigest') or '')
    connection=db();row=connection.execute("select * from environment_secret_materials where secret_reference=? and project_slug=? and status='active' and expires_at>?",(secret_reference,slug,now())).fetchone();connection.close()
    if not row:raise LookupError('active_secret_not_found')
    row=dict(row)
    if not hmac.compare_digest(str(row['material_digest']),bound_digest):raise PermissionError('secret_material_changed')
    plaintext=_decrypt(row);timestamp=now();connection=db();connection.execute('begin immediate');fresh=connection.execute('select status from environment_secret_plans where plan_digest=?',(plan_digest,)).fetchone()
    if not fresh or fresh['status']!='planned':connection.rollback();connection.close();plaintext='';raise PermissionError('secret_read_already_consumed')
    connection.execute("update environment_secret_plans set status='applied',applied_at=? where plan_digest=? and status='planned'",(timestamp,plan_digest));_event(connection,row,'read-approved',actor,{'planDigest':plan_digest,'oneTime':True});connection.commit();connection.close()
    return {'ok':True,'projectSlug':slug,'environment':row['environment'],'service':row['service'],'name':row['name'],'secretReference':secret_reference,'version':int(row['version']),'secretValue':plaintext,'secretValueIncluded':True,'ciphertextIncluded':False,'oneTime':True,'cacheControl':'no-store','auditRecorded':True}


def revocation_plan(slug:str,secret_reference:str,expected_revision:int,actor:str,reason:str,ttl_seconds:int=900)->dict[str,Any]:
    init_db();slug=str(slug or '').strip().lower();match=REFERENCE_RE.fullmatch(str(secret_reference or ''))
    if not match or match.group(1)!=slug:raise ValueError('invalid_secret_reference')
    actual=_current_environment_revision(slug)
    if int(expected_revision)!=actual:raise ValueError('environment_revision_mismatch')
    connection=db();row=connection.execute("select * from environment_secret_materials where secret_reference=? and status='active'",(secret_reference,)).fetchone();connection.close()
    if not row:raise LookupError('active_secret_not_found')
    row=dict(row);created=now();expires=created+max(60,min(int(ttl_seconds),86400));material={'kind':'secret-revocation-v1','projectSlug':slug,'secretReference':secret_reference,'expectedRevision':actual,'version':row['version']};plan_digest=digest(material)
    connection=db();connection.execute('insert or ignore into environment_secret_plans values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
        plan_digest,'revoke',slug,row['environment'],row['service'],row['name'],None,secret_reference,actual,int(row['version']),'{}',str(reason)[:500],'planned',str(actor)[:128],created,expires,None,
    ));connection.commit();connection.close()
    return {'ok':True,'sideEffectFree':True,'action':'revoke','projectSlug':slug,'environment':row['environment'],'service':row['service'],'name':row['name'],'secretReference':secret_reference,'version':int(row['version']),'expectedRevision':actual,'planDigest':plan_digest,'expiresAt':expires,'approvalRequired':True,'configurationWillBecomeBlocked':True,'secretValueIncluded':False}


def apply_revocation(slug:str,plan_digest:str,secret_reference:str,expected_revision:int,actor:str)->dict[str,Any]:
    init_db();plan=_plan(plan_digest);slug=str(slug or '').strip().lower()
    if plan['action']!='revoke' or plan['project_slug']!=slug or plan['secret_reference']!=secret_reference or int(plan['expected_revision'])!=int(expected_revision):raise PermissionError('secret_plan_binding_mismatch')
    if plan['status']=='applied':return {'ok':True,'idempotent':True,'projectSlug':slug,'secretReference':secret_reference,'status':'revoked','secretValueIncluded':False}
    if plan['status']!='planned' or int(plan['expires_at'])<=now():raise ValueError('secret_plan_expired_or_unavailable')
    timestamp=now();connection=db();connection.execute('begin immediate');row=connection.execute("select * from environment_secret_materials where secret_reference=? and status='active'",(secret_reference,)).fetchone()
    if not row:connection.rollback();connection.close();raise LookupError('active_secret_not_found')
    row=dict(row);connection.execute("update environment_secret_materials set status='revoked',revoked_at=? where secret_reference=?",(timestamp,secret_reference));connection.execute("update environment_secret_plans set status='applied',applied_at=? where plan_digest=?",(timestamp,plan_digest));_event(connection,row,'revoked',actor,{'planDigest':plan_digest,'configurationStillReferencesSecret':True});connection.commit();connection.close()
    return {'ok':True,'idempotent':False,'projectSlug':slug,'environment':row['environment'],'service':row['service'],'name':row['name'],'secretReference':secret_reference,'version':int(row['version']),'status':'revoked','configurationBlocked':True,'secretValueIncluded':False}


def list_secrets(slug:str,environment:str='',service:str='')->dict[str,Any]:
    init_db();slug=str(slug or '').strip().lower();args=[slug];query='select * from environment_secret_materials where project_slug=?'
    if environment:query+=' and environment=?';args.append(str(environment).lower())
    if service:query+=' and service=?';args.append(str(service).lower())
    query+=' order by environment,service,name,version desc'
    connection=db();rows=connection.execute(query,tuple(args)).fetchall();connection.close();items=[]
    for raw in rows:
        row=dict(raw);derived_status=('expired' if row['status']=='active' and int(row['expires_at'] or 0)<=now() else row['status']);items.append({'stageId':row['stage_id'] if row['status']=='staged' else None,'projectSlug':row['project_slug'],'environment':row['environment'],'service':row['service'],'name':row['name'],'version':int(row['version']),'secretReference':row['secret_reference'],'status':derived_status,'createdBy':row['created_by'],'createdAt':row['created_at'],'expiresAt':row['expires_at'] if row['status']=='staged' else None,'activeExpiresAt':row['expires_at'] if row['status'] in {'active','superseded','revoked'} else None,'activatedAt':row['activated_at'],'revokedAt':row['revoked_at'],'materialDigest':row['material_digest'],'secretValueIncluded':False,'ciphertextIncluded':False})
    return {'ok':True,'projectSlug':slug,'secrets':items,'count':len(items),'secretValuesIncluded':False,'ciphertextsIncluded':False}


def history(slug:str,limit:int=100)->dict[str,Any]:
    init_db();slug=str(slug or '').strip().lower();limit=max(1,min(int(limit),500));connection=db();rows=connection.execute('select * from environment_secret_events where project_slug=? order by created_at desc limit ?',(slug,limit)).fetchall();connection.close();items=[]
    for raw in rows:
        row=dict(raw);items.append({'eventId':row['event_id'],'projectSlug':row['project_slug'],'environment':row['environment'],'service':row['service'],'name':row['name'],'action':row['action'],'secretReference':row['secret_reference'],'version':int(row['version']),'actor':row['actor'],'details':json.loads(row['details_json'] or '{}'),'createdAt':row['created_at'],'secretValueIncluded':False})
    return {'ok':True,'projectSlug':slug,'events':items,'count':len(items),'secretValuesIncluded':False}


# INTERNAL SECRET RESOLUTION ONLY
def resolve_internal(slug:str,environment:str,references:dict[str,dict[str,str]],actor:str='internal-resolver')->dict[str,Any]:
    init_db();slug=str(slug or '').strip().lower();environment=str(environment or '').strip().lower()
    if environment not in ENVIRONMENTS or not isinstance(references,dict):raise ValueError('invalid_secret_resolution_request')
    resolved:dict[str,dict[str,str]]={};connection=db()
    try:
        for service,values in references.items():
            if not isinstance(values,dict):raise ValueError('invalid_secret_resolution_request')
            resolved[str(service)]={}
            for name,reference in values.items():
                match=REFERENCE_RE.fullmatch(str(reference or ''))
                if not match or match.group(1)!=slug or match.group(2)!=environment or (match.group(3)!='project' and match.group(3)!=str(service)) or match.group(4)!=str(name):raise PermissionError('secret_reference_scope_mismatch')
                row=connection.execute("select * from environment_secret_materials where secret_reference=? and project_slug=? and environment=? and status='active' and expires_at>?",(reference,slug,environment,now())).fetchone()
                if not row:raise LookupError('active_secret_not_found:'+str(name))
                resolved[str(service)][str(name)]=_decrypt(dict(row))
    finally:connection.close()
    audit=db();audit.execute('begin immediate')
    for service,values in references.items():
        for name,reference in values.items():
            row=audit.execute('select * from environment_secret_materials where secret_reference=?',(reference,)).fetchone()
            if row:_event(audit,dict(row),'resolved-internal',actor,{'environment':environment,'service':service,'reason':'runtime-injection'})
    audit.commit();audit.close()
    return {'ok':True,'internal':True,'projectSlug':slug,'environment':environment,'resolvedSecrets':resolved,'count':sum(len(values) for values in resolved.values()),'secretValuesIncluded':True,'auditRequired':True}


def _decrypt(row:dict[str,Any])->str:
    key=_secure_key();nonce=base64.b64decode(row['nonce_b64']);ciphertext=base64.b64decode(row['ciphertext_b64']);aad=str(row['aad_json']).encode();plaintext=AESGCM(key).decrypt(nonce,ciphertext,aad)
    return plaintext.decode('utf-8')
