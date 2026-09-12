#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST=os.environ.get('CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_HOST','10.62.91.2')
PORT=int(os.environ.get('CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_PORT','18230'))
TOKEN=(os.environ.get('CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_TOKEN') or '').strip()
DB_PATH=Path(os.environ.get('CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_DB','/var/lib/cloudif/multiservice-deployment-executor/deployments.db'))
RUN_DIR=Path(os.environ.get('CLOUDIF_MULTISERVICE_DEPLOYMENT_RUN_DIR','/run/cloudif-multiservice-deployment'))
MAX_BODY=2*1024*1024
MAX_SERVICES=16
DEPLOYMENT_RE=re.compile(r'^dep_[a-f0-9]{24}$')
BUILD_RE=re.compile(r'^build_[a-f0-9]{24}$')
SLUG_RE=re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
SERVICE_RE=re.compile(r'^[a-z][a-z0-9-]{0,31}$')
IMAGE_RE=re.compile(r'^sha256:[a-f0-9]{64}$')
SHA_RE=re.compile(r'^[a-f0-9]{64}$')
ENV_NAME_RE=re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,127}$')
ENVIRONMENTS={'homologation','production'}
MONGODB_IMAGE_ID='sha256:2ef525f154744fbbe650043a9c6a1097d8e0f299db6ef7695e05e81d0b620dde'
MONGODB_IMAGE_REF='cgr.dev/chainguard/mongodb@sha256:2ef525f154744fbbe650043a9c6a1097d8e0f299db6ef7695e05e81d0b620dde'
MONGODB_VARIABLE_KEYS={'host','port','database','username','password'}
MONGODB_MEMORY_LIMIT='768m'
PUBLICATION_NETWORK='cloudif-publications'
PUBLICATION_BRIDGE_IMAGE_ID='sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10'
PUBLICATION_BRIDGE_IMAGE_REF='nginx@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10'
PUBLICATION_BRIDGE_ROOT=Path(os.environ.get('CLOUDIF_MULTISERVICE_DEPLOYMENT_BRIDGE_DIR','/var/lib/cloudif/multiservice-deployment-executor/bridges'))
COMPOSE_SNAPSHOT_ROOT=Path(os.environ.get('CLOUDIF_COMPOSE_SNAPSHOT_ROOT',str(DB_PATH.parent/'compose-snapshots')))
COMPOSE_RUNTIME_ROOT=Path(os.environ.get('CLOUDIF_COMPOSE_RUNTIME_ROOT',str(DB_PATH.parent/'compose-runtime')))
COMPOSE_SNAPSHOT_RE=re.compile(r'^snap_[a-f0-9]{24}$')
COMPOSE_SNAPSHOT_MAX_BYTES=int(os.environ.get('CLOUDIF_COMPOSE_SNAPSHOT_MAX_BYTES',str(16*1024*1024*1024)))
COMPOSE_EPHEMERAL_PREFIXES=('/run','/tmp','/var/run','/var/cache','/var/log')
COMPOSE_DANGEROUS_CAPS={'SYS_ADMIN','SYS_MODULE','SYS_PTRACE','NET_ADMIN','DAC_READ_SEARCH','SYS_RAWIO'}


class DeploymentError(RuntimeError):
    def __init__(self,code:str,message:str,status:int=422,detail:Any=None):
        super().__init__(code);self.code=code;self.message=message;self.status=status;self.detail=detail
    def as_dict(self):
        out={'code':self.code,'message':self.message,'documentation':'multiservice-deployment-v1'}
        if self.detail is not None:out['detail']=self.detail
        return out


def canonical(value:Any)->bytes:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()


def db()->sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(DB_PATH,timeout=20);conn.row_factory=sqlite3.Row
    conn.execute('pragma busy_timeout=20000')
    return conn


def init_db():
    conn=db();conn.execute('pragma journal_mode=delete')
    conn.executescript('''
    create table if not exists deployments(
      deployment_id text primary key,
      project_slug text not null,
      environment text not null,
      build_job_id text not null,
      plan_digest text not null,
      build_plan_digest text not null,
      config_revision integer not null,
      config_digest text not null,
      toolchain_digest text not null,
      archive_sha256 text not null,
      variables_digest text not null,
      status text not null,
      services_json text not null,
      routes_json text not null,
      error_json text not null default '{}',
      created_at integer not null,
      updated_at integer not null
    );
    create index if not exists idx_deployments_project on deployments(project_slug,environment,status,updated_at);
    create table if not exists runtime_states(
      project_slug text not null,
      environment text not null,
      deployment_id text not null,
      status text not null,
      config_revision integer not null,
      config_digest text not null,
      toolchain_digest text not null,
      build_environment_digest text not null,
      runtime_environment_digest text not null,
      environment_digest text not null,
      build_job_id text not null,
      variable_names_json text not null,
      updated_at integer not null,
      primary key(project_slug,environment)
    );
    create table if not exists compose_snapshots(
      snapshot_id text primary key,
      project_slug text not null,
      source_digest text not null,
      snapshot_digest text not null,
      source_commit text not null,
      edge_service text not null,
      edge_port integer not null,
      manifest_json text not null,
      status text not null,
      created_at integer not null
    );
    create index if not exists idx_compose_snapshots_project on compose_snapshots(project_slug,created_at desc);
    ''')
    cols={row[1] for row in conn.execute('pragma table_info(deployments)')}
    if 'snapshot_id' not in cols:conn.execute("alter table deployments add column snapshot_id text not null default ''")
    conn.commit();conn.close();os.chmod(DB_PATH,0o600)


def run(command:list[str],timeout:int=90)->subprocess.CompletedProcess:
    safe=list(command);child_env=os.environ.copy();index=0
    while index<len(safe):
        if safe[index]=='--env' and index+1<len(safe) and '=' in str(safe[index+1]):
            name,value=str(safe[index+1]).split('=',1)
            if not ENV_NAME_RE.fullmatch(name):raise DeploymentError('invalid_environment_name','Nome de variável de ambiente inválido.')
            child_env[name]=value;safe[index+1]=name
        elif str(safe[index]).startswith('--env=') and '=' in str(safe[index])[6:]:
            name,value=str(safe[index])[6:].split('=',1)
            if not ENV_NAME_RE.fullmatch(name):raise DeploymentError('invalid_environment_name','Nome de variável de ambiente inválido.')
            child_env[name]=value;safe[index]='--env='+name
        index+=1
    if isinstance(command,list):command[:]=safe
    return subprocess.run(safe,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,env=child_env)

def docker(*args:str,timeout:int=90,check:bool=True)->subprocess.CompletedProcess:
    result=run(['docker',*args],timeout=timeout)
    if check and result.returncode:
        raise DeploymentError('docker_operation_failed','A operação Docker do deploy falhou.',502,{'operation':args[:3],'error':result.stderr[-500:]})
    return result


def docker_host_env(environment:dict[str,str],*args:str,timeout:int=60,check:bool=True)->subprocess.CompletedProcess:
    child=os.environ.copy();child.update({str(key):str(value) for key,value in environment.items()})
    result=subprocess.run(['docker',*args],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,env=child)
    if check and result.returncode:
        raise DeploymentError('docker_operation_failed','A operação Docker da dependência falhou.',502,{'operation':args[:3],'error':result.stderr[-500:]})
    return result


def inspect_image(image_id:str)->dict:
    result=docker('image','inspect',image_id,timeout=30)
    rows=json.loads(result.stdout)
    if not rows:raise DeploymentError('image_not_found','A imagem do build não existe no executor.',404)
    return rows[0]


def normalize_route(item:Any,index:int,services:set[str])->dict:
    if not isinstance(item,dict):raise DeploymentError('invalid_route','Cada rota deve ser um objeto.',detail={'index':index})
    prefix=str(item.get('pathPrefix') or '').strip();service=str(item.get('service') or '').strip();strip=bool(item.get('stripPrefix',False))
    if not prefix.startswith('/') or '..' in prefix or '//' in prefix or len(prefix)>128:
        raise DeploymentError('invalid_route_prefix','A rota deve começar com / e não pode conter .. ou //.',detail={'index':index})
    if len(prefix)>1:prefix=prefix.rstrip('/')
    if service not in services:raise DeploymentError('route_service_not_found','A rota aponta para serviço inexistente.',detail={'index':index,'service':service})
    return {'pathPrefix':prefix,'service':service,'stripPrefix':strip}


def normalize_variables(value:Any,services:set[str])->dict[str,dict[str,str]]:
    if not isinstance(value,dict):raise DeploymentError('invalid_variables','variables deve ser um objeto por serviço.')
    result={}
    for service,raw in value.items():
        if service not in services or not isinstance(raw,dict):raise DeploymentError('invalid_service_variables','Variáveis apontam para serviço inexistente.',detail={'service':service})
        if len(raw)>128:raise DeploymentError('variable_limit_exceeded','Cada serviço aceita até 128 variáveis.')
        normalized={}
        for name,item in raw.items():
            name=str(name)
            if not ENV_NAME_RE.fullmatch(name):raise DeploymentError('invalid_variable_name','Nome de variável inválido.',detail={'service':service,'name':name})
            text=str(item)
            if len(text)>16384 or '\x00' in text or '\n' in text or '\r' in text:raise DeploymentError('invalid_variable_value','Valor de variável incompatível.',detail={'service':service,'name':name})
            normalized[name]=text
        result[service]=normalized
    for service in services:result.setdefault(service,{})
    return result


def normalize_dependencies(value:Any,services:set[str],variables:dict[str,dict[str,str]])->list[dict]:
    if value is None:return []
    if not isinstance(value,list) or len(value)>8:raise DeploymentError('invalid_dependencies','dependencies deve conter até oito dependências.')
    result=[];names=set()
    for index,raw in enumerate(value):
        if not isinstance(raw,dict):raise DeploymentError('invalid_dependency','Dependência gerenciada inválida.',detail={'index':index})
        required={'kind','name','service','database','username','variableMap','persistent'}
        if set(raw)!=required:raise DeploymentError('invalid_dependency','Dependência gerenciada contém campos ausentes ou não reconhecidos.',detail={'index':index})
        kind=str(raw.get('kind') or '');name=str(raw.get('name') or '');service=str(raw.get('service') or '');database=str(raw.get('database') or '');username=str(raw.get('username') or '');mapping=raw.get('variableMap') or {}
        if kind!='mongodb':raise DeploymentError('dependency_kind_not_approved','Somente dependências homologadas podem entrar no deploy.',detail={'kind':kind})
        if raw.get('persistent') is not True:raise DeploymentError('dependency_must_be_persistent','Dependência de homologação/publicação deve ser persistente.',409,{'name':name})
        if not SERVICE_RE.fullmatch(name) or name in services or name in names:raise DeploymentError('invalid_dependency_name','Nome de dependência inválido ou colide com serviço.',detail={'name':name})
        if service not in services:raise DeploymentError('dependency_service_not_found','A dependência aponta para serviço inexistente.',detail={'service':service})
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,62}',database):raise DeploymentError('invalid_dependency_database','Nome de banco gerenciado inválido.')
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,62}',username):raise DeploymentError('invalid_dependency_username','Usuário de banco gerenciado inválido.')
        if not isinstance(mapping,dict) or set(mapping)!=MONGODB_VARIABLE_KEYS:raise DeploymentError('invalid_dependency_variable_map','O binding MongoDB exige host, port, database, username e password.')
        normalized_map={str(role):str(var) for role,var in mapping.items()}
        if any(not ENV_NAME_RE.fullmatch(var) for var in normalized_map.values()) or len(set(normalized_map.values()))!=5:raise DeploymentError('invalid_dependency_variable_name','Bindings MongoDB possuem nomes inválidos ou duplicados.')
        target=variables.get(service) or {};password_name=normalized_map['password']
        if not str(target.get(password_name) or ''):raise DeploymentError('dependency_password_missing','A senha da dependência deve vir de secretRef resolvida.',409,{'name':name,'variable':password_name})
        generated={normalized_map[role] for role in ('host','port','database','username')};collisions=sorted(generated&set(target))
        if collisions:raise DeploymentError('dependency_variable_collision','Bindings gerados da dependência colidem com variáveis aprovadas.',409,{'name':name,'variables':collisions})
        names.add(name);result.append({'kind':'mongodb','name':name,'service':service,'database':database,'username':username,'variableMap':normalized_map,'persistent':True})
    return sorted(result,key=lambda item:item['name'])


