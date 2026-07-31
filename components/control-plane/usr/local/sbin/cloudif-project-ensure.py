#!/usr/bin/env python3
import argparse
import json
import sqlite3
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path

DB = "/var/lib/cloudif/portal/cloudif-portal.db"
FORJA_AGENT = "http://10.62.91.2:18095"
KOMODO_AGENT = "http://10.62.91.2:18098"


def load_env_file(path):
    data = {}
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return data

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def http_json(method, url, payload=None, timeout=90, extra_headers=None):
    data = None
    headers = {"Accept": "application/json", "User-Agent": "CloudIF-ProjectEnsure-v47b"}
    if extra_headers:
        headers.update(extra_headers)

    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            return {"ok": True, "status": r.status, "data": json.loads(raw) if raw else {}}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"raw": raw}
        return {"ok": False, "status": e.code, "data": parsed}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}

def audit(actor, project, action, status, message, request, response):
    con = db()
    con.execute("""
      insert into project_audit(actor, project, action, status, message, request_json, response_json)
      values (?, ?, ?, ?, ?, ?, ?)
    """, (
      actor, project, action, status, message,
      json.dumps(request, ensure_ascii=False),
      json.dumps(response, ensure_ascii=False)
    ))
    con.commit()
    con.close()

def save_project(args):
    con = db()
    con.execute("""
      insert into projects(slug, name, tenant_default, repo_url, status, created_by, updated_at)
      values (?, ?, ?, ?, 'active', ?, CURRENT_TIMESTAMP)
      on conflict(slug) do update set
        name=excluded.name,
        tenant_default=excluded.tenant_default,
        repo_url=excluded.repo_url,
        status='active',
        updated_at=CURRENT_TIMESTAMP
    """, (args.project, args.name or args.project, args.tenant, args.repo_url, args.actor))

    con.execute("""
      insert into project_tenants(project, tenant, role, is_primary, created_by)
      values (?, ?, 'database', 1, ?)
      on conflict(project, tenant) do update set is_primary=1
    """, (args.project, args.tenant, args.actor))

    for u in args.allow_user or []:
        con.execute("""
          insert into project_permissions(project, subject_type, subject_value, role, created_by)
          values (?, 'user', ?, ?, ?)
          on conflict(project, subject_type, subject_value) do update set role=excluded.role
        """, (args.project, u, args.role, args.actor))

    for g in args.allow_group or []:
        con.execute("""
          insert into project_permissions(project, subject_type, subject_value, role, created_by)
          values (?, 'group', ?, ?, ?)
          on conflict(project, subject_type, subject_value) do update set role=excluded.role
        """, (args.project, g, args.role, args.actor))

    con.commit()
    con.close()

def ensure_supabase(args):
    endpoint = f"http://10.62.91.2:18095/webhook/supabase/{args.project}"
    cmd = [
        "/srv/cloudif/bin/cloudif-supabase-ensure-project-hooks.sh",
        args.tenant,
        args.project,
        endpoint
    ]
    r = subprocess.run(cmd, text=True, capture_output=True, timeout=120)
    return {
        "ok": r.returncode == 0,
        "rc": r.returncode,
        "stdout": r.stdout[-4000:],
        "stderr": r.stderr[-4000:]
    }

def ensure_forgejo(args):
    # O Forja Agent v4 espera project_slug.
    # Mantemos também project por compatibilidade com outros agentes.
    payload = {
        "project_slug": args.project,
        "project": args.project,
        "name": args.name or args.project,
        "tenant": args.tenant,
        "repo_url": args.repo_url,
        "actor": args.actor,
        "allow_users": args.allow_user or [],
        "allow_groups": args.allow_group or []
    }

    env = load_env_file("/etc/cloudif/forja-agent-client.env")
    token = env.get("FORJA_AGENT_TOKEN", "")
    headers = {}

    if token:
        headers["Authorization"] = "Bearer " + token

    res = http_json("POST", FORJA_AGENT + "/project/ensure", payload, extra_headers=headers)

    # HTTP 200 com {"ok": false} deve ser tratado como falha lógica.
    if res.get("ok") and isinstance(res.get("data"), dict) and res["data"].get("ok") is False:
        res["ok"] = False
        res["logical_error"] = True

    return res

def ensure_komodo(args):
    payload = {
        "project": args.project,
        "name": args.name or args.project,
        "tenant": args.tenant,
        "actor": args.actor,
        "repo_url": args.repo_url,
        "allow_users": args.allow_user or [],
        "allow_groups": args.allow_group or []
    }
    return http_json("POST", KOMODO_AGENT + "/komodo/project/ensure", payload)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--name", default="")
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--repo-url", required=True)
    ap.add_argument("--actor", default="portal")
    ap.add_argument("--allow-user", action="append", default=[])
    ap.add_argument("--allow-group", action="append", default=[])
    ap.add_argument("--role", default="developer")
    args = ap.parse_args()

    request = vars(args)

    save_project(args)

    supabase = ensure_supabase(args)
    forgejo = ensure_forgejo(args)
    komodo = ensure_komodo(args)

    ok = bool(supabase.get("ok") and forgejo.get("ok") and komodo.get("ok"))

    response = {
        "ok": ok,
        "project": args.project,
        "tenant": args.tenant,
        "supabase": supabase,
        "forgejo": forgejo,
        "komodo": komodo
    }

    con = db()
    con.execute("""
      insert into project_integrations(
        project, tenant, forgejo_repo_url, komodo_stack_name,
        supabase_status, forgejo_status, komodo_status, status, message, updated_at
      )
      values (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
      on conflict(project) do update set
        tenant=excluded.tenant,
        forgejo_repo_url=excluded.forgejo_repo_url,
        komodo_stack_name=excluded.komodo_stack_name,
        supabase_status=excluded.supabase_status,
        forgejo_status=excluded.forgejo_status,
        komodo_status=excluded.komodo_status,
        status=excluded.status,
        message=excluded.message,
        updated_at=CURRENT_TIMESTAMP
    """, (
        args.project,
        args.tenant,
        args.repo_url,
        "cloudif-" + args.project,
        "ok" if supabase.get("ok") else "failed",
        "ok" if forgejo.get("ok") else "failed",
        "ok" if komodo.get("ok") else "failed",
        "ready" if ok else "partial",
        "Projeto garantido nos três lados." if ok else "Projeto parcialmente garantido; verificar detalhes."
    ))
    con.commit()
    con.close()

    audit(args.actor, args.project, "project.ensure", "ok" if ok else "partial", response["komodo"].get("data", {}).get("message", ""), request, response)

    print(json.dumps(response, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
