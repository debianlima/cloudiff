#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST=os.environ.get('CLOUDIF_MULTISERVICE_PREVIEW_HOST','127.0.0.1')
PORT=int(os.environ.get('CLOUDIF_MULTISERVICE_PREVIEW_PORT','18228'))
TOKEN=(os.environ.get('CLOUDIF_MULTISERVICE_PREVIEW_TOKEN') or '').strip()
EXECUTOR_TOKEN=(os.environ.get('CLOUDIF_PREVIEW_EXECUTOR_TOKEN') or '').strip()
EXECUTOR_URL=os.environ.get('CLOUDIF_PREVIEW_EXECUTOR_URL','http://10.62.91.2:18227').rstrip('/')
BUILD_URL=os.environ.get('CLOUDIF_BUILD_URL','http://127.0.0.1:18213').rstrip('/')
BUILD_TOKEN=(os.environ.get('CLOUDIF_BUILD_BROKER_TOKEN') or '').strip()
PUBLIC_ORIGIN=os.environ.get('CLOUDIF_PUBLIC_ORIGIN','https://cloudiff.duckdns.org').rstrip('/')
DB_PATH=Path(os.environ.get('CLOUDIF_MULTISERVICE_PREVIEW_DB','/var/lib/cloudif/multiservice-preview/previews.db'))
MAX_BODY=2*1024*1024
PREVIEW_RE=re.compile(r'^pv_[a-f0-9]{24}$')
JOB_RE=re.compile(r'^build_[a-f0-9]{24}$')
SHA_RE=re.compile(r'^[a-f0-9]{64}$')
SLUG_RE=re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
HOP_HEADERS={'connection','keep-alive','proxy-authenticate','proxy-authorization','te','trailers','transfer-encoding','upgrade','set-cookie'}
SAFE_RESPONSE={'content-type','content-encoding','cache-control','etag','last-modified','accept-ranges','content-range','location','vary'}
SAFE_REQUEST={'accept','accept-encoding','accept-language','content-type','if-match','if-none-match','if-modified-since','if-unmodified-since','range','user-agent'}


class BrokerError(RuntimeError):
    def __init__(self,code:str,message:str,status:int=422,detail:Any=None):
        super().__init__(code);self.code=code;self.message=message;self.status=status;self.detail=detail
    def as_dict(self):
        result={'code':self.code,'message':self.message,'documentation':'multiservice-preview-v1'}
        if self.detail is not None:result['detail']=self.detail
        return result


def canonical(value:Any)->bytes:return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()

def db()->sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True,exist_ok=True);conn=sqlite3.connect(DB_PATH,timeout=20);conn.row_factory=sqlite3.Row;conn.execute('pragma busy_timeout=20000');return conn

def init_db():
    conn=db();conn.execute('pragma journal_mode=delete');conn.executescript('''
    create table if not exists previews(
      preview_id text primary key,
      project_slug text not null,
      build_job_id text not null,
      plan_digest text not null,
      created_by text not null,
      actor_groups_json text not null,
      status text not null,
      result_json text not null,
      created_at integer not null,
      expires_at integer not null,
      updated_at integer not null
    );
    create index if not exists idx_broker_preview_expiry on previews(status,expires_at);
    ''');conn.commit();conn.close();os.chmod(DB_PATH,0o600)


def internal(method:str,url:str,token:str,payload:Any=None,headers:dict[str,str]|None=None,timeout:int=120)->tuple[int,dict[str,str],bytes]:
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode() if payload is not None else None
    request_headers={'Authorization':'Bearer '+token,'Accept':'application/json'}
    if payload is not None:request_headers['Content-Type']='application/json'
    request_headers.update(headers or {})
    request=urllib.request.Request(url,data=raw,method=method,headers=request_headers)
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,dict(response.headers),response.read(MAX_BODY+1)
    except urllib.error.HTTPError as error:return error.code,dict(error.headers),error.read(MAX_BODY+1)


