#!/usr/bin/env python3
import json, os, re, secrets, sys, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, '/srv/cloudif/lib')
import cloudif_release_manager as rm

HOST=os.environ.get('CLOUDIF_SUPABASE_AGENT_HOST','127.0.0.1')
PORT=int(os.environ.get('CLOUDIF_SUPABASE_AGENT_PORT','18100'))
TOKEN=os.environ.get('CLOUDIF_SUPABASE_AGENT_TOKEN','')
MAX_BODY=6*1024*1024
SLUG_RE=re.compile(r'^[a-z0-9][a-z0-9._-]{0,62}$')
VERSION_RE=rm.VERSION_RE


def authorized(headers):
    supplied=(headers.get('Authorization') or '').removeprefix('Bearer ').strip()
    supplied=supplied or (headers.get('X-CloudIF-Token') or '').strip()
    return bool(TOKEN) and secrets.compare_digest(supplied,TOKEN)


def safe_payload(handler):
    try: length=int(handler.headers.get('Content-Length','0') or 0)
    except Exception: raise ValueError('invalid_content_length')
    if length < 0 or length > MAX_BODY: raise ValueError('request_too_large')
    raw=handler.rfile.read(length)
    data=json.loads(raw.decode('utf-8') or '{}')
    if not isinstance(data,dict): raise ValueError('invalid_json_object')
    return data


def validate_identity(data):
    project=str(data.get('project') or '').strip().lower()
    tenant=str(data.get('tenant') or '').strip().lower()
    version=str(data.get('version') or '').strip()
    if not SLUG_RE.fullmatch(project): raise ValueError('invalid_project')
    if tenant and not SLUG_RE.fullmatch(tenant): raise ValueError('invalid_tenant')
    if version and not VERSION_RE.fullmatch(version): raise ValueError('invalid_version')
    return project,tenant,version


def inspect_tenant(data):
    project,tenant,version=validate_identity(data)
    if not tenant:
        return {'ok':True,'project':project,'tenant':'','container':'','available':False,'migration_count':len(data.get('migrations') or [])}
    container=rm.tenant_container(tenant)
    return {'ok':True,'project':project,'tenant':tenant,'container':container,'available':bool(container),'migration_count':len(data.get('migrations') or [])}


def backup(data):
    project,tenant,version=validate_identity(data)
    if not tenant or not version: raise ValueError('tenant_and_version_required')
    container=rm.tenant_container(tenant)
    if not container: raise RuntimeError('tenant_container_not_found')
    path=rm.backup_tenant(project,version,tenant,container)
    return {'ok':True,'project':project,'tenant':tenant,'version':version,'container':container,'backup_path':path}


def migrate(data):
    project,tenant,version=validate_identity(data)
    items=data.get('migrations') or []
    if not isinstance(items,list): raise ValueError('invalid_migrations')
    if items and (not tenant or not version): raise ValueError('tenant_and_version_required')
    if not items: return {'ok':True,'project':project,'tenant':tenant,'version':version,'total':0,'applied':0}
    container=rm.tenant_container(tenant)
    if not container: raise RuntimeError('tenant_container_not_found')
    applied=rm.apply_migrations(project,version,container,items)
    return {'ok':True,'project':project,'tenant':tenant,'version':version,'container':container,'total':len(items),'applied':applied}

class Handler(BaseHTTPRequestHandler):
    server_version='CloudIF-Supabase-Agent'
    sys_version=''
    def log_message(self,fmt,*args):
        print('%s %s' % (self.address_string(),fmt%args),flush=True)
    def send_json(self,obj,status=200):
        raw=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        if self.path=='/health': return self.send_json({'ok':True,'agent':'supabase-release','version':1})
        if not authorized(self.headers): return self.send_json({'ok':False,'error':'forbidden'},403)
        return self.send_json({'ok':False,'error':'not_found'},404)
    def do_POST(self):
        if not authorized(self.headers): return self.send_json({'ok':False,'error':'forbidden'},403)
        try:
            data=safe_payload(self)
            if self.path=='/supabase/release/inspect': result=inspect_tenant(data)
            elif self.path=='/supabase/release/backup': result=backup(data)
            elif self.path=='/supabase/release/migrate': result=migrate(data)
            else: return self.send_json({'ok':False,'error':'not_found'},404)
            return self.send_json(result,200)
        except ValueError as exc:
            return self.send_json({'ok':False,'error':str(exc)},400)
        except Exception as exc:
            print('agent_error='+type(exc).__name__,flush=True)
            return self.send_json({'ok':False,'error':type(exc).__name__,'message':str(exc)[:500]},500)

if __name__=='__main__':
    if not TOKEN: raise SystemExit('missing token')
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
