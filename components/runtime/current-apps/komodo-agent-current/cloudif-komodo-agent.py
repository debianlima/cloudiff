import functools
#!/usr/bin/env python3
import json
import hashlib
import base64
import os
import pathlib
from pathlib import Path
import re
import sqlite3
import subprocess
import shutil
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ENV = "/etc/cloudif/komodo-agent.env"
BASE_STATE = pathlib.Path("/var/lib/cloudif/komodo-agent")
PROJECT_STATE = BASE_STATE / "projects"
DB_PATH = BASE_STATE / "komodo-agent.db"

PROJECT_STATE.mkdir(parents=True, exist_ok=True)

FORGEJO_BASE = "https://cloudiff.duckdns.org/git"
FORGEJO_PROVIDER = "cloudiff.duckdns.org/git"
DEFAULT_OWNER = "cloudif"
DEFAULT_BRANCH = "main"
DEFAULT_SERVER_NAME = "Local"

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
    create table if not exists deployments (
        id integer primary key autoincrement,
        created_at text not null,
        project text not null,
        tenant text,
        actor text,
        action text not null,
        status text not null,
        stack_id text,
        stack_name text,
        repo_id text,
        repo_name text,
        message text,
        request_json text,
        response_json text
    )
    """)
    con.execute("""
    create table if not exists integrations (
        project text primary key,
        tenant text,
        repo_name text,
        repo_url text,
        stack_name text,
        stack_id text,
        repo_id text,
        server_id text,
        server_name text,
        status text,
        message text,
        updated_at text
    )
    """)
    con.commit()
    con.close()

def db_exec(sql, params=()):
    init_db()
    con = sqlite3.connect(DB_PATH)
    # CloudIF v107 sqlite bind sanitizer
    safe_params = []
    for _v in (params or []):
        if isinstance(_v, (dict, list)):
            safe_params.append(json.dumps(_v, ensure_ascii=False))
        elif isinstance(_v, bool):
            safe_params.append(1 if _v else 0)
        else:
            safe_params.append(_v)
    con.execute(sql, safe_params)
    con.commit()
    con.close()

def db_query(sql, params=()):
    init_db()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = [dict(x) for x in con.execute(sql, params).fetchall()]
    con.close()
    return rows

def record_deployment(project, tenant, actor, action, status, message="", stack_id="", stack_name="", repo_id="", repo_name="", request=None, response=None):
    db_exec("""
    insert into deployments (
        created_at, project, tenant, actor, action, status, stack_id, stack_name,
        repo_id, repo_name, message, request_json, response_json
    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        now(),
        project or "",
        tenant or "",
        actor or "",
        action or "",
        status or "",
        stack_id or "",
        stack_name or "",
        repo_id or "",
        repo_name or "",
        message or "",
        json.dumps(request or {}, ensure_ascii=False),
        json.dumps(response or {}, ensure_ascii=False),
    ))

def load_env():
    d = {}
    try:
        with open(ENV, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return d

def send(h, code, payload):
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode()
    h.send_response(code)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Cache-Control", "no-store")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)

def safe_slug(s):
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s).strip(".-_")
    return s[:80] or "unknown"

def komodo_core_url():
    env = load_env()
    return (env.get("KOMODO_CORE_URL") or "http://10.62.91.2:9120").rstrip("/")

def auth_headers():
    env = load_env()

    key = env.get("KOMODO_API_KEY") or env.get("KOMODO_BOOTSTRAP_API_KEY") or ""
    secret = env.get("KOMODO_API_SECRET") or env.get("KOMODO_BOOTSTRAP_API_SECRET") or ""
    token = env.get("KOMODO_API_TOKEN") or env.get("KOMODO_BOOTSTRAP_TOKEN") or ""

    if key and secret:
        return {
            "X-Api-Key": key,
            "X-Api-Secret": secret,
        }, "api_key"

    if token:
        return {
            "Authorization": "Bearer " + token,
        }, "bearer_token"

    return {}, "none"

def http_request(method, url, payload=None, headers=None, timeout=45):
    headers = headers or {}
    data = None

    if payload is not None:
        data = json.dumps(payload).encode()
        headers.setdefault("Content-Type", "application/json")

    headers.setdefault("Accept", "application/json")
    headers.setdefault("User-Agent", "CloudIF-Komodo-Agent-v42")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    ctx = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                parsed = json.loads(raw) if raw else {}
            except Exception:
                parsed = {"raw": raw[:3000]}
            return {"ok": True, "status": r.status, "url": url, "data": parsed}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw[:3000]}
        return {"ok": False, "status": e.code, "url": url, "data": parsed}
    except Exception as e:
        return {"ok": False, "status": 0, "url": url, "error": str(e)}

def komodo_call(kind, op_type, params=None):
    env = load_env()
    endpoint = {
        "read": env.get("KOMODO_READ_ENDPOINT", "/read"),
        "write": env.get("KOMODO_WRITE_ENDPOINT", "/write"),
        "execute": env.get("KOMODO_EXECUTE_ENDPOINT", "/execute"),
    }[kind]

    headers, method = auth_headers()
    payload = {
        "type": op_type,
        "params": params or {},
    }

    return http_request("POST", komodo_core_url() + endpoint, payload=payload, headers=headers), method

def check_master_auth():
    headers, method = auth_headers()

    if method == "none":
        return {
            "ok": False,
            "method": "none",
            "message": "KOMODO_API_KEY/KOMODO_API_SECRET ou token não configurados.",
        }

    r, used = komodo_call("read", "ListStacks", {})
    return {
        "ok": bool(r.get("ok")),
        "method": used,
        "status": r.get("status"),
        "message": "" if r.get("ok") else str((r.get("data") or {}).get("error") or r.get("error") or "falha"),
    }

def parse_repo(repo_url, project):
    repo_url = (repo_url or "").strip()

    repo_name = safe_slug(project) if safe_slug(project).startswith("cloudif-") else "cloudif-" + safe_slug(project)
    owner = DEFAULT_OWNER
    branch = DEFAULT_BRANCH

    if repo_url:
        clean = repo_url.rstrip("/")
        if clean.endswith(".git"):
            clean_no_git = clean[:-4]
        else:
            clean_no_git = clean

        parts = clean_no_git.split("/")
        if len(parts) >= 2:
            repo_name = parts[-1]
            owner = parts[-2]

    normalized_repo = f"{owner}/{repo_name}"
    normalized_url = f"{FORGEJO_BASE}/{normalized_repo}.git"

    return {
        "owner": owner,
        "repo_name": repo_name,
        "repo_path": normalized_repo,
        "repo_url": normalized_url,
        "branch": branch,
        "git_provider": FORGEJO_PROVIDER,
    }

def _cloudif_repo_item_path(item):
    if not isinstance(item,dict): return ''
    cfg=item.get('config') if isinstance(item.get('config'),dict) else {}
    info=item.get('info') if isinstance(item.get('info'),dict) else {}
    return str(cfg.get('repo') or info.get('repo') or '').strip().removesuffix('.git')

def _cloudif_reconcile_local_repo_origin(project, repo_info):
    base=Path('/etc/komodo/stacks')/('cloudif-'+safe_slug(project))
    if not (base/'.git').exists(): return {'ok':True,'changed':False,'reason':'clone_absent'}
    try:
        old=subprocess.check_output(['git','-C',str(base),'remote','get-url','origin'],text=True,timeout=20).strip()
        parsed=urllib.parse.urlsplit(old)
        wanted_path='/git/'+repo_info['repo_path']+'.git'
        new=urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,wanted_path,'',''))
        if old==new:return {'ok':True,'changed':False,'origin_path':wanted_path}
        subprocess.run(['git','-C',str(base),'remote','set-url','origin',new],check=True,timeout=20)
        subprocess.run(['git','-C',str(base),'fetch','--quiet','origin','main'],check=True,timeout=90)
        return {'ok':True,'changed':True,'origin_path':wanted_path}
    except Exception as exc:return {'ok':False,'error':'local_repo_origin_reconcile_failed','detail':str(exc)[:500]}

def find_by_name(items, name):
    if not isinstance(items, list):
        return None
    for x in items:
        if isinstance(x, dict) and x.get("name") == name:
            return x
    return None

def item_id(x):
    if not isinstance(x, dict):
        return ""
    return x.get("id") or x.get("_id") or ""

def list_resources():
    servers, _ = komodo_call("read", "ListServers", {})
    repos, _ = komodo_call("read", "ListRepos", {})
    stacks, _ = komodo_call("read", "ListStacks", {})
    return servers, repos, stacks

def choose_server(servers_data):
    server = find_by_name(servers_data, DEFAULT_SERVER_NAME)
    if not server and isinstance(servers_data, list) and servers_data:
        server = servers_data[0]
    return server

def create_or_update_repo(repo_info, server_id):
    repos_resp, _ = komodo_call("read", "ListRepos", {})
    repos = repos_resp.get("data") if repos_resp.get("ok") else []
    exact=next((x for x in repos if isinstance(x,dict) and _cloudif_repo_item_path(x)==repo_info["repo_path"]),None)
    existing = exact or find_by_name(repos, repo_info["repo_name"])

    desired_config = {
        "server_id": server_id,
        "repo": repo_info["repo_path"],
        "branch": repo_info["branch"],
        "git_provider": repo_info["git_provider"],
        "git_https": True,
                "git_account": _cloudif_v125_git_account(),
    }

    if existing:
        rid = item_id(existing)

        # Tenta corrigir provider/link se estava errado.
        update_attempts = []
        for params in [
            {"id": rid, "config": desired_config},
            {"repo": rid, "config": desired_config},
            {"id": rid, "name": repo_info["repo_name"], "config": desired_config},
        ]:
            r, _ = komodo_call("write", "UpdateRepo", params)
            update_attempts.append({"params": params, "response": r})
            if r.get("ok"):
                return existing, {"updated": True, "attempts": update_attempts}

        return existing, {"updated": False, "exists": True, "attempts": update_attempts}

    attempts = []
    for params in [
        {"name": repo_info["repo_name"], "config": desired_config},
        {"name": repo_info["repo_name"], "server_id": server_id, "repo": repo_info["repo_path"], "branch": repo_info["branch"], "git_provider": repo_info["git_provider"], "git_https": True, "git_account": _cloudif_v125_git_account()},
        {"name": repo_info["repo_name"], "config": {"server_id": server_id, "repo": repo_info["repo_path"], "branch": repo_info["branch"], "git_provider": repo_info["git_provider"], "git_account": _cloudif_v125_git_account()}},
        {"name": repo_info["repo_name"], "config": {"server_id": server_id, "repo": repo_info["repo_url"], "branch": repo_info["branch"], "git_provider": repo_info["git_provider"], "git_account": _cloudif_v125_git_account()}},
    ]:
        r, _ = komodo_call("write", "CreateRepo", params)
        attempts.append({"params": params, "response": r})
        if r.get("ok"):
            return r.get("data"), {"created": True, "attempts": attempts}

    return None, {"created": False, "attempts": attempts}

def create_or_update_stack(project, repo_info, server_id, runtime_layout="legacy"):
    stack_name = "cloudif-" + safe_slug(project)
    compose_file = ".cloudif/docker-compose.yml" if runtime_layout == "unified-v1" else "docker-compose.yml"

    stacks_resp, _ = komodo_call("read", "ListStacks", {})
    stacks = stacks_resp.get("data") if stacks_resp.get("ok") else []
    existing = find_by_name(stacks, stack_name)

    desired_config = {
        "server_id": server_id,
        "repo": repo_info["repo_path"],
        "branch": repo_info["branch"],
        "git_provider": repo_info["git_provider"],
        "git_https": True,
                "git_account": _cloudif_v125_git_account(),
        "file_paths": [compose_file],
        "run_directory": ".",
        "webhook_enabled": True,
    }

    if existing:
        sid = item_id(existing)
        update_attempts = []
        for params in [
            {"id": sid, "config": desired_config},
            {"stack": sid, "config": desired_config},
            {"id": sid, "name": stack_name, "config": desired_config},
        ]:
            r, _ = komodo_call("write", "UpdateStack", params)
            update_attempts.append({"params": params, "response": r})
            if r.get("ok"):
                return existing, {"updated": True, "attempts": update_attempts}

        return existing, {"updated": False, "exists": True, "attempts": update_attempts}

    attempts = []
    for params in [
        {"name": stack_name, "config": desired_config},
        {"name": stack_name, "server_id": server_id, "repo": repo_info["repo_path"], "branch": repo_info["branch"], "git_provider": repo_info["git_provider"], "git_https": True, "git_account": _cloudif_v125_git_account(), "file_paths": [compose_file]},
        {"name": stack_name, "config": {"server_id": server_id, "repo": repo_info["repo_path"], "branch": repo_info["branch"], "git_provider": repo_info["git_provider"], "git_https": True, "git_account": _cloudif_v125_git_account(), "file_paths": [compose_file], "run_directory": ".", "webhook_enabled": True}},
    ]:
        r, _ = komodo_call("write", "CreateStack", params)
        attempts.append({"params": params, "response": r})
        if r.get("ok"):
            return r.get("data"), {"created": True, "attempts": attempts}

    return None, {"created": False, "attempts": attempts}

def _cloudif_related_stack_ids(project, integration=None):
    project=safe_slug(project);integration=integration or find_integration(project) or {}
    listed,_=komodo_call('read','ListStacks',{})
    stacks=listed.get('data') if isinstance(listed.get('data'),list) else []
    related=[]
    base_id=normalize_resource_id(integration.get('stack_id'))
    if base_id: related.append(base_id)
    public_numbers=set()
    try:
        ids=subprocess.check_output(['docker','ps','-aq'],text=True,timeout=20).split()
        if ids:
            rows=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True,timeout=30))
            expected_root=str((Path('/etc/komodo/stacks')/('cloudif-'+project)).resolve())
            for row in rows:
                labels=((row.get('Config') or {}).get('Labels') or {})
                config_files=str(labels.get('com.docker.compose.project.config_files') or '')
                name=str(row.get('Name') or '').lstrip('/')
                if expected_root in config_files:
                    match=re.match(r'^cloudif-p(\d+)-d\d+-web$',name)
                    if match: public_numbers.add(match.group(1))
    except Exception: pass
    for item in stacks:
        if not isinstance(item,dict): continue
        name=str(item.get('name') or '')
        rid=normalize_resource_id(item.get('_id') or item.get('id'))
        if rid and any(name.startswith('cloudif-p'+number+'-d') for number in public_numbers): related.append(rid)
    tenant=str(integration.get('tenant') or '').strip()
    tenant_stack={}
    if tenant:
        tenant_name='cloudif-tenant-'+safe_slug(tenant)
        tenant_stack=next((x for x in stacks if isinstance(x,dict) and x.get('name')==tenant_name),None) or {}
        if not tenant_stack:
            servers,_=komodo_call('read','ListServers',{})
            server_items=servers.get('data') if isinstance(servers.get('data'),list) else []
            server=next((x for x in server_items if isinstance(x,dict) and x.get('name')=='Hospedagem-Supabase'),None)
            server_id=normalize_resource_id((server or {}).get('_id') or (server or {}).get('id'))
            if server_id:
                cfg={'server_id':server_id,'files_on_host':True,'run_directory':'/srv/cloudif/tenants/'+tenant,'file_paths':['docker-compose.yml'],'env_file_path':'.env','project_name':'cloudif_'+tenant,'auto_pull':False,'run_build':False,'webhook_enabled':False,'send_alerts':False}
                komodo_call('write','CreateStack',{'name':tenant_name,'config':cfg})
                listed,_=komodo_call('read','ListStacks',{})
                stacks=listed.get('data') if isinstance(listed.get('data'),list) else []
                tenant_stack=next((x for x in stacks if isinstance(x,dict) and x.get('name')==tenant_name),None) or {}
        tenant_id=normalize_resource_id(tenant_stack.get('_id') or tenant_stack.get('id'))
        if tenant_id: related.append(tenant_id)
    return list(dict.fromkeys(x for x in related if x))

def _cloudif_sync_project_authz(project, owner, acl, stack_id, repo_id, stack_ids=None, server_id=""):
    payload={'project':safe_slug(project),'owner':str(owner or '').strip().lower(),'acl':acl if isinstance(acl,list) else [],'stack_id':str(stack_id or ''),'stack_ids':stack_ids if isinstance(stack_ids,list) else ([str(stack_id)] if stack_id else []),'repo_id':str(repo_id or ''),'server_id':str(server_id or '')}
    try:
        proc=subprocess.run(['/usr/local/sbin/cloudif-komodo-project-authz.py'],input=json.dumps(payload),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90,check=False)
        result=json.loads((proc.stdout or '{}').splitlines()[-1])
        if proc.returncode not in (0,3) and result.get('ok') is not False:result={'ok':False,'error':'authz_helper_failed','detail':(proc.stderr or proc.stdout or '')[-500:]}
        return result
    except Exception as exc:return {'ok':False,'error':'komodo_authz_sync_failed','detail':str(exc)[:500]}

def cloudif_project_authz_sync(handler):
    if not _cloudif_pub_auth(handler): return send(handler,403,{'ok':False,'error':'forbidden'})
    payload=_cloudif_pub_json(handler);project=safe_slug(payload.get('project') or payload.get('slug') or '')
    integration=find_integration(project)
    if not integration:return send(handler,404,{'ok':False,'error':'project_not_integrated'})
    access=payload.get('access') if isinstance(payload.get('access'),dict) else {}
    stack_ids=_cloudif_related_stack_ids(project,integration)
    result=_cloudif_sync_project_authz(project,access.get('owner') or payload.get('owner_user'),access.get('acl') or [],normalize_resource_id(integration.get('stack_id')),normalize_resource_id(integration.get('repo_id')),stack_ids,normalize_resource_id(integration.get('server_id')))
    return send(handler,200 if result.get('ok') else 422,result)

