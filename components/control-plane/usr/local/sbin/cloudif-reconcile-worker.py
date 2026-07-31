#!/usr/bin/env python3
import argparse
import fcntl
import json
import os
import sqlite3
import subprocess
import sys
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
    con.execute("UPDATE reconcile_requests SET status=?,message=?,result_json=?,finished_at=? WHERE request_id=?",
                (status,message[:4000],json.dumps(result,ensure_ascii=False,default=str)[:100000],client.now_utc(),request_id))
    con.commit(); con.close()


def process(row):
    rid=row["request_id"]
    con=client.connect()
    con.execute("UPDATE reconcile_requests SET status='running',started_at=?,message='Reconciliação em execução.' WHERE request_id=?",(client.now_utc(),rid))
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


def drain():
    client.ensure_schema(); QUEUE.mkdir(parents=True,exist_ok=True); LOCK.parent.mkdir(parents=True,exist_ok=True)
    with LOCK.open("w") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        markers=sorted(QUEUE.glob("*.json"))
        for marker in markers:
            try:
                data=json.loads(marker.read_text(errors="ignore")); rid=str(data.get("request_id") or "")
                con=client.connect(); row=con.execute("SELECT * FROM reconcile_requests WHERE request_id=?",(rid,)).fetchone(); con.close()
                if row and row["status"] in {"queued","waiting"}:
                    try:
                        process(row)
                    except Exception as exc:
                        update_request(rid,"failed",f"Falha na reconciliação: {type(exc).__name__}",{"error_type":type(exc).__name__})
                marker.unlink(missing_ok=True)
            except Exception:
                marker.unlink(missing_ok=True)
    return 0


def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="cmd",required=True)
    sub.add_parser("init")
    sub.add_parser("drain")
    e=sub.add_parser("enqueue"); e.add_argument("--event",required=True); e.add_argument("--actor",default="portal"); e.add_argument("--username",default=""); e.add_argument("--project",default=""); e.add_argument("--tenant",default=""); e.add_argument("--payload",default="{}")
    s=sub.add_parser("status"); s.add_argument("request_id")
    r=sub.add_parser("recent"); r.add_argument("--project",default=""); r.add_argument("--limit",type=int,default=20)
    args=ap.parse_args()
    if args.cmd=="init": client.ensure_schema(); print(json.dumps({"ok":True})); return
    if args.cmd=="drain": raise SystemExit(drain())
    if args.cmd=="enqueue": print(json.dumps(client.enqueue(args.event,args.actor,args.username,args.project,args.tenant,json.loads(args.payload)),ensure_ascii=False)); return
    if args.cmd=="status": print(json.dumps(client.status(args.request_id) or {"ok":False,"error":"not_found"},ensure_ascii=False)); return
    if args.cmd=="recent": print(json.dumps(client.recent(args.project,args.limit),ensure_ascii=False)); return

if __name__=="__main__": main()