def json_internal(method:str,url:str,token:str,payload:Any=None,timeout:int=120)->tuple[int,dict]:
    status,headers,raw=internal(method,url,token,payload,timeout=timeout)
    try:data=json.loads(raw or b'{}')
    except Exception:data={'ok':False,'error':{'code':'non_json_internal_response','message':'Serviço interno retornou resposta inválida.'}}
    return status,data


def build_status(job_id:str)->dict:
    if not JOB_RE.fullmatch(job_id):raise BrokerError('invalid_job_id','job_id é inválido.',400)
    status,data=json_internal('GET',BUILD_URL+'/v1/multiservice/jobs/'+urllib.parse.quote(job_id,safe=''),BUILD_TOKEN,timeout=60)
    if status==404:raise BrokerError('build_not_found','Build não encontrado.',404)
    if status!=200 or not data.get('ok'):raise BrokerError('build_status_failed','O status do build não pôde ser consultado.',502)
    if data.get('status')!='succeeded':raise BrokerError('build_not_ready','O preview exige um build concluído.',409,{'status':data.get('status'),'jobId':job_id})
    result=data.get('result') or {}
    if not result.get('ok') or not result.get('applications'):raise BrokerError('build_result_invalid','O resultado do build não contém aplicações.',409)
    return data


def normalize_routes(value:Any,applications:list[dict])->list[dict]:
    services=[str(item.get('service') or '') for item in applications]
    names=set(services)
    if value is None:
        primary='web' if 'web' in names else services[0]
        routes=[{'pathPrefix':'/','service':primary,'stripPrefix':False}]
        for name in services:
            if name!=primary:routes.append({'pathPrefix':'/'+name,'service':name,'stripPrefix':True})
        return sorted(routes,key=lambda item:len(item['pathPrefix']),reverse=True)
    if not isinstance(value,list) or not value:raise BrokerError('routes_required','routes deve ser uma lista não vazia.')
    result=[];prefixes=set()
    for index,item in enumerate(value):
        if not isinstance(item,dict):raise BrokerError('invalid_route','Cada rota deve ser um objeto.',detail={'index':index})
        prefix=str(item.get('pathPrefix') or '').strip();service=str(item.get('service') or '').strip();strip=bool(item.get('stripPrefix',False))
        if not prefix.startswith('/') or '..' in prefix or '//' in prefix or len(prefix)>128:raise BrokerError('invalid_route_prefix','pathPrefix é inválido.',detail={'index':index})
        if len(prefix)>1:prefix=prefix.rstrip('/')
        if prefix in prefixes:raise BrokerError('duplicate_route','Rotas duplicadas não são permitidas.',detail={'pathPrefix':prefix})
        prefixes.add(prefix)
        if service not in names:raise BrokerError('route_service_not_found','A rota aponta para serviço inexistente.',detail={'service':service})
        result.append({'pathPrefix':prefix,'service':service,'stripPrefix':strip})
    if '/' not in prefixes:raise BrokerError('root_route_required','Uma rota raiz / é obrigatória.')
    return sorted(result,key=lambda item:len(item['pathPrefix']),reverse=True)