def ensure_project(payload):
    # CloudIF v125: aplica wrapper runtime para /write e payloads antes do provisionamento.
    _cloudif_v125_runtime_patch()


    # CloudIF v124: git_account será aplicado em configs antes de enviar ao Komodo Core.
    project = safe_slug(payload.get("project") or payload.get("slug") or payload.get("name"))
    tenant = safe_slug(payload.get("tenant") or "")
    actor = payload.get("actor") or "unknown"
    repo_url = payload.get("repo_url") or ""

    result = {
        "ok": False,
        "project": project,
        "tenant": tenant,
        "actor": actor,
        "repo_url_original": repo_url,
        "time": now(),
        "actions": [],
    }

    auth = check_master_auth()
    result["auth"] = auth

    if not auth.get("ok"):
        result["stage"] = "auth"
        result["message"] = "Falha na autenticação Komodo."
        record_deployment(project, tenant, actor, "ensure", "failed", result["message"], request=payload, response=result)
        return result

    repo_info = parse_repo(repo_url, project)
    result["forgejo"] = repo_info

    servers, repos, stacks = list_resources()
    result["checks"] = {
        "servers": {"ok": servers.get("ok"), "status": servers.get("status"), "count": len(servers.get("data") or []) if isinstance(servers.get("data"), list) else None},
        "repos": {"ok": repos.get("ok"), "status": repos.get("status"), "count": len(repos.get("data") or []) if isinstance(repos.get("data"), list) else None},
        "stacks": {"ok": stacks.get("ok"), "status": stacks.get("status"), "count": len(stacks.get("data") or []) if isinstance(stacks.get("data"), list) else None},
    }

    server = choose_server(servers.get("data") if servers.get("ok") else [])
    if not server:
        result["stage"] = "no_server"
        result["message"] = "Komodo API funcional, mas não há Server cadastrado."
        record_deployment(project, tenant, actor, "ensure", "failed", result["message"], request=payload, response=result)
        return result

    server_id = item_id(server)
    server_name = server.get("name") or DEFAULT_SERVER_NAME

    result["server"] = {
        "id": server_id,
        "name": server_name,
        "state": server.get("state"),
    }
    result["runtime"] = {
        "layout": str(payload.get("runtime_layout") or "managed-root-v1"),
        "runtime_template": str(payload.get("runtime_template") or "node22"),
        "php_version": str(payload.get("php_version") or "8.3"),
        "infrastructure_in_git": False,
    }

    repo, repo_action = create_or_update_repo(repo_info, server_id)
    result["repo_action"] = repo_action
    result["local_repo_origin"] = _cloudif_reconcile_local_repo_origin(project,repo_info)

    if not repo or not result["local_repo_origin"].get("ok"):
        result["stage"] = "repo"
        result["message"] = "Não foi possível criar/atualizar Repo no Komodo."
        record_deployment(project, tenant, actor, "ensure", "failed", result["message"], server_id, "", "", repo_info["repo_name"], request=payload, response=result)
        return result

    stack, stack_action = create_or_update_stack(project, repo_info, server_id, str(payload.get("runtime_layout") or "legacy"))
    result["stack_action"] = stack_action

    if not stack:
        result["stage"] = "stack"
        result["message"] = "Não foi possível criar/atualizar Stack no Komodo."
        record_deployment(project, tenant, actor, "ensure", "failed", result["message"], server_id, "", item_id(repo), repo_info["repo_name"], request=payload, response=result)
        return result

    stack_id = item_id(stack)
    repo_id = item_id(repo)
    stack_name = stack.get("name") or ("cloudif-" + project)
    access=payload.get("access") if isinstance(payload.get("access"),dict) else {}
    temp_integration={'stack_id':stack_id,'repo_id':repo_id,'tenant':tenant}
    stack_ids=_cloudif_related_stack_ids(project,temp_integration)
    authz=_cloudif_sync_project_authz(project,access.get("owner") or payload.get("owner_user") or actor,access.get("acl") or [],stack_id,repo_id,stack_ids,server_id)
    result["authz"] = authz
    if not authz.get("ok"):
        result["stage"]="authz";result["message"]="Stack criada, mas as permissões do projeto não foram sincronizadas."
        record_deployment(project,tenant,actor,"ensure","failed",result["message"],stack_id,stack_name,repo_id,repo_info["repo_name"],request=payload,response=result)
        return result

    result["ok"] = True
    result["stage"] = "ready"
    result["message"] = "Projeto sincronizado no Komodo com Forgejo normalizado."
    result["repo"] = {"id": repo_id, "name": repo_info["repo_name"], "owner": repo_info["owner"], "path": repo_info["repo_path"], "url": repo_info["repo_url"]}
    result["stack"] = {"id": stack_id, "name": stack_name, "state": stack.get("state")}

    db_exec("""
    insert into integrations (
        project, tenant, repo_name, repo_url, stack_name, stack_id, repo_id,
        server_id, server_name, status, message, updated_at
    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    on conflict(project) do update set
        tenant=excluded.tenant,
        repo_name=excluded.repo_name,
        repo_url=excluded.repo_url,
        stack_name=excluded.stack_name,
        stack_id=excluded.stack_id,
        repo_id=excluded.repo_id,
        server_id=excluded.server_id,
        server_name=excluded.server_name,
        status=excluded.status,
        message=excluded.message,
        updated_at=excluded.updated_at
    """, (
        project, tenant, repo_info["repo_name"], repo_info["repo_url"], stack_name,
        stack_id, repo_id, server_id, server_name, "ready", result["message"], now()
    ))

    PROJECT_STATE.joinpath(project + ".json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    record_deployment(project, tenant, actor, "ensure", "ok", result["message"], stack_id, stack_name, repo_id, repo_info["repo_name"], request=payload, response=result)

    return result

def find_integration(project):
    rows = db_query("select * from integrations where project=?", (safe_slug(project),))
    return rows[0] if rows else None

def normalize_resource_id(value):
    if isinstance(value, dict):
        return str(value.get("$oid") or value.get("oid") or value.get("id") or "").strip()
    text=str(value or "").strip()
    if text.startswith("{"):
        try:
            parsed=json.loads(text)
            if isinstance(parsed,dict):
                return str(parsed.get("$oid") or parsed.get("oid") or parsed.get("id") or "").strip()
        except Exception:
            pass
    return text

def repo_absent(repo_id, repo_name):
    listed, _ = komodo_call("read", "ListRepos", {})
    if not listed.get("ok"):
        return False, listed
    raw = listed.get("data")
    items = raw if isinstance(raw, list) else []
    wanted_id = normalize_resource_id(repo_id)
    wanted_name = str(repo_name or "").strip()
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = normalize_resource_id(item.get("_id") or item.get("id"))
        item_name = str(item.get("name") or "").strip()
        if (wanted_id and item_id == wanted_id) or (wanted_name and item_name == wanted_name):
            return False, {"ok": True, "found": {"id": item_id, "name": item_name}}
    return True, {"ok": True, "found": None}


def resolve_repo_resource(integration):
    repo_id = normalize_resource_id(integration.get("repo_id"))
    repo_name = str(integration.get("repo_name") or "").strip()
    if repo_id:
        return repo_id, repo_name
    listed, _ = komodo_call("read", "ListRepos", {})
    items = listed.get("data") if isinstance(listed.get("data"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if repo_name and name == repo_name:
            return normalize_resource_id(item.get("_id") or item.get("id")), name
        if not repo_name and name == str(integration.get("stack_name") or "").strip():
            return normalize_resource_id(item.get("_id") or item.get("id")), name
    return "", repo_name

def stack_absent(stack_id, stack_name):
    listed, _ = komodo_call("read", "ListStacks", {})
    if not listed.get("ok"):
        return False, listed
    raw = listed.get("data")
    items = raw if isinstance(raw, list) else []
    wanted_id = normalize_resource_id(stack_id)
    wanted_name = str(stack_name or "").strip()
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = normalize_resource_id(item.get("_id") or item.get("id"))
        item_name = str(item.get("name") or "").strip()
        if (wanted_id and item_id == wanted_id) or (wanted_name and item_name == wanted_name):
            return False, {"ok": True, "found": {"id": item_id, "name": item_name}}
    return True, {"ok": True, "found": None}

def _cloudif_project_containers(project):
    project = safe_slug(project)
    expected_root = str((Path("/etc/komodo/stacks") / ("cloudif-" + project)).resolve())
    proc=subprocess.run(["docker","ps","-a","--format","{{.ID}}"],text=True,capture_output=True,timeout=30,check=False)
    items=[]; errors=[]
    for cid in [x.strip() for x in (proc.stdout or "").splitlines() if x.strip()]:
        try:
            raw=subprocess.check_output(["docker","inspect",cid],text=True,timeout=20)
            info=json.loads(raw)[0]; cfg=info.get("Config") or {}; labels=cfg.get("Labels") or {}; name=str(info.get("Name") or "").lstrip('/')
            config_files=str(labels.get("com.docker.compose.project.config_files") or "")
            explicit_project=str(labels.get("cloudif.project") or "")
            belongs = explicit_project == project or any(path.strip().startswith(expected_root + "/") for path in config_files.split(',') if path.strip())
            if not belongs:
                continue
            service=str(labels.get("com.docker.compose.service") or labels.get("cloudif.service") or "")
            lowered=(name+" "+service+" "+json.dumps(labels,ensure_ascii=False)).lower()
            database=any(marker in lowered for marker in ("cloudif.role=database","cloudif.service=database","-db-","_db_","postgres","supabase-db"))
            items.append({"id":cid,"name":name,"labels":labels,"service":service,"database":database,"config_files":config_files})
        except Exception as exc:
            errors.append({"id":cid,"error":str(exc)[:300]})
    return {"ok": proc.returncode == 0 and not errors, "items": items, "errors": errors, "stderr": (proc.stderr or "")[:500], "expected_root": expected_root}


def _cloudif_remove_project_application_containers(project):
    before = _cloudif_project_containers(project)
    removed = []
    errors = []
    for item in before.get("items", []):
        if item.get("database"):
            continue
        proc = subprocess.run(["docker", "rm", "-f", item["id"]], text=True, capture_output=True, timeout=60, check=False)
        if proc.returncode == 0:
            removed.append(item["name"])
        else:
            errors.append({"name": item["name"], "error": (proc.stderr or proc.stdout or "")[:500]})
    after = _cloudif_project_containers(project)
    remaining_application = [x for x in after.get("items", []) if not x.get("database")]
    preserved_database = [x["name"] for x in after.get("items", []) if x.get("database")]
    return {"ok": not errors and not remaining_application, "removed": removed, "errors": errors, "remaining_application": remaining_application, "preserved_database": preserved_database}



def _cloudif_delete_related_resources(project, public_number=0, tenant=''):
    project=safe_slug(project)
    tenant=safe_slug(tenant)
    public_numbers={str(int(public_number))} if str(public_number or '').isdigit() and int(public_number or 0)>0 else set()
    base_name='cloudif-'+project
    publication_stack_re=re.compile(r'^cloudif-p(\d+)-d(\d+)$')
    publication_container_re=re.compile(r'^cloudif-p(\d+)-d(\d+)-web$')
    terminal_prefix=base_name+'-'
    result={
        'ok':True,'project':project,'tenant_preserved':tenant,'public_numbers':[],
        'terminals':{'matched':[],'deleted':[],'errors':[]},
        'publication_stacks':{'matched':[],'destroyed':[],'deleted':[],'errors':[]},
        'builds':{'matched':[],'deleted':[],'errors':[]},
        'images':{'matched':[],'deleted':[],'errors':[]},
        'paths':{'matched':[],'deleted':[],'errors':[]},
        'tenant_stack_preserved':'cloudif-tenant-'+tenant if tenant else '',
    }
    # Discover public number from containers and stack names when it was not supplied.
    try:
        ids=subprocess.check_output(['docker','ps','-aq'],text=True,timeout=20).split()
        if ids:
            rows=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True,timeout=30))
            expected_root=str((Path('/etc/komodo/stacks')/base_name).resolve())
            for row in rows:
                name=str(row.get('Name') or '').lstrip('/')
                labels=((row.get('Config') or {}).get('Labels') or {})
                files=[str(x).strip() for x in str(labels.get('com.docker.compose.project.config_files') or '').split(',')]
                explicit=str(labels.get('cloudif.project') or '')
                if explicit==project or any(x.startswith(expected_root+'/') for x in files if x):
                    match=publication_container_re.match(name)
                    if match: public_numbers.add(match.group(1))
    except Exception as exc:
        result['publication_stacks']['errors'].append({'stage':'container_discovery','error':str(exc)[:300]})

    listed,_=komodo_call('read','ListStacks',{'limit':0})
    stacks=listed.get('data') if isinstance(listed.get('data'),list) else []
    related_stack_ids=set()
    publication_stacks=[]
    for item in stacks:
        if not isinstance(item,dict): continue
        name=str(item.get('name') or '')
        rid=normalize_resource_id(item.get('_id') or item.get('id'))
        if name==base_name and rid: related_stack_ids.add(rid)
        match=publication_stack_re.match(name)
        if match and (not public_numbers or match.group(1) in public_numbers):
            public_numbers.add(match.group(1))
            publication_stacks.append({'id':rid,'name':name})
            if rid: related_stack_ids.add(rid)
    result['public_numbers']=sorted(public_numbers)

    # Terminals are independent resources and must be removed before their stacks.
    terminals_res,_=komodo_call('read','ListTerminals',{'limit':0,'use_names':False})
    terminals=terminals_res.get('data') if isinstance(terminals_res.get('data'),list) else []
    for item in terminals:
        if not isinstance(item,dict): continue
        name=str(item.get('name') or '')
        target=item.get('target') if isinstance(item.get('target'),dict) else {}
        params=target.get('params') if isinstance(target.get('params'),dict) else {}
        target_stack=normalize_resource_id(params.get('stack')) if target.get('type')=='Stack' else ''
        container=str(params.get('container') or '') if target.get('type')=='Container' else ''
        container_match=publication_container_re.match(container)
        belongs=(name.startswith(terminal_prefix) or target_stack in related_stack_ids or bool(container_match and container_match.group(1) in public_numbers))
        if not belongs: continue
        result['terminals']['matched'].append(name)
        deleted,_=komodo_call('write','DeleteTerminal',{'target':target,'terminal':name})
        if deleted.get('ok'): result['terminals']['deleted'].append(name)
        else: result['terminals']['errors'].append({'name':name,'response':deleted})

    # Destroy and delete only publication stacks. Tenant stack is intentionally excluded.
    for item in publication_stacks:
        name=item['name'];rid=item['id']
        result['publication_stacks']['matched'].append(name)
        destroyed,_=komodo_call('execute','DestroyStack',{'stack':rid or name})
        destroy_ok=destroyed.get('ok')
        if destroy_ok:
            opid=normalize_resource_id((destroyed.get('data') or {}).get('_id') if isinstance(destroyed.get('data'),dict) else '')
            if opid:
                final=_cloudif_pub_wait_operation(opid,timeout=180)
                destroy_ok=final.get('success') is True
        if destroy_ok: result['publication_stacks']['destroyed'].append(name)
        else:
            text=json.dumps(destroyed,ensure_ascii=False)
            if 'Did not find any Stack matching' not in text:
                result['publication_stacks']['errors'].append({'name':name,'stage':'destroy','response':destroyed})
        deleted,_=komodo_call('write','DeleteStack',{'id':rid or name})
        if deleted.get('ok') or 'Did not find any Stack matching' in json.dumps(deleted,ensure_ascii=False):
            result['publication_stacks']['deleted'].append(name)
        else: result['publication_stacks']['errors'].append({'name':name,'stage':'delete','response':deleted})

    # Komodo Build resources, when present, are matched by project slug or publication number.
    builds_res,_=komodo_call('read','ListBuilds',{'limit':0})
    builds=builds_res.get('data') if isinstance(builds_res.get('data'),list) else []
    for item in builds:
        if not isinstance(item,dict): continue
        name=str(item.get('name') or '')
        rid=normalize_resource_id(item.get('_id') or item.get('id'))
        config=item.get('config') if isinstance(item.get('config'),dict) else {}
        haystack=' '.join([name,str(config.get('repo') or ''),str(config.get('image_name') or ''),json.dumps(config,ensure_ascii=False)])
        belongs=(project in haystack or any(('p'+n) in haystack or ('publication-p'+n) in haystack for n in public_numbers))
        if not belongs: continue
        result['builds']['matched'].append(name)
        deleted,_=komodo_call('write','DeleteBuild',{'id':rid or name})
        if deleted.get('ok'): result['builds']['deleted'].append(name)
        else: result['builds']['errors'].append({'name':name,'response':deleted})

    # Remove only project-specific images; shared runtime base images are never matched.
    try:
        rows=subprocess.check_output(['docker','images','--format','{{.Repository}}:{{.Tag}}'],text=True,timeout=30).splitlines()
        image_names=[]
        for image in rows:
            if any(image.startswith('cloudif/publication-p'+n+'-d') for n in public_numbers) or any(image.startswith('cloudif/project-'+n+':') for n in public_numbers):
                image_names.append(image)
        result['images']['matched']=sorted(set(image_names))
        for image in result['images']['matched']:
            proc=subprocess.run(['docker','image','rm','-f',image],text=True,capture_output=True,timeout=120,check=False)
            if proc.returncode==0: result['images']['deleted'].append(image)
            else: result['images']['errors'].append({'image':image,'error':(proc.stderr or proc.stdout or '')[:500]})
    except Exception as exc:
        result['images']['errors'].append({'error':str(exc)[:300]})

    # Remove immutable publication snapshots and version stack directories.
    paths=[]
    for number in public_numbers:
        paths.append(Path('/srv/cloudif/publications')/('p'+number))
        paths.extend(Path('/etc/komodo/stacks').glob('cloudif-p'+number+'-d*'))
    for path in sorted(set(paths),key=lambda x:str(x)):
        if not path.exists(): continue
        result['paths']['matched'].append(str(path))
        try:
            if path.is_dir(): shutil.rmtree(path)
            else: path.unlink()
            result['paths']['deleted'].append(str(path))
        except Exception as exc: result['paths']['errors'].append({'path':str(path),'error':str(exc)[:300]})

    # Verify no derived resources remain. Tenant stack is excluded by design.
    after_stacks,_=komodo_call('read','ListStacks',{'limit':0})
    after_items=after_stacks.get('data') if isinstance(after_stacks.get('data'),list) else []
    remaining_stacks=[str(x.get('name') or '') for x in after_items if isinstance(x,dict) and publication_stack_re.match(str(x.get('name') or '')) and (not public_numbers or publication_stack_re.match(str(x.get('name') or '')).group(1) in public_numbers)]
    after_terms,_=komodo_call('read','ListTerminals',{'limit':0,'use_names':False})
    after_term_items=after_terms.get('data') if isinstance(after_terms.get('data'),list) else []
    remaining_terminals=[str(x.get('name') or '') for x in after_term_items if isinstance(x,dict) and str(x.get('name') or '').startswith(terminal_prefix)]
    result['remaining']={'publication_stacks':remaining_stacks,'terminals':remaining_terminals}
    result['ok']=not any((result['terminals']['errors'],result['publication_stacks']['errors'],result['builds']['errors'],result['images']['errors'],result['paths']['errors'],remaining_stacks,remaining_terminals))
    return result

def stack_action(action, payload):
    project = safe_slug(payload.get("project") or "")
    tenant = safe_slug(payload.get("tenant") or "")
    actor = payload.get("actor") or "unknown"
    integration = find_integration(project)

    if not integration:
        if action == "destroy":
            derived_cleanup = _cloudif_delete_related_resources(project,payload.get('public_number') or 0,tenant)
            container_cleanup = _cloudif_remove_project_application_containers(project)
            result = {
                "ok": bool(container_cleanup.get("ok") and derived_cleanup.get("ok")),
                "stage": "integration",
                "project": project,
                "tenant": tenant,
                "actor": actor,
                "action": action,
                "idempotent_absent": True,
                "container_cleanup": container_cleanup,
        "derived_cleanup": derived_cleanup,
                "message": "Projeto já ausente do Komodo; containers de aplicação verificados." if container_cleanup.get("ok") else "Projeto ausente do Komodo, mas restaram containers de aplicação.",
            }
            record_deployment(project, tenant, actor, action, "ok" if result["ok"] else "failed", result["message"], request=payload, response=result)
            return result
        result = {"ok": False, "stage": "integration", "message": "Projeto não integrado no Komodo.", "project": project}
        record_deployment(project, tenant, actor, action, "failed", result["message"], request=payload, response=result)
        return result

    stack_id = normalize_resource_id(integration.get("stack_id"))
    stack_name = str(integration.get("stack_name") or "").strip()

    op_map = {
        "deploy": ["DeployStack"],
        "deploy-if-changed": ["DeployStackIfChanged"],
        "pull": ["PullStack"],
        "start": ["StartStack"],
        "stop": ["StopStack"],
        "restart": ["RestartStack"],
        "destroy": ["DestroyStack"],
        # O Komodo 2.2.0 não expõe RollbackStack direto.
        # Rollback real será feito depois por commit específico + DeployStack.
        "rollback": [],
    }

    if action == "rollback":
        result = {
            "ok": False,
            "project": project,
            "tenant": tenant,
            "actor": actor,
            "action": action,
            "stack_id": stack_id,
            "stack_name": stack_name,
            "attempts": [],
            "message": "Rollback direto ainda não existe na API Komodo 2.2.0. Será implementado por commit específico."
        }
        record_deployment(project, tenant, actor, action, "failed", result["message"], stack_id, stack_name, integration.get("repo_id"), integration.get("repo_name"), request=payload, response=result)
        return result

    derived_cleanup = _cloudif_delete_related_resources(project,payload.get('public_number') or 0,tenant) if action=='destroy' else {'ok':True,'skipped':True}
    attempts = []
    ok = False
    last = None

    for op in op_map.get(action, []):
        for params in [
            {"stack": stack_id},
            {"id": stack_id},
            {"stack_id": stack_id},
            {"name": stack_name},
        ]:
            r, _ = komodo_call("execute", op, params)
            attempts.append({"op": op, "params": params, "response": r})
            last = r
            response_text=json.dumps(r,ensure_ascii=False)
            already_absent=(action=="destroy" and "Did not find any Stack matching" in response_text)
            if r.get("ok") or already_absent:
                ok = True
                if already_absent:
                    attempts[-1]["idempotent_absent"] = True
                break
        if ok:
            break

    operation_id = ""
    operation_final = {}
    verified_absent = False
    absence_check = {}
    delete_stack = {}
    delete_repo = {}
    repo_verified_absent = True
    repo_absence_check = {"ok": True, "found": None}
    if action == "destroy" and ok:
        last_data = (last or {}).get("data") if isinstance(last, dict) else {}
        operation_id = normalize_resource_id((last_data or {}).get("_id") if isinstance(last_data, dict) else "")
        idempotent_absent = any(bool(a.get("idempotent_absent")) for a in attempts)
        if operation_id:
            operation_final = _cloudif_pub_wait_operation(operation_id, timeout=180)
            operation_ok = operation_final.get("success") is True and bool(operation_final.get("end_ts"))
        else:
            operation_ok = idempotent_absent
        if operation_ok and not idempotent_absent:
            delete_stack, _ = komodo_call("write", "DeleteStack", {"id": stack_id})
        else:
            delete_stack = {"ok": bool(idempotent_absent), "idempotent_absent": bool(idempotent_absent)}
        verified_absent, absence_check = stack_absent(stack_id, stack_name)
        repo_id, repo_name = resolve_repo_resource(integration)
        if repo_id:
            delete_repo, _ = komodo_call("write", "DeleteRepo", {"id": repo_id})
        else:
            delete_repo = {"ok": True, "skipped": True, "reason": "repo_not_found"}
        repo_verified_absent, repo_absence_check = repo_absent(repo_id, repo_name)
        container_cleanup = _cloudif_remove_project_application_containers(project)
        # A ausência verificada é a condição final de sucesso. As chamadas DeleteStack/DeleteRepo
        # podem responder "not found" em retomadas idempotentes depois que o recurso já sumiu.
        stack_final_ok = bool(verified_absent and container_cleanup.get("ok"))
        repo_final_ok = bool(repo_verified_absent)
        ok = bool(operation_ok and stack_final_ok and repo_final_ok and derived_cleanup.get('ok'))
    else:
        container_cleanup = {"ok": action != "destroy", "skipped": True}

    result = {
        "ok": ok,
        "project": project,
        "tenant": tenant,
        "actor": actor,
        "action": action,
        "stack_id": stack_id,
        "stack_name": stack_name,
        "attempts": attempts,
        "operation_id": operation_id,
        "operation_final": operation_final,
        "delete_stack": delete_stack,
        "verified_absent": verified_absent,
        "absence_check": absence_check,
        "delete_repo": delete_repo,
        "repo_verified_absent": repo_verified_absent,
        "repo_absence_check": repo_absence_check,
        "container_cleanup": container_cleanup,
        "message": ("Stack destruída e ausência confirmada." if action == "destroy" and ok else "Ação executada.") if ok else "Ação não concluída ou ausência da stack não confirmada.",
    }

    record_deployment(project, tenant, actor, action, "ok" if ok else "failed", result["message"], stack_id, stack_name, integration.get("repo_id"), integration.get("repo_name"), request=payload, response=result)
    return result


def extract_operation_ids_from_response_json(response_json):
    ids = []

    def walk(x):
        if isinstance(x, dict):
            oid = None

            if isinstance(x.get("_id"), dict):
                oid = x["_id"].get("$oid") or x["_id"].get("oid")

            if isinstance(x.get("data"), dict) and isinstance(x["data"].get("_id"), dict):
                oid = x["data"]["_id"].get("$oid") or x["data"]["_id"].get("oid")

            if isinstance(x.get("data"), dict) and isinstance(x["data"].get("id"), str):
                maybe = x["data"].get("id")
                if len(maybe) == 24:
                    oid = maybe

            if isinstance(x.get("id"), str) and len(x.get("id")) == 24:
                oid = x.get("id")

            if oid and oid not in ids:
                ids.append(oid)

            for v in x.values():
                walk(v)

        elif isinstance(x, list):
            for v in x:
                walk(v)

    try:
        data = json.loads(response_json or "{}")
        walk(data)
    except Exception:
        pass

    return ids

def komodo_mongo_env():
    core = ""
    mongo = ""

    try:
        ps = subprocess.run(
            ["bash", "-lc", "docker ps --format '{{.Names}} {{.Image}}'"],
            text=True,
            capture_output=True,
            timeout=8
        ).stdout.splitlines()

        for line in ps:
            l = line.lower()
            name = line.split()[0] if line.split() else ""
            if "komodo-core" in l:
                core = name
            if "mongo" in l and "komodo" in l:
                mongo = name
    except Exception:
        pass

    if not core or not mongo:
        return {"ok": False, "error": "containers_not_found", "core": core, "mongo": mongo}

    try:
        env_raw = subprocess.run(
            ["docker", "exec", core, "sh", "-lc", "env | grep -E '^KOMODO_DATABASE_(USERNAME|PASSWORD)=' || true"],
            text=True,
            capture_output=True,
            timeout=8
        ).stdout
    except Exception as e:
        return {"ok": False, "error": str(e), "core": core, "mongo": mongo}

    d = {}
    for line in env_raw.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            d[k] = v

    user = d.get("KOMODO_DATABASE_USERNAME", "")
    password = d.get("KOMODO_DATABASE_PASSWORD", "")

    if not user or not password:
        return {"ok": False, "error": "missing_mongo_credentials", "core": core, "mongo": mongo}

    return {"ok": True, "core": core, "mongo": mongo, "user": user, "password": password}


def cloudif_safe_error(e):
    """Oculta comandos e variáveis sensíveis em erros retornados ao Portal."""
    msg = str(e)
    upper = msg.upper()

    sensitive_words = [
        "MONGO_PASS", "MONGO_USER", "PASSWORD", "PASS=", "TOKEN",
        "SECRET", "KEY=", "AUTHORIZATION", "BEARER"
    ]

    if "COMMAND '" in upper or "DOCKER EXEC" in upper:
        return "Falha ao consultar operações do Komodo/Mongo. Detalhe interno ocultado por segurança."

    for word in sensitive_words:
        if word in upper:
            return "Falha ao consultar operações do Komodo/Mongo. Detalhe sensível ocultado por segurança."

    return msg[:500]


def komodo_query_updates(operation_ids):
    if not operation_ids:
        return {}

    env = komodo_mongo_env()
    if not env.get("ok"):
        return {"_error": env}

    js_ids = json.dumps(operation_ids)

    js = f"""
const ids = {js_ids};
const kdb = db.getSiblingDB("komodo");
const out = [];
for (const id of ids) {{
  try {{
    const doc = kdb.Update.findOne({{ _id: ObjectId(id) }});
    if (doc) {{
      out.push({{
        id: id,
        operation: doc.operation,
        status: doc.status,
        success: doc.success,
        start_ts: doc.start_ts,
        end_ts: doc.end_ts,
        target: doc.target,
        operator: doc.operator,
        logs: (doc.logs || []).slice(-50)
      }});
    }} else {{
      out.push({{ id: id, status: "not_found" }});
    }}
  }} catch(e) {{
    out.push({{ id: id, status: "error", error: String(e) }});
  }}
}}
print(JSON.stringify(out));
"""

    try:
        tmp_host = "/tmp/cloudif-komodo-query-updates.js"
        Path(tmp_host).write_text(js)

        subprocess.run(
            ["docker", "cp", tmp_host, f"{env['mongo']}:/tmp/cloudif-komodo-query-updates.js"],
            text=True,
            capture_output=True,
            timeout=8
        )

        shell = subprocess.run(
            ["docker", "exec", env["mongo"], "sh", "-lc", "command -v mongosh >/dev/null 2>&1 && echo mongosh || echo mongo"],
            text=True,
            capture_output=True,
            timeout=8
        ).stdout.strip() or "mongosh"

        r = subprocess.run(
            [
                "docker", "exec",
                "-e", f"MONGO_USER={env['user']}",
                "-e", f"MONGO_PASS={env['password']}",
                env["mongo"],
                "sh", "-lc",
                f'{shell} --quiet -u "$MONGO_USER" -p "$MONGO_PASS" --authenticationDatabase admin /tmp/cloudif-komodo-query-updates.js'
            ],
            text=True,
            capture_output=True,
            timeout=60
        )

        if r.returncode != 0:
            return {"_error": {"rc": r.returncode, "stderr": "Falha no mongosh. Saída ocultada por segurança."}}

        text = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "[]"
        data = json.loads(text)
        return {x.get("id"): x for x in data if isinstance(x, dict)}

    except Exception as e:
        return {"_error": {"error": cloudif_safe_error(e)}}

def human_operation_status(update):
    if not update:
        return "sem_operação"

    if update.get("status") == "not_found":
        return "operação_não_encontrada"

    status = str(update.get("status") or "").lower()
    success = update.get("success")
    end_ts = update.get("end_ts")

    if status in ["inprogress", "in_progress", "running"] or not end_ts:
        return "em_andamento"

    if success is True:
        return "sucesso"

    if success is False:
        return "falha"

    return status or "desconhecido"

def enrich_deployment_rows(rows):
    op_ids = []

    for row in rows:
        ids = extract_operation_ids_from_response_json(row.get("response_json") or "")
        row["operation_ids"] = ids
        op_ids.extend(ids)

    updates = komodo_query_updates(sorted(set(op_ids))) if op_ids else {}

    for row in rows:
        final_updates = []
        for oid in row.get("operation_ids") or []:
            u = updates.get(oid) if isinstance(updates, dict) else None
            if u:
                final_updates.append(u)

        row["komodo_updates"] = final_updates

        if final_updates:
            row["operation_status"] = human_operation_status(final_updates[-1])
            row["operation_status_raw"] = final_updates[-1].get("status")
            row["operation_success"] = final_updates[-1].get("success")
            row["operation_start_ts"] = final_updates[-1].get("start_ts")
            row["operation_end_ts"] = final_updates[-1].get("end_ts")
            row["operation_name"] = final_updates[-1].get("operation")
        else:
            row["operation_status"] = "sem_operação"

    if isinstance(updates, dict) and updates.get("_error"):
        for row in rows:
            row["operation_query_error"] = updates["_error"]

    return rows



# CloudIF v51 rollback por commit BEGIN

def v51_load_env(path):
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

def v51_send(handler, code, data):
    body = json.dumps(data, ensure_ascii=False, indent=2).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def v51_read_json_body(handler):
    try:
        length = int(handler.headers.get("Content-Length", "0") or "0")
        raw = handler.rfile.read(length).decode("utf-8", "ignore") if length else "{}"
        return json.loads(raw or "{}")
    except Exception:
        return {}

def v51_komodo_headers():
    env = v51_load_env("/etc/cloudif/komodo-agent.env")
    key = env.get("KOMODO_API_KEY") or env.get("KOMODO_BOOTSTRAP_API_KEY") or ""
    secret = env.get("KOMODO_API_SECRET") or env.get("KOMODO_BOOTSTRAP_API_SECRET") or ""
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "CloudIF-Komodo-Agent-v51",
        "X-Api-Key": key,
        "X-Api-Secret": secret,
    }

def v51_komodo_call(kind, op, params=None, timeout=90):
    core = v51_load_env("/etc/cloudif/komodo-agent.env").get("KOMODO_CORE_URL", "http://10.62.91.2:9120").rstrip("/")
    path = {"read": "/read", "write": "/write", "execute": "/execute"}[kind]
    payload = {"type": op, "params": params or {}}

    req = urllib.request.Request(
        core + path,
        data=json.dumps(payload).encode(),
        headers=v51_komodo_headers(),
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                data = json.loads(raw) if raw else {}
            except Exception:
                data = {"raw": raw[:3000]}
            return {"ok": True, "status": r.status, "data": data}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {"raw": raw[:3000]}
        return {"ok": False, "status": e.code, "data": data}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e), "data": {}}

def v51_stack_name(project):
    project = safe_slug(project) if "safe_slug" in globals() else re.sub(r"[^a-zA-Z0-9_.-]+", "-", project).strip("-").lower()
    if project.startswith("cloudif-"):
        return project
    return "cloudif-" + project

def v51_find_by_name(items, name):
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            return item
    return None

def v51_item_id(item):
    if not isinstance(item, dict):
        return ""
    return item.get("id") or item.get("_id") or ""

def v51_repo_path_from_project(project):
    project = safe_slug(project) if "safe_slug" in globals() else re.sub(r"[^a-zA-Z0-9_.-]+", "-", project).strip("-").lower()
    repo_name = project if project.startswith("cloudif-") else "cloudif-" + project
    return "cloudif", repo_name, "cloudif/" + repo_name

