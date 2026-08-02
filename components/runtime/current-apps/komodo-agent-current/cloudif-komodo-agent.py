import functools
#!/usr/bin/env python3
import json
import base64
import os
import pathlib
from pathlib import Path
import re
import sqlite3
import subprocess
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
    existing = find_by_name(repos, repo_info["repo_name"])

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

def create_or_update_stack(project, repo_info, server_id):
    stack_name = "cloudif-" + safe_slug(project)

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
        "file_paths": ["docker-compose.yml"],
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
        {"name": stack_name, "server_id": server_id, "repo": repo_info["repo_path"], "branch": repo_info["branch"], "git_provider": repo_info["git_provider"], "git_https": True, "git_account": _cloudif_v125_git_account(), "file_paths": ["docker-compose.yml"]},
        {"name": stack_name, "config": {"server_id": server_id, "repo": repo_info["repo_path"], "branch": repo_info["branch"], "git_provider": repo_info["git_provider"], "git_https": True, "git_account": _cloudif_v125_git_account(), "file_paths": ["docker-compose.yml"], "run_directory": ".", "webhook_enabled": True}},
    ]:
        r, _ = komodo_call("write", "CreateStack", params)
        attempts.append({"params": params, "response": r})
        if r.get("ok"):
            return r.get("data"), {"created": True, "attempts": attempts}

    return None, {"created": False, "attempts": attempts}

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

    repo, repo_action = create_or_update_repo(repo_info, server_id)
    result["repo_action"] = repo_action

    if not repo:
        result["stage"] = "repo"
        result["message"] = "Não foi possível criar/atualizar Repo no Komodo."
        record_deployment(project, tenant, actor, "ensure", "failed", result["message"], server_id, "", "", repo_info["repo_name"], request=payload, response=result)
        return result

    stack, stack_action = create_or_update_stack(project, repo_info, server_id)
    result["stack_action"] = stack_action

    if not stack:
        result["stage"] = "stack"
        result["message"] = "Não foi possível criar/atualizar Stack no Komodo."
        record_deployment(project, tenant, actor, "ensure", "failed", result["message"], server_id, "", item_id(repo), repo_info["repo_name"], request=payload, response=result)
        return result

    stack_id = item_id(stack)
    repo_id = item_id(repo)
    stack_name = stack.get("name") or ("cloudif-" + project)

    result["ok"] = True
    result["stage"] = "ready"
    result["message"] = "Projeto sincronizado no Komodo com Forgejo normalizado."
    result["repo"] = {"id": repo_id, "name": repo_info["repo_name"]}
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

