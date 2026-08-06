#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
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
    ''')
    conn.commit();conn.close();os.chmod(DB_PATH,0o600)


def docker(*args:str,timeout:int=90,check:bool=True)->subprocess.CompletedProcess:
    result=subprocess.run(['docker',*args],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if check and result.returncode:
        raise DeploymentError('docker_operation_failed','A operação Docker do deploy falhou.',502,{'operation':args[:3],'error':result.stderr[-500:]})
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
    return {'deployment_id':deployment_id,'project_slug':slug,'environment':environment,'build_job_id':build_job,'deployment_plan_digest':plan,'build_plan_digest':build_plan,'config_revision':config_revision,'config_digest':config_digest,'toolchain_digest':toolchain_digest,'archive_sha256':archive,'applications':normalized,'routes':sorted(normalized_routes,key=lambda x:len(x['pathPrefix']),reverse=True),'variables':variables,'variables_digest':variables_digest}


def validate_image_labels(request:dict,app:dict)->dict:
    data=inspect_image(app['image_id']);config=data.get('Config') or {};labels=config.get('Labels') or {}
    expected={'org.cloudiff.kind':'application','org.cloudiff.project':request['project_slug'],'org.cloudiff.service':app['service'],'org.cloudiff.config-revision':str(request['config_revision']),'org.cloudiff.config-digest':request['config_digest'],'org.cloudiff.toolchain-digest':request['toolchain_digest'],'org.cloudiff.archive-sha256':request['archive_sha256'],'org.cloudiff.application-digest':app['application_digest']}
    mismatch={key:{'expected':value,'actual':labels.get(key)} for key,value in expected.items() if str(labels.get(key) or '')!=str(value)}
    if mismatch:raise DeploymentError('image_label_mismatch','A imagem não corresponde ao projeto, revisão ou archive aprovados.',409,{'service':app['service'],'mismatch':mismatch})
    user=str(config.get('User') or '')
    if user in {'','0','root','0:0'}:raise DeploymentError('image_user_policy_failed','A imagem não pode executar como root.',409,{'service':app['service'],'user':user})
    return {'image_id':data.get('Id'),'user':user,'labels':expected}


def network_name(deployment_id:str)->str:return 'cloudif-'+deployment_id.replace('_','-')
def container_name(deployment_id:str,service:str)->str:return 'cloudif-'+deployment_id.replace('_','-')+'-'+service


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


def cleanup_resources(deployment_id:str)->dict:
    prefix='cloudif-'+deployment_id.replace('_','-')+'-';names=docker('ps','-a','--format','{{.Names}}',check=False).stdout.splitlines();removed=[]
    for name in names:
        if name.startswith(prefix):docker('rm','-f',name,timeout=30,check=False);removed.append(name)
    docker('network','rm',network_name(deployment_id),timeout=30,check=False)
    return {'containersRemoved':len(removed),'networkRemoved':True}


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


def create_deployment(payload:Any)->dict:
    request=normalize_payload(payload);deployment_id=request['deployment_id'];now=int(time.time())
    conn=db();row=conn.execute('select * from deployments where deployment_id=?',(deployment_id,)).fetchone();conn.close()
    if row:
        if row['plan_digest']==request['deployment_plan_digest'] and row['variables_digest']==request['variables_digest'] and row['status']=='running':
            result=status_deployment(deployment_id);result['idempotent']=True;return result
        raise DeploymentError('deployment_id_conflict','deployment_id já foi usado por outro plano.',409)
    validations={app['service']:validate_image_labels(request,app) for app in request['applications']}
    network=network_name(deployment_id);docker('network','create','--label',f'org.cloudiff.deployment={deployment_id}','--label',f'org.cloudiff.environment={request["environment"]}',network,timeout=30)
    services=[]
    try:
        for app in request['applications']:
            service=app['service'];name=container_name(deployment_id,service)
            generated={'CLOUDIF_PROJECT_SLUG':request['project_slug'],'CLOUDIF_ENVIRONMENT':request['environment'],'CLOUDIF_CONFIG_REVISION':str(request['config_revision']),'CLOUDIF_BUILD_JOB_ID':request['build_job_id'],'CLOUDIF_DEPLOYMENT_ID':deployment_id,'CLOUDIF_SERVICE':service}
            variables={**request['variables'].get(service,{}),**generated};path=env_file(deployment_id,service,variables)
            try:
                command=['run','-d','--name',name,'--network',network,'--network-alias',service,'--restart','unless-stopped','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=64m','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256','--memory','512m','--cpus','1.0','-p',f'127.0.0.1::{app["port"]}','--env-file',str(path),'--label',f'org.cloudiff.deployment={deployment_id}','--label',f'org.cloudiff.environment={request["environment"]}','--label',f'org.cloudiff.project={request["project_slug"]}','--label',f'org.cloudiff.service={service}',app['image_id']]
                container_id=docker(*command,timeout=120).stdout.strip()
            finally:path.unlink(missing_ok=True)
            services.append({**app,'container_name':name,'container_id':container_id,'host_port':assigned_port(name,app['port']),'image_validation':validations[service],'variable_names':sorted(variables)})
        health={item['service']:probe(item['host_port'],item['healthcheck'],time.time()+90) for item in services};failed={name:value for name,value in health.items() if not value.get('ok')}
        if failed:raise DeploymentError('deployment_healthcheck_failed','Um ou mais serviços não ficaram prontos.',409,failed)
        safe_services=[{key:value for key,value in item.items() if key not in {'host_port','image_validation'}} for item in services]
        conn=db();conn.execute('insert into deployments(deployment_id,project_slug,environment,build_job_id,plan_digest,build_plan_digest,config_revision,config_digest,toolchain_digest,archive_sha256,variables_digest,status,services_json,routes_json,error_json,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(deployment_id,request['project_slug'],request['environment'],request['build_job_id'],request['deployment_plan_digest'],request['build_plan_digest'],request['config_revision'],request['config_digest'],request['toolchain_digest'],request['archive_sha256'],request['variables_digest'],'running',json.dumps(services,separators=(',',':')),json.dumps(request['routes'],separators=(',',':')),'{}',now,now));conn.commit();conn.close()
        return {'ok':True,'deployment_id':deployment_id,'project_slug':request['project_slug'],'environment':request['environment'],'build_job_id':request['build_job_id'],'status':'running','services':safe_services,'routes':request['routes'],'health':health,'created_at':now,'network_internal':False,'ports_loopback_only':True,'read_only':True,'capabilities_dropped':True,'variables_digest':request['variables_digest'],'variable_values_returned':False,'secrets_persisted':False,'idempotent':False}
    except Exception as error:
        cleanup_resources(deployment_id);detail=error.as_dict() if isinstance(error,DeploymentError) else {'code':'deployment_create_failed','message':type(error).__name__}
        conn=db();conn.execute('insert or replace into deployments(deployment_id,project_slug,environment,build_job_id,plan_digest,build_plan_digest,config_revision,config_digest,toolchain_digest,archive_sha256,variables_digest,status,services_json,routes_json,error_json,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(deployment_id,request['project_slug'],request['environment'],request['build_job_id'],request['deployment_plan_digest'],request['build_plan_digest'],request['config_revision'],request['config_digest'],request['toolchain_digest'],request['archive_sha256'],request['variables_digest'],'failed','[]',json.dumps(request['routes'],separators=(',',':')),json.dumps(detail,separators=(',',':')),now,now));conn.commit();conn.close();raise


def row_to_status(row:sqlite3.Row)->dict:
    services=json.loads(row['services_json'] or '[]');safe=[]
    for item in services:
        safe.append({key:value for key,value in item.items() if key not in {'host_port','image_validation'}})
    return {'ok':True,'deployment_id':row['deployment_id'],'project_slug':row['project_slug'],'environment':row['environment'],'build_job_id':row['build_job_id'],'plan_digest':row['plan_digest'],'build_plan_digest':row['build_plan_digest'],'config_revision':row['config_revision'],'config_digest':row['config_digest'],'toolchain_digest':row['toolchain_digest'],'archive_sha256':row['archive_sha256'],'variables_digest':row['variables_digest'],'status':row['status'],'services':safe,'routes':json.loads(row['routes_json'] or '[]'),'error':json.loads(row['error_json'] or '{}'),'created_at':row['created_at'],'updated_at':row['updated_at'],'ports_loopback_only':True,'variable_values_returned':False,'secrets_persisted':False}


def status_deployment(deployment_id:str)->dict:
    if not DEPLOYMENT_RE.fullmatch(deployment_id):raise DeploymentError('invalid_deployment_id','deployment_id é inválido.',400)
    conn=db();row=conn.execute('select * from deployments where deployment_id=?',(deployment_id,)).fetchone();conn.close()
    if not row:raise DeploymentError('deployment_not_found','Deploy não encontrado.',404)
    result=row_to_status(row)
    if row['status']=='running':
        names={item['container_name'] for item in json.loads(row['services_json'] or '[]')};active=set(docker('ps','--format','{{.Names}}',check=False).stdout.splitlines())
        if not names<=active:
            conn=db();conn.execute("update deployments set status='failed',error_json=?,updated_at=? where deployment_id=?",(json.dumps({'code':'deployment_container_missing','message':'Um container não está em execução.'},separators=(',',':')),int(time.time()),deployment_id));conn.commit();conn.close();result['status']='failed'
    return result


def remove_deployment(deployment_id:str,reason:str='removed')->dict:
    status_deployment(deployment_id);cleanup=cleanup_resources(deployment_id);now=int(time.time())
    conn=db();conn.execute('update deployments set status=?,updated_at=? where deployment_id=?',(reason,now,deployment_id));conn.commit();conn.close()
    return {'ok':True,'deployment_id':deployment_id,'status':reason,**cleanup,'removed_at':now}


class Handler(BaseHTTPRequestHandler):
    server_version='CloudIFFMultiserviceDeploymentExecutor/1'
    def log_message(self,*args):pass
    def authorized(self):return bool(TOKEN) and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+TOKEN)
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
        match=re.fullmatch(r'/v1/deployments/(dep_[a-f0-9]{24})',self.path)
        if match:
            try:return self.out(200,status_deployment(match.group(1)))
            except Exception as error:return self.error(error)
        return self.out(404,{'ok':False,'error':{'code':'not_found','message':'Rota não encontrada.'}})
    def do_POST(self):
        if not self.authorized():return self.out(401,{'ok':False,'error':{'code':'unauthorized','message':'Credencial interna inválida.'}})
        if self.path!='/v1/deployments':return self.out(404,{'ok':False,'error':{'code':'not_found','message':'Rota não encontrada.'}})
        try:return self.out(201,create_deployment(self.body()))
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