def normalize_payload(payload:Any)->dict:
    if not isinstance(payload,dict):raise DeploymentError('invalid_request','A solicitação deve ser um objeto.',400)
    required={'deployment_id','project_slug','environment','build_job_id','deployment_plan_digest','build_plan_digest','config_revision','config_digest','toolchain_digest','archive_sha256','applications','routes','variables','variables_digest'}
    if not required.issubset(payload):raise DeploymentError('required_field_missing','Campos obrigatórios estão ausentes.',400,{'missing':sorted(required-set(payload))})
    deployment_id=str(payload.get('deployment_id') or '');slug=str(payload.get('project_slug') or '');environment=str(payload.get('environment') or '');build_job=str(payload.get('build_job_id') or '')
    plan=str(payload.get('deployment_plan_digest') or '').lower();build_plan=str(payload.get('build_plan_digest') or '').lower();config_revision=int(payload.get('config_revision') or 0);config_digest=str(payload.get('config_digest') or '').lower();toolchain_digest=str(payload.get('toolchain_digest') or '').lower();archive=str(payload.get('archive_sha256') or '').lower();variables_digest=str(payload.get('variables_digest') or '').lower()
    if not DEPLOYMENT_RE.fullmatch(deployment_id):raise DeploymentError('invalid_deployment_id','deployment_id é inválido.',400)
    if not SLUG_RE.fullmatch(slug):raise DeploymentError('invalid_project_slug','project_slug é inválido.',400)
    if environment not in ENVIRONMENTS:raise DeploymentError('invalid_environment','environment deve ser homologation ou production.',400)
    if not BUILD_RE.fullmatch(build_job):raise DeploymentError('invalid_build_job_id','build_job_id é inválido.',400)
    for name,value in {'deployment_plan_digest':plan,'build_plan_digest':build_plan,'config_digest':config_digest,'toolchain_digest':toolchain_digest,'archive_sha256':archive,'variables_digest':variables_digest}.items():
        if not SHA_RE.fullmatch(value):raise DeploymentError('invalid_digest',f'{name} é inválido.',400)
    if config_revision<1:raise DeploymentError('configuration_required','O deploy exige uma revisão aprovada.')
    applications=payload.get('applications')
    if not isinstance(applications,list) or not 1<=len(applications)<=MAX_SERVICES:raise DeploymentError('invalid_applications','applications deve conter entre 1 e 16 serviços.')
    normalized=[];names=set()
    for index,raw in enumerate(applications):
        if not isinstance(raw,dict):raise DeploymentError('invalid_application','Cada aplicação deve ser um objeto.',detail={'index':index})
        service=str(raw.get('service') or '');image=str(raw.get('image_id') or '');digest=str(raw.get('application_digest') or '').lower();port=int(raw.get('port') or 0);health=str(raw.get('healthcheck') or '/')
        if not SERVICE_RE.fullmatch(service) or service in names:raise DeploymentError('invalid_service_name','Nome de serviço inválido ou duplicado.',detail={'index':index})
        names.add(service)
        if not IMAGE_RE.fullmatch(image):raise DeploymentError('invalid_image_id','O deploy aceita somente imageId sha256.',detail={'service':service})
        if not SHA_RE.fullmatch(digest):raise DeploymentError('invalid_application_digest','application_digest é inválido.',detail={'service':service})
        if not 1024<=port<=65535:raise DeploymentError('invalid_container_port','A porta interna deve estar entre 1024 e 65535.',detail={'service':service})
        if not health.startswith('/') or '..' in health or len(health)>256:raise DeploymentError('invalid_healthcheck','healthcheck deve ser um caminho HTTP relativo.',detail={'service':service})
        normalized.append({'service':service,'image_id':image,'application_digest':digest,'port':port,'healthcheck':health})
    routes=payload.get('routes')
    if not isinstance(routes,list) or not routes:raise DeploymentError('routes_required','O deploy exige ao menos uma rota.')
    normalized_routes=[normalize_route(item,index,names) for index,item in enumerate(routes)]
    prefixes=[item['pathPrefix'] for item in normalized_routes]
    if len(prefixes)!=len(set(prefixes)) or '/' not in prefixes:raise DeploymentError('invalid_routes','Rotas duplicadas ou sem rota raiz.')
    variables=normalize_variables(payload.get('variables'),names)
    calculated=hashlib.sha256(canonical(variables)).hexdigest()
    if not hmac.compare_digest(calculated,variables_digest):raise DeploymentError('variables_digest_mismatch','As variáveis mudaram após a aprovação.',409)
    dependencies=normalize_dependencies(payload.get('dependencies'),names,variables)
    return {'deployment_id':deployment_id,'project_slug':slug,'environment':environment,'build_job_id':build_job,'deployment_plan_digest':plan,'build_plan_digest':build_plan,'config_revision':config_revision,'config_digest':config_digest,'toolchain_digest':toolchain_digest,'archive_sha256':archive,'applications':normalized,'routes':sorted(normalized_routes,key=lambda x:len(x['pathPrefix']),reverse=True),'dependencies':dependencies,'variables':variables,'variables_digest':variables_digest}


def validate_image_labels(request:dict,app:dict)->dict:
    data=inspect_image(app['image_id']);config=data.get('Config') or {};labels=config.get('Labels') or {}
    expected={'org.cloudiff.kind':'application','org.cloudiff.project':request['project_slug'],'org.cloudiff.service':app['service'],'org.cloudiff.config-revision':str(request['config_revision']),'org.cloudiff.config-digest':request['config_digest'],'org.cloudiff.toolchain-digest':request['toolchain_digest'],'org.cloudiff.archive-sha256':request['archive_sha256'],'org.cloudiff.application-digest':app['application_digest']}
    mismatch={key:{'expected':value,'actual':labels.get(key)} for key,value in expected.items() if str(labels.get(key) or '')!=str(value)}
    if mismatch:raise DeploymentError('image_label_mismatch','A imagem não corresponde ao projeto, revisão ou archive aprovados.',409,{'service':app['service'],'mismatch':mismatch})
    user=str(config.get('User') or '')
    if user in {'','0','root','0:0'}:raise DeploymentError('image_user_policy_failed','A imagem não pode executar como root.',409,{'service':app['service'],'user':user})
    return {'image_id':data.get('Id'),'user':user,'labels':expected}


def network_name(deployment_id:str)->str:return 'cloudif-'+deployment_id.replace('_','-')
def egress_network_name(deployment_id:str)->str:return network_name(deployment_id)+'-egress'
def container_name(deployment_id:str,service:str)->str:return 'cloudif-'+deployment_id.replace('_','-')+'-'+service


def managed_dependency_container_name(project_slug:str,environment:str,name:str)->str:
    return 'cloudif-managed-'+project_slug+'-'+environment+'-'+name


def managed_dependency_volume_name(project_slug:str,environment:str,name:str)->str:
    return 'cloudif-data-'+project_slug+'-'+environment+'-'+name


def wait_mongodb(container:str,deadline:float)->None:
    command=['exec',container,'/usr/bin/mongo','--quiet','--host','127.0.0.1','--port','27017','--eval','db.runCommand({ping:1}).ok']
    last='not-ready'
    while time.time()<deadline:
        result=docker(*command,timeout=10,check=False)
        if result.returncode==0 and '1' in result.stdout:return
        last=(result.stderr or result.stdout)[-200:];time.sleep(1)
    raise DeploymentError('dependency_healthcheck_failed','MongoDB gerenciado não ficou pronto.',409,{'kind':'mongodb','status':last})


def _mongo_auth(container:str,database:str,username:str,password:str)->None:
    script="const d=db.getSiblingDB(_getEnv('CLOUDIF_MONGO_DATABASE'));if(!d.auth(_getEnv('CLOUDIF_MONGO_USER'),_getEnv('CLOUDIF_MONGO_PASSWORD')))throw new Error('application auth failed');if(d.runCommand({ping:1}).ok!==1)throw new Error('ping failed');"
    result=docker_host_env({'CLOUDIF_MONGO_DATABASE':database,'CLOUDIF_MONGO_USER':username,'CLOUDIF_MONGO_PASSWORD':password},'exec','--env','CLOUDIF_MONGO_DATABASE','--env','CLOUDIF_MONGO_USER','--env','CLOUDIF_MONGO_PASSWORD',container,'/usr/bin/mongo','--quiet','--host','127.0.0.1','--port','27017','--eval',script,timeout=30,check=False)
    if result.returncode:raise DeploymentError('dependency_credentials_mismatch','A credencial aprovada não autentica no MongoDB persistente.',409,{'kind':'mongodb','database':database,'username':username})


def ensure_mongodb_dependency(request:dict,network:str,dependency:dict)->tuple[dict,dict[str,str]]:
    data=inspect_image(MONGODB_IMAGE_REF);config=data.get('Config') or {}
    if str(data.get('Id') or '')!=MONGODB_IMAGE_ID or str(config.get('User') or '')!='65532':raise DeploymentError('dependency_image_validation_failed','MongoDB gerenciado diverge da imagem homologada.',409)
    container=managed_dependency_container_name(request['project_slug'],request['environment'],dependency['name']);volume=managed_dependency_volume_name(request['project_slug'],request['environment'],dependency['name'])
    expected_labels={'org.cloudiff.managed-dependency':'mongodb','org.cloudiff.project':request['project_slug'],'org.cloudiff.environment':request['environment'],'org.cloudiff.dependency':dependency['name'],'org.cloudiff.database':dependency['database'],'org.cloudiff.username':dependency['username']}
    volume_result=docker('volume','inspect',volume,timeout=30,check=False);created_volume=volume_result.returncode!=0
    if created_volume:
        args=['volume','create']
        for key,value in expected_labels.items():args.extend(['--label',key+'='+value])
        args.append(volume);docker(*args,timeout=30)
    else:
        rows=json.loads(volume_result.stdout or '[]');labels=((rows[0] if rows else {}).get('Labels') or {})
        mismatch={key:{'expected':value,'actual':labels.get(key)} for key,value in expected_labels.items() if str(labels.get(key) or '')!=value}
        if mismatch:raise DeploymentError('dependency_volume_mismatch','Volume persistente não corresponde ao projeto/ambiente aprovados.',409,{'name':dependency['name'],'mismatch':mismatch})
    inspect=docker('inspect',container,timeout=30,check=False);created_container=inspect.returncode!=0
    if created_container:
        command=['run','-d','--name',container,'--user','65532:65532','--network',network,'--network-alias',dependency['name'],'--restart','unless-stopped','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=32m,uid=65532,gid=65532,mode=1777','--mount',f'type=volume,src={volume},dst=/data/db','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256','--memory',MONGODB_MEMORY_LIMIT,'--cpus','0.5']
        for key,value in expected_labels.items():command.extend(['--label',key+'='+value])
        command.extend([MONGODB_IMAGE_REF,'--auth','--bind_ip_all','--port','27017','--dbpath','/data/db','--quiet'])
        container_id=docker(*command,timeout=120).stdout.strip()
    else:
        rows=json.loads(inspect.stdout or '[]');row=rows[0] if rows else {};labels=(row.get('Config') or {}).get('Labels') or {};mismatch={key:{'expected':value,'actual':labels.get(key)} for key,value in expected_labels.items() if str(labels.get(key) or '')!=value}
        mounts=row.get('Mounts') or [];volume_ok=any(item.get('Type')=='volume' and item.get('Name')==volume and item.get('Destination')=='/data/db' for item in mounts)
        if str(row.get('Image') or '')!=MONGODB_IMAGE_ID or mismatch or not volume_ok:raise DeploymentError('dependency_container_mismatch','Container MongoDB persistente diverge do contrato aprovado.',409,{'name':dependency['name'],'labelsMismatch':mismatch,'volumeMatch':volume_ok})
        container_id=str(row.get('Id') or '')
        if not bool((row.get('State') or {}).get('Running')):docker('start',container,timeout=60)
        networks=((row.get('NetworkSettings') or {}).get('Networks') or {})
        if network not in networks:docker('network','connect','--alias',dependency['name'],network,container,timeout=30)
    wait_mongodb(container,time.time()+60)
    password_name=dependency['variableMap']['password'];password=str(request['variables'][dependency['service']][password_name])
    if created_volume:
        admin_password=secrets.token_urlsafe(48)
        create_admin="db.getSiblingDB('admin').createUser({user:'cloudif_admin',pwd:_getEnv('CLOUDIF_MONGO_ADMIN_PASSWORD'),roles:[{role:'userAdminAnyDatabase',db:'admin'}]});"
        try:
            docker_host_env({'CLOUDIF_MONGO_ADMIN_PASSWORD':admin_password},'exec','--env','CLOUDIF_MONGO_ADMIN_PASSWORD',container,'/usr/bin/mongo','--quiet','--host','127.0.0.1','--port','27017','--eval',create_admin,timeout=30)
            create_user="const a=db.getSiblingDB('admin');if(!a.auth('cloudif_admin',_getEnv('CLOUDIF_MONGO_ADMIN_PASSWORD')))throw new Error('admin auth failed');db.getSiblingDB(_getEnv('CLOUDIF_MONGO_DATABASE')).createUser({user:_getEnv('CLOUDIF_MONGO_USER'),pwd:_getEnv('CLOUDIF_MONGO_PASSWORD'),roles:[{role:'readWrite',db:_getEnv('CLOUDIF_MONGO_DATABASE')}]});"
            docker_host_env({'CLOUDIF_MONGO_ADMIN_PASSWORD':admin_password,'CLOUDIF_MONGO_DATABASE':dependency['database'],'CLOUDIF_MONGO_USER':dependency['username'],'CLOUDIF_MONGO_PASSWORD':password},'exec','--env','CLOUDIF_MONGO_ADMIN_PASSWORD','--env','CLOUDIF_MONGO_DATABASE','--env','CLOUDIF_MONGO_USER','--env','CLOUDIF_MONGO_PASSWORD',container,'/usr/bin/mongo','--quiet','--host','127.0.0.1','--port','27017','--eval',create_user,timeout=30)
        finally:admin_password=''
    _mongo_auth(container,dependency['database'],dependency['username'],password)
    mapping=dependency['variableMap'];bindings={mapping['host']:dependency['name'],mapping['port']:'27017',mapping['database']:dependency['database'],mapping['username']:dependency['username']}
    safe={'kind':'mongodb','name':dependency['name'],'service':dependency['service'],'database':dependency['database'],'username':dependency['username'],'image_id':MONGODB_IMAGE_ID,'container_name':container,'container_id':container_id,'volume_name':volume,'user':'65532','port':27017,'published_ports':[],'persistent':True,'variable_names':sorted(mapping.values()),'created_container':created_container,'created_volume':created_volume}
    return safe,bindings


def publication_bridge_name(public_number:int,stage:str,number:int)->str:
    if not (1<=int(public_number)<=999999999 and 1<=int(number)<=999999):raise DeploymentError('invalid_publication_number','Número de publicação inválido.',400)
    stage=str(stage or '').strip().lower()
    if stage=='homologation':return f'cloudif-p{int(public_number)}-d{int(number)}-web'
    if stage=='publication':return f'cloudif-p{int(public_number)}-p{int(number)}-publication-web'
    raise DeploymentError('invalid_publication_stage','Estágio de publicação inválido.',400)


