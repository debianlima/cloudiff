#!/usr/bin/env python3
import html
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if "/srv/cloudif/lib" not in sys.path:
    sys.path.insert(0, "/srv/cloudif/lib")
import cloudif_reconcile_client as reconcile_client
import cloudif_release_manager as release_manager

DB = os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db")
HOST = os.environ.get("CLOUDIF_DEPLOY_PANEL_HOST", "10.62.92.7")
PORT = int(os.environ.get("CLOUDIF_DEPLOY_PANEL_PORT", "18099"))
KOMODO_AGENT = os.environ.get("CLOUDIF_KOMODO_AGENT_URL", "http://10.62.91.2:18098").rstrip("/")

DEFAULT_PROJECT = os.environ.get("CLOUDIF_DEFAULT_PROJECT", "sistema-de-biblioteca-teste")
DEFAULT_TENANT = os.environ.get("CLOUDIF_DEFAULT_TENANT", "iff1742962")
BASE_PATH = "/cloudif/portal/deploy/"

def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def ensure_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB, timeout=25)
    cur = con.cursor()
    cur.execute("PRAGMA busy_timeout=25000")
    try:
        cur.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass

    cur.execute("""
        CREATE TABLE IF NOT EXISTS deploy_state (
            project TEXT PRIMARY KEY,
            tenant TEXT,
            mode TEXT,
            commit_sha TEXT,
            commit_short TEXT,
            commit_message TEXT,
            actor TEXT,
            updated_at TEXT,
            response_json TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS deployments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            project TEXT,
            tenant TEXT,
            actor TEXT,
            action TEXT,
            status TEXT,
            message TEXT,
            commit_sha TEXT,
            commit_short TEXT,
            mode TEXT,
            response_json TEXT
        )
    """)

    cols = {r[1] for r in cur.execute("PRAGMA table_info(deployments)").fetchall()}
    for name, typ in [
        ("commit_sha", "TEXT"),
        ("commit_short", "TEXT"),
        ("mode", "TEXT"),
    ]:
        if name not in cols:
            cur.execute(f"ALTER TABLE deployments ADD COLUMN {name} {typ}")

    con.commit()
    con.close()

def db_exec(sql, params=()):
    con = sqlite3.connect(DB, timeout=25)
    con.execute("PRAGMA busy_timeout=25000")
    cur = con.cursor()
    cur.execute(sql, params)
    con.commit()
    con.close()

def db_one(sql, params=()):
    con = sqlite3.connect(DB, timeout=25)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=25000")
    row = con.execute(sql, params).fetchone()
    con.close()
    return dict(row) if row else None

def db_all(sql, params=()):
    con = sqlite3.connect(DB, timeout=25)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=25000")
    rows = [dict(r) for r in con.execute(sql, params).fetchall()]
    con.close()
    return rows

def h(s):
    return html.escape("" if s is None else str(s))

def http_json(method, url, payload=None, timeout=90):
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "CloudIF-DeployCenter-v54",
    }

    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                parsed = json.loads(raw) if raw else {}
            except Exception:
                parsed = {"raw": raw[:4000]}
            return {"ok": True, "status": r.status, "data": parsed}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw[:4000]}
        return {"ok": False, "status": e.code, "data": parsed}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e), "data": {}}

def get_actor(headers):
    return (
        headers.get("X-authentik-username")
        or headers.get("X-Authentik-Username")
        or headers.get("X-authentik-email")
        or headers.get("X-Forwarded-User")
        or "portal"
    )

def get_groups(headers):
    return (
        headers.get("X-authentik-groups")
        or headers.get("X-Authentik-Groups")
        or ""
    )


def authenticated_actor(headers):
    return (
        headers.get("X-authentik-username")
        or headers.get("X-Authentik-Username")
        or headers.get("X-authentik-email")
        or headers.get("X-Forwarded-User")
        or ""
    ).strip()


def valid_origin(handler):
    origin = (handler.headers.get("Origin") or "").strip()
    referer = (handler.headers.get("Referer") or "").strip()
    host = (handler.headers.get("X-Forwarded-Host") or handler.headers.get("Host") or "").split(",")[0].strip().lower()
    candidate = origin or referer
    if not candidate:
        return handler.client_address[0] in {"127.0.0.1", "10.62.91.3", "10.62.92.7"}
    try:
        return urllib.parse.urlparse(candidate).netloc.lower() == host
    except Exception:
        return False

def get_commits(project):
    url = KOMODO_AGENT + "/komodo/project/commits?project=" + urllib.parse.quote(project) + "&limit=20"
    res = http_json("GET", url, timeout=40)
    if res.get("ok") and isinstance(res.get("data"), dict):
        return res["data"].get("items", []), res
    return [], res