def stack_action(action, payload):
    project = safe_slug(payload.get("project") or "")
    tenant = safe_slug(payload.get("tenant") or "")
    actor = payload.get("actor") or "unknown"
    integration = find_integration(project)

    if not integration:
        result = {"ok": False, "stage": "integration", "message": "Projeto não integrado no Komodo.", "project": project}
        record_deployment(project, tenant, actor, action, "failed", result["message"], request=payload, response=result)
        return result

    stack_id = integration.get("stack_id")
    stack_name = integration.get("stack_name")

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
            if r.get("ok"):
                ok = True
                break
        if ok:
            break

    result = {
        "ok": ok,
        "project": project,
        "tenant": tenant,
        "actor": actor,
        "action": action,
        "stack_id": stack_id,
        "stack_name": stack_name,
        "attempts": attempts,
        "message": "Ação executada." if ok else "Ação não executada. Verifique schema/operação retornada pelo Komodo.",
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

    return _cloudif_v117_send_json(handler, 200, {
        "ok": True,
        "component": "komodo-agent",
        "mode": "execute" if execute else "dry-run",
        "project_slug": slug,
        "repo": repo,
        "sqlite": sqlite_result,
        "remote_stack_delete": {
            "attempted": False,
            "status": "remote_delete_pending",
            "message": "Endpoint seguro de delete no Komodo Core ainda não mapeado; rollback limpou/avaliou mapeamentos locais do agent.",
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

    if repo_busy or stack_busy:
        deploy_status = "in_progress"
    elif errors:
        deploy_status = "failed"
    elif not missing and not errors and (st.get("latest_hash") or deployed_hash):
        deploy_status = "completed"
    elif not missing and not errors:
        deploy_status = "ready"
    else:
        deploy_status = "needs_attention"

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

    if deploy:
        deploy_stack = _cloudif_v131_core_call("execute", "DeployStack", {"stack": stack_id}, timeout=60)
        actions.append(deploy_stack)
        _cloudif_v131_wait(payload.get("wait_after_stack_deploy", 3))

    poll_snapshots = []

    if wait_for_completion:
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
            "DeployStack quando deploy=true",
            "Polling GetRepoActionState/GetStackActionState",
            "GetRepo/GetStack final",
        ],
        "before": before,
        "after": final_status,
        "actions": actions,
        "poll_snapshots": poll_snapshots,
        "reset_reclone_after": reset_reclone_after,
        "reset_action": reset_action,
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
    missing=list(info.get('missing_files') or [])
    services_result,_=komodo_call('read','ListStackServices',{'stack':stack_id})
    services=services_result.get('data') if isinstance(services_result.get('data'),list) else []
    service_row=next((x for x in services if isinstance(x,dict) and x.get('service')==service),None)
    if not service_row or not isinstance(service_row.get('container'),dict) or str((service_row.get('container') or {}).get('state') or '').lower()!='running':
        service_row=next((x for x in services if isinstance(x,dict) and isinstance(x.get('container'),dict) and str((x.get('container') or {}).get('state') or '').lower()=='running'),service_row)
    if service_row and service_row.get('service'): service=safe_slug(service_row.get('service'))
    container=(service_row or {}).get('container') if isinstance((service_row or {}).get('container'),dict) else {}
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
    server_id=str(container.get('server_id') or '')
    container_name=str(container.get('name') or '')
    target={'type':'Container','params':{'server':server_id,'container':container_name}} if server_id and container_name else {'type':'Stack','params':{'stack':stack_id,'service':service}}
    listed,_=komodo_call('read','ListTerminals',{'target':target}); items=listed.get('data') if isinstance(listed.get('data'),list) else []
    item=next((x for x in items if isinstance(x,dict) and x.get('name')==terminal),None)
    cmd=str((item or {}).get('command') or '')
    terminal_ok=bool(item and cmd.endswith(' '+shell))
    running=state=='running'
    issues=[]
    if not stack.get('ok'): issues.append('stack_unavailable')
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

def cloudif_project_terminal_ensure(handler):
    if not _cloudif_pub_auth(handler): return send(handler,403,{"ok":False,"error":"forbidden"})
    payload=_cloudif_pub_json(handler)
    audit=_cloudif_project_audit_data(payload)
    if not audit.get("ok"): return send(handler,400,audit)
    if not audit.get("running") or not audit.get("server_id") or not audit.get("container_name"):
        return send(handler,422,{"ok":False,"error":"container_not_running","audit":audit})
    target={"type":"Container","params":{"server":audit["server_id"],"container":audit["container_name"]}}
    terminal=audit["terminal"]; shell=audit["shell"]
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
    url=f"https://komodoiff.duckdns.org/servers/{audit['server_id']}/container/{audit['container_name']}/terminal/{terminal}"
    return send(handler,200,{"ok":True,"created":created,"terminal":terminal,"target":target,"server_id":audit["server_id"],"container_name":audit["container_name"],"url":url,"audit":audit})

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
        return send(handler, 404, {"ok": False, "error": "base_project_not_found", "status": status})
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
    content = _cloudif_pub_transform_compose(compose.get("content"), public_number, deploy_number)
    content = content.replace("./site:/usr/share/nginx/html:ro", f"{snap_dir}/site:/usr/share/nginx/html:ro")
    content = content.replace("./nginx.conf:/etc/nginx/conf.d/default.conf:ro", f"{snap_dir}/nginx.conf:/etc/nginx/conf.d/default.conf:ro")
    if "cloudif-publications" not in content:
        return send(handler, 422, {"ok": False, "error": "publication_network_missing"})
    base_stack, base_stack_id, _ = _cloudif_v131_get_stack(project=project)
    if not base_stack:
        stacks_result = _cloudif_v131_core_call("read", "ListStacks", {})
        expected_names = {project, f"cloudif-{project}"}
        expected_repo = f"cloudif/{project}"
        base_stack = next((item for item in _cloudif_v131_list_items(stacks_result.get("data"))
                           if isinstance(item, dict) and (
                               item.get("name") in expected_names
                               or ((item.get("info") or {}).get("repo") == expected_repo)
                               or ((item.get("config") or {}).get("repo") == expected_repo)
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
    dep = _cloudif_v131_core_call("execute", "DeployStack", {"stack": stack_id}, timeout=60)
    opid = _cloudif_v131_oid(dep.get("data") or {})
    container = f"cloudif-p{public_number}-d{deploy_number}-web"
    healthy = False
    final = {}
    timeout_s = int(payload.get("timeout") or 300)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        pr = subprocess.run(["docker", "inspect", container, "--format", "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}"], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        healthy = pr.returncode == 0 and pr.stdout.strip() == "running|healthy"
        if opid:
            try:
                updates = komodo_query_updates([opid])
                final = updates.get(opid) if isinstance(updates, dict) else {}
            except Exception:
                final = {}
        if healthy:
            break
        if final and final.get("success") is False:
            break
        time.sleep(4)
    terminal = _cloudif_ensure_container_terminal(server_id, container) if healthy else {"ok": False, "created": False, "error": "container_not_healthy"}
    ok = bool(update.get("ok") and dep.get("ok") and healthy and terminal.get("ok"))
    return send(handler, 200 if ok else 422, {
        "ok": ok, "project": project, "public_number": public_number, "deploy_number": deploy_number,
        "commit": commit, "stack_id": stack_id, "stack_name": name, "container": container,
        "created": created, "deploy": dep, "operation_id": opid, "operation_final": final, "healthy": healthy,
        "terminal": terminal, "content_digest": content_digest, "source": "git_commit", "generated_compose": generated_compose,
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
    except Exception as e:
        if previous:
            try: reconnect(previous, True)
            except Exception: pass
        return send(handler, 422, {"ok": False, "error": "promotion_failed", "detail": str(e), "previous": previous})
    return send(handler, 200, {"ok": True, "public_number": public_number, "deploy_number": deploy_number, "target": target, "previous": previous})


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
        if _cloudif_pub_path == "/komodo/project/audit":
            return cloudif_project_audit(self)
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

if __name__ == "__main__":
    init_db()
    env = load_env()
    host = env.get("KOMODO_AGENT_HOST", "10.62.91.2")
    port = int(env.get("KOMODO_AGENT_PORT", "18098"))
    print(f"CloudIF Komodo Agent v42 ouvindo em {host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), H).serve_forever()