def _publication_bridge_config(status:dict)->str:
    services={str(item.get('service') or ''):int(item.get('port') or 0) for item in status.get('services') or []}
    routes=status.get('routes') or []
    if not services or not routes:raise DeploymentError('publication_bridge_contract_invalid','Deploy sem serviços ou rotas para publicação.',409)
    lines=['pid /tmp/nginx.pid;','worker_processes 1;','events { worker_connections 256; }','http {','  access_log off;','  error_log /dev/stderr warn;','  client_body_temp_path /tmp/client_temp;','  proxy_temp_path /tmp/proxy_temp;','  fastcgi_temp_path /tmp/fastcgi_temp;','  uwsgi_temp_path /tmp/uwsgi_temp;','  scgi_temp_path /tmp/scgi_temp;','  client_max_body_size 16m;','  server {','    listen 80;','    location = /__cloudif_bridge_health { default_type application/json; return 200 \'{"ok":true,"service":"cloudif-publication-bridge"}\'; }']
    common=['      proxy_http_version 1.1;','      proxy_set_header Host $host;','      proxy_set_header X-Real-IP $remote_addr;','      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;','      proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;','      proxy_set_header Upgrade $http_upgrade;','      proxy_set_header Connection "upgrade";']
    for route in sorted(routes,key=lambda item:len(str(item.get('pathPrefix') or '')),reverse=True):
        prefix=str(route.get('pathPrefix') or '');service=str(route.get('service') or '');strip=bool(route.get('stripPrefix',False));port=services.get(service,0)
        if not prefix.startswith('/') or service not in services or port<1:raise DeploymentError('publication_bridge_route_invalid','Rota de publicação inválida.',409)
        target=f'http://{service}:{port}'
        if prefix=='/':
            lines.append('    location / {');lines.extend(common);lines.append(f'      proxy_pass {target};');lines.append('    }');continue
        exact=prefix.rstrip('/');lines.append(f'    location = {exact} {{');lines.extend(common);lines.append(f'      proxy_pass {target}/;' if strip else f'      proxy_pass {target};');lines.append('    }')
        lines.append(f'    location ^~ {exact}/ {{');lines.extend(common);lines.append(f'      proxy_pass {target}/;' if strip else f'      proxy_pass {target};');lines.append('    }')
    lines.extend(['  }','}']);return '\n'.join(lines)+'\n'


def ensure_publication_bridge(payload:Any)->dict:
    if not isinstance(payload,dict) or set(payload)!={'project_slug','deployment_id','public_number','stage','number'}:raise DeploymentError('invalid_publication_bridge_request','Pedido de bridge inválido.',400)
    slug=str(payload.get('project_slug') or '').strip().lower();deployment_id=str(payload.get('deployment_id') or '');stage=str(payload.get('stage') or '').strip().lower();public_number=int(payload.get('public_number') or 0);number=int(payload.get('number') or 0)
    if not SLUG_RE.fullmatch(slug) or not DEPLOYMENT_RE.fullmatch(deployment_id):raise DeploymentError('invalid_publication_bridge_request','Pedido de bridge inválido.',400)
    status=status_deployment(deployment_id)
    expected_environment='homologation' if stage=='homologation' else 'production' if stage=='publication' else ''
    if status.get('status')!='running' or status.get('project_slug')!=slug or status.get('environment')!=expected_environment:raise DeploymentError('publication_bridge_deployment_mismatch','Deploy não corresponde ao estágio de publicação.',409)
    image=inspect_image(PUBLICATION_BRIDGE_IMAGE_REF)
    if str(image.get('Id') or '')!=PUBLICATION_BRIDGE_IMAGE_ID:raise DeploymentError('publication_bridge_image_mismatch','Imagem do bridge diverge do digest homologado.',409)
    name=publication_bridge_name(public_number,stage,number);network=network_name(deployment_id);root=PUBLICATION_BRIDGE_ROOT/name;config=root/'nginx.conf';root.mkdir(parents=True,exist_ok=True);config.write_text(_publication_bridge_config(status));os.chmod(config,0o644)
    labels={'org.cloudiff.publication-bridge':'true','org.cloudiff.project':slug,'org.cloudiff.deployment':deployment_id,'org.cloudiff.public-number':str(public_number),'org.cloudiff.stage':stage,'org.cloudiff.stage-number':str(number)}
    existing=docker('inspect',name,timeout=30,check=False)
    if existing.returncode==0:
        row=(json.loads(existing.stdout or '[]') or [{}])[0];current=(row.get('Config') or {}).get('Labels') or {}
        if any(str(current.get(k) or '')!=v for k,v in labels.items()) or str(row.get('Image') or '')!=PUBLICATION_BRIDGE_IMAGE_ID:raise DeploymentError('publication_bridge_conflict','Bridge existente diverge do deployment aprovado.',409)
        if not bool((row.get('State') or {}).get('Running')):docker('start',name,timeout=30)
        return {'ok':True,'bridge':name,'deployment_id':deployment_id,'public_number':public_number,'stage':stage,'number':number,'image_id':PUBLICATION_BRIDGE_IMAGE_ID,'published_ports':[],'read_only':True,'user':'101:101','capabilities':['NET_BIND_SERVICE'],'idempotent':True}
    command=['run','-d','--name',name,'--user','101:101','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=32m,uid=101,gid=101,mode=1777','--cap-drop','ALL','--cap-add','NET_BIND_SERVICE','--security-opt','no-new-privileges','--pids-limit','128','--memory','128m','--cpus','0.25','--restart','unless-stopped','--network',network]
    for k,v in labels.items():command.extend(['--label',k+'='+v])
    command.extend(['--mount',f'type=bind,src={config},dst=/etc/nginx/nginx.conf,readonly',PUBLICATION_BRIDGE_IMAGE_REF]);docker(*command,timeout=60)
    docker('network','connect','--alias',name,PUBLICATION_NETWORK,name,timeout=30)
    deadline=time.time()+30
    while time.time()<deadline:
        probe=docker('exec',name,'wget','-qO-','http://127.0.0.1/__cloudif_bridge_health',timeout=5,check=False)
        if probe.returncode==0 and '"ok":true' in probe.stdout:break
        time.sleep(.5)
    else:docker('rm','-f',name,timeout=30,check=False);raise DeploymentError('publication_bridge_health_failed','Bridge de publicação não ficou saudável.',409)
    return {'ok':True,'bridge':name,'deployment_id':deployment_id,'public_number':public_number,'stage':stage,'number':number,'image_id':PUBLICATION_BRIDGE_IMAGE_ID,'published_ports':[],'read_only':True,'user':'101:101','capabilities':['NET_BIND_SERVICE'],'idempotent':False}


def ensure_source_preview_bridge(payload:Any)->dict:
    if not isinstance(payload,dict) or set(payload)!={'project_slug','public_number','generation'}:raise DeploymentError('invalid_source_preview_bridge_request','Pedido de bridge W1 inválido.',400)
    slug=str(payload.get('project_slug') or '').strip().lower();public_number=int(payload.get('public_number') or 0);generation=int(payload.get('generation') or 0)
    if not SLUG_RE.fullmatch(slug) or not (1<=public_number<=999999999 and 1<=generation<=999999):raise DeploymentError('invalid_source_preview_bridge_request','Pedido de bridge W1 inválido.',400)
    source=compose_source_state(slug);project,_,_,rows=_compose_source_rows(slug);edge_service=str(source.get('edge_service') or '');edge_port=int(source.get('edge_port') or 0)
    edge_row=next((row for row in rows if str((((row.get('Config') or {}).get('Labels') or {}).get('com.docker.compose.service')) or '')==edge_service),None)
    if not edge_row:raise DeploymentError('compose_public_edge_missing','Serviço público do Compose não foi localizado.',409)
    networks=((edge_row.get('NetworkSettings') or {}).get('Networks') or {});project_networks=[];non_public=[]
    for network_name_source in sorted(networks):
        if network_name_source==PUBLICATION_NETWORK:continue
        non_public.append(network_name_source);nrows=_json_rows(docker('network','inspect',network_name_source,timeout=30,check=False));labels=(nrows[0].get('Labels') or {}) if nrows else {}
        if str(labels.get('com.docker.compose.project') or '')==project:project_networks.append(network_name_source)
    if len(project_networks)==1:source_network=project_networks[0]
    elif not project_networks and len(non_public)==1:source_network=non_public[0]
    elif not non_public and PUBLICATION_NETWORK in networks:source_network=PUBLICATION_NETWORK
    else:raise DeploymentError('compose_source_network_ambiguous','Não foi possível determinar uma única rede privada para o serviço web do Compose.',409,{'networks':sorted(networks)})
    image=inspect_image(PUBLICATION_BRIDGE_IMAGE_REF)
    if str(image.get('Id') or '')!=PUBLICATION_BRIDGE_IMAGE_ID:raise DeploymentError('publication_bridge_image_mismatch','Imagem do bridge diverge do digest homologado.',409)
    name=f'cloudif-p{public_number}-w{generation}-preview-web';root=PUBLICATION_BRIDGE_ROOT/name;config=root/'nginx.conf';root.mkdir(parents=True,exist_ok=True)
    config.write_text(_publication_bridge_config({'services':[{'service':edge_service,'port':edge_port}],'routes':[{'pathPrefix':'/','service':edge_service,'stripPrefix':False}]}));os.chmod(config,0o644)
    labels={'org.cloudiff.source-preview-bridge':'true','org.cloudiff.project':slug,'org.cloudiff.public-number':str(public_number),'org.cloudiff.stage':'preview','org.cloudiff.stage-number':str(generation),'org.cloudiff.source-digest':str(source.get('source_digest') or '')}
    existing=docker('inspect',name,timeout=30,check=False);legacy=False
    if existing.returncode==0:
        row=(json.loads(existing.stdout or '[]') or [{}])[0];current=(row.get('Config') or {}).get('Labels') or {}
        same_bridge=current.get('org.cloudiff.source-preview-bridge')=='true' and current.get('org.cloudiff.project')==slug
        legacy=current.get('cloudif.project')==slug and str(current.get('cloudif.public-number') or '')==str(public_number) and current.get('cloudif.stage')=='preview' and str(current.get('cloudif.stage-number') or '')==str(generation)
        if same_bridge and all(str(current.get(k) or '')==v for k,v in labels.items()) and bool((row.get('State') or {}).get('Running')):
            return {'ok':True,'bridge':name,'project_slug':slug,'public_number':public_number,'generation':generation,'source_digest':source['source_digest'],'edge_service':edge_service,'edge_port':edge_port,'source_network':source_network,'idempotent':True,'migratedLegacyPreview':False,'secretValuesIncluded':False}
        if not same_bridge and not legacy:raise DeploymentError('source_preview_bridge_conflict','O alias W1 já pertence a outro runtime.',409)
    candidate=name+'-candidate-'+str(source.get('source_digest') or '')[:8]
    docker('rm','-f',candidate,timeout=30,check=False)
    command=['run','-d','--name',candidate,'--user','101:101','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=32m,uid=101,gid=101,mode=1777','--cap-drop','ALL','--cap-add','NET_BIND_SERVICE','--security-opt','no-new-privileges','--pids-limit','128','--memory','128m','--cpus','0.25','--restart','unless-stopped','--network',source_network]
    for k,v in labels.items():command.extend(['--label',k+'='+v])
    command.extend(['--mount',f'type=bind,src={config},dst=/etc/nginx/nginx.conf,readonly',PUBLICATION_BRIDGE_IMAGE_REF]);docker(*command,timeout=60)
    deadline=time.time()+45
    while time.time()<deadline:
        health=docker('exec',candidate,'wget','-qO-','http://127.0.0.1/__cloudif_bridge_health',timeout=5,check=False)
        upstream=docker('exec',candidate,'wget','-qO-','--timeout=5',f'http://{edge_service}:{edge_port}/',timeout=8,check=False)
        if health.returncode==0 and '"ok":true' in health.stdout and upstream.returncode==0:break
        time.sleep(.5)
    else:docker('rm','-f',candidate,timeout=30,check=False);raise DeploymentError('source_preview_bridge_health_failed','Bridge W1 não conseguiu alcançar o serviço web do Compose.',409)
    backup='';migrated=existing.returncode==0
    try:
        if existing.returncode==0:
            backup=name+'-rollback-'+secrets.token_hex(4);docker('stop',name,timeout=30,check=False);docker('rename',name,backup,timeout=30)
        docker('rename',candidate,name,timeout=30)
        if source_network==PUBLICATION_NETWORK:
            docker('network','disconnect','-f',PUBLICATION_NETWORK,name,timeout=30,check=False);docker('network','connect','--alias',name,PUBLICATION_NETWORK,name,timeout=30)
        else:docker('network','connect','--alias',name,PUBLICATION_NETWORK,name,timeout=30)
        health=docker('exec',name,'wget','-qO-','http://127.0.0.1/__cloudif_bridge_health',timeout=8,check=False)
        if health.returncode!=0 or '"ok":true' not in health.stdout:raise DeploymentError('source_preview_bridge_health_failed','Bridge W1 não ficou saudável após ativação.',409)
        if backup:docker('rm','-f',backup,timeout=30,check=False)
    except Exception:
        docker('rm','-f',name,timeout=30,check=False);docker('rm','-f',candidate,timeout=30,check=False)
        if backup:
            docker('rename',backup,name,timeout=30,check=False);docker('start',name,timeout=30,check=False)
        raise
    return {'ok':True,'bridge':name,'project_slug':slug,'public_number':public_number,'generation':generation,'source_digest':source['source_digest'],'edge_service':edge_service,'edge_port':edge_port,'source_network':source_network,'idempotent':False,'migratedLegacyPreview':bool(legacy),'replacedPreviousBridge':bool(migrated and not legacy),'secretValuesIncluded':False}



