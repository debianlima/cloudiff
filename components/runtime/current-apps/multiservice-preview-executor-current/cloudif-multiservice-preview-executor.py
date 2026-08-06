#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import os
import re
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST=os.environ.get('CLOUDIF_MULTISERVICE_PREVIEW_EXECUTOR_HOST','10.62.91.2')
PORT=int(os.environ.get('CLOUDIF_MULTISERVICE_PREVIEW_EXECUTOR_PORT','18227'))
TOKEN=(os.environ.get('CLOUDIF_PREVIEW_EXECUTOR_TOKEN') or '').strip()
DB_PATH=Path(os.environ.get('CLOUDIF_PREVIEW_EXECUTOR_DB','/var/lib/cloudif/multiservice-preview-executor/previews.db'))
MAX_BODY=2*1024*1024
MAX_SERVICES=16
PREVIEW_RE=re.compile(r'^pv_[a-f0-9]{24}$')
SLUG_RE=re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
SERVICE_RE=re.compile(r'^[a-z][a-z0-9-]{0,31}$')
IMAGE_RE=re.compile(r'^sha256:[a-f0-9]{64}$')
SHA_RE=re.compile(r'^[a-f0-9]{64}$')
JOB_RE=re.compile(r'^build_[a-f0-9]{24}$')
HOP_HEADERS={'connection','keep-alive','proxy-authenticate','proxy-authorization','te','trailers','transfer-encoding','upgrade','set-cookie'}
REQUEST_HEADERS={'accept','accept-encoding','accept-language','content-type','if-match','if-none-match','if-modified-since','if-unmodified-since','range','user-agent'}
RESPONSE_HEADERS={'content-type','content-encoding','cache-control','etag','last-modified','accept-ranges','content-range','location','vary'}


class PreviewError(RuntimeError):
    def __init__(self,code:str,message:str,status:int=422,detail:Any=None):
        super().__init__(code);self.code=code;self.message=message;self.status=status;self.detail=detail
    def as_dict(self):
        out={'code':self.code,'message':self.message,'documentation':'multiservice-preview-v1'}
        if self.detail is not None:out['detail']=self.detail
        return out


def db()->sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(DB_PATH,timeout=20);conn.row_factory=sqlite3.Row
    conn.execute('pragma busy_timeout=20000')
    return conn


def init_db():
    conn=db();conn.execute('pragma journal_mode=delete')
    conn.executescript('''
    create table if not exists previews(
      preview_id text primary key,
      project_slug text not null,
      build_job_id text not null,
      plan_digest text not null,
      config_revision integer not null,
      archive_sha256 text not null,
      status text not null,
      services_json text not null,
      routes_json text not null,
      error_json text not null default '{}',
      created_at integer not null,
      expires_at integer not null,
      updated_at integer not null
    );
    create index if not exists idx_previews_expiry on previews(status,expires_at);
    ''')
    conn.commit();conn.close();os.chmod(DB_PATH,0o600)