def preview_plan(payload:Any)->dict:
    if not isinstance(payload,dict):raise BrokerError('invalid_request','A solicitação deve ser um objeto.',400)
    allowed={'build_job_id','routes','ttl_seconds','actor_user','actor_groups'}
    if 'build_job_id' not in payload or not set(payload).issubset(allowed):raise BrokerError('required_field_missing','build_job_id é obrigatório.',400)
    job_id=str(payload.get('build_job_id') or '');ttl=int(payload.get('ttl_seconds') or 1800)
    if not 300<=ttl<=7200:raise BrokerError('invalid_ttl','ttl_seconds deve estar entre 300 e 7200.',400)
    status=build_status(job_id);result=status['result'];applications=[]
    for raw in result.get('applications') or []:
        image=raw.get('image') or {};image_id=str(image.get('immutableReference') or image.get('imageId') or '')
        item={'service':str(raw.get('service') or ''),'image_id':image_id,'application_digest':str(raw.get('applicationDigest') or ''),'runtime':str(raw.get('runtime') or ''),'port':int(raw.get('containerPort') or 0),'healthcheck':str(raw.get('healthcheck') or '/')}
        if not item['service'] or not SHA_RE.fullmatch(item['application_digest']) or not re.fullmatch(r'sha256:[a-f0-9]{64}',item['image_id']) or not 1024<=item['port']<=65535:raise BrokerError('build_application_invalid','Uma aplicação do build não possui metadados de preview válidos.',409,{'service':item['service']})
        applications.append(item)
    routes=normalize_routes(payload.get('routes'),applications)
    material={'project_slug':result.get('projectSlug'),'build_job_id':job_id,'build_plan_digest':result.get('planDigest'),'config_revision':result.get('configRevision'),'config_digest':result.get('configDigest'),'archive_sha256':result.get('archiveSha256'),'applications':applications,'routes':routes,'ttl_seconds':ttl}
    digest=hashlib.sha256(canonical(material)).hexdigest()
    return {'ok':True,'side_effect_free':True,'approval_required':True,'preview_plan_digest':digest,'project_slug':material['project_slug'],'build_job_id':job_id,'build_plan_digest':material['build_plan_digest'],'config_revision':material['config_revision'],'config_digest':material['config_digest'],'archive_sha256':material['archive_sha256'],'applications':applications,'routes':routes,'ttl_seconds':ttl,'public_url_template':PUBLIC_ORIGIN+'/cloudiff/portal/preview/{preview_id}/','security':{'networkInternal':True,'portsLoopbackOnly':True,'readOnly':True,'capabilitiesDropped':True,'ttlCleanup':True,'secretsIncluded':False},'summary':{'serviceCount':len(applications),'services':[{'service':item['service'],'runtime':item['runtime'],'port':item['port'],'healthcheck':item['healthcheck']} for item in applications],'routes':routes,'ttlSeconds':ttl,'buildJobId':job_id,'configRevision':material['config_revision'],'archiveSha256':material['archive_sha256']}}


def create_preview(payload:Any)->dict:
    if not isinstance(payload,dict):raise BrokerError('invalid_request','A solicitação deve ser um objeto.',400)
    required={'build_job_id','preview_plan_digest','ttl_seconds','actor_user','actor_groups'}
    allowed=required|{'routes'}
    if not required.issubset(payload) or not set(payload).issubset(allowed):raise BrokerError('required_field_missing','build_job_id, preview_plan_digest, ttl_seconds, actor_user e actor_groups são obrigatórios.',400)
    actor=str(payload.get('actor_user') or '').strip();groups=payload.get('actor_groups') or []
    if not actor or not isinstance(groups,list):raise BrokerError('actor_identity_required','A identidade autenticada é obrigatória.',403)
    plan=preview_plan({'build_job_id':payload['build_job_id'],'routes':payload.get('routes'),'ttl_seconds':payload['ttl_seconds'],'actor_user':actor,'actor_groups':groups})
    digest=str(payload.get('preview_plan_digest') or '').lower()
    if not SHA_RE.fullmatch(digest) or not hmac.compare_digest(digest,plan['preview_plan_digest']):raise BrokerError('preview_plan_digest_mismatch','O plano do preview mudou. Gere uma nova aprovação.',409)
    preview_id='pv_'+secrets.token_hex(12)
    executor_payload={'preview_id':preview_id,'project_slug':plan['project_slug'],'build_job_id':plan['build_job_id'],'plan_digest':digest,'config_revision':plan['config_revision'],'archive_sha256':plan['archive_sha256'],'applications':[{key:item[key] for key in ('service','image_id','application_digest','port','healthcheck')} for item in plan['applications']],'routes':plan['routes'],'ttl_seconds':plan['ttl_seconds']}
    status,data=json_internal('POST',EXECUTOR_URL+'/v1/previews',EXECUTOR_TOKEN,executor_payload,timeout=180)
    if status not in {200,201} or not data.get('ok'):
        error=data.get('error') or {};raise BrokerError(str(error.get('code') or 'preview_executor_failed'),str(error.get('message') or 'O executor não criou o preview.'),status if status>=400 else 502,error.get('detail'))
    now=int(time.time());expires=int(data.get('expires_at') or now+plan['ttl_seconds']);result={**data,'public_url':PUBLIC_ORIGIN+'/cloudiff/portal/preview/'+preview_id+'/','created_by':actor,'preview_plan_digest':digest}
    conn=db();conn.execute('insert into previews(preview_id,project_slug,build_job_id,plan_digest,created_by,actor_groups_json,status,result_json,created_at,expires_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?)',(preview_id,plan['project_slug'],plan['build_job_id'],digest,actor,json.dumps(sorted(set(str(x) for x in groups)),separators=(',',':')),str(data.get('status') or 'running'),json.dumps(result,ensure_ascii=False,separators=(',',':')),now,expires,now));conn.commit();conn.close()
    return result