def v51_list_commits(project, limit=20):
    env = v51_load_env("/etc/cloudif/forja-agent.env")
    forgejo_url = env.get("FORGEJO_URL", "https://cloudiff.duckdns.org/git").rstrip("/")
    token = env.get("FORGEJO_TOKEN", "")

    owner, repo_name, repo_path = v51_repo_path_from_project(project)

    url = (
        forgejo_url
        + "/api/v1/repos/"
        + urllib.parse.quote(owner)
        + "/"
        + urllib.parse.quote(repo_name)
        + "/commits?sha=main&limit="
        + str(int(limit))
    )

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": "token " + token,
            "Accept": "application/json",
            "User-Agent": "CloudIF-Komodo-Agent-v51",
        },
        method="GET"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8", "ignore") or "[]")
    except Exception as e:
        return {"ok": False, "error": str(e), "items": []}

    items = []
    for c in data if isinstance(data, list) else []:
        commit = c.get("commit", {}) if isinstance(c, dict) else {}
        author = commit.get("author", {}) if isinstance(commit, dict) else {}
        items.append({
            "sha": c.get("sha", ""),
            "short": (c.get("sha", "") or "")[:7],
            "message": (commit.get("message", "") or "").strip(),
            "author": author.get("name", ""),
            "date": author.get("date", ""),
            "html_url": c.get("html_url", ""),
        })

    return {"ok": True, "project": project, "repo": repo_path, "items": items}

def v51_handle_commits(handler):
    parsed = urllib.parse.urlparse(handler.path)
    qs = urllib.parse.parse_qs(parsed.query)
    project = qs.get("project", [""])[0]
    limit = int(qs.get("limit", ["20"])[0] or "20")

    if not project:
        return v51_send(handler, 400, {"ok": False, "error": "project obrigatório"})

    return v51_send(handler, 200, v51_list_commits(project, limit))

def v51_handle_rollback_commit(handler):
    payload = v51_read_json_body(handler)

    project = payload.get("project", "")
    tenant = payload.get("tenant", "")
    actor = payload.get("actor", "portal")
    commit = payload.get("commit", "") or payload.get("sha", "")

    if not project:
        return v51_send(handler, 400, {"ok": False, "error": "project obrigatório"})
    if not commit or len(commit) < 7:
        return v51_send(handler, 400, {"ok": False, "error": "commit obrigatório"})

    stack_name = v51_stack_name(project)
    owner, repo_name, repo_path = v51_repo_path_from_project(project)

    stacks = v51_komodo_call("read", "ListStacks", {})
    stack = v51_find_by_name(stacks.get("data"), stack_name)

    if not stack:
        return v51_send(handler, 404, {
            "ok": False,
            "error": "stack_not_found",
            "stack_name": stack_name,
            "stacks_status": stacks.get("status")
        })

    stack_id = v51_item_id(stack)
    info = stack.get("info", {}) or {}
    server_id = info.get("server_id", "") or payload.get("server_id", "")

    if not server_id:
        return v51_send(handler, 422, {"ok": False, "error": "server_id não localizado na stack"})

    config = {
        "server_id": server_id,
        "repo": repo_path,
        "branch": "main",
        "commit": commit,
        "git_provider": "cloudiff.duckdns.org/git",
        "git_https": True,
                "git_account": _cloudif_v125_git_account(),
        "git_account": "cloudif-bot",
        "file_paths": ["docker-compose.yml"],
        "run_directory": ".",
        "webhook_enabled": True,
        "reclone": True,
    }

    update = v51_komodo_call("write", "UpdateStack", {"id": stack_id, "config": config})
    pull = v51_komodo_call("execute", "PullStack", {"stack": stack_id})
    deploy = v51_komodo_call("execute", "DeployStack", {"stack": stack_id})

    result = {
        "ok": bool(update.get("ok") and pull.get("ok") and deploy.get("ok")),
        "project": project,
        "tenant": tenant,
        "actor": actor,
        "action": "rollback-commit",
        "commit": commit,
        "stack_id": stack_id,
        "stack_name": stack_name,
        "update": update,
        "pull": pull,
        "deploy": deploy,
        "message": "Rollback por commit enviado ao Komodo."
    }

    try:
        if "record_deployment" in globals():
            record_deployment(
                project, tenant, actor, "rollback-commit",
                "ok" if result["ok"] else "failed",
                result["message"], stack_id, stack_name,
                "", "", request=payload, response=result
            )
    except Exception:
        pass

    return v51_send(handler, 200 if result["ok"] else 422, result)

# CloudIF v51 rollback por commit END



# CloudIF v52 rollback por branch temporária BEGIN

def v52_load_env(path):
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

def v52_send(handler, code, data):
    body = json.dumps(data, ensure_ascii=False, indent=2).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def v52_read_json_body(handler):
    try:
        length = int(handler.headers.get("Content-Length", "0") or "0")
        raw = handler.rfile.read(length).decode("utf-8", "ignore") if length else "{}"
        return json.loads(raw or "{}")
    except Exception:
        return {}

def v52_slug(s):
    if "safe_slug" in globals():
        return safe_slug(s)
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(s)).strip("-").lower()

def v52_repo_parts(project):
    project = v52_slug(project)
    repo_name = project if project.startswith("cloudif-") else "cloudif-" + project
    return "cloudif", repo_name, "cloudif/" + repo_name

def v52_stack_name(project):
    project = v52_slug(project)
    return project if project.startswith("cloudif-") else "cloudif-" + project

def v52_komodo_headers():
    env = v52_load_env("/etc/cloudif/komodo-agent.env")
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "CloudIF-Komodo-Agent-v52",
        "X-Api-Key": env.get("KOMODO_API_KEY") or env.get("KOMODO_BOOTSTRAP_API_KEY") or "",
        "X-Api-Secret": env.get("KOMODO_API_SECRET") or env.get("KOMODO_BOOTSTRAP_API_SECRET") or "",
    }

def v52_komodo_call(kind, op, params=None, timeout=90):
    core = v52_load_env("/etc/cloudif/komodo-agent.env").get("KOMODO_CORE_URL", "http://10.62.91.2:9120").rstrip("/")
    path = {"read": "/read", "write": "/write", "execute": "/execute"}[kind]
    payload = {"type": op, "params": params or {}}
    req = urllib.request.Request(
        core + path,
        data=json.dumps(payload).encode(),
        headers=v52_komodo_headers(),
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                data = json.loads(raw) if raw else {}
            except Exception:
                data = {"raw": raw[:3000]}
            return {"ok": True, "status": r.status, "data": data}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {"raw": raw[:3000]}
        return {"ok": False, "status": e.code, "data": data}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e), "data": {}}

def v52_find_by_name(items, name):
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            return item
    return None

def v52_item_id(item):
    if not isinstance(item, dict):
        return ""
    return item.get("id") or item.get("_id") or ""

def v52_forgejo_call(method, path, payload=None):
    env = v52_load_env("/etc/cloudif/forja-agent.env")
    base = env.get("FORGEJO_URL", "https://cloudiff.duckdns.org/git").rstrip("/")
    token = env.get("FORGEJO_TOKEN", "")
    url = base + path

    data = None
    headers = {
        "Authorization": "token " + token,
        "Accept": "application/json",
        "User-Agent": "CloudIF-Komodo-Agent-v52",
    }

    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                parsed = json.loads(raw) if raw else {}
            except Exception:
                parsed = {"raw": raw[:3000]}
            return {"ok": True, "status": r.status, "data": parsed}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw[:3000]}
        return {"ok": False, "status": e.code, "data": parsed}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e), "data": {}}

def v52_ensure_rollback_branch(project, commit):
    owner, repo_name, repo_path = v52_repo_parts(project)
    branch = "cloudif-rollback/" + v52_slug(project)

    encoded_owner = urllib.parse.quote(owner)
    encoded_repo = urllib.parse.quote(repo_name)
    encoded_branch = urllib.parse.quote(branch, safe="")

    # Verifica se branch existe.
    get_branch = v52_forgejo_call(
        "GET",
        f"/api/v1/repos/{encoded_owner}/{encoded_repo}/branches/{encoded_branch}"
    )

    if get_branch.get("ok"):
        # Atualiza referência existente.
        # Forgejo/Gitea aceita PATCH /git/refs/heads/{branch} em várias versões.
        ref_path = urllib.parse.quote("heads/" + branch, safe="")
        patch = v52_forgejo_call(
            "PATCH",
            f"/api/v1/repos/{encoded_owner}/{encoded_repo}/git/refs/{ref_path}",
            {"sha": commit, "force": True}
        )

        # Fallback: delete + create se PATCH não existir.
        if not patch.get("ok"):
            delete = v52_forgejo_call(
                "DELETE",
                f"/api/v1/repos/{encoded_owner}/{encoded_repo}/branches/{encoded_branch}"
            )
            create = v52_forgejo_call(
                "POST",
                f"/api/v1/repos/{encoded_owner}/{encoded_repo}/branches",
                {"new_branch_name": branch, "old_ref_name": commit}
            )
            return {
                "ok": create.get("ok"),
                "branch": branch,
                "mode": "delete_create",
                "get": get_branch,
                "patch": patch,
                "delete": delete,
                "create": create,
            }

        return {"ok": True, "branch": branch, "mode": "patch_ref", "get": get_branch, "patch": patch}

    # Cria branch nova a partir do commit.
    create = v52_forgejo_call(
        "POST",
        f"/api/v1/repos/{encoded_owner}/{encoded_repo}/branches",
        {"new_branch_name": branch, "old_ref_name": commit}
    )

    return {"ok": create.get("ok"), "branch": branch, "mode": "create", "get": get_branch, "create": create}

def v52_stack_update_and_deploy(project, branch, actor, tenant, action):
    stack_name = v52_stack_name(project)
    owner, repo_name, repo_path = v52_repo_parts(project)

    stacks = v52_komodo_call("read", "ListStacks", {})
    stack = v52_find_by_name(stacks.get("data"), stack_name)

    if not stack:
        return {"ok": False, "error": "stack_not_found", "stack_name": stack_name}

    stack_id = v52_item_id(stack)
    info = stack.get("info", {}) or {}
    server_id = info.get("server_id", "")

    if not server_id:
        return {"ok": False, "error": "server_id_not_found", "stack_name": stack_name}

    config = {
        "server_id": server_id,
        "repo": repo_path,
        "branch": branch,
        "commit": "",
        "git_provider": "cloudiff.duckdns.org/git",
        "git_https": True,
                "git_account": _cloudif_v125_git_account(),
        "git_account": "cloudif-bot",
        "file_paths": ["docker-compose.yml"],
        "run_directory": ".",
        "webhook_enabled": True,
        "reclone": True,
    }

    update = v52_komodo_call("write", "UpdateStack", {"id": stack_id, "config": config})
    pull = v52_komodo_call("execute", "PullStack", {"stack": stack_id})
    deploy = v52_komodo_call("execute", "DeployStack", {"stack": stack_id})

    result = {
        "ok": bool(update.get("ok") and pull.get("ok") and deploy.get("ok")),
        "project": project,
        "tenant": tenant,
        "actor": actor,
        "action": action,
        "branch": branch,
        "stack_id": stack_id,
        "stack_name": stack_name,
        "update": update,
        "pull": pull,
        "deploy": deploy,
        "message": "Stack atualizada para branch e deploy enviado."
    }

    try:
        if "record_deployment" in globals():
            record_deployment(
                project, tenant, actor, action,
                "ok" if result["ok"] else "failed",
                result["message"], stack_id, stack_name,
                "", "", request={"project": project, "tenant": tenant, "actor": actor, "branch": branch},
                response=result
            )
    except Exception:
        pass

    return result

def v52_handle_rollback_branch(handler):
    payload = v52_read_json_body(handler)
    project = payload.get("project", "")
    tenant = payload.get("tenant", "")
    actor = payload.get("actor", "portal")
    commit = payload.get("commit", "") or payload.get("sha", "")

    if not project:
        return v52_send(handler, 400, {"ok": False, "error": "project obrigatório"})
    if not commit or len(commit) < 7:
        return v52_send(handler, 400, {"ok": False, "error": "commit obrigatório"})

    br = v52_ensure_rollback_branch(project, commit)

    if not br.get("ok"):
        return v52_send(handler, 422, {
            "ok": False,
            "error": "rollback_branch_failed",
            "branch_result": br
        })

    result = v52_stack_update_and_deploy(project, br["branch"], actor, tenant, "rollback-branch")
    result["commit"] = commit
    result["branch_result"] = br

    return v52_send(handler, 200 if result.get("ok") else 422, result)

def v52_handle_return_main(handler):
    payload = v52_read_json_body(handler)
    project = payload.get("project", "")
    tenant = payload.get("tenant", "")
    actor = payload.get("actor", "portal")

    if not project:
        return v52_send(handler, 400, {"ok": False, "error": "project obrigatório"})

    result = v52_stack_update_and_deploy(project, "main", actor, tenant, "return-main")
    return v52_send(handler, 200 if result.get("ok") else 422, result)

# CloudIF v52 rollback por branch temporária END



# CloudIF v53c rollback file_contents BEGIN

def v53c_load_env(path):
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

def v53c_send(handler, code, data):
    body = json.dumps(data, ensure_ascii=False, indent=2).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def v53c_body(handler):
    try:
        length = int(handler.headers.get("Content-Length", "0") or "0")
        raw = handler.rfile.read(length).decode("utf-8", "ignore") if length else "{}"
        return json.loads(raw or "{}")
    except Exception:
        return {}

def v53c_slug(s):
    if "safe_slug" in globals():
        return safe_slug(s)
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(s)).strip("-").lower()

def v53c_parts(project):
    slug = v53c_slug(project)
    repo_name = slug if slug.startswith("cloudif-") else "cloudif-" + slug
    stack_name = repo_name
    return "cloudif", repo_name, "cloudif/" + repo_name, stack_name

def v53c_komodo_headers():
    env = v53c_load_env("/etc/cloudif/komodo-agent.env")
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "CloudIF-Komodo-Agent-v53c",
        "X-Api-Key": env.get("KOMODO_API_KEY") or env.get("KOMODO_BOOTSTRAP_API_KEY") or "",
        "X-Api-Secret": env.get("KOMODO_API_SECRET") or env.get("KOMODO_BOOTSTRAP_API_SECRET") or "",
    }

def v53c_komodo_call(kind, op, params=None, timeout=90):
    core = v53c_load_env("/etc/cloudif/komodo-agent.env").get("KOMODO_CORE_URL", "http://10.62.91.2:9120").rstrip("/")
    path = {"read": "/read", "write": "/write", "execute": "/execute"}[kind]
    req = urllib.request.Request(
        core + path,
        data=json.dumps({"type": op, "params": params or {}}).encode(),
        headers=v53c_komodo_headers(),
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                data = json.loads(raw) if raw else {}
            except Exception:
                data = {"raw": raw[:3000]}
            return {"ok": True, "status": r.status, "data": data}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {"raw": raw[:3000]}
        return {"ok": False, "status": e.code, "data": data}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e), "data": {}}

def v53c_forgejo_call(method, path, payload=None):
    env = v53c_load_env("/etc/cloudif/forja-agent.env")
    base = env.get("FORGEJO_URL", "https://cloudiff.duckdns.org/git").rstrip("/")
    token = env.get("FORGEJO_TOKEN", "")

    data = None
    headers = {
        "Authorization": "token " + token,
        "Accept": "application/json",
        "User-Agent": "CloudIF-Komodo-Agent-v53c",
    }

    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read().decode("utf-8", "ignore")
            return {"ok": True, "status": r.status, "data": json.loads(raw) if raw else {}}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {"raw": raw[:3000]}
        return {"ok": False, "status": e.code, "data": data}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e), "data": {}}

def v53c_find(items, name):
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            return item
    return None

def v53c_id(item):
    if not isinstance(item, dict):
        return ""
    return item.get("id") or item.get("_id") or ""

def v53c_get_compose_at_commit(project, commit):
    owner, repo_name, repo_path, stack_name = v53c_parts(project)
    attempts = []
    for filename in ("docker-compose.yml", "compose.yaml", "compose.yml"):
        path = (
            "/api/v1/repos/" + urllib.parse.quote(owner) + "/" + urllib.parse.quote(repo_name)
            + "/contents/" + urllib.parse.quote(filename) + "?ref=" + urllib.parse.quote(commit)
        )
        for attempt in range(1, 4):
            res = v53c_forgejo_call("GET", path)
            attempts.append({"filename": filename, "attempt": attempt, "ok": bool(res.get("ok")), "status": int(res.get("status") or 0)})
            if res.get("ok"):
                encoded = res.get("data", {}).get("content", "")
                try:
                    content = base64.b64decode(encoded).decode("utf-8", "ignore")
                except Exception as e:
                    return {"ok": False, "error": "compose_decode_failed", "filename": filename, "detail": str(e), "attempts": attempts}
                if not content.strip():
                    return {"ok": False, "error": "compose_empty", "filename": filename, "attempts": attempts}
                return {"ok": True, "content": content, "filename": filename, "attempts": attempts, "forgejo": res.get("data", {})}
            status = int(res.get("status") or 0)
            if status not in (0, 404, 408, 429, 500, 502, 503, 504):
                break
            if attempt < 3:
                time.sleep(0.5 * attempt)
    return {"ok": False, "error": "compose_not_found", "attempts": attempts}

def v53c_locate_stack(project):
    owner, repo_name, repo_path, stack_name = v53c_parts(project)
    stacks = v53c_komodo_call("read", "ListStacks", {})
    stack = v53c_find(stacks.get("data"), stack_name)

    if not stack:
        return {"ok": False, "error": "stack_not_found", "stack_name": stack_name, "stacks": stacks}

    stack_id = v53c_id(stack)
    server_id = (stack.get("info") or {}).get("server_id", "")

    if not stack_id or not server_id:
        return {"ok": False, "error": "stack_id_or_server_id_empty", "stack": stack}

    return {
        "ok": True,
        "stack": stack,
        "stack_id": stack_id,
        "server_id": server_id,
        "stack_name": stack_name,
        "repo_path": repo_path,
    }

def v53c_handle_rollback_filecontents(handler):
    payload = v53c_body(handler)
    project = payload.get("project", "")
    tenant = payload.get("tenant", "")
    actor = payload.get("actor", "portal")
    commit = payload.get("commit", "") or payload.get("sha", "")

    if not project:
        return v53c_send(handler, 400, {"ok": False, "error": "project obrigatório"})
    if not commit or len(commit) < 7:
        return v53c_send(handler, 400, {"ok": False, "error": "commit obrigatório"})

    compose = v53c_get_compose_at_commit(project, commit)
    if not compose.get("ok"):
        return v53c_send(handler, 422, {"ok": False, "project": project, "commit": commit, "compose": compose})

    located = v53c_locate_stack(project)
    if not located.get("ok"):
        return v53c_send(handler, 404, {"ok": False, "project": project, "locate": located})

    stack_id = located["stack_id"]
    server_id = located["server_id"]
    stack_name = located["stack_name"]

    config = {
        "server_id": server_id,
        "files_on_host": False,
        "file_contents": compose["content"],
        "file_paths": [],
        "linked_repo": "",
        "repo": "",
        "branch": "",
        "commit": "",
        "git_provider": "",
        "git_https": True,
                "git_account": _cloudif_v125_git_account(),
        "git_account": _cloudif_v124_git_account(),
        "run_directory": ".",
        "webhook_enabled": False,
        "reclone": False,
    }

    update = v53c_komodo_call("write", "UpdateStack", {"id": stack_id, "config": config})
    deploy = v53c_komodo_call("execute", "DeployStack", {"stack": stack_id})

    operation_id = ""
    try:
        operation_id = str((((deploy.get("data") or {}).get("_id") or {}).get("$oid")) or "")
    except Exception:
        operation_id = ""
    operation_final = {}
    poll_snapshots = []
    deadline = time.time() + 240
    if update.get("ok") and deploy.get("ok") and operation_id:
        while time.time() < deadline:
            updates = komodo_query_updates([operation_id])
            operation_final = updates.get(operation_id) if isinstance(updates, dict) else {}
            poll_snapshots.append({
                "elapsed": round(240 - max(0, deadline - time.time()), 1),
                "status": (operation_final or {}).get("status"),
                "success": (operation_final or {}).get("success"),
                "end_ts": (operation_final or {}).get("end_ts"),
            })
            if operation_final and (operation_final.get("end_ts") or operation_final.get("success") is False):
                break
            time.sleep(4)

    operation_ok = bool(
        operation_id
        and operation_final
        and operation_final.get("success") is True
        and operation_final.get("end_ts")
    )

    final_stack = _cloudif_v132_status_from_payload({"project_slug": project, "stack_id": stack_id})
    deployed_contents=((update.get("data") or {}).get("info") or {}).get("deployed_contents") or []
    same_content=any(str(x.get("contents") or "").strip()==str(compose.get("content") or "").strip() for x in deployed_contents if isinstance(x,dict))
    logs=(operation_final or {}).get("logs") or []
    rate_limited_pull=bool(logs) and all(str(x.get("stage") or "")=="Compose Pull" and "429 Too Many Requests" in str(x.get("stderr") or "") for x in logs if isinstance(x,dict))
    busy=(final_stack.get("busy") or {}) if isinstance(final_stack,dict) else {}
    final_healthy=bool(final_stack.get("ok") and final_stack.get("deploy_status") in {"ready","completed"} and not busy.get("repo") and not busy.get("stack"))
    safe_noop=bool(update.get("ok") and deploy.get("ok") and not operation_ok and same_content and rate_limited_pull and final_healthy)
    result = {
        "ok": bool(update.get("ok") and deploy.get("ok") and (operation_ok or safe_noop)),
        "project": project,
        "tenant": tenant,
        "actor": actor,
        "action": "rollback-filecontents",
        "commit": commit,
        "commit_short": commit[:7],
        "stack_id": stack_id,
        "stack_name": stack_name,
        "mode": "file_contents",
        "update": update,
        "deploy": deploy,
        "operation_id": operation_id,
        "operation_final": operation_final,
        "safe_noop": safe_noop,
        "same_content": same_content,
        "rate_limited_pull": rate_limited_pull,
        "poll_snapshots": poll_snapshots[-20:],
        "final_status": final_stack,
        "message": "Deploy por file_contents confirmado pelo Komodo." if operation_ok else ("Conteúdo já implantado; pull limitado por 429 tratado como no-op seguro." if safe_noop else "Deploy por file_contents não foi confirmado pelo Komodo.")
    }

    try:
        if "record_deployment" in globals():
            record_deployment(
                project, tenant, actor, "rollback-filecontents",
                "ok" if result["ok"] else "failed",
                result["message"], stack_id, stack_name,
                "", "", request=payload, response=result
            )
    except Exception:
        pass

    return v53c_send(handler, 200 if result["ok"] else 422, result)

def v53c_handle_return_git_main(handler):
    payload = v53c_body(handler)
    project = payload.get("project", "")
    tenant = payload.get("tenant", "")
    actor = payload.get("actor", "portal")

    if not project:
        return v53c_send(handler, 400, {"ok": False, "error": "project obrigatório"})

    owner, repo_name, repo_path, stack_name = v53c_parts(project)
    located = v53c_locate_stack(project)

    if not located.get("ok"):
        return v53c_send(handler, 404, {"ok": False, "project": project, "locate": located})

    stack_id = located["stack_id"]
    server_id = located["server_id"]

    repos = v53c_komodo_call("read", "ListRepos", {})
    repo = v53c_find(repos.get("data"), repo_name)
    repo_id = v53c_id(repo) if repo else ""

    pull_repo = None
    if repo_id:
        pull_repo = v53c_komodo_call("execute", "PullRepo", {"repo": repo_id})

    config = {
        "server_id": server_id,
        "repo": repo_path,
        "branch": "main",
        "commit": "",
        "git_provider": "cloudiff.duckdns.org/git",
        "git_https": True,
                "git_account": _cloudif_v125_git_account(),
        "git_account": "cloudif-bot",
        "file_paths": ["docker-compose.yml"],
        "run_directory": ".",
        "webhook_enabled": True,
        "reclone": True,
        "files_on_host": False,
        "file_contents": "",
    }

    update = v53c_komodo_call("write", "UpdateStack", {"id": stack_id, "config": config})
    pull_stack = v53c_komodo_call("execute", "PullStack", {"stack": stack_id})
    deploy = v53c_komodo_call("execute", "DeployStack", {"stack": stack_id})

    result = {
        "ok": bool(update.get("ok") and pull_stack.get("ok") and deploy.get("ok")),
        "project": project,
        "tenant": tenant,
        "actor": actor,
        "action": "return-git-main",
        "stack_id": stack_id,
        "stack_name": stack_name,
        "repo_id": repo_id,
        "pull_repo": pull_repo,
        "update": update,
        "pull_stack": pull_stack,
        "deploy": deploy,
        "message": "Stack restaurada para Git main e deploy enviado."
    }

    try:
        if "record_deployment" in globals():
            record_deployment(
                project, tenant, actor, "return-git-main",
                "ok" if result["ok"] else "failed",
                result["message"], stack_id, stack_name,
                repo_id, repo_name, request=payload, response=result
            )
    except Exception:
        pass

    return v53c_send(handler, 200 if result["ok"] else 422, result)

# CloudIF v53c rollback file_contents END




