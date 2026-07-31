#!/usr/bin/env python3
import csv, datetime, json, os, sqlite3, subprocess, urllib.request
from pathlib import Path

BASE = Path(os.environ.get("CLOUDIF_BASE", "/srv/cloudif"))
DB = Path(os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db"))
NODES = os.environ.get("CLOUDIF_NODES", "")

DB.parent.mkdir(parents=True, exist_ok=True)

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS projects(
      slug TEXT PRIMARY KEY,
      name TEXT,
      tenant TEXT,
      owner TEXT,
      description TEXT,
      repo_url TEXT,
      komodo_status TEXT DEFAULT 'not_configured',
      created_at TEXT,
      updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS project_acl(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      slug TEXT,
      subject_type TEXT,
      subject TEXT,
      UNIQUE(slug, subject_type, subject)
    );

    CREATE TABLE IF NOT EXISTS tenant_acl(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant TEXT,
      subject_type TEXT,
      subject TEXT,
      UNIQUE(tenant, subject_type, subject)
    );

    CREATE TABLE IF NOT EXISTS tenant_policy(
      tenant TEXT PRIMARY KEY,
      always_alive INTEGER DEFAULT 0,
      keepalive_until TEXT,
      max_hours INTEGER DEFAULT 6,
      updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS settings(
      key TEXT PRIMARY KEY,
      value TEXT,
      description TEXT,
      admin_only INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS action_log(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT,
      actor TEXT,
      action TEXT,
      target TEXT,
      rc INTEGER,
      stdout TEXT,
      stderr TEXT
    );

    CREATE TABLE IF NOT EXISTS node_metrics_cache(
      node TEXT PRIMARY KEY,
      url TEXT,
      ok INTEGER,
      payload TEXT,
      updated_at TEXT
    );
    """)
    defaults = [
        ("SUPABASE_DISABLE_SIGNUP", "false", "Controla se novos usuários podem se cadastrar no Auth do Supabase."),
        ("SUPABASE_ENABLE_EMAIL_AUTOCONFIRM", "true", "Confirma e-mail automaticamente em ambiente didático."),
        ("CLOUDIF_MAX_STUDENT_KEEPALIVE_HOURS", "6", "Limite máximo que usuário pode manter banco ligado temporariamente."),
        ("CLOUDIF_ALLOW_GIT_ONLY_PROJECT", "true", "Permite projeto Git/Komodo sem banco Supabase vinculado."),
    ]
    for k, v, d in defaults:
        con.execute(
            "INSERT OR IGNORE INTO settings(key,value,description,admin_only) VALUES(?,?,?,1)",
            (k, v, d),
        )
    con.commit()
    con.close()

def fetch_json(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return {"ok": True, "data": json.loads(r.read().decode())}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def refresh_nodes():
    con = db()
    for item in NODES.split(","):
        if "=" not in item:
            continue
        name, url = item.split("=", 1)
        name = name.strip()
        url = url.strip().rstrip("/") + "/metrics"
        result = fetch_json(url, 5)
        payload = result.get("data") if result.get("ok") else result
        con.execute("""
          INSERT INTO node_metrics_cache(node,url,ok,payload,updated_at)
          VALUES(?,?,?,?,?)
          ON CONFLICT(node) DO UPDATE SET
            url=excluded.url,
            ok=excluded.ok,
            payload=excluded.payload,
            updated_at=excluded.updated_at
        """, (name, url, 1 if result.get("ok") else 0, json.dumps(payload, ensure_ascii=False), now_iso()))
    con.commit()
    con.close()

def tenants_registry():
    reg = BASE / "registry" / "tenants.csv"
    if not reg.exists():
        return []
    with reg.open(errors="ignore") as f:
        return list(csv.DictReader(f))

def refresh_tenants():
    con = db()
    for r in tenants_registry():
        tenant = r.get("tenant") or ""
        if not tenant:
            continue
        con.execute("""
          INSERT OR IGNORE INTO tenant_policy(tenant,always_alive,max_hours,updated_at)
          VALUES(?,0,6,?)
        """, (tenant, now_iso()))
        if tenant in ["akadmin"]:
            con.execute("""
              UPDATE tenant_policy
              SET always_alive=1, max_hours=24, updated_at=?
              WHERE tenant=?
            """, (now_iso(), tenant))
    con.commit()
    con.close()

def main():
    init_db()
    refresh_tenants()
    refresh_nodes()
    print("OK: cache atualizado", now_iso())

if __name__ == "__main__":
    main()