def preview_row(preview_id:str)->sqlite3.Row:
    if not PREVIEW_RE.fullmatch(preview_id):raise BrokerError('invalid_preview_id','preview_id é inválido.',400)
    conn=db();row=conn.execute('select * from previews where preview_id=?',(preview_id,)).fetchone();conn.close()
    if not row:raise BrokerError('preview_not_found','Preview não encontrado.',404)
    return row


def authorized(row:sqlite3.Row,user:str,groups:list[str])->bool:
    normalized={str(item).strip().casefold() for item in groups if str(item).strip()}
    admin=bool(normalized&{'cloudif-tenants-admin','cloudif-admin','domain admins'})
    return bool(user) and (user.strip().casefold()==str(row['created_by']).strip().casefold() or admin)


def status_preview(preview_id:str,user:str='',groups:list[str]|None=None,require_access:bool=False)->dict:
    row=preview_row(preview_id)
    if require_access and not authorized(row,user,groups or []):raise BrokerError('preview_access_denied','A sessão não possui acesso a este preview.',403)
    status,data=json_internal('GET',EXECUTOR_URL+'/v1/previews/'+preview_id,EXECUTOR_TOKEN,timeout=30)
    if status==404:
        conn=db();conn.execute("update previews set status='missing',updated_at=? where preview_id=?",(int(time.time()),preview_id));conn.commit();conn.close();raise BrokerError('preview_not_found','O executor não possui este preview.',404)
    if status!=200 or not data.get('ok'):raise BrokerError('preview_status_failed','O estado do preview não pôde ser consultado.',502)
    result={**data,'public_url':PUBLIC_ORIGIN+'/cloudiff/portal/preview/'+preview_id+'/','created_by':row['created_by'],'preview_plan_digest':row['plan_digest']}
    conn=db();conn.execute('update previews set status=?,result_json=?,expires_at=?,updated_at=? where preview_id=?',(str(data.get('status') or row['status']),json.dumps(result,ensure_ascii=False,separators=(',',':')),int(data.get('expires_at') or row['expires_at']),int(time.time()),preview_id));conn.commit();conn.close()
    return result


def delete_preview(preview_id:str,user:str,groups:list[str])->dict:
    row=preview_row(preview_id)
    if not authorized(row,user,groups):raise BrokerError('preview_access_denied','A sessão não possui acesso a este preview.',403)
    status,data=json_internal('DELETE',EXECUTOR_URL+'/v1/previews/'+preview_id,EXECUTOR_TOKEN,timeout=60)
    if status not in {200,404}:raise BrokerError('preview_delete_failed','O executor não removeu o preview.',502)
    now=int(time.time());conn=db();conn.execute("update previews set status='deleted',updated_at=? where preview_id=?",(now,preview_id));conn.commit();conn.close()
    return {'ok':True,'preview_id':preview_id,'status':'deleted','deleted_at':now}