# CloudIF v117 — rollback remoto/local do Komodo Agent
def _cloudif_v117_slug(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value

def _cloudif_v117_repo_name(slug):
    slug = _cloudif_v117_slug(slug)
    return slug if slug.startswith("cloudif-") else "cloudif-" + slug

def _cloudif_v117_send_json(handler, code, data):
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def _cloudif_v117_read_json(handler):
    try:
        size = int(handler.headers.get("Content-Length", "0") or "0")
    except Exception:
        size = 0
    raw = handler.rfile.read(size) if size > 0 else b"{}"
    try:
        return json.loads(raw.decode("utf-8", "ignore") or "{}")
    except Exception:
        return {}

def _cloudif_v117_find_db_paths():
    paths = []
    for candidate in [
        "/var/lib/cloudif/komodo-agent.db",
        "/srv/cloudif/komodo-agent.db",
        "/var/lib/cloudif/komodo/komodo-agent.db",
        "/srv/cloudif/komodo/komodo-agent.db",
    ]:
        if Path(candidate).exists():
            paths.append(candidate)

    for root in ["/var/lib/cloudif", "/srv/cloudif"]:
        rp = Path(root)
        if rp.exists():
            for f in rp.rglob("*.db"):
                s = str(f)
                if "komodo" in s.lower() and s not in paths:
                    paths.append(s)

    return paths

def _cloudif_v117_sqlite_rollback(slug, execute=False):
    repo = _cloudif_v117_repo_name(slug)
    terms = {slug, repo, "cloudif/" + repo}
    result = []

    for db in _cloudif_v117_find_db_paths():
        item = {"db": db, "tables": []}
        try:
            con = sqlite3.connect(db)
            con.row_factory = sqlite3.Row
            tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
            for table in tables:
                try:
                    cols = [r[1] for r in con.execute(f'pragma table_info("{table}")')]
                    text_cols = [c for c in cols if any(x in c.lower() for x in ["slug", "project", "repo", "stack", "name", "id"])]
                    if not text_cols:
                        continue

                    where = []
                    params = []
                    for c in text_cols:
                        for t in terms:
                            where.append(f'"{c}" = ?')
                            params.append(t)

                    if not where:
                        continue

                    sql_count = f'select count(*) from "{table}" where ' + " or ".join(where)
                    count = con.execute(sql_count, params).fetchone()[0]

                    deleted = 0
                    if execute and count:
                        sql_del = f'delete from "{table}" where ' + " or ".join(where)
                        cur = con.execute(sql_del, params)
                        deleted = cur.rowcount if cur.rowcount != -1 else count

                    if count or deleted:
                        item["tables"].append({
                            "table": table,
                            "matched": count,
                            "deleted": deleted,
                            "columns_checked": text_cols,
                        })
                except Exception as e:
                    item["tables"].append({"table": table, "error": str(e)})

            if execute:
                con.commit()
            con.close()
        except Exception as e:
            item["error"] = str(e)

        if item.get("tables") or item.get("error"):
            result.append(item)

    return result

def cloudif_v117_komodo_project_rollback(handler):
    payload = _cloudif_v117_read_json(handler)
    slug = _cloudif_v117_slug(payload.get("project_slug") or payload.get("slug") or payload.get("project") or "")

    execute = bool(payload.get("execute") is True or str(payload.get("mode", "")).lower() == "execute")
    confirm = str(payload.get("confirm", ""))

    if not slug:
        return _cloudif_v117_send_json(handler, 400, {"ok": False, "error": "project_slug inválido"})

    expected_confirm = f"ROLLBACK {slug}"
    if execute and confirm != expected_confirm:
        return _cloudif_v117_send_json(handler, 400, {
            "ok": False,
            "error": "confirmacao_invalida",
            "expected_confirm": expected_confirm,
        })

    repo = _cloudif_v117_repo_name(slug)

    sqlite_result = _cloudif_v117_sqlite_rollback(slug, execute=execute)
    stack_path = Path('/etc/komodo/stacks') / ('cloudif-' + slug)
    state_path = PROJECT_STATE / f'{slug}.json'
    local_cleanup = {
        "stack_path": str(stack_path),
        "stack_present": stack_path.exists(),
        "state_path": str(state_path),
        "state_present": state_path.exists(),
        "stack_removed": False,
        "state_removed": False,
    }
    if execute:
        if stack_path.exists():
            shutil.rmtree(stack_path)
            local_cleanup["stack_removed"] = True
        if state_path.exists():
            state_path.unlink()
            local_cleanup["state_removed"] = True

    return _cloudif_v117_send_json(handler, 200, {
        "ok": True,
        "component": "komodo-agent",
        "mode": "execute" if execute else "dry-run",
        "project_slug": slug,
        "repo": repo,
        "sqlite": sqlite_result,
        "local_cleanup": local_cleanup,
        "remote_stack_delete": {
            "attempted": execute,
            "status": "local_stack_removed" if execute else "dry_run",
            "message": "O shell local da stack e o estado do agente são removidos no modo execute; o tenant/banco não é alterado.",
        },
    })




# CloudIF v124 — preencher git_account do Komodo para Forgejo privado
def _cloudif_v124_env(key, default=""):
    try:
        if "CFG" in globals() and isinstance(CFG, dict):
            v = CFG.get(key, "")
            if v:
                return str(v)
    except Exception:
        pass
    return str(os.environ.get(key, default) or default)

def _cloudif_v124_git_account():
    return (
        _cloudif_v124_env("KOMODO_GIT_ACCOUNT", "")
        or _cloudif_v124_env("FORGEJO_SERVICE_USER", "")
        or "cloudif-bot"
    )

def _cloudif_v124_git_provider():
    return _cloudif_v124_env("KOMODO_GIT_PROVIDER", "cloudiff.duckdns.org/git")

def _cloudif_v124_patch_config(config):
    if not isinstance(config, dict):
        return config

    # Só aplica quando é repo Forgejo CloudIF via HTTPS.
    repo = str(config.get("repo", "") or "")
    provider = str(config.get("git_provider", "") or "")

    if repo.startswith("cloudif/") or provider in ["", "cloudiff.duckdns.org/git"]:
        config["git_provider"] = _cloudif_v124_git_provider()
        config["git_https"] = True
        config["git_account"] = _cloudif_v124_git_account()

    return config

def _cloudif_v124_patch_payload(payload):
    if isinstance(payload, dict):
        cfg = payload.get("config")
        if isinstance(cfg, dict):
            payload["config"] = _cloudif_v124_patch_config(cfg)

        params = payload.get("params")
        if isinstance(params, dict) and isinstance(params.get("config"), dict):
            params["config"] = _cloudif_v124_patch_config(params["config"])

    return payload




# CloudIF v125 — injeção recursiva de git_account antes do /write
def _cloudif_v125_env(key, default=""):
    try:
        if "CFG" in globals() and isinstance(CFG, dict):
            v = CFG.get(key, "")
            if v:
                return str(v)
    except Exception:
        pass
    return str(os.environ.get(key, default) or default)

def _cloudif_v125_git_account():
    return _cloudif_v125_env("KOMODO_GIT_ACCOUNT", "cloudif-bot") or "cloudif-bot"

def _cloudif_v125_git_provider():
    return _cloudif_v125_env("KOMODO_GIT_PROVIDER", "cloudiff.duckdns.org/git") or "cloudiff.duckdns.org/git"

def _cloudif_v125_is_cloudif_config(d):
    if not isinstance(d, dict):
        return False

    repo = str(d.get("repo", "") or "")
    provider = str(d.get("git_provider", "") or "")

    return (
        repo.startswith("cloudif/")
        or provider in ["cloudiff.duckdns.org/git", "cloudiff.duckdns.org"]
        or "cloudiff.duckdns.org/git" in provider
    )

def _cloudif_v125_patch_obj(obj):
    """
    Percorre dict/list e injeta git_account em qualquer config de repo/stack CloudIF.
    Também injeta em dicts que já tenham repo/git_provider direto.
    """
    if isinstance(obj, dict):
        if _cloudif_v125_is_cloudif_config(obj):
            obj["git_provider"] = _cloudif_v125_git_provider()
            obj["git_https"] = True
            obj["git_account"] = _cloudif_v125_git_account()

        for k, v in list(obj.items()):
            if k == "config" and isinstance(v, dict) and _cloudif_v125_is_cloudif_config(v):
                v["git_provider"] = _cloudif_v125_git_provider()
                v["git_https"] = True
                v["git_account"] = _cloudif_v125_git_account()
                obj[k] = v
            else:
                obj[k] = _cloudif_v125_patch_obj(v)

        return obj

    if isinstance(obj, list):
        return [_cloudif_v125_patch_obj(x) for x in obj]

    return obj

def _cloudif_v125_runtime_patch():
    """
    Envolve funções comuns de escrita para garantir patch antes do envio ao Komodo Core.
    Chamar no começo do ensure_project.
    """
    if globals().get("_cloudif_v125_runtime_patched"):
        return

    globals()["_cloudif_v125_runtime_patched"] = True

    candidate_names = [
        "komodo_write",
        "core_write",
        "write",
        "komodo_core_write",
        "api_write",
        "call_write",
        "komodo_request",
        "core_request",
        "http_json",
    ]

    for name in candidate_names:
        fn = globals().get(name)
        if not callable(fn):
            continue

        # Evita envolver helper genérico demais se já foi envolvido.
        if getattr(fn, "_cloudif_v125_wrapped", False):
            continue

        def make_wrapper(original, func_name):
            def wrapper(*args, **kwargs):
                patched_args = tuple(_cloudif_v125_patch_obj(a) for a in args)
                patched_kwargs = {k: _cloudif_v125_patch_obj(v) for k, v in kwargs.items()}
                return original(*patched_args, **patched_kwargs)
            wrapper._cloudif_v125_wrapped = True
            wrapper.__name__ = getattr(original, "__name__", func_name)
            return wrapper

        globals()[name] = make_wrapper(fn, name)

def _cloudif_v125_patch_result_preview(result):
    """
    Também corrige estruturas de retorno locais antes de responder,
    para facilitar visualização de params.config no JSON.
    """
    return _cloudif_v125_patch_obj(result)




# CloudIF v131 — deploy completo Komodo usando sequência validada no v130
def _cloudif_v131_load_env_file(path="/etc/cloudif/komodo-agent.env"):
    data = {}
    try:
        p = Path(path)
        if p.exists():
            for raw in p.read_text(errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return data

def _cloudif_v131_cfg(key, default=""):
    try:
        if "CFG" in globals() and isinstance(CFG, dict):
            v = CFG.get(key, "")
            if v:
                return str(v)
    except Exception:
        pass

    if os.environ.get(key):
        return str(os.environ.get(key))

    env = _cloudif_v131_load_env_file()
    return str(env.get(key, default) or default)

def _cloudif_v131_send_json(handler, code, data):
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def _cloudif_v131_read_json(handler):
    try:
        size = int(handler.headers.get("Content-Length", "0") or "0")
    except Exception:
        size = 0
    raw = handler.rfile.read(size) if size > 0 else b"{}"
    try:
        return json.loads(raw.decode("utf-8", "ignore") or "{}")
    except Exception:
        return {}

def _cloudif_v131_project(payload):
    project = (
        payload.get("project")
        or payload.get("project_slug")
        or payload.get("slug")
        or payload.get("name")
        or ""
    )
    project = str(project or "").strip().lower()
    if project.startswith("cloudif-"):
        return project[len("cloudif-"):]
    return project

def _cloudif_v131_resource_name(project):
    project = str(project or "").strip()
    if not project:
        return "cloudif-unknown"
    if project.startswith("cloudif-"):
        return project
    return "cloudif-" + project

def _cloudif_v131_repo_path(project):
    return "cloudif/" + _cloudif_v131_resource_name(project)

def _cloudif_v131_headers():
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    key = _cloudif_v131_cfg("KOMODO_API_KEY", "")
    sec = _cloudif_v131_cfg("KOMODO_API_SECRET", "")

    if key:
        headers["X-API-Key"] = key
    if sec:
        headers["X-API-Secret"] = sec

    return headers

def _cloudif_v131_core_call(kind, typ, params, timeout=60):
    base = _cloudif_v131_cfg("KOMODO_CORE_URL", "http://10.62.91.2:9120").rstrip("/")
    params = json.loads(json.dumps(params or {}))
    if kind == "write" and typ in ("CreateStack","UpdateStack","CreateRepo","UpdateRepo"):
        cfg = params.get("config") if isinstance(params.get("config"), dict) else None
        target = cfg if cfg is not None else params
        repo = str(target.get("repo") or "")
        provider = str(target.get("git_provider") or "")
        if repo and (provider or "/" in repo):
            target["git_provider"] = provider or _cloudif_v131_cfg("KOMODO_GIT_PROVIDER", "cloudiff.duckdns.org/git")
            target["git_https"] = True
            target["git_account"] = target.get("git_account") or _cloudif_v131_cfg("KOMODO_GIT_ACCOUNT", "cloudif-bot")
    payload = {"type": typ, "params": params}
    req = urllib.request.Request(
        base + "/" + kind,
        data=json.dumps(payload).encode("utf-8"),
        headers=_cloudif_v131_headers(),
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                data = json.loads(raw) if raw else {}
            except Exception:
                data = {"raw": raw}
            return {
                "ok": r.status in [200, 201, 202],
                "status": r.status,
                "kind": kind,
                "type": typ,
                "params": params,
                "data": data,
            }
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {"raw": raw}
        return {
            "ok": False,
            "status": e.code,
            "kind": kind,
            "type": typ,
            "params": params,
            "data": data,
        }
    except Exception as e:
        return {
            "ok": False,
            "status": 0,
            "kind": kind,
            "type": typ,
            "params": params,
            "error": f"{type(e).__name__}: {e}",
        }

def _cloudif_v131_oid(resource):
    if not isinstance(resource, dict):
        return ""
    oid = resource.get("_id")
    if isinstance(oid, dict):
        return oid.get("$oid", "") or ""
    if isinstance(oid, str):
        return oid
    return resource.get("id", "") or ""

def _cloudif_v131_list_items(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["data", "items", "repos", "stacks", "resources"]:
            value = data.get(key)
            if isinstance(value, list):
                return value
        # Algumas respostas retornam dict de recursos.
        for value in data.values():
            if isinstance(value, list):
                return value
    return []

def _cloudif_v131_get_repo(repo_id="", project=""):
    name = _cloudif_v131_resource_name(project)
    repo_path = _cloudif_v131_repo_path(project)

    attempts = []

    if repo_id:
        res = _cloudif_v131_core_call("read", "GetRepo", {"id": repo_id})
        attempts.append(res)
        if res.get("ok") and isinstance(res.get("data"), dict) and res["data"].get("name"):
            return res["data"], repo_id, attempts

    for params in [
        {"name": name},
        {"repo": repo_path},
    ]:
        res = _cloudif_v131_core_call("read", "GetRepo", params)
        attempts.append(res)
        data = res.get("data")
        if res.get("ok") and isinstance(data, dict) and data.get("name"):
            return data, _cloudif_v131_oid(data), attempts

    res = _cloudif_v131_core_call("read", "ListRepos", {})
    attempts.append(res)
    for item in _cloudif_v131_list_items(res.get("data")):
        if not isinstance(item, dict):
            continue
        cfg = item.get("config") or {}
        if item.get("name") == name or cfg.get("repo") == repo_path:
            return item, _cloudif_v131_oid(item), attempts

    return {}, "", attempts

def _cloudif_v131_get_stack(stack_id="", project=""):
    name = _cloudif_v131_resource_name(project)

    attempts = []

    if stack_id:
        res = _cloudif_v131_core_call("read", "GetStack", {"id": stack_id})
        attempts.append(res)
        if res.get("ok") and isinstance(res.get("data"), dict) and res["data"].get("name"):
            return res["data"], stack_id, attempts

    for params in [
        {"name": name},
    ]:
        res = _cloudif_v131_core_call("read", "GetStack", params)
        attempts.append(res)
        data = res.get("data")
        if res.get("ok") and isinstance(data, dict) and data.get("name"):
            return data, _cloudif_v131_oid(data), attempts

    res = _cloudif_v131_core_call("read", "ListStacks", {})
    attempts.append(res)
    for item in _cloudif_v131_list_items(res.get("data")):
        if not isinstance(item, dict):
            continue
        if item.get("name") == name:
            return item, _cloudif_v131_oid(item), attempts

    return {}, "", attempts

def _cloudif_v131_summary(repo, stack):
    rinfo = repo.get("info", {}) if isinstance(repo, dict) else {}
    rcfg = repo.get("config", {}) if isinstance(repo, dict) else {}

    sinfo = stack.get("info", {}) if isinstance(stack, dict) else {}
    scfg = stack.get("config", {}) if isinstance(stack, dict) else {}

    return {
        "repo": {
            "id": _cloudif_v131_oid(repo),
            "name": repo.get("name") if isinstance(repo, dict) else None,
            "last_pulled_at": rinfo.get("last_pulled_at"),
            "latest_hash": rinfo.get("latest_hash"),
            "latest_message": rinfo.get("latest_message"),
            "cloned_hash": rinfo.get("cloned_hash"),
            "cloned_message": rinfo.get("cloned_message"),
            "git_account": rcfg.get("git_account"),
            "repo": rcfg.get("repo"),
            "branch": rcfg.get("branch"),
        },
        "stack": {
            "id": _cloudif_v131_oid(stack),
            "name": stack.get("name") if isinstance(stack, dict) else None,
            "state": sinfo.get("state"),
            "status": sinfo.get("status"),
            "missing_files": sinfo.get("missing_files"),
            "latest_hash": sinfo.get("latest_hash"),
            "latest_message": sinfo.get("latest_message"),
            "remote_errors": sinfo.get("remote_errors"),
            "services": sinfo.get("services"),
            "git_account": scfg.get("git_account"),
            "repo": scfg.get("repo"),
            "file_paths": scfg.get("file_paths"),
            "reclone": scfg.get("reclone"),
        },
    }

def _cloudif_v131_update_stack_reclone(stack_id, stack, project, reclone=True):
    if not stack_id or not isinstance(stack, dict):
        return {
            "ok": False,
            "message": "stack_id/stack ausente para UpdateStack reclone.",
        }

    cfg = dict(stack.get("config") or {})
    cfg["reclone"] = bool(reclone)
    cfg["git_account"] = cfg.get("git_account") or _cloudif_v131_cfg("KOMODO_GIT_ACCOUNT", "cloudif-bot")
    cfg["git_provider"] = cfg.get("git_provider") or _cloudif_v131_cfg("KOMODO_GIT_PROVIDER", "cloudiff.duckdns.org/git")
    cfg["git_https"] = True
    cfg["repo"] = cfg.get("repo") or _cloudif_v131_repo_path(project)
    cfg["branch"] = cfg.get("branch") or "main"
    cfg["file_paths"] = cfg.get("file_paths") or ["docker-compose.yml"]

    return _cloudif_v131_core_call("write", "UpdateStack", {
        "id": stack_id,
        "config": cfg,
    }, timeout=60)

def _cloudif_v131_wait(seconds):
    try:
        time.sleep(float(seconds))
    except Exception:
        pass

def cloudif_v131_project_deploy_full(handler):
    payload = _cloudif_v131_read_json(handler)

    project = _cloudif_v131_project(payload)
    if not project:
        return _cloudif_v131_send_json(handler, 400, {
            "ok": False,
            "error": "project/project_slug/slug obrigatório.",
        })

    repo_id_in = str(payload.get("repo_id") or "").strip()
    stack_id_in = str(payload.get("stack_id") or "").strip()

    deploy = bool(payload.get("deploy", True))
    force_reclone = bool(payload.get("force_reclone", False))
    force_clone = bool(payload.get("force_clone", True))
    reset_reclone_after = bool(payload.get("reset_reclone_after", False))

    actions = []

    repo, repo_id, repo_attempts = _cloudif_v131_get_repo(repo_id_in, project)
    stack, stack_id, stack_attempts = _cloudif_v131_get_stack(stack_id_in, project)

    before = _cloudif_v131_summary(repo, stack)

    if not repo_id:
        return _cloudif_v131_send_json(handler, 404, {
            "ok": False,
            "error": "repo Komodo não encontrado.",
            "project": project,
            "repo_name": _cloudif_v131_resource_name(project),
            "repo_path": _cloudif_v131_repo_path(project),
            "repo_lookup_attempts": repo_attempts,
        })

    if not stack_id:
        return _cloudif_v131_send_json(handler, 404, {
            "ok": False,
            "error": "stack Komodo não encontrada.",
            "project": project,
            "stack_name": _cloudif_v131_resource_name(project),
            "stack_lookup_attempts": stack_attempts,
        })

    # Sequência validada no v130.
    pull_repo = _cloudif_v131_core_call("execute", "PullRepo", {"repo": repo_id}, timeout=60)
    actions.append(pull_repo)
    _cloudif_v131_wait(payload.get("wait_after_repo_pull", 8))

    if force_clone:
        clone_repo = _cloudif_v131_core_call("execute", "CloneRepo", {"repo": repo_id}, timeout=60)
        actions.append(clone_repo)
        _cloudif_v131_wait(payload.get("wait_after_repo_clone", 8))

    # Recarrega repo/stack depois do repo pull/clone.
    repo, repo_id, _ = _cloudif_v131_get_repo(repo_id, project)
    stack, stack_id, _ = _cloudif_v131_get_stack(stack_id, project)

    sinfo = stack.get("info", {}) if isinstance(stack, dict) else {}
    missing = sinfo.get("missing_files") or []
    stack_latest = sinfo.get("latest_hash")
    rinfo = repo.get("info", {}) if isinstance(repo, dict) else {}
    repo_latest = rinfo.get("latest_hash")

    need_reclone = bool(force_reclone or missing or (repo_latest and stack_latest != repo_latest))

    if need_reclone:
        upd = _cloudif_v131_update_stack_reclone(stack_id, stack, project, reclone=True)
        actions.append(upd)
        _cloudif_v131_wait(payload.get("wait_after_update_stack", 3))

    pull_stack = _cloudif_v131_core_call("execute", "PullStack", {"stack": stack_id}, timeout=60)
    actions.append(pull_stack)
    _cloudif_v131_wait(payload.get("wait_after_stack_pull", 10))

    if deploy:
        deploy_stack = _cloudif_v131_core_call("execute", "DeployStack", {"stack": stack_id}, timeout=60)
        actions.append(deploy_stack)
        _cloudif_v131_wait(payload.get("wait_after_stack_deploy", 10))

    repo, repo_id, _ = _cloudif_v131_get_repo(repo_id, project)
    stack, stack_id, _ = _cloudif_v131_get_stack(stack_id, project)

    after = _cloudif_v131_summary(repo, stack)

    reset_action = None
    if reset_reclone_after:
        sinfo = stack.get("info", {}) if isinstance(stack, dict) else {}
        if not (sinfo.get("missing_files") or sinfo.get("remote_errors")):
            reset_action = _cloudif_v131_update_stack_reclone(stack_id, stack, project, reclone=False)
            actions.append(reset_action)
            stack, stack_id, _ = _cloudif_v131_get_stack(stack_id, project)
            after = _cloudif_v131_summary(repo, stack)

    stack_after = after.get("stack", {})
    ok = bool(
        after.get("repo", {}).get("latest_hash")
        and not (stack_after.get("missing_files") or [])
        and not (stack_after.get("remote_errors") or [])
    )

    return _cloudif_v131_send_json(handler, 200 if ok else 207, {
        "ok": ok,
        "project": project,
        "repo_id": repo_id,
        "stack_id": stack_id,
        "sequence": [
            "PullRepo",
            "CloneRepo",
            "UpdateStack(reclone=true) quando necessário",
            "PullStack",
            "DeployStack quando deploy=true",
            "GetRepo/GetStack",
        ],
        "before": before,
        "after": after,
        "actions": actions,
        "reset_reclone_after": reset_reclone_after,
        "reset_action": reset_action,
        "message": "Deploy completo Komodo v131 executado.",
    })

def cloudif_v131_stack_action(handler, action):
    payload = _cloudif_v131_read_json(handler)
    project = _cloudif_v131_project(payload)
    stack_id = str(payload.get("stack_id") or payload.get("stack") or "").strip()

    if not stack_id:
        if not project:
            return _cloudif_v131_send_json(handler, 400, {
                "ok": False,
                "error": "Informe stack_id ou project/project_slug/slug.",
            })
        stack, stack_id, attempts = _cloudif_v131_get_stack("", project)
        if not stack_id:
            return _cloudif_v131_send_json(handler, 404, {
                "ok": False,
                "error": "stack não encontrada.",
                "project": project,
                "attempts": attempts,
            })

    op = "PullStack" if action == "pull" else "DeployStack"
    result = _cloudif_v131_core_call("execute", op, {"stack": stack_id}, timeout=60)

    return _cloudif_v131_send_json(handler, 200 if result.get("ok") else 500, {
        "ok": result.get("ok"),
        "project": project or "(por stack_id)",
        "action": action,
        "operation": op,
        "stack_id": stack_id,
        "result": result,
    })




# CloudIF v132 — status unificado e deploy-full com polling assíncrono

def _cloudif_v132_status_from_payload(payload):
    project = _cloudif_v131_project(payload) if "cloudif_v131_project" not in globals() else _cloudif_v131_project(payload)

    repo_id = str(payload.get("repo_id") or payload.get("repo") or "").strip()
    stack_id = str(payload.get("stack_id") or payload.get("stack") or "").strip()

    repo, resolved_repo_id, repo_attempts = _cloudif_v131_get_repo(repo_id, project)
    stack, resolved_stack_id, stack_attempts = _cloudif_v131_get_stack(stack_id, project)

    repo_state = {}
    stack_state = {}

    if resolved_repo_id:
        repo_state = _cloudif_v131_core_call("read", "GetRepoActionState", {"repo": resolved_repo_id}, timeout=30)
    if resolved_stack_id:
        stack_state = _cloudif_v131_core_call("read", "GetStackActionState", {"stack": resolved_stack_id}, timeout=30)

    summary = _cloudif_v131_summary(repo, stack)

    raction = repo_state.get("data") if isinstance(repo_state, dict) else {}
    saction = stack_state.get("data") if isinstance(stack_state, dict) else {}

    repo_busy = bool(
        isinstance(raction, dict)
        and any(bool(raction.get(k)) for k in ["cloning", "pulling", "building", "renaming"])
    )

    stack_busy = bool(
        isinstance(saction, dict)
        and any(bool(saction.get(k)) for k in [
            "pulling", "deploying", "starting", "restarting",
            "pausing", "unpausing", "stopping", "destroying"
        ])
    )

    st = summary.get("stack", {})
    missing = st.get("missing_files") or []
    errors = st.get("remote_errors") or []

    deployed_services = None
    latest_services = None
    deployed_hash = None
    deployed_message = None

    if isinstance(stack, dict):
        info = stack.get("info") or {}
        deployed_services = info.get("deployed_services")
        latest_services = info.get("latest_services")
        deployed_hash = info.get("deployed_hash")
        deployed_message = info.get("deployed_message")

    runtime_services = []
    running_container = {}
    if resolved_stack_id:
        service_result = _cloudif_v131_core_call("read", "ListStackServices", {"stack": resolved_stack_id}, timeout=30)
        raw_services = service_result.get("data") if isinstance(service_result, dict) else []
        runtime_services = raw_services if isinstance(raw_services, list) else []
        for service_row in runtime_services:
            container = service_row.get("container") if isinstance(service_row, dict) else None
            if isinstance(container, dict) and str(container.get("state") or "").lower() == "running":
                running_container = dict(container)
                running_container["service"] = service_row.get("service") or ""
                break
        if not running_container:
            all_result = _cloudif_v131_core_call("read", "ListAllDockerContainers", {}, timeout=30)
            all_items = all_result.get("data") if isinstance(all_result, dict) else []
            all_items = all_items if isinstance(all_items, list) else []
            stack_name = str((stack or {}).get("name") or ("cloudif-" + project))
            for container in all_items:
                name = str(container.get("name") or "") if isinstance(container, dict) else ""
                if isinstance(container, dict) and str(container.get("state") or "").lower() == "running" and (stack_name in name or project in name):
                    running_container = dict(container)
                    break

    runtime_running = bool(running_container)
    if repo_busy or stack_busy:
        deploy_status = "in_progress"
    elif errors:
        deploy_status = "failed"
    elif missing:
        deploy_status = "needs_attention"
    elif runtime_running:
        deploy_status = "completed"
    elif st.get("latest_hash") or deployed_hash:
        deploy_status = "in_progress"
    else:
        deploy_status = "ready"

    return {
        "ok": deploy_status in ["completed", "ready", "in_progress"],
        "project": project,
        "repo_id": resolved_repo_id,
        "stack_id": resolved_stack_id,
        "deploy_status": deploy_status,
        "repo": summary.get("repo"),
        "stack": {
            **(summary.get("stack") or {}),
            "deployed_hash": deployed_hash,
            "deployed_message": deployed_message,
            "deployed_services": deployed_services,
            "latest_services": latest_services,
        },
        "action_state": {
            "repo": repo_state.get("data") if isinstance(repo_state, dict) else repo_state,
            "stack": stack_state.get("data") if isinstance(stack_state, dict) else stack_state,
        },
        "busy": {
            "repo": repo_busy,
            "stack": stack_busy,
        },
        "runtime": {
            "running": runtime_running,
            "container_name": running_container.get("name") or "",
            "container_state": running_container.get("state") or "missing",
            "service": running_container.get("service") or "",
            "services_count": len(runtime_services),
        },
        "lookup": {
            "repo_attempts_count": len(repo_attempts or []),
            "stack_attempts_count": len(stack_attempts or []),
        },
    }

def cloudif_v132_project_status(handler):
    payload = {}

    try:
        method = getattr(handler, "command", "GET")
    except Exception:
        method = "GET"

    if method == "POST":
        payload = _cloudif_v131_read_json(handler)
    else:
        parsed = urllib.parse.urlparse(handler.path)
        qs = urllib.parse.parse_qs(parsed.query)
        for key in ["project", "project_slug", "slug", "repo_id", "stack_id"]:
            if key in qs and qs[key]:
                payload[key] = qs[key][0]

    status = _cloudif_v132_status_from_payload(payload)
    return _cloudif_v131_send_json(handler, 200 if status.get("ok") else 207, status)

def _cloudif_v132_wait_for_completion(project, repo_id, stack_id, max_wait_seconds=90, interval=5):
    start = time.time()
    snapshots = []

    while True:
        payload = {
            "project_slug": project,
            "repo_id": repo_id,
            "stack_id": stack_id,
        }

        status = _cloudif_v132_status_from_payload(payload)
        snapshots.append({
            "elapsed": round(time.time() - start, 1),
            "deploy_status": status.get("deploy_status"),
            "busy": status.get("busy"),
            "stack": {
                "missing_files": ((status.get("stack") or {}).get("missing_files")),
                "remote_errors": ((status.get("stack") or {}).get("remote_errors")),
                "latest_hash": ((status.get("stack") or {}).get("latest_hash")),
                "deployed_hash": ((status.get("stack") or {}).get("deployed_hash")),
            },
        })

        if status.get("deploy_status") not in ["in_progress"]:
            return status, snapshots

        if time.time() - start >= float(max_wait_seconds):
            status["deploy_status"] = "in_progress"
            status["timeout"] = True
            return status, snapshots

        time.sleep(float(interval))

def _cloudif_v132_force_local_rebuild(project, no_cache=False):
    project = safe_slug(project)
    stack_dir = Path("/etc/komodo/stacks") / ("cloudif-" + project)
    unified = stack_dir / ".cloudif" / "docker-compose.yml"
    compose = unified if unified.is_file() else stack_dir / "docker-compose.yml"
    if not compose.is_file():
        return {"ok": False, "error": "local_stack_compose_missing", "stack_dir": str(stack_dir)}
    base_result = {"ok": True, "skipped": True}
    if unified.is_file():
        runtime_file = stack_dir / ".cloudif" / "runtime.json"
        base_file = stack_dir / ".cloudif" / "Dockerfile.base"
        try:
            runtime = json.loads(runtime_file.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"ok": False, "error": "runtime_manifest_invalid", "detail": str(exc)[:300]}
        base_tag = str(runtime.get("base_image") or "").strip()
        if not base_tag or not base_file.is_file():
            return {"ok": False, "error": "runtime_base_definition_missing", "base_image": base_tag}
        inspect = subprocess.run(["docker", "image", "inspect", base_tag], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if inspect.returncode != 0 or no_cache:
            cmd = ["docker", "build", "-f", ".cloudif/Dockerfile.base", "-t", base_tag]
            if no_cache: cmd.append("--no-cache")
            cmd.append(".")
            built = subprocess.run(cmd, cwd=stack_dir, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2400)
            base_result = {"ok": built.returncode == 0, "image": base_tag, "returncode": built.returncode, "detail": (built.stderr or built.stdout)[-1200:]}
            if built.returncode != 0:
                return {"ok": False, "error": "runtime_base_build_failed", "base": base_result}
        else:
            base_result = {"ok": True, "skipped": True, "image": base_tag, "reason": "shared_base_exists"}
    compose_args = ["docker", "compose", "-f", str(compose.relative_to(stack_dir))]
    env_file = stack_dir / ".cloudif" / ".env"
    if unified.is_file() and env_file.is_file():
        compose_args += ["--env-file", str(env_file.relative_to(stack_dir))]
    build_cmd = compose_args + ["build"]
    if no_cache: build_cmd.append("--no-cache")
    build = subprocess.run(build_cmd, cwd=stack_dir, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800)
    if build.returncode != 0:
        return {"ok": False, "error": "local_compose_build_failed", "returncode": build.returncode, "base": base_result, "detail": (build.stderr or build.stdout)[-1200:]}
    up = subprocess.run(compose_args + ["up", "-d", "--force-recreate"], cwd=stack_dir, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
    return {
        "ok": up.returncode == 0,
        "operation": "local_compose_rebuild",
        "layout": "unified-v1" if unified.is_file() else "legacy",
        "compose_file": str(compose.relative_to(stack_dir)),
        "base": base_result,
        "stack_dir": str(stack_dir),
        "build_returncode": build.returncode,
        "up_returncode": up.returncode,
        "detail": ((up.stderr or up.stdout) if up.returncode else (up.stdout or build.stdout))[-1200:],
    }


def _cloudif_v132_local_web_health(project, wait_seconds=90):
    stack_dir = Path("/etc/komodo/stacks") / ("cloudif-" + safe_slug(project))
    expected_compose = str((stack_dir / ".cloudif" / "docker-compose.yml").resolve())
    deadline = time.time() + max(1, int(wait_seconds))
    last = {"ok": False, "container": "", "running": False, "health": "missing", "expected_compose": expected_compose, "candidates": []}
    while time.time() < deadline:
        candidates=[]
        try:
            ps=subprocess.run(["docker","ps","-a","--format","{{.Names}}"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
            candidates=[x.strip() for x in ps.stdout.splitlines() if x.strip()]
        except Exception as exc:
            last["error"] = str(exc)[:300]
        inspected=[]
        for name in candidates:
            try:
                raw=subprocess.check_output(["docker","inspect",name],text=True,timeout=15)
                info=json.loads(raw)[0]
                labels=(info.get("Config") or {}).get("Labels") or {}
                service=str(labels.get("com.docker.compose.service") or "")
                config_files=str(labels.get("com.docker.compose.project.config_files") or "")
                if service != "web" or expected_compose not in config_files.split(','):
                    continue
                state=info.get("State") or {}; health=(state.get("Health") or {}).get("Status") or ""
                running=bool(state.get("Running")); item={"container":name,"running":running,"health":health or ("running" if running else str(state.get("Status") or "unknown")),"image":((info.get("Config") or {}).get("Image") or ""),"service":service,"config_files":config_files}
                inspected.append(item)
                if running and health in ("healthy",""):
                    result=dict(item)
                    result.update({"ok":True,"expected_compose":expected_compose,"candidates":[dict(x) for x in inspected]})
                    return result
            except Exception as exc:
                inspected.append({"container":name,"error":str(exc)[:220]})
        last={"ok":False,"container":inspected[0].get("container","") if inspected else "","running":bool(inspected and inspected[0].get("running")),"health":inspected[0].get("health","missing") if inspected else "missing","expected_compose":expected_compose,"candidates":inspected}
        time.sleep(3)
    return last


def cloudif_v132_project_deploy_full(handler):
    payload = _cloudif_v131_read_json(handler)

    # Executa a lógica v131 já validada.
    # Para evitar resposta prematura, chamamos a sequência v131 por dentro replicando o essencial,
    # mas adicionando polling/status final.
    project = _cloudif_v131_project(payload)
    if not project:
        return _cloudif_v131_send_json(handler, 400, {
            "ok": False,
            "error": "project/project_slug/slug obrigatório.",
        })

    repo_id_in = str(payload.get("repo_id") or "").strip()
    stack_id_in = str(payload.get("stack_id") or "").strip()

    deploy = bool(payload.get("deploy", True))
    force_reclone = bool(payload.get("force_reclone", False))
    force_clone = bool(payload.get("force_clone", True))
    force_rebuild = bool(payload.get("force_rebuild", False))
    no_cache = bool(payload.get("no_cache", False))
    wait_for_completion = bool(payload.get("wait_for_completion", True))
    max_wait_seconds = int(payload.get("max_wait_seconds", 90))
    poll_interval = int(payload.get("poll_interval", 5))
    reset_reclone_after = bool(payload.get("reset_reclone_after", False))

    actions = []

    repo, repo_id, repo_attempts = _cloudif_v131_get_repo(repo_id_in, project)
    stack, stack_id, stack_attempts = _cloudif_v131_get_stack(stack_id_in, project)

    before = _cloudif_v131_summary(repo, stack)

    if not repo_id:
        return _cloudif_v131_send_json(handler, 404, {
            "ok": False,
            "error": "repo Komodo não encontrado.",
            "project": project,
            "repo_lookup_attempts": repo_attempts,
        })

    if not stack_id:
        return _cloudif_v131_send_json(handler, 404, {
            "ok": False,
            "error": "stack Komodo não encontrada.",
            "project": project,
            "stack_lookup_attempts": stack_attempts,
        })

    pull_repo = _cloudif_v131_core_call("execute", "PullRepo", {"repo": repo_id}, timeout=60)
    actions.append(pull_repo)
    _cloudif_v131_wait(payload.get("wait_after_repo_pull", 8))

    if force_clone:
        clone_repo = _cloudif_v131_core_call("execute", "CloneRepo", {"repo": repo_id}, timeout=60)
        actions.append(clone_repo)
        _cloudif_v131_wait(payload.get("wait_after_repo_clone", 8))

    repo, repo_id, _ = _cloudif_v131_get_repo(repo_id, project)
    stack, stack_id, _ = _cloudif_v131_get_stack(stack_id, project)

    sinfo = stack.get("info", {}) if isinstance(stack, dict) else {}
    missing = sinfo.get("missing_files") or []
    stack_latest = sinfo.get("latest_hash")

    rinfo = repo.get("info", {}) if isinstance(repo, dict) else {}
    repo_latest = rinfo.get("latest_hash")

    need_reclone = bool(force_reclone or missing or (repo_latest and stack_latest != repo_latest))

    if need_reclone:
        upd = _cloudif_v131_update_stack_reclone(stack_id, stack, project, reclone=True)
        actions.append(upd)
        _cloudif_v131_wait(payload.get("wait_after_update_stack", 3))

    pull_stack = _cloudif_v131_core_call("execute", "PullStack", {"stack": stack_id}, timeout=60)
    actions.append(pull_stack)
    _cloudif_v131_wait(payload.get("wait_after_stack_pull", 10))

    if force_rebuild:
        rebuild_action = _cloudif_v132_force_local_rebuild(project, no_cache=no_cache)
        actions.append(rebuild_action)
        if not rebuild_action.get("ok"):
            return _cloudif_v131_send_json(handler, 500, {
                "ok": False,
                "error": "force_rebuild_failed",
                "project": project,
                "repo_id": repo_id,
                "stack_id": stack_id,
                "actions": actions,
                "rebuild": rebuild_action,
            })

    local_after_rebuild = {"ok": False}
    if force_rebuild:
        local_after_rebuild = _cloudif_v132_local_web_health(project, wait_seconds=int(payload.get("local_health_wait_seconds", 90)))
        actions.append({"operation":"local_web_health","ok":bool(local_after_rebuild.get("ok")),"detail":local_after_rebuild})
        if not local_after_rebuild.get("ok"):
            return _cloudif_v131_send_json(handler, 500, {"ok":False,"error":"local_web_health_failed","project":project,"repo_id":repo_id,"stack_id":stack_id,"actions":actions,"local_health":local_after_rebuild})
    elif deploy:
        deploy_stack = _cloudif_v131_core_call("execute", "DeployStack", {"stack": stack_id}, timeout=60)
        actions.append(deploy_stack)
        _cloudif_v131_wait(payload.get("wait_after_stack_deploy", 3))

    poll_snapshots = []

    if force_rebuild and local_after_rebuild.get("ok"):
        final_status={"project":project,"repo_id":repo_id,"stack_id":stack_id,"deploy_status":"completed","local_reconciled":True,"local_health":local_after_rebuild}
    elif wait_for_completion:
        final_status, poll_snapshots = _cloudif_v132_wait_for_completion(
            project,
            repo_id,
            stack_id,
            max_wait_seconds=max_wait_seconds,
            interval=poll_interval,
        )
    else:
        final_status = _cloudif_v132_status_from_payload({
            "project_slug": project,
            "repo_id": repo_id,
            "stack_id": stack_id,
        })

    if reset_reclone_after and final_status.get("deploy_status") in ["completed", "ready"]:
        stack_obj, stack_id2, _ = _cloudif_v131_get_stack(stack_id, project)
        reset_action = _cloudif_v131_update_stack_reclone(stack_id2, stack_obj, project, reclone=False)
        actions.append(reset_action)
        final_status = _cloudif_v132_status_from_payload({
            "project_slug": project,
            "repo_id": repo_id,
            "stack_id": stack_id,
        })
    else:
        reset_action = None

    deploy_status = final_status.get("deploy_status")
    local_health = local_after_rebuild if force_rebuild else {"ok": False}
    if deploy_status not in ["completed", "ready", "in_progress"] and local_health.get("ok"):
        deploy_status = "completed"
        final_status = dict(final_status or {})
        final_status.update({"deploy_status": "completed", "local_reconciled": True, "local_health": local_health})

    ok = deploy_status in ["completed", "ready", "in_progress"]

    http_code = 200 if deploy_status in ["completed", "ready"] else (202 if deploy_status == "in_progress" else 207)

    return _cloudif_v131_send_json(handler, http_code, {
        "ok": ok,
        "project": project,
        "repo_id": repo_id,
        "stack_id": stack_id,
        "deploy_status": deploy_status,
        "sequence": [
            "PullRepo",
            "CloneRepo",
            "UpdateStack(reclone=true) quando necessário",
            "PullStack",
            "docker compose build/up --force-recreate quando force_rebuild=true",
            "DeployStack quando deploy=true",
            "Polling GetRepoActionState/GetStackActionState",
            "GetRepo/GetStack final",
        ],
        "before": before,
        "after": final_status,
        "actions": actions,
        "poll_snapshots": poll_snapshots,
        "force_rebuild": force_rebuild,
        "no_cache": no_cache,
        "reset_reclone_after": reset_reclone_after,
        "reset_action": reset_action,
        "local_health": local_health,
        "message": "Deploy completo Komodo v132 executado.",
    })



# CloudIF fixed local stack smoke BEGIN
def cloudif_stack_http_smoke(handler):
    import hashlib,hmac
    cfg=load_env()
    expected=str(cfg.get('KOMODO_PUBLICATION_TOKEN') or '')
    supplied=str(handler.headers.get('X-CloudIF-Token') or handler.headers.get('Authorization','').replace('Bearer ','',1))
    if not expected or not hmac.compare_digest(expected,supplied):
        return send(handler,403,{'ok':False,'error':'forbidden'})
    try:payload=handler.parse_json()
    except Exception:return send(handler,400,{'ok':False,'error':'invalid_json'})
    if set(payload)!={'project'}:
        return send(handler,400,{'ok':False,'error':'invalid_request'})
    project=str(payload.get('project') or '').strip()
    targets={'sistema-de-biblioteca-teste':'http://127.0.0.1:18080/'}
    url=targets.get(project)
    if not url:return send(handler,404,{'ok':False,'error':'project_not_allowed'})
    req=urllib.request.Request(url,headers={'User-Agent':'CloudIF-Komodo-Local-Smoke/1.0','Accept':'text/html'})
    try:
        with urllib.request.urlopen(req,timeout=8) as r:
            raw=r.read(2*1024*1024+1);status=r.status;ctype=str(r.headers.get('Content-Type') or '')
    except Exception as e:
        return send(handler,502,{'ok':False,'error':'http_smoke_failed','error_type':type(e).__name__})
    if len(raw)>2*1024*1024:return send(handler,502,{'ok':False,'error':'body_too_large'})
    body=raw.decode('utf-8','replace')
    ok=status==200 and ctype.lower().startswith('text/html') and len(raw)>=32 and '<html' in body.lower()
    result={'ok':ok,'project':project,'status':status,'content_type':ctype,'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'html':True if '<html' in body.lower() else False,'target':'fixed-local','checked_at':now()}
    return send(handler,200 if ok else 502,result)
# CloudIF fixed local stack smoke END


# CloudIF versioned publications BEGIN

def _cloudif_pub_auth(handler):
    import hmac
    cfg = load_env()
    expected = str(cfg.get("KOMODO_PUBLICATION_TOKEN") or "")
    supplied = str(handler.headers.get("X-CloudIF-Token") or handler.headers.get("Authorization", "").replace("Bearer ", ""))
    return bool(expected and hmac.compare_digest(expected, supplied))

def _cloudif_pub_json(handler):
    try:
        return handler.parse_json()
    except Exception:
        return {}

def _cloudif_pub_transform_compose(content, public_number, deploy_number):
    import re
    out = str(content or "")
    out = out.replace("${CLOUDIF_PUBLIC_NUMBER}", str(public_number))
    out = out.replace("${CLOUDIF_DEPLOY_NUMBER}", str(deploy_number))
    out = re.sub(r"cloudif-p%d-d\d+-web" % int(public_number), "cloudif-p%d-d%d-web" % (int(public_number), int(deploy_number)), out)
    out = re.sub(r"^\s*-\s*cloudif-p%d-active-web\s*$" % int(public_number), "", out, flags=re.M)
    return out

def _cloudif_pub_wait_operation(operation_id, timeout=300):
    deadline = time.time() + timeout
    final = {}
    while time.time() < deadline:
        updates = komodo_query_updates([operation_id]) if operation_id else {}
        final = updates.get(operation_id) if isinstance(updates, dict) else {}
        if final and (final.get("end_ts") or final.get("success") is False):
            break
        time.sleep(4)
    return final

def _cloudif_ensure_container_terminal(server_id, container):
    import re
    terminal='sh-'+re.sub(r'[^a-zA-Z0-9_.-]+','-',container)[-48:]
    target={'type':'Container','params':{'server':server_id,'container':container}}
    listed,_=komodo_call('read','ListTerminals',{'target':target})
    items=listed.get('data') if isinstance(listed.get('data'),list) else []
    if any(x.get('name')==terminal for x in items if isinstance(x,dict)):
        return {'ok':True,'created':False,'terminal':terminal,'target':target}
    created,_=komodo_call('write','CreateTerminal',{'target':target,'name':terminal,'command':'sh','mode':'exec'})
    return {'ok':bool(created.get('ok')),'created':bool(created.get('ok')),'terminal':terminal,'target':target,'result':created}

def _cloudif_project_audit_data(payload):
    project=safe_slug(payload.get('project') or payload.get('slug') or payload.get('project_slug'))
    stack_id=str(payload.get('stack_id') or '').strip(); service=safe_slug(payload.get('service') or 'web')
    terminal=safe_slug(payload.get('terminal') or ('cloudif-'+project)); shell=str(payload.get('shell') or 'sh').strip() or 'sh'
    if project and not stack_id:
        integration=find_integration(project) or {}
        stack_id=normalize_resource_id(integration.get('stack_id'))
    if not project or not stack_id: return {'ok':False,'error':'invalid_payload','project':project,'stack_id':stack_id}
    requested_stack_id=stack_id
    stack,_=komodo_call('read','GetStack',{'stack':stack_id}); data=stack.get('data') if isinstance(stack.get('data'),dict) else {}
    if not stack.get('ok'):
        listed,_=komodo_call('read','ListStacks',{})
        raw_candidates=listed.get('data') if isinstance(listed,dict) else listed
        candidates=raw_candidates if isinstance(raw_candidates,list) else []
        wanted='cloudif-'+project
        found=next((x for x in candidates if isinstance(x,dict) and x.get('name')==wanted),None)
        if found:
            raw_id=found.get('_id') or found.get('id') or ''
            if isinstance(raw_id,dict): raw_id=raw_id.get('$oid') or ''
            if raw_id:
                stack_id=str(raw_id); stack,_=komodo_call('read','GetStack',{'stack':stack_id}); data=stack.get('data') if isinstance(stack.get('data'),dict) else {}
    info=data.get('info') if isinstance(data.get('info'),dict) else {}
    config=data.get('config') if isinstance(data.get('config'),dict) else {}
    stack_root=Path('/etc/komodo/stacks')/('cloudif-'+project)
    unified_compose=stack_root/'.cloudif'/'docker-compose.yml'
    missing=list(info.get('missing_files') or [])
    if unified_compose.is_file():
        missing=[x for x in missing if str(x) not in ('docker-compose.yml','.cloudif/docker-compose.yml')]
    services_result,_=komodo_call('read','ListStackServices',{'stack':stack_id})
    services=services_result.get('data') if isinstance(services_result.get('data'),list) else []
    service_row=next((x for x in services if isinstance(x,dict) and x.get('service')==service),None)
    if not service_row or not isinstance(service_row.get('container'),dict) or str((service_row.get('container') or {}).get('state') or '').lower()!='running':
        service_row=next((x for x in services if isinstance(x,dict) and isinstance(x.get('container'),dict) and str((x.get('container') or {}).get('state') or '').lower()=='running'),service_row)
    if service_row and service_row.get('service'): service=safe_slug(service_row.get('service'))
    container=(service_row or {}).get('container') if isinstance((service_row or {}).get('container'),dict) else {}
    if not container or str(container.get('state') or '').lower()!='running':
        expected_compose=str(unified_compose.resolve())
        try:
            ids=subprocess.check_output(['docker','ps','-aq'],text=True,timeout=15).split()
            if ids:
                rows=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True,timeout=30))
                local=next((row for row in rows if str(((row.get('Config') or {}).get('Labels') or {}).get('com.docker.compose.service') or '')==service and expected_compose in str(((row.get('Config') or {}).get('Labels') or {}).get('com.docker.compose.project.config_files') or '').split(',') and bool((row.get('State') or {}).get('Running'))),None)
                if local:
                    state=local.get('State') or {};cfg=local.get('Config') or {}
                    container={'name':str(local.get('Name') or '').lstrip('/'),'state':'running','status':str(state.get('Status') or 'running'),'image':str(cfg.get('Image') or ''),'stats':{},'local_discovered':True}
        except Exception:
            pass
    if not container or str(container.get('state') or '').lower()!='running':
        all_result,_=komodo_call('read','ListAllDockerContainers',{})
        all_items=all_result.get('data') if isinstance(all_result,dict) else all_result
        all_items=all_items if isinstance(all_items,list) else []
        stack_name=str(data.get('name') or ('cloudif-'+project))
        expected=[stack_name+'-'+service, stack_name+'-web', 'cloudif-'+project+'-'+service, 'cloudif-'+project+'-web']
        found=next((x for x in all_items if isinstance(x,dict) and str(x.get('state') or '').lower()=='running' and x.get('name') in expected),None)
        if not found:
            found=next((x for x in all_items if isinstance(x,dict) and str(x.get('state') or '').lower()=='running' and (stack_name in str(x.get('name') or '') or project in str(x.get('name') or ''))),None)
        if found:
            container=dict(found)
    state=str(container.get('state') or 'missing').lower()
    server_id=str(container.get('server_id') or info.get('server_id') or config.get('server_id') or '')
    if not server_id and state=='running':
        servers_result,_=komodo_call('read','ListServers',{})
        server_items=servers_result.get('data') if isinstance(servers_result.get('data'),list) else []
        preferred=next((x for x in server_items if isinstance(x,dict) and x.get('name')=='Local'),None) or next((x for x in server_items if isinstance(x,dict) and str((x.get('info') or {}).get('state') or '').lower()=='ok'),None)
        if preferred:
            raw_id=preferred.get('_id') or preferred.get('id') or ''
            if isinstance(raw_id,dict): raw_id=raw_id.get('$oid') or ''
            server_id=str(raw_id or '')
    container_name=str(container.get('name') or '')
    target={'type':'Container','params':{'server':server_id,'container':container_name}} if server_id and container_name else {'type':'Stack','params':{'stack':stack_id,'service':service}}
    listed,_=komodo_call('read','ListTerminals',{'target':target}); items=listed.get('data') if isinstance(listed.get('data'),list) else []
    item=next((x for x in items if isinstance(x,dict) and x.get('name')==terminal),None)
    cmd=str((item or {}).get('command') or '')
    terminal_ok=bool(item and cmd.endswith(' '+shell))
    running=state=='running'
    issues=[]
    if not stack.get('ok') and not container.get('local_discovered'): issues.append('stack_unavailable')
    if missing: issues.append('missing_compose')
    if not running: issues.append('stack_not_running')
    if not terminal_ok: issues.append('terminal_invalid')
    return {'ok':True,'project':project,'stack_id':stack_id,'service':service,'terminal':terminal,'shell':shell,
      'stack_name':data.get('name') or '', 'requested_stack_id':requested_stack_id,
      'resolved_stack_id':stack_id, 'stack_id_stale':bool(stack_id!=requested_stack_id),
      'state':state,'running':running,'missing_files':missing,
      'container_name':container.get('name') or '', 'container_status':container.get('status') or '',
      'container_image':container.get('image') or (service_row or {}).get('image') or '',
      'container_stats':container.get('stats') or {}, 'server_id':server_id,
      'terminal_target_type':target.get('type'),'terminal_ok':terminal_ok,'terminal_command':cmd,'issues':issues,'healthy':not issues,'target':target}

def cloudif_project_runtime_inspect(handler):
    if not _cloudif_pub_auth(handler):
        return send(handler,403,{'ok':False,'error':'forbidden'})
    payload=_cloudif_pub_json(handler)
    if not set(payload).issubset({'project','public_numbers'}):
        return send(handler,400,{'ok':False,'error':'invalid_request'})
    project=safe_slug(payload.get('project') or '')
    if not project:
        return send(handler,400,{'ok':False,'error':'invalid_project'})
    numbers=[]
    for value in payload.get('public_numbers') or []:
        try:
            number=int(value)
            if 1 <= number <= 999999999:numbers.append(number)
        except Exception:pass
    repo=Path('/etc/komodo/stacks')/('cloudif-'+project)
    repository_present=bool((repo/'.git').is_dir())
    files=[];commit='';images=[]
    if repository_present:
        try:
            commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True,stderr=subprocess.DEVNULL,timeout=12).strip()
            files=subprocess.check_output(['git','-C',str(repo),'ls-tree','-r','--name-only',commit],text=True,stderr=subprocess.DEVNULL,timeout=12).splitlines()
        except Exception:files=[];commit=''
        for compose_name in ('docker-compose.yml','compose.yaml','compose.yml'):
            try:
                raw=subprocess.check_output(['git','-C',str(repo),'show',commit+':'+compose_name],text=True,stderr=subprocess.DEVNULL,timeout=12)
            except Exception:continue
            images.extend(re.findall(r'^\s*image:\s*["\']?([^"\'\s#]+)',raw,re.M))
    file_set=set(files)
    def has(name):return name in file_set or any(x.endswith('/'+name) for x in file_set)
    framework='Não identificado';framework_evidence=[]
    package={}
    if repository_present and has('package.json'):
        target=next((x for x in files if x=='package.json' or x.endswith('/package.json')),'package.json')
        try:package=json.loads(subprocess.check_output(['git','-C',str(repo),'show',commit+':'+target],text=True,stderr=subprocess.DEVNULL,timeout=12))
        except Exception:package={}
        deps={**(package.get('dependencies') or {}),**(package.get('devDependencies') or {})}
        mapping=(('next','Next.js'),('nuxt','Nuxt'),('@angular/core','Angular'),('@sveltejs/kit','SvelteKit'),('astro','Astro'),('vite','Vite'),('express','Express'))
        match=next(((key,label) for key,label in mapping if key in deps),None)
        framework=match[1] if match else 'Node.js'
        framework_evidence=['package.json']+([match[0]] if match else [])
    elif repository_present and (has('composer.json') or has('index.php')):
        framework='PHP';framework_evidence=['composer.json' if has('composer.json') else 'index.php']
    elif repository_present and (has('requirements.txt') or has('pyproject.toml')):
        framework='Python';framework_evidence=['requirements.txt' if has('requirements.txt') else 'pyproject.toml']
    elif repository_present and (has('index.html') or any(x.startswith(('site/','dist/','build/','public/')) and x.endswith('.html') for x in files)):
        framework='Site estático';framework_evidence=['arquivo HTML publicado']
    if framework=='Não identificado' and any('nginx' in x.lower() for x in images):
        framework='Site estático';framework_evidence=['imagem Nginx no compose']
    candidates=[]
    try:
        ids=subprocess.check_output(['docker','ps','-aq'],text=True,timeout=15).split()
        if ids:
            rows=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True,timeout=30))
            expected={project,'cloudif-'+project}
            for info in rows:
                cfg=info.get('Config') or {};labels=cfg.get('Labels') or {};name=str(info.get('Name') or '').lstrip('/')
                compose_project=str(labels.get('com.docker.compose.project') or '')
                direct=str(labels.get('cloudif.project') or '')
                publication=any(re.match(r'^cloudif-p%d-d\d+-web$'%n,name) for n in numbers)
                if direct==project or compose_project in expected or project in name or publication:
                    candidates.append({'name':name,'image':cfg.get('Image') or '', 'running':bool((info.get('State') or {}).get('Running'))})
    except Exception:pass
    probes=(('node',['node','--version']),('npm',['npm','--version']),('php',['php','--version']),('python',['python3','--version']),('nginx',['nginx','-v']),('apache',['apache2','-v']),('httpd',['httpd','-v']))
    runtimes={}
    for container in candidates:
        if not container['running']:continue
        found={}
        for key,cmd in probes:
            try:
                run=subprocess.run(['docker','exec',container['name'],*cmd],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=6)
                text=' '.join((run.stdout or '').split())[:180]
                if run.returncode==0 and text:found[key]=text
            except Exception:pass
        if found:runtimes[container['name']]=found
    flat={}
    for values in runtimes.values():
        for key,value in values.items():flat.setdefault(key,value)
    server='Nginx' if 'nginx' in flat or any('nginx' in x.lower() for x in images+[c['image'] for c in candidates]) else ('Apache' if 'apache' in flat or 'httpd' in flat else None)
    return send(handler,200,{
        'ok':True,'read_only':True,'project':project,
        'repository':{'present':repository_present,'commit':commit,'file_count':len(files),'manifest_files':[x for x in files if x.rsplit('/',1)[-1] in ('package.json','composer.json','requirements.txt','pyproject.toml','index.php','index.html','docker-compose.yml','compose.yaml','compose.yml')][:30]},
        'detection':{'framework':framework,'evidence':framework_evidence,'server':server,'runtimes':flat},
        'containers':candidates,'container_probes':runtimes,'compose_images':sorted(set(images)),
        'mutation_supported':False,'mutation_reason':'framework_change_requires_transactional_repository_proposal_build_validation_and_rollback',
        'secrets_exposed':False,
    })


def cloudif_project_audit(handler):
    if not _cloudif_pub_auth(handler): return send(handler,403,{'ok':False,'error':'forbidden'})
    return send(handler,200,_cloudif_project_audit_data(_cloudif_pub_json(handler)))

def cloudif_project_repair(handler):
    if not _cloudif_pub_auth(handler): return send(handler,403,{'ok':False,'error':'forbidden'})
    payload=_cloudif_pub_json(handler); before=_cloudif_project_audit_data(payload)
    if not before.get('ok'): return send(handler,400,before)
    actions=[]; stack_id=before['stack_id']
    if before.get('missing_files'):
        return send(handler,422,{'ok':False,'error':'missing_compose','audit':before,'message':'O repositório não possui docker-compose.yml.'})
    if not before.get('running'):
        pull,_=komodo_call('execute','PullStack',{'stack':stack_id}); actions.append({'action':'pull','result':pull})
        deploy,_=komodo_call('execute','DeployStack',{'stack':stack_id}); actions.append({'action':'deploy','result':deploy})
        time.sleep(4)
    target=before['target']; terminal=before['terminal']; shell=before['shell']
    listed,_=komodo_call('read','ListTerminals',{'target':target}); items=listed.get('data') if isinstance(listed.get('data'),list) else []
    existing=next((x for x in items if isinstance(x,dict) and x.get('name')==terminal),None)
    if existing and not str(existing.get('command') or '').endswith(' '+shell):
        deleted,_=komodo_call('write','DeleteTerminal',{'target':target,'terminal':terminal}); actions.append({'action':'delete_terminal','result':deleted}); existing=None
    if not existing:
        created,_=komodo_call('write','CreateTerminal',{'target':target,'name':terminal,'command':shell,'mode':'exec'}); actions.append({'action':'create_terminal','result':created})
    after=_cloudif_project_audit_data(payload)
    return send(handler,200 if after.get('healthy') else 202,{'ok':True,'actions':actions,'before':before,'after':after})

def cloudif_project_runtime_info(handler):
    if not _cloudif_pub_auth(handler):
        return send(handler,403,{"ok":False,"error":"forbidden"})
    payload=_cloudif_pub_json(handler)
    project=safe_slug(payload.get("project") or ""); kind=str(payload.get("kind") or "").strip().lower()
    stack_id=normalize_resource_id(payload.get("stack_id") or ""); service=str(payload.get("service") or "web")
    if not project or kind not in {"php","node"}:
        return send(handler,400,{"ok":False,"error":"invalid_request"})

    # O diagnóstico pertence à publicação ativa, não à stack-base usada como
    # checkout. Terminal, ACL de terminal e metadados do Komodo não devem
    # bloquear uma consulta somente-leitura executada diretamente no container.
    integration=find_integration(project) or {}
    base_stack_id=normalize_resource_id(integration.get("stack_id") or stack_id)
    active=_cloudif_active_publication_stack(project,base_stack_id)
    resolved_stack_id=normalize_resource_id(active.get("stack_id") if active.get("ok") else base_stack_id)
    audit=_cloudif_project_audit_data({"project":project,"stack_id":resolved_stack_id,"service":service,"terminal":"cloudif-"+project,"shell":"sh"})

    candidates=[]
    for value in (active.get("container"),audit.get("container_name")):
        value=str(value or "").strip()
        if value and value not in candidates and re.fullmatch(r"[A-Za-z0-9_.-]+",value):
            candidates.append(value)
    container="";container_state={}
    for candidate in candidates:
        try:
            inspected=subprocess.run(
                ["docker","inspect",candidate],text=True,stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,timeout=12,check=False,
            )
            rows=json.loads(inspected.stdout or "[]") if inspected.returncode==0 else []
            state=(rows[0].get("State") or {}) if rows else {}
            if bool(state.get("Running")):
                container=candidate;container_state=state;break
        except Exception:
            continue
    if not container:
        return send(handler,422,{"ok":False,"error":"active_container_not_running","active_publication":active,"audit":audit,"candidates":candidates})
    if kind=="php":
        script="""php -v
printf '\n---INI---\n'
php --ini
printf '\n---CONFIG---\n'
php -r '$k=["memory_limit","upload_max_filesize","post_max_size","max_execution_time","date.timezone"]; foreach($k as $x){echo $x,"=",ini_get($x),PHP_EOL;}'
printf '\n---MODULES---\n'
php -m
"""
    else:
        script="""node -e 'console.log(process.version); console.log("---VERSIONS---"); console.log(JSON.stringify(process.versions,null,2)); console.log("---PLATFORM---"); console.log(process.platform+" "+process.arch)'
printf '\n---NPM---\n'
(npm --version 2>/dev/null || true)
printf '\n---PACKAGE---\n'
if [ -f /var/www/html/api/package.json ]; then
  node -e 'const p=require("/var/www/html/api/package.json"); console.log(JSON.stringify({name:p.name||"",version:p.version||"",scripts:p.scripts||{},dependencies:p.dependencies||{},devDependencies:p.devDependencies||{}},null,2))'
else
  echo 'package.json não encontrado'
fi
"""
    command=["docker","exec",container,"sh","-lc",script]
    try:
        proc=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=False)
    except Exception as exc:
        return send(handler,500,{"ok":False,"error":"runtime_info_failed","detail":str(exc)[:300]})
    return send(handler,200 if proc.returncode==0 else 422,{"ok":proc.returncode==0,"project":project,"kind":kind,"container":container,"output":(proc.stdout or "")[:120000],"stderr":(proc.stderr or "")[:4000],"returncode":proc.returncode})


def _cloudif_active_publication_stack(project, fallback_stack_id=''):
    project=safe_slug(project);fallback_stack_id=normalize_resource_id(fallback_stack_id)
    public_numbers=set();active_container='';compose_project=''
    try:
        ids=subprocess.check_output(['docker','ps','-q'],text=True,timeout=15).split()
        rows=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True,timeout=30)) if ids else []
        expected=str((Path('/etc/komodo/stacks')/('cloudif-'+project)/'.cloudif'/'docker-compose.yml').resolve())
        for row in rows:
            labels=((row.get('Config') or {}).get('Labels') or {})
            files=[str(x).strip() for x in str(labels.get('com.docker.compose.project.config_files') or '').split(',')]
            name=str(row.get('Name') or '').lstrip('/')
            if expected in files:
                match=re.match(r'^cloudif-p(\d+)-d\d+-web$',name)
                if match: public_numbers.add(match.group(1))
        for row in rows:
            name=str(row.get('Name') or '').lstrip('/')
            networks=((row.get('NetworkSettings') or {}).get('Networks') or {})
            aliases=[]
            for net in networks.values(): aliases.extend(net.get('Aliases') or [])
            for number in public_numbers:
                if 'cloudif-p'+number+'-active-web' in aliases:
                    active_container=name
                    labels=((row.get('Config') or {}).get('Labels') or {})
                    compose_project=str(labels.get('com.docker.compose.project') or '')
                    break
            if active_container: break
    except Exception: pass
    if not compose_project or not re.match(r'^cloudif-p\d+-d\d+$',compose_project):
        return {'ok':False,'stack_id':fallback_stack_id,'container':active_container,'reason':'active_version_stack_not_found'}
    listed,_=komodo_call('read','ListStacks',{})
    stacks=listed.get('data') if isinstance(listed.get('data'),list) else []
    item=next((x for x in stacks if isinstance(x,dict) and str(x.get('name') or '')==compose_project),None)
    stack_id=normalize_resource_id((item or {}).get('_id') or (item or {}).get('id'))
    return {'ok':bool(stack_id),'stack_id':stack_id or fallback_stack_id,'stack_name':compose_project,'container':active_container}

def _cloudif_reconcile_unified_stack_metadata(project, stack_id):
    project=safe_slug(project);stack_id=normalize_resource_id(stack_id)
    compose=Path('/etc/komodo/stacks')/('cloudif-'+project)/'.cloudif'/'docker-compose.yml'
    if not project or not stack_id or not compose.is_file():
        return {'ok':True,'changed':False,'reason':'not_unified'}
    public_number='';deploy_number=''
    try:
        ids=subprocess.check_output(['docker','ps','-aq'],text=True,timeout=15).split()
        if ids:
            rows=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True,timeout=30))
            expected=str(compose.resolve())
            for row in rows:
                labels=((row.get('Config') or {}).get('Labels') or {})
                files=str(labels.get('com.docker.compose.project.config_files') or '').split(',')
                if expected not in [str(x).strip() for x in files]: continue
                name=str(row.get('Name') or '').lstrip('/')
                match=re.match(r'^cloudif-p(\d+)-d(\d+)-web$',name)
                if match:
                    public_number,deploy_number=match.groups();break
    except Exception: pass
    environment=''
    if public_number and deploy_number:
        environment=f'CLOUDIF_PUBLIC_NUMBER={public_number}\nCLOUDIF_DEPLOY_NUMBER={deploy_number}'
    config={'project_name':'cloudif','file_paths':['.cloudif/docker-compose.yml'],'run_directory':'.'}
    if environment: config['environment']=environment
    update,_=komodo_call('write','UpdateStack',{'id':stack_id,'config':config})
    if not update.get('ok'):
        return {'ok':False,'error':'stack_metadata_update_failed','update':update}
    refresh,_=komodo_call('write','RefreshStackCache',{'stack':stack_id})
    if not refresh.get('ok'):
        return {'ok':False,'error':'stack_cache_refresh_failed','refresh':refresh}
    deadline=time.time()+30
    services=[]
    while time.time()<deadline:
        listed,_=komodo_call('read','ListStackServices',{'stack':stack_id})
        services=listed.get('data') if isinstance(listed.get('data'),list) else []
        if services: break
        time.sleep(2)
    return {'ok':bool(services),'changed':True,'public_number':public_number,'deploy_number':deploy_number,'services':[str(x.get('service') or x.get('service_name') or '') for x in services if isinstance(x,dict)],'error':'' if services else 'stack_services_not_discovered'}

