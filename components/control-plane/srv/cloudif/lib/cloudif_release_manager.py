#!/usr/bin/env python3
import base64
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tarfile
import tempfile
from pathlib import Path

DB = Path(os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db"))
BACKUP_BASE = Path(os.environ.get("CLOUDIF_RELEASE_BACKUP_DIR", "/srv/cloudif/managed-backups/releases"))
FORJA_ENV = Path("/etc/cloudif/forja-agent-client.env")
KOMODO_ENV = Path("/etc/cloudif/komodo-agent-client.env")
SUPABASE_ENV = Path("/etc/cloudif/supabase-release-agent-client.env")
VERSION_RE = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z.-]+))?$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
MIGRATION_RE = re.compile(r"^[0-9][0-9A-Za-z_.-]*\.sql$")


def now_utc():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value):
    value = str(value or "").strip()
    if not value:
        return dt.datetime.now(dt.timezone.utc)
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def read_env(path):
    data = {}
    try:
        for raw in path.read_text(errors="ignore").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return data


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    try:
        con.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        pass
    return con


def ensure_schema():
    con = connect()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS release_jobs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      scheduled_at TEXT NOT NULL,
      started_at TEXT DEFAULT '',
      finished_at TEXT DEFAULT '',
      project TEXT NOT NULL,
      tenant TEXT DEFAULT '',
      version TEXT NOT NULL,
      commit_sha TEXT NOT NULL,
      actor TEXT DEFAULT '',
      status TEXT NOT NULL,
      dry_run INTEGER NOT NULL DEFAULT 0,
      migration_count INTEGER NOT NULL DEFAULT 0,
      migration_applied INTEGER NOT NULL DEFAULT 0,
      release_id TEXT DEFAULT '',
      release_url TEXT DEFAULT '',
      backup_path TEXT DEFAULT '',
      message TEXT DEFAULT '',
      notes TEXT DEFAULT '',
      detail_json TEXT DEFAULT '{}',
      UNIQUE(project, version)
    );
    CREATE INDEX IF NOT EXISTS idx_release_jobs_due ON release_jobs(status, scheduled_at);
    CREATE INDEX IF NOT EXISTS idx_release_jobs_project_created ON release_jobs(project, created_at);
    CREATE TABLE IF NOT EXISTS release_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      job_id INTEGER,
      project TEXT NOT NULL,
      event TEXT NOT NULL,
      status TEXT NOT NULL,
      message TEXT DEFAULT '',
      detail_json TEXT DEFAULT '{}'
    );
    """)
    con.commit(); con.close()


def safe_detail(value, limit=100000):
    return json.dumps(value, ensure_ascii=False, default=str)[:limit]


def event(job_id, project, name, status, message="", detail=None):
    con = connect()
    con.execute("INSERT INTO release_events(created_at,job_id,project,event,status,message,detail_json) VALUES(?,?,?,?,?,?,?)",
                (now_utc(), job_id, project, name, status, message[:4000], safe_detail(detail or {})))
    con.commit(); con.close()


def http_json(method, url, token="", payload=None, timeout=90):
    import urllib.request, urllib.error
    headers = {"Accept": "application/json", "User-Agent": "CloudIF-ReleaseManager/1.0"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
        headers["X-CloudIF-Token"] = token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "ignore")
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {"raw": raw[:4000]}
            return {"ok": 200 <= response.status < 300, "status": response.status, "data": body}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "ignore")
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            body = {"raw": raw[:4000]}
        return {"ok": False, "status": exc.code, "data": body}
    except Exception as exc:
        return {"ok": False, "status": 0, "error": type(exc).__name__, "data": {}}


def agent_call(env_path, url_key, token_key, default_url, path, payload, timeout=180):
    cfg = read_env(env_path)
    base = (cfg.get(url_key) or default_url).rstrip("/")
    token = cfg.get(token_key) or ""
    return http_json("POST", base + path, token, payload, timeout)


def forja_prepare(project, version, commit, notes, dry_run):
    return agent_call(FORJA_ENV, "FORJA_AGENT_URL", "FORJA_AGENT_TOKEN", "http://10.62.91.2:18095",
                      "/project/release/prepare", {"project": project, "version": version, "commit": commit, "notes": notes, "dry_run": bool(dry_run)}, 120)


def forja_finalize(project, version, release_id, notes):
    return agent_call(FORJA_ENV, "FORJA_AGENT_URL", "FORJA_AGENT_TOKEN", "http://10.62.91.2:18095",
                      "/project/release/finalize", {"project": project, "version": version, "release_id": release_id, "notes": notes}, 120)


def komodo_deploy_commit(project, tenant, commit, actor):
    return agent_call(KOMODO_ENV, "KOMODO_AGENT_URL", "KOMODO_AGENT_TOKEN", "http://10.62.91.2:18098",
                      "/komodo/stack/rollback-filecontents", {"project": project, "project_slug": project, "tenant": tenant, "commit": commit, "actor": actor, "source": "scheduled-release"}, 240)


def supabase_agent_call(path, payload, timeout=1800):
    return agent_call(SUPABASE_ENV, "SUPABASE_AGENT_URL", "SUPABASE_AGENT_TOKEN", "http://127.0.0.1:18100", path, payload, timeout)


def supabase_inspect(project, tenant, version, migrations):
    return supabase_agent_call("/supabase/release/inspect", {"project": project, "tenant": tenant, "version": version, "migrations": migrations}, 120)


def supabase_backup(project, tenant, version):
    return supabase_agent_call("/supabase/release/backup", {"project": project, "tenant": tenant, "version": version}, 3600)


def supabase_migrate(project, tenant, version, migrations):
    return supabase_agent_call("/supabase/release/migrate", {"project": project, "tenant": tenant, "version": version, "migrations": migrations}, 1800)


def next_version(project):
    ensure_schema(); con = connect()
    versions = [r[0] for r in con.execute("SELECT version FROM release_jobs WHERE project=?", (project,))]
    con.close()
    parsed = []
    for value in versions:
        match = VERSION_RE.fullmatch(value or "")
        if match and not match.group(4):
            parsed.append(tuple(map(int, match.groups()[:3])))
    if not parsed:
        return "v0.1.0"
    major, minor, patch = max(parsed)
    return f"v{major}.{minor}.{patch + 1}"


def project_setting(project):
    con = connect()
    row = con.execute("SELECT * FROM release_settings WHERE project=? AND enabled=1", (project,)).fetchone()
    con.close()
    return dict(row) if row else None


def schedule(project, tenant, version, commit, scheduled_at, actor, dry_run=True, notes=""):
    ensure_schema()
    project = str(project or "").strip().lower()
    tenant = str(tenant or "").strip().lower()
    commit = str(commit or "").strip().lower()
    actor = str(actor or "portal")[:200]
    notes = str(notes or "")[:12000]
    if not SLUG_RE.fullmatch(project):
        raise ValueError("project inválido")
    if not COMMIT_RE.fullmatch(commit):
        raise ValueError("commit inválido")
    version = str(version or "").strip() or next_version(project)
    if not VERSION_RE.fullmatch(version):
        raise ValueError("versão inválida; use vMAJOR.MINOR.PATCH[-sufixo]")
    when = parse_utc(scheduled_at)
    now = dt.datetime.now(dt.timezone.utc)
    if when < now - dt.timedelta(minutes=5) or when > now + dt.timedelta(days=366):
        raise ValueError("horário fora da janela permitida")
    setting = project_setting(project)
    if not setting:
        raise ValueError("projeto ainda não reconciliado")
    tenant = tenant or setting.get("tenant") or ""
    if not dry_run and not clock_synchronized():
        raise RuntimeError("relógio do servidor não está sincronizado por NTP; publicação real bloqueada")
    validation = forja_prepare(project, version, commit, notes, True)
    body = validation.get("data") if isinstance(validation.get("data"), dict) else {}
    if not validation.get("ok") or not body.get("ok"):
        raise RuntimeError("validação do commit/release falhou")
    migration_count = int(((body.get("migrations") or {}).get("count")) or 0)
    if migration_count and not tenant:
        raise ValueError("release contém migrações, mas não possui tenant")
    created = now_utc()
    con = connect()
    cur = con.execute("""INSERT INTO release_jobs(
        created_at,scheduled_at,project,tenant,version,commit_sha,actor,status,dry_run,migration_count,message,notes,detail_json
      ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (created, when.replace(microsecond=0).isoformat().replace("+00:00", "Z"), project, tenant, version, commit, actor,
       "scheduled", 1 if dry_run else 0, migration_count, "Release validada e agendada.", notes,
       safe_detail({"validation": {"project": body.get("project"), "repo": body.get("repo"), "commit": body.get("commit"), "migration_count": migration_count}})))
    job_id = cur.lastrowid
    con.commit(); con.close()
    event(job_id, project, "scheduled", "ok", "Release agendada.", {"scheduled_at": when.isoformat(), "dry_run": bool(dry_run), "migration_count": migration_count})
    return {"ok": True, "job_id": job_id, "project": project, "tenant": tenant, "version": version, "commit": commit,
            "scheduled_at": when.replace(microsecond=0).isoformat().replace("+00:00", "Z"), "dry_run": bool(dry_run), "migration_count": migration_count}