def get_status():
    return http_json("GET", KOMODO_AGENT + "/status", timeout=30)

def stack_info(status, project):
    name = project if project.startswith("cloudif-") else "cloudif-" + project
    data = status.get("data", {}) if isinstance(status, dict) else {}
    stacks = (((data.get("stacks") or {}).get("data")) or [])
    for st in stacks:
        if st.get("name") == name:
            return st
    return stacks[0] if stacks else {}

def current_mode(project):
    state = db_one("SELECT * FROM deploy_state WHERE project=?", (project,))
    return state or {
        "project": project,
        "tenant": "",
        "mode": "git_main",
        "commit_sha": "",
        "commit_short": "",
        "commit_message": "",
        "actor": "",
        "updated_at": "",
        "response_json": "",
    }

def save_state(project, tenant, mode, actor, commit_sha="", commit_message="", response=None):
    commit_short = (commit_sha or "")[:7]
    db_exec("""
        INSERT INTO deploy_state(project, tenant, mode, commit_sha, commit_short, commit_message, actor, updated_at, response_json)
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(project) DO UPDATE SET
            tenant=excluded.tenant,
            mode=excluded.mode,
            commit_sha=excluded.commit_sha,
            commit_short=excluded.commit_short,
            commit_message=excluded.commit_message,
            actor=excluded.actor,
            updated_at=excluded.updated_at,
            response_json=excluded.response_json
    """, (
        project, tenant, mode, commit_sha, commit_short, commit_message,
        actor, now(), json.dumps(response or {}, ensure_ascii=False)
    ))

def record(project, tenant, actor, action, status, message, commit_sha="", mode="", response=None):
    db_exec("""
        INSERT INTO deployments(created_at, project, tenant, actor, action, status, message, commit_sha, commit_short, mode, response_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
    """, (
        now(), project, tenant, actor, action, status, message,
        commit_sha or "", (commit_sha or "")[:7], mode or "",
        json.dumps(response or {}, ensure_ascii=False)
    ))

def discover_projects():
    queries = [
        "SELECT slug, name, tenant, repo_url FROM projects ORDER BY updated_at DESC LIMIT 100",
        "SELECT slug, title AS name, tenant, repo_url FROM projects ORDER BY updated_at DESC LIMIT 100",
        "SELECT slug, name, tenant FROM projects ORDER BY slug LIMIT 100",
        "SELECT slug, name FROM projects ORDER BY slug LIMIT 100",
    ]
    for q in queries:
        try:
            rows = db_all(q)
            if rows:
                return rows
        except Exception:
            pass
    return []

def action_url():
    return BASE_PATH + "action"

def self_url(project="", tenant="", msg=""):
    q = {}
    if project:
        q["project"] = project
    if tenant:
        q["tenant"] = tenant
    if msg:
        q["msg"] = msg
    return BASE_PATH + ("?" + urllib.parse.urlencode(q) if q else "")

