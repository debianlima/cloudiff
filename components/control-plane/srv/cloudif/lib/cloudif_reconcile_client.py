#!/usr/bin/env python3
import datetime as dt
import json
import os
import re
import sqlite3
import tempfile
import uuid
import hashlib
from pathlib import Path

DB = Path(os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db"))
QUEUE = Path(os.environ.get("CLOUDIF_RECONCILE_QUEUE", "/var/lib/cloudif/reconcile-queue/incoming"))
ALLOWED_EVENTS = {
    "user.created", "user.seen",
    "project.created", "project.updated", "project.integrated",
    "repository.created", "repository.updated",
    "tenant.created", "tenant.ready", "tenant.bound",
    "reconcile.requested",
}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")


def now_utc():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    CREATE TABLE IF NOT EXISTS reconcile_requests (
      request_id TEXT PRIMARY KEY,
      created_at TEXT NOT NULL,
      started_at TEXT DEFAULT '',
      finished_at TEXT DEFAULT '',
      event_type TEXT NOT NULL,
      actor TEXT DEFAULT '',
      username TEXT DEFAULT '',
      project TEXT DEFAULT '',
      tenant TEXT DEFAULT '',
      status TEXT NOT NULL,
      message TEXT DEFAULT '',
      payload_json TEXT DEFAULT '{}',
      result_json TEXT DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_reconcile_requests_status_created
      ON reconcile_requests(status, created_at);
    CREATE INDEX IF NOT EXISTS idx_reconcile_requests_project_created
      ON reconcile_requests(project, created_at);

    CREATE TABLE IF NOT EXISTS release_users (
      username TEXT PRIMARY KEY,
      email TEXT DEFAULT '',
      groups_json TEXT DEFAULT '[]',
      enabled INTEGER NOT NULL DEFAULT 1,
      discovered_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS release_settings (
      project TEXT PRIMARY KEY,
      tenant TEXT DEFAULT '',
      repo_full_name TEXT DEFAULT '',
      repo_url TEXT DEFAULT '',
      enabled INTEGER NOT NULL DEFAULT 1,
      default_channel TEXT NOT NULL DEFAULT 'stable',
      version_policy TEXT NOT NULL DEFAULT 'patch',
      auto_discovered INTEGER NOT NULL DEFAULT 1,
      discovered_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS release_tenants (
      tenant TEXT PRIMARY KEY,
      db_container TEXT DEFAULT '',
      enabled INTEGER NOT NULL DEFAULT 1,
      discovered_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    """)
    cols={r[1] for r in con.execute("PRAGMA table_info(reconcile_requests)")}
    additions={
      "attempt_count":"INTEGER NOT NULL DEFAULT 0","max_attempts":"INTEGER NOT NULL DEFAULT 5",
      "next_attempt_at":"TEXT NOT NULL DEFAULT ''","lease_owner":"TEXT NOT NULL DEFAULT ''",
      "lease_expires_at":"TEXT NOT NULL DEFAULT ''","heartbeat_at":"TEXT NOT NULL DEFAULT ''",
      "partition_key":"TEXT NOT NULL DEFAULT ''","coalesce_key":"TEXT NOT NULL DEFAULT ''",
      "dead_lettered_at":"TEXT NOT NULL DEFAULT ''","last_error_type":"TEXT NOT NULL DEFAULT ''"
    }
    for name,kind in additions.items():
        if name not in cols: con.execute(f"ALTER TABLE reconcile_requests ADD COLUMN {name} {kind}")
    con.execute("CREATE INDEX IF NOT EXISTS idx_reconcile_due ON reconcile_requests(status,next_attempt_at,created_at)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_reconcile_partition ON reconcile_requests(partition_key,status,created_at)")
    con.commit()
    con.close()


def _safe_slug(value):
    value = str(value or "").strip().lower()
    return value if not value or SLUG_RE.fullmatch(value) else ""


SENSITIVE_KEYS={"token","password","secret","authorization","api_key","access_token","refresh_token","token_hash"}
def _contains_secret(value):
    if isinstance(value,dict):
        return any(str(k).strip().lower() in SENSITIVE_KEYS or _contains_secret(v) for k,v in value.items())
    if isinstance(value,list): return any(_contains_secret(v) for v in value)
    return False

def _partition(event_type,username,project,tenant):
    if project:return "project:"+project
    if tenant:return "tenant:"+tenant
    if username:return "user:"+username.lower()
    return "global:"+event_type

def _coalesce(event_type,username,project,tenant):
    return hashlib.sha256((event_type+"|"+username+"|"+project+"|"+tenant).encode()).hexdigest()

def enqueue(event_type, actor="", username="", project="", tenant="", payload=None, dedupe_seconds=30):
    ensure_schema()
    event_type = str(event_type or "").strip()
    if event_type not in ALLOWED_EVENTS:
        raise ValueError("event_type não permitido")
    username = str(username or "").strip()[:200]
    project = _safe_slug(project)
    tenant = _safe_slug(tenant)
    actor = str(actor or "portal").strip()[:200]
    payload = payload if isinstance(payload, dict) else {}
    if _contains_secret(payload): raise ValueError("payload contém campo sensível")
    created = now_utc(); partition_key=_partition(event_type,username,project,tenant); coalesce_key=_coalesce(event_type,username,project,tenant)
    con = connect()
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=max(0, int(dedupe_seconds)))).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    old = con.execute("""
      SELECT request_id,status,message,created_at FROM reconcile_requests
      WHERE event_type=? AND username=? AND project=? AND tenant=?
        AND created_at>=? AND status IN ('queued','running','ready','waiting')
      ORDER BY created_at DESC LIMIT 1
    """, (event_type, username, project, tenant, cutoff)).fetchone()
    if old:
        con.close()
        return {"ok": True, "deduplicated": True, **dict(old), "event_type": event_type}
    request_id = str(uuid.uuid4())
    con.execute("""
      INSERT INTO reconcile_requests(
        request_id,created_at,event_type,actor,username,project,tenant,status,message,payload_json,result_json,
        attempt_count,max_attempts,next_attempt_at,partition_key,coalesce_key
      ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (request_id, created, event_type, actor, username, project, tenant, "queued", "Mensagem recebida pela interface.", json.dumps(payload, ensure_ascii=False), "{}",0,5,created,partition_key,coalesce_key))
    con.commit(); con.close()
    QUEUE.mkdir(parents=True, exist_ok=True)
    marker = {"request_id": request_id, "created_at": created, "event_type": event_type}
    fd, tmp_name = tempfile.mkstemp(prefix=".reconcile-", suffix=".tmp", dir=str(QUEUE))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(marker, f, ensure_ascii=False)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp_name, QUEUE / f"{request_id}.json")
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
    return {"ok": True, "deduplicated": False, "request_id": request_id, "status": "queued", "event_type": event_type, "created_at": created}


def status(request_id):
    ensure_schema()
    con = connect()
    row = con.execute("SELECT * FROM reconcile_requests WHERE request_id=?", (str(request_id),)).fetchone()
    con.close()
    return dict(row) if row else None


def recent(project="", limit=20):
    ensure_schema()
    limit = max(1, min(int(limit), 100))
    con = connect()
    if project:
        rows = con.execute("SELECT * FROM reconcile_requests WHERE project=? ORDER BY created_at DESC LIMIT ?", (_safe_slug(project), limit)).fetchall()
    else:
        rows = con.execute("SELECT * FROM reconcile_requests ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def ensure_user(user):
    if not isinstance(user, dict):
        return None
    username = str(user.get("username") or user.get("email") or "").strip()
    if not username:
        return None
    ensure_schema()
    con = connect()
    exists = con.execute("SELECT 1 FROM release_users WHERE username=?", (username,)).fetchone()
    con.close()
    if exists:
        return {"ok": True, "status": "ready", "deduplicated": True, "username": username}
    groups = user.get("groups") or []
    if isinstance(groups, str):
        groups = [x.strip() for x in groups.split(",") if x.strip()]
    return enqueue("user.created", actor=username, username=username, payload={"email": user.get("email") or "", "groups": groups}, dedupe_seconds=3600)