def proxy(preview_id:str,path:str,method:str,headers:dict[str,str],body:bytes,user:str,groups:list[str])->tuple[int,dict[str,str],bytes]:
    row=preview_row(preview_id)
    if not authorized(row,user,groups):raise BrokerError('preview_access_denied','A sessão não possui acesso a este preview.',403)
    if int(row['expires_at'])<=int(time.time()):raise BrokerError('preview_expired','O preview expirou.',410)
    request_headers={key:value for key,value in headers.items() if key.lower() in SAFE_REQUEST and key.lower() not in HOP_HEADERS}
    status,response_headers,raw=internal(method,EXECUTOR_URL+'/v1/proxy/'+preview_id+path,EXECUTOR_TOKEN,None,request_headers,timeout=45) if method in {'GET','HEAD'} else internal_raw(method,EXECUTOR_URL+'/v1/proxy/'+preview_id+path,EXECUTOR_TOKEN,body,request_headers,45)
    safe={key:value for key,value in response_headers.items() if key.lower() in SAFE_RESPONSE and key.lower() not in HOP_HEADERS}
    return status,safe,raw


def internal_raw(method:str,url:str,token:str,body:bytes,headers:dict[str,str],timeout:int)->tuple[int,dict[str,str],bytes]:
    request_headers={'Authorization':'Bearer '+token,**headers};request=urllib.request.Request(url,data=body,method=method,headers=request_headers)
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,dict(response.headers),response.read(MAX_BODY+1)
    except urllib.error.HTTPError as error:return error.code,dict(error.headers),error.read(MAX_BODY+1)


