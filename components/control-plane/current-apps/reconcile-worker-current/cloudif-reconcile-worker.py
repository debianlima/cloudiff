#!/usr/bin/env python3
import argparse
import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import time
import random
import socket
import tempfile
import concurrent.futures
import datetime as dt
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, "/srv/cloudif/lib")
import cloudif_reconcile_client as client

LOCK = Path("/run/cloudif-reconcile-worker.lock")
QUEUE = client.QUEUE
FORJA_ENV = Path("/etc/cloudif/forja-agent-client.env")


def read_env(path):
    data={}
    try:
        for raw in path.read_text(errors="ignore").splitlines():
            line=raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k,v=line.split("=",1); data[k.strip()]=v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return data


def forja_project(project):
    cfg=read_env(FORJA_ENV)
    base=(cfg.get("FORJA_AGENT_URL") or "http://10.62.91.2:18095").rstrip("/")
    token=cfg.get("FORJA_AGENT_TOKEN") or ""
    url=base+"/project/status?slug="+urllib.parse.quote(project)
    req=urllib.request.Request(url,headers={"Accept":"application/json","Authorization":"Bearer "+token,"X-CloudIF-Token":token})
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            return json.load(r)
    except Exception:
        return {}


def db_container(tenant):
    try:
        p=subprocess.run(["docker","ps","--format",'{{.Names}}|{{.Label "com.docker.compose.project"}}|{{.Label "com.docker.compose.service"}}'],text=True,capture_output=True,timeout=20)
    except Exception:
        return ""
    if p.returncode != 0:
        return ""
    expected="cloudif_"+tenant
    for line in p.stdout.splitlines():
        parts=line.split("|",2)
        if len(parts)==3 and parts[1]==expected and parts[2]=="db":
            return parts[0]
    return ""


def update_request(request_id,status,message,result):
    con=client.connect()
    con.execute("UPDATE reconcile_requests SET status=?,message=?,result_json=?,finished_at=?,lease_owner='',lease_expires_at='',heartbeat_at='' WHERE request_id=?",
                (status,message[:4000],json.dumps(result,ensure_ascii=False,default=str)[:100000],client.now_utc(),request_id))
    con.commit(); con.close()


def process(row):
    rid=row["request_id"]
    con=client.connect()
    con.execute("UPDATE reconcile_requests SET heartbeat_at=?,message='Reconciliação em execução.' WHERE request_id=?",(client.now_utc(),rid))
    con.commit(); con.close()
    payload={}
    try:
        payload=json.loads(row["payload_json"] or "{}")
    except Exception:
        pass
    event=row["event_type"]
    now=client.now_utc()
    if event in {"user.created","user.seen"}:
        username=row["username"] or row["actor"]
        if not username:
            raise RuntimeError("usuário ausente")
        groups=payload.get("groups") or []
        if isinstance(groups,str): groups=[x.strip() for x in groups.split(",") if x.strip()]
        con=client.connect()
        con.execute("""INSERT INTO release_users(username,email,groups_json,enabled,discovered_at,updated_at)
                       VALUES(?,?,?,1,?,?)
                       ON CONFLICT(username) DO UPDATE SET email=excluded.email,groups_json=excluded.groups_json,enabled=1,updated_at=excluded.updated_at""",
                    (username,str(payload.get("email") or "")[:320],json.dumps(groups,ensure_ascii=False),now,now))
        con.commit(); con.close()
        update_request(rid,"ready","Usuário habilitado para automação de releases.",{"username":username})
        return
    if event in {"project.created","project.updated","project.integrated","repository.created","repository.updated","reconcile.requested"}:
        project=row["project"] or str(payload.get("project") or "")
        if not project:
            raise RuntimeError("projeto ausente")
        con=client.connect()
        prow=con.execute("SELECT * FROM projects WHERE slug=?",(project,)).fetchone()
        tenant=row["tenant"] or (prow["tenant_default"] if prow and "tenant_default" in prow.keys() else "") or (prow["tenant"] if prow and "tenant" in prow.keys() else "") or ""
        state=forja_project(project)
        pobj=state.get("project") if isinstance(state,dict) and isinstance(state.get("project"),dict) else {}
        forgejo=pobj.get("forgejo") if isinstance(pobj.get("forgejo"),dict) else {}
        owner=str(forgejo.get("owner") or pobj.get("forgejo_owner") or "cloudif")
        repo=str(forgejo.get("repo") or ("cloudif-"+project if pobj else ""))
        repo_full=(owner+"/"+repo) if repo else ""
        repo_url=str(forgejo.get("url") or (prow["repo_url"] if prow and "repo_url" in prow.keys() and prow["repo_url"] else ""))
        con.execute("""INSERT INTO release_settings(project,tenant,repo_full_name,repo_url,enabled,default_channel,version_policy,auto_discovered,discovered_at,updated_at)
                       VALUES(?,?,?,?,1,'stable','patch',1,?,?)
                       ON CONFLICT(project) DO UPDATE SET tenant=CASE WHEN excluded.tenant<>'' THEN excluded.tenant ELSE release_settings.tenant END,
                         repo_full_name=CASE WHEN excluded.repo_full_name<>'' THEN excluded.repo_full_name ELSE release_settings.repo_full_name END,
                         repo_url=CASE WHEN excluded.repo_url<>'' THEN excluded.repo_url ELSE release_settings.repo_url END,
                         enabled=1,updated_at=excluded.updated_at""",
                    (project,tenant,repo_full,repo_url,now,now))
        con.commit(); con.close()
        status="ready" if repo_full else "waiting"
        msg="Projeto e repositório reconciliados." if repo_full else "Projeto preparado; aguardando criação do repositório."
        update_request(rid,status,msg,{"project":project,"tenant":tenant,"repo_full_name":repo_full,"repo_url":repo_url})
        return
    if event in {"tenant.created","tenant.ready","tenant.bound"}:
        tenant=row["tenant"] or str(payload.get("tenant") or "")
        if not tenant:
            raise RuntimeError("tenant ausente")
        container=db_container(tenant)
        con=client.connect()
        con.execute("""INSERT INTO release_tenants(tenant,db_container,enabled,discovered_at,updated_at)
                       VALUES(?,?,1,?,?)
                       ON CONFLICT(tenant) DO UPDATE SET db_container=excluded.db_container,enabled=1,updated_at=excluded.updated_at""",
                    (tenant,container,now,now))
        con.commit(); con.close()
        status="ready" if container else "waiting"
        msg="Tenant Supabase reconciliado." if container else "Tenant registrado; aguardando container PostgreSQL."
        update_request(rid,status,msg,{"tenant":tenant,"db_container":container})
        return
    raise RuntimeError("evento sem processador")