def page(project, tenant, actor, groups, msg=""):
    ensure_db()

    commits, commits_res = get_commits(project)
    status = get_status()
    st = stack_info(status, project)
    info = st.get("info", {}) if isinstance(st, dict) else {}
    mode = current_mode(project)
    history = db_all("""
        SELECT * FROM deployments
        WHERE project=?
        ORDER BY id DESC
        LIMIT 20
    """, (project,))
    reconcile_history = reconcile_client.recent(project, 15)
    release_history = release_manager.recent(project, 20)
    default_schedule = (time.strftime("%Y-%m-%dT%H:%M", time.gmtime(time.time() + 300)))

    is_file_contents = bool(info.get("file_contents"))
    komodo_mode = "rollback por conteúdo" if is_file_contents else "Git/branch"

    state_badge = "ok" if info.get("state") == "running" else "err"
    missing = info.get("missing_files") or []
    services = info.get("services") or []

    commit_rows = []
    for c in commits:
        sha = c.get("sha", "")
        short = c.get("short") or sha[:7]
        message = (c.get("message") or "").splitlines()[0]
        author = c.get("author", "")
        date = c.get("date", "")
        url = c.get("html_url", "")
        btn_disabled = "" if sha else "disabled"

        commit_rows.append(f"""
        <tr>
          <td><code>{h(short)}</code></td>
          <td>{h(message)}</td>
          <td>{h(author)}<br><small>{h(date)}</small></td>
          <td>
            <a class="linkbtn" href="{h(url)}" target="_blank">Abrir commit</a>
            <form method="post" action="{h(action_url())}" style="display:inline" onsubmit="return confirm('Confirmar rollback para este commit?');">
              <input type="hidden" name="action" value="rollback-filecontents">
              <input type="hidden" name="project" value="{h(project)}">
              <input type="hidden" name="tenant" value="{h(tenant)}">
              <input type="hidden" name="commit" value="{h(sha)}">
              <input type="hidden" name="message" value="{h(message)}">
              <button class="btn danger" {btn_disabled}>Rollback</button>
            </form>
          </td>
        </tr>
        """)

    if not commit_rows:
        commit_rows.append(f"""
        <tr><td colspan="4">Não foi possível listar commits. Verifique se o Komodo Agent está online. Resposta: <code>{h(commits_res)}</code></td></tr>
        """)
    commit_options = []
    for c in commits:
        sha = c.get("sha", "")
        if sha:
            label = (c.get("short") or sha[:7]) + " — " + ((c.get("message") or "").splitlines()[0][:100])
            commit_options.append(f'<option value="{h(sha)}">{h(label)}</option>')

    service_rows = []
    for s in services:
        service_rows.append(f"""
        <tr>
          <td>{h(s.get("service"))}</td>
          <td>{h(s.get("image"))}</td>
          <td>{h(s.get("update_available"))}</td>
        </tr>
        """)
    if not service_rows:
        service_rows.append("<tr><td colspan='3'>Nenhum serviço listado.</td></tr>")

    hist_rows = []
    for r in history:
        status_class = "ok" if r.get("status") == "ok" else "err"
        hist_rows.append(f"""
        <tr>
          <td>{h(r.get("created_at"))}</td>
          <td>{h(r.get("actor"))}</td>
          <td>{h(r.get("action"))}</td>
          <td><span class="badge {status_class}">{h(r.get("status"))}</span></td>
          <td><code>{h(r.get("commit_short"))}</code></td>
          <td>{h(r.get("mode"))}</td>
          <td>{h(r.get("message"))}</td>
        </tr>
        """)
    if not hist_rows:
        hist_rows.append("<tr><td colspan='7'>Nenhum histórico registrado ainda.</td></tr>")

    reconcile_rows = []
    for r in reconcile_history:
        status_class = "ok" if r.get("status") == "ready" else ("err" if r.get("status") == "failed" else "info")
        reconcile_rows.append(f"""
        <tr>
          <td>{h(r.get("created_at"))}</td>
          <td><code>{h((r.get("request_id") or "")[:8])}</code></td>
          <td>{h(r.get("event_type"))}</td>
          <td><span class="badge {status_class}">{h(r.get("status"))}</span></td>
          <td>{h(r.get("message"))}</td>
        </tr>
        """)
    if not reconcile_rows:
        reconcile_rows.append("<tr><td colspan='5'>Nenhuma mensagem de reconciliação para este projeto.</td></tr>")

    release_rows = []
    for r in release_history:
        release_status = r.get("status") or ""
        status_class = "ok" if release_status in {"published", "validated"} else ("err" if release_status in {"failed", "deployed_unfinalized"} else "info")
        cancel = ""
        if release_status in {"scheduled", "retry"}:
            cancel = f"""
            <form method="post" action="{h(BASE_PATH)}release/cancel" style="display:inline" onsubmit="return confirm('Cancelar esta publicação programada?');">
              <input type="hidden" name="job_id" value="{h(r.get('id'))}">
              <input type="hidden" name="project" value="{h(project)}">
              <input type="hidden" name="tenant" value="{h(tenant)}">
              <button class="btn danger" type="submit">Cancelar</button>
            </form>
            """
        release_rows.append(f"""
        <tr>
          <td>{h(r.get("scheduled_at"))}</td>
          <td><code>{h(r.get("version"))}</code></td>
          <td><code>{h((r.get("commit_sha") or "")[:7])}</code></td>
          <td><span class="badge {status_class}">{h(release_status)}</span></td>
          <td>{h("sim" if r.get("dry_run") else "não")}</td>
          <td>{h(r.get("migration_applied"))}/{h(r.get("migration_count"))}</td>
          <td>{h(r.get("message"))}<br>{cancel}</td>
        </tr>
        """)
    if not release_rows:
        release_rows.append("<tr><td colspan='7'>Nenhuma release programada.</td></tr>")

    mode_label = {
        "git_main": "Git main",
        "rollback_filecontents": "Rollback por conteúdo",
    }.get(mode.get("mode"), mode.get("mode") or "Git main")

    project_options = []
    for p in discover_projects():
        slug = p.get("slug") or ""
        name = p.get("name") or slug
        t = p.get("tenant") or tenant
        selected = "selected" if slug == project else ""
        project_options.append(f'<option value="{h(slug)}" data-tenant="{h(t)}" {selected}>{h(slug)} — {h(name)}</option>')

    msg_html = f'<div class="notice">{h(msg)}</div>' if msg else ""
    komodo_alert = ""
    if not status.get("ok"):
        komodo_alert = f"""
        <div class="notice warn">
          Komodo Agent não respondeu corretamente. O portal principal continua funcionando.
          Detalhe: {h(status.get("error") or status.get("status") or status)}
        </div>
        """

    html_out = f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CloudIF Deploy Center</title>
