#!/usr/bin/env python3
from __future__ import annotations

import hmac
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

BROKER_URL=os.environ.get('CLOUDIF_MULTISERVICE_PREVIEW_URL','http://127.0.0.1:18228').rstrip('/')
TOKEN=(os.environ.get('CLOUDIF_MULTISERVICE_PREVIEW_TOKEN') or '').strip()
MAX_BODY=2*1024*1024
ROUTE_RE=re.compile(r'^/cloudiff/portal/preview/(pv_[a-f0-9]{24})(/.*)?$')
REQUEST_HEADERS={'accept','accept-encoding','accept-language','content-type','if-match','if-none-match','if-modified-since','if-unmodified-since','range','user-agent'}
RESPONSE_HEADERS={'content-type','content-encoding','cache-control','etag','last-modified','accept-ranges','content-range','location','vary'}
HOP={'connection','keep-alive','proxy-authenticate','proxy-authorization','te','trailers','transfer-encoding','upgrade','set-cookie'}


def _send(handler,status:int,headers:dict[str,str],raw:bytes,head:bool=False):
    handler.send_response(status)
    handler.send_header('X-Content-Type-Options','nosniff')
    handler.send_header('Referrer-Policy','same-origin')
    for key,value in headers.items():
        if key.lower() in RESPONSE_HEADERS and key.lower() not in HOP:
            handler.send_header(key,value)
    handler.send_header('Content-Length',str(0 if head else len(raw)))
    handler.end_headers()
    if not head:handler.wfile.write(raw)


def _json(handler,status:int,code:str,message:str):
    raw=json.dumps({'ok':False,'error':{'code':code,'message':message}},ensure_ascii=False,separators=(',',':')).encode()
    _send(handler,status,{'Content-Type':'application/json','Cache-Control':'no-store'},raw,handler.command=='HEAD')


def handle_preview_request(handler)->bool:
    parts=urllib.parse.urlsplit(handler.path)
    match=ROUTE_RE.fullmatch(parts.path)
    if not match:return False
    if not TOKEN:
        _json(handler,503,'preview_proxy_unavailable','O proxy de preview não está configurado.');return True
    user=str(handler.headers.get('X-authentik-username') or handler.headers.get('X-Authentik-Username') or '').strip()
    groups=str(handler.headers.get('X-authentik-groups') or handler.headers.get('X-Authentik-Groups') or '').strip()
    if not user:
        _json(handler,401,'authentication_required','A sessão CloudIFF é obrigatória para abrir o preview.');return True
    subpath=match.group(2) or '/'
    if parts.query:subpath+='?'+parts.query
    method=str(handler.command or 'GET').upper()
    body=None
    if method not in {'GET','HEAD'}:
        try:size=int(handler.headers.get('Content-Length','0') or '0')
        except ValueError:size=-1
        if size<0 or size>MAX_BODY:
            _json(handler,413,'request_too_large','A solicitação excede 2 MiB.');return True
        body=handler.rfile.read(size) if size else b''
    request_headers={'Authorization':'Bearer '+TOKEN,'X-CloudIF-Actor-User':user,'X-CloudIF-Actor-Groups':groups}
    for key,value in handler.headers.items():
        if key.lower() in REQUEST_HEADERS and key.lower() not in HOP:request_headers[key]=value
    request=urllib.request.Request(BROKER_URL+'/v1/proxy/'+match.group(1)+subpath,data=body,method=method,headers=request_headers)
    try:
        with urllib.request.urlopen(request,timeout=45) as response:
            raw=response.read(MAX_BODY+1);status=response.status;headers=dict(response.headers)
    except urllib.error.HTTPError as error:
        raw=error.read(MAX_BODY+1);status=error.code;headers=dict(error.headers)
    except Exception:
        _json(handler,502,'preview_proxy_failed','O Portal não conseguiu acessar o preview.');return True
    if len(raw)>MAX_BODY:
        _json(handler,502,'preview_response_too_large','A resposta do preview excede 2 MiB.');return True
    _send(handler,status,headers,raw,method=='HEAD')
    return True