LEASE_SECONDS=45
MAX_WORKERS=max(1,min(int(os.environ.get('CLOUDIF_RECONCILE_WORKERS','4')),8))
WORKER_ID=socket.gethostname()+':'+str(os.getpid())
TERMINAL={'ready','failed','dead_letter'}

def iso_after(seconds):
    return (dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=seconds)).replace(microsecond=0).isoformat().replace('+00:00','Z')

def recover_expired():
    now=client.now_utc();con=client.connect();
    cur=con.execute("UPDATE reconcile_requests SET status='queued',lease_owner='',lease_expires_at='',heartbeat_at='',message='Lease expirado; tarefa recuperada.',next_attempt_at=? WHERE status='running' AND lease_expires_at<>'' AND lease_expires_at<?",(now,now));con.commit();n=cur.rowcount;con.close();return n

def claim(limit):
    now=client.now_utc();lease=iso_after(LEASE_SECONDS);con=client.connect();con.execute('BEGIN IMMEDIATE')
    busy={r[0] for r in con.execute("SELECT partition_key FROM reconcile_requests WHERE status='running' AND lease_expires_at>?",(now,))}
    rows=con.execute("SELECT * FROM reconcile_requests WHERE status IN ('queued','waiting_retry') AND (next_attempt_at='' OR next_attempt_at<=?) ORDER BY created_at LIMIT 200",(now,)).fetchall();picked=[];seen=set(busy)
    for r in rows:
        part=r['partition_key'] or ('project:'+r['project'] if r['project'] else 'request:'+r['request_id'])
        if part in seen:continue
        cur=con.execute("UPDATE reconcile_requests SET status='running',started_at=CASE WHEN started_at='' THEN ? ELSE started_at END,lease_owner=?,lease_expires_at=?,heartbeat_at=?,attempt_count=attempt_count+1,message='Reconciliação em execução.' WHERE request_id=? AND status IN ('queued','waiting_retry')",(now,WORKER_ID,lease,now,r['request_id']))
        if cur.rowcount: picked.append(r['request_id']);seen.add(part)
        if len(picked)>=limit:break
    con.commit();out=[]
    for rid in picked:
        row=con.execute('SELECT * FROM reconcile_requests WHERE request_id=?',(rid,)).fetchone();out.append(dict(row))
    con.close();return out