def cloudif_project_terminal_ensure(handler):
    if not _cloudif_pub_auth(handler): return send(handler,403,{"ok":False,"error":"forbidden"})
    payload=_cloudif_pub_json(handler)
    actor=str(payload.get("actor_username") or "").strip().lower()
    actor_groups={str(x).strip() for x in (payload.get("actor_groups") or []) if str(x).strip()}
    access=payload.get("access") if isinstance(payload.get("access"),dict) else {}
    owner=str(access.get("owner") or payload.get("project_owner") or "").strip().lower()
    allowed=bool(actor and (actor==owner or actor_groups.intersection({"CloudIF-Tenants-Admin","CloudIF-Professor","Domain Admins","domain admins"})))
    for item in access.get("acl") or []:
        kind=str(item.get("type") or "").strip().lower();subject=str(item.get("subject") or "").strip()
        if kind=="user" and subject.lower()==actor: allowed=True
        if kind=="group" and subject in actor_groups: allowed=True
    if not allowed:return send(handler,403,{"ok":False,"error":"actor_not_authorized","actor":actor,"project":payload.get("project")})
    integration=find_integration(safe_slug(payload.get("project") or ""))
    if integration:
        stack_ids=_cloudif_related_stack_ids(payload.get("project"),integration)
        sync=_cloudif_sync_project_authz(payload.get("project"),owner,access.get("acl") or [],normalize_resource_id(integration.get("stack_id")),normalize_resource_id(integration.get("repo_id")),stack_ids,normalize_resource_id(integration.get("server_id")))
        if not sync.get("ok"):return send(handler,422,{"ok":False,"error":"actor_permission_sync_failed","actor":actor,"sync":sync})
    base_stack_id=normalize_resource_id((integration or {}).get("stack_id") or payload.get("stack_id"))
    metadata=_cloudif_reconcile_unified_stack_metadata(payload.get("project"),base_stack_id)
    active=_cloudif_active_publication_stack(payload.get("project"),base_stack_id)
    audit_payload=dict(payload);audit_payload["stack_id"]=active.get("stack_id") if active.get("ok") else base_stack_id
    audit=_cloudif_project_audit_data(audit_payload)
    if not audit.get("ok"): return send(handler,400,audit)
    if not audit.get("running") or not audit.get("server_id") or not audit.get("container_name"):
        return send(handler,422,{"ok":False,"error":"container_not_running","audit":audit})
    use_stack=bool(active.get("ok") and audit.get("resolved_stack_id"))
    target={"type":"Stack","params":{"stack":audit["resolved_stack_id"],"service":audit["service"]}} if use_stack else {"type":"Container","params":{"server":audit["server_id"],"container":audit["container_name"]}}
    base_terminal=audit["terminal"]; shell=audit["shell"]
    actor_key=safe_slug(actor)[:40] or "user"
    terminal=(base_terminal[:70]+"-"+actor_key)[:120]
    listed,_=komodo_call("read","ListTerminals",{"target":target})
    items=listed.get("data") if isinstance(listed.get("data"),list) else []
    existing=next((x for x in items if isinstance(x,dict) and x.get("name")==terminal),None)
    if existing and not str(existing.get("command") or "").endswith(" "+shell):
        komodo_call("write","DeleteTerminal",{"target":target,"terminal":terminal}); existing=None
    created=False
    if not existing:
        result,_=komodo_call("write","CreateTerminal",{"target":target,"name":terminal,"command":shell,"mode":"exec"})
        if not result.get("ok"): return send(handler,502,{"ok":False,"error":"terminal_create_failed","result":result,"audit":audit})
        created=True
    url=(f"https://komodoiff.duckdns.org/stacks/{audit['resolved_stack_id']}/service/{audit['service']}/terminal/{terminal}" if use_stack else f"https://komodoiff.duckdns.org/servers/{audit['server_id']}/container/{audit['container_name']}/terminal/{terminal}")
    return send(handler,200,{"ok":True,"created":created,"terminal":terminal,"target":target,"server_id":audit["server_id"],"container_name":audit["container_name"],"url":url,"actor_username":actor,"project_owner":owner,"active_publication":active,"stack_metadata":metadata,"target_mode":"stack" if use_stack else "container","audit":audit})