<style>
:root {{
  --if-green:#17882c;
  --if-green-dark:#0f5f1f;
  --if-red:#c8191e;
  --if-gray:#f4f6f5;
  --if-text:#1f2937;
  --muted:#6b7280;
}}
body {{
  margin:0;
  font-family: Arial, Helvetica, sans-serif;
  background:var(--if-gray);
  color:var(--if-text);
}}
header {{
  background:white;
  border-bottom:4px solid var(--if-green);
  padding:16px 24px;
  display:flex;
  align-items:center;
  gap:14px;
}}
.logo-grid {{
  width:34px;
  display:grid;
  grid-template-columns:repeat(2, 13px);
  gap:4px;
}}
.logo-grid span {{
  width:13px;
  height:13px;
  background:var(--if-green);
  border-radius:3px;
}}
.logo-grid span.red {{ background:var(--if-red); border-radius:50%; }}
header h1 {{ margin:0; font-size:22px; }}
header small {{ display:block; color:#4b5563; margin-top:3px; }}
nav {{
  background:#0f5f1f;
  padding:10px 24px;
}}
nav a {{
  color:white;
  text-decoration:none;
  margin-right:12px;
  padding:8px 10px;
  border-radius:8px;
  display:inline-block;
}}
nav a.active, nav a:hover {{
  background:#17882c;
}}
main {{ max-width:1240px; margin:24px auto; padding:0 18px; }}
.card {{
  background:white;
  border-radius:14px;
  box-shadow:0 8px 24px rgba(0,0,0,.08);
  padding:20px;
  margin-bottom:18px;
}}
.grid {{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
  gap:14px;
}}
.box {{
  border:1px solid #e5e7eb;
  border-radius:12px;
  padding:14px;
  background:#fbfbfb;
}}
.btn, .linkbtn {{
  border:0;
  border-radius:8px;
  background:var(--if-green);
  color:white;
  padding:8px 11px;
  font-weight:bold;
  cursor:pointer;
  margin:3px;
  text-decoration:none;
  display:inline-block;
  font-size:13px;
}}
.btn.secondary, .linkbtn {{ background:#374151; }}
.btn.warn {{ background:#b45309; }}
.btn.danger {{ background:var(--if-red); }}
.btn:disabled {{ opacity:.45; cursor:not-allowed; }}
.badge {{
  display:inline-block;
  padding:4px 8px;
  border-radius:999px;
  background:#e8f5e9;
  color:var(--if-green-dark);
  font-weight:bold;
  font-size:12px;
}}
.badge.err {{ background:#fee2e2; color:#991b1b; }}
.badge.info {{ background:#e0f2fe; color:#075985; }}
.notice {{
  background:#ecfdf5;
  border:1px solid #bbf7d0;
  color:#14532d;
  padding:12px;
  border-radius:10px;
  margin-bottom:16px;
}}
.notice.warn {{
  background:#fff7ed;
  border-color:#fed7aa;
  color:#9a3412;
}}
table {{
  width:100%;
  border-collapse:collapse;
  margin-top:12px;
}}
th,td {{
  border-bottom:1px solid #e5e7eb;
  padding:9px;
  text-align:left;
  vertical-align:top;
}}
th {{ background:#f9fafb; }}
input, select {{
  padding:9px;
  border:1px solid #d1d5db;
  border-radius:8px;
  box-sizing:border-box;
}}
label {{ font-weight:bold; display:block; margin-top:8px; }}
small {{ color:var(--muted); }}
code {{
  background:#f3f4f6;
  border-radius:5px;
  padding:2px 5px;
}}
.actions {{
  display:flex;
  flex-wrap:wrap;
  align-items:center;
  gap:8px;
}}
footer {{
  text-align:center;
  color:#6b7280;
  padding:24px;
}}
</style>
<script>
function openSelectedProject() {{
  const sel = document.getElementById("project_select");
  const tenantInput = document.getElementById("tenant_manual");
  const slug = sel.value;
  const opt = sel.options[sel.selectedIndex];
  const tenant = tenantInput.value || opt.getAttribute("data-tenant") || "";
  window.location.href = "{BASE_PATH}?project=" + encodeURIComponent(slug) + "&tenant=" + encodeURIComponent(tenant);
}}
</script>
</head>
<body>
<header>
  <div class="logo-grid">
    <span></span><span class="red"></span>
    <span></span><span></span>
    <span></span><span></span>
  </div>
  <div>
    <h1>CloudIF Deploy Center</h1>
    <small>Deploy, rollback por commit e retorno ao Git main</small>
  </div>
</header>

<nav>
  <a href="/cloudif/portal/">Portal</a>
  <a class="active" href="{h(BASE_PATH)}?project={h(project)}&tenant={h(tenant)}">Deploy / Komodo</a>
  <a href="https://cloudiff.duckdns.org/git/user/oauth2/Authentik/" target="_blank">Git</a>
  <a href="https://komodoiff.duckdns.org/auth/oidc/login" target="_blank">Komodo</a>
</nav>

<main>
{msg_html}
{komodo_alert}

<section class="card">
  <h2>Projeto integrado</h2>
  <div class="grid">
    <div class="box">
      <strong>Projeto</strong><br>
      <code>{h(project)}</code><br><br>
      <strong>Tenant</strong><br>
      <code>{h(tenant)}</code>
    </div>

    <div class="box">
      <strong>Modo registrado no Portal</strong><br>
      <span class="badge info">{h(mode_label)}</span><br><br>
      <strong>Commit registrado</strong><br>
      <code>{h(mode.get("commit_short") or "-")}</code><br>
      <small>{h(mode.get("commit_message") or "")}</small><br>
      <small>Atualizado por {h(mode.get("actor") or "-")} em {h(mode.get("updated_at") or "-")}</small>
    </div>

    <div class="box">
      <strong>Estado Komodo</strong><br>
      <span class="badge {state_badge}">{h(info.get("state") or "desconhecido")}</span>
      <span class="badge info">{h(info.get("status") or "-")}</span><br><br>
      <strong>Modo Komodo</strong><br>
      <code>{h(komodo_mode)}</code><br>
      <small>file_contents={h(info.get("file_contents"))}</small>
    </div>

    <div class="box">
      <strong>Git/Hash Komodo</strong><br>
      repo: <code>{h(info.get("repo") or "-")}</code><br>
      branch: <code>{h(info.get("branch") or "-")}</code><br>
      deployed: <code>{h(info.get("deployed_hash") or "-")}</code><br>
      latest: <code>{h(info.get("latest_hash") or "-")}</code><br>
      missing: <code>{h(", ".join(missing) if missing else "-")}</code>
    </div>
  </div>

  <h3>Ações principais</h3>
  <div class="actions">
    <a class="linkbtn" href="https://cloudiff.duckdns.org/git/user/oauth2/Authentik/" target="_blank">Abrir Git</a>
    <a class="linkbtn" href="https://komodoiff.duckdns.org/auth/oidc/login" target="_blank">Abrir Komodo</a>

    <form method="post" action="{h(action_url())}" onsubmit="return confirm('Confirmar retorno ao Git main?');">
      <input type="hidden" name="action" value="return-git-main">
      <input type="hidden" name="project" value="{h(project)}">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      <button class="btn secondary">Voltar ao Git main</button>
    </form>

    <form method="post" action="{h(action_url())}">
      <input type="hidden" name="action" value="deploy">
      <input type="hidden" name="project" value="{h(project)}">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      <button class="btn">Deploy atual</button>
    </form>

    <form method="post" action="{h(action_url())}">
      <input type="hidden" name="action" value="deploy-if-changed">
      <input type="hidden" name="project" value="{h(project)}">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      <button class="btn secondary">Deploy se alterado</button>
    </form>
  </div>
</section>

<section class="card">
  <h2>Escolher projeto do portal</h2>
  <div class="grid">
    <div>
      <label>Projeto</label>
      <select id="project_select">
        {''.join(project_options) or f'<option value="{h(project)}">{h(project)}</option>'}
      </select>
    </div>
    <div>
      <label>Tenant</label>
      <input id="tenant_manual" value="{h(tenant)}">
    </div>
    <div style="align-self:end">
      <button class="btn" onclick="openSelectedProject()">Abrir projeto</button>
    </div>
  </div>
</section>

<section class="card">
  <h2>Serviços da Stack</h2>
  <table>
    <thead><tr><th>Serviço</th><th>Imagem</th><th>Atualização disponível</th></tr></thead>
    <tbody>{''.join(service_rows)}</tbody>
  </table>
</section>

<section class="card">
  <h2>Rollback por commit</h2>
  <p>Este rollback baixa o <code>docker-compose.yml</code> do commit escolhido no Forgejo e aplica a Stack em modo <code>file_contents</code>. O commit aplicado é registrado no SQLite do Portal.</p>

  <table>
    <thead>
      <tr>
        <th>Commit</th>
        <th>Mensagem</th>
        <th>Autor/Data</th>
        <th>Ações</th>
      </tr>
    </thead>
    <tbody>{''.join(commit_rows)}</tbody>
  </table>
</section>

<section class="card">
  <h2>Reconciliação automática</h2>
  <p>A interface envia uma mensagem quando usuário, projeto, repositório ou tenant é criado. O worker inicia sob demanda, atualiza o status e encerra.</p>
  <form method="post" action="{h(BASE_PATH)}reconcile" class="actions">
    <input type="hidden" name="event_type" value="reconcile.requested">
    <input type="hidden" name="project" value="{h(project)}">
    <input type="hidden" name="tenant" value="{h(tenant)}">
    <button class="btn secondary" type="submit">Reconciliar agora</button>
  </form>
  <table>
    <thead><tr><th>Recebido</th><th>Requisição</th><th>Evento</th><th>Status</th><th>Mensagem</th></tr></thead>
    <tbody>{''.join(reconcile_rows)}</tbody>
  </table>
</section>

<section class="card">
  <h2>Versionamento e publicação programada</h2>
  <p>O commit é validado no Forgejo. Na publicação real, o fluxo exige backup do tenant, aplica migrações Supabase pendentes, publica o commit exato pelo Komodo e finaliza a release.</p>
  <form method="post" action="{h(BASE_PATH)}release/schedule" onsubmit="return confirm('Confirmar o agendamento desta release?');">
    <div class="grid">
      <div>
        <label>Versão</label>
        <input name="version" placeholder="v0.1.0 — vazio gera próximo patch">
      </div>
      <div>
        <label>Commit</label>
        <select name="commit" required>{''.join(commit_options) or '<option value="">Nenhum commit disponível</option>'}</select>
      </div>
      <div>
        <label>Publicar em UTC</label>
        <input type="datetime-local" name="scheduled_at" value="{h(default_schedule)}" required>
      </div>
      <div>
        <label>Tenant Supabase</label>
        <input name="tenant" value="{h(tenant)}">
      </div>
    </div>
    <label>Notas da release</label>
    <input name="notes" maxlength="4000" placeholder="Resumo das alterações">
    <p><label><input type="checkbox" name="dry_run" value="1" checked> Modo seco: validar sem criar release, migrar ou publicar</label></p>
    <label>Confirmação para publicação real</label>
    <input name="publish_confirm" placeholder="Digite PUBLICAR somente para execução real">
    <input type="hidden" name="project" value="{h(project)}">
    <button class="btn" type="submit">Agendar release</button>
  </form>
  <table>
    <thead><tr><th>Horário UTC</th><th>Versão</th><th>Commit</th><th>Status</th><th>Seco</th><th>Migrações</th><th>Resultado</th></tr></thead>
    <tbody>{''.join(release_rows)}</tbody>
  </table>
</section>

<section class="card">
  <h2>Histórico de deploy/rollback</h2>
  <table>
    <thead>
      <tr>
        <th>Data</th>
        <th>Usuário</th>
        <th>Ação</th>
        <th>Status</th>
        <th>Commit</th>
        <th>Modo</th>
        <th>Mensagem</th>
      </tr>
    </thead>
    <tbody>{''.join(hist_rows)}</tbody>
  </table>
</section>

</main>
<footer>IFFluminense — Campus Bom Jesus do Itabapoana · Portal CloudIF</footer>
</body>
</html>
"""
    return html_out.encode()

def parse_post(handler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length < 0 or length > 16384:
        raise ValueError("request_too_large")
    raw = handler.rfile.read(length).decode("utf-8", "ignore")
    if (handler.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower() == "application/json":
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    parsed = urllib.parse.parse_qs(raw)
    return {k: v[0] if v else "" for k, v in parsed.items()}

class H(BaseHTTPRequestHandler):
    def send_html(self, body, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, url):
        self.send_response(303)
        self.send_header("Location", url)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self):
        ensure_db()

        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        project = qs.get("project", [DEFAULT_PROJECT])[0] or DEFAULT_PROJECT
        tenant = qs.get("tenant", [DEFAULT_TENANT])[0] or DEFAULT_TENANT
        msg = qs.get("msg", [""])[0]

        actor = get_actor(self.headers)
        groups = get_groups(self.headers)

        if parsed.path in ["/", "/index.html", "/cloudif/portal/deploy", "/cloudif/portal/deploy/"]:
            return self.send_html(page(project, tenant, actor, groups, msg))

        if parsed.path in ["/health", "/cloudif/portal/deploy/health"]:
            return self.send_json({"ok": True, "service": "cloudif-deploy-center-v54", "time": now()})

        if parsed.path in ["/api/status", "/cloudif/portal/deploy/api/status"]:
            return self.send_json({
                "ok": True,
                "komodo_agent": KOMODO_AGENT,
                "db": DB,
                "projects": discover_projects(),
                "status": get_status(),
            })

        if parsed.path in ["/api/reconcile/status", "/cloudif/portal/deploy/api/reconcile/status"]:
            if not authenticated_actor(self.headers):
                return self.send_json({"ok": False, "error": "authentication_required"}, 403)
            request_id = qs.get("request_id", qs.get("id", [""]))[0]
            item = reconcile_client.status(request_id)
            return self.send_json({"ok": bool(item), "item": item} if item else {"ok": False, "error": "not_found"}, 200 if item else 404)

        if parsed.path in ["/api/reconcile/recent", "/cloudif/portal/deploy/api/reconcile/recent"]:
            if not authenticated_actor(self.headers):
                return self.send_json({"ok": False, "error": "authentication_required"}, 403)
            project_q = qs.get("project", [project])[0]
            return self.send_json({"ok": True, "items": reconcile_client.recent(project_q, 30)})

        if parsed.path in ["/api/release/status", "/cloudif/portal/deploy/api/release/status"]:
            if not authenticated_actor(self.headers):
                return self.send_json({"ok": False, "error": "authentication_required"}, 403)
            try:
                job_id = int(qs.get("job_id", qs.get("id", ["0"]))[0])
            except Exception:
                return self.send_json({"ok": False, "error": "invalid_job_id"}, 400)
            item = release_manager.get_job(job_id)
            return self.send_json({"ok": bool(item), "item": item} if item else {"ok": False, "error": "not_found"}, 200 if item else 404)

        if parsed.path in ["/api/release/recent", "/cloudif/portal/deploy/api/release/recent"]:
            if not authenticated_actor(self.headers):
                return self.send_json({"ok": False, "error": "authentication_required"}, 403)
            project_q = qs.get("project", [project])[0]
            return self.send_json({"ok": True, "items": release_manager.recent(project_q, 30)})

        return self.send_html(b"not found", 404)

    def do_POST(self):
        ensure_db()
        actor = get_actor(self.headers)

        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ["/release/schedule", "/cloudif/portal/deploy/release/schedule", "/api/release/schedule", "/cloudif/portal/deploy/api/release/schedule"]:
            actor = authenticated_actor(self.headers)
            if not actor:
                return self.send_json({"ok": False, "error": "authentication_required"}, 403)
            if not valid_origin(self):
                return self.send_json({"ok": False, "error": "invalid_origin"}, 403)
            try:
                form = parse_post(self)
                dry_run = str(form.get("dry_run") or "").lower() in {"1", "true", "yes", "on", "sim"}
                if not dry_run and form.get("publish_confirm") != "PUBLICAR":
                    raise ValueError("confirmation_required")
                result = release_manager.schedule(
                    form.get("project") or DEFAULT_PROJECT,
                    form.get("tenant") or "",
                    form.get("version") or "",
                    form.get("commit") or "",
                    form.get("scheduled_at") or "",
                    actor,
                    dry_run=dry_run,
                    notes=form.get("notes") or "",
                )
            except Exception as exc:
                if "/api/" in parsed.path:
                    return self.send_json({"ok": False, "error": type(exc).__name__, "message": str(exc)[:500]}, 400)
                return self.redirect(self_url(form.get("project", DEFAULT_PROJECT) if 'form' in locals() else DEFAULT_PROJECT, form.get("tenant", "") if 'form' in locals() else "", "Falha ao agendar release: " + str(exc)[:240]))
            if result.get("scheduled_at", "") <= now().replace(" ", "T") + "Z":
                try:
                    os.system("systemctl start cloudif-release-dispatch.service >/dev/null 2>&1 &")
                except Exception:
                    pass
            if "/api/" in parsed.path:
                return self.send_json(result, 202)
            msg = "Release " + result["version"] + " agendada no job #" + str(result["job_id"]) + "."
            return self.redirect(self_url(result["project"], result["tenant"], msg))

        if parsed.path in ["/release/cancel", "/cloudif/portal/deploy/release/cancel", "/api/release/cancel", "/cloudif/portal/deploy/api/release/cancel"]:
            actor = authenticated_actor(self.headers)
            if not actor:
                return self.send_json({"ok": False, "error": "authentication_required"}, 403)
            if not valid_origin(self):
                return self.send_json({"ok": False, "error": "invalid_origin"}, 403)
            try:
                form = parse_post(self)
                result = release_manager.cancel(int(form.get("job_id") or 0), actor)
            except Exception as exc:
                result = {"ok": False, "error": type(exc).__name__}
            if "/api/" in parsed.path:
                return self.send_json(result, 200 if result.get("ok") else 409)
            return self.redirect(self_url(form.get("project", DEFAULT_PROJECT), form.get("tenant", ""), "Release cancelada." if result.get("ok") else "Não foi possível cancelar a release."))

        if parsed.path in ["/reconcile", "/cloudif/portal/deploy/reconcile", "/api/reconcile", "/cloudif/portal/deploy/api/reconcile"]:
            actor = authenticated_actor(self.headers)
            if not actor:
                return self.send_json({"ok": False, "error": "authentication_required"}, 403)
            try:
                form = parse_post(self)
                event_type = form.get("event_type") or "reconcile.requested"
                project = form.get("project") or DEFAULT_PROJECT
                tenant = form.get("tenant") or ""
                result = reconcile_client.enqueue(
                    event_type,
                    actor=actor,
                    username=actor,
                    project=project,
                    tenant=tenant,
                    payload={"source": "deploy_panel"},
                    dedupe_seconds=0,
                )
            except Exception as exc:
                return self.send_json({"ok": False, "error": type(exc).__name__}, 400)
            if "/api/" in parsed.path:
                return self.send_json(result, 202)
            msg = "Reconciliação " + (result.get("request_id") or "")[:8] + " recebida com status " + result.get("status", "queued") + "."
            return self.redirect(self_url(project, tenant, msg))

        if parsed.path not in ["/action", "/cloudif/portal/deploy/action"]:
            return self.send_html(b"not found", 404)

        form = parse_post(self)

        action = form.get("action", "")
        project = form.get("project", DEFAULT_PROJECT) or DEFAULT_PROJECT
        tenant = form.get("tenant", DEFAULT_TENANT) or DEFAULT_TENANT
        commit = form.get("commit", "")
        commit_message = form.get("message", "")

        payload = {"project": project, "tenant": tenant, "actor": actor}

        if action == "rollback-filecontents":
            endpoint = KOMODO_AGENT + "/komodo/stack/rollback-filecontents"
            payload["commit"] = commit
            res = http_json("POST", endpoint, payload, timeout=120)
            ok = bool(res.get("ok") and isinstance(res.get("data"), dict) and res["data"].get("ok"))
            status = "ok" if ok else "failed"
            message = (res.get("data") or {}).get("message") or ("Rollback solicitado." if ok else "Rollback falhou.")
            record(project, tenant, actor, action, status, message, commit, "rollback_filecontents", res)

            if ok:
                save_state(project, tenant, "rollback_filecontents", actor, commit, commit_message, res)

            return self.redirect(self_url(project, tenant, message))

        if action == "return-git-main":
            endpoint = KOMODO_AGENT + "/komodo/stack/return-git-main"
            res = http_json("POST", endpoint, payload, timeout=120)
            ok = bool(res.get("ok") and isinstance(res.get("data"), dict) and res["data"].get("ok"))
            status = "ok" if ok else "failed"
            message = (res.get("data") or {}).get("message") or ("Retorno ao Git main solicitado." if ok else "Retorno ao Git main falhou.")
            record(project, tenant, actor, action, status, message, "", "git_main", res)

            if ok:
                save_state(project, tenant, "git_main", actor, "", "Git main", res)

            return self.redirect(self_url(project, tenant, message))

        if action in ["deploy", "deploy-if-changed", "pull", "start", "stop", "restart", "destroy"]:
            endpoint = KOMODO_AGENT + "/komodo/stack/" + action
            res = http_json("POST", endpoint, payload, timeout=120)
            ok = bool(res.get("ok") and isinstance(res.get("data"), dict) and res["data"].get("ok"))
            status = "ok" if ok else "failed"
            message = (res.get("data") or {}).get("message") or ("Ação enviada." if ok else "Ação falhou.")
            record(project, tenant, actor, action, status, message, "", current_mode(project).get("mode", ""), res)
            return self.redirect(self_url(project, tenant, message))

        return self.redirect(self_url(project, tenant, "Ação inválida"))

    def log_message(self, fmt, *args):
        print(time.strftime("[%Y-%m-%dT%H:%M:%S]"), self.client_address[0], fmt % args, flush=True)

if __name__ == "__main__":
    ensure_db()
    print(f"CloudIF Deploy Center v54 ouvindo em {HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