def activate_publication_bridge(payload:Any)->dict:
    if not isinstance(payload,dict) or set(payload)!={'project_slug','public_number','publication_number'}:raise DeploymentError('invalid_publication_activation_request','Pedido de ativação inválido.',400)
    slug=str(payload.get('project_slug') or '').strip().lower();public_number=int(payload.get('public_number') or 0);number=int(payload.get('publication_number') or 0);target=publication_bridge_name(public_number,'publication',number);alias=f'cloudif-p{public_number}-active-web'
    if not SLUG_RE.fullmatch(slug):raise DeploymentError('invalid_project_slug','Projeto inválido.',400)
    raw=docker('inspect',target,timeout=30,check=False)
    if raw.returncode:raise DeploymentError('publication_bridge_not_found','Bridge de publicação não encontrado.',404)
    row=(json.loads(raw.stdout or '[]') or [{}])[0];labels=(row.get('Config') or {}).get('Labels') or {}
    if labels.get('org.cloudiff.publication-bridge')!='true' or labels.get('org.cloudiff.project')!=slug:raise DeploymentError('publication_bridge_mismatch','Bridge não pertence ao projeto.',409)
    names=docker('ps','-a','--filter','label=org.cloudiff.publication-bridge=true','--filter',f'label=org.cloudiff.public-number={public_number}','--format','{{.Names}}',check=False).stdout.splitlines()
    for name in names:
        item=(json.loads(docker('inspect',name).stdout or '[]') or [{}])[0];networks=((item.get('NetworkSettings') or {}).get('Networks') or {});pub=networks.get(PUBLICATION_NETWORK) or {};aliases=pub.get('Aliases') or []
        if alias in aliases or name==target:
            docker('network','disconnect','-f',PUBLICATION_NETWORK,name,timeout=30,check=False)
            args=['network','connect','--alias',name]
            if name==target:args.extend(['--alias',alias])
            args.extend([PUBLICATION_NETWORK,name]);docker(*args,timeout=30)
    return {'ok':True,'project_slug':slug,'public_number':public_number,'publication_number':number,'bridge':target,'active_alias':alias,'secretValuesIncluded':False}


def _json_rows(result:subprocess.CompletedProcess)->list[dict]:
    try:value=json.loads(result.stdout or '[]')
    except Exception:raise DeploymentError('docker_response_invalid','Resposta Docker inválida.',502)
    return value if isinstance(value,list) else []


def _sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as handle:
        while True:
            chunk=handle.read(1024*1024)
            if not chunk:break
            h.update(chunk)
    return h.hexdigest()


