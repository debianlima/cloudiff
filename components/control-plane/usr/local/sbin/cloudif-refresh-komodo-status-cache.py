#!/usr/bin/env python3
import datetime
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

DB = "/var/lib/cloudif/portal/cloudif-portal.db"
DEFAULT_KOMODO_AGENT = "http://10.62.91.2:18098"
TTL_SECONDS = 300

def now_iso():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def add_seconds_iso(seconds):
    return (
        datetime.datetime.utcnow() + datetime.timedelta(seconds=int(seconds))
    ).replace(microsecond=0).isoformat() + "Z"

def read_env(path):
    data = {}
    p = Path(path)
    if not p.exists():
        return data
    for raw in p.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data

def komodo_agent_config():
    env1 = read_env("/etc/cloudif/komodo-agent-client.env")
    env2 = read_env("/etc/cloudif/provision.env")
    url = (
        env1.get("KOMODO_AGENT_URL")
        or env2.get("KOMODO_AGENT_URL")
        or DEFAULT_KOMODO_AGENT
    ).rstrip("/")
    token = env1.get("KOMODO_AGENT_TOKEN") or env2.get("KOMODO_AGENT_TOKEN") or ""
    return url, token

def http_json(url, payload, timeout=12):
    base, token = komodo_agent_config()

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    if token:
        headers["X-CloudIF-Token"] = token
        headers["Authorization"] = "Bearer " + token

    req = urllib.request.Request(
        base + url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            data = json.loads(raw) if raw else {}
            return {"ok": 200 <= r.status < 300, "status": r.status, "data": data}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {"raw": raw}
        return {"ok": False, "status": e.code, "data": data}
    except Exception as e:
        return {"ok": False, "status": 0, "error": f"{type(e).__name__}: {e}", "data": {}}

def ensure_table(con):
    con.executescript("""
    create table if not exists project_runtime_status (
      slug text primary key,
      komodo_deploy_status text,
      komodo_latest_hash text,
      komodo_deployed_hash text,
      komodo_latest_message text,
      komodo_services_json text,
      komodo_remote_errors_json text,
      komodo_missing_files_json text,
      komodo_busy_repo integer default 0,
      komodo_busy_stack integer default 0,
      komodo_repo_id text,
      komodo_stack_id text,
      komodo_last_checked_at text,
      komodo_next_check_at text,
      komodo_cache_ttl_seconds integer default 300,
      komodo_last_http_status integer,
      komodo_last_error text,
      komodo_raw_json text,
      updated_at text default current_timestamp
    );

    create index if not exists idx_project_runtime_status_next_check
    on project_runtime_status(komodo_next_check_at);
    """)
    con.commit()

def list_project_slugs(con):
    tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    if "projects" not in tables:
        return []

    cols = [r[1] for r in con.execute("pragma table_info(projects)")]
    if "slug" not in cols:
        return []

    return [
        r[0]
        for r in con.execute(
            "select slug from projects where slug is not null and trim(slug) <> '' order by slug"
        )
    ]

def save_status(con, slug, res, ttl=TTL_SECONDS):
    data = res.get("data") if isinstance(res, dict) else {}
    if not isinstance(data, dict):
        data = {}

    repo = data.get("repo") or {}
    stack = data.get("stack") or {}
    busy = data.get("busy") or {}

    services = stack.get("deployed_services") or stack.get("latest_services") or []
    errors = stack.get("remote_errors") or []
    missing = stack.get("missing_files") or []

    last_error = ""
    if not res.get("ok"):
        last_error = res.get("error") or data.get("error") or data.get("message") or "falha ao consultar Komodo"

    con.execute("""
        insert into project_runtime_status (
          slug,
          komodo_deploy_status,
          komodo_latest_hash,
          komodo_deployed_hash,
          komodo_latest_message,
          komodo_services_json,
          komodo_remote_errors_json,
          komodo_missing_files_json,
          komodo_busy_repo,
          komodo_busy_stack,
          komodo_repo_id,
          komodo_stack_id,
          komodo_last_checked_at,
          komodo_next_check_at,
          komodo_cache_ttl_seconds,
          komodo_last_http_status,
          komodo_last_error,
          komodo_raw_json,
          updated_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(slug) do update set
          komodo_deploy_status=excluded.komodo_deploy_status,
          komodo_latest_hash=excluded.komodo_latest_hash,
          komodo_deployed_hash=excluded.komodo_deployed_hash,
          komodo_latest_message=excluded.komodo_latest_message,
          komodo_services_json=excluded.komodo_services_json,
          komodo_remote_errors_json=excluded.komodo_remote_errors_json,
          komodo_missing_files_json=excluded.komodo_missing_files_json,
          komodo_busy_repo=excluded.komodo_busy_repo,
          komodo_busy_stack=excluded.komodo_busy_stack,
          komodo_repo_id=excluded.komodo_repo_id,
          komodo_stack_id=excluded.komodo_stack_id,
          komodo_last_checked_at=excluded.komodo_last_checked_at,
          komodo_next_check_at=excluded.komodo_next_check_at,
          komodo_cache_ttl_seconds=excluded.komodo_cache_ttl_seconds,
          komodo_last_http_status=excluded.komodo_last_http_status,
          komodo_last_error=excluded.komodo_last_error,
          komodo_raw_json=excluded.komodo_raw_json,
          updated_at=excluded.updated_at
    """, (
        slug,
        data.get("deploy_status") or "",
        stack.get("latest_hash") or repo.get("latest_hash") or "",
        stack.get("deployed_hash") or "",
        stack.get("latest_message") or repo.get("latest_message") or "",
        json.dumps(services, ensure_ascii=False),
        json.dumps(errors, ensure_ascii=False),
        json.dumps(missing, ensure_ascii=False),
        1 if busy.get("repo") else 0,
        1 if busy.get("stack") else 0,
        data.get("repo_id") or "",
        data.get("stack_id") or "",
        now_iso(),
        add_seconds_iso(ttl),
        int(ttl),
        int(res.get("status") or 0),
        last_error,
        json.dumps(data, ensure_ascii=False),
        now_iso(),
    ))
    con.commit()

def main():
    force_slug = sys.argv[1].strip() if len(sys.argv) > 1 else ""

    con = sqlite3.connect(DB)
    ensure_table(con)

    if force_slug:
        slugs = [force_slug]
    else:
        slugs = list_project_slugs(con)

    if not slugs:
        print("Nenhum projeto encontrado.")
        return 0

    print(f"Projetos para atualizar: {len(slugs)}")

    for slug in slugs:
        res = http_json("/komodo/project/status", {"project_slug": slug}, timeout=12)
        save_status(con, slug, res)
        data = res.get("data") or {}
        print(
            f"- {slug}: http={res.get('status')} ok={res.get('ok')} "
            f"deploy_status={data.get('deploy_status')} "
            f"hash={(data.get('stack') or {}).get('latest_hash') or (data.get('repo') or {}).get('latest_hash') or '-'}"
        )

    print()
    print("Cache atual:")
    con.row_factory = sqlite3.Row
    for row in con.execute("""
        select
          slug,
          komodo_deploy_status,
          substr(komodo_latest_hash, 1, 8) as hash,
          komodo_last_checked_at,
          komodo_next_check_at,
          komodo_last_error
        from project_runtime_status
        order by slug
    """):
        print(dict(row))

    con.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