class Handler(BaseHTTPRequestHandler):
    server_version='CloudIFFPreviewBroker/1'
    def log_message(self,*args):pass
    def auth(self):return bool(TOKEN) and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+TOKEN)
    def identity(self):
        user=str(self.headers.get('X-CloudIF-Actor-User') or '').strip();groups=[x.strip() for x in re.split(r'[|,;]',str(self.headers.get('X-CloudIF-Actor-Groups') or '')) if x.strip()];return user,groups
    def subpath_with_query(self,match):
        parts=urllib.parse.urlsplit(self.path);subpath=match.group(2) or '/'
        return subpath+('?' + parts.query if parts.query else '')
    def body(self)->bytes:
        size=int(self.headers.get('Content-Length','0') or '0')
        if size<0 or size>MAX_BODY:raise BrokerError('request_too_large','A solicitação excede 2 MiB.',413)
        return self.rfile.read(size) if size else b''
    def out(self,status:int,data:dict):
        raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def error(self,error:Exception):
        if isinstance(error,BrokerError):return self.out(error.status,{'ok':False,'error':error.as_dict()})
        return self.out(500,{'ok':False,'error':{'code':'preview_broker_failed','message':'O coordenador de preview falhou.'}})
    def do_GET(self):
        if self.path=='/health':
            conn=db();counts={row['status']:row['n'] for row in conn.execute('select status,count(*) n from previews group by status')};conn.close();return self.out(200,{'ok':True,'service':'cloudif-multiservice-preview-broker','previews':counts,'publicBase':PUBLIC_ORIGIN+'/cloudiff/portal/preview/'})
        if not self.auth():return self.out(401,{'ok':False,'error':{'code':'unauthorized','message':'Credencial interna inválida.'}})
        path=urllib.parse.urlsplit(self.path).path;match=re.fullmatch(r'/v1/previews/(pv_[a-f0-9]{24})',path)
        if match:
            try:user,groups=self.identity();return self.out(200,status_preview(match.group(1),user,groups,bool(user)))
            except Exception as error:return self.error(error)
        match=re.fullmatch(r'/v1/proxy/(pv_[a-f0-9]{24})(/.*)?',path)
        if match:return self.proxy_request(match.group(1),self.subpath_with_query(match),'GET')
        return self.out(404,{'ok':False,'error':{'code':'not_found','message':'Rota não encontrada.'}})
    def do_HEAD(self):
        if not self.auth():return self.out(401,{'ok':False,'error':{'code':'unauthorized','message':'Credencial interna inválida.'}})
        match=re.fullmatch(r'/v1/proxy/(pv_[a-f0-9]{24})(/.*)?',urllib.parse.urlsplit(self.path).path)
        if match:return self.proxy_request(match.group(1),self.subpath_with_query(match),'HEAD')
        return self.out(404,{'ok':False,'error':{'code':'not_found','message':'Rota não encontrada.'}})
    def do_POST(self):
        if not self.auth():return self.out(401,{'ok':False,'error':{'code':'unauthorized','message':'Credencial interna inválida.'}})
        path=urllib.parse.urlsplit(self.path).path
        try:
            if path=='/v1/plan':return self.out(200,preview_plan(json.loads(self.body() or b'{}')))
            if path=='/v1/previews':return self.out(201,create_preview(json.loads(self.body() or b'{}')))
            match=re.fullmatch(r'/v1/proxy/(pv_[a-f0-9]{24})(/.*)?',path)
            if match:return self.proxy_request(match.group(1),self.subpath_with_query(match),'POST')
            return self.out(404,{'ok':False,'error':{'code':'not_found','message':'Rota não encontrada.'}})
        except Exception as error:return self.error(error)
    def do_PUT(self):return self.proxy_method('PUT')
    def do_PATCH(self):return self.proxy_method('PATCH')
    def do_DELETE(self):
        if not self.auth():return self.out(401,{'ok':False,'error':{'code':'unauthorized','message':'Credencial interna inválida.'}})
        path=urllib.parse.urlsplit(self.path).path;match=re.fullmatch(r'/v1/previews/(pv_[a-f0-9]{24})',path)
        if match:
            try:user,groups=self.identity();return self.out(200,delete_preview(match.group(1),user,groups))
            except Exception as error:return self.error(error)
        match=re.fullmatch(r'/v1/proxy/(pv_[a-f0-9]{24})(/.*)?',path)
        if match:return self.proxy_request(match.group(1),self.subpath_with_query(match),'DELETE')
        return self.out(404,{'ok':False,'error':{'code':'not_found','message':'Rota não encontrada.'}})
    def proxy_method(self,method):
        if not self.auth():return self.out(401,{'ok':False,'error':{'code':'unauthorized','message':'Credencial interna inválida.'}})
        match=re.fullmatch(r'/v1/proxy/(pv_[a-f0-9]{24})(/.*)?',urllib.parse.urlsplit(self.path).path)
        if match:return self.proxy_request(match.group(1),self.subpath_with_query(match),method)
        return self.out(404,{'ok':False,'error':{'code':'not_found','message':'Rota não encontrada.'}})
    def proxy_request(self,preview_id,path,method):
        try:
            user,groups=self.identity();body=self.body() if method not in {'GET','HEAD'} else b''
            status,headers,raw=proxy(preview_id,path,method,{key:value for key,value in self.headers.items()},body,user,groups)
            self.send_response(status);self.send_header('X-Content-Type-Options','nosniff')
            for key,value in headers.items():
                if key.lower() not in HOP_HEADERS:self.send_header(key,value)
            self.send_header('Content-Length',str(0 if method=='HEAD' else len(raw)));self.end_headers()
            if method!='HEAD':self.wfile.write(raw)
        except Exception as error:return self.error(error)


if __name__=='__main__':init_db();ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