def cloudif_publication_deploy(handler):
    import shutil
    if not _cloudif_pub_auth(handler):
        return send(handler, 403, {"ok": False, "error": "forbidden"})
    payload = _cloudif_pub_json(handler)
    project = safe_slug(payload.get("project") or payload.get("project_slug") or payload.get("slug"))
    try:
        public_number = int(payload.get("public_number"))
        deploy_number = int(payload.get("deploy_number"))
    except Exception:
        return send(handler, 400, {"ok": False, "error": "invalid_numbers"})
    if not project or not (1 <= public_number <= 999999999 and 1 <= deploy_number <= 999999):
        return send(handler, 400, {"ok": False, "error": "invalid_payload"})
    status = _cloudif_v132_status_from_payload({"project_slug": project})
    if not status.get("ok"):
        local_base = _cloudif_v132_local_web_health(project, wait_seconds=1)
        if not local_base.get("ok"):
            return send(handler, 404, {"ok": False, "error": "base_project_not_found", "status": status, "local_base": local_base})
        status["ok"] = True
        status["local_reconciled"] = True
        status["local_base"] = local_base
    base_dir = Path(f"/etc/komodo/stacks/cloudif-{project}")
    if not (base_dir / ".git").exists():
        return send(handler, 422, {"ok": False, "error": "git_repository_missing", "base_dir": str(base_dir)})
    subprocess.run(["git","-C",str(base_dir),"fetch","--quiet","origin","main"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
    requested = str(payload.get("commit") or "").strip()
    commit = ""
    for candidate in (requested,"origin/main","HEAD"):
        if not candidate: continue
        pr=subprocess.run(["git","-C",str(base_dir),"rev-parse","--verify",candidate+"^{commit}"],text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        if pr.returncode==0:
            commit=pr.stdout.strip();break
    if len(commit)!=40:
        return send(handler, 422, {"ok": False, "error": "valid_git_commit_not_found"})
    def git_file(path):
        pr=subprocess.run(["git","-C",str(base_dir),"show",commit+":"+path],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        return pr.stdout if pr.returncode==0 else b""
    runtime_manifest={}
    try:
        runtime_manifest=json.loads(git_file(".cloudif/runtime.json").decode("utf-8","ignore") or "{}")
    except Exception:
        runtime_manifest={}
    unified_runtime=bool(runtime_manifest.get("php") and runtime_manifest.get("node"))
    compose_content=b"";compose_name=""
    for name in ("docker-compose.yml","compose.yaml","compose.yml"):
        raw=git_file(name)
        if raw.strip(): compose_content=raw;compose_name=name;break
    compose_text=compose_content.decode("utf-8","ignore")
    generated_compose=False
    if not compose_text or "cloudif-publications" not in compose_text:
        compose_text="""services:
  web:
    image: nginxinc/nginx-unprivileged:1.27-alpine
    container_name: cloudif-p${CLOUDIF_PUBLIC_NUMBER}-d${CLOUDIF_DEPLOY_NUMBER}-web
    restart: unless-stopped
    read_only: true
    user: "101:101"
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=16m
      - /var/cache/nginx:rw,noexec,nosuid,size=16m
      - /var/run:rw,noexec,nosuid,size=4m
    volumes:
      - ./site:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O- http://127.0.0.1:80/__cloudif_health >/dev/null"]
      interval: 10s
      timeout: 3s
      retries: 12
    networks: [cloudif-publications]
networks:
  cloudif-publications:
    external: true
"""
        compose_name="cloudif-generated-compose.yml";generated_compose=True
    def git_tree(prefix=""):
        cmd=["git","-C",str(base_dir),"ls-tree","-r","--name-only",commit]
        if prefix: cmd.append(prefix)
        tree=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        return [x.strip() for x in tree.stdout.splitlines() if x.strip()]
    publication_files=[]
    publication_source=""
    for prefix in ("site","dist","build","public"):
        files=[x for x in git_tree(prefix) if x.startswith(prefix+"/")]
        if files:
            publication_source=prefix
            publication_files=[(x,x[len(prefix)+1:]) for x in files]
            break
    if not publication_files and git_file("index.html").strip():
        publication_source="root"
        ignored={"README.md","docker-compose.yml","compose.yml","compose.yaml","Dockerfile","nginx.conf"}
        publication_files=[(x,x) for x in git_tree() if x not in ignored and not x.startswith(".")]
    generated_placeholder=not publication_files
    nginx_content=git_file("nginx.conf")
    generated_nginx=not bool(nginx_content.strip())
    if generated_nginx:
        nginx_content=b"""server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;
  index index.html;
  location = /__cloudif_health { access_log off; return 200 'ok'; add_header Content-Type text/plain; }
  location / { try_files $uri $uri/ /index.html; }
}
"""
    compose={"ok":True,"content":compose_text,"filename":compose_name,"source":"git_commit","commit":commit}
    snap_dir = Path(f"/srv/cloudif/publications/p{public_number}/d{deploy_number}")
    marker = snap_dir / ".cloudif-commit"
    valid_snapshot = snap_dir.is_dir() and marker.is_file() and (snap_dir / "site").is_dir() and (snap_dir / "nginx.conf").is_file()
    if valid_snapshot:
        existing_commit = marker.read_text().strip()
        if existing_commit != commit:
            return send(handler, 409, {"ok": False, "error": "immutable_deploy_conflict", "existing_commit": existing_commit, "requested_commit": commit})
    else:
        if snap_dir.exists(): shutil.rmtree(snap_dir)
        snap_dir.mkdir(parents=True, mode=0o755)
        (snap_dir / "site").mkdir(mode=0o755)
        for source_rel,dest_rel in publication_files:
            raw=git_file(source_rel);dst=snap_dir / "site" / dest_rel;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw)
        if generated_placeholder:
            import html as _html
            title=_html.escape(project.replace("-"," ").title())
            safe_project=_html.escape(project)
            safe_commit=_html.escape(commit[:12])
            placeholder=f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>body{{margin:0;font-family:system-ui,sans-serif;background:#f7f7f5;color:#171717}}main{{max-width:720px;margin:0 auto;padding:12vh 24px}}small{{letter-spacing:.08em;text-transform:uppercase;color:#666}}h1{{font-size:clamp(2rem,7vw,4rem);line-height:1;margin:.4em 0}}p{{font-size:1.05rem;line-height:1.6;color:#555}}code{{font-size:.85rem}}</style></head><body><main><small>CloudIFF · pré-publicação</small><h1>{title}</h1><p>Este projeto já possui um endereço público, mas ainda não contém arquivos web. A próxima publicação substituirá esta página pelo site do projeto.</p><p><code>{safe_project} · {safe_commit}</code></p></main></body></html>"""
            (snap_dir / "site" / "index.html").write_text(placeholder,encoding="utf-8")
        (snap_dir / "nginx.conf").write_bytes(nginx_content)
        marker.write_text(commit + "\n");marker.chmod(0o640)
        for fp in (snap_dir / "site").rglob("*"):
            if fp.is_dir(): fp.chmod(0o755)
            elif fp.is_file(): fp.chmod(0o644)
        snap_dir.chmod(0o755);(snap_dir / "site").chmod(0o755)
        (snap_dir / "nginx.conf").chmod(0o644)
    if unified_runtime:
        php=str(runtime_manifest.get("php") or "").strip()
        node=str(runtime_manifest.get("node") or "").strip()
        runtime_dockerfile=f"""FROM cloudif/project-{public_number}:php{php}-node{node}
RUN find /var/www/html -mindepth 1 -maxdepth 1 ! -name api -exec rm -rf {{}} + \
 && if [ -d /var/www/html/api ]; then find /var/www/html/api -mindepth 1 -maxdepth 1 ! -name node_modules -exec rm -rf {{}} +; fi
COPY --chown=www-data:www-data site/ /var/www/html/
"""
        (snap_dir / "Dockerfile.runtime").write_text(runtime_dockerfile,encoding="utf-8")
        (snap_dir / "Dockerfile.runtime").chmod(0o644)
    import hashlib
    digest=hashlib.sha256()
    for fp in sorted((snap_dir / "site").rglob("*")):
        if fp.is_file(): digest.update(str(fp.relative_to(snap_dir)).encode()+b"\0"+fp.read_bytes()+b"\0")
    digest.update(b"nginx.conf\0"+(snap_dir / "nginx.conf").read_bytes())
    content_digest=digest.hexdigest()
    prior=[]
    root=Path(f"/srv/cloudif/publications/p{public_number}")
    for d in root.glob("d*"):
        if d==snap_dir or not d.is_dir(): continue
        try:n=int(d.name[1:])
        except Exception:continue
        if n>=deploy_number:continue
        dm=d/".cloudif-content-sha256"
        if dm.is_file() and dm.read_text().strip()==content_digest:prior.append(n)
    (snap_dir / ".cloudif-content-sha256").write_text(content_digest+"\n")
    republished_from=max(prior) if prior else None
    if republished_from is not None:
        (snap_dir / ".cloudif-republished-from").write_text(str(republished_from)+"\n")
    if unified_runtime:
        php=str(runtime_manifest.get("php") or "").strip()
        node=str(runtime_manifest.get("node") or "").strip()
        compose["content"]=f"""services:
  web:
    image: cloudif/publication-p{public_number}-d{deploy_number}:php{php}-node{node}
    build:
      context: .
      dockerfile: Dockerfile.runtime
    container_name: cloudif-p${{CLOUDIF_PUBLIC_NUMBER}}-d${{CLOUDIF_DEPLOY_NUMBER}}-web
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1/.cloudif-health >/dev/null"]
      interval: 15s
      timeout: 5s
      retries: 12
      start_period: 30s
    networks: [cloudif-publications]
networks:
  cloudif-publications:
    external: true
"""
        compose["filename"]="cloudif-generated-unified-compose.yml"
        compose["runtime"]="unified-php-node"
    content = _cloudif_pub_transform_compose(compose.get("content"), public_number, deploy_number)
    content = content.replace("./site:/usr/share/nginx/html:ro", f"{snap_dir}/site:/usr/share/nginx/html:ro")
    content = content.replace("./site:/var/www/html:ro", f"{snap_dir}/site:/var/www/html:ro")
    content = content.replace("./nginx.conf:/etc/nginx/conf.d/default.conf:ro", f"{snap_dir}/nginx.conf:/etc/nginx/conf.d/default.conf:ro")
    if "cloudif-publications" not in content:
        return send(handler, 422, {"ok": False, "error": "publication_network_missing"})
    base_stack, base_stack_id, _ = _cloudif_v131_get_stack(project=project)
    if not base_stack:
        stacks_result = _cloudif_v131_core_call("read", "ListStacks", {})
        expected_names = {project, f"cloudif-{project}"}
        expected_repo_suffix = "/cloudif-" + project
        base_stack = next((item for item in _cloudif_v131_list_items(stacks_result.get("data"))
                           if isinstance(item, dict) and (
                               item.get("name") in expected_names
                               or str(((item.get("info") or {}).get("repo") or "")).endswith(expected_repo_suffix)
                               or str(((item.get("config") or {}).get("repo") or "")).endswith(expected_repo_suffix)
                           )), {})
        base_stack_id = _cloudif_v131_oid(base_stack)
    server_id = ((base_stack.get("info") or {}).get("server_id") or (base_stack.get("config") or {}).get("server_id") or "")
    if not server_id:
        servers_result = _cloudif_v131_core_call("read", "ListServers", {})
        servers = [item for item in _cloudif_v131_list_items(servers_result.get("data")) if isinstance(item, dict)]
        preferred = next((item for item in servers if item.get("name") == "Local"), None)
        if preferred is None:
            preferred = next((item for item in servers if (item.get("info") or {}).get("state") == "Ok"), None)
        server_id = _cloudif_v131_oid(preferred or {})
    if not server_id:
        return send(handler, 422, {"ok": False, "error": "server_id_missing"})
    name = f"cloudif-p{public_number}-d{deploy_number}"
    stacks = _cloudif_v131_core_call("read", "ListStacks", {}).get("data") or []
    existing = next((x for x in _cloudif_v131_list_items(stacks) if isinstance(x, dict) and x.get("name") == name), None)
    cfg = {
        "server_id": server_id,
        "files_on_host": False,
        "run_build": bool(unified_runtime),
        "auto_pull": not bool(unified_runtime),
        "file_contents": content,
        "file_paths": [],
        "linked_repo": "",
        "repo": "",
        "branch": "",
        "commit": commit,
        "git_provider": "",
        "git_https": True,
        "run_directory": ".",
        "webhook_enabled": False,
        "reclone": False,
    }
    if existing:
        stack_id = _cloudif_v131_oid(existing)
        created = False
        update = _cloudif_v131_core_call("write", "UpdateStack", {"id": stack_id, "config": cfg}, timeout=60)
    else:
        cr = _cloudif_v131_core_call("write", "CreateStack", {"name": name, "config": cfg}, timeout=60)
        if not cr.get("ok"):
            return send(handler, 422, {"ok": False, "error": "create_stack_failed", "create": cr})
        data = cr.get("data") or {}
        stack_id = _cloudif_v131_oid(data)
        if not stack_id:
            # Resolve by name after creation.
            time.sleep(2)
            stacks2 = _cloudif_v131_core_call("read", "ListStacks", {}).get("data") or []
            item = next((x for x in _cloudif_v131_list_items(stacks2) if isinstance(x, dict) and x.get("name") == name), None)
            stack_id = _cloudif_v131_oid(item or {})
        created = True
        update = {"ok": True, "created": cr}
    if not stack_id:
        return send(handler, 422, {"ok": False, "error": "stack_id_missing"})
    if unified_runtime:
        version_stack_dir=Path("/etc/komodo/stacks") / name
        staged_site=version_stack_dir / "site"
        try:
            version_stack_dir.mkdir(parents=True,exist_ok=True)
            if staged_site.exists(): shutil.rmtree(staged_site)
            shutil.copytree(snap_dir / "site",staged_site)
            shutil.copy2(snap_dir / "Dockerfile.runtime",version_stack_dir / "Dockerfile.runtime")
        except Exception as exc:
            return send(handler,422,{"ok":False,"error":"version_runtime_stage_failed","detail":str(exc)[:500],"stack_dir":str(version_stack_dir)})
    dep = _cloudif_v131_core_call("execute", "DeployStack", {"stack": stack_id}, timeout=60)
    opid = _cloudif_v131_oid(dep.get("data") or {})
    container = f"cloudif-p{public_number}-d{deploy_number}-web"
    expected_image = f"cloudif/publication-p{public_number}-d{deploy_number}:php{runtime_manifest.get('php')}-node{runtime_manifest.get('node')}" if unified_runtime else "nginxinc/nginx-unprivileged:1.27-alpine"
    healthy = False
    actual_image = ""
    final = {}
    timeout_s = int(payload.get("timeout") or 300)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        pr = subprocess.run(["docker", "inspect", container, "--format", "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}|{{.Config.Image}}"], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        parts=pr.stdout.strip().split("|",2) if pr.returncode==0 else []
        actual_image=parts[2] if len(parts)==3 else ""
        healthy = len(parts)==3 and parts[0]=="running" and parts[1]=="healthy" and actual_image==expected_image
        if opid:
            try:
                updates = komodo_query_updates([opid])
                final = updates.get(opid) if isinstance(updates, dict) else {}
            except Exception:
                final = {}
        operation_complete = (not opid) or bool(final and str(final.get("status") or "").lower()=="complete" and final.get("success") is True)
        if healthy and operation_complete:
            break
        if final and final.get("success") is False:
            break
        time.sleep(4)
    operation_complete = (not opid) or bool(final and str(final.get("status") or "").lower()=="complete" and final.get("success") is True)
    terminal = _cloudif_ensure_container_terminal(server_id, container) if healthy and operation_complete else {"ok": False, "created": False, "error": "container_or_operation_not_ready"}
    ok = bool(update.get("ok") and dep.get("ok") and healthy and operation_complete and terminal.get("ok"))
    return send(handler, 200 if ok else 422, {
        "ok": ok, "project": project, "public_number": public_number, "deploy_number": deploy_number,
        "commit": commit, "stack_id": stack_id, "stack_name": name, "container": container,
        "created": created, "deploy": dep, "operation_id": opid, "operation_final": final, "healthy": healthy,
        "terminal": terminal, "expected_image": expected_image, "actual_image": actual_image,
        "content_digest": content_digest, "source": "git_commit", "generated_compose": generated_compose,
        "publication_source": publication_source or "generated_placeholder", "generated_placeholder": generated_placeholder, "generated_nginx": generated_nginx,
        "republished": republished_from is not None, "republished_from": republished_from
    })

def cloudif_publication_promote(handler):
    if not _cloudif_pub_auth(handler):
        return send(handler, 403, {"ok": False, "error": "forbidden"})
    payload = _cloudif_pub_json(handler)
    try:
        public_number = int(payload.get("public_number")); deploy_number = int(payload.get("deploy_number"))
    except Exception:
        return send(handler, 400, {"ok": False, "error": "invalid_numbers"})
    target = f"cloudif-p{public_number}-d{deploy_number}-web"
    network = "cloudif-publications"
    chk = subprocess.run(["docker", "inspect", target, "--format", "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}"], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if chk.returncode or chk.stdout.strip() != "running|healthy":
        return send(handler, 422, {"ok": False, "error": "target_not_healthy", "target": target})
    active_alias = f"cloudif-p{public_number}-active-web"
    previous = ""
    names = subprocess.check_output(["docker", "ps", "-a", "--format", "{{.Names}}"], text=True).splitlines()
    candidates = [n for n in names if re.match(rf"^cloudif-p{public_number}-d\d+-web$", n)]
    def aliases(name):
        try:
            raw = subprocess.check_output(["docker", "inspect", name, "--format", "{{json (index .NetworkSettings.Networks \"cloudif-publications\").Aliases}}"], text=True).strip()
            return json.loads(raw) if raw and raw != "null" else []
        except Exception:
            return []
    for name in candidates:
        if active_alias in aliases(name):
            previous = name
            break
    def reconnect(name, active=False):
        m = re.match(rf"cloudif-p{public_number}-d(\d+)-web$", name)
        if not m: return
        depn = m.group(1)
        subprocess.run(["docker", "network", "disconnect", network, name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cmd=["docker", "network", "connect", "--alias", f"cloudif-p{public_number}-d{depn}-web"]
        if active: cmd += ["--alias", active_alias]
        cmd += [network, name]
        subprocess.check_call(cmd)
    try:
        for name in candidates:
            if name != target:
                reconnect(name, False)
        reconnect(target, True)
        deadline=time.time()+10
        while time.time()<deadline and active_alias not in aliases(target):
            time.sleep(1)
        if active_alias not in aliases(target):
            raise RuntimeError("active_alias_not_applied")
    except Exception as e:
        if previous:
            try: reconnect(previous, True)
            except Exception: pass
        return send(handler, 422, {"ok": False, "error": "promotion_failed", "detail": str(e), "previous": previous})
    return send(handler, 200, {"ok": True, "public_number": public_number, "deploy_number": deploy_number, "target": target, "previous": previous, "active_alias": active_alias, "aliases": aliases(target)})


def cloudif_container_telemetry(handler):
    if not _cloudif_pub_auth(handler):
        return send(handler, 403, {"ok": False, "error": "forbidden"})
    parsed = urllib.parse.urlparse(handler.path)
    qs = urllib.parse.parse_qs(parsed.query)
    prefix = str(qs.get("prefix", ["cloudif-"])[0] or "cloudif-")
    if not re.match(r"^[a-zA-Z0-9_.-]{1,80}$", prefix):
        return send(handler, 400, {"ok": False, "error": "invalid_prefix"})
    try:
        raw = subprocess.check_output([
            "docker","stats","--no-stream","--format","{{json .}}"
        ], text=True, stderr=subprocess.DEVNULL, timeout=30)
    except Exception as exc:
        return send(handler, 502, {"ok": False, "error": "docker_stats_failed", "detail": str(exc)[:180]})
    stats = {}
    for line in raw.splitlines():
        try:
            row=json.loads(line); name=row.get("Name") or row.get("Container") or ""
            if name: stats[name]=row
        except Exception: pass
    names=subprocess.check_output(["docker","ps","-a","--format","{{.Names}}"],text=True).splitlines()
    items=[]
    for name in sorted(n for n in names if n.startswith(prefix)):
        try:
            info=json.loads(subprocess.check_output(["docker","inspect",name],text=True,timeout=20))[0]
        except Exception:
            continue
        state=info.get("State") or {}; cfg=info.get("Config") or {}; net=info.get("NetworkSettings") or {}
        health=((state.get("Health") or {}).get("Status") or "")
        ports=[]
        for key,vals in (net.get("Ports") or {}).items():
            if vals:
                for v in vals: ports.append({"container":key,"host_ip":v.get("HostIp") or "","host_port":v.get("HostPort") or ""})
            else: ports.append({"container":key,"host_ip":"","host_port":""})
        aliases=[]
        for ndata in (net.get("Networks") or {}).values(): aliases.extend(ndata.get("Aliases") or [])
        st=stats.get(name) or {}
        m=re.match(r"^cloudif-p(\d+)-d(\d+)-web$",name)
        urls=[]
        if m:
            num,dep=m.groups(); urls=[f"https://{num}-d{dep}.cloudiff.duckdns.org/"]
            if f"cloudif-p{num}-active-web" in aliases: urls.insert(0,f"https://{num}.cloudiff.duckdns.org/")
        items.append({
          "name":name,"image":cfg.get("Image") or "","status":state.get("Status") or "unknown",
          "health":health or ("running" if state.get("Running") else "stopped"),
          "started_at":state.get("StartedAt") or "","finished_at":state.get("FinishedAt") or "",
          "cpu":st.get("CPUPerc") or "0.00%","memory":st.get("MemUsage") or "-",
          "memory_percent":st.get("MemPerc") or "0.00%","network_io":st.get("NetIO") or "-",
          "block_io":st.get("BlockIO") or "-","pids":st.get("PIDs") or "0",
          "ports":ports,"aliases":sorted(set(a for a in aliases if a)),"urls":urls
        })
    return send(handler,200,{"ok":True,"generated_at":now(),"items":items})

# CloudIF versioned publications END

class H(BaseHTTPRequestHandler):
    def parse_json(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode("utf-8", "ignore")
        if not raw:
            return {}
        return json.loads(raw)

    def do_GET(self):

        _cloudif_v132_get_path = self.path.split("?", 1)[0]
        if _cloudif_v132_get_path in ["/komodo/project/status", "/komodo/status"]:
            return cloudif_v132_project_status(self)

        # CloudIF v51 rollback routes
        if self.path.startswith("/komodo/project/commits"):
            return v51_handle_commits(self)

        env = load_env()

        if self.path.split("?",1)[0] == "/komodo/containers/telemetry":
            return cloudif_container_telemetry(self)

        if self.path in ["/", "/health"]:
            auth = check_master_auth()
            return send(self, 200, {
                "ok": True,
                "service": "cloudif-komodo-agent-v42",
                "time": now(),
                "bind": f"{env.get('KOMODO_AGENT_HOST','10.62.91.2')}:{env.get('KOMODO_AGENT_PORT','18098')}",
                "komodo_core_url": env.get("KOMODO_CORE_URL", ""),
                "auth_method_config": env.get("KOMODO_AUTH_METHOD", ""),
                "master_auth_ok": bool(auth.get("ok")),
                "master_method": auth.get("method", ""),
                "master_message": auth.get("message", ""),
            })

        if self.path == "/auth/test":
            auth = check_master_auth()
            return send(self, 200 if auth.get("ok") else 422, auth)

        if self.path == "/status":
            stacks, method = komodo_call("read", "ListStacks", {})
            servers, _ = komodo_call("read", "ListServers", {})
            repos, _ = komodo_call("read", "ListRepos", {})
            return send(self, 200 if stacks.get("ok") and servers.get("ok") else 502, {
                "ok": bool(stacks.get("ok") and servers.get("ok")),
                "method": method,
                "stacks": {"ok": stacks.get("ok"), "status": stacks.get("status"), "count": len(stacks.get("data") or []) if isinstance(stacks.get("data"), list) else None, "data": stacks.get("data")},
                "servers": {"ok": servers.get("ok"), "status": servers.get("status"), "count": len(servers.get("data") or []) if isinstance(servers.get("data"), list) else None, "data": servers.get("data")},
                "repos": {"ok": repos.get("ok"), "status": repos.get("status"), "count": len(repos.get("data") or []) if isinstance(repos.get("data"), list) else None, "data": repos.get("data")},
            })

        if self.path.startswith("/komodo/project/status"):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            project = safe_slug(qs.get("project", [""])[0])
            if project:
                rows = db_query("select * from integrations where project=?", (project,))
            else:
                rows = db_query("select * from integrations order by updated_at desc")
            return send(self, 200, {"ok": True, "items": rows})

        if self.path.startswith("/komodo/deployments"):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            project = safe_slug(qs.get("project", [""])[0])
            if project:
                rows = db_query("select * from deployments where project=? order by id desc limit 100", (project,))
            else:
                rows = db_query("select * from deployments order by id desc limit 100")
            rows = enrich_deployment_rows(rows)
            return send(self, 200, {"ok": True, "items": rows})

        return send(self, 404, {"ok": False, "error": "not_found", "path": self.path})

    def do_POST(self):

        _cloudif_http_smoke_path = self.path.split("?", 1)[0]
        if _cloudif_http_smoke_path == "/komodo/stack/http-smoke":
            return cloudif_stack_http_smoke(self)

        _cloudif_pub_path = self.path.split("?", 1)[0]
        if _cloudif_pub_path == "/komodo/project/runtime-inspect":
            return cloudif_project_runtime_inspect(self)
        if _cloudif_pub_path == "/komodo/project/audit":
            return cloudif_project_audit(self)
        if _cloudif_pub_path == "/komodo/project/runtime-info":
            return cloudif_project_runtime_info(self)
        if _cloudif_pub_path == "/komodo/project/authz-sync":
            return cloudif_project_authz_sync(self)
        if _cloudif_pub_path == "/komodo/project/membership/reconcile":
            return cloudif_project_membership_reconcile(self)
        if _cloudif_pub_path == "/komodo/project/repair":
            return cloudif_project_repair(self)
        if _cloudif_pub_path == "/komodo/project/terminal/ensure":
            return cloudif_project_terminal_ensure(self)
        if _cloudif_pub_path == "/komodo/publication/deploy":
            return cloudif_publication_deploy(self)
        if _cloudif_pub_path == "/komodo/publication/promote":
            return cloudif_publication_promote(self)

        _cloudif_v132_path = self.path.split("?", 1)[0]
        if _cloudif_v132_path in ["/komodo/project/status", "/komodo/status"]:
            return cloudif_v132_project_status(self)


        _cloudif_v131_path = self.path.split("?", 1)[0]
        if _cloudif_v131_path in ["/komodo/project/deploy-full", "/komodo/project/deploy_full", "/komodo/deploy-full"]:
            return cloudif_v132_project_deploy_full(self)
        if _cloudif_v131_path == "/komodo/stack/pull":
            return cloudif_v131_stack_action(self, "pull")
        if _cloudif_v131_path == "/komodo/stack/deploy":
            return cloudif_v131_stack_action(self, "deploy")


        _cloudif_v117_path = self.path.split("?", 1)[0]
        if _cloudif_v117_path in ["/komodo/project/rollback", "/project/rollback", "/komodo/rollback"]:
            return cloudif_v117_komodo_project_rollback(self)

        # CloudIF v53c routes
        if self.path.startswith("/komodo/stack/rollback-filecontents"):
            return v53c_handle_rollback_filecontents(self)
        if self.path.startswith("/komodo/stack/return-git-main"):
            return v53c_handle_return_git_main(self)

        # CloudIF v52 rollback branch routes
        if self.path.startswith("/komodo/stack/rollback-branch"):
            return v52_handle_rollback_branch(self)
        if self.path.startswith("/komodo/stack/return-main"):
            return v52_handle_return_main(self)

        # CloudIF v51 rollback routes
        if self.path.startswith("/komodo/stack/rollback-commit"):
            return v51_handle_rollback_commit(self)

        try:
            payload = self.parse_json()
        except Exception as e:
            return send(self, 400, {"ok": False, "error": "invalid_json", "detail": str(e)})

        if self.path in ["/komodo/project/ensure", "/project/ensure", "/komodo/ensure"]:
            result = ensure_project(payload)
            return send(self, 200 if result.get("ok") else 422, result)

        if self.path in [
            "/komodo/stack/deploy",
            "/komodo/stack/deploy-if-changed",
            "/komodo/stack/pull",
            "/komodo/stack/start",
            "/komodo/stack/stop",
            "/komodo/stack/restart",
            "/komodo/stack/destroy",
            "/komodo/stack/rollback"
        ]:
            action = self.path.rstrip("/").split("/")[-1]
            result = stack_action(action, payload)
            return send(self, 200 if result.get("ok") else 422, result)

        return send(self, 404, {"ok": False, "error": "not_found", "path": self.path})

    def log_message(self, fmt, *args):
        print(time.strftime("[%Y-%m-%dT%H:%M:%S]"), self.client_address[0], fmt % args, flush=True)

# CloudIFF v143 — código na raiz, runtime fora do Git e membros reconciliados

def _cloudif_v143_ensure_schema():
    init_db()
    con=sqlite3.connect(DB_PATH)
    cols={r[1] for r in con.execute('pragma table_info(integrations)')}
    for name,kind in (
        ('public_number','integer not null default 0'),
        ('active_deploy','integer not null default 0'),
        ('runtime_template','text not null default \'node22\''),
        ('php_version','text not null default \'8.3\''),
    ):
        if name not in cols:
            con.execute(f'alter table integrations add column {name} {kind}')
    terminal_cols={r[1] for r in con.execute('pragma table_info(project_member_terminals)')}
    if terminal_cols and 'stack_id' not in terminal_cols:
        con.execute('drop table project_member_terminals')
    con.executescript('''
    create table if not exists publication_runtimes(
      project text not null,public_number integer not null,deploy_number integer not null,
      stack_id text not null default '',stack_name text not null default '',container text not null default '',
      commit_sha text not null default '',status text not null default '',is_active integer not null default 0,
      updated_at text not null,primary key(project,deploy_number));
    create table if not exists project_member_terminals(
      project text not null,username text not null,stack_id text not null,
      terminal text not null,target_json text not null,updated_at text not null,
      primary key(project,username,stack_id));
    ''')
    con.commit();con.close()


def _cloudif_v143_runtime_settings(project):
    project=safe_slug(project)
    state={}
    try:
        state=json.loads((PROJECT_STATE/(project+'.json')).read_text(encoding='utf-8'))
    except Exception:
        state={}
    runtime=state.get('runtime') if isinstance(state.get('runtime'),dict) else {}
    template=str(runtime.get('runtime_template') or state.get('runtime_template') or 'node22').strip().lower()
    php=str(runtime.get('php_version') or state.get('php_version') or '8.3').strip()
    if template not in {'node20','node22','node24'}:template='node22'
    if php not in {'8.2','8.3','8.4'}:php='8.3'
    return {'layout':'managed-root-v1','runtime_template':template,'node':template.replace('node',''),'php':php}


def _cloudif_v143_base_files(php,node):
    apache='''<VirtualHost *:80>
  DocumentRoot /var/www/html
  DirectoryIndex index.php index.html
  <Directory /var/www/html>
    AllowOverride All
    Options FollowSymLinks
    Require all granted
  </Directory>
  Alias /.cloudif-health /opt/cloudif/health.php
  <Location /.cloudif-health>
    Require all granted
  </Location>
  ProxyPreserveHost On
  ProxyPass /api/ http://127.0.0.1:3000/
  ProxyPassReverse /api/ http://127.0.0.1:3000/
  SetEnvIf X-Forwarded-Proto https HTTPS=on
  ErrorLog ${APACHE_LOG_DIR}/error.log
  CustomLog ${APACHE_LOG_DIR}/access.log combined
</VirtualHost>
'''
    supervisor='''[supervisord]
nodaemon=true
user=root

[program:apache]
command=/usr/sbin/apache2ctl -D FOREGROUND
autostart=true
autorestart=true
priority=10
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
stderr_logfile=/dev/fd/2
stderr_logfile_maxbytes=0

[program:node]
command=/usr/local/bin/cloudif-node-runner
autostart=true
autorestart=true
startsecs=2
priority=20
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
stderr_logfile=/dev/fd/2
stderr_logfile_maxbytes=0
'''
    runner='''#!/bin/sh
set -eu
cd /var/www/html
if [ -f api/server.js ]; then
  cd api
  export HOST=127.0.0.1 PORT=3000 NODE_ENV=${NODE_ENV:-production}
  exec node server.js
fi
exec sh -c 'while :; do sleep 3600; done'
'''
    dockerfile=f'''FROM php:{php}-apache
ARG NODE_MAJOR={node}
RUN apt-get update \\
 && apt-get install -y --no-install-recommends ca-certificates curl gnupg supervisor libpq-dev libpng-dev libjpeg62-turbo-dev libfreetype6-dev libzip-dev libicu-dev default-mysql-client postgresql-client unzip git \\
 && curl -fsSL https://deb.nodesource.com/setup_${{NODE_MAJOR}}.x | bash - \\
 && apt-get install -y --no-install-recommends nodejs \\
 && docker-php-ext-configure gd --with-freetype --with-jpeg \\
 && docker-php-ext-install -j"$(nproc)" pdo pdo_mysql mysqli pdo_pgsql pgsql gd intl zip opcache \\
 && a2enmod rewrite headers proxy proxy_http expires \\
 && rm -rf /var/lib/apt/lists/*
COPY apache-vhost.conf /etc/apache2/sites-available/000-default.conf
COPY supervisor.conf /etc/supervisor/conf.d/cloudif.conf
COPY node-runner.sh /usr/local/bin/cloudif-node-runner
COPY health.php /opt/cloudif/health.php
RUN chmod 0755 /usr/local/bin/cloudif-node-runner
EXPOSE 80
CMD ["/usr/bin/supervisord","-n","-c","/etc/supervisor/supervisord.conf"]
'''
    health="<?php header('Content-Type: application/json'); echo json_encode(['ok'=>true,'php'=>PHP_VERSION]);"
    return {'Dockerfile':dockerfile,'apache-vhost.conf':apache,'supervisor.conf':supervisor,'node-runner.sh':runner,'health.php':health}


def _cloudif_v143_ensure_base_image(php,node,no_cache=False):
    tag=f'cloudif/runtime-apache-php{php}-node{node}:v2'
    inspect=subprocess.run(['docker','image','inspect',tag],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if inspect.returncode==0 and not no_cache:
        return {'ok':True,'image':tag,'created':False}
    root=BASE_STATE/'runtime-bases'/f'php{php}-node{node}'
    root.mkdir(parents=True,exist_ok=True)
    for name,content in _cloudif_v143_base_files(php,node).items():
        path=root/name;path.write_text(content,encoding='utf-8');path.chmod(0o755 if name=='node-runner.sh' else 0o644)
    cmd=['docker','build','-t',tag]
    if no_cache:cmd.append('--no-cache')
    cmd.append(str(root))
    proc=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=2400)
    return {'ok':proc.returncode==0,'image':tag,'created':proc.returncode==0,'returncode':proc.returncode,'detail':(proc.stderr or proc.stdout)[-1600:]}


def _cloudif_v143_ensure_checkout(project,base_dir):
    project=safe_slug(project);base_dir=Path(base_dir)
    if (base_dir/'.git').is_dir():
        return {'ok':True,'created':False,'base_dir':str(base_dir)}
    integration=find_integration(project) or {}
    repo,repo_id,repo_attempts=_cloudif_v131_get_repo(str(integration.get('repo_id') or ''),project)
    stack,stack_id,stack_attempts=_cloudif_v131_get_stack(str(integration.get('stack_id') or ''),project)
    actions=[]
    if repo_id:
        clone=_cloudif_v131_core_call('execute','CloneRepo',{'repo':repo_id},timeout=60);actions.append({'operation':'CloneRepo','result':clone})
        opid=_cloudif_v131_oid(clone.get('data') or {})
        if opid:actions[-1]['final']=_cloudif_pub_wait_operation(opid,timeout=180)
    if stack_id:
        pull=_cloudif_v131_core_call('execute','PullStack',{'stack':stack_id},timeout=60);actions.append({'operation':'PullStack','result':pull})
        opid=_cloudif_v131_oid(pull.get('data') or {})
        if opid:actions[-1]['final']=_cloudif_pub_wait_operation(opid,timeout=180)
    deadline=time.time()+180
    while time.time()<deadline:
        if (base_dir/'.git').is_dir():
            return {'ok':True,'created':True,'base_dir':str(base_dir),'repo_id':repo_id,'stack_id':stack_id,'actions':actions}
        time.sleep(3)
    return {'ok':False,'error':'git_repository_missing_after_reconcile','base_dir':str(base_dir),'repo_id':repo_id,'stack_id':stack_id,'repo_attempts':repo_attempts[-3:],'stack_attempts':stack_attempts[-3:],'actions':actions}


def _cloudif_v143_git_files(base_dir,commit):
    tree=subprocess.run(['git','-C',str(base_dir),'ls-tree','-r','--name-only',commit],text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    names=[x.strip() for x in tree.stdout.splitlines() if x.strip()]
    site=[x for x in names if x.startswith('site/')]
    if site:
        return [(x,x[5:]) for x in site if x[5:]] ,'site'
    blocked={'README.md','docker-compose.yml','docker-compose.yaml','compose.yml','compose.yaml','Dockerfile','Dockerfile.runtime','nginx.conf','.env'}
    out=[]
    for name in names:
        if name in blocked or name.startswith('.cloudif/') or name.startswith('.git'):
            continue
        if '/.git' in name or name.startswith('../') or '/..' in name:
            continue
        out.append((name,name))
    return out,'root'


def _cloudif_v143_git_blob(base_dir,commit,path):
    proc=subprocess.run(['git','-C',str(base_dir),'show',commit+':'+path],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    return proc.stdout if proc.returncode==0 else b''


def _cloudif_v143_related_stack_ids(project,integration=None):
    _cloudif_v143_ensure_schema()
    project=safe_slug(project);integration=integration or find_integration(project) or {}
    ids=[]
    base=normalize_resource_id(integration.get('stack_id'))
    if base:ids.append(base)
    number=int(integration.get('public_number') or 0)
    listed,_=komodo_call('read','ListStacks',{})
    stacks=listed.get('data') if isinstance(listed.get('data'),list) else []
    pattern=re.compile(rf'^cloudif-p{number}-d\d+$') if number else None
    for item in stacks:
        if not isinstance(item,dict):continue
        name=str(item.get('name') or '')
        if pattern and pattern.match(name):
            rid=normalize_resource_id(item.get('_id') or item.get('id'))
            if rid and rid not in ids:ids.append(rid)
    tenant=str(integration.get('tenant') or '').strip()
    if tenant:
        wanted='cloudif-tenant-'+tenant
        for item in stacks:
            if isinstance(item,dict) and str(item.get('name') or '')==wanted:
                rid=normalize_resource_id(item.get('_id') or item.get('id'))
                if rid and rid not in ids:ids.append(rid)
    return ids

_cloudif_related_stack_ids=_cloudif_v143_related_stack_ids


def _cloudif_active_publication_stack(project,fallback_stack_id=''):
    _cloudif_v143_ensure_schema()
    project=safe_slug(project);fallback_stack_id=normalize_resource_id(fallback_stack_id)
    integration=find_integration(project) or {}
    number=int(integration.get('public_number') or 0);deploy=int(integration.get('active_deploy') or 0)
    if not number or not deploy:
        return {'ok':False,'stack_id':fallback_stack_id,'reason':'active_version_not_bound'}
    name=f'cloudif-p{number}-d{deploy}'
    rows=db_query('select * from publication_runtimes where project=? and deploy_number=?',(project,deploy))
    if rows:
        row=rows[0]
        return {'ok':bool(row.get('stack_id')),'stack_id':normalize_resource_id(row.get('stack_id')) or fallback_stack_id,'stack_name':row.get('stack_name') or name,'container':row.get('container') or name+'-web','public_number':number,'deploy_number':deploy}
    listed,_=komodo_call('read','ListStacks',{})
    stacks=listed.get('data') if isinstance(listed.get('data'),list) else []
    item=next((x for x in stacks if isinstance(x,dict) and str(x.get('name') or '')==name),None)
    sid=normalize_resource_id((item or {}).get('_id') or (item or {}).get('id'))
    return {'ok':bool(sid),'stack_id':sid or fallback_stack_id,'stack_name':name,'container':name+'-web','public_number':number,'deploy_number':deploy}


def cloudif_publication_deploy(handler):
    if not _cloudif_pub_auth(handler):
        return send(handler,403,{'ok':False,'error':'forbidden'})
    payload=_cloudif_pub_json(handler)
    project=safe_slug(payload.get('project') or payload.get('project_slug') or payload.get('slug'))
    try:
        public_number=int(payload.get('public_number'));deploy_number=int(payload.get('deploy_number'))
    except Exception:
        return send(handler,400,{'ok':False,'error':'invalid_numbers'})
    if not project or public_number<1 or deploy_number<1:
        return send(handler,400,{'ok':False,'error':'invalid_payload'})
    _cloudif_v143_ensure_schema()
    base_dir=Path('/etc/komodo/stacks')/('cloudif-'+project)
    checkout=_cloudif_v143_ensure_checkout(project,base_dir)
    if not checkout.get('ok'):
        return send(handler,422,checkout)
    subprocess.run(['git','-C',str(base_dir),'fetch','--quiet','origin','main'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=90)
    requested=str(payload.get('commit') or '').strip();commit=''
    for candidate in (requested,'origin/main','HEAD'):
        if not candidate:continue
        proc=subprocess.run(['git','-C',str(base_dir),'rev-parse','--verify',candidate+'^{commit}'],text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        if proc.returncode==0:commit=proc.stdout.strip();break
    if len(commit)!=40:
        return send(handler,422,{'ok':False,'error':'valid_git_commit_not_found'})
    runtime=_cloudif_v143_runtime_settings(project);php=runtime['php'];node=runtime['node']
    base=_cloudif_v143_ensure_base_image(php,node,bool(payload.get('rebuild_runtime_base')))
    if not base.get('ok'):
        return send(handler,422,{'ok':False,'error':'runtime_base_build_failed','base':base})
    files,source_kind=_cloudif_v143_git_files(base_dir,commit)
    snap=Path(f'/srv/cloudif/publications/p{public_number}/d{deploy_number}')
    marker=snap/'.cloudif-commit'
    if marker.is_file() and marker.read_text().strip()!=commit:
        return send(handler,409,{'ok':False,'error':'immutable_deploy_conflict','existing_commit':marker.read_text().strip(),'requested_commit':commit})
    if not marker.is_file():
        if snap.exists():shutil.rmtree(snap)
        source=snap/'source';source.mkdir(parents=True,exist_ok=True)
        for src,dst in files:
            target=source/dst;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(_cloudif_v143_git_blob(base_dir,commit,src))
        if not files:
            (source/'index.php').write_text("<?php echo '<h1>CloudIFF</h1><p>Projeto sem código publicado.</p>';",encoding='utf-8')
        marker.write_text(commit+'\n');marker.chmod(0o640)
    source=snap/'source'
    dockerfile=f'''FROM {base['image']}
COPY --chown=www-data:www-data source/ /var/www/html/
WORKDIR /var/www/html
RUN if [ -f api/package-lock.json ]; then cd api && npm ci --omit=dev; elif [ -f api/package.json ]; then cd api && npm install --omit=dev; fi \\
 && chown -R www-data:www-data /var/www/html
'''
    (snap/'Dockerfile.runtime').write_text(dockerfile,encoding='utf-8')
    image=f'cloudif/publication-p{public_number}-d{deploy_number}:php{php}-node{node}'
    compose=f'''services:
  web:
    image: {image}
    build:
      context: .
      dockerfile: Dockerfile.runtime
    container_name: cloudif-p{public_number}-d{deploy_number}-web
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1/.cloudif-health >/dev/null"]
      interval: 15s
      timeout: 5s
      retries: 12
      start_period: 30s
    networks: [cloudif-publications]
networks:
  cloudif-publications:
    external: true
'''
    digest=hashlib.sha256()
    for path in sorted(source.rglob('*')):
        if path.is_file():digest.update(str(path.relative_to(source)).encode()+b'\0'+path.read_bytes()+b'\0')
    content_digest=digest.hexdigest();(snap/'.cloudif-content-sha256').write_text(content_digest+'\n')
    prior=[]
    for old in snap.parent.glob('d*'):
        if old==snap or not old.is_dir():continue
        try:n=int(old.name[1:])
        except Exception:continue
        checksum=old/'.cloudif-content-sha256'
        if n<deploy_number and checksum.is_file() and checksum.read_text().strip()==content_digest:prior.append(n)
    republished_from=max(prior) if prior else None
    base_stack,_,_=_cloudif_v131_get_stack(project=project)
    server_id=((base_stack.get('info') or {}).get('server_id') or (base_stack.get('config') or {}).get('server_id') or '') if isinstance(base_stack,dict) else ''
    if not server_id:
        servers=_cloudif_v131_list_items((_cloudif_v131_core_call('read','ListServers',{}).get('data')))
        preferred=next((x for x in servers if isinstance(x,dict) and x.get('name')=='Local'),None) or next((x for x in servers if isinstance(x,dict)),None)
        server_id=_cloudif_v131_oid(preferred or {})
    if not server_id:return send(handler,422,{'ok':False,'error':'server_id_missing'})
    name=f'cloudif-p{public_number}-d{deploy_number}'
    stack_dir=Path('/etc/komodo/stacks')/name
    try:
        stack_dir.mkdir(parents=True,exist_ok=True)
        staged=stack_dir/'source'
        if staged.exists():shutil.rmtree(staged)
        shutil.copytree(source,staged)
        shutil.copy2(snap/'Dockerfile.runtime',stack_dir/'Dockerfile.runtime')
    except Exception as exc:
        return send(handler,422,{'ok':False,'error':'version_runtime_stage_failed','detail':str(exc)[:500]})
    cfg={'server_id':server_id,'files_on_host':False,'run_build':True,'auto_pull':False,'file_contents':compose,'file_paths':[],'linked_repo':'','repo':'','branch':'','commit':commit,'git_provider':'','git_https':True,'run_directory':'.','webhook_enabled':False,'reclone':False}
    stacks=_cloudif_v131_list_items((_cloudif_v131_core_call('read','ListStacks',{}).get('data')))
    existing=next((x for x in stacks if isinstance(x,dict) and x.get('name')==name),None)
    if existing:
        stack_id=_cloudif_v131_oid(existing);created=False;update=_cloudif_v131_core_call('write','UpdateStack',{'id':stack_id,'config':cfg},timeout=60)
    else:
        create=_cloudif_v131_core_call('write','CreateStack',{'name':name,'config':cfg},timeout=60)
        if not create.get('ok'):return send(handler,422,{'ok':False,'error':'create_stack_failed','create':create})
        stack_id=_cloudif_v131_oid(create.get('data') or {});created=True;update={'ok':True,'created':create}
        if not stack_id:
            time.sleep(2);stacks=_cloudif_v131_list_items((_cloudif_v131_core_call('read','ListStacks',{}).get('data')));item=next((x for x in stacks if isinstance(x,dict) and x.get('name')==name),None);stack_id=_cloudif_v131_oid(item or {})
    if not stack_id:return send(handler,422,{'ok':False,'error':'stack_id_missing'})
    deploy=_cloudif_v131_core_call('execute','DeployStack',{'stack':stack_id},timeout=60)
    opid=_cloudif_v131_oid(deploy.get('data') or {})
    final=_cloudif_pub_wait_operation(opid,timeout=int(payload.get('timeout') or 420)) if opid else {}
    container=name+'-web';healthy=False;actual='';deadline=time.time()+int(payload.get('timeout') or 420)
    while time.time()<deadline:
        inspect=subprocess.run(['docker','inspect',container,'--format','{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}|{{.Config.Image}}'],text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        parts=inspect.stdout.strip().split('|',2) if inspect.returncode==0 else []
        actual=parts[2] if len(parts)==3 else ''
        healthy=len(parts)==3 and parts[0]=='running' and parts[1]=='healthy' and actual==image
        if healthy:break
        time.sleep(4)
    terminal=_cloudif_ensure_container_terminal(server_id,container) if healthy else {'ok':False,'error':'container_not_ready'}
    ok=bool(update.get('ok') and deploy.get('ok') and healthy and terminal.get('ok'))
    db_exec('''insert into publication_runtimes(project,public_number,deploy_number,stack_id,stack_name,container,commit_sha,status,is_active,updated_at)
      values(?,?,?,?,?,?,?,?,0,?) on conflict(project,deploy_number) do update set stack_id=excluded.stack_id,stack_name=excluded.stack_name,container=excluded.container,commit_sha=excluded.commit_sha,status=excluded.status,updated_at=excluded.updated_at''',(project,public_number,deploy_number,stack_id,name,container,commit,'ready' if ok else 'failed',now()))
    return send(handler,200 if ok else 422,{'ok':ok,'project':project,'public_number':public_number,'deploy_number':deploy_number,'commit':commit,'stack_id':stack_id,'stack_name':name,'container':container,'created':created,'deploy':deploy,'operation_id':opid,'operation_final':final,'healthy':healthy,'terminal':terminal,'expected_image':image,'actual_image':actual,'runtime':runtime,'runtime_base':base,'content_digest':content_digest,'source':'git_commit','publication_source':source_kind,'infrastructure_in_git':False,'republished':republished_from is not None,'republished_from':republished_from})


def cloudif_publication_promote(handler):
    if not _cloudif_pub_auth(handler):return send(handler,403,{'ok':False,'error':'forbidden'})
    payload=_cloudif_pub_json(handler);project=safe_slug(payload.get('project') or '')
    try:num=int(payload.get('public_number'));dep=int(payload.get('deploy_number'))
    except Exception:return send(handler,400,{'ok':False,'error':'invalid_numbers'})
    target=f'cloudif-p{num}-d{dep}-web';network='cloudif-publications'
    chk=subprocess.run(['docker','inspect',target,'--format','{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}'],text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    if chk.returncode or chk.stdout.strip()!='running|healthy':return send(handler,422,{'ok':False,'error':'target_not_healthy','target':target})
    active=f'cloudif-p{num}-active-web';names=subprocess.check_output(['docker','ps','-a','--format','{{.Names}}'],text=True).splitlines();candidates=[n for n in names if re.match(rf'^cloudif-p{num}-d\d+-web$',n)]
    def aliases(name):
        try:
            raw=subprocess.check_output(['docker','inspect',name,'--format','{{json (index .NetworkSettings.Networks "cloudif-publications").Aliases}}'],text=True).strip();return json.loads(raw) if raw and raw!='null' else []
        except Exception:return []
    previous=next((n for n in candidates if active in aliases(n)),'')
    def reconnect(name,is_active=False):
        match=re.match(rf'^cloudif-p{num}-d(\d+)-web$',name)
        if not match:return
        subprocess.run(['docker','network','disconnect',network,name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        cmd=['docker','network','connect','--alias',name]
        if is_active:cmd+=['--alias',active]
        cmd+=[network,name];subprocess.check_call(cmd)
    try:
        for name in candidates:
            if name!=target:reconnect(name,False)
        reconnect(target,True)
        deadline=time.time()+15
        while time.time()<deadline and active not in aliases(target):time.sleep(1)
        if active not in aliases(target):raise RuntimeError('active_alias_not_applied')
    except Exception as exc:
        if previous:
            try:reconnect(previous,True)
            except Exception:pass
        return send(handler,422,{'ok':False,'error':'promotion_failed','detail':str(exc),'previous':previous})
    _cloudif_v143_ensure_schema()
    if project:
        db_exec('update integrations set public_number=?,active_deploy=?,updated_at=? where project=?',(num,dep,now(),project))
        db_exec('update publication_runtimes set is_active=case when deploy_number=? then 1 else 0 end,updated_at=? where project=?',(dep,now(),project))
    return send(handler,200,{'ok':True,'project':project,'public_number':num,'deploy_number':dep,'target':target,'previous':previous,'active_alias':active,'aliases':aliases(target)})


def cloudif_project_membership_reconcile(handler):
    if not _cloudif_pub_auth(handler):
        return send(handler,403,{'ok':False,'error':'forbidden'})
    payload=_cloudif_pub_json(handler)
    project=safe_slug(payload.get('project') or payload.get('slug') or '')
    access=payload.get('access') if isinstance(payload.get('access'),dict) else {}
    owner=str(access.get('owner') or payload.get('owner_user') or '').strip().lower()
    acl=access.get('acl') if isinstance(access.get('acl'),list) else []
    integration=find_integration(project)
    if not project or not integration:
        return send(handler,404,{'ok':False,'error':'project_not_integrated','project':project})
    stack_ids=_cloudif_related_stack_ids(project,integration)
    authz=_cloudif_sync_project_authz(
        project,owner,acl,
        normalize_resource_id(integration.get('stack_id')),
        normalize_resource_id(integration.get('repo_id')),
        stack_ids,
        normalize_resource_id(integration.get('server_id')),
    )
    if not authz.get('ok'):
        return send(handler,422,{'ok':False,'error':'authz_sync_failed','authz':authz})
    desired={owner} if owner else set()
    for item in acl:
        if str(item.get('type') or '').strip().lower()=='user':
            username=str(item.get('subject') or '').strip().lower()
            if username:desired.add(username)
    _cloudif_v143_ensure_schema()
    runtime_rows=db_query(
        "select * from publication_runtimes where project=? and status='ready' order by deploy_number",
        (project,),
    )
    targets=[]
    for runtime in runtime_rows:
        stack_id=normalize_resource_id(runtime.get('stack_id'))
        if not stack_id:continue
        listed,_=komodo_call('read','ListStackServices',{'stack':stack_id})
        services=listed.get('data') if isinstance(listed.get('data'),list) else []
        service=next((x for x in services if isinstance(x,dict) and str(x.get('service') or '')=='web'),None)
        if service is None:
            service=next((x for x in services if isinstance(x,dict)),None)
        if not service:continue
        target={'type':'Stack','params':{'stack':stack_id,'service':str(service.get('service') or 'web')}}
        targets.append({
            'stack_id':stack_id,
            'deploy_number':int(runtime.get('deploy_number') or 0),
            'container':str(runtime.get('container') or ''),
            'target':target,
        })
    known_rows=db_query('select * from project_member_terminals where project=?',(project,))
    known={(str(row.get('username') or ''),normalize_resource_id(row.get('stack_id'))):row for row in known_rows}
    current_stack_ids={item['stack_id'] for item in targets}
    created=[];existing=[];removed=[];errors=[]
    for target_row in targets:
        target=target_row['target'];stack_id=target_row['stack_id']
        listed,_=komodo_call('read','ListTerminals',{'target':target})
        items=listed.get('data') if isinstance(listed.get('data'),list) else []
        for username in sorted(desired):
            terminal=('cloudif-'+project+'-'+safe_slug(username))[:120]
            found=next((x for x in items if isinstance(x,dict) and x.get('name')==terminal),None)
            descriptor={'username':username,'stack_id':stack_id,'deploy_number':target_row['deploy_number'],'terminal':terminal}
            if found:
                existing.append(descriptor)
            else:
                result,_=komodo_call('write','CreateTerminal',{'target':target,'name':terminal,'command':'sh','mode':'exec'})
                if result.get('ok'):
                    created.append(descriptor)
                else:
                    errors.append({**descriptor,'stage':'create_terminal','result':result})
                    continue
            db_exec('''insert into project_member_terminals(project,username,stack_id,terminal,target_json,updated_at)
              values(?,?,?,?,?,?) on conflict(project,username,stack_id) do update set
              terminal=excluded.terminal,target_json=excluded.target_json,updated_at=excluded.updated_at''',
              (project,username,stack_id,terminal,json.dumps(target,ensure_ascii=False),now()))
    for (username,stack_id),row in known.items():
        should_remove=username not in desired or stack_id not in current_stack_ids
        if not should_remove:continue
        try:old_target=json.loads(row.get('target_json') or '{}')
        except Exception:old_target={}
        result,_=komodo_call('write','DeleteTerminal',{'target':old_target,'terminal':row.get('terminal')})
        descriptor={'username':username,'stack_id':stack_id,'terminal':row.get('terminal')}
        if result.get('ok') or 'not found' in json.dumps(result).lower():
            db_exec('delete from project_member_terminals where project=? and username=? and stack_id=?',(project,username,stack_id))
            removed.append(descriptor)
        else:
            errors.append({**descriptor,'stage':'delete_terminal','result':result})
    active=_cloudif_active_publication_stack(project,normalize_resource_id(integration.get('stack_id')))
    return send(handler,200 if not errors else 207,{
        'ok':not errors,'project':project,'owner':owner,'desired_users':sorted(desired),
        'authz':authz,'active_publication':active,'publication_targets':len(targets),
        'terminals':{'created':created,'existing':existing,'removed':removed,'errors':errors},
        'waiting_for_publication':not bool(targets),
    })

# CloudIFF v143 END


if __name__ == "__main__":
    init_db()
    env = load_env()
    host = env.get("KOMODO_AGENT_HOST", "10.62.91.2")
    port = int(env.get("KOMODO_AGENT_PORT", "18098"))
    print(f"CloudIF Komodo Agent v42 ouvindo em {host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), H).serve_forever()
