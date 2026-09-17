#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

LOG=Path(os.environ.get('CLOUDIF_PROJECT_ACCESS_LOG','/srv/cloudif/router/logs/cloudif_project_access.log'))
STATE=Path(os.environ.get('CLOUDIF_PROJECT_ACCESS_STATE','/var/lib/cloudif-project-access-collector/state.json'))
DB=Path(os.environ.get('CLOUDIF_PROJECT_ACCESS_DB','/var/lib/cloudif/portal/cloudif-portal.db'))
AUDIT_URL=os.environ.get('CLOUDIF_AUDIT_URL','http://127.0.0.1:18201').rstrip('/')
AUDIT_TOKEN=os.environ.get('CLOUDIF_AUDIT_TOKEN','').strip()
HOST=os.environ.get('CLOUDIF_PROJECT_ACCESS_HOST','127.0.0.1')
PORT=int(os.environ.get('CLOUDIF_PROJECT_ACCESS_PORT','18207'))
POLL=max(.1,float(os.environ.get('CLOUDIF_PROJECT_ACCESS_POLL','0.5')))
WRITE_METHODS={'POST','PUT','PATCH','DELETE'}

class Runtime:
    def __init__(self):
        self.lock=threading.Lock();self.processed=0;self.emitted=0;self.skipped=0;self.errors=0;self.last_event='';self.last_error='';self.started=time.time()
    def snapshot(self):
        with self.lock:
            return {'ok':True,'service':'cloudif-project-access-collector','processed':self.processed,'emitted':self.emitted,'skipped':self.skipped,'errors':self.errors,'last_event':self.last_event,'last_error':self.last_error,'uptime_s':int(time.time()-self.started),'log':str(LOG)}
RUNTIME=Runtime()

def _state_load()->dict[str,Any]:
    try:return json.loads(STATE.read_text())
    except Exception:return {}

def _state_save(inode:int,offset:int)->None:
    STATE.parent.mkdir(parents=True,exist_ok=True)
    tmp=STATE.with_suffix('.tmp');tmp.write_text(json.dumps({'inode':inode,'offset':offset},separators=(',',':'))+'\n');tmp.replace(STATE)

def _project_for_tenant(tenant:str)->tuple[str,str] | None:
    if not tenant or not DB.exists():return None
    try:
        c=sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True,timeout=5)
        rows=c.execute('select slug,name from projects where tenant=? and lower(coalesce(status,\'\')) not in (\'deleted\',\'disabled\') order by slug',(tenant,)).fetchall();c.close()
    except Exception:return None
    if len(rows)!=1:return None
    return str(rows[0][0] or ''),str(rows[0][1] or rows[0][0] or '')

def _event_id(rec:dict[str,Any],slug:str,action:str)->str:
    user=str(rec.get('user') or '').strip().lower();tenant=str(rec.get('tenant') or '');uri=str(rec.get('uri') or '');method=str(rec.get('method') or '')
    if action=='environment.view':
        try:bucket=int(float(rec.get('msec') or 0)//300)
        except Exception:bucket=int(time.time()//300)
        raw=f'project-access|{slug}|{user}|{action}|{bucket}'
    else:
        raw=f"project-access|{slug}|{user}|{action}|{rec.get('msec')}|{method}|{tenant}|{uri}|{rec.get('status')}"
    return 'project-access-'+hashlib.sha256(raw.encode()).hexdigest()[:40]

def _event_from_record(rec:dict[str,Any])->dict[str,Any] | None:
    user=str(rec.get('user') or '').strip().lower();tenant=str(rec.get('tenant') or '').strip().lower();method=str(rec.get('method') or '').strip().upper();uri=str(rec.get('uri') or '').strip()
    if not user or user in {'-','unknown'} or not tenant or not uri.startswith('/'):return None
    project=_project_for_tenant(tenant)
    if not project:return None
    slug,name=project
    if uri.startswith('/project/'):
        action='environment.write' if method in WRITE_METHODS else 'environment.view'
        resource='project-ui'
    elif uri.startswith('/api/') and method in WRITE_METHODS:
        action='environment.write';resource='project-api'
    else:return None
    try:status=int(rec.get('status') or 0)
    except Exception:status=0
    result='success' if 200<=status<400 else 'error'
    event={
        'event_id':_event_id(rec,slug,action),
        'ts':str(rec.get('ts') or ''),
        'project_slug':slug,
        'actor_type':'user',
        'actor_id':user,
        'delegated_user_id':user,
        'source':'project-access',
        'action':action,
        'result':result,
        'duration_ms':0,
        'client_id':'cloudif-project-access-collector',
        'attrs':{'tenant':tenant,'project_name':name[:200],'resource':resource,'method':method,'path':uri[:512],'status':status},
    }
    return event

def _post_event(event:dict[str,Any])->bool:
    if not AUDIT_TOKEN:return False
    raw=json.dumps(event,ensure_ascii=False,separators=(',',':')).encode()
    req=urllib.request.Request(AUDIT_URL+'/v1/events',data=raw,method='POST',headers={'Authorization':'Bearer '+AUDIT_TOKEN,'Content-Type':'application/json','Accept':'application/json','User-Agent':'CloudIFF-Project-Access-Collector/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=5) as r:return 200<=int(r.status)<300
    except Exception:return False

def _process_line(line:str)->None:
    with RUNTIME.lock:RUNTIME.processed+=1
    try:rec=json.loads(line)
    except Exception:
        with RUNTIME.lock:RUNTIME.skipped+=1
        return
    event=_event_from_record(rec)
    if not event:
        with RUNTIME.lock:RUNTIME.skipped+=1
        return
    if _post_event(event):
        with RUNTIME.lock:RUNTIME.emitted+=1;RUNTIME.last_event=str(event.get('ts') or '')
    else:
        with RUNTIME.lock:RUNTIME.errors+=1;RUNTIME.last_error='audit_post_failed'

def _tail_loop()->None:
    state=_state_load();handle=None;inode=0;offset=0
    while True:
        try:
            if not LOG.exists():time.sleep(POLL);continue
            stat=LOG.stat();current_inode=int(stat.st_ino)
            if handle is None or current_inode!=inode or stat.st_size<offset:
                if handle:
                    try:handle.close()
                    except Exception:pass
                handle=LOG.open('r',encoding='utf-8',errors='ignore');inode=current_inode
                if int(state.get('inode') or 0)==inode:
                    offset=min(int(state.get('offset') or 0),int(stat.st_size))
                else:
                    # First install or rotation: don't backfill old router history.
                    offset=int(stat.st_size)
                handle.seek(offset);_state_save(inode,offset);state={'inode':inode,'offset':offset}
            line=handle.readline()
            if not line:
                time.sleep(POLL);continue
            offset=handle.tell();_process_line(line);_state_save(inode,offset);state={'inode':inode,'offset':offset}
        except Exception as exc:
            with RUNTIME.lock:RUNTIME.errors+=1;RUNTIME.last_error=type(exc).__name__
            time.sleep(1)

class Health(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path!='/health':self.send_response(404);self.end_headers();return
        body=json.dumps(RUNTIME.snapshot(),separators=(',',':')).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

if __name__=='__main__':
    threading.Thread(target=_tail_loop,name='project-access-tail',daemon=True).start()
    ThreadingHTTPServer((HOST,PORT),Health).serve_forever()