def docker(*args:str,timeout:int=60,check:bool=True)->subprocess.CompletedProcess:
    result=subprocess.run(['docker',*args],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if check and result.returncode:
        raise PreviewError('docker_operation_failed','A operação Docker do preview falhou.',502,{'operation':args[:3],'error':result.stderr[-500:]})
    return result


def inspect_image(image_id:str)->dict:
    result=docker('image','inspect',image_id,timeout=30)
    rows=json.loads(result.stdout)
    if not rows:raise PreviewError('image_not_found','A imagem do build não existe no executor.',404)
    return rows[0]


def normalize_route(item:Any,index:int,services:set[str])->dict:
    if not isinstance(item,dict):raise PreviewError('invalid_route','Cada rota deve ser um objeto.',detail={'index':index})
    prefix=str(item.get('pathPrefix') or '').strip()
    service=str(item.get('service') or '').strip()
    strip=bool(item.get('stripPrefix',False))
    if not prefix.startswith('/') or '//' in prefix or '..' in prefix or len(prefix)>128:
        raise PreviewError('invalid_route_prefix','A rota deve começar com / e não pode conter .. ou //.',detail={'index':index})
    if len(prefix)>1:prefix=prefix.rstrip('/')
    if service not in services:raise PreviewError('route_service_not_found','A rota aponta para serviço inexistente.',detail={'index':index,'service':service})
    return {'pathPrefix':prefix,'service':service,'stripPrefix':strip}


def normalize_payload(payload:Any)->dict:
    if not isinstance(payload,dict):raise PreviewError('invalid_request','A solicitação deve ser um objeto.',400)
    required={'preview_id','project_slug','build_job_id','plan_digest','config_revision','archive_sha256','applications','routes','ttl_seconds'}
    if not required.issubset(payload):raise PreviewError('required_field_missing','Campos obrigatórios estão ausentes.',400,{'missing':sorted(required-set(payload))})
    preview_id=str(payload.get('preview_id') or '');slug=str(payload.get('project_slug') or '');job=str(payload.get('build_job_id') or '')
    plan=str(payload.get('plan_digest') or '').lower();archive=str(payload.get('archive_sha256') or '').lower();revision=int(payload.get('config_revision') or 0);ttl=int(payload.get('ttl_seconds') or 0)
    if not PREVIEW_RE.fullmatch(preview_id):raise PreviewError('invalid_preview_id','preview_id é inválido.',400)
    if not SLUG_RE.fullmatch(slug):raise PreviewError('invalid_project_slug','project_slug é inválido.',400)
    if not JOB_RE.fullmatch(job):raise PreviewError('invalid_build_job_id','build_job_id é inválido.',400)
    if not SHA_RE.fullmatch(plan) or not SHA_RE.fullmatch(archive):raise PreviewError('invalid_digest','plan_digest ou archive_sha256 é inválido.',400)
    if revision<1:raise PreviewError('configuration_required','O preview exige uma revisão de configuração aprovada.')
    if not 300<=ttl<=7200:raise PreviewError('invalid_ttl','ttl_seconds deve estar entre 300 e 7200.',400)
    applications=payload.get('applications')
    if not isinstance(applications,list) or not 1<=len(applications)<=MAX_SERVICES:raise PreviewError('invalid_applications','applications deve conter entre 1 e 16 serviços.')
    normalized=[];names=set()
    for index,raw in enumerate(applications):
        if not isinstance(raw,dict):raise PreviewError('invalid_application','Cada aplicação deve ser um objeto.',detail={'index':index})
        name=str(raw.get('service') or '');image=str(raw.get('image_id') or '');digest=str(raw.get('application_digest') or '').lower();port=int(raw.get('port') or 0);health=str(raw.get('healthcheck') or '/')
        if not SERVICE_RE.fullmatch(name) or name in names:raise PreviewError('invalid_service_name','Nome de serviço inválido ou duplicado.',detail={'index':index})
        names.add(name)
        if not IMAGE_RE.fullmatch(image):raise PreviewError('invalid_image_id','O preview aceita somente imageId sha256.',detail={'service':name})
        if not SHA_RE.fullmatch(digest):raise PreviewError('invalid_application_digest','application_digest é inválido.',detail={'service':name})
        if not 1024<=port<=65535:raise PreviewError('invalid_container_port','A porta interna deve estar entre 1024 e 65535.',detail={'service':name})
        if not health.startswith('/') or '..' in health or len(health)>256:raise PreviewError('invalid_healthcheck','healthcheck deve ser um caminho HTTP relativo.',detail={'service':name})
        normalized.append({'service':name,'image_id':image,'application_digest':digest,'port':port,'healthcheck':health})
    routes=payload.get('routes')
    if not isinstance(routes,list) or not routes:raise PreviewError('routes_required','O preview exige ao menos uma rota.')
    normalized_routes=[normalize_route(item,index,names) for index,item in enumerate(routes)]
    prefixes=[item['pathPrefix'] for item in normalized_routes]
    if len(prefixes)!=len(set(prefixes)):raise PreviewError('duplicate_route','Rotas duplicadas não são permitidas.')
    if '/' not in prefixes:raise PreviewError('root_route_required','Uma rota raiz / é obrigatória.')
    return {'preview_id':preview_id,'project_slug':slug,'build_job_id':job,'plan_digest':plan,'config_revision':revision,'archive_sha256':archive,'applications':normalized,'routes':sorted(normalized_routes,key=lambda x:len(x['pathPrefix']),reverse=True),'ttl_seconds':ttl}


def validate_image_labels(request:dict,app:dict)->dict:
    data=inspect_image(app['image_id']);config=data.get('Config') or {};labels=config.get('Labels') or {}
    expected={'org.cloudiff.kind':'application','org.cloudiff.project':request['project_slug'],'org.cloudiff.service':app['service'],'org.cloudiff.config-revision':str(request['config_revision']),'org.cloudiff.archive-sha256':request['archive_sha256'],'org.cloudiff.application-digest':app['application_digest']}
    mismatch={key:{'expected':value,'actual':labels.get(key)} for key,value in expected.items() if str(labels.get(key) or '')!=str(value)}
    if mismatch:raise PreviewError('image_label_mismatch','A imagem não corresponde ao projeto, revisão ou archive aprovados.',409,{'service':app['service'],'mismatch':mismatch})
    user=str(config.get('User') or '')
    if user in {'','0','root','0:0'}:raise PreviewError('image_user_policy_failed','A imagem do preview não pode executar como root.',409,{'service':app['service'],'user':user})
    return {'image_id':data.get('Id'),'user':user,'labels':expected}


def network_name(preview_id:str)->str:return 'cloudif-'+preview_id.replace('_','-')
def container_name(preview_id:str,service:str)->str:return 'cloudif-'+preview_id.replace('_','-')+'-'+service


def assigned_port(name:str,container_port:int)->int:
    data=json.loads(docker('inspect',name,timeout=30).stdout)[0]
    bindings=((data.get('NetworkSettings') or {}).get('Ports') or {}).get(f'{container_port}/tcp') or []
    for binding in bindings:
        if str(binding.get('HostIp') or '')=='127.0.0.1' and str(binding.get('HostPort') or '').isdigit():return int(binding['HostPort'])
    raise PreviewError('preview_port_unavailable','A porta local do preview não foi atribuída.',502,{'container':name})


def probe(port:int,path:str,deadline:float)->dict:
    last='not_started'
    while time.time()<deadline:
        try:
            request=urllib.request.Request(f'http://127.0.0.1:{port}{path}',headers={'User-Agent':'CloudIFF-preview-health'})
            with urllib.request.urlopen(request,timeout=3) as response:
                if response.status<500:return {'ok':True,'status':response.status,'path':path}
                last='http_'+str(response.status)
        except urllib.error.HTTPError as error:
            if error.code<500:return {'ok':True,'status':error.code,'path':path}
            last='http_'+str(error.code)
        except Exception as error:last=type(error).__name__
        time.sleep(1)
    return {'ok':False,'status':last,'path':path}


def cleanup_resources(preview_id:str)->dict:
    prefix='cloudif-'+preview_id.replace('_','-')+'-'
    names=docker('ps','-a','--format','{{.Names}}',check=False).stdout.splitlines()
    removed=[]
    for name in names:
        if name.startswith(prefix):
            docker('rm','-f',name,timeout=30,check=False);removed.append(name)
    docker('network','rm',network_name(preview_id),timeout=30,check=False)
    return {'containersRemoved':len(removed),'networkRemoved':True}


def create_preview(payload:Any)->dict:
    request=normalize_payload(payload);preview_id=request['preview_id'];now=int(time.time())
    conn=db();row=conn.execute('select * from previews where preview_id=?',(preview_id,)).fetchone();conn.close()
    if row:
        if row['plan_digest']==request['plan_digest'] and row['status']=='running':
            result=status_preview(preview_id);result['idempotent']=True;return result
        raise PreviewError('preview_id_conflict','preview_id já foi usado por outro plano.',409)
    validations={app['service']:validate_image_labels(request,app) for app in request['applications']}
    network=network_name(preview_id);docker('network','create','--internal','--label',f'org.cloudiff.preview={preview_id}',network,timeout=30)
    services=[]
    try:
        for app in request['applications']:
            name=container_name(preview_id,app['service'])
            command=['run','-d','--name',name,'--network',network,'--network-alias',app['service'],'--restart','no','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=64m','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256','--memory','512m','--cpus','1.0','-p',f'127.0.0.1::{app["port"]}','--label',f'org.cloudiff.preview={preview_id}','--label',f'org.cloudiff.service={app["service"]}',app['image_id']]
            container_id=docker(*command,timeout=90).stdout.strip();host_port=assigned_port(name,app['port'])
            services.append({**app,'container_name':name,'container_id':container_id,'host_port':host_port,'image_validation':validations[app['service']]})
        health={item['service']:probe(item['host_port'],item['healthcheck'],time.time()+75) for item in services}
        failed={name:value for name,value in health.items() if not value.get('ok')}
        if failed:raise PreviewError('preview_healthcheck_failed','Um ou mais serviços não ficaram prontos.',409,failed)
        expires=now+request['ttl_seconds']
        conn=db();conn.execute('insert into previews(preview_id,project_slug,build_job_id,plan_digest,config_revision,archive_sha256,status,services_json,routes_json,error_json,created_at,expires_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?)',(preview_id,request['project_slug'],request['build_job_id'],request['plan_digest'],request['config_revision'],request['archive_sha256'],'running',json.dumps(services,separators=(',',':')),json.dumps(request['routes'],separators=(',',':')),'{}',now,expires,now));conn.commit();conn.close()
        return {'ok':True,'preview_id':preview_id,'project_slug':request['project_slug'],'build_job_id':request['build_job_id'],'status':'running','services':[{key:value for key,value in item.items() if key not in {'host_port','image_validation'}} for item in services],'routes':request['routes'],'health':health,'created_at':now,'expires_at':expires,'ttl_seconds':request['ttl_seconds'],'network_internal':True,'ports_loopback_only':True,'read_only':True,'capabilities_dropped':True,'secrets_included':False,'idempotent':False}
    except Exception as error:
        cleanup_resources(preview_id)
        detail=error.as_dict() if isinstance(error,PreviewError) else {'code':'preview_create_failed','message':str(error)[:200]}
        conn=db();conn.execute('insert or replace into previews(preview_id,project_slug,build_job_id,plan_digest,config_revision,archive_sha256,status,services_json,routes_json,error_json,created_at,expires_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?)',(preview_id,request['project_slug'],request['build_job_id'],request['plan_digest'],request['config_revision'],request['archive_sha256'],'failed','[]',json.dumps(request['routes'],separators=(',',':')),json.dumps(detail,separators=(',',':')),now,now,now));conn.commit();conn.close()
        raise


def row_to_status(row:sqlite3.Row)->dict:
    services=json.loads(row['services_json'] or '[]');routes=json.loads(row['routes_json'] or '[]');error=json.loads(row['error_json'] or '{}')
    safe_services=[{key:value for key,value in item.items() if key not in {'host_port','image_validation'}} for item in services]
    return {'ok':True,'preview_id':row['preview_id'],'project_slug':row['project_slug'],'build_job_id':row['build_job_id'],'plan_digest':row['plan_digest'],'config_revision':row['config_revision'],'archive_sha256':row['archive_sha256'],'status':row['status'],'services':safe_services,'routes':routes,'error':error,'created_at':row['created_at'],'expires_at':row['expires_at'],'updated_at':row['updated_at'],'network_internal':True,'ports_loopback_only':True,'secrets_included':False}


def status_preview(preview_id:str)->dict:
    if not PREVIEW_RE.fullmatch(preview_id):raise PreviewError('invalid_preview_id','preview_id é inválido.',400)
    conn=db();row=conn.execute('select * from previews where preview_id=?',(preview_id,)).fetchone();conn.close()
    if not row:raise PreviewError('preview_not_found','Preview não encontrado.',404)
    result=row_to_status(row)
    if row['status']=='running':
        names={item['container_name'] for item in json.loads(row['services_json'] or '[]')}
        active=set(docker('ps','--format','{{.Names}}',check=False).stdout.splitlines())
        if not names<=active:
            conn=db();conn.execute("update previews set status='failed',error_json=?,updated_at=? where preview_id=?",(json.dumps({'code':'preview_container_missing','message':'Um container do preview não está em execução.'},separators=(',',':')),int(time.time()),preview_id));conn.commit();conn.close();result['status']='failed'
    return result


def delete_preview(preview_id:str,reason:str='deleted')->dict:
    status=status_preview(preview_id);cleanup=cleanup_resources(preview_id);now=int(time.time())
    conn=db();conn.execute('update previews set status=?,updated_at=? where preview_id=?',(reason,now,preview_id));conn.commit();conn.close()
    return {'ok':True,'preview_id':preview_id,'status':reason,**cleanup,'deleted_at':now}


def route_target(row:sqlite3.Row,path:str)->tuple[dict,str]:
    routes=json.loads(row['routes_json'] or '[]');services={item['service']:item for item in json.loads(row['services_json'] or '[]')}
    selected=None
    for route in sorted(routes,key=lambda item:len(item['pathPrefix']),reverse=True):
        prefix=route['pathPrefix']
        if prefix=='/' or path==prefix or path.startswith(prefix.rstrip('/')+'/'):
            selected=route;break
    if not selected:raise PreviewError('preview_route_not_found','Nenhuma rota do preview corresponde ao caminho.',404)
    service=services.get(selected['service'])
    if not service:raise PreviewError('preview_service_not_found','O serviço da rota não está disponível.',404)
    target=path
    if selected.get('stripPrefix') and selected['pathPrefix']!='/':
        target=path[len(selected['pathPrefix']):] or '/'
        if not target.startswith('/'):target='/'+target
    return service,target


def proxy_preview(preview_id:str,path:str,method:str,headers:dict[str,str],body:bytes)->tuple[int,dict[str,str],bytes]:
    if not PREVIEW_RE.fullmatch(preview_id):raise PreviewError('invalid_preview_id','preview_id é inválido.',400)
    conn=db();row=conn.execute("select * from previews where preview_id=? and status='running'",(preview_id,)).fetchone();conn.close()
    if not row:raise PreviewError('preview_not_running','O preview não está em execução.',404)
    if int(row['expires_at'])<=int(time.time()):
        delete_preview(preview_id,'expired');raise PreviewError('preview_expired','O preview expirou.',410)
    parts=urllib.parse.urlsplit(path)
    service,target=route_target(row,parts.path or '/')
    if parts.query:target+='?'+parts.query
    request_headers={key:value for key,value in headers.items() if key.lower() in REQUEST_HEADERS and key.lower() not in HOP_HEADERS}
    request_headers['X-Forwarded-Prefix']='/cloudiff/portal/preview/'+preview_id
    request=urllib.request.Request(f'http://127.0.0.1:{service["host_port"]}{target}',data=body if method not in {'GET','HEAD'} else None,method=method,headers=request_headers)
    try:
        with urllib.request.urlopen(request,timeout=30) as response:
            raw=response.read(MAX_BODY+1);status=response.status;response_headers={key:value for key,value in response.headers.items() if key.lower() in RESPONSE_HEADERS and key.lower() not in HOP_HEADERS}
    except urllib.error.HTTPError as error:
        raw=error.read(MAX_BODY+1);status=error.code;response_headers={key:value for key,value in error.headers.items() if key.lower() in RESPONSE_HEADERS and key.lower() not in HOP_HEADERS}
    if len(raw)>MAX_BODY:raise PreviewError('preview_response_too_large','A resposta do preview excede 2 MiB.',502)
    return status,response_headers,raw


def expire_loop():
    while True:
        try:
            now=int(time.time());conn=db();rows=conn.execute("select preview_id from previews where status='running' and expires_at<=?",(now,)).fetchall();conn.close()
            for row in rows:
                try:delete_preview(row['preview_id'],'expired')
                except Exception:pass
        except Exception:pass
        time.sleep(10)


class Handler(BaseHTTPRequestHandler):
    server_version='CloudIFFPreviewExecutor/1'
    def log_message(self,*args):pass
    def authorized(self):return bool(TOKEN) and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+TOKEN)
    def out(self,status:int,data:dict,headers:dict[str,str]|None=None):
        raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        for key,value in (headers or {}).items():self.send_header(key,value)
        self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def subpath_with_query(self,match):
        parts=urllib.parse.urlsplit(self.path);subpath=match.group(2) or '/'
        return subpath+('?' + parts.query if parts.query else '')
    def body(self)->bytes:
        size=int(self.headers.get('Content-Length','0') or '0')
        if size<0 or size>MAX_BODY:raise PreviewError('request_too_large','A solicitação excede 2 MiB.',413)
        return self.rfile.read(size) if size else b''
    def handle_error(self,error:Exception):
        if isinstance(error,PreviewError):return self.out(error.status,{'ok':False,'error':error.as_dict()})
        return self.out(500,{'ok':False,'error':{'code':'preview_executor_failed','message':'O executor de preview falhou.'}})
    def do_GET(self):
        if self.path=='/health':
            conn=db();counts={row['status']:row['n'] for row in conn.execute('select status,count(*) n from previews group by status')};conn.close();return self.out(200,{'ok':True,'service':'cloudif-multiservice-preview-executor','previews':counts,'networkInternal':True,'portsLoopbackOnly':True,'ttlCleanup':True})
        if not self.authorized():return self.out(401,{'ok':False,'error':{'code':'unauthorized','message':'Credencial interna inválida.'}})
        match=re.fullmatch(r'/v1/previews/(pv_[a-f0-9]{24})',urllib.parse.urlsplit(self.path).path)
        if match:
            try:return self.out(200,status_preview(match.group(1)))
            except Exception as error:return self.handle_error(error)
        match=re.fullmatch(r'/v1/proxy/(pv_[a-f0-9]{24})(/.*)?',urllib.parse.urlsplit(self.path).path)
        if match:return self.proxy(match.group(1),self.subpath_with_query(match), 'GET')
        return self.out(404,{'ok':False,'error':{'code':'not_found','message':'Rota não encontrada.'}})
    def do_HEAD(self):
        if not self.authorized():return self.out(401,{'ok':False,'error':{'code':'unauthorized','message':'Credencial interna inválida.'}})
        match=re.fullmatch(r'/v1/proxy/(pv_[a-f0-9]{24})(/.*)?',urllib.parse.urlsplit(self.path).path)
        if match:return self.proxy(match.group(1),self.subpath_with_query(match),'HEAD')
        return self.out(404,{'ok':False,'error':{'code':'not_found','message':'Rota não encontrada.'}})
    def do_POST(self):
        if not self.authorized():return self.out(401,{'ok':False,'error':{'code':'unauthorized','message':'Credencial interna inválida.'}})
        path=urllib.parse.urlsplit(self.path).path
        if path=='/v1/previews':
            try:return self.out(201,create_preview(json.loads(self.body() or b'{}')))
            except Exception as error:return self.handle_error(error)
        match=re.fullmatch(r'/v1/proxy/(pv_[a-f0-9]{24})(/.*)?',path)
        if match:return self.proxy(match.group(1),self.subpath_with_query(match),'POST')
        return self.out(404,{'ok':False,'error':{'code':'not_found','message':'Rota não encontrada.'}})
    def do_PUT(self):return self.proxy_method('PUT')
    def do_PATCH(self):return self.proxy_method('PATCH')
    def do_DELETE(self):
        if not self.authorized():return self.out(401,{'ok':False,'error':{'code':'unauthorized','message':'Credencial interna inválida.'}})
        path=urllib.parse.urlsplit(self.path).path
        match=re.fullmatch(r'/v1/previews/(pv_[a-f0-9]{24})',path)
        if match:
            try:return self.out(200,delete_preview(match.group(1)))
            except Exception as error:return self.handle_error(error)
        match=re.fullmatch(r'/v1/proxy/(pv_[a-f0-9]{24})(/.*)?',path)
        if match:return self.proxy(match.group(1),self.subpath_with_query(match),'DELETE')
        return self.out(404,{'ok':False,'error':{'code':'not_found','message':'Rota não encontrada.'}})
    def proxy_method(self,method):
        if not self.authorized():return self.out(401,{'ok':False,'error':{'code':'unauthorized','message':'Credencial interna inválida.'}})
        match=re.fullmatch(r'/v1/proxy/(pv_[a-f0-9]{24})(/.*)?',urllib.parse.urlsplit(self.path).path)
        if match:return self.proxy(match.group(1),self.subpath_with_query(match),method)
        return self.out(404,{'ok':False,'error':{'code':'not_found','message':'Rota não encontrada.'}})
    def proxy(self,preview_id,path,method):
        try:
            body=self.body() if method not in {'GET','HEAD'} else b''
            status,headers,raw=proxy_preview(preview_id,path,method,{key:value for key,value in self.headers.items()},body)
            self.send_response(status);self.send_header('Cache-Control',headers.pop('Cache-Control','no-store'));self.send_header('X-Content-Type-Options','nosniff')
            for key,value in headers.items():
                if key.lower() not in HOP_HEADERS:self.send_header(key,value)
            self.send_header('Content-Length',str(0 if method=='HEAD' else len(raw)));self.end_headers()
            if method!='HEAD':self.wfile.write(raw)
        except Exception as error:return self.handle_error(error)


if __name__=='__main__':
    init_db();threading.Thread(target=expire_loop,daemon=True).start();ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