def _path_size(path:Path)->int:
    if path.is_file() or path.is_symlink():return int(path.lstat().st_size)
    result=subprocess.run(['du','-sb','--',str(path)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if result.returncode:raise DeploymentError('compose_snapshot_size_failed','Não foi possível medir a origem do snapshot.',502,{'path':str(path)})
    try:return int(result.stdout.split()[0])
    except Exception:raise DeploymentError('compose_snapshot_size_failed','Tamanho do snapshot inválido.',502,{'path':str(path)})


def _export_rootfs(container:str,target:Path)->None:
    target.parent.mkdir(parents=True,exist_ok=True)
    result=docker('export','--output',str(target),container,timeout=1200,check=False)
    if result.returncode:raise DeploymentError('compose_rootfs_export_failed','Não foi possível congelar o root filesystem do serviço Compose.',502,{'container':container,'error':result.stderr[-400:]})
    os.chmod(target,0o600)


def _compress_rootfs(archive:Path)->Path:
    result=subprocess.run(['gzip','-1n','-f',str(archive)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=1200)
    generated=Path(str(archive)+'.gz')
    if result.returncode or not generated.is_file():raise DeploymentError('compose_rootfs_compress_failed','Não foi possível comprimir o root filesystem congelado.',502,{'archive':archive.name,'error':result.stderr[-400:]})
    os.chmod(generated,0o600);return generated


def _snapshot_rootfs_image(snapshot_id:str,service:str,archive:Path,expected_sha256:str)->tuple[str,str]:
    if not COMPOSE_SNAPSHOT_RE.fullmatch(snapshot_id) or not SERVICE_RE.fullmatch(service) or not SHA_RE.fullmatch(expected_sha256):raise DeploymentError('compose_snapshot_image_identity_invalid','Identidade do rootfs do snapshot é inválida.',409)
    if not archive.is_file() or not hmac.compare_digest(_sha_file(archive),expected_sha256):raise DeploymentError('compose_snapshot_rootfs_digest_mismatch','Root filesystem do snapshot não confere.',409,{'service':service})
    tag=f'cloudif/compose-snapshot:{snapshot_id}-{service}'
    inspected=docker('image','inspect',tag,timeout=30,check=False)
    if inspected.returncode==0:
        rows=_json_rows(inspected);row=rows[0] if rows else {};labels=(row.get('Config') or {}).get('Labels') or {}
        if labels.get('org.cloudiff.snapshot')!=snapshot_id or labels.get('org.cloudiff.rootfs-sha256')!=expected_sha256:raise DeploymentError('compose_snapshot_image_conflict','Imagem local do snapshot diverge do artefato congelado.',409,{'service':service})
        return str(row.get('Id') or ''),tag
    change_snapshot=f'LABEL org.cloudiff.snapshot={snapshot_id}';change_digest=f'LABEL org.cloudiff.rootfs-sha256={expected_sha256}';change_service=f'LABEL org.cloudiff.service={service}'
    result=docker('import','--change',change_snapshot,'--change',change_digest,'--change',change_service,str(archive),tag,timeout=1200)
    image_id=result.stdout.strip();rows=_json_rows(docker('image','inspect',tag,timeout=30));row=rows[0] if rows else {}
    if not IMAGE_RE.fullmatch(str(row.get('Id') or '')):raise DeploymentError('compose_snapshot_image_import_failed','Root filesystem congelado não gerou imagem válida.',502,{'service':service})
    return str(row['Id']),tag


def _tar_contents(source:Path,target:Path)->None:
    target.parent.mkdir(parents=True,exist_ok=True)
    result=subprocess.run(['tar','--numeric-owner','-C',str(source),'-cpf',str(target),'.'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=900)
    if result.returncode:raise DeploymentError('compose_snapshot_archive_failed','Não foi possível congelar um volume Compose.',502,{'source':str(source),'error':result.stderr[-400:]})
    os.chmod(target,0o600)


def _tar_container_path(container:str,source_path:str,target:Path)->None:
    if not container or not source_path.startswith('/') or '\x00' in container or '\x00' in source_path:raise DeploymentError('compose_snapshot_source_invalid','Origem do volume Compose inválida.',409)
    target.parent.mkdir(parents=True,exist_ok=True)
    source_path=source_path.rstrip('/') or '/'
    command=['docker','cp',f'{container}:{source_path}/.','-']
    try:
        with target.open('wb') as output:
            result=subprocess.run(command,stdout=output,stderr=subprocess.PIPE,timeout=900)
    except subprocess.TimeoutExpired:
        target.unlink(missing_ok=True)
        raise DeploymentError('compose_snapshot_archive_timeout','Tempo excedido ao congelar volume Compose.',504,{'container':container,'destination':source_path})
    if result.returncode:
        target.unlink(missing_ok=True)
        error=(result.stderr or b'').decode(errors='replace')[-400:]
        raise DeploymentError('compose_snapshot_archive_failed','Não foi possível congelar um volume Compose pelo daemon Docker.',502,{'container':container,'destination':source_path,'error':error})
    if not target.is_file() or target.stat().st_size<=0:raise DeploymentError('compose_snapshot_archive_failed','O daemon Docker não produziu o arquivo do volume Compose.',502,{'container':container,'destination':source_path})
    os.chmod(target,0o600)



def _tar_path(source:Path,target:Path)->None:
    target.parent.mkdir(parents=True,exist_ok=True)
    result=subprocess.run(['tar','--numeric-owner','-C',str(source.parent),'-cpf',str(target),source.name],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=900)
    if result.returncode:raise DeploymentError('compose_snapshot_archive_failed','Não foi possível congelar um bind Compose.',502,{'source':str(source),'error':result.stderr[-400:]})
    os.chmod(target,0o600)


def _extract_tar(archive:Path,target:Path)->None:
    if not archive.is_file():raise DeploymentError('compose_snapshot_restore_failed','Arquivo do snapshot não existe.',502,{'archive':archive.name})
    image=inspect_image(PUBLICATION_BRIDGE_IMAGE_REF)
    if str(image.get('Id') or '')!=PUBLICATION_BRIDGE_IMAGE_ID:raise DeploymentError('snapshot_helper_image_mismatch','Imagem auxiliar de restauração diverge do digest homologado.',409)
    target.mkdir(parents=True,exist_ok=True)
    archive_path=archive.resolve();target_path=target.resolve()
    command=['run','--rm','--network','none','--user','0:0','--read-only','--cap-drop','ALL','--cap-add','CHOWN','--cap-add','DAC_OVERRIDE','--cap-add','FOWNER','--security-opt','no-new-privileges','--mount',f'type=bind,src={target_path},dst=/restore','--mount',f'type=bind,src={archive_path},dst=/snapshot.tar,readonly','--entrypoint','/bin/sh',PUBLICATION_BRIDGE_IMAGE_REF,'-c','cd /restore && tar --numeric-owner -xpf /snapshot.tar']
    result=docker(*command,timeout=900,check=False)
    if result.returncode:raise DeploymentError('compose_snapshot_restore_failed','Não foi possível restaurar um arquivo do snapshot pelo helper Docker.',502,{'archive':archive.name,'error':result.stderr[-400:]})


def _compose_overlay_roots(container:str,mount_destinations:list[str])->list[str]:
    result=docker('diff',container,timeout=120,check=False)
    if result.returncode:raise DeploymentError('compose_rootfs_diff_failed','Não foi possível validar o filesystem do serviço Compose.',502,{'container':container})
    mounts=sorted({str(x).rstrip('/') or '/' for x in mount_destinations},key=len,reverse=True)
    roots=set()
    unsupported=[]
    for raw in result.stdout.splitlines():
        parts=raw.split(' ',1)
        if len(parts)!=2:continue
        path=parts[1].strip()
        if not path.startswith('/'):continue
        if any(path==m or path.startswith(m+'/') or m.startswith(path.rstrip('/')+'/') for m in mounts):continue
        if any(path==p or path.startswith(p+'/') or p.startswith(path.rstrip('/')+'/') for p in COMPOSE_EPHEMERAL_PREFIXES):continue
        top='/'+path.strip('/').split('/',1)[0] if path.strip('/') else '/'
        if top=='/etc':roots.add('/etc')
        elif top not in {'/'}:unsupported.append(path)
    if unsupported:
        raise DeploymentError('compose_rootfs_drift_unsupported','O stack altera filesystem fora de volumes/binds em caminho ainda não publicável.',409,{'container':container,'paths':sorted(set(unsupported))[:24]})
    return sorted(roots)


def _compose_tcp_ports(row:dict)->list[int]:
    exposed=((row.get('Config') or {}).get('ExposedPorts') or {})
    result=[]
    for key in exposed:
        match=re.fullmatch(r'(\d+)/tcp',str(key))
        if match:
            port=int(match.group(1))
            if 1<=port<=65535:result.append(port)
    return sorted(set(result))


def _compose_public_port(row:dict)->int:
    labels=(row.get('Config') or {}).get('Labels') or {};raw=str(labels.get('org.cloudiff.public-port') or '')
    if raw.isdigit() and 1<=int(raw)<=65535:return int(raw)
    ports=_compose_tcp_ports(row)
    if 80 in ports:return 80
    if len(ports)==1:return ports[0]
    raise DeploymentError('compose_public_port_ambiguous','O serviço público Compose deve expor porta 80, uma única porta TCP ou org.cloudiff.public-port.',409,{'service':labels.get('com.docker.compose.service'),'ports':ports})


def _compose_source_rows(slug:str)->tuple[str,Path,str,list[dict]]:
    if not SLUG_RE.fullmatch(str(slug or '')):raise DeploymentError('invalid_project_slug','project_slug é inválido.',400)
    project='cloudif-'+slug
    ids=docker('ps','-a','--filter',f'label=com.docker.compose.project={project}','--format','{{.ID}}',timeout=30,check=False).stdout.splitlines()
    if not ids:raise DeploymentError('compose_source_not_found','Stack Compose vinculado não encontrado.',404,{'project':project})
    rows=_json_rows(docker('inspect',*ids,timeout=60));services=[];working_dirs=set()
    for row in rows:
        config=row.get('Config') or {};labels=config.get('Labels') or {}
        if str(labels.get('com.docker.compose.oneoff') or '').lower()=='true':continue
        service=str(labels.get('com.docker.compose.service') or '')
        if not SERVICE_RE.fullmatch(service):raise DeploymentError('compose_service_invalid','Serviço Compose sem identidade válida.',409,{'service':service})
        if not bool((row.get('State') or {}).get('Running')):raise DeploymentError('compose_source_not_running','Todos os serviços Compose devem estar ativos para gerar candidato.',409,{'service':service})
        host=row.get('HostConfig') or {};network_mode=str(host.get('NetworkMode') or '')
        if host.get('Privileged') or network_mode=='host' or network_mode.startswith('container:') or host.get('Devices') or host.get('DeviceRequests'):
            raise DeploymentError('compose_source_security_blocked','Stack Compose usa privilégio, device ou network mode não publicável.',409,{'service':service})
        caps={str(x).upper() for x in (host.get('CapAdd') or [])}
        dangerous=sorted(caps&COMPOSE_DANGEROUS_CAPS)
        if dangerous:raise DeploymentError('compose_source_capability_blocked','Stack Compose usa capability não publicável.',409,{'service':service,'capabilities':dangerous})
        work=str(labels.get('com.docker.compose.project.working_dir') or '')
        if not work or not Path(work).is_absolute():raise DeploymentError('compose_source_workdir_missing','Stack Compose não informa o checkout vinculado.',409,{'service':service})
        working_dirs.add(str(Path(work).resolve()));services.append(row)
    if not services or len(services)>MAX_SERVICES or len(working_dirs)!=1:raise DeploymentError('compose_source_invalid','Stack Compose possui composição ou checkout inconsistente.',409)
    working_dir=Path(next(iter(working_dirs)))
    git=subprocess.run(['git','-C',str(working_dir),'rev-parse','HEAD'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    commit=git.stdout.strip() if git.returncode==0 else ''
    if not re.fullmatch(r'[a-f0-9]{40,64}',commit):raise DeploymentError('compose_source_git_unavailable','O checkout Forgejo do stack não possui HEAD válido.',409)
    return project,working_dir,commit,services


def compose_source_state(slug:str)->dict:
    project,working_dir,commit,rows=_compose_source_rows(slug);safe=[];publication_edges=[];fallback_edges=[]
    for row in rows:
        config=row.get('Config') or {};labels=config.get('Labels') or {};service=str(labels.get('com.docker.compose.service') or '')
        mounts=[];destinations=[]
        for item in row.get('Mounts') or []:
            kind=str(item.get('Type') or '');dest=str(item.get('Destination') or '');rw=bool(item.get('RW'))
            if kind not in {'volume','bind'} or not dest.startswith('/'):raise DeploymentError('compose_mount_unsupported','Mount Compose não publicável.',409,{'service':service,'type':kind,'destination':dest})
            source=Path(str(item.get('Source') or '')).resolve()
            if kind=='bind':
                try:source.relative_to(working_dir)
                except ValueError:raise DeploymentError('compose_bind_outside_checkout','Bind Compose precisa estar dentro do checkout Forgejo.',409,{'service':service,'destination':dest})
                source_ref=str(source.relative_to(working_dir))
            else:source_ref=str(item.get('Name') or '')
            mounts.append({'type':kind,'sourceRef':source_ref,'destination':dest,'rw':rw});destinations.append(dest)
        mounts=sorted(mounts,key=lambda item:(item['destination'],item['type'],item['sourceRef'],bool(item['rw'])))
        destinations=sorted(destinations)
        overlay_roots=[]
        networks=((row.get('NetworkSettings') or {}).get('Networks') or {})
        is_publication=PUBLICATION_NETWORK in networks
        requires_egress=False;network_contract=[]
        for network_name_source in sorted(networks):
            nrows=_json_rows(docker('network','inspect',network_name_source,timeout=30,check=False))
            internal=bool((nrows[0] if nrows else {}).get('Internal'))
            network_contract.append({'name':network_name_source,'internal':internal,'publication':network_name_source==PUBLICATION_NETWORK})
            if network_name_source!=PUBLICATION_NETWORK and not internal:requires_egress=True
        ports=_compose_tcp_ports(row);explicit=str(labels.get('org.cloudiff.public-port') or '')
        if is_publication:publication_edges.append((service,_compose_public_port(row)))
        elif explicit.isdigit() and 1<=int(explicit)<=65535:fallback_edges.append((service,int(explicit)))
        elif 80 in ports:fallback_edges.append((service,80))
        port=ports[0] if len(ports)==1 else 0
        env=[str(x) for x in (config.get('Env') or [])]
        host=row.get('HostConfig') or {}
        material={'service':service,'image_id':str(row.get('Image') or ''),'config_hash':str(labels.get('com.docker.compose.config-hash') or ''),'environment_digest':hashlib.sha256(canonical(sorted(env))).hexdigest(),'environment_names':sorted({x.split('=',1)[0] for x in env if '=' in x}),'entrypoint':config.get('Entrypoint') or [],'cmd':config.get('Cmd') or [],'user':str(config.get('User') or ''),'working_dir':str(config.get('WorkingDir') or ''),'mounts':mounts,'rootfs_overlays':overlay_roots,'rootfs_snapshot':'full-export','ports':ports,'port':port,'source_networks':network_contract,'requires_egress':requires_egress,'cap_add':sorted(str(x) for x in (host.get('CapAdd') or [])),'cap_drop':sorted(str(x) for x in (host.get('CapDrop') or [])),'read_only':bool(host.get('ReadonlyRootfs'))}
        material['service_digest']=hashlib.sha256(canonical(material)).hexdigest();safe.append(material)
    if publication_edges:
        if len(publication_edges)!=1:raise DeploymentError('compose_public_edge_invalid','Stack Compose deve possuir exatamente um serviço público.',409,{'edges':[x[0] for x in publication_edges]})
        edge_service,edge_port=publication_edges[0]
    else:
        if len(fallback_edges)!=1:raise DeploymentError('compose_public_edge_invalid','Stack Compose sem rede CloudIFF deve expor exatamente um serviço HTTP em 80/tcp ou declarar org.cloudiff.public-port.',409,{'edges':[x[0] for x in fallback_edges]})
        edge_service,edge_port=fallback_edges[0]
    for item in safe:
        if item.get('service')==edge_service:item['port']=edge_port
    safe=sorted(safe,key=lambda item:item['service'])
    digest=hashlib.sha256(canonical({'project':project,'source_commit':commit,'edge_service':edge_service,'edge_port':edge_port,'services':safe})).hexdigest()
    return {'ok':True,'source_kind':'linked-compose','project_slug':slug,'compose_project':project,'source_digest':digest,'source_commit':commit,'edge_service':edge_service,'edge_port':edge_port,'services':safe,'service_count':len(safe),'secretValuesIncluded':False,'effectsExecuted':False}



def _snapshot_safe_status(row:sqlite3.Row)->dict:
    manifest=json.loads(row['manifest_json'] or '{}')
    return {'ok':True,'source_kind':'linked-compose','snapshot_id':row['snapshot_id'],'project_slug':row['project_slug'],'source_digest':row['source_digest'],'snapshot_digest':row['snapshot_digest'],'source_commit':row['source_commit'],'edge_service':row['edge_service'],'edge_port':int(row['edge_port']),'services':manifest.get('services') or [],'status':row['status'],'created_at':int(row['created_at']),'secretValuesIncluded':False,'secretValuesPersistedRootOnly':True,'effectsExecuted':False}


def compose_snapshot_status(snapshot_id:str)->dict:
    if not COMPOSE_SNAPSHOT_RE.fullmatch(str(snapshot_id or '')):raise DeploymentError('invalid_snapshot_id','snapshot_id inválido.',400)
    connection=db();row=connection.execute('select * from compose_snapshots where snapshot_id=?',(snapshot_id,)).fetchone();connection.close()
    if not row:raise DeploymentError('compose_snapshot_not_found','Snapshot Compose não encontrado.',404)
    return _snapshot_safe_status(row)


def _snapshot_archive_record(path:Path)->dict:
    return {'file':path.name,'sha256':_sha_file(path),'bytes':path.stat().st_size}


def create_compose_snapshot(slug:str,expected_source_digest:str,deployment_id:str,expected_source_commit:str='')->dict:
    if not SHA_RE.fullmatch(str(expected_source_digest or '')):raise DeploymentError('invalid_source_digest','source_digest inválido.',400)
    if not DEPLOYMENT_RE.fullmatch(str(deployment_id or '')):raise DeploymentError('invalid_deployment_id','deployment_id inválido.',400)
    current=compose_source_state(slug)
    if not hmac.compare_digest(current['source_digest'],expected_source_digest):raise DeploymentError('compose_source_changed','O stack mudou depois do plano; gere o candidato novamente.',409)
    if expected_source_commit and not hmac.compare_digest(current['source_commit'],str(expected_source_commit)):raise DeploymentError('compose_source_commit_changed','O HEAD Forgejo mudou depois do plano.',409)
    snapshot_id='snap_'+hashlib.sha256((slug+'|'+deployment_id+'|'+expected_source_digest).encode()).hexdigest()[:24]
    connection=db();row=connection.execute('select * from compose_snapshots where snapshot_id=?',(snapshot_id,)).fetchone();connection.close()
    if row:return _snapshot_safe_status(row)
    project,working_dir,commit,rows=_compose_source_rows(slug);root=COMPOSE_SNAPSHOT_ROOT/snapshot_id;tmp=COMPOSE_SNAPSHOT_ROOT/('.'+snapshot_id+'.tmp-'+secrets.token_hex(4))
    COMPOSE_SNAPSHOT_ROOT.mkdir(parents=True,exist_ok=True);os.chmod(COMPOSE_SNAPSHOT_ROOT,0o700);tmp.mkdir(mode=0o700)
    paused=[];private={'project_slug':slug,'compose_project':project,'source_commit':commit,'services':[]};safe_services=[];total=0
    try:
        for row in rows:
            name=str(row.get('Name') or '').lstrip('/');docker('pause',name,timeout=30);paused.append(name)
        subprocess.run(['sync'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
        for row in sorted(rows,key=lambda r:str(((r.get('Config') or {}).get('Labels') or {}).get('com.docker.compose.service') or '')):
            config=row.get('Config') or {};host=row.get('HostConfig') or {};labels=config.get('Labels') or {};service=str(labels.get('com.docker.compose.service') or '');name=str(row.get('Name') or '').lstrip('/')
            env=[str(x) for x in (config.get('Env') or [])];mount_records=[];safe_mounts=[];destinations=[]
            for index,item in enumerate(row.get('Mounts') or []):
                kind=str(item.get('Type') or '');dest=str(item.get('Destination') or '');rw=bool(item.get('RW'));source=Path(str(item.get('Source') or '')).resolve();archive=tmp/'artifacts'/service/f'mount-{index}.tar'
                if kind=='volume':
                    source_ref=str(item.get('Name') or '')
                    _tar_container_path(name,dest,archive)
                elif kind=='bind':
                    try:source_ref=str(source.relative_to(working_dir))
                    except ValueError:raise DeploymentError('compose_bind_outside_checkout','Bind Compose precisa estar dentro do checkout Forgejo.',409,{'service':service,'destination':dest})
                    _path_size(source)
                    _tar_path(source,archive)
                else:raise DeploymentError('compose_mount_unsupported','Mount Compose não publicável.',409,{'service':service,'type':kind})
                total+=archive.stat().st_size
                if total>COMPOSE_SNAPSHOT_MAX_BYTES:raise DeploymentError('compose_snapshot_too_large','Snapshot Compose excede o limite configurado.',409,{'bytes':total,'limit':COMPOSE_SNAPSHOT_MAX_BYTES})
                rec={'type':kind,'source_ref':source_ref,'destination':dest,'rw':rw,'archive':str(archive.relative_to(tmp)),'source_name':source.name};mount_records.append(rec);safe_mounts.append({'type':kind,'sourceRef':source_ref,'destination':dest,'rw':rw,**_snapshot_archive_record(archive)});destinations.append(dest)
            rootfs_archive=tmp/'artifacts'/service/'rootfs.tar';_export_rootfs(name,rootfs_archive);total+=rootfs_archive.stat().st_size
            if total>COMPOSE_SNAPSHOT_MAX_BYTES:raise DeploymentError('compose_snapshot_too_large','Snapshot Compose excede o limite configurado.',409,{'bytes':total,'limit':COMPOSE_SNAPSHOT_MAX_BYTES})
            rootfs_record={'archive':str(rootfs_archive.relative_to(tmp)),'sha256':_sha_file(rootfs_archive),'bytes':rootfs_archive.stat().st_size}
            overlays=[];safe_overlays=[]
            entry=config.get('Entrypoint') or [];cmd=config.get('Cmd') or [];health=config.get('Healthcheck') or {}
            private['services'].append({'service':service,'image_id':str(row.get('Image') or ''),'environment':env,'entrypoint':entry,'cmd':cmd,'user':str(config.get('User') or ''),'working_dir':str(config.get('WorkingDir') or ''),'healthcheck':health,'cap_add':[str(x) for x in (host.get('CapAdd') or [])],'cap_drop':[str(x) for x in (host.get('CapDrop') or [])],'security_opt':[str(x) for x in (host.get('SecurityOpt') or [])],'read_only':bool(host.get('ReadonlyRootfs')),'pids_limit':host.get('PidsLimit'),'memory':int(host.get('Memory') or 0),'nano_cpus':int(host.get('NanoCpus') or 0),'shm_size':int(host.get('ShmSize') or 0),'tmpfs':host.get('Tmpfs') or {},'mounts':mount_records,'overlays':overlays,'rootfs':rootfs_record,'ports':_compose_tcp_ports(row),'requires_egress':bool(next((item.get('requires_egress') for item in current.get('services') or [] if item.get('service')==service),False))})
            safe={'service':service,'image_id':str(row.get('Image') or ''),'environment_digest':hashlib.sha256(canonical(sorted(env))).hexdigest(),'environment_names':sorted({x.split('=',1)[0] for x in env if '=' in x}),'mounts':safe_mounts,'rootfs_overlays':safe_overlays,'rootfs':{'sha256':rootfs_record['sha256'],'bytes':rootfs_record['bytes']},'ports':_compose_tcp_ports(row),'port':_compose_public_port(row) if service==current['edge_service'] else (_compose_tcp_ports(row)[0] if _compose_tcp_ports(row) else 0),'requires_egress':bool(next((item.get('requires_egress') for item in current.get('services') or [] if item.get('service')==service),False))}
            safe['service_digest']=hashlib.sha256(canonical(safe)).hexdigest();safe_services.append(safe)
    except Exception:
        shutil.rmtree(tmp,ignore_errors=True)
        raise
    finally:
        for name in reversed(paused):docker('unpause',name,timeout=30,check=False)
    safe_by_service={item['service']:item for item in safe_services}
    for spec in private['services']:
        service=str(spec['service']);raw=tmp/str((spec.get('rootfs') or {}).get('archive') or '')
        compressed=_compress_rootfs(raw);record={'archive':str(compressed.relative_to(tmp)),'sha256':_sha_file(compressed),'bytes':compressed.stat().st_size}
        spec['rootfs']=record;safe_by_service[service]['rootfs']={'sha256':record['sha256'],'bytes':record['bytes']}
    private_path=tmp/'private-spec.json';private_path.write_text(json.dumps(private,ensure_ascii=False,separators=(',',':')));os.chmod(private_path,0o600)
    manifest={'project_slug':slug,'source_kind':'linked-compose','source_digest':current['source_digest'],'source_commit':commit,'edge_service':current['edge_service'],'edge_port':int(current['edge_port']),'services':sorted(safe_services,key=lambda x:x['service']),'private_spec_sha256':_sha_file(private_path),'artifact_bytes':sum(item.get('bytes',0) for svc in safe_services for item in (svc.get('mounts') or [])+(svc.get('rootfs_overlays') or []))+sum(int((svc.get('rootfs') or {}).get('bytes') or 0) for svc in safe_services)}
    snapshot_digest=hashlib.sha256(canonical(manifest)).hexdigest();(tmp/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n');os.chmod(tmp/'manifest.json',0o600)
    if root.exists():shutil.rmtree(tmp,ignore_errors=True)
    else:os.replace(tmp,root);os.chmod(root,0o700)
    now=int(time.time());connection=db();connection.execute('insert into compose_snapshots(snapshot_id,project_slug,source_digest,snapshot_digest,source_commit,edge_service,edge_port,manifest_json,status,created_at) values(?,?,?,?,?,?,?,?,?,?)',(snapshot_id,slug,current['source_digest'],snapshot_digest,commit,current['edge_service'],int(current['edge_port']),json.dumps(manifest,ensure_ascii=False,separators=(',',':')),'ready',now));connection.commit();row=connection.execute('select * from compose_snapshots where snapshot_id=?',(snapshot_id,)).fetchone();connection.close();return _snapshot_safe_status(row)


def _restore_volume_archive(archive:Path,volume:str)->None:
    image=inspect_image(PUBLICATION_BRIDGE_IMAGE_REF)
    if str(image.get('Id') or '')!=PUBLICATION_BRIDGE_IMAGE_ID:raise DeploymentError('snapshot_helper_image_mismatch','Imagem auxiliar de restauração diverge do digest homologado.',409)
    command=['run','--rm','--network','none','--user','0:0','--mount',f'type=volume,src={volume},dst=/restore','--mount',f'type=bind,src={archive},dst=/snapshot.tar,readonly','--entrypoint','/bin/sh',PUBLICATION_BRIDGE_IMAGE_REF,'-c','cd /restore && tar -xpf /snapshot.tar']
    docker(*command,timeout=900)


def _health_options(health:dict)->list[str]:
    test=health.get('Test') or []
    if not test:return []
    if not isinstance(test,list) or len(test)<2 or test[0]!='CMD-SHELL':raise DeploymentError('compose_healthcheck_unsupported','Healthcheck Compose deve usar CMD-SHELL.',409)
    out=['--health-cmd',str(test[1])]
    for key,opt in (('Interval','--health-interval'),('Timeout','--health-timeout'),('StartPeriod','--health-start-period')):
        value=int(health.get(key) or 0)
        if value>0:out.extend([opt,str(value)+'ns'])
    retries=int(health.get('Retries') or 0)
    if retries>0:out.extend(['--health-retries',str(retries)])
    return out


def _compose_container_ready(name:str)->tuple[bool,str]:
    rows=_json_rows(docker('inspect',name,timeout=30,check=False))
    if not rows:return False,'missing'
    state=rows[0].get('State') or {}
    if not state.get('Running'):return False,str(state.get('Status') or 'stopped')
    health=state.get('Health') or {}
    status=str(health.get('Status') or '')
    return (status=='healthy',status) if status else (True,'running')


def deploy_compose_snapshot(payload:Any)->dict:
    if not isinstance(payload,dict):raise DeploymentError('invalid_request','Pedido Compose inválido.',400)
    required={'deployment_id','project_slug','environment','deployment_plan_digest','config_revision','config_digest','toolchain_digest','routes','variables','variables_digest'}
    if not required.issubset(payload):raise DeploymentError('required_field_missing','Campos obrigatórios estão ausentes.',400,{'missing':sorted(required-set(payload))})
    deployment_id=str(payload.get('deployment_id') or '');slug=str(payload.get('project_slug') or '');environment=str(payload.get('environment') or '');plan=str(payload.get('deployment_plan_digest') or '').lower();snapshot_id=str(payload.get('snapshot_id') or '');source_digest=str(payload.get('source_digest') or '');source_commit=str(payload.get('source_commit') or '')
    if not DEPLOYMENT_RE.fullmatch(deployment_id) or not SLUG_RE.fullmatch(slug) or environment not in ENVIRONMENTS or not SHA_RE.fullmatch(plan):raise DeploymentError('invalid_request','Identidade do deploy Compose inválida.',400)
    config_revision=int(payload.get('config_revision') or 0);config_digest=str(payload.get('config_digest') or '');toolchain_digest=str(payload.get('toolchain_digest') or '')
    if config_revision<1 or not SHA_RE.fullmatch(config_digest) or not SHA_RE.fullmatch(toolchain_digest):raise DeploymentError('invalid_digest','Configuração do deploy Compose inválida.',400)
    variables=payload.get('variables') or {}
    if not isinstance(variables,dict):raise DeploymentError('invalid_variables','Variáveis inválidas.',400)
    variables_digest=str(payload.get('variables_digest') or '')
    if not SHA_RE.fullmatch(variables_digest) or not hmac.compare_digest(hashlib.sha256(canonical(variables)).hexdigest(),variables_digest):raise DeploymentError('variables_digest_mismatch','As variáveis mudaram após o plano.',409)
    connection=db();existing=connection.execute('select * from deployments where deployment_id=?',(deployment_id,)).fetchone();connection.close()
    if existing:
        if str(existing['plan_digest'])==plan and str(existing['status'])=='running':result=status_deployment(deployment_id);result['idempotent']=True;return result
        raise DeploymentError('deployment_id_conflict','deployment_id já foi usado por outro plano.',409)
    if snapshot_id:
        snapshot=compose_snapshot_status(snapshot_id)
        if snapshot['project_slug']!=slug:raise DeploymentError('compose_snapshot_project_mismatch','Snapshot pertence a outro projeto.',409)
    else:
        if environment!='homologation':raise DeploymentError('compose_snapshot_required','Produção exige snapshot homologado existente.',409)
        snapshot=create_compose_snapshot(slug,source_digest,deployment_id,source_commit)
        snapshot_id=snapshot['snapshot_id']
    root=COMPOSE_SNAPSHOT_ROOT/snapshot_id;private_path=root/'private-spec.json'
    if not private_path.is_file() or _sha_file(private_path)!=json.loads((root/'manifest.json').read_text()).get('private_spec_sha256'):raise DeploymentError('compose_snapshot_private_spec_invalid','Snapshot privado não confere.',409)
    private=json.loads(private_path.read_text());network=network_name(deployment_id);runtime_root=COMPOSE_RUNTIME_ROOT/deployment_id
    runtime_root.mkdir(parents=True,exist_ok=True);os.chmod(runtime_root,0o700)
    docker('network','create','--internal','--label',f'org.cloudiff.deployment={deployment_id}','--label',f'org.cloudiff.environment={environment}','--label',f'org.cloudiff.project={slug}',network,timeout=30)
    needs_egress=any(bool(item.get('requires_egress')) for item in (private.get('services') or []));egress=egress_network_name(deployment_id)
    if needs_egress:docker('network','create','--label',f'org.cloudiff.deployment={deployment_id}','--label',f'org.cloudiff.environment={environment}','--label',f'org.cloudiff.project={slug}',egress,timeout=30)
    services=[];created=[]
    try:
        for spec in private.get('services') or []:
            service=str(spec.get('service') or '');name=container_name(deployment_id,service);mount_args=[];runtime_service=runtime_root/service;runtime_service.mkdir(parents=True,exist_ok=True)
            for index,mount in enumerate(spec.get('mounts') or []):
                archive=root/str(mount['archive']);dest=str(mount['destination']);rw=bool(mount.get('rw'));kind=str(mount['type'])
                if kind=='volume':
                    volume=f'cloudif-vol-{deployment_id[4:]}-{service}-{index}';args=['volume','create','--label',f'org.cloudiff.deployment={deployment_id}','--label',f'org.cloudiff.project={slug}','--label',f'org.cloudiff.snapshot={snapshot_id}',volume];docker(*args,timeout=30);_restore_volume_archive(archive,volume);mount_args.extend(['--mount',f'type=volume,src={volume},dst={dest}'+('' if rw else ',readonly')])
                elif kind=='bind':
                    target=runtime_service/f'bind-{index}';_extract_tar(archive,target);source=target/str(mount.get('source_name') or '')
                    if not source.exists():raise DeploymentError('compose_snapshot_restore_failed','Bind restaurado não existe.',502,{'service':service,'destination':dest})
                    mount_args.extend(['--mount',f'type=bind,src={source},dst={dest}'+('' if rw else ',readonly')])
            rootfs=spec.get('rootfs') or {};rootfs_archive=root/str(rootfs.get('archive') or '');snapshot_image_id,snapshot_image_ref=_snapshot_rootfs_image(snapshot_id,service,rootfs_archive,str(rootfs.get('sha256') or ''))
            env={}
            for item in spec.get('environment') or []:
                if '=' in str(item):key,value=str(item).split('=',1);env[key]=value
            approved=variables.get(service) or {}
            if not isinstance(approved,dict):raise DeploymentError('invalid_variables','Variáveis por serviço inválidas.',400,{'service':service})
            env.update({str(k):str(v) for k,v in approved.items()});env.update({'CLOUDIF_PROJECT_SLUG':slug,'CLOUDIF_ENVIRONMENT':environment,'CLOUDIF_DEPLOYMENT_ID':deployment_id,'CLOUDIF_SERVICE':service,'CLOUDIF_COMPOSE_SNAPSHOT_ID':snapshot_id})
            path=env_file(deployment_id,service,env)
            command=['create','--name',name,'--network',network,'--network-alias',service,'--restart','unless-stopped','--env-file',str(path),'--label',f'org.cloudiff.deployment={deployment_id}','--label',f'org.cloudiff.environment={environment}','--label',f'org.cloudiff.project={slug}','--label',f'org.cloudiff.service={service}','--label',f'org.cloudiff.snapshot={snapshot_id}']
            if spec.get('read_only'):command.append('--read-only')
            user=str(spec.get('user') or '')
            if user:command.extend(['--user',user])
            workdir=str(spec.get('working_dir') or '')
            if workdir:command.extend(['--workdir',workdir])
            for cap in spec.get('cap_add') or []:command.extend(['--cap-add',str(cap)])
            for cap in spec.get('cap_drop') or []:command.extend(['--cap-drop',str(cap)])
            for opt in spec.get('security_opt') or []:
                if str(opt):command.extend(['--security-opt',str(opt)])
            pids=spec.get('pids_limit')
            if pids not in (None,0,-1):command.extend(['--pids-limit',str(int(pids))])
            memory=int(spec.get('memory') or 0)
            if memory>0:command.extend(['--memory',str(memory)])
            nano=int(spec.get('nano_cpus') or 0)
            if nano>0:command.extend(['--cpus',str(nano/1_000_000_000)])
            shm=int(spec.get('shm_size') or 0)
            if shm>0:command.extend(['--shm-size',str(shm)])
            for tmp_path,tmp_value in (spec.get('tmpfs') or {}).items():command.extend(['--tmpfs',str(tmp_path)+((':'+str(tmp_value)) if tmp_value else '')])
            command.extend(_health_options(spec.get('healthcheck') or {}));command.extend(mount_args)
            entry=[str(x) for x in (spec.get('entrypoint') or [])];cmd=[str(x) for x in (spec.get('cmd') or [])]
            if entry:command.extend(['--entrypoint',entry[0]])
            command.append(snapshot_image_ref)
            if entry:command.extend(entry[1:])
            command.extend(cmd)
            try:cid=docker(*command,timeout=180).stdout.strip()
            finally:path.unlink(missing_ok=True)
            if spec.get('requires_egress'):docker('network','connect','--alias',service,egress,name,timeout=30)
            created.append(name);ports=[int(x) for x in (spec.get('ports') or []) if int(x)>0];port=int(snapshot['edge_port']) if service==snapshot['edge_service'] else (ports[0] if ports else 0);services.append({'service':service,'container_name':name,'container_id':cid,'image_id':snapshot_image_id,'source_image_id':str(spec.get('image_id') or ''),'snapshot_id':snapshot_id,'port':port,'healthcheck':'/','requires_egress':bool(spec.get('requires_egress')),'variable_names':sorted(env)})
        for name in created:docker('start',name,timeout=60)
        deadline=time.time()+900;pending=set(created);last={}
        while pending and time.time()<deadline:
            for name in list(pending):
                ready,status=_compose_container_ready(name);last[name]=status
                if ready:pending.remove(name)
            if pending:time.sleep(2)
        if pending:raise DeploymentError('compose_snapshot_health_failed','Um ou mais serviços do snapshot não ficaram saudáveis.',409,{'pending':sorted(pending),'status':last})
        routes=payload.get('routes') or [{'pathPrefix':'/','service':snapshot['edge_service'],'stripPrefix':False}]
        now=int(time.time());safe_services=[{k:v for k,v in item.items() if k!='container_id'} for item in services]
        connection=db();connection.execute('insert into deployments(deployment_id,project_slug,environment,build_job_id,plan_digest,build_plan_digest,config_revision,config_digest,toolchain_digest,archive_sha256,variables_digest,status,services_json,routes_json,error_json,created_at,updated_at,snapshot_id) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(deployment_id,slug,environment,snapshot_id,plan,snapshot['snapshot_digest'],config_revision,config_digest,toolchain_digest,snapshot['snapshot_digest'],variables_digest,'running',json.dumps(services,separators=(',',':')),json.dumps(routes,separators=(',',':')),'{}',now,now,snapshot_id));connection.commit();connection.close()
        runtime_configuration={'buildEnvironmentDigest':'','runtimeEnvironmentDigest':str(payload.get('runtime_environment_digest') or variables_digest),'environmentDigest':str(payload.get('environment_digest') or variables_digest),'buildJobId':snapshot_id}
        _runtime_state_record({'project_slug':slug,'environment':environment,'deployment_id':deployment_id,'config_revision':config_revision,'config_digest':config_digest,'toolchain_digest':toolchain_digest,'build_job_id':snapshot_id,'variables':variables},runtime_configuration,'running')
        return {'ok':True,'deployment_id':deployment_id,'project_slug':slug,'environment':environment,'source_kind':'linked-compose','snapshot_id':snapshot_id,'snapshot_digest':snapshot['snapshot_digest'],'artifact_image_id':'sha256:'+snapshot['snapshot_digest'],'source_commit':snapshot['source_commit'],'status':'running','services':safe_services,'routes':routes,'edge_service':snapshot['edge_service'],'edge_port':snapshot['edge_port'],'snapshotBacked':True,'sameSnapshotReusable':True,'secretValuesIncluded':False,'secretValuesPersistedRootOnly':True,'idempotent':False}
    except Exception as error:
        cleanup_resources(deployment_id);detail=error.as_dict() if isinstance(error,DeploymentError) else {'code':'compose_snapshot_deploy_failed','message':type(error).__name__}
        now=int(time.time());connection=db();connection.execute('insert or replace into deployments(deployment_id,project_slug,environment,build_job_id,plan_digest,build_plan_digest,config_revision,config_digest,toolchain_digest,archive_sha256,variables_digest,status,services_json,routes_json,error_json,created_at,updated_at,snapshot_id) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(deployment_id,slug,environment,snapshot_id,plan,str(snapshot.get('snapshot_digest') or '0'*64),config_revision,config_digest,toolchain_digest,str(snapshot.get('snapshot_digest') or '0'*64),variables_digest,'failed','[]',json.dumps(payload.get('routes') or [],separators=(',',':')),json.dumps(detail,separators=(',',':')),now,now,snapshot_id));connection.commit();connection.close();raise


def assigned_port(name:str,container_port:int)->int:
    data=json.loads(docker('inspect',name,timeout=30).stdout)[0]
    bindings=((data.get('NetworkSettings') or {}).get('Ports') or {}).get(f'{container_port}/tcp') or []
    for binding in bindings:
        if str(binding.get('HostIp') or '')=='127.0.0.1' and str(binding.get('HostPort') or '').isdigit():return int(binding['HostPort'])
    raise DeploymentError('deployment_port_unavailable','A porta local do deploy não foi atribuída.',502,{'container':name})


def probe(port:int,path:str,deadline:float)->dict:
    last='not_started'
    while time.time()<deadline:
        try:
            request=urllib.request.Request(f'http://127.0.0.1:{port}{path}',headers={'User-Agent':'CloudIFF-deployment-health'})
            with urllib.request.urlopen(request,timeout=3) as response:
                if response.status<500:return {'ok':True,'status':response.status,'path':path}
                last='http_'+str(response.status)
        except urllib.error.HTTPError as error:
            if error.code<500:return {'ok':True,'status':error.code,'path':path}
            last='http_'+str(error.code)
        except Exception as error:last=type(error).__name__
        time.sleep(1)
    return {'ok':False,'status':last,'path':path}


def cleanup_resources(deployment_id:str,dependency_containers:list[str]|None=None)->dict:
    prefix='cloudif-'+deployment_id.replace('_','-')+'-';names=docker('ps','-a','--format','{{.Names}}',check=False).stdout.splitlines();removed=[];network=network_name(deployment_id)
    bridges=docker('ps','-a','--filter','label=org.cloudiff.publication-bridge=true','--filter',f'label=org.cloudiff.deployment={deployment_id}','--format','{{.Names}}',check=False).stdout.splitlines()
    for bridge in bridges:docker('rm','-f',bridge,timeout=30,check=False);removed.append(bridge)
    for name in names:
        if name.startswith(prefix):docker('rm','-f',name,timeout=30,check=False);removed.append(name)
    detached=0
    for name in sorted(set(dependency_containers or [])):
        result=docker('network','disconnect','-f',network,name,timeout=30,check=False)
        if result.returncode==0:detached+=1
    egress_result=docker('network','rm',egress_network_name(deployment_id),timeout=30,check=False)
    network_result=docker('network','rm',network,timeout=30,check=False)
    volumes=docker('volume','ls','-q','--filter',f'label=org.cloudiff.deployment={deployment_id}',timeout=30,check=False).stdout.splitlines();volumes_removed=0
    for volume in volumes:
        if docker('volume','rm',volume,timeout=60,check=False).returncode==0:volumes_removed+=1
    shutil.rmtree(COMPOSE_RUNTIME_ROOT/deployment_id,ignore_errors=True)
    return {'containersRemoved':len(removed),'dependencyContainersDetached':detached,'volumesRemoved':volumes_removed,'networkRemoved':network_result.returncode==0,'egressNetworkRemoved':egress_result.returncode==0}


def env_file(deployment_id:str,service:str,variables:dict[str,str])->Path:
    RUN_DIR.mkdir(parents=True,exist_ok=True);os.chmod(RUN_DIR,0o700)
    fd,name=tempfile.mkstemp(prefix=deployment_id+'-'+service+'-',suffix='.env',dir=RUN_DIR,text=True)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as handle:
            for key,value in sorted(variables.items()):handle.write(f'{key}={value}\n')
            handle.flush();os.fsync(handle.fileno())
        os.chmod(name,0o600);return Path(name)
    except Exception:
        try:os.unlink(name)
        except FileNotFoundError:pass
        raise



def _runtime_scalar(value):
    if value is None:
        return ''
    if isinstance(value,bool):
        return 'true' if value else 'false'
    if isinstance(value,(str,int,float)):
        return str(value)
    raise ValueError('runtime_environment_value_not_scalar')


def _validated_runtime_configuration(payload):
    configuration=payload.get('runtimeConfiguration')
    legacy=configuration is None
    if legacy:
        public=payload.get('variables') or {}
        if not isinstance(public,dict):raise ValueError('invalid_runtime_configuration')
        digest=str(payload.get('variables_digest') or '')
        configuration={
            'project_slug':str(payload.get('project_slug') or ''),'environment':str(payload.get('environment') or ''),
            'job_id':str(payload.get('build_job_id') or ''),'publicRuntimeEnvironment':public,'secretRuntimeReferences':{},
            'runtimeEnvironmentDigest':digest,'environmentDigest':digest,'secretValuesIncluded':False,
        }
    if not isinstance(configuration,dict):raise ValueError('invalid_runtime_configuration')
    if configuration.get('secretValuesIncluded') is not False:raise ValueError('runtime_secret_contract_invalid')
    project=str(payload.get('project_slug') or payload.get('projectSlug') or '');environment=str(payload.get('environment') or '');build_job=str(payload.get('build_job_id') or '')
    if str(configuration.get('project_slug') or configuration.get('projectSlug') or '')!=project:raise ValueError('runtime_project_binding_mismatch')
    if str(configuration.get('environment') or '')!=environment:raise ValueError('runtime_environment_binding_mismatch')
    configuration_job=str(configuration.get('job_id') or configuration.get('buildJobId') or '')
    if configuration_job and configuration_job!=build_job:raise ValueError('runtime_build_binding_mismatch')
    public=configuration.get('publicRuntimeEnvironment') or {};secret=configuration.get('secretRuntimeReferences') or {}
    if not isinstance(public,dict) or not isinstance(secret,dict):raise ValueError('invalid_runtime_environment_contract')
    if any(bool(values) for values in secret.values() if isinstance(values,dict)):raise ValueError('secret_resolution_unavailable')
    normalized={}
    for service,values in public.items():
        if not isinstance(values,dict):raise ValueError('invalid_public_runtime_environment')
        normalized[str(service)]={}
        for name,value in values.items():
            if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,127}',str(name)):raise ValueError('invalid_runtime_environment_name')
            normalized[str(service)][str(name)]=_runtime_scalar(value)
    runtime_digest=str(configuration.get('runtimeEnvironmentDigest') or '');environment_digest=str(configuration.get('environmentDigest') or '');build_environment_digest=str(configuration.get('buildEnvironmentDigest') or '')
    if not re.fullmatch(r'[a-f0-9]{64}',runtime_digest) or not re.fullmatch(r'[a-f0-9]{64}',environment_digest):raise ValueError('runtime_environment_digest_invalid')
    if build_environment_digest and not re.fullmatch(r'[a-f0-9]{64}',build_environment_digest):raise ValueError('build_environment_digest_invalid')
    return {'publicRuntimeEnvironment':normalized,'buildEnvironmentDigest':build_environment_digest,'runtimeEnvironmentDigest':runtime_digest,'environmentDigest':environment_digest,'buildJobId':configuration_job or build_job,'secretValuesIncluded':False,'legacyCompatibility':legacy}

def _apply_runtime_configuration(payload,configuration):
    public=configuration['publicRuntimeEnvironment']
    applications=payload.get('applications') or []
    application_names={str(item.get('service') or '') for item in applications if isinstance(item,dict)}
    services=payload.get('services') or []
    service_names=set()
    if services:
        if not isinstance(services,list):raise ValueError('invalid_deployment_services')
        for service in services:
            if not isinstance(service,dict):raise ValueError('invalid_deployment_service')
            name=str(service.get('name') or service.get('service') or '')
            if not name:raise ValueError('deployment_service_name_missing')
            service_names.add(name)
            existing=service.get('environment') or {}
            if not isinstance(existing,dict):raise ValueError('deployment_service_environment_must_be_object')
            merged={str(key):_runtime_scalar(value) for key,value in existing.items()};merged.update(public.get(name) or {});service['environment']=merged
            labels=service.get('labels') or {}
            if not isinstance(labels,dict):raise ValueError('deployment_service_labels_must_be_object')
            labels.update({'cloudiff.environment':str(payload.get('environment') or ''),'cloudiff.environment.digest':configuration['environmentDigest'],'cloudiff.runtime-environment.digest':configuration['runtimeEnvironmentDigest'],'cloudiff.build.job':configuration['buildJobId']});service['labels']=labels
    known=service_names or application_names
    unknown=sorted(set(public)-known)
    if unknown:raise ValueError('runtime_environment_unknown_service')
    variables=payload.get('variables') or {}
    if not isinstance(variables,dict):raise ValueError('invalid_variables')
    for name in known:
        existing=variables.get(name) or {}
        if not isinstance(existing,dict):raise ValueError('invalid_variables')
        merged={str(key):_runtime_scalar(value) for key,value in existing.items()};merged.update(public.get(name) or {});variables[name]=merged
    payload['variables']=variables
    payload['variables_digest']=hashlib.sha256(canonical(variables)).hexdigest()
    return payload

def _runtime_state_record(request:dict,runtime_configuration:dict,status:str='running')->None:
    variable_names={}
    for service,values in (request.get('variables') or {}).items():
        if isinstance(values,dict):variable_names[str(service)]=sorted(str(name) for name in values)
    record=(
        str(request.get('project_slug') or ''),str(request.get('environment') or ''),str(request.get('deployment_id') or ''),str(status or 'unknown'),
        int(request.get('config_revision') or 0),str(request.get('config_digest') or ''),str(request.get('toolchain_digest') or ''),
        str(runtime_configuration.get('buildEnvironmentDigest') or ''),str(runtime_configuration.get('runtimeEnvironmentDigest') or ''),str(runtime_configuration.get('environmentDigest') or ''),
        str(request.get('build_job_id') or ''),json.dumps(variable_names,ensure_ascii=False,sort_keys=True,separators=(',',':')),int(time.time()),
    )
    connection=db();connection.execute('''insert into runtime_states(project_slug,environment,deployment_id,status,config_revision,config_digest,toolchain_digest,build_environment_digest,runtime_environment_digest,environment_digest,build_job_id,variable_names_json,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?) on conflict(project_slug,environment) do update set deployment_id=excluded.deployment_id,status=excluded.status,config_revision=excluded.config_revision,config_digest=excluded.config_digest,toolchain_digest=excluded.toolchain_digest,build_environment_digest=excluded.build_environment_digest,runtime_environment_digest=excluded.runtime_environment_digest,environment_digest=excluded.environment_digest,build_job_id=excluded.build_job_id,variable_names_json=excluded.variable_names_json,updated_at=excluded.updated_at''',record);connection.commit();connection.close()

def project_runtime_state(project_slug:str,environment:str)->dict:
    if not SLUG_RE.fullmatch(str(project_slug or '')):raise DeploymentError('invalid_project_slug','project_slug é inválido.',400)
    if environment not in ENVIRONMENTS:raise DeploymentError('invalid_environment','environment deve ser homologation ou production.',400)
    connection=db();row=connection.execute('select * from runtime_states where project_slug=? and environment=?',(project_slug,environment)).fetchone()
    if row:
        deployment=connection.execute('select status from deployments where deployment_id=?',(row['deployment_id'],)).fetchone()
    else:deployment=None
    connection.close()
    if not row:return {'ok':True,'projectSlug':project_slug,'environment':environment,'states':[],'count':0,'secretValuesIncluded':False,'secretReferencesIncluded':False,'effectsExecuted':False}
    status=str((deployment['status'] if deployment else row['status']) or row['status'])
    state={'deploymentId':row['deployment_id'],'status':status,'configRevision':int(row['config_revision']),'configDigest':row['config_digest'],'toolchainDigest':row['toolchain_digest'],'buildEnvironmentDigest':row['build_environment_digest'],'runtimeEnvironmentDigest':row['runtime_environment_digest'],'environmentDigest':row['environment_digest'],'buildJobId':row['build_job_id'],'variableNames':json.loads(row['variable_names_json'] or '{}'),'updatedAt':int(row['updated_at'])}
    return {'ok':True,'projectSlug':project_slug,'environment':environment,'states':[state],'count':1,'secretValuesIncluded':False,'secretReferencesIncluded':False,'effectsExecuted':False}

def _runtime_state_authorized(headers)->bool:
    presented=str(headers.get('Authorization') or '');expected='Bearer '+TOKEN
    return bool(TOKEN) and hmac.compare_digest(presented,expected)


def create_deployment(payload:Any)->dict:
    runtime_configuration=_validated_runtime_configuration(payload)
    _apply_runtime_configuration(payload,runtime_configuration)
    request=normalize_payload(payload);deployment_id=request['deployment_id'];now=int(time.time())
    conn=db();row=conn.execute('select * from deployments where deployment_id=?',(deployment_id,)).fetchone();conn.close()
    if row:
        if row['plan_digest']==request['deployment_plan_digest'] and row['variables_digest']==request['variables_digest'] and row['status']=='running':
            result=status_deployment(deployment_id);result['idempotent']=True;return result
        raise DeploymentError('deployment_id_conflict','deployment_id já foi usado por outro plano.',409)
    validations={app['service']:validate_image_labels(request,app) for app in request['applications']}
    network=network_name(deployment_id);docker('network','create','--label',f'org.cloudiff.deployment={deployment_id}','--label',f'org.cloudiff.environment={request["environment"]}',network,timeout=30)
    services=[];safe_dependencies=[]
    try:
        for dependency in request['dependencies']:
            safe,bindings=ensure_mongodb_dependency(request,network,dependency);safe_dependencies.append(safe);target=dependency['service']
            collisions=sorted(set(request['variables'][target])&set(bindings))
            if collisions:raise DeploymentError('dependency_variable_collision','Bindings gerados colidem com variáveis do serviço.',409,{'name':dependency['name'],'variables':collisions})
            request['variables'][target].update(bindings)
        for app in request['applications']:
            service=app['service'];name=container_name(deployment_id,service)
            generated={'CLOUDIF_PROJECT_SLUG':request['project_slug'],'CLOUDIF_ENVIRONMENT':request['environment'],'CLOUDIF_CONFIG_REVISION':str(request['config_revision']),'CLOUDIF_BUILD_JOB_ID':request['build_job_id'],'CLOUDIF_DEPLOYMENT_ID':deployment_id,'CLOUDIF_SERVICE':service}
            variables={**request['variables'].get(service,{}),**generated};path=env_file(deployment_id,service,variables)
            try:
                command=['run','-d','--name',name,'--network',network,'--network-alias',service,'--restart','unless-stopped','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=64m','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256','--memory','512m','--cpus','1.0','-p',f'127.0.0.1::{app["port"]}','--env-file',str(path),'--label',f'org.cloudiff.deployment={deployment_id}','--label',f'org.cloudiff.environment={request["environment"]}','--label',f'org.cloudiff.project={request["project_slug"]}','--label',f'org.cloudiff.service={service}',app['image_id']]
                container_id=docker(*command,timeout=120).stdout.strip()
            finally:path.unlink(missing_ok=True)
            dependency_containers=[item['container_name'] for item in safe_dependencies if item['service']==service]
            services.append({**app,'container_name':name,'container_id':container_id,'host_port':assigned_port(name,app['port']),'image_validation':validations[service],'variable_names':sorted(variables),'dependency_containers':dependency_containers})
        health={item['service']:probe(item['host_port'],item['healthcheck'],time.time()+90) for item in services};failed={name:value for name,value in health.items() if not value.get('ok')}
        if failed:raise DeploymentError('deployment_healthcheck_failed','Um ou mais serviços não ficaram prontos.',409,failed)
        safe_services=[{key:value for key,value in item.items() if key not in {'host_port','image_validation'}} for item in services]
        conn=db();conn.execute('insert into deployments(deployment_id,project_slug,environment,build_job_id,plan_digest,build_plan_digest,config_revision,config_digest,toolchain_digest,archive_sha256,variables_digest,status,services_json,routes_json,error_json,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(deployment_id,request['project_slug'],request['environment'],request['build_job_id'],request['deployment_plan_digest'],request['build_plan_digest'],request['config_revision'],request['config_digest'],request['toolchain_digest'],request['archive_sha256'],request['variables_digest'],'running',json.dumps(services,separators=(',',':')),json.dumps(request['routes'],separators=(',',':')),'{}',now,now));conn.commit();conn.close()
        _runtime_state_record(request,runtime_configuration,'running')
        safe_dependencies_out=[{key:value for key,value in item.items() if key not in {'container_id','created_container','created_volume'}} for item in safe_dependencies]
        return {'ok':True,'deployment_id':deployment_id,'project_slug':request['project_slug'],'environment':request['environment'],'build_job_id':request['build_job_id'],'status':'running','services':safe_services,'dependencies':safe_dependencies_out,'routes':request['routes'],'health':health,'created_at':now,'network_internal':False,'ports_loopback_only':True,'dependency_ports_published':False,'persistent_dependencies':bool(safe_dependencies),'read_only':True,'capabilities_dropped':True,'variables_digest':request['variables_digest'],'variable_values_returned':False,'secrets_persisted':False,'idempotent':False}
    except Exception as error:
        cleanup_resources(deployment_id,[item['container_name'] for item in safe_dependencies]);detail=error.as_dict() if isinstance(error,DeploymentError) else {'code':'deployment_create_failed','message':type(error).__name__}
        conn=db();conn.execute('insert or replace into deployments(deployment_id,project_slug,environment,build_job_id,plan_digest,build_plan_digest,config_revision,config_digest,toolchain_digest,archive_sha256,variables_digest,status,services_json,routes_json,error_json,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(deployment_id,request['project_slug'],request['environment'],request['build_job_id'],request['deployment_plan_digest'],request['build_plan_digest'],request['config_revision'],request['config_digest'],request['toolchain_digest'],request['archive_sha256'],request['variables_digest'],'failed','[]',json.dumps(request['routes'],separators=(',',':')),json.dumps(detail,separators=(',',':')),now,now));conn.commit();conn.close();raise


def row_to_status(row:sqlite3.Row)->dict:
    services=json.loads(row['services_json'] or '[]');safe=[]
    for item in services:
        safe.append({key:value for key,value in item.items() if key not in {'host_port','image_validation'}})
    result={'ok':True,'deployment_id':row['deployment_id'],'project_slug':row['project_slug'],'environment':row['environment'],'build_job_id':row['build_job_id'],'plan_digest':row['plan_digest'],'build_plan_digest':row['build_plan_digest'],'config_revision':row['config_revision'],'config_digest':row['config_digest'],'toolchain_digest':row['toolchain_digest'],'archive_sha256':row['archive_sha256'],'variables_digest':row['variables_digest'],'status':row['status'],'services':safe,'routes':json.loads(row['routes_json'] or '[]'),'error':json.loads(row['error_json'] or '{}'),'created_at':row['created_at'],'updated_at':row['updated_at'],'ports_loopback_only':True,'dependency_ports_published':False,'persistent_dependencies':any(bool(item.get('dependency_containers')) for item in services),'variable_values_returned':False,'secrets_persisted':False}
    if 'snapshot_id' in row.keys() and str(row['snapshot_id'] or ''):
        result.update({'source_kind':'linked-compose','snapshot_id':str(row['snapshot_id']),'snapshotBacked':True,'secretValuesPersistedRootOnly':True});result['secrets_persisted']=True
    return result


def status_deployment(deployment_id:str)->dict:
    if not DEPLOYMENT_RE.fullmatch(deployment_id):raise DeploymentError('invalid_deployment_id','deployment_id é inválido.',400)
    conn=db();row=conn.execute('select * from deployments where deployment_id=?',(deployment_id,)).fetchone();conn.close()
    if not row:raise DeploymentError('deployment_not_found','Deploy não encontrado.',404)
    result=row_to_status(row)
    if row['status']=='running':
        persisted=json.loads(row['services_json'] or '[]');names={item['container_name'] for item in persisted};names.update(name for item in persisted for name in (item.get('dependency_containers') or []));active=set(docker('ps','--format','{{.Names}}',check=False).stdout.splitlines())
        if not names<=active:
            conn=db();conn.execute("update deployments set status='failed',error_json=?,updated_at=? where deployment_id=?",(json.dumps({'code':'deployment_container_missing','message':'Um container não está em execução.'},separators=(',',':')),int(time.time()),deployment_id));conn.commit();conn.close();result['status']='failed'
    return result


def remove_deployment(deployment_id:str,reason:str='removed')->dict:
    status_deployment(deployment_id);connection=db();row=connection.execute('select services_json from deployments where deployment_id=?',(deployment_id,)).fetchone();connection.close();persisted=json.loads((row['services_json'] if row else '') or '[]');dependencies=[name for item in persisted for name in (item.get('dependency_containers') or [])];cleanup=cleanup_resources(deployment_id,dependencies);now=int(time.time())
    conn=db();conn.execute('update deployments set status=?,updated_at=? where deployment_id=?',(reason,now,deployment_id));conn.execute('update runtime_states set status=?,updated_at=? where deployment_id=?',(reason,now,deployment_id));conn.commit();conn.close()
    return {'ok':True,'deployment_id':deployment_id,'status':reason,**cleanup,'removed_at':now}


class Handler(BaseHTTPRequestHandler):
    server_version='CloudIFFMultiserviceDeploymentExecutor/1'
    def log_message(self,*args):pass
    def authorized(self):return _runtime_state_authorized(self.headers)
    def out(self,status:int,data:dict):
        raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def body(self):
        size=int(self.headers.get('Content-Length','0') or '0')
        if size<2 or size>MAX_BODY:raise DeploymentError('invalid_length','Corpo inválido.',400)
        data=json.loads(self.rfile.read(size));return data
    def error(self,error):
        if isinstance(error,DeploymentError):return self.out(error.status,{'ok':False,'error':error.as_dict()})
        return self.out(500,{'ok':False,'error':{'code':'deployment_executor_failed','message':'O executor falhou.'}})
    def do_GET(self):
        if self.path=='/health':
            conn=db();counts={row['status']:row['n'] for row in conn.execute('select status,count(*) n from deployments group by status')};conn.close();return self.out(200,{'ok':True,'service':'cloudif-multiservice-deployment-executor','deployments':counts,'portsLoopbackOnly':True,'persistent':True,'variableValuesReturned':False})
        if not self.authorized():return self.out(401,{'ok':False,'error':{'code':'unauthorized','message':'Credencial interna inválida.'}})
        parsed=urllib.parse.urlparse(self.path);runtime_match=re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/runtime-state',parsed.path)
        if runtime_match:
            environment=(urllib.parse.parse_qs(parsed.query).get('environment') or [''])[0]
            try:return self.out(200,project_runtime_state(runtime_match.group(1),environment))
            except Exception as error:return self.error(error)
        source_match=re.fullmatch(r'/v1/compose-sources/([a-z0-9][a-z0-9-]{0,62})',parsed.path)
        if source_match:
            try:return self.out(200,compose_source_state(source_match.group(1)))
            except Exception as error:return self.error(error)
        snapshot_match=re.fullmatch(r'/v1/compose-snapshots/(snap_[a-f0-9]{24})',parsed.path)
        if snapshot_match:
            try:return self.out(200,compose_snapshot_status(snapshot_match.group(1)))
            except Exception as error:return self.error(error)
        match=re.fullmatch(r'/v1/deployments/(dep_[a-f0-9]{24})',parsed.path)
        if match:
            try:return self.out(200,status_deployment(match.group(1)))
            except Exception as error:return self.error(error)
        return self.out(404,{'ok':False,'error':{'code':'not_found','message':'Rota não encontrada.'}})
    def do_POST(self):
        if not self.authorized():return self.out(401,{'ok':False,'error':{'code':'unauthorized','message':'Credencial interna inválida.'}})
        try:
            if self.path=='/v1/deployments':return self.out(201,create_deployment(self.body()))
            if self.path=='/v1/compose-snapshots/deploy':return self.out(201,deploy_compose_snapshot(self.body()))
            if self.path=='/v1/compose-source-preview-bridge':return self.out(201,ensure_source_preview_bridge(self.body()))
            if self.path=='/v1/publication-bridges':return self.out(201,ensure_publication_bridge(self.body()))
            if self.path=='/v1/publication-bridges/activate':return self.out(200,activate_publication_bridge(self.body()))
            return self.out(404,{'ok':False,'error':{'code':'not_found','message':'Rota não encontrada.'}})
        except Exception as error:return self.error(error)
    def do_DELETE(self):
        if not self.authorized():return self.out(401,{'ok':False,'error':{'code':'unauthorized','message':'Credencial interna inválida.'}})
        match=re.fullmatch(r'/v1/deployments/(dep_[a-f0-9]{24})',self.path)
        if match:
            try:return self.out(200,remove_deployment(match.group(1)))
            except Exception as error:return self.error(error)
        return self.out(404,{'ok':False,'error':{'code':'not_found','message':'Rota não encontrada.'}})


if __name__=='__main__':
    if not TOKEN:raise SystemExit('missing token')
    init_db();ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