def clock_synchronized():
    try:
        proc = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"], text=True, capture_output=True, timeout=10)
        return proc.returncode == 0 and proc.stdout.strip().lower() == "yes"
    except Exception:
        return False


def run_bytes(cmd, input_bytes=None, timeout=600):
    return subprocess.run(cmd, input=input_bytes, capture_output=True, timeout=timeout)


def tenant_container(tenant):
    con = connect()
    row = con.execute("SELECT db_container FROM release_tenants WHERE tenant=? AND enabled=1", (tenant,)).fetchone()
    con.close()
    if row and row[0]:
        probe = subprocess.run(["docker", "inspect", row[0]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if probe.returncode == 0:
            return row[0]
    p = subprocess.run(["docker", "ps", "--format", '{{.Names}}|{{.Label "com.docker.compose.project"}}|{{.Label "com.docker.compose.service"}}'], text=True, capture_output=True, timeout=30)
    if p.returncode == 0:
        expected = "cloudif_" + tenant
        for line in p.stdout.splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3 and parts[1] == expected and parts[2] == "db":
                return parts[0]
    return ""


def backup_tenant(project, version, tenant, container):
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    work = BACKUP_BASE / project / version / (stamp + "-" + tenant)
    work.mkdir(parents=True, exist_ok=False, mode=0o700)
    globals_path = work / "globals.sql.gz"
    proc = subprocess.Popen(["docker", "exec", container, "sh", "-lc", 'pg_dumpall -U "$POSTGRES_USER" --globals-only'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None
    with gzip.open(globals_path, "wb", compresslevel=9) as gz:
        while True:
            chunk = proc.stdout.read(1024 * 1024)
            if not chunk:
                break
            gz.write(chunk)
    stderr = proc.stderr.read() if proc.stderr else b""
    rc = proc.wait(timeout=600)
    if rc != 0 or globals_path.stat().st_size == 0:
        raise RuntimeError("backup de globals falhou: " + stderr.decode(errors="ignore")[-500:])
    q = run_bytes(["docker", "exec", container, "sh", "-lc", 'psql -U "$POSTGRES_USER" -d postgres -Atc "select datname from pg_database where datistemplate=false order by datname"'], timeout=120)
    if q.returncode != 0:
        raise RuntimeError("listagem de bancos falhou")
    databases = [x.strip() for x in q.stdout.decode(errors="ignore").splitlines() if x.strip()]
    (work / "databases.txt").write_text("\n".join(databases) + "\n")
    for dbname in databases:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", dbname)
        dest = work / (safe + ".dump")
        with dest.open("wb") as out:
            p = subprocess.run(["docker", "exec", container, "sh", "-lc", 'pg_dump -U "$POSTGRES_USER" -Fc --no-owner --no-privileges -d "$1"', "sh", dbname], stdout=out, stderr=subprocess.PIPE, timeout=1800)
        if p.returncode != 0 or dest.stat().st_size == 0:
            raise RuntimeError("backup do banco falhou: " + dbname)
    sums = []
    for f in sorted(work.iterdir()):
        if f.is_file() and f.name != "SHA256SUMS.txt":
            sums.append(hashlib.sha256(f.read_bytes()).hexdigest() + "  " + f.name)
            os.chmod(f, 0o600)
    (work / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")
    archive = work.with_suffix(".tar.gz")
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(work, arcname=work.name)
    os.chmod(archive, 0o600)
    if archive.stat().st_size == 0:
        raise RuntimeError("arquivo de backup vazio")
    import shutil
    shutil.rmtree(work)
    return str(archive)


def sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def psql(container, sql_bytes, tuples=False, timeout=600):
    cmd = ["docker", "exec", "-i", container, "psql", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"]
    if tuples:
        cmd.extend(["-At"])
    return run_bytes(cmd, input_bytes=sql_bytes, timeout=timeout)


def apply_migrations(project, version, container, items):
    bootstrap = b"CREATE SCHEMA IF NOT EXISTS cloudif_deploy; CREATE TABLE IF NOT EXISTS cloudif_deploy.schema_migrations(project text not null, version text not null, migration_name text not null, sha256 text not null, applied_at timestamptz not null default now(), primary key(project,migration_name));\n"
    result = psql(container, bootstrap)
    if result.returncode != 0:
        raise RuntimeError("não foi possível preparar controle de migrações")
    applied = 0
    for item in items:
        name = str(item.get("name") or "")
        sha = str(item.get("sha256") or "")
        if not MIGRATION_RE.fullmatch(name) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise RuntimeError("metadados de migração inválidos")
        raw = base64.b64decode(item.get("content_b64") or "", validate=True)
        if hashlib.sha256(raw).hexdigest() != sha:
            raise RuntimeError("hash da migração não confere: " + name)
        check_sql = f"SELECT sha256 FROM cloudif_deploy.schema_migrations WHERE project={sql_literal(project)} AND migration_name={sql_literal(name)};\n".encode()
        check = psql(container, check_sql, tuples=True, timeout=120)
        if check.returncode != 0:
            raise RuntimeError("falha ao consultar migração: " + name)
        existing = check.stdout.decode(errors="ignore").strip()
        if existing:
            if existing != sha:
                raise RuntimeError("migração já aplicada foi alterada: " + name)
            continue
        wrapper = ("BEGIN;\n".encode() + raw + b"\n" +
                   f"INSERT INTO cloudif_deploy.schema_migrations(project,version,migration_name,sha256) VALUES({sql_literal(project)},{sql_literal(version)},{sql_literal(name)},{sql_literal(sha)});\nCOMMIT;\n".encode())
        run = psql(container, wrapper, timeout=1200)
        if run.returncode != 0:
            raise RuntimeError("migração falhou: " + name)
        applied += 1
    return applied


def update_job(job_id, **fields):
    if not fields:
        return
    con = connect()
    keys = list(fields)
    con.execute("UPDATE release_jobs SET " + ",".join(k + "=?" for k in keys) + " WHERE id=?", [fields[k] for k in keys] + [job_id])
    con.commit(); con.close()


def record_deployment(job, status, message, response):
    con = connect()
    try:
        con.execute("""INSERT INTO deployments(created_at,project,tenant,actor,action,status,message,commit_sha,commit_short,mode,response_json)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (now_utc(), job["project"], job["tenant"], job["actor"], "scheduled-release", status, message,
                     job["commit_sha"], job["commit_sha"][:7], "versioned_release", safe_detail(response)))
        con.execute("""INSERT INTO deploy_state(project,tenant,mode,commit_sha,commit_short,commit_message,actor,updated_at,response_json)
                       VALUES(?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(project) DO UPDATE SET tenant=excluded.tenant,mode=excluded.mode,commit_sha=excluded.commit_sha,
                         commit_short=excluded.commit_short,commit_message=excluded.commit_message,actor=excluded.actor,
                         updated_at=excluded.updated_at,response_json=excluded.response_json""",
                    (job["project"], job["tenant"], "versioned_release", job["commit_sha"], job["commit_sha"][:7], job["version"], job["actor"], now_utc(), safe_detail(response)))
        con.commit()
    finally:
        con.close()


def process_job(job_id):
    ensure_schema(); con = connect()
    row = con.execute("SELECT * FROM release_jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        con.close(); return {"ok": False, "error": "not_found"}
    job = dict(row)
    if job["status"] not in {"scheduled", "retry"}:
        con.close(); return {"ok": False, "error": "not_runnable", "status": job["status"]}
    claimed = con.execute("UPDATE release_jobs SET status='running',started_at=?,message='Execução iniciada.' WHERE id=? AND status IN ('scheduled','retry')", (now_utc(), job_id)).rowcount
    con.commit(); con.close()
    if not claimed:
        return {"ok": False, "error": "already_claimed"}
    event(job_id, job["project"], "start", "ok", "Execução iniciada.")
    detail = {}
    try:
        if not job["dry_run"] and not clock_synchronized():
            raise RuntimeError("relógio do servidor não está sincronizado por NTP")
        validation = forja_prepare(job["project"], job["version"], job["commit_sha"], job["notes"], True)
        body = validation.get("data") if isinstance(validation.get("data"), dict) else {}
        if not validation.get("ok") or not body.get("ok"):
            raise RuntimeError("validação Forgejo falhou")
        migrations = (body.get("migrations") or {}).get("items") or []
        supabase_check = supabase_inspect(job["project"], job["tenant"], job["version"], migrations)
        supabase_check_body = supabase_check.get("data") if isinstance(supabase_check.get("data"), dict) else {}
        if not supabase_check.get("ok") or not supabase_check_body.get("ok"):
            raise RuntimeError("validação Supabase Agent falhou")
        if migrations and not supabase_check_body.get("available"):
            raise RuntimeError("tenant Supabase indisponível para migrações")
        update_job(job_id, migration_count=len(migrations))
        event(job_id, job["project"], "validate", "ok", "Forgejo e Supabase Agent validados.", {"migration_count": len(migrations), "tenant_available": supabase_check_body.get("available")})
        if job["dry_run"]:
            update_job(job_id, status="validated", finished_at=now_utc(), message="Validação dos três agentes concluída; nenhuma alteração foi publicada.", detail_json=safe_detail({"migration_count": len(migrations), "supabase": supabase_check_body}))
            event(job_id, job["project"], "dry_run", "ok", "Validação seca concluída.")
            return {"ok": True, "status": "validated", "job_id": job_id}
        backup_path = ""
        if job["tenant"]:
            backup_result = supabase_backup(job["project"], job["tenant"], job["version"])
            backup_body = backup_result.get("data") if isinstance(backup_result.get("data"), dict) else {}
            if not backup_result.get("ok") or not backup_body.get("ok") or not backup_body.get("backup_path"):
                raise RuntimeError("backup pelo Supabase Agent falhou")
            backup_path = str(backup_body.get("backup_path") or "")
            update_job(job_id, backup_path=backup_path)
            event(job_id, job["project"], "backup", "ok", "Backup pré-publicação concluído pelo Supabase Agent.", {"backup_path": backup_path})
        elif migrations:
            raise RuntimeError("migrações encontradas sem tenant")
        prepared = forja_prepare(job["project"], job["version"], job["commit_sha"], job["notes"], False)
        prepared_body = prepared.get("data") if isinstance(prepared.get("data"), dict) else {}
        if not prepared.get("ok") or not prepared_body.get("ok"):
            raise RuntimeError("não foi possível criar release em rascunho")
        release_id = str(prepared_body.get("release_id") or "")
        release_url = str(prepared_body.get("release_url") or "")
        update_job(job_id, release_id=release_id, release_url=release_url)
        event(job_id, job["project"], "release_draft", "ok", "Release em rascunho criada.", {"release_id": release_id})
        applied = 0
        if migrations:
            migration_result = supabase_migrate(job["project"], job["tenant"], job["version"], migrations)
            migration_body = migration_result.get("data") if isinstance(migration_result.get("data"), dict) else {}
            if not migration_result.get("ok") or not migration_body.get("ok"):
                raise RuntimeError("migração pelo Supabase Agent falhou")
            applied = int(migration_body.get("applied") or 0)
            update_job(job_id, migration_applied=applied)
            event(job_id, job["project"], "migrations", "ok", "Migrações aplicadas pelo Supabase Agent.", {"applied": applied, "total": len(migrations)})
        deploy = komodo_deploy_commit(job["project"], job["tenant"], job["commit_sha"], job["actor"])
        deploy_body = deploy.get("data") if isinstance(deploy.get("data"), dict) else {}
        if not deploy.get("ok") or not deploy_body.get("ok"):
            raise RuntimeError("deploy Komodo falhou")
        event(job_id, job["project"], "deploy", "ok", "Commit publicado pelo Komodo.", {"commit": job["commit_sha"]})
        finalized = forja_finalize(job["project"], job["version"], release_id, job["notes"])
        finalized_body = finalized.get("data") if isinstance(finalized.get("data"), dict) else {}
        if not finalized.get("ok") or not finalized_body.get("ok"):
            update_job(job_id, status="deployed_unfinalized", finished_at=now_utc(), message="Deploy concluído, mas a release permaneceu em rascunho.", detail_json=safe_detail({"deploy": deploy_body, "finalize": finalized}))
            record_deployment(job, "partial", "Deploy concluído; release não finalizada.", {"deploy": deploy_body, "finalize": finalized})
            event(job_id, job["project"], "finalize", "failed", "Release não finalizada.")
            return {"ok": False, "status": "deployed_unfinalized", "job_id": job_id}
        detail = {"release": finalized_body, "deploy": deploy_body, "backup_path": backup_path, "migrations_applied": applied}
        update_job(job_id, status="published", finished_at=now_utc(), message="Release publicada com sucesso.", release_url=finalized_body.get("release_url") or release_url, detail_json=safe_detail(detail))
        record_deployment(job, "ok", "Release publicada com sucesso.", detail)
        event(job_id, job["project"], "published", "ok", "Release publicada com sucesso.", {"version": job["version"]})
        return {"ok": True, "status": "published", "job_id": job_id}
    except Exception as exc:
        message = "Publicação interrompida: " + str(exc)[:1000]
        update_job(job_id, status="failed", finished_at=now_utc(), message=message, detail_json=safe_detail({"error_type": type(exc).__name__}))
        event(job_id, job["project"], "failed", "failed", message, {"error_type": type(exc).__name__})
        return {"ok": False, "status": "failed", "job_id": job_id, "error": type(exc).__name__}


def dispatch_due(limit=3):
    ensure_schema(); now = now_utc(); con = connect()
    ids = [r[0] for r in con.execute("SELECT id FROM release_jobs WHERE status IN ('scheduled','retry') AND scheduled_at<=? ORDER BY scheduled_at,id LIMIT ?", (now, max(1, min(int(limit), 20))))]
    con.close()
    return [process_job(job_id) for job_id in ids]


def get_job(job_id):
    ensure_schema(); con = connect(); row = con.execute("SELECT * FROM release_jobs WHERE id=?", (int(job_id),)).fetchone(); con.close(); return dict(row) if row else None


def recent(project="", limit=30):
    ensure_schema(); con = connect(); limit=max(1,min(int(limit),100))
    if project:
        rows=con.execute("SELECT * FROM release_jobs WHERE project=? ORDER BY id DESC LIMIT ?",(project,limit)).fetchall()
    else:
        rows=con.execute("SELECT * FROM release_jobs ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
    con.close(); return [dict(r) for r in rows]


def cancel(job_id, actor=""):
    ensure_schema(); con=connect(); row=con.execute("SELECT project,status FROM release_jobs WHERE id=?",(int(job_id),)).fetchone()
    if not row:
        con.close(); return {"ok":False,"error":"not_found"}
    if row["status"] not in {"scheduled","retry"}:
        con.close(); return {"ok":False,"error":"not_cancellable","status":row["status"]}
    con.execute("UPDATE release_jobs SET status='cancelled',finished_at=?,message=? WHERE id=?",(now_utc(),"Cancelada por "+str(actor)[:200],int(job_id)))
    con.commit(); con.close(); event(int(job_id),row["project"],"cancelled","ok","Release cancelada.",{"actor":actor}); return {"ok":True,"status":"cancelled","job_id":int(job_id)}