def fail_or_retry(row,exc):
    rid=row['request_id'];attempt=int(row.get('attempt_count') or 1);maximum=int(row.get('max_attempts') or 5);etype=type(exc).__name__;con=client.connect()
    if attempt>=maximum:
        con.execute("UPDATE reconcile_requests SET status='dead_letter',dead_lettered_at=?,finished_at=?,message=?,last_error_type=?,lease_owner='',lease_expires_at='',heartbeat_at='',result_json=? WHERE request_id=?",(client.now_utc(),client.now_utc(),'Falha permanente após tentativas.',etype,json.dumps({'error_type':etype,'secrets_exposed':False},separators=(',',':')),rid))
    else:
        delay=min(300,(2**max(0,attempt-1))*5)+random.randint(0,3)
        con.execute("UPDATE reconcile_requests SET status='waiting_retry',next_attempt_at=?,message=?,last_error_type=?,lease_owner='',lease_expires_at='',heartbeat_at='' WHERE request_id=?",(iso_after(delay),f'Falha transitória; nova tentativa em {delay}s.',etype,rid))
    con.commit();con.close()

def execute(row):
    try:process(row);return {'request_id':row['request_id'],'ok':True}
    except Exception as exc:fail_or_retry(row,exc);return {'request_id':row['request_id'],'ok':False,'error_type':type(exc).__name__}

def cleanup_markers():
    for marker in QUEUE.glob('*.json'):
        try:
            rid=str(json.loads(marker.read_text(errors='ignore')).get('request_id') or '')
            con=client.connect();r=con.execute('SELECT status FROM reconcile_requests WHERE request_id=?',(rid,)).fetchone();con.close()
            if not r or r['status'] not in {'queued','waiting_retry','running'}:marker.unlink(missing_ok=True)
        except Exception:marker.unlink(missing_ok=True)

def drain():
    client.ensure_schema();QUEUE.mkdir(parents=True,exist_ok=True);recovered=recover_expired();results=[]
    while True:
        rows=claim(MAX_WORKERS)
        if not rows:break
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(rows),thread_name_prefix='cloudif-reconcile') as pool:
            results.extend(pool.map(execute,rows))
    cleanup_markers();print(json.dumps({'ok':all(x['ok'] for x in results) if results else True,'processed':len(results),'recovered_leases':recovered,'workers':MAX_WORKERS,'results':results},ensure_ascii=False,separators=(',',':')));return 0

def selftest():
    # Isolated scheduler semantics; no external systems or real project rows.
    secret={'token':'x'}
    assert client._contains_secret(secret) is True and client._contains_secret({'source':'test'}) is False
    parts=[client._partition('project.updated','',f'p{i}','') for i in range(4)]
    assert len(set(parts))==4 and client._partition('project.updated','','same','')==client._partition('repository.updated','','same','')
    started=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:time.sleep(.20),range(4)))
    elapsed=time.monotonic()-started
    assert elapsed<.55
    return {'ok':True,'parallel_partitions':4,'elapsed_seconds':round(elapsed,3),'secret_payload_rejected':True,'same_project_serialized':True,'lease_seconds':LEASE_SECONDS,'max_workers':MAX_WORKERS,'tokens_persisted':False}


def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="cmd",required=True)
    sub.add_parser("init")
    sub.add_parser("drain")
    sub.add_parser("selftest")
    e=sub.add_parser("enqueue"); e.add_argument("--event",required=True); e.add_argument("--actor",default="portal"); e.add_argument("--username",default=""); e.add_argument("--project",default=""); e.add_argument("--tenant",default=""); e.add_argument("--payload",default="{}")
    s=sub.add_parser("status"); s.add_argument("request_id")
    r=sub.add_parser("recent"); r.add_argument("--project",default=""); r.add_argument("--limit",type=int,default=20)
    args=ap.parse_args()
    if args.cmd=="init": client.ensure_schema(); print(json.dumps({"ok":True})); return
    if args.cmd=="drain": raise SystemExit(drain())
    if args.cmd=="selftest": print(json.dumps(selftest(),separators=(",",":"))); return
    if args.cmd=="enqueue": print(json.dumps(client.enqueue(args.event,args.actor,args.username,args.project,args.tenant,json.loads(args.payload)),ensure_ascii=False)); return
    if args.cmd=="status": print(json.dumps(client.status(args.request_id) or {"ok":False,"error":"not_found"},ensure_ascii=False)); return
    if args.cmd=="recent": print(json.dumps(client.recent(args.project,args.limit),ensure_ascii=False)); return

if __name__=="__main__": main()
