
# CloudIF v61 modular lib path BEGIN
import sys as _cloudif_mod_sys
if "/srv/cloudif/staging/lib" not in _cloudif_mod_sys.path:
    _cloudif_mod_sys.path.insert(0, "/srv/cloudif/staging/lib")
# CloudIF v61 modular lib path END

#!/usr/bin/env python3
import csv
import datetime
import html
import json
import os
import re
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request
import sys
sys.path.insert(0, '/srv/cloudif/staging/lib')

# CloudIF v57 lib path BEGIN
import sys as _cloudif_sys
if "/srv/cloudif/staging/lib" not in _cloudif_sys.path:
    _cloudif_sys.path.insert(0, "/srv/cloudif/staging/lib")
# CloudIF v57 lib path END

import cloudif_git_komodo_module as gk
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("CLOUDIF_PORTAL_HOST", "0.0.0.0")
PORT = int(os.environ.get("CLOUDIF_PORTAL_PORT", "18094"))
BASE = Path(os.environ.get("CLOUDIF_BASE", "/srv/cloudif"))
PUBLIC_HOST = os.environ.get("CLOUDIF_PUBLIC_HOST", "cloudiff.duckdns.org")
BASE_PATH = os.environ.get("CLOUDIF_PORTAL_BASE_PATH", "/cloudif/portal").rstrip("/")
DB = Path(os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db"))
AD_AGENT_URL = os.environ.get("CLOUDIF_AD_AGENT_URL", "")
NODES = os.environ.get("CLOUDIF_NODES", "")

if BASE_PATH == "/":
    BASE_PATH = ""

DB.parent.mkdir(parents=True, exist_ok=True)

# Cores baseadas na logo enviada:
# verde IF aproximado: #2f9338 / #168821
# vermelho da bolinha: #c80808
# texto escuro: #2b2723

CSS = r"""
:root{
  --if-green:#2f9338;
  --if-green-strong:#168821;
  --if-green-dark:#086018;
  --if-red:#c80808;
  --if-text:#2b2723;
  --bg:#f5f7f4;
  --card:#ffffff;
  --line:#dfe8dd;
  --soft:#f9fbf8;
  --muted:#66736a;
  --blue:#1d4ed8;
  --amber:#b45309;
  --danger:#b91c1c;
}
*{box-sizing:border-box}
body{
  margin:0;
  background:var(--bg);
  color:var(--if-text);
  font-family:Arial, Helvetica, sans-serif;
}
.header{
  background:#fff;
  border-bottom:5px solid var(--if-green);
}
.header-inner{
  max-width:1380px;
  margin:auto;
  padding:18px 24px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:18px;
}
.brand{
  display:flex;
  align-items:center;
  gap:18px;
}
.if-mark{
  width:72px;
  height:92px;
  display:grid;
  grid-template-columns:repeat(3,18px);
  grid-template-rows:repeat(4,18px);
  gap:6px;
  align-content:start;
}
.if-dot{
  width:18px;
  height:18px;
  border-radius:50%;
  background:var(--if-red);
}
.if-block{
  width:18px;
  height:18px;
  border-radius:4px;
  background:var(--if-green);
}
.if-empty{width:18px;height:18px}
.brand-title h1{
  margin:0;
  font-size:26px;
  color:var(--if-text);
  letter-spacing:.2px;
}
.brand-title p{
  margin:4px 0 0;
  font-size:14px;
  color:#455046;
}
.inst-badge{
  padding:9px 13px;
  border:1px solid var(--line);
  background:#f8fbf8;
  border-radius:999px;
  color:var(--if-green-dark);
  font-weight:700;
  font-size:13px;
}
.wrap{
  max-width:1380px;
  margin:22px auto;
  padding:0 18px;
}
.card{
  background:var(--card);
  border:1px solid var(--line);
  border-radius:16px;
  padding:18px;
  margin:14px 0;
  box-shadow:0 8px 22px rgba(20,40,20,.05);
}
.userbar{
  display:flex;
  justify-content:space-between;
  gap:16px;
  flex-wrap:wrap;
}
.tabs{
  display:flex;
  gap:8px;
  flex-wrap:wrap;
  margin:14px 0;
}
.tabs a{
  text-decoration:none;
  background:#fff;
  color:var(--if-text);
  border:1px solid var(--line);
  padding:11px 14px;
  border-radius:12px;
  font-weight:700;
}
.tabs a.active{
  background:var(--if-green);
  color:white;
  border-color:var(--if-green);
}
.grid{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
  gap:14px;
}
.grid2{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:14px;
}
@media(max-width:900px){.grid2{grid-template-columns:1fr}}
.box{
  background:var(--soft);
  border:1px solid var(--line);
  border-radius:14px;
  padding:14px;
}
.box h3{margin:0 0 8px}
.kpi{
  color:var(--if-green-dark);
  font-weight:800;
  font-size:34px;
}
.help{
  background:#f0fbf1;
  border-left:5px solid var(--if-green);
  border-radius:12px;
  padding:12px;
  margin:10px 0;
}
.warn{
  background:#fff7ed;
  border-left:5px solid #f59e0b;
  border-radius:12px;
  padding:12px;
  margin:10px 0;
}
table{
  width:100%;
  border-collapse:collapse;
  background:white;
  border-radius:12px;
  overflow:hidden;
}
th{
  background:#eef8ef;
  color:#18351d;
  font-size:13px;
}
td,th{
  border-bottom:1px solid #e5e7eb;
  padding:9px;
  text-align:left;
  vertical-align:middle;
}
.btn{
  display:inline-block;
  border:0;
  border-radius:9px;
  padding:9px 12px;
  margin:4px 4px 4px 0;
  background:var(--if-green);
  color:white;
  text-decoration:none;
  cursor:pointer;
  font-weight:700;
}
.btn.gray{background:#374151}
.btn.blue{background:var(--blue)}
.btn.red{background:var(--danger)}
.btn.amber{background:var(--amber)}
.btn.light{background:#e8f5e9;color:#14532d}
input,select,textarea{
  width:100%;
  padding:9px;
  border:1px solid #cbd5c0;
  border-radius:9px;
  margin:4px 0 10px;
  background:white;
}
label{font-weight:700}
.small{font-size:12px;color:var(--muted)}
.pill{
  display:inline-block;
  padding:4px 9px;
  border-radius:999px;
  font-size:12px;
  font-weight:800;
}
.pill.ok{background:#dcfce7;color:#166534}
.pill.bad{background:#fee2e2;color:#991b1b}
.pill.warn{background:#fef3c7;color:#92400e}
.pill.muted{background:#e5e7eb;color:#374151}
pre{
  background:#111827;
  color:#e5e7eb;
  padding:12px;
  border-radius:12px;
  overflow:auto;
  max-height:420px;
}
.footer{
  text-align:center;
  margin:28px 0;
  color:#556;
  font-size:13px;
}
details{
  background:white;
  border:1px solid var(--line);
  border-radius:14px;
  padding:12px;
  margin:12px 0;
}
summary{
  cursor:pointer;
  font-weight:800;
  color:var(--if-green-dark);
}
.wizard-panel{
  display:none;
  margin-top:12px;
}
.wizard-panel.open{
  display:block;
}
.project-card{
  border:1px solid var(--line);
  border-radius:14px;
  background:white;
  padding:14px;
  margin:12px 0;
}
.project-line{
  display:grid;
  grid-template-columns:1.25fr .7fr .9fr auto;
  gap:12px;
  align-items:center;
}
@media(max-width:1000px){.project-line{grid-template-columns:1fr}}
.container-grid{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:8px;
  margin:12px 0;
}
.container-chip{
  border:1px solid var(--line);
  background:white;
  border-radius:12px;
  padding:10px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:8px;
}
.container-name{
  font-weight:800;
}
.section-title{
  display:flex;
  justify-content:space-between;
  gap:12px;
  align-items:center;
  flex-wrap:wrap;
}
.action-group{
  border-top:1px solid var(--line);
  margin-top:12px;
  padding-top:12px;
}
"""

JS = r"""
<script>
function togglePanel(id){
  const el=document.getElementById(id);
  if(!el) return;
  el.classList.toggle('open');
}
function closePanels(prefix){
  document.querySelectorAll('[id^="'+prefix+'"]').forEach(e=>e.classList.remove('open'));
}
</script>
"""

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

def h(x):
    return html.escape(str(x or ""))

def norm(s):
    return (s or "").strip().lower()

def slugify(s):
    s = norm(s)
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = s.strip(".-_")
    return s[:63] or "projeto"

def parse_groups(raw):
    raw = raw or ""
    for sep in [";", "|"]:
        raw = raw.replace(sep, ",")
    return [x.strip() for x in raw.split(",") if x.strip()]

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

    settings = [
      ("CLOUDIF_ADMIN_GROUP","CloudIF-Tenants-Admin","Grupo tratado como administrador do portal.",1),
      ("CLOUDIF_TENANT_CREATOR_GROUPS","CloudIF-Tenants,CloudIF-Professor","Grupos que podem criar/solicitar bancos.",1),
      ("CLOUDIF_ALLOW_NON_ADMIN_CREATE_TENANT","true","Permite que grupos autorizados, além dos admins, criem bancos.",1),
      ("CLOUDIF_ALLOW_GIT_ONLY_PROJECT","true","Permite projeto sem banco, usando apenas Git/Komodo.",1),
      ("CLOUDIF_MAX_STUDENT_KEEPALIVE_HOURS","6","Limite máximo de tempo ligado temporário para banco de aluno.",1),
      ("CLOUDIF_STUDENT_CAN_REPAIR","true","Permite usuário comum acionar reparo do próprio tenant.",1),
      ("CLOUDIF_ALWAYS_ALIVE_ADMIN_ONLY","true","Deixa Sempre ligado restrito a admin.",1),
      ("CLOUDIF_FORGEJO_URL","https://cloudiff.duckdns.org/git","URL pública do Forgejo.",0),
      ("CLOUDIF_KOMODO_URL","https://komodoiff.duckdns.org/","URL pública do Komodo.",0),
    ]
    for k,v,d,a in settings:
        con.execute("""
          INSERT INTO settings(key,value,description,admin_only)
          VALUES(?,?,?,?)
          ON CONFLICT(key) DO UPDATE SET
            description=excluded.description,
            admin_only=excluded.admin_only
        """,(k,v,d,a))
    con.commit()
    con.close()

def setting_value(key, default=""):
    con = db()
    row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    con.close()
    return row["value"] if row else default

def setting_bool(key, default=False):
    v = str(setting_value(key, "true" if default else "false")).lower().strip()
    return v in ["1","true","yes","sim","on"]

def setting_list(key, default=""):
    raw = setting_value(key, default)
    for sep in [";", "|"]:
        raw = raw.replace(sep, ",")
    return [x.strip() for x in raw.split(",") if x.strip()]

def is_admin(groups):
    admin_groups = {x.lower() for x in setting_list("CLOUDIF_ADMIN_GROUP", "CloudIF-Tenants-Admin")}
    current = {x.lower() for x in groups}
    return bool(admin_groups & current) or "domain admins" in current

def can_create_tenant(groups):
    if is_admin(groups):
        return True
    if not setting_bool("CLOUDIF_ALLOW_NON_ADMIN_CREATE_TENANT", True):
        return False
    allowed = {x.lower() for x in setting_list("CLOUDIF_TENANT_CREATOR_GROUPS", "CloudIF-Tenants,CloudIF-Professor")}
    current = {x.lower() for x in groups}
    return bool(allowed & current)

def max_keepalive_hours():
    try:
        return max(1, min(24, int(setting_value("CLOUDIF_MAX_STUDENT_KEEPALIVE_HOURS", "6"))))
    except Exception:
        return 6

def run(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return 999, "", str(e)

def log_action(actor, action, target, rc, out, err):
    con = db()
    con.execute(
        "INSERT INTO action_log(ts,actor,action,target,rc,stdout,stderr) VALUES(?,?,?,?,?,?,?)",
        (now_iso(), actor, action, target, rc, (out or "")[-8000:], (err or "")[-8000:])
    )
    con.commit()
    con.close()

def fmt_bytes(n):
    try:
        n = float(n)
    except Exception:
        return "-"
    for unit in ["B","KB","MB","GB","TB"]:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"

def url(path):
    if path.startswith("http"):
        return path
    if path.startswith("?"):
        return BASE_PATH + "/" + path
    if path.startswith("/"):
        return BASE_PATH + path
    return BASE_PATH + "/" + path

def tenants_registry():
    reg = BASE / "registry" / "tenants.csv"
    rows = []
    if not reg.exists():
        return rows
    with reg.open(errors="ignore") as f:
        for r in csv.DictReader(f):
            if r.get("tenant"):
                rows.append(r)
    return rows

def tenant_visible(tenant, username, groups, con=None):
    if is_admin(groups):
        return True
    if norm(tenant) == norm(username):
        return True

    own = con is None
    if con is None:
        con = db()

    group_set = {g.lower() for g in groups}
    rows = con.execute("SELECT subject_type, subject FROM tenant_acl WHERE tenant=?", (tenant,)).fetchall()

    if own:
        con.close()

    for r in rows:
        if r["subject_type"] == "user" and norm(r["subject"]) == norm(username):
            return True
        if r["subject_type"] == "group" and norm(r["subject"]) in group_set:
            return True
    return False

def visible_tenants(username, groups):
    con = db()
    out = []
    for t in tenants_registry():
        tenant = t.get("tenant") or ""
        if tenant_visible(tenant, username, groups, con):
            out.append(t)
    con.close()
    return out

def user_visible_projects(username, groups):
    con = db()
    rows = con.execute("SELECT * FROM projects ORDER BY updated_at DESC, name").fetchall()
    if is_admin(groups):
        con.close()
        return rows

    out = []
    group_set = {g.lower() for g in groups}

    for p in rows:
        if norm(p["owner"]) == norm(username):
            out.append(p)
            continue

        ok = False
        acl = con.execute("SELECT subject_type, subject FROM project_acl WHERE slug=?", (p["slug"],)).fetchall()
        for a in acl:
            if a["subject_type"] == "user" and norm(a["subject"]) == norm(username):
                ok = True
            if a["subject_type"] == "group" and norm(a["subject"]) in group_set:
                ok = True

        if ok or (p["tenant"] and tenant_visible(p["tenant"], username, groups, con)):
            out.append(p)

    con.close()
    return out

def refresh_tenant_policies():
    con = db()
    for t in tenants_registry():
        tenant = t.get("tenant") or ""
        if tenant:
            con.execute("""
              INSERT OR IGNORE INTO tenant_policy(tenant,always_alive,max_hours,updated_at)
              VALUES(?,0,6,?)
            """, (tenant, now_iso()))
    con.commit()
    con.close()

def compose_services(tenant):
    tdir = BASE / "tenants" / tenant
    if not tdir.is_dir():
        return []

    rc, out, err = run(["bash","-lc",f"cd {str(tdir)!r} && docker compose --env-file .env ps --services"], 20)
    services = [x.strip() for x in out.splitlines() if x.strip()]

    rows = []
    for svc in services:
        rc, cid, err = run(["bash","-lc",f"cd {str(tdir)!r} && docker compose --env-file .env ps -q {svc!r}"], 20)
        cid = cid.strip()
        status = ""
        if cid:
            rc, js, err = run(["bash","-lc",f"docker inspect {cid!r}"], 20)
            try:
                data = json.loads(js)[0]
                st = data.get("State", {})
                status = st.get("Status", "")
                health = (st.get("Health") or {}).get("Status", "")
                if health:
                    status += " " + health
            except Exception:
                status = ""
        rows.append({"service": svc, "status": status})
    return rows

def status_badge(status):
    s = (status or "").lower()
    if "running" in s or "healthy" in s or "up" in s:
        return '<span class="pill ok">ativo</span>'
    if "exited" in s or "dead" in s or "unhealthy" in s:
        return '<span class="pill bad">problema</span>'
    if "restarting" in s:
        return '<span class="pill warn">reiniciando</span>'
    return '<span class="pill muted">parado</span>'

def node_cache():
    con = db()
    rows = con.execute("SELECT * FROM node_metrics_cache ORDER BY node").fetchall()
    con.close()
    out = []
    for r in rows:
        try:
            payload = json.loads(r["payload"] or "{}")
        except Exception:
            payload = {}
        out.append({"node": r["node"], "ok": r["ok"], "updated_at": r["updated_at"], "payload": payload})
    return out

def git_komodo_status():
    rc, out, err = run(["bash","-lc","/srv/cloudif/bin/cloudif-forja-client.py status"], 30)
    try:
        return json.loads(out)
    except Exception:
        return {"ok": False, "rc": rc, "stdout": out, "stderr": err}

def fetch_json(urlx, timeout=8):
    try:
        with urllib.request.urlopen(urlx, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"ok": False, "error": str(e)}

def page(user, tab, body):
    tabs = [
        ("resumo","Resumo"),
        ("projetos","Projetos"),
        ("bancos","Bancos / Tenants"),
        ("git","Git + Komodo"),
        ("admin","Administração"),
        ("ajuda","Ajuda"),
    ]
    nav = "".join(f'<a class="{"active" if tab==k else ""}" href="{url("?tab="+k)}">{v}</a>' for k,v in tabs)
    groups = ", ".join(user["groups"]) or "-"

    return f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CloudIF Portal</title>
<style>{CSS}</style>
{JS}
</head>
<body>
<header class="header">
  <div class="header-inner">
    <div class="brand">
      <div class="if-mark">
        <div class="if-dot"></div><div class="if-block"></div><div class="if-block"></div>
        <div class="if-block"></div><div class="if-block"></div><div class="if-empty"></div>
        <div class="if-block"></div><div class="if-block"></div><div class="if-block"></div>
        <div class="if-block"></div><div class="if-block"></div><div class="if-empty"></div>
      </div>
      <div class="brand-title">
        <h1>CloudIF Portal</h1>
        <p>Instituto Federal Fluminense · Campus Bom Jesus do Itabapoana</p>
      </div>
    </div>
    <div class="inst-badge">Projetos · Bancos · Git · Komodo</div>
  </div>
</header>

<div class="wrap">
  <div class="card userbar">
    <div>
      <b>Usuário:</b> {h(user["username"])}
      &nbsp; <b>Email:</b> {h(user["email"] or "-")}
      &nbsp; <b>Perfil:</b> {"Administrador" if user["admin"] else "Usuário"}<br>
      <span class="small">Grupos Authentik: {h(groups)}</span>
    </div>
    <div>
      <a class="btn light" href="{url("?tab=ajuda")}">Ajuda</a>
      <a class="btn light" href="{url("/action/refresh_cache")}">Atualizar cache</a>
    </div>
  </div>

  <nav class="tabs">{nav}</nav>

  {body}

  <div class="footer">
    Instituto Federal Fluminense · Campus Bom Jesus do Itabapoana<br>
    Portal interno CloudIF para uso didático, gestão de projetos e laboratórios.
  </div>
</div>
</body>
</html>"""

def render_resumo(user):
    projects = user_visible_projects(user["username"], user["groups"])
    tenants = visible_tenants(user["username"], user["groups"])

    body = f"""
<div class="grid">
  <div class="box"><h3>Projetos visíveis</h3><div class="kpi">{len(projects)}</div><p>Projetos que seu usuário ou grupos podem acessar.</p></div>
  <div class="box"><h3>Bancos acessíveis</h3><div class="kpi">{len(tenants)}</div><p>Tenants Supabase autorizados para sua sessão.</p></div>
  <div class="box"><h3>Perfil</h3><div class="kpi">{"ADM" if user["admin"] else "USR"}</div><p>Controle vem dos grupos enviados pelo Authentik.</p></div>
</div>
"""

    if user["admin"]:
        cards = []
        total_mem = used_mem = total_disk = used_disk = 0
        for n in node_cache():
            p = n["payload"] if isinstance(n["payload"], dict) else {}
            mem = p.get("memory", {}) if isinstance(p, dict) else {}
            disk = p.get("disk_root", {}) if isinstance(p, dict) else {}
            docker = p.get("docker", {}) if isinstance(p, dict) else {}
            total_mem += mem.get("total", 0) or 0
            used_mem += mem.get("used", 0) or 0
            total_disk += disk.get("size", 0) or 0
            used_disk += disk.get("used", 0) or 0
            cards.append(f"""
<div class="box">
  <h3>{h(n['node'])}</h3>
  <p>Status: <span class="pill {'ok' if n['ok'] else 'bad'}">{'online' if n['ok'] else 'falha'}</span></p>
  <p><b>RAM:</b> {fmt_bytes(used_mem if False else mem.get('used'))} / {fmt_bytes(mem.get('total'))}</p>
  <p><b>Disco:</b> {fmt_bytes(disk.get('used'))} / {fmt_bytes(disk.get('size'))} ({h(disk.get('pcent'))})</p>
  <p><b>Containers:</b> {h(docker.get('count','-'))}</p>
  <p class="small">Atualizado: {h(n['updated_at'])}</p>
</div>""")

        body += f"""
<div class="card">
  <h2>Servidores CloudIF</h2>
  <div class="grid">
    <div class="box"><h3>RAM agregada</h3><p>{fmt_bytes(used_mem)} / {fmt_bytes(total_mem)}</p></div>
    <div class="box"><h3>Disco agregado</h3><p>{fmt_bytes(used_disk)} / {fmt_bytes(total_disk)}</p></div>
  </div>
  <div class="grid">{''.join(cards) or '<div class="box">Sem cache. Clique em Atualizar cache.</div>'}</div>
</div>"""
    return body

def render_projects(user):
    rows = user_visible_projects(user["username"], user["groups"])
    tenants = visible_tenants(user["username"], user["groups"])

    allow_git_only = setting_bool("CLOUDIF_ALLOW_GIT_ONLY_PROJECT", True)
    tenant_opts = ""
    if allow_git_only:
        tenant_opts += '<option value="">Sem banco: somente Git/Komodo</option>'
    tenant_opts += "".join(f'<option value="{h(t.get("tenant"))}">{h(t.get("tenant"))}</option>' for t in tenants)

    cards = []
    for p in rows:
        forgejo = p["repo_url"] or setting_value("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git")
        komodo = setting_value("CLOUDIF_KOMODO_URL", "https://komodoiff.duckdns.org/")
        edit_id = "edit_" + re.sub(r"[^a-zA-Z0-9_]+", "_", p["slug"])

        cards.append(f"""
<div class="project-card">
  <div class="project-line">
    <div>
      <h3>{h(p['name'])}</h3>
      <p class="small">Slug: {h(p['slug'])}</p>
      <p>{h(p['description'] or 'Sem descrição.')}</p>
    </div>
    <div>
      <b>Banco</b><br>
      <span class="pill {'ok' if p['tenant'] else 'muted'}">{h(p['tenant'] or 'sem banco')}</span>
    </div>
    <div>
      <b>Links</b><br>
      <a href="{h(forgejo)}" target="_blank">Git</a> ·
      <a href="{h(komodo)}" target="_blank">Komodo</a><br>
      <span class="small">Status: {h(p['komodo_status'] or 'not_configured')}</span>
    </div>
    <div>
      <form method="post" action="{url('/action/project_action')}">
        <input type="hidden" name="slug" value="{h(p['slug'])}">
        <button class="btn gray" name="op" value="check">Checar</button>
        <button class="btn blue" name="op" value="sync">Sincronizar</button>
      </form>
      <button class="btn light" onclick="togglePanel('{edit_id}')">Editar</button>
    </div>
  </div>

  <div id="{edit_id}" class="wizard-panel">
    <form method="post" action="{url('/action/project_action')}">
      <input type="hidden" name="slug" value="{h(p['slug'])}">
      <input type="hidden" name="op" value="edit_save">
      <div class="grid2">
        <div>
          <label>Nome</label>
          <input name="name" value="{h(p['name'])}">
        </div>
        <div>
          <label>URL do Git/Forgejo</label>
          <input name="repo_url" value="{h(p['repo_url'])}">
        </div>
      </div>
      <label>Descrição</label>
      <textarea name="description">{h(p['description'])}</textarea>
      <label>Status Komodo</label>
      <input name="komodo_status" value="{h(p['komodo_status'])}">
      <button class="btn" type="submit">Salvar edição</button>
    </form>
  </div>
</div>""")

    return f"""
<div class="card">
  <div class="section-title">
    <div>
      <h2>Projetos</h2>
      <p class="small">Apenas projetos que você pode acessar aparecem aqui.</p>
    </div>
    <button class="btn" onclick="togglePanel('new_project')">Novo projeto</button>
  </div>

  <div id="new_project" class="wizard-panel">
    <div class="help">
      Projeto pode começar sem banco, usando só Git/Komodo. O banco pode ser vinculado depois.
    </div>
    <form method="post" action="{url('/action/create_project')}">
      <label>Nome do projeto</label>
      <input name="name" required placeholder="Ex: Sistema de Biblioteca">
      <label>Descrição</label>
      <textarea name="description" placeholder="Objetivo, turma, disciplina ou grupo responsável"></textarea>
      <label>Banco/Tenant Supabase</label>
      <select name="tenant">{tenant_opts}</select>
      <button class="btn" type="submit">Criar / registrar projeto</button>
    </form>
  </div>

  {''.join(cards) or '<div class="box">Nenhum projeto visível ainda.</div>'}
</div>"""

def render_bancos(user):
    tenants = visible_tenants(user["username"], user["groups"])
    blocks = []
    con = db()

    for t in tenants:
        tenant = t.get("tenant") or ""
        pol = con.execute("SELECT * FROM tenant_policy WHERE tenant=?", (tenant,)).fetchone()
        policy = "-"
        if pol:
            policy = f"Sempre ligado: {'sim' if pol['always_alive'] else 'não'} · Ligado até: {pol['keepalive_until'] or '-'}"

        services = compose_services(tenant)
        chips = []
        for s in services:
            chips.append(f"""
<div class="container-chip">
  <span class="container-name">{h(s['service'])}</span>
  {status_badge(s.get('status'))}
</div>""")

        hours = "".join(f'<option value="{i}">{i} hora{"s" if i > 1 else ""}</option>' for i in range(1, max_keepalive_hours()+1))

        admin_buttons = ""
        if user["admin"]:
            admin_buttons = """
<button class="btn amber" name="op" value="always_on">Sempre ligado</button>
<button class="btn gray" name="op" value="always_off">Desativar sempre ligado</button>
"""

        repair_button = ""
        if user["admin"] or setting_bool("CLOUDIF_STUDENT_CAN_REPAIR", True):
            repair_button = '<button class="btn red" name="op" value="repair">Reparar</button>'

        blocks.append(f"""
<div class="card">
  <div class="section-title">
    <div>
      <h2>{h(tenant)}</h2>
      <p class="small">{h(policy)}</p>
    </div>
    <span class="pill muted">Tenant Supabase</span>
  </div>

  <div class="container-grid">
    {''.join(chips) or '<div class="container-chip"><span class="container-name">sem serviços</span><span class="pill muted">-</span></div>'}
  </div>

  <div class="action-group">
    <form method="post" action="{url('/action/tenant_action')}">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      <button class="btn" name="op" value="start">Iniciar contêiner</button>
      <button class="btn gray" name="op" value="stop">Parar contêiner</button>
      <button class="btn blue" name="op" value="restart">Reiniciar contêiner</button>
      <select name="hours" style="max-width:150px;display:inline-block">{hours}</select>
      <button class="btn" name="op" value="keepalive">Tempo ligado</button>
      {repair_button}
      {admin_buttons}
    </form>
  </div>
</div>""")

    con.close()
    return f"""
<div class="help">
  Esta tela mostra somente o nome do serviço do container e se está ativo.
  Ações avançadas como Sync roles e Render router ficam na Administração.
</div>
{''.join(blocks) or '<div class="card">Nenhum tenant visível.</div>'}"""

def render_git(user):
    status = git_komodo_status()
    projects = user_visible_projects(user["username"], user["groups"])
    forgejo = setting_value("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git")
    komodo = setting_value("CLOUDIF_KOMODO_URL", "https://komodoiff.duckdns.org/")

    rows = []
    for p in projects:
        repo = p["repo_url"] or forgejo
        rows.append(f"""
<tr>
  <td><b>{h(p['name'])}</b><br><span class="small">{h(p['slug'])}</span></td>
  <td><a href="{h(repo)}" target="_blank">Abrir Git</a></td>
  <td><a href="{h(komodo)}" target="_blank">Abrir Komodo</a></td>
  <td><span class="pill muted">{h(p['komodo_status'] or 'not_configured')}</span></td>
  <td>
    <form method="post" action="{url('/action/project_action')}">
      <input type="hidden" name="slug" value="{h(p['slug'])}">
      <button class="btn gray" name="op" value="check">Checar</button>
      <button class="btn blue" name="op" value="sync">Sincronizar</button>
    </form>
  </td>
</tr>""")

    return f"""
<div class="grid">
  <div class="box"><h3>Forgejo</h3><p>Repositório Git do projeto.</p><a class="btn light" href="{h(forgejo)}" target="_blank">Abrir Forgejo</a></div>
  <div class="box"><h3>Komodo</h3><p>Automação e deploy.</p><a class="btn light" href="{h(komodo)}" target="_blank">Abrir Komodo</a></div>
  <div class="box"><h3>Webhook</h3><p>O Forgejo avisa o Forja Agent quando há push.</p></div>
</div>

<div class="card">
  <h2>Projetos integrados</h2>
  <table>
    <tr><th>Projeto</th><th>Git</th><th>Komodo</th><th>Status</th><th>Ações</th></tr>
    {''.join(rows) or '<tr><td colspan="5">Nenhum projeto visível.</td></tr>'}
  </table>
</div>

<div class="card">
  <h2>Diagnóstico geral</h2>
  <form method="post" action="{url('/action/gitkomodo')}">
    <button class="btn gray" name="op" value="status">Checar Forgejo/Komodo agora</button>
  </form>
  <pre>{h(json.dumps(status, ensure_ascii=False, indent=2))}</pre>
</div>"""

def render_admin(user):
    if not user["admin"]:
        return '<div class="card"><h2>Administração</h2><p class="pill bad">Acesso restrito.</p></div>'

    con = db()
    settings = con.execute("SELECT * FROM settings ORDER BY key").fetchall()
    logs = con.execute("SELECT * FROM action_log ORDER BY id DESC LIMIT 40").fetchall()
    con.close()

    settings_rows = ""
    for s in settings:
        settings_rows += f"""
<tr>
  <td><b>{h(s['key'])}</b><br><span class="small">{h(s['description'])}</span></td>
  <td>
    <form method="post" action="{url('/action/admin_setting')}">
      <input type="hidden" name="key" value="{h(s['key'])}">
      <input name="value" value="{h(s['value'])}">
      <button class="btn light" type="submit">Salvar</button>
    </form>
  </td>
</tr>"""

    tenant_opts = "".join(f'<option value="{h(t.get("tenant"))}">{h(t.get("tenant"))}</option>' for t in tenants_registry())
    logs_rows = "".join(f"<tr><td>{h(l['ts'])}</td><td>{h(l['actor'])}</td><td>{h(l['action'])}</td><td>{h(l['target'])}</td><td>{h(l['rc'])}</td></tr>" for l in logs)

    return f"""
<div class="card">
  <h2>Administração</h2>
  <div class="help">
    A autorização de tela usa os grupos vindos do Authentik. A busca direta no AD serve para localizar usuários e grupos.
  </div>

  <div class="grid2">
    <div class="box">
      <h3>Pesquisar usuário/grupo no AD</h3>
      <form method="get" action="{url('/ad-search')}">
        <label>Busca</label>
        <input name="q" placeholder="matrícula, login, nome ou grupo">
        <label>Tipo</label>
        <select name="type">
          <option value="all">Usuários e grupos</option>
          <option value="user">Usuários</option>
          <option value="group">Grupos</option>
        </select>
        <button class="btn" type="submit">Pesquisar</button>
      </form>
    </div>

    <div class="box">
      <h3>Ações avançadas de tenant</h3>
      <form method="post" action="{url('/action/admin_tenant_advanced')}">
        <label>Tenant</label>
        <select name="tenant">{tenant_opts}</select>
        <button class="btn" name="op" value="sync_roles">Sync roles</button>
        <button class="btn blue" name="op" value="render_router">Render router</button>
        <button class="btn amber" name="op" value="ensure">Ensure/restore</button>
      </form>
    </div>
  </div>

  <h3>Parâmetros de política</h3>
  <table><tr><th>Parâmetro</th><th>Valor</th></tr>{settings_rows}</table>

  <h3>Auditoria</h3>
  <table><tr><th>Data</th><th>Ator</th><th>Ação</th><th>Alvo</th><th>RC</th></tr>{logs_rows}</table>
</div>"""

def render_help(user):
    return """
<div class="card">
  <h2>Ajuda</h2>
  <div class="grid">
    <div class="box"><h3>Projeto</h3><p>Espaço de trabalho. Pode ter Git, Komodo e banco Supabase.</p></div>
    <div class="box"><h3>Projeto sem banco</h3><p>Permite começar pelo código e vincular banco depois.</p></div>
    <div class="box"><h3>Banco/Tenant</h3><p>Conjunto de serviços Supabase: db, kong, studio, auth, storage, realtime, rest e meta.</p></div>
    <div class="box"><h3>Tempo ligado</h3><p>Evita manter banco de aluno consumindo RAM o dia inteiro.</p></div>
  </div>
  <div class="help">
    <b>Aluno:</b> entra pelo Authentik, abre o portal, acessa projetos autorizados, abre Git/Komodo e inicia o banco quando precisar.
  </div>
  <div class="help">
    <b>Professor/Admin:</b> cria/edita projetos, libera grupos, acompanha métricas e executa manutenção avançada.
  </div>
</div>"""


# CloudIF v54 Git/Komodo integration helpers BEGIN
def cloudif_v54_actor(headers):
    return (
        headers.get("X-authentik-username")
        or headers.get("X-Authentik-Username")
        or headers.get("X-authentik-email")
        or headers.get("X-Forwarded-User")
        or "portal"
    )

def cloudif_v54_groups(headers):
    return (
        headers.get("X-authentik-groups")
        or headers.get("X-Authentik-Groups")
        or ""
    )

def cloudif_v54_is_admin(headers):
    g = cloudif_v54_groups(headers).lower()
    u = cloudif_v54_actor(headers).lower()
    return (
        "cloudif-admin" in g
        or "cloudif-tenants-admin" in g
        or "admin" in g
        or u in ["admin", "akadmin"]
    )

def cloudif_v54_parse_post(handler):
    import urllib.parse
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length).decode("utf-8", "ignore")
    parsed = urllib.parse.parse_qs(raw)
    return {k: v[0] if v else "" for k, v in parsed.items()}

def cloudif_v54_send_html(handler, html_text, code=200):
    body = html_text.encode() if isinstance(html_text, str) else html_text
    handler.send_response(code)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def cloudif_v54_redirect(handler, url):
    handler.send_response(303)
    handler.send_header("Location", url)
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
# CloudIF v54 Git/Komodo integration helpers END



# CloudIF v56 Git/Komodo additive helpers BEGIN
def cloudif_v56_actor(headers):
    return (
        headers.get("X-authentik-username")
        or headers.get("X-Authentik-Username")
        or headers.get("X-authentik-email")
        or headers.get("X-Forwarded-User")
        or "portal"
    )

def cloudif_v56_groups(headers):
    return (
        headers.get("X-authentik-groups")
        or headers.get("X-Authentik-Groups")
        or ""
    )

def cloudif_v56_is_admin(headers):
    g = cloudif_v56_groups(headers).lower()
    u = cloudif_v56_actor(headers).lower()
    return (
        "cloudif-admin" in g
        or "cloudif-tenants-admin" in g
        or "admin" in g
        or u in ["admin", "akadmin"]
    )

def cloudif_v56_parse_post(handler):
    import urllib.parse
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length).decode("utf-8", "ignore")
    parsed = urllib.parse.parse_qs(raw)
    return {k: v[0] if v else "" for k, v in parsed.items()}

def cloudif_v56_send_html(handler, html_text, code=200):
    body = html_text.encode() if isinstance(html_text, str) else html_text
    handler.send_response(code)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def cloudif_v56_redirect(handler, url):
    handler.send_response(303)
    handler.send_header("Location", url)
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
# CloudIF v56 Git/Komodo additive helpers END


class Portal(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        super().end_headers()

    def user(self):
        username = (self.headers.get("X-authentik-username") or self.headers.get("X-Authentik-Username") or "unknown").strip().lower()
        email = (self.headers.get("X-authentik-email") or self.headers.get("X-Authentik-Email") or "").strip().lower()
        groups = parse_groups(self.headers.get("X-authentik-groups") or self.headers.get("X-Authentik-Groups") or "")
        return {"username": username, "email": email, "groups": groups, "admin": is_admin(groups)}

    def send_html(self, body, code=200):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, path=None):
        if not path:
            path = BASE_PATH + "/"
        elif path.startswith("/?"):
            path = BASE_PATH + path
        elif path.startswith("?"):
            path = BASE_PATH + "/" + path
        elif path.startswith("/"):
            path = BASE_PATH + path
        self.send_response(302)
        self.send_header("Location", path)
        self.end_headers()

    def do_GET(self):
        global urllib
        # CloudIF v56 Git/Komodo additive route
        if self.path.startswith("/cloudif/portal/git-komodo") or self.path.startswith("/git-komodo"):
            import urllib.parse
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            project = qs.get("project", [gk.DEFAULT_PROJECT])[0] or gk.DEFAULT_PROJECT
            tenant = qs.get("tenant", [gk.DEFAULT_TENANT])[0] or gk.DEFAULT_TENANT
            actor = cloudif_v56_actor(self.headers)
            is_admin = cloudif_v56_is_admin(self.headers)
            content = gk.render_git_komodo_module(project, tenant, actor, is_admin=is_admin)
            html = f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CloudIF - Git / Komodo</title>
<style>
body {{ margin:0; font-family:Arial,Helvetica,sans-serif; background:#f4f6f5; color:#1f2937; }}
header {{ background:white; border-bottom:4px solid #17882c; padding:16px 24px; }}
nav a {{ margin-right:10px; color:#17882c; font-weight:bold; text-decoration:none; }}
main {{ max-width:1240px; margin:24px auto; padding:0 18px; }}
.logo-dot {{ display:inline-block; width:13px; height:13px; background:#c8191e; border-radius:50%; margin-right:8px; }}
</style>
</head>
<body>
<header>
  <h1><span class="logo-dot"></span>CloudIF Portal</h1>
  <nav>
    <a href="/cloudif/portal/">Resumo</a>
    <a href="/cloudif/portal/git-komodo?project={project}&tenant={tenant}">Git / Komodo</a>
  </nav>
</header>
<main>{content}</main>
</body>
</html>"""
            return cloudif_v56_send_html(self, html)

        # CloudIF v54 Git/Komodo routes
        if self.path.startswith("/cloudif/portal/git-komodo") or self.path.startswith("/git-komodo"):
            import urllib.parse
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            project = qs.get("project", [gk.DEFAULT_PROJECT])[0] or gk.DEFAULT_PROJECT
            tenant = qs.get("tenant", [gk.DEFAULT_TENANT])[0] or gk.DEFAULT_TENANT
            actor = cloudif_v54_actor(self.headers)
            is_admin = cloudif_v54_is_admin(self.headers)

            content = gk.render_git_komodo_module(project, tenant, actor, is_admin=is_admin)
            # Página completa simples, mantendo módulo integrado ao mesmo portal.
            html = f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CloudIF - Git / Komodo</title>
<style>
body {{ margin:0; font-family:Arial,Helvetica,sans-serif; background:#f4f6f5; color:#1f2937; }}
header {{ background:white; border-bottom:4px solid #17882c; padding:16px 24px; }}
nav a {{ margin-right:10px; color:#17882c; font-weight:bold; text-decoration:none; }}
main {{ max-width:1240px; margin:24px auto; padding:0 18px; }}
.logo-dot {{ display:inline-block; width:13px; height:13px; background:#c8191e; border-radius:50%; margin-right:8px; }}
</style>
</head>
<body>
<header>
  <h1><span class="logo-dot"></span>CloudIF Portal</h1>
  <nav>
    <a href="/cloudif/portal/">Resumo</a>
    <a href="/cloudif/portal/git-komodo?project={project}&tenant={tenant}">Git / Komodo</a>
  </nav>
</header>
<main>{content}</main>
</body>
</html>"""
            return cloudif_v54_send_html(self, html)

        init_db()
        refresh_tenant_policies()
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        user = self.user()

        if parsed.path.endswith("/health") or parsed.path == "/health":
            return self.send_html("ok\n")

        if parsed.path.endswith("/action/refresh_cache"):
            rc, out, err = run(["bash","-lc","systemctl start cloudif-portal-refresh-cache.service"], 10)
            log_action(user["username"], "refresh_cache", "portal", rc, out, err)
            return self.redirect("/?tab=resumo")

        if parsed.path.endswith("/ad-search"):
            if not user["admin"]:
                return self.send_html(page(user, "admin", '<div class="card"><p class="pill bad">Restrito a admin.</p></div>'), 403)
            q = qs.get("q", [""])[0]
            typ = qs.get("type", ["all"])[0]
            data = fetch_json(f"{AD_AGENT_URL.rstrip()}/search?q={urllib.parse.quote(q)}&type={urllib.parse.quote(typ)}", 8) if AD_AGENT_URL else {"ok":False,"error":"AD_AGENT_URL vazio"}
            rows = ""
            for r in data.get("results", []):
                rows += f"<tr><td>{h(r.get('type'))}</td><td>{h(r.get('name'))}</td><td>{h(', '.join(r.get('members', [])))}</td></tr>"
            body = f"""
<div class="card">
  <h2>Resultado da busca AD</h2>
  <p>Busca: <b>{h(q)}</b></p>
  <table><tr><th>Tipo</th><th>Nome</th><th>Membros</th></tr>{rows or '<tr><td colspan="3">Nada encontrado.</td></tr>'}</table>
  <p><a class="btn" href="{url('?tab=admin')}">Voltar</a></p>
</div>"""
            return self.send_html(page(user, "admin", body))

        tab = qs.get("tab", ["resumo"])[0]
        render = {
            "resumo": render_resumo,
            "projetos": render_projects,
            "bancos": render_bancos,
            "git": render_git,
            "admin": render_admin,
            "ajuda": render_help,
        }.get(tab, render_resumo)

        return self.send_html(page(user, tab, render(user)))

    def do_POST(self):
        global urllib
        # CloudIF v56 Git/Komodo additive route
        if self.path.startswith("/cloudif/portal/git-komodo/action") or self.path.startswith("/git-komodo/action"):
            import urllib.parse
            form = cloudif_v56_parse_post(self)
            actor = cloudif_v56_actor(self.headers)
            _cloudif_v135b6_gk_result = gk.handle_git_komodo_action(form, actor)

            # CloudIF v135b6: algumas ações Git/Komodo retornam HTML direto,
            # por exemplo a tela de confirmação de exclusão Git/Komodo.
            if not (
                isinstance(_cloudif_v135b6_gk_result, tuple)
                and len(_cloudif_v135b6_gk_result) == 3
            ):
                body = str(_cloudif_v135b6_gk_result)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body.encode("utf-8"))))
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))
                return

            ok, msg, res = _cloudif_v135b6_gk_result
            project = form.get("project", gk.DEFAULT_PROJECT) or gk.DEFAULT_PROJECT
            tenant = form.get("tenant", gk.DEFAULT_TENANT) or gk.DEFAULT_TENANT
            url = "/cloudif/portal/git-komodo?project=" + urllib.parse.quote(project) + "&tenant=" + urllib.parse.quote(tenant)
            return cloudif_v56_redirect(self, url)

        # CloudIF v54 Git/Komodo routes
        if self.path.startswith("/cloudif/portal/git-komodo/action") or self.path.startswith("/git-komodo/action"):
            import urllib.parse
            form = cloudif_v54_parse_post(self)
            actor = cloudif_v54_actor(self.headers)
            ok, msg, res = gk.handle_git_komodo_action(form, actor)
            project = form.get("project", gk.DEFAULT_PROJECT) or gk.DEFAULT_PROJECT
            tenant = form.get("tenant", gk.DEFAULT_TENANT) or gk.DEFAULT_TENANT
            url = "/cloudif/portal/git-komodo?project=" + urllib.parse.quote(project) + "&tenant=" + urllib.parse.quote(tenant)
            return cloudif_v54_redirect(self, url)

        init_db()
        user = self.user()
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0") or 0)
        form = urllib.parse.parse_qs(self.rfile.read(length).decode())

        def val(k):
            return form.get(k, [""])[0]

        if parsed.path.endswith("/action/create_project"):
            name = val("name")
            tenant = val("tenant").strip()
            desc = val("description")
            slug = slugify(name)

            if tenant and not tenant_visible(tenant, user["username"], user["groups"]):
                return self.send_html(page(user, "projetos", '<div class="card"><p class="pill bad">Sem permissão no tenant.</p></div>'), 403)

            if not tenant and not setting_bool("CLOUDIF_ALLOW_GIT_ONLY_PROJECT", True):
                return self.send_html(page(user, "projetos", '<div class="card"><p class="pill bad">Projeto sem banco desabilitado.</p></div>'), 403)

            con = db()
            con.execute("""
              INSERT INTO projects(slug,name,tenant,owner,description,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?)
              ON CONFLICT(slug) DO UPDATE SET
                name=excluded.name,
                tenant=excluded.tenant,
                description=excluded.description,
                updated_at=excluded.updated_at
            """, (slug, name, tenant, user["username"], desc, now_iso(), now_iso()))
            con.execute("INSERT OR IGNORE INTO project_acl(slug,subject_type,subject) VALUES(?,?,?)", (slug, "user", user["username"]))
            con.commit()
            con.close()
            log_action(user["username"], "create_project", slug, 0, f"tenant={tenant}", "")
            return self.redirect("/?tab=projetos")

        if parsed.path.endswith("/action/project_action"):
            slug = val("slug")
            op = val("op")
            rc, out, err = 0, "", ""

            if op in ["sync", "check"]:
                rc, out, err = run(["bash","-lc","/srv/cloudif/bin/cloudif-forja-client.py status"], 30)
                con = db()
                con.execute("UPDATE projects SET komodo_status=?, updated_at=? WHERE slug=?", ("checked" if rc == 0 else "erro", now_iso(), slug))
                con.commit()
                con.close()
                log_action(user["username"], f"project_{op}", slug, rc, out, err)
                return self.redirect("/?tab=git")

            if op == "edit_save":
                con = db()
                con.execute("""
                  UPDATE projects
                  SET name=?, description=?, repo_url=?, komodo_status=?, updated_at=?
                  WHERE slug=?
                """, (val("name"), val("description"), val("repo_url"), val("komodo_status"), now_iso(), slug))
                con.commit()
                con.close()
                log_action(user["username"], "project_edit_save", slug, 0, "Projeto atualizado.", "")
                return self.redirect("/?tab=projetos")

        if parsed.path.endswith("/action/gitkomodo"):
            rc, out, err = run(["bash","-lc","/srv/cloudif/bin/cloudif-forja-client.py status"], 30)
            log_action(user["username"], "gitkomodo_status", "global", rc, out, err)
            return self.redirect("/?tab=git")

        if parsed.path.endswith("/action/tenant_action"):
            tenant = slugify(val("tenant"))
            op = val("op")

            if not tenant_visible(tenant, user["username"], user["groups"]):
                return self.send_html(page(user, "bancos", '<div class="card"><p class="pill bad">Sem permissão.</p></div>'), 403)

            tdir = BASE / "tenants" / tenant
            rc, out, err = 0, "", ""

            if op in ["start", "stop", "restart"]:
                cmdop = {"start":"up -d", "stop":"stop", "restart":"restart"}[op]
                rc, out, err = run(["bash","-lc",f"cd {str(tdir)!r} && docker compose --env-file .env {cmdop}"], 180)

            elif op == "keepalive":
                hours = min(max(int(val("hours") or "1"), 1), max_keepalive_hours())
                until = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)).isoformat(timespec="seconds")
                con = db()
                con.execute("""
                  INSERT INTO tenant_policy(tenant,always_alive,keepalive_until,max_hours,updated_at)
                  VALUES(?,0,?,6,?)
                  ON CONFLICT(tenant) DO UPDATE SET
                    keepalive_until=excluded.keepalive_until,
                    updated_at=excluded.updated_at
                """, (tenant, until, now_iso()))
                con.commit()
                con.close()
                rc, out, err = run(["bash","-lc",f"cd {str(tdir)!r} && docker compose --env-file .env up -d"], 180)

            elif op in ["always_on", "always_off"]:
                if not user["admin"]:
                    return self.send_html(page(user, "bancos", '<div class="card"><p class="pill bad">Restrito a admin.</p></div>'), 403)
                con = db()
                if op == "always_on":
                    con.execute("""
                      INSERT INTO tenant_policy(tenant,always_alive,max_hours,updated_at)
                      VALUES(?,1,24,?)
                      ON CONFLICT(tenant) DO UPDATE SET always_alive=1,max_hours=24,updated_at=excluded.updated_at
                    """, (tenant, now_iso()))
                else:
                    con.execute("""
                      INSERT INTO tenant_policy(tenant,always_alive,max_hours,updated_at)
                      VALUES(?,0,6,?)
                      ON CONFLICT(tenant) DO UPDATE SET always_alive=0,max_hours=6,updated_at=excluded.updated_at
                    """, (tenant, now_iso()))
                con.commit()
                con.close()

            elif op == "repair":
                if not (user["admin"] or setting_bool("CLOUDIF_STUDENT_CAN_REPAIR", True)):
                    return self.send_html(page(user, "bancos", '<div class="card"><p class="pill bad">Reparo não permitido.</p></div>'), 403)
                rc, out, err = run(["bash","-lc",f"/usr/local/sbin/cloudif-tenant-ensure-bg.sh {tenant!r} restore {user['username']!r}"], 120)

            log_action(user["username"], op, tenant, rc, out, err)
            return self.redirect("/?tab=bancos")

        if parsed.path.endswith("/action/admin_setting"):
            if not user["admin"]:
                return self.send_html(page(user, "admin", '<div class="card"><p class="pill bad">Restrito a admin.</p></div>'), 403)
            con = db()
            con.execute("UPDATE settings SET value=? WHERE key=?", (val("value"), val("key")))
            con.commit()
            con.close()
            log_action(user["username"], "admin_setting", val("key"), 0, val("value"), "")
            return self.redirect("/?tab=admin")

        if parsed.path.endswith("/action/admin_tenant_advanced"):
            if not user["admin"]:
                return self.send_html(page(user, "admin", '<div class="card"><p class="pill bad">Restrito a admin.</p></div>'), 403)
            tenant = slugify(val("tenant"))
            op = val("op")
            rc, out, err = 0, "", ""
            if op == "sync_roles":
                rc, out, err = run(["bash","-lc",f"/srv/cloudif/bin/cloudif-sync-db-passwords.sh {tenant!r}"], 240)
            elif op == "render_router":
                rc, out, err = run(["bash","-lc","/srv/cloudif/bin/cloudif-render-router-sso.sh"], 240)
            elif op == "ensure":
                rc, out, err = run(["bash","-lc",f"/usr/local/sbin/cloudif-tenant-ensure-bg.sh {tenant!r} restore {user['username']!r}"], 120)
            log_action(user["username"], f"admin_{op}", tenant, rc, out, err)
            return self.redirect("/?tab=admin")

        return self.redirect("/")

    def log_message(self, fmt, *args):
        print(time.strftime("[%Y-%m-%dT%H:%M:%S]"), self.client_address[0], fmt % args, flush=True)

# ===== CloudIF Portal v18 UX + Integration Overrides BEGIN =====

def auth_start_url(target):
    """
    Gera link passando pelo Authentik/outpost quando habilitado.
    Isso evita jogar o usuário diretamente numa tela de login do Forgejo/Komodo.
    """
    if not setting_bool("CLOUDIF_USE_AUTHENTIK_START_LINKS", True):
        return target
    start = setting_value("CLOUDIF_AUTHENTIK_START_URL", "https://cloudiff.duckdns.org/outpost.goauthentik.io/start")
    return start.rstrip("/") + "?rd=" + urllib.parse.quote(target, safe="")

def supabase_studio_url(tenant):
    path = setting_value("CLOUDIF_SUPABASE_STUDIO_PATH", "/project/default")
    if not path.startswith("/"):
        path = "/" + path
    return f"https://{tenant}.{PUBLIC_HOST}{path}"

def tenant_is_running(tenant):
    services = compose_services(tenant)
    if not services:
        return False
    # Considera ativo se pelo menos db/kong/studio ou a maioria dos serviços essenciais estiver running/healthy.
    good = 0
    total = 0
    for s in services:
        total += 1
        st = (s.get("status") or "").lower()
        if "running" in st or "healthy" in st or "up" in st:
            good += 1
    return good >= max(1, min(3, total))

def last_actions_html(limit=8):
    con = db()
    rows = con.execute("""
      SELECT ts, actor, action, target, rc
      FROM action_log
      ORDER BY id DESC
      LIMIT ?
    """, (limit,)).fetchall()
    con.close()
    if not rows:
        return '<p class="small">Sem ações recentes.</p>'
    out = '<table><tr><th>Data</th><th>Usuário</th><th>Ação</th><th>Alvo</th><th>RC</th></tr>'
    for r in rows:
        out += f"<tr><td>{h(r['ts'])}</td><td>{h(r['actor'])}</td><td>{h(r['action'])}</td><td>{h(r['target'])}</td><td>{h(r['rc'])}</td></tr>"
    out += "</table>"
    return out

def render_projects(user):
    rows = user_visible_projects(user["username"], user["groups"])
    tenants = visible_tenants(user["username"], user["groups"])

    allow_git_only = setting_bool("CLOUDIF_ALLOW_GIT_ONLY_PROJECT", True)
    tenant_opts = ""
    if allow_git_only:
        tenant_opts += '<option value="">Sem banco: somente Git/Komodo</option>'
    tenant_opts += "".join(f'<option value="{h(t.get("tenant"))}">{h(t.get("tenant"))}</option>' for t in tenants)

    cards = []
    for p in rows:
        forgejo_target = p["repo_url"] or setting_value("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git")
        komodo_target = setting_value("CLOUDIF_KOMODO_URL", "https://komodoiff.duckdns.org/")
        forgejo = auth_start_url(forgejo_target)
        komodo = auth_start_url(komodo_target)
        studio = auth_start_url(supabase_studio_url(p["tenant"])) if p["tenant"] else ""
        edit_id = "edit_" + re.sub(r"[^a-zA-Z0-9_]+", "_", p["slug"])

        studio_btn = f'<a class="btn light" href="{h(studio)}" target="_blank">Abrir Studio</a>' if p["tenant"] else ""

        cards.append(f"""
<div class="project-card">
  <div class="project-line">
    <div>
      <h3>{h(p['name'])}</h3>
      <p class="small">Slug: {h(p['slug'])}</p>
      <p>{h(p['description'] or 'Sem descrição.')}</p>
    </div>
    <div>
      <b>Banco</b><br>
      <span class="pill {'ok' if p['tenant'] else 'muted'}">{h(p['tenant'] or 'sem banco')}</span><br>
      {studio_btn}
    </div>
    <div>
      <b>Painéis</b><br>
      <a class="btn light" href="{h(forgejo)}" target="_blank">Git</a>
      <a class="btn light" href="{h(komodo)}" target="_blank">Komodo</a><br>
      <span class="small">Status: {h(p['komodo_status'] or 'not_configured')}</span>
    </div>
    <div>
      <form method="post" action="{url('/action/project_action')}">
        <input type="hidden" name="slug" value="{h(p['slug'])}">
        <button class="btn gray" name="op" value="check">Checar</button>
        <button class="btn blue" name="op" value="sync">Sincronizar</button>
        <button class="btn amber" name="op" value="integrate">Integrar</button>
      </form>
      <button class="btn light" onclick="togglePanel('{edit_id}')">Editar</button>
    </div>
  </div>

  <div id="{edit_id}" class="wizard-panel">
    <form method="post" action="{url('/action/project_action')}">
      <input type="hidden" name="slug" value="{h(p['slug'])}">
      <input type="hidden" name="op" value="edit_save">
      <div class="grid2">
        <div>
          <label>Nome</label>
          <input name="name" value="{h(p['name'])}">
        </div>
        <div>
          <label>URL do Git/Forgejo</label>
          <input name="repo_url" value="{h(p['repo_url'])}">
        </div>
      </div>
      <label>Descrição</label>
      <textarea name="description">{h(p['description'])}</textarea>
      <label>Status Komodo</label>
      <input name="komodo_status" value="{h(p['komodo_status'])}">
      <button class="btn" type="submit">Salvar edição</button>
    </form>
  </div>
</div>""")

    return f"""
<div class="card">
  <div class="section-title">
    <div>
      <h2>Projetos</h2>
      <p class="small">Apenas projetos que você pode acessar aparecem aqui.</p>
    </div>
    <button class="btn" onclick="togglePanel('new_project')">Novo projeto</button>
  </div>

  <div id="new_project" class="wizard-panel">
    <div class="help">
      Projeto pode começar sem banco, usando só Git/Komodo. O banco pode ser vinculado depois.
    </div>
    <form method="post" action="{url('/action/create_project')}">
      <label>Nome do projeto</label>
      <input name="name" required placeholder="Ex: Sistema de Biblioteca">
      <label>Descrição</label>
      <textarea name="description" placeholder="Objetivo, turma, disciplina ou grupo responsável"></textarea>
      <label>Banco/Tenant Supabase</label>
      <select name="tenant">{tenant_opts}</select>
      <button class="btn" type="submit">Criar / registrar projeto</button>
    </form>
  </div>

  {''.join(cards) or '<div class="box">Nenhum projeto visível ainda.</div>'}
</div>

<div class="card">
  <h2>Últimas ações</h2>
  {last_actions_html(8)}
</div>"""

def render_bancos(user):
    tenants = visible_tenants(user["username"], user["groups"])
    blocks = []
    con = db()

    for t in tenants:
        tenant = t.get("tenant") or ""
        pol = con.execute("SELECT * FROM tenant_policy WHERE tenant=?", (tenant,)).fetchone()
        policy = "-"
        if pol:
            policy = f"Sempre ligado: {'sim' if pol['always_alive'] else 'não'} · Ligado até: {pol['keepalive_until'] or '-'}"

        services = compose_services(tenant)
        running = tenant_is_running(tenant)
        chips = []
        for s in services:
            chips.append(f"""
<div class="container-chip">
  <span class="container-name">{h(s['service'])}</span>
  {status_badge(s.get('status'))}
</div>""")

        hours = "".join(f'<option value="{i}">{i} hora{"s" if i > 1 else ""}</option>' for i in range(1, max_keepalive_hours()+1))

        studio_link = auth_start_url(supabase_studio_url(tenant))

        if running:
            action_buttons = f"""
<a class="btn light" href="{h(studio_link)}" target="_blank">Abrir Studio</a>
<button class="btn gray" name="op" value="stop">Parar</button>
<button class="btn blue" name="op" value="restart">Reiniciar</button>
<select name="hours" style="max-width:150px;display:inline-block">{hours}</select>
<button class="btn" name="op" value="keepalive">Tempo ligado</button>
"""
            if user["admin"]:
                action_buttons += """
<button class="btn amber" name="op" value="always_on">Marcar sempre ligado</button>
<button class="btn gray" name="op" value="always_off">Desativar sempre ligado</button>
"""
        else:
            action_buttons = f"""
<button class="btn" name="op" value="start">Iniciar</button>
<select name="hours" style="max-width:150px;display:inline-block">{hours}</select>
<button class="btn" name="op" value="keepalive">Iniciar temporariamente</button>
"""
            if user["admin"]:
                action_buttons += '<button class="btn amber" name="op" value="always_on_start">Iniciar sempre ligado</button>'
            if user["admin"] or setting_bool("CLOUDIF_STUDENT_CAN_REPAIR", True):
                action_buttons += '<button class="btn red" name="op" value="repair">Reparar</button>'

        blocks.append(f"""
<div class="card">
  <div class="section-title">
    <div>
      <h2>{h(tenant)}</h2>
      <p class="small">{h(policy)}</p>
    </div>
    <div>
      <span class="pill {'ok' if running else 'muted'}">{'em execução' if running else 'parado'}</span>
    </div>
  </div>

  <div class="container-grid">
    {''.join(chips) or '<div class="container-chip"><span class="container-name">sem serviços</span><span class="pill muted">-</span></div>'}
  </div>

  <div class="action-group">
    <form method="post" action="{url('/action/tenant_action')}">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      {action_buttons}
    </form>
  </div>
</div>""")

    con.close()
    return f"""
<div class="help">
  Botões mudam conforme o estado do tenant. Se estiver ativo, aparecem ações de parar/reiniciar/abrir Studio.
  Se estiver parado, aparecem ações de iniciar/reparar.
</div>
{''.join(blocks) or '<div class="card">Nenhum tenant visível.</div>'}"""

def render_git(user):
    status = git_komodo_status()
    projects = user_visible_projects(user["username"], user["groups"])
    forgejo_target = setting_value("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git")
    komodo_target = setting_value("CLOUDIF_KOMODO_URL", "https://komodoiff.duckdns.org/")
    forgejo = auth_start_url(forgejo_target)
    komodo = auth_start_url(komodo_target)

    rows = []
    for p in projects:
        repo_target = p["repo_url"] or forgejo_target
        repo = auth_start_url(repo_target)
        rows.append(f"""
<tr>
  <td><b>{h(p['name'])}</b><br><span class="small">{h(p['slug'])}</span></td>
  <td><a href="{h(repo)}" target="_blank">Abrir Git</a></td>
  <td><a href="{h(komodo)}" target="_blank">Abrir Komodo</a></td>
  <td><span class="pill muted">{h(p['komodo_status'] or 'not_configured')}</span></td>
  <td>
    <form method="post" action="{url('/action/project_action')}">
      <input type="hidden" name="slug" value="{h(p['slug'])}">
      <button class="btn gray" name="op" value="check">Checar</button>
      <button class="btn blue" name="op" value="sync">Sincronizar</button>
      <button class="btn amber" name="op" value="integrate">Integrar</button>
    </form>
  </td>
</tr>""")

    return f"""
<div class="grid">
  <div class="box"><h3>Forgejo</h3><p>Repositório Git do projeto.</p><a class="btn light" href="{h(forgejo)}" target="_blank">Abrir Forgejo via Authentik</a></div>
  <div class="box"><h3>Komodo</h3><p>Automação e deploy.</p><a class="btn light" href="{h(komodo)}" target="_blank">Abrir Komodo via Authentik</a></div>
  <div class="box"><h3>Webhook</h3><p>O Forgejo avisa o Forja Agent quando há push.</p></div>
</div>

<div class="card">
  <h2>Projetos integrados</h2>
  <table>
    <tr><th>Projeto</th><th>Git</th><th>Komodo</th><th>Status</th><th>Ações</th></tr>
    {''.join(rows) or '<tr><td colspan="5">Nenhum projeto visível.</td></tr>'}
  </table>
</div>

<div class="card">
  <h2>Diagnóstico geral</h2>
  <form method="post" action="{url('/action/gitkomodo')}">
    <button class="btn gray" name="op" value="status">Checar Forgejo/Komodo agora</button>
  </form>
  <pre>{h(json.dumps(status, ensure_ascii=False, indent=2))}</pre>
</div>

<div class="card">
  <h2>Últimas ações</h2>
  {last_actions_html(10)}
</div>"""

def do_POST_v18(self):
    init_db()
    user = self.user()
    parsed = urllib.parse.urlparse(self.path)
    length = int(self.headers.get("Content-Length", "0") or 0)
    form = urllib.parse.parse_qs(self.rfile.read(length).decode())

    def val(k):
        return form.get(k, [""])[0]

    if parsed.path.endswith("/action/create_project"):
        name = val("name")
        tenant = val("tenant").strip()
        desc = val("description")
        slug = slugify(name)

        if tenant and not tenant_visible(tenant, user["username"], user["groups"]):
            return self.send_html(page(user, "projetos", '<div class="card"><p class="pill bad">Sem permissão no tenant.</p></div>'), 403)

        if not tenant and not setting_bool("CLOUDIF_ALLOW_GIT_ONLY_PROJECT", True):
            return self.send_html(page(user, "projetos", '<div class="card"><p class="pill bad">Projeto sem banco desabilitado.</p></div>'), 403)

        con = db()
        con.execute("""
          INSERT INTO projects(slug,name,tenant,owner,description,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?)
          ON CONFLICT(slug) DO UPDATE SET
            name=excluded.name,
            tenant=excluded.tenant,
            description=excluded.description,
            updated_at=excluded.updated_at
        """, (slug, name, tenant, user["username"], desc, now_iso(), now_iso()))
        con.execute("INSERT OR IGNORE INTO project_acl(slug,subject_type,subject) VALUES(?,?,?)", (slug, "user", user["username"]))
        con.commit()
        con.close()
        log_action(user["username"], "create_project", slug, 0, f"tenant={tenant}", "")
        return self.redirect("/?tab=projetos")

    if parsed.path.endswith("/action/project_action"):
        slug = val("slug")
        op = val("op")
        rc, out, err = 0, "", ""

        if op in ["sync", "check", "integrate"]:
            con = db()
            p = con.execute("SELECT * FROM projects WHERE slug=?", (slug,)).fetchone()
            tenant = p["tenant"] if p else ""
            script = setting_value("CLOUDIF_PROJECT_INTEGRATION_SCRIPT", "/srv/cloudif/bin/cloudif-project-integrate.sh")
            con.close()

            action = "integrate" if op == "integrate" else op
            rc, out, err = run(["bash", "-lc", f"{script!r} {action!r} {slug!r} {tenant!r} {user['username']!r}"], 180)

            con = db()
            con.execute("UPDATE projects SET komodo_status=?, updated_at=? WHERE slug=?", ("ok" if rc == 0 else "erro", now_iso(), slug))
            con.commit()
            con.close()

            log_action(user["username"], f"project_{op}", slug, rc, out, err)
            return self.redirect("/?tab=git")

        if op == "edit_save":
            con = db()
            con.execute("""
              UPDATE projects
              SET name=?, description=?, repo_url=?, komodo_status=?, updated_at=?
              WHERE slug=?
            """, (val("name"), val("description"), val("repo_url"), val("komodo_status"), now_iso(), slug))
            con.commit()
            con.close()
            log_action(user["username"], "project_edit_save", slug, 0, "Projeto atualizado.", "")
            return self.redirect("/?tab=projetos")

    if parsed.path.endswith("/action/gitkomodo"):
        rc, out, err = run(["bash", "-lc", "/srv/cloudif/bin/cloudif-forja-client.py status"], 30)
        log_action(user["username"], "gitkomodo_status", "global", rc, out, err)
        return self.redirect("/?tab=git")

    if parsed.path.endswith("/action/tenant_action"):
        tenant = slugify(val("tenant"))
        op = val("op")

        if not tenant_visible(tenant, user["username"], user["groups"]):
            return self.send_html(page(user, "bancos", '<div class="card"><p class="pill bad">Sem permissão.</p></div>'), 403)

        tdir = BASE / "tenants" / tenant
        rc, out, err = 0, "", ""

        if op in ["start", "stop", "restart"]:
            cmdop = {"start":"up -d", "stop":"stop", "restart":"restart"}[op]
            rc, out, err = run(["bash","-lc",f"cd {str(tdir)!r} && docker compose --env-file .env {cmdop}"], 180)

        elif op == "keepalive":
            hours = min(max(int(val("hours") or "1"), 1), max_keepalive_hours())
            until = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)).isoformat(timespec="seconds")
            con = db()
            con.execute("""
              INSERT INTO tenant_policy(tenant,always_alive,keepalive_until,max_hours,updated_at)
              VALUES(?,0,?,6,?)
              ON CONFLICT(tenant) DO UPDATE SET
                keepalive_until=excluded.keepalive_until,
                updated_at=excluded.updated_at
            """, (tenant, until, now_iso()))
            con.commit()
            con.close()
            rc, out, err = run(["bash","-lc",f"cd {str(tdir)!r} && docker compose --env-file .env up -d"], 180)

        elif op in ["always_on", "always_off", "always_on_start"]:
            if not user["admin"]:
                return self.send_html(page(user, "bancos", '<div class="card"><p class="pill bad">Restrito a admin.</p></div>'), 403)
            con = db()
            if op in ["always_on", "always_on_start"]:
                con.execute("""
                  INSERT INTO tenant_policy(tenant,always_alive,max_hours,updated_at)
                  VALUES(?,1,24,?)
                  ON CONFLICT(tenant) DO UPDATE SET always_alive=1,max_hours=24,updated_at=excluded.updated_at
                """, (tenant, now_iso()))
                if op == "always_on_start":
                    rc, out, err = run(["bash","-lc",f"cd {str(tdir)!r} && docker compose --env-file .env up -d"], 180)
            else:
                con.execute("""
                  INSERT INTO tenant_policy(tenant,always_alive,max_hours,updated_at)
                  VALUES(?,0,6,?)
                  ON CONFLICT(tenant) DO UPDATE SET always_alive=0,max_hours=6,updated_at=excluded.updated_at
                """, (tenant, now_iso()))
            con.commit()
            con.close()

        elif op == "repair":
            if not (user["admin"] or setting_bool("CLOUDIF_STUDENT_CAN_REPAIR", True)):
                return self.send_html(page(user, "bancos", '<div class="card"><p class="pill bad">Reparo não permitido.</p></div>'), 403)
            rc, out, err = run(["bash","-lc",f"/usr/local/sbin/cloudif-tenant-ensure-bg.sh {tenant!r} restore {user['username']!r}"], 120)

        log_action(user["username"], op, tenant, rc, out, err)
        return self.redirect("/?tab=bancos")

    # Mantém handlers originais para admin_setting/admin_tenant_advanced, se existirem.
    return Portal._old_do_POST(self)

Portal._old_do_POST = Portal.do_POST
Portal.do_POST = do_POST_v18

# ===== CloudIF Portal v18 UX + Integration Overrides END =====

# ===== CloudIF Portal v19 OIDC + Tenant ACL + Integration Overrides BEGIN =====

def direct_oidc_url(kind, fallback):
    if not setting_bool("CLOUDIF_USE_DIRECT_OIDC_LINKS", True):
        return fallback
    if kind == "forgejo":
        return setting_value("CLOUDIF_FORGEJO_OIDC_URL", "https://cloudiff.duckdns.org/git/user/oauth2/Authentik/")
    if kind == "komodo":
        return setting_value("CLOUDIF_KOMODO_OIDC_URL", "https://cloudiff.duckdns.org/git/user/oauth2/Authentik/")
    return fallback

def supabase_studio_url(tenant):
    return f"https://{tenant}.{PUBLIC_HOST}/project/default"

def tenant_is_running(tenant):
    services = compose_services(tenant)
    if not services:
        return False
    good = 0
    total = 0
    for s in services:
        total += 1
        st = (s.get("status") or "").lower()
        if "running" in st or "healthy" in st or "up" in st:
            good += 1
    return good >= max(1, min(3, total))

def tenant_acl_rows(tenant):
    con = db()
    rows = con.execute("""
      SELECT id, tenant, subject_type, subject
      FROM tenant_acl
      WHERE tenant=?
      ORDER BY subject_type, subject
    """, (tenant,)).fetchall()
    con.close()
    return rows

def tenant_acl_html(tenant, user):
    rows = tenant_acl_rows(tenant)
    if not rows:
        acl_table = '<p class="small">Nenhuma permissão adicional cadastrada. O dono natural ainda pode ser o próprio tenant/usuário.</p>'
    else:
        trs = ""
        for r in rows:
            rm = ""
            if user["admin"]:
                rm = f"""
<form method="post" action="{url('/action/tenant_acl')}" style="display:inline">
  <input type="hidden" name="op" value="remove">
  <input type="hidden" name="id" value="{h(r['id'])}">
  <button class="btn red" type="submit">Remover</button>
</form>"""
            trs += f"<tr><td>{h(r['subject_type'])}</td><td>{h(r['subject'])}</td><td>{rm}</td></tr>"
        acl_table = f"<table><tr><th>Tipo</th><th>Usuário/Grupo</th><th>Ação</th></tr>{trs}</table>"

    add_form = ""
    if user["admin"]:
        add_form = f"""
<div class="grid2">
  <div class="box">
    <h3>Adicionar permissão</h3>
    <form method="post" action="{url('/action/tenant_acl')}">
      <input type="hidden" name="op" value="add">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      <label>Tipo</label>
      <select name="subject_type">
        <option value="user">Usuário</option>
        <option value="group">Grupo</option>
      </select>
      <label>Usuário ou grupo</label>
      <input name="subject" placeholder="ex: aluno123 ou CloudIF-Turma-2026">
      <button class="btn" type="submit">Adicionar</button>
    </form>
  </div>
  <div class="box">
    <h3>Busca AD</h3>
    <p class="small">Use a aba Administração para pesquisar usuários/grupos reais no AD antes de vincular.</p>
    <a class="btn light" href="{url('?tab=admin')}">Ir para Administração</a>
  </div>
</div>"""
    return acl_table + add_form

def last_actions_html(limit=8):
    con = db()
    rows = con.execute("""
      SELECT ts, actor, action, target, rc
      FROM action_log
      ORDER BY id DESC
      LIMIT ?
    """, (limit,)).fetchall()
    con.close()
    if not rows:
        return '<p class="small">Sem ações recentes.</p>'
    out = '<table><tr><th>Data</th><th>Usuário</th><th>Ação</th><th>Alvo</th><th>RC</th></tr>'
    for r in rows:
        out += f"<tr><td>{h(r['ts'])}</td><td>{h(r['actor'])}</td><td>{h(r['action'])}</td><td>{h(r['target'])}</td><td>{h(r['rc'])}</td></tr>"
    out += "</table>"
    return out

def render_projects(user):
    rows = user_visible_projects(user["username"], user["groups"])
    tenants = visible_tenants(user["username"], user["groups"])

    allow_git_only = setting_bool("CLOUDIF_ALLOW_GIT_ONLY_PROJECT", True)
    tenant_opts = ""
    if allow_git_only:
        tenant_opts += '<option value="">Sem banco: somente Git/Komodo</option>'
    tenant_opts += "".join(f'<option value="{h(t.get("tenant"))}">{h(t.get("tenant"))}</option>' for t in tenants)

    cards = []
    for p in rows:
        forgejo = direct_oidc_url("forgejo", p["repo_url"] or setting_value("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git"))
        komodo = direct_oidc_url("komodo", setting_value("CLOUDIF_KOMODO_URL", "https://komodoiff.duckdns.org/"))
        studio = supabase_studio_url(p["tenant"]) if p["tenant"] else ""
        edit_id = "edit_" + re.sub(r"[^a-zA-Z0-9_]+", "_", p["slug"])

        studio_btn = f'<a class="btn light" href="{h(studio)}" target="_blank">Abrir Studio</a>' if p["tenant"] else ""

        cards.append(f"""
<div class="project-card">
  <div class="project-line">
    <div>
      <h3>{h(p['name'])}</h3>
      <p class="small">Slug: {h(p['slug'])}</p>
      <p>{h(p['description'] or 'Sem descrição.')}</p>
    </div>
    <div>
      <b>Banco</b><br>
      <span class="pill {'ok' if p['tenant'] else 'muted'}">{h(p['tenant'] or 'sem banco')}</span><br>
      {studio_btn}
    </div>
    <div>
      <b>Painéis</b><br>
      <a class="btn light" href="{h(forgejo)}" target="_blank">Git</a>
      <a class="btn light" href="{h(komodo)}" target="_blank">Komodo</a><br>
      <span class="small">Status: {h(p['komodo_status'] or 'not_configured')}</span>
    </div>
    <div>
      <form method="post" action="{url('/action/project_action')}">
        <input type="hidden" name="slug" value="{h(p['slug'])}">
        <button class="btn gray" name="op" value="check">Checar</button>
        <button class="btn blue" name="op" value="sync">Sincronizar</button>
        <button class="btn amber" name="op" value="integrate">Integrar</button>
      </form>
      <button class="btn light" onclick="togglePanel('{edit_id}')">Editar</button>
    </div>
  </div>

  <div id="{edit_id}" class="wizard-panel">
    <form method="post" action="{url('/action/project_action')}">
      <input type="hidden" name="slug" value="{h(p['slug'])}">
      <input type="hidden" name="op" value="edit_save">
      <div class="grid2">
        <div>
          <label>Nome</label>
          <input name="name" value="{h(p['name'])}">
        </div>
        <div>
          <label>URL do Git/Forgejo</label>
          <input name="repo_url" value="{h(p['repo_url'])}">
        </div>
      </div>
      <label>Descrição</label>
      <textarea name="description">{h(p['description'])}</textarea>
      <label>Status Komodo</label>
      <input name="komodo_status" value="{h(p['komodo_status'])}">
      <button class="btn" type="submit">Salvar edição</button>
    </form>
  </div>
</div>""")

    return f"""
<div class="card">
  <div class="section-title">
    <div>
      <h2>Projetos</h2>
      <p class="small">Apenas projetos que você pode acessar aparecem aqui.</p>
    </div>
    <button class="btn" onclick="togglePanel('new_project')">Novo projeto</button>
  </div>

  <div id="new_project" class="wizard-panel">
    <div class="help">Projeto pode começar sem banco, usando só Git/Komodo.</div>
    <form method="post" action="{url('/action/create_project')}">
      <label>Nome do projeto</label>
      <input name="name" required placeholder="Ex: Sistema de Biblioteca">
      <label>Descrição</label>
      <textarea name="description" placeholder="Objetivo, turma, disciplina ou grupo responsável"></textarea>
      <label>Banco/Tenant Supabase</label>
      <select name="tenant">{tenant_opts}</select>
      <button class="btn" type="submit">Criar / registrar projeto</button>
    </form>
  </div>

  {''.join(cards) or '<div class="box">Nenhum projeto visível ainda.</div>'}
</div>

<div class="card">
  <h2>Últimas ações</h2>
  {last_actions_html(8)}
</div>"""

def render_bancos(user):
    tenants = visible_tenants(user["username"], user["groups"])
    blocks = []
    con = db()

    for t in tenants:
        tenant = t.get("tenant") or ""
        pol = con.execute("SELECT * FROM tenant_policy WHERE tenant=?", (tenant,)).fetchone()
        policy = "-"
        if pol:
            policy = f"Sempre ligado: {'sim' if pol['always_alive'] else 'não'} · Ligado até: {pol['keepalive_until'] or '-'}"

        services = compose_services(tenant)
        running = tenant_is_running(tenant)

        chips = []
        for s in services:
            chips.append(f"""
<div class="container-chip">
  <span class="container-name">{h(s['service'])}</span>
  {status_badge(s.get('status'))}
</div>""")

        hours = "".join(f'<option value="{i}">{i} hora{"s" if i > 1 else ""}</option>' for i in range(1, max_keepalive_hours()+1))
        studio_link = supabase_studio_url(tenant)

        if running:
            action_buttons = f"""
<a class="btn light" href="{h(studio_link)}" target="_blank">Abrir Studio</a>
<button class="btn gray" name="op" value="stop">Parar</button>
<button class="btn blue" name="op" value="restart">Reiniciar</button>
<select name="hours" style="max-width:150px;display:inline-block">{hours}</select>
<button class="btn" name="op" value="keepalive">Tempo ligado</button>
"""
            if user["admin"]:
                action_buttons += """
<button class="btn amber" name="op" value="always_on">Marcar sempre ligado</button>
<button class="btn gray" name="op" value="always_off">Desativar sempre ligado</button>
"""
        else:
            action_buttons = f"""
<button class="btn" name="op" value="start">Iniciar</button>
<select name="hours" style="max-width:150px;display:inline-block">{hours}</select>
<button class="btn" name="op" value="keepalive">Iniciar temporariamente</button>
"""
            if user["admin"]:
                action_buttons += '<button class="btn amber" name="op" value="always_on_start">Iniciar sempre ligado</button>'
                if setting_bool("CLOUDIF_ALLOW_ADMIN_DELETE_TENANT", False):
                    action_buttons += '<button class="btn red" name="op" value="delete">Apagar banco</button><button class="btn red" name="op" value="delete_recreate">Apagar e recriar</button>'
            if user["admin"] or setting_bool("CLOUDIF_STUDENT_CAN_REPAIR", True):
                action_buttons += '<button class="btn red" name="op" value="repair">Reparar</button>'

        acl_id = "acl_" + re.sub(r"[^a-zA-Z0-9_]+", "_", tenant)

        blocks.append(f"""
<div class="card">
  <div class="section-title">
    <div>
      <h2>{h(tenant)}</h2>
      <p class="small">{h(policy)}</p>
    </div>
    <div>
      <span class="pill {'ok' if running else 'muted'}">{'em execução' if running else 'parado'}</span>
    </div>
  </div>

  <div class="container-grid">
    {''.join(chips) or '<div class="container-chip"><span class="container-name">sem serviços</span><span class="pill muted">-</span></div>'}
  </div>

  <div class="action-group">
    <form method="post" action="{url('/action/tenant_action')}">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      {action_buttons}
    </form>
  </div>

  <div class="action-group">
    <button class="btn light" onclick="togglePanel('{acl_id}')">Permissões do banco</button>
    <div id="{acl_id}" class="wizard-panel">
      {tenant_acl_html(tenant, user)}
    </div>
  </div>
</div>""")

    con.close()
    return f"""
<div class="help">
  A lista de bancos é dinâmica, baseada no registry e nas permissões. Admin pode vincular usuários/grupos ao tenant.
</div>
{''.join(blocks) or '<div class="card">Nenhum tenant visível.</div>'}"""

def render_git(user):
    status = git_komodo_status()
    projects = user_visible_projects(user["username"], user["groups"])
    forgejo = direct_oidc_url("forgejo", setting_value("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git"))
    komodo = direct_oidc_url("komodo", setting_value("CLOUDIF_KOMODO_URL", "https://komodoiff.duckdns.org/"))

    rows = []
    for p in projects:
        repo = direct_oidc_url("forgejo", p["repo_url"] or setting_value("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git"))
        rows.append(f"""
<tr>
  <td><b>{h(p['name'])}</b><br><span class="small">{h(p['slug'])}</span></td>
  <td><a href="{h(repo)}" target="_blank">Abrir Git</a></td>
  <td><a href="{h(komodo)}" target="_blank">Abrir Komodo</a></td>
  <td><span class="pill muted">{h(p['komodo_status'] or 'not_configured')}</span></td>
  <td>
    <form method="post" action="{url('/action/project_action')}">
      <input type="hidden" name="slug" value="{h(p['slug'])}">
      <button class="btn gray" name="op" value="check">Checar</button>
      <button class="btn blue" name="op" value="sync">Sincronizar</button>
      <button class="btn amber" name="op" value="integrate">Integrar</button>
    </form>
  </td>
</tr>""")

    return f"""
<div class="grid">
  <div class="box"><h3>Forgejo</h3><p>Repositório Git.</p><a class="btn light" href="{h(forgejo)}" target="_blank">Abrir Forgejo OIDC</a></div>
  <div class="box"><h3>Komodo</h3><p>Automação/deploy.</p><a class="btn light" href="{h(komodo)}" target="_blank">Abrir Komodo OIDC</a></div>
  <div class="box"><h3>Webhook</h3><p>Forgejo chama o Forja Agent em alterações.</p></div>
</div>

<div class="card">
  <h2>Projetos integrados</h2>
  <table>
    <tr><th>Projeto</th><th>Git</th><th>Komodo</th><th>Status</th><th>Ações</th></tr>
    {''.join(rows) or '<tr><td colspan="5">Nenhum projeto visível.</td></tr>'}
  </table>
</div>

<div class="card">
  <h2>Diagnóstico geral</h2>
  <form method="post" action="{url('/action/gitkomodo')}">
    <button class="btn gray" name="op" value="status">Checar Forgejo/Komodo agora</button>
  </form>
  <pre>{h(json.dumps(status, ensure_ascii=False, indent=2))}</pre>
</div>

<div class="card">
  <h2>Últimas ações</h2>
  {last_actions_html(10)}
</div>"""

def do_POST_v19(self):
    init_db()
    user = self.user()
    parsed = urllib.parse.urlparse(self.path)
    length = int(self.headers.get("Content-Length", "0") or 0)
    form = urllib.parse.parse_qs(self.rfile.read(length).decode())

    def val(k):
        return form.get(k, [""])[0]

    if parsed.path.endswith("/action/tenant_acl"):
        if not user["admin"]:
            return self.send_html(page(user, "bancos", '<div class="card"><p class="pill bad">Restrito a admin.</p></div>'), 403)

        op = val("op")
        con = db()

        if op == "add":
            tenant = slugify(val("tenant"))
            stype = val("subject_type")
            subject = val("subject").strip()
            if stype not in ["user", "group"]:
                stype = "user"
            if subject:
                con.execute("""
                  INSERT OR IGNORE INTO tenant_acl(tenant,subject_type,subject)
                  VALUES(?,?,?)
                """, (tenant, stype, subject))
                con.commit()
                log_action(user["username"], "tenant_acl_add", tenant, 0, f"{stype}:{subject}", "")
        elif op == "remove":
            rid = val("id")
            row = con.execute("SELECT * FROM tenant_acl WHERE id=?", (rid,)).fetchone()
            con.execute("DELETE FROM tenant_acl WHERE id=?", (rid,))
            con.commit()
            log_action(user["username"], "tenant_acl_remove", row["tenant"] if row else rid, 0, str(dict(row)) if row else "", "")
        con.close()
        return self.redirect("/?tab=bancos")

    if parsed.path.endswith("/action/project_action"):
        slug = val("slug")
        op = val("op")
        rc, out, err = 0, "", ""

        if op in ["sync", "check", "integrate"]:
            con = db()
            p = con.execute("SELECT * FROM projects WHERE slug=?", (slug,)).fetchone()
            tenant = p["tenant"] if p else ""
            script = setting_value("CLOUDIF_PROJECT_INTEGRATION_SCRIPT", "/srv/cloudif/bin/cloudif-project-integrate.sh")
            con.close()

            action = "integrate" if op == "integrate" else op
            rc, out, err = run(["bash", "-lc", f"{script!r} {action!r} {slug!r} {tenant!r} {user['username']!r}"], 180)

            con = db()
            con.execute("UPDATE projects SET komodo_status=?, updated_at=? WHERE slug=?", ("ok" if rc == 0 else "erro", now_iso(), slug))
            con.commit()
            con.close()

            log_action(user["username"], f"project_{op}", slug, rc, out, err)
            return self.redirect("/?tab=git")

    if parsed.path.endswith("/action/tenant_action"):
        tenant = slugify(val("tenant"))
        op = val("op")

        if op in ["delete", "delete_recreate"] and not user["admin"]:
            return self.send_html(page(user, "bancos", '<div class="card"><p class="pill bad">Restrito a admin.</p></div>'), 403)

        if op in ["delete", "delete_recreate"] and not setting_bool("CLOUDIF_ALLOW_ADMIN_DELETE_TENANT", False):
            return self.send_html(page(user, "bancos", '<div class="card"><p class="pill bad">Apagar tenant está desabilitado em CLOUDIF_ALLOW_ADMIN_DELETE_TENANT.</p></div>'), 403)

        if not tenant_visible(tenant, user["username"], user["groups"]):
            return self.send_html(page(user, "bancos", '<div class="card"><p class="pill bad">Sem permissão.</p></div>'), 403)

        tdir = BASE / "tenants" / tenant
        rc, out, err = 0, "", ""

        if op in ["start", "stop", "restart"]:
            cmdop = {"start":"up -d", "stop":"stop", "restart":"restart"}[op]
            rc, out, err = run(["bash","-lc",f"cd {str(tdir)!r} && docker compose --env-file .env {cmdop}"], 180)

        elif op == "keepalive":
            hours = min(max(int(val("hours") or "1"), 1), max_keepalive_hours())
            until = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)).isoformat(timespec="seconds")
            con = db()
            con.execute("""
              INSERT INTO tenant_policy(tenant,always_alive,keepalive_until,max_hours,updated_at)
              VALUES(?,0,?,6,?)
              ON CONFLICT(tenant) DO UPDATE SET
                keepalive_until=excluded.keepalive_until,
                updated_at=excluded.updated_at
            """, (tenant, until, now_iso()))
            con.commit()
            con.close()
            rc, out, err = run(["bash","-lc",f"cd {str(tdir)!r} && docker compose --env-file .env up -d"], 180)

        elif op in ["always_on", "always_off", "always_on_start"]:
            if not user["admin"]:
                return self.send_html(page(user, "bancos", '<div class="card"><p class="pill bad">Restrito a admin.</p></div>'), 403)
            con = db()
            if op in ["always_on", "always_on_start"]:
                con.execute("""
                  INSERT INTO tenant_policy(tenant,always_alive,max_hours,updated_at)
                  VALUES(?,1,24,?)
                  ON CONFLICT(tenant) DO UPDATE SET always_alive=1,max_hours=24,updated_at=excluded.updated_at
                """, (tenant, now_iso()))
                if op == "always_on_start":
                    rc, out, err = run(["bash","-lc",f"cd {str(tdir)!r} && docker compose --env-file .env up -d"], 180)
            else:
                con.execute("""
                  INSERT INTO tenant_policy(tenant,always_alive,max_hours,updated_at)
                  VALUES(?,0,6,?)
                  ON CONFLICT(tenant) DO UPDATE SET always_alive=0,max_hours=6,updated_at=excluded.updated_at
                """, (tenant, now_iso()))
            con.commit()
            con.close()

        elif op == "repair":
            rc, out, err = run(["bash","-lc",f"/usr/local/sbin/cloudif-tenant-ensure-bg.sh {tenant!r} restore {user['username']!r}"], 120)

        elif op == "delete":
            rc, out, err = run(["bash","-lc",f"cd {str(tdir)!r} && docker compose --env-file .env down"], 240)

        elif op == "delete_recreate":
            rc, out, err = run(["bash","-lc",f"cd {str(tdir)!r} && docker compose --env-file .env down && /srv/cloudif/bin/cloudif-create-tenant.real.sh {tenant!r}"], 600)

        log_action(user["username"], op, tenant, rc, out, err)
        return self.redirect("/?tab=bancos")

    return Portal._old_do_POST_v19(self)

Portal._old_do_POST_v19 = Portal.do_POST
Portal.do_POST = do_POST_v19

# ===== CloudIF Portal v19 OIDC + Tenant ACL + Integration Overrides END =====

# ===== CloudIF Portal v20 Fast Banks + Direct OIDC BEGIN =====

_DOCKER_PS_CACHE_V20 = {"ts": 0, "rows": []}

def direct_oidc_url(kind, fallback):
    if not setting_bool("CLOUDIF_USE_DIRECT_OIDC_LINKS", True):
        return fallback
    if kind == "forgejo":
        return setting_value("CLOUDIF_FORGEJO_OIDC_URL", "https://cloudiff.duckdns.org/git/user/oauth2/Authentik/")
    if kind == "komodo":
        return setting_value("CLOUDIF_KOMODO_OIDC_URL", "https://komodoiff.duckdns.org/auth/oidc/login")
    return fallback

def supabase_studio_url(tenant):
    return f"https://{tenant}.{PUBLIC_HOST}/project/default"

def docker_ps_rows_v20():
    """
    Leitura única e rápida dos containers.
    Evita docker compose por tenant durante a abertura da aba Bancos.
    """
    now = time.time()
    if now - _DOCKER_PS_CACHE_V20["ts"] < 3:
        return _DOCKER_PS_CACHE_V20["rows"]

    rc, out, err = run(["bash", "-lc", "docker ps -a --format '{{.Names}}\t{{.Status}}'"], 15)
    rows = []
    if rc == 0:
        for line in out.splitlines():
            if "\t" not in line:
                continue
            name, status = line.split("\t", 1)
            rows.append({"name": name.strip(), "status": status.strip()})

    _DOCKER_PS_CACHE_V20["ts"] = now
    _DOCKER_PS_CACHE_V20["rows"] = rows
    return rows

def service_from_container_v20(tenant, name):
    name = name or ""

    if tenant == "akadmin" and name == "realtime-dev.supabase-realtime":
        return "realtime"

    if tenant == "akadmin":
        if name.startswith("supabase-"):
            svc = name.replace("supabase-", "", 1)
            return {
                "pooler": "supavisor",
                "edge-functions": "functions",
            }.get(svc, svc)
        return ""

    prefixes = [
        f"cloudif_{tenant}-",
        f"cloudif-{tenant}-",
        f"{tenant}-",
    ]

    for prefix in prefixes:
        if name.startswith(prefix):
            svc = name[len(prefix):]
            svc = re.sub(r"-1$", "", svc)
            return svc

    return ""

def compose_services(tenant):
    """
    Override v20: mantém o nome da função usada pelo portal,
    mas troca a implementação para leitura rápida via docker ps.
    """
    rows = docker_ps_rows_v20()
    found = {}

    for r in rows:
        svc = service_from_container_v20(tenant, r["name"])
        if svc:
            found[svc] = r["status"]

    order = [
        "db", "kong", "studio", "auth", "storage", "realtime",
        "rest", "meta", "supavisor", "functions", "imgproxy"
    ]

    out = []
    for svc in order:
        if svc in found:
            out.append({"service": svc, "status": found[svc]})

    for svc, status in sorted(found.items()):
        if svc not in order:
            out.append({"service": svc, "status": status})

    return out

def tenant_is_running(tenant):
    services = compose_services(tenant)
    if not services:
        return False

    good = 0
    for s in services:
        st = (s.get("status") or "").lower()
        if "up" in st or "running" in st or "healthy" in st:
            good += 1

    return good >= 1

def tenant_acl_rows(tenant):
    con = db()
    rows = con.execute("""
      SELECT id, tenant, subject_type, subject
      FROM tenant_acl
      WHERE tenant=?
      ORDER BY subject_type, subject
    """, (tenant,)).fetchall()
    con.close()
    return rows

def tenant_acl_html(tenant, user):
    rows = tenant_acl_rows(tenant)

    if not rows:
        acl_table = '<p class="small">Nenhuma permissão adicional cadastrada. O dono natural ainda pode ser o próprio tenant/usuário.</p>'
    else:
        trs = ""
        for r in rows:
            rm = ""
            if user["admin"]:
                rm = f"""
<form method="post" action="{url('/action/tenant_acl')}" style="display:inline">
  <input type="hidden" name="op" value="remove">
  <input type="hidden" name="id" value="{h(r['id'])}">
  <button class="btn red" type="submit">Remover</button>
</form>"""
            trs += f"<tr><td>{h(r['subject_type'])}</td><td>{h(r['subject'])}</td><td>{rm}</td></tr>"
        acl_table = f"<table><tr><th>Tipo</th><th>Usuário/Grupo</th><th>Ação</th></tr>{trs}</table>"

    add_form = ""
    if user["admin"]:
        add_form = f"""
<div class="grid2">
  <div class="box">
    <h3>Adicionar permissão</h3>
    <form method="post" action="{url('/action/tenant_acl')}">
      <input type="hidden" name="op" value="add">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      <label>Tipo</label>
      <select name="subject_type">
        <option value="user">Usuário</option>
        <option value="group">Grupo</option>
      </select>
      <label>Usuário ou grupo</label>
      <input name="subject" placeholder="ex: aluno123 ou CloudIF-Turma-2026">
      <button class="btn" type="submit">Adicionar</button>
    </form>
  </div>
  <div class="box">
    <h3>Busca AD</h3>
    <p class="small">Pesquise o nome correto do usuário/grupo na aba Administração.</p>
    <a class="btn light" href="{url('?tab=admin')}">Ir para Administração</a>
  </div>
</div>"""

    return acl_table + add_form

def render_bancos(user):
    """
    Renderização dinâmica e rápida.
    Tenants vêm de visible_tenants(), ou seja:
    registry + Authentik/admin + tenant_acl.
    """
    tenants = visible_tenants(user["username"], user["groups"])
    blocks = []
    con = db()

    for t in tenants:
        tenant = t.get("tenant") or ""
        pol = con.execute("SELECT * FROM tenant_policy WHERE tenant=?", (tenant,)).fetchone()

        policy = "-"
        if pol:
            policy = f"Sempre ligado: {'sim' if pol['always_alive'] else 'não'} · Ligado até: {pol['keepalive_until'] or '-'}"

        services = compose_services(tenant)
        running = tenant_is_running(tenant)

        chips = []
        for s in services:
            chips.append(f"""
<div class="container-chip">
  <span class="container-name">{h(s['service'])}</span>
  {status_badge(s.get('status'))}
</div>""")

        hours = "".join(
            f'<option value="{i}">{i} hora{"s" if i > 1 else ""}</option>'
            for i in range(1, max_keepalive_hours()+1)
        )

        studio_link = supabase_studio_url(tenant)

        if running:
            action_buttons = f"""
<a class="btn light" href="{h(studio_link)}" target="_blank">Abrir Studio</a>
<button class="btn gray" name="op" value="stop">Parar</button>
<button class="btn blue" name="op" value="restart">Reiniciar</button>
<select name="hours" style="max-width:150px;display:inline-block">{hours}</select>
<button class="btn" name="op" value="keepalive">Tempo ligado</button>
"""
            if user["admin"]:
                action_buttons += """
<button class="btn amber" name="op" value="always_on">Marcar sempre ligado</button>
<button class="btn gray" name="op" value="always_off">Desativar sempre ligado</button>
"""
        else:
            action_buttons = f"""
<button class="btn" name="op" value="start">Iniciar</button>
<select name="hours" style="max-width:150px;display:inline-block">{hours}</select>
<button class="btn" name="op" value="keepalive">Iniciar temporariamente</button>
"""
            if user["admin"]:
                action_buttons += '<button class="btn amber" name="op" value="always_on_start">Iniciar sempre ligado</button>'
                if setting_bool("CLOUDIF_ALLOW_ADMIN_DELETE_TENANT", False):
                    action_buttons += '<button class="btn red" name="op" value="delete">Apagar banco</button><button class="btn red" name="op" value="delete_recreate">Apagar e recriar</button>'
            if user["admin"] or setting_bool("CLOUDIF_STUDENT_CAN_REPAIR", True):
                action_buttons += '<button class="btn red" name="op" value="repair">Reparar</button>'

        acl_id = "acl_" + re.sub(r"[^a-zA-Z0-9_]+", "_", tenant)

        blocks.append(f"""
<div class="card">
  <div class="section-title">
    <div>
      <h2>{h(tenant)}</h2>
      <p class="small">{h(policy)}</p>
    </div>
    <div>
      <span class="pill {'ok' if running else 'muted'}">{'em execução' if running else 'parado'}</span>
    </div>
  </div>

  <div class="container-grid">
    {''.join(chips) or '<div class="container-chip"><span class="container-name">sem serviços detectados</span><span class="pill muted">-</span></div>'}
  </div>

  <div class="action-group">
    <form method="post" action="{url('/action/tenant_action')}">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      {action_buttons}
    </form>
  </div>

  <div class="action-group">
    <button class="btn light" onclick="togglePanel('{acl_id}')">Permissões do banco</button>
    <div id="{acl_id}" class="wizard-panel">
      {tenant_acl_html(tenant, user)}
    </div>
  </div>
</div>""")

    con.close()

    return f"""
<div class="help">
  A lista é dinâmica e rápida: tenants vêm do registry/permissões, containers vêm de uma leitura única de docker ps.
</div>
{''.join(blocks) or '<div class="card">Nenhum tenant visível.</div>'}"""

def render_git(user):
    status = git_komodo_status()
    projects = user_visible_projects(user["username"], user["groups"])

    forgejo = direct_oidc_url("forgejo", setting_value("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git"))
    komodo = direct_oidc_url("komodo", setting_value("CLOUDIF_KOMODO_URL", "https://komodoiff.duckdns.org/"))

    rows = []
    for p in projects:
        repo = direct_oidc_url("forgejo", p["repo_url"] or setting_value("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git"))
        rows.append(f"""
<tr>
  <td><b>{h(p['name'])}</b><br><span class="small">{h(p['slug'])}</span></td>
  <td><a href="{h(repo)}" target="_blank">Abrir Git</a></td>
  <td><a href="{h(komodo)}" target="_blank">Abrir Komodo</a></td>
  <td><span class="pill muted">{h(p['komodo_status'] or 'not_configured')}</span></td>
  <td>
    <form method="post" action="{url('/action/project_action')}">
      <input type="hidden" name="slug" value="{h(p['slug'])}">
      <button class="btn gray" name="op" value="check">Checar</button>
      <button class="btn blue" name="op" value="sync">Sincronizar</button>
      <button class="btn amber" name="op" value="integrate">Integrar</button>
    </form>
  </td>
</tr>""")

    return f"""
<div class="grid">
  <div class="box"><h3>Forgejo</h3><p>Repositório Git.</p><a class="btn light" href="{h(forgejo)}" target="_blank">Abrir Forgejo OIDC</a></div>
  <div class="box"><h3>Komodo</h3><p>Automação/deploy.</p><a class="btn light" href="{h(komodo)}" target="_blank">Abrir Komodo OIDC</a></div>
  <div class="box"><h3>Webhook</h3><p>Forgejo chama o Forja Agent em alterações.</p></div>
</div>

<div class="card">
  <h2>Projetos integrados</h2>
  <table>
    <tr><th>Projeto</th><th>Git</th><th>Komodo</th><th>Status</th><th>Ações</th></tr>
    {''.join(rows) or '<tr><td colspan="5">Nenhum projeto visível.</td></tr>'}
  </table>
</div>

<div class="card">
  <h2>Diagnóstico geral</h2>
  <form method="post" action="{url('/action/gitkomodo')}">
    <button class="btn gray" name="op" value="status">Checar Forgejo/Komodo agora</button>
  </form>
  <pre>{h(json.dumps(status, ensure_ascii=False, indent=2))}</pre>
</div>"""

# ===== CloudIF Portal v20 Fast Banks + Direct OIDC END =====

# ===== CloudIF Portal v21 Wizard Visual Sync BEGIN =====

_DOCKER_PS_CACHE_V21 = {"ts": 0, "rows": []}

def direct_oidc_url(kind, fallback):
    if not setting_bool("CLOUDIF_USE_DIRECT_OIDC_LINKS", True):
        return fallback
    if kind == "forgejo":
        return setting_value("CLOUDIF_FORGEJO_OIDC_URL", "https://cloudiff.duckdns.org/git/user/oauth2/Authentik/")
    if kind == "komodo":
        return setting_value("CLOUDIF_KOMODO_OIDC_URL", "https://komodoiff.duckdns.org/auth/oidc/login")
    return fallback

def supabase_studio_url(tenant):
    return f"https://{tenant}.{PUBLIC_HOST}/project/default"

def docker_ps_rows_v21():
    now = time.time()
    if now - _DOCKER_PS_CACHE_V21["ts"] < 3:
        return _DOCKER_PS_CACHE_V21["rows"]

    rc, out, err = run(["bash", "-lc", "docker ps -a --format '{{.Names}}\t{{.Status}}'"], 15)
    rows = []
    if rc == 0:
        for line in out.splitlines():
            if "\t" in line:
                name, status = line.split("\t", 1)
                rows.append({"name": name.strip(), "status": status.strip()})

    _DOCKER_PS_CACHE_V21["ts"] = now
    _DOCKER_PS_CACHE_V21["rows"] = rows
    return rows

def service_from_container_v21(tenant, name):
    name = name or ""

    if tenant == "akadmin" and name == "realtime-dev.supabase-realtime":
        return "realtime"

    if tenant == "akadmin":
        if name.startswith("supabase-"):
            svc = name.replace("supabase-", "", 1)
            return {"pooler": "supavisor", "edge-functions": "functions"}.get(svc, svc)
        return ""

    prefixes = [f"cloudif_{tenant}-", f"cloudif-{tenant}-", f"{tenant}-"]
    for prefix in prefixes:
        if name.startswith(prefix):
            svc = name[len(prefix):]
            svc = re.sub(r"-1$", "", svc)
            return svc

    return ""

def compose_services(tenant):
    rows = docker_ps_rows_v21()
    found = {}

    for r in rows:
        svc = service_from_container_v21(tenant, r["name"])
        if svc:
            found[svc] = r["status"]

    order = ["db", "kong", "studio", "auth", "storage", "realtime", "rest", "meta", "supavisor", "functions", "imgproxy"]

    out = []
    for svc in order:
        if svc in found:
            out.append({"service": svc, "status": found[svc]})

    for svc, status in sorted(found.items()):
        if svc not in order:
            out.append({"service": svc, "status": status})

    return out

def tenant_is_running(tenant):
    services = compose_services(tenant)
    if not services:
        return False
    for s in services:
        st = (s.get("status") or "").lower()
        if "up" in st or "running" in st or "healthy" in st:
            return True
    return False

def status_simple(ok):
    return '<span class="pill ok">Online</span>' if ok else '<span class="pill bad">Offline</span>'

def project_acl_rows(slug):
    con = db()
    rows = con.execute("""
      SELECT id, slug, subject_type, subject
      FROM project_acl
      WHERE slug=?
      ORDER BY subject_type, subject
    """, (slug,)).fetchall()
    con.close()
    return rows

def project_acl_html(slug, user):
    rows = project_acl_rows(slug)

    if rows:
        trs = ""
        for r in rows:
            remove = ""
            if user["admin"]:
                remove = f"""
<form method="post" action="{url('/action/project_acl')}" style="display:inline">
  <input type="hidden" name="op" value="remove">
  <input type="hidden" name="id" value="{h(r['id'])}">
  <button class="btn red" type="submit">Remover</button>
</form>"""
            trs += f"<tr><td>{h(r['subject_type'])}</td><td>{h(r['subject'])}</td><td>{remove}</td></tr>"
        table = f"<table><tr><th>Tipo</th><th>Usuário/Grupo</th><th>Ação</th></tr>{trs}</table>"
    else:
        table = '<p class="small">Nenhuma permissão adicional cadastrada para este projeto.</p>'

    if not user["admin"]:
        return table

    return table + f"""
<div class="grid2">
  <div class="box">
    <h3>Adicionar permissão ao projeto</h3>
    <form method="post" action="{url('/action/project_acl')}">
      <input type="hidden" name="op" value="add">
      <input type="hidden" name="slug" value="{h(slug)}">
      <label>Tipo</label>
      <select name="subject_type">
        <option value="user">Usuário</option>
        <option value="group">Grupo</option>
      </select>
      <label>Usuário ou grupo</label>
      <input name="subject" placeholder="ex: aluno123 ou CloudIF-Turma-2026">
      <button class="btn" type="submit">Adicionar</button>
    </form>
  </div>
  <div class="box">
    <h3>Busca AD</h3>
    <p class="small">Pesquise o nome correto na Administração e volte para vincular.</p>
    <a class="btn light" href="{url('?tab=admin')}">Ir para Administração</a>
  </div>
</div>"""

def tenant_acl_rows(tenant):
    con = db()
    rows = con.execute("""
      SELECT id, tenant, subject_type, subject
      FROM tenant_acl
      WHERE tenant=?
      ORDER BY subject_type, subject
    """, (tenant,)).fetchall()
    con.close()
    return rows

def tenant_acl_html(tenant, user):
    rows = tenant_acl_rows(tenant)

    if rows:
        trs = ""
        for r in rows:
            remove = ""
            if user["admin"]:
                remove = f"""
<form method="post" action="{url('/action/tenant_acl')}" style="display:inline">
  <input type="hidden" name="op" value="remove">
  <input type="hidden" name="id" value="{h(r['id'])}">
  <button class="btn red" type="submit">Remover</button>
</form>"""
            trs += f"<tr><td>{h(r['subject_type'])}</td><td>{h(r['subject'])}</td><td>{remove}</td></tr>"
        table = f"<table><tr><th>Tipo</th><th>Usuário/Grupo</th><th>Ação</th></tr>{trs}</table>"
    else:
        table = '<p class="small">Nenhuma permissão adicional cadastrada para este banco.</p>'

    if not user["admin"]:
        return table

    return table + f"""
<div class="grid2">
  <div class="box">
    <h3>Adicionar permissão ao banco</h3>
    <form method="post" action="{url('/action/tenant_acl')}">
      <input type="hidden" name="op" value="add">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      <label>Tipo</label>
      <select name="subject_type">
        <option value="user">Usuário</option>
        <option value="group">Grupo</option>
      </select>
      <label>Usuário ou grupo</label>
      <input name="subject" placeholder="ex: aluno123 ou CloudIF-Turma-2026">
      <button class="btn" type="submit">Adicionar</button>
    </form>
  </div>
  <div class="box">
    <h3>Busca AD</h3>
    <p class="small">Pesquise o nome correto na Administração e volte para vincular.</p>
    <a class="btn light" href="{url('?tab=admin')}">Ir para Administração</a>
  </div>
</div>"""

def render_projects(user):
    rows = user_visible_projects(user["username"], user["groups"])
    tenants = visible_tenants(user["username"], user["groups"])

    allow_git_only = setting_bool("CLOUDIF_ALLOW_GIT_ONLY_PROJECT", True)
    tenant_opts = ""
    if allow_git_only:
        tenant_opts += '<option value="">Sem banco: somente Git/Komodo</option>'
    tenant_opts += "".join(f'<option value="{h(t.get("tenant"))}">{h(t.get("tenant"))}</option>' for t in tenants)

    cards = []
    wizards = []

    for p in rows:
        forgejo = direct_oidc_url("forgejo", p["repo_url"] or setting_value("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git"))
        komodo = direct_oidc_url("komodo", setting_value("CLOUDIF_KOMODO_URL", "https://komodoiff.duckdns.org/"))
        studio = supabase_studio_url(p["tenant"]) if p["tenant"] else ""
        edit_id = "wiz_edit_" + re.sub(r"[^a-zA-Z0-9_]+", "_", p["slug"])
        acl_id = "wiz_acl_" + re.sub(r"[^a-zA-Z0-9_]+", "_", p["slug"])

        studio_btn = f'<a class="btn light" href="{h(studio)}" target="_blank">Abrir Studio</a>' if p["tenant"] else ""

        cards.append(f"""
<div class="project-card">
  <div class="project-line">
    <div>
      <h3>{h(p['name'])}</h3>
      <p class="small">Slug: {h(p['slug'])}</p>
      <p>{h(p['description'] or 'Sem descrição.')}</p>
    </div>
    <div>
      <b>Banco</b><br>
      <span class="pill {'ok' if p['tenant'] else 'muted'}">{h(p['tenant'] or 'sem banco')}</span><br>
      {studio_btn}
    </div>
    <div>
      <b>Painéis</b><br>
      <a class="btn light" href="{h(forgejo)}" target="_blank">Git</a>
      <a class="btn light" href="{h(komodo)}" target="_blank">Komodo</a>
    </div>
    <div>
      <form method="post" action="{url('/action/project_action')}">
        <input type="hidden" name="slug" value="{h(p['slug'])}">
        <button class="btn gray" name="op" value="check">Checar</button>
        <button class="btn blue" name="op" value="sync">Sincronizar</button>
        <button class="btn amber" name="op" value="integrate">Integrar</button>
      </form>
      <button class="btn light" onclick="cloudifShowWizard('{edit_id}')">Editar</button>
      <button class="btn light" onclick="cloudifShowWizard('{acl_id}')">Permissões</button>
    </div>
  </div>
</div>""")

        wizards.append(f"""
<div id="{edit_id}" class="wizard-panel cloudif-wizard">
  <div class="card">
    <h2>Editar projeto: {h(p['name'])}</h2>
    <form method="post" action="{url('/action/project_action')}">
      <input type="hidden" name="slug" value="{h(p['slug'])}">
      <input type="hidden" name="op" value="edit_save">
      <div class="grid2">
        <div>
          <label>Nome</label>
          <input name="name" value="{h(p['name'])}">
        </div>
        <div>
          <label>URL do Git/Forgejo</label>
          <input name="repo_url" value="{h(p['repo_url'])}">
        </div>
      </div>
      <label>Descrição</label>
      <textarea name="description">{h(p['description'])}</textarea>
      <label>Status Komodo</label>
      <input name="komodo_status" value="{h(p['komodo_status'])}">
      <button class="btn" type="submit">Salvar</button>
      <button class="btn gray" type="button" onclick="cloudifCancelWizard()">Cancelar</button>
    </form>
  </div>
</div>""")

        wizards.append(f"""
<div id="{acl_id}" class="wizard-panel cloudif-wizard">
  <div class="card">
    <h2>Permissões do projeto: {h(p['name'])}</h2>
    {project_acl_html(p['slug'], user)}
    <button class="btn gray" type="button" onclick="cloudifCancelWizard()">Voltar</button>
  </div>
</div>""")

    return f"""
<script>
function cloudifShowWizard(id) {{
  var list = document.getElementById('cloudif-project-list');
  if (list) list.style.display = 'none';
  document.querySelectorAll('.cloudif-wizard').forEach(function(el) {{ el.style.display = 'none'; }});
  var target = document.getElementById(id);
  if (target) {{
    target.style.display = 'block';
    window.scrollTo({{top: 0, behavior: 'smooth'}});
  }}
}}
function cloudifCancelWizard() {{
  document.querySelectorAll('.cloudif-wizard').forEach(function(el) {{ el.style.display = 'none'; }});
  var list = document.getElementById('cloudif-project-list');
  if (list) {{
    list.style.display = 'block';
    window.scrollTo({{top: 0, behavior: 'smooth'}});
  }}
}}
</script>

<div id="cloudif-project-list" class="card">
  <div class="section-title">
    <div>
      <h2>Projetos</h2>
      <p class="small">Somente projetos visíveis para seu usuário/grupo aparecem aqui.</p>
    </div>
    <button class="btn" onclick="cloudifShowWizard('wiz_new_project')">Novo projeto</button>
  </div>

  {''.join(cards) or '<div class="box">Nenhum projeto visível ainda.</div>'}
</div>

<div id="wiz_new_project" class="wizard-panel cloudif-wizard">
  <div class="card">
    <h2>Novo projeto</h2>
    <div class="help">Cadastre um projeto com banco Supabase ou somente Git/Komodo.</div>
    <form method="post" action="{url('/action/create_project')}">
      <label>Nome do projeto</label>
      <input name="name" required placeholder="Ex: Sistema de Biblioteca">
      <label>Descrição</label>
      <textarea name="description" placeholder="Objetivo, turma, disciplina ou grupo responsável"></textarea>
      <label>Banco/Tenant Supabase</label>
      <select name="tenant">{tenant_opts}</select>
      <button class="btn" type="submit">Criar / registrar</button>
      <button class="btn gray" type="button" onclick="cloudifCancelWizard()">Cancelar</button>
    </form>
  </div>
</div>

{''.join(wizards)}
"""

def render_bancos(user):
    tenants = visible_tenants(user["username"], user["groups"])
    blocks = []
    con = db()

    for t in tenants:
        tenant = t.get("tenant") or ""
        pol = con.execute("SELECT * FROM tenant_policy WHERE tenant=?", (tenant,)).fetchone()

        policy = "-"
        if pol:
            policy = f"Sempre ligado: {'sim' if pol['always_alive'] else 'não'} · Ligado até: {pol['keepalive_until'] or '-'}"

        services = compose_services(tenant)
        running = tenant_is_running(tenant)

        chips = []
        for s in services:
            chips.append(f"""
<div class="container-chip">
  <span class="container-name">{h(s['service'])}</span>
  {status_badge(s.get('status'))}
</div>""")

        hours = "".join(f'<option value="{i}">{i} hora{"s" if i > 1 else ""}</option>' for i in range(1, max_keepalive_hours()+1))
        studio_link = supabase_studio_url(tenant)
        acl_id = "acl_" + re.sub(r"[^a-zA-Z0-9_]+", "_", tenant)

        if running:
            action_buttons = f"""
<a class="btn light" href="{h(studio_link)}" target="_blank">Abrir Studio</a>
<button class="btn gray" name="op" value="stop">Parar</button>
<button class="btn blue" name="op" value="restart">Reiniciar</button>
<select name="hours" style="max-width:150px;display:inline-block">{hours}</select>
<button class="btn" name="op" value="keepalive">Tempo ligado</button>
"""
            if user["admin"]:
                action_buttons += """
<button class="btn amber" name="op" value="always_on">Sempre ligado</button>
<button class="btn gray" name="op" value="always_off">Desativar sempre ligado</button>
"""
        else:
            action_buttons = f"""
<button class="btn" name="op" value="start">Iniciar</button>
<select name="hours" style="max-width:150px;display:inline-block">{hours}</select>
<button class="btn" name="op" value="keepalive">Iniciar temporariamente</button>
"""
            if user["admin"]:
                action_buttons += '<button class="btn amber" name="op" value="always_on_start">Iniciar sempre ligado</button>'
                if setting_bool("CLOUDIF_ALLOW_ADMIN_DELETE_TENANT", False):
                    action_buttons += '<button class="btn red" name="op" value="delete">Apagar banco</button><button class="btn red" name="op" value="delete_recreate">Apagar e recriar</button>'
            if user["admin"] or setting_bool("CLOUDIF_STUDENT_CAN_REPAIR", True):
                action_buttons += '<button class="btn red" name="op" value="repair">Reparar</button>'

        blocks.append(f"""
<div class="card">
  <div class="section-title">
    <div>
      <h2>{h(tenant)}</h2>
      <p class="small">{h(policy)}</p>
    </div>
    <div><span class="pill {'ok' if running else 'muted'}">{'em execução' if running else 'parado'}</span></div>
  </div>

  <div class="container-grid">
    {''.join(chips) or '<div class="container-chip"><span class="container-name">sem serviços detectados</span><span class="pill muted">-</span></div>'}
  </div>

  <div class="action-group">
    <form method="post" action="{url('/action/tenant_action')}">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      {action_buttons}
    </form>
  </div>

  <div class="action-group">
    <button class="btn light" onclick="togglePanel('{acl_id}')">Permissões do banco</button>
    <div id="{acl_id}" class="wizard-panel">
      {tenant_acl_html(tenant, user)}
    </div>
  </div>
</div>""")

    con.close()
    return f"""
<div class="help">
  Bancos/Tenants são listados dinamicamente conforme permissões. Ações avançadas e auditoria ficam na Administração.
</div>
{''.join(blocks) or '<div class="card">Nenhum tenant visível.</div>'}"""

def render_git(user):
    status = git_komodo_status()
    projects = user_visible_projects(user["username"], user["groups"])

    forgejo = status.get("forgejo", {}) if isinstance(status, dict) else {}
    komodo = status.get("komodo", {}) if isinstance(status, dict) else {}

    forgejo_ok = bool(forgejo.get("ok")) if isinstance(forgejo, dict) else False
    komodo_ok = bool(komodo.get("ok")) if isinstance(komodo, dict) else False

    forgejo_url = direct_oidc_url("forgejo", setting_value("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git"))
    komodo_url = direct_oidc_url("komodo", setting_value("CLOUDIF_KOMODO_URL", "https://komodoiff.duckdns.org/"))

    rows = []
    for p in projects:
        repo = direct_oidc_url("forgejo", p["repo_url"] or setting_value("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git"))
        rows.append(f"""
<tr>
  <td><b>{h(p['name'])}</b><br><span class="small">{h(p['slug'])}</span></td>
  <td><a href="{h(repo)}" target="_blank">Abrir Git</a></td>
  <td><a href="{h(komodo_url)}" target="_blank">Abrir Komodo</a></td>
  <td><span class="pill muted">{h(p['komodo_status'] or 'not_configured')}</span></td>
  <td>
    <form method="post" action="{url('/action/project_action')}">
      <input type="hidden" name="slug" value="{h(p['slug'])}">
      <button class="btn gray" name="op" value="check">Checar</button>
      <button class="btn blue" name="op" value="sync">Sincronizar</button>
      <button class="btn amber" name="op" value="integrate">Integrar</button>
    </form>
  </td>
</tr>""")

    return f"""
<div class="grid">
  <div class="box">
    <h3>Forgejo</h3>
    <p>{status_simple(forgejo_ok)}</p>
    <p class="small">{h(forgejo.get('message','') if isinstance(forgejo, dict) else '')}</p>
    <a class="btn light" href="{h(forgejo_url)}" target="_blank">Abrir Forgejo OIDC</a>
  </div>
  <div class="box">
    <h3>Komodo</h3>
    <p>{status_simple(komodo_ok)}</p>
    <p class="small">{h(komodo.get('message','') if isinstance(komodo, dict) else '')}</p>
    <a class="btn light" href="{h(komodo_url)}" target="_blank">Abrir Komodo OIDC</a>
  </div>
  <div class="box">
    <h3>Integração</h3>
    <p>Checar apenas valida. Sincronizar usa Forgejo. Integrar tenta Forgejo + Komodo.</p>
  </div>
</div>

<div class="card">
  <h2>Projetos integrados</h2>
  <table>
    <tr><th>Projeto</th><th>Git</th><th>Komodo</th><th>Status</th><th>Ações</th></tr>
    {''.join(rows) or '<tr><td colspan="5">Nenhum projeto visível.</td></tr>'}
  </table>
</div>
"""

def do_POST_v21(self):
    init_db()
    user = self.user()
    parsed = urllib.parse.urlparse(self.path)
    length = int(self.headers.get("Content-Length", "0") or 0)
    form = urllib.parse.parse_qs(self.rfile.read(length).decode())

    def val(k):
        return form.get(k, [""])[0]

    if parsed.path.endswith("/action/project_acl"):
        if not user["admin"]:
            return self.send_html(page(user, "projetos", '<div class="card"><p class="pill bad">Restrito a admin.</p></div>'), 403)

        op = val("op")
        con = db()

        if op == "add":
            slug = slugify(val("slug"))
            stype = val("subject_type")
            subject = val("subject").strip()
            if stype not in ["user", "group"]:
                stype = "user"
            if subject:
                con.execute("""
                  INSERT OR IGNORE INTO project_acl(slug,subject_type,subject)
                  VALUES(?,?,?)
                """, (slug, stype, subject))
                con.commit()
                log_action(user["username"], "project_acl_add", slug, 0, f"{stype}:{subject}", "")
        elif op == "remove":
            rid = val("id")
            row = con.execute("SELECT * FROM project_acl WHERE id=?", (rid,)).fetchone()
            con.execute("DELETE FROM project_acl WHERE id=?", (rid,))
            con.commit()
            log_action(user["username"], "project_acl_remove", row["slug"] if row else rid, 0, str(dict(row)) if row else "", "")

        con.close()
        return self.redirect("/?tab=projetos")

    if parsed.path.endswith("/action/tenant_acl"):
        if not user["admin"]:
            return self.send_html(page(user, "bancos", '<div class="card"><p class="pill bad">Restrito a admin.</p></div>'), 403)

        op = val("op")
        con = db()

        if op == "add":
            tenant = slugify(val("tenant"))
            stype = val("subject_type")
            subject = val("subject").strip()
            if stype not in ["user", "group"]:
                stype = "user"
            if subject:
                con.execute("""
                  INSERT OR IGNORE INTO tenant_acl(tenant,subject_type,subject)
                  VALUES(?,?,?)
                """, (tenant, stype, subject))
                con.commit()
                log_action(user["username"], "tenant_acl_add", tenant, 0, f"{stype}:{subject}", "")
        elif op == "remove":
            rid = val("id")
            row = con.execute("SELECT * FROM tenant_acl WHERE id=?", (rid,)).fetchone()
            con.execute("DELETE FROM tenant_acl WHERE id=?", (rid,))
            con.commit()
            log_action(user["username"], "tenant_acl_remove", row["tenant"] if row else rid, 0, str(dict(row)) if row else "", "")

        con.close()
        return self.redirect("/?tab=bancos")

    if parsed.path.endswith("/action/project_action"):
        slug = val("slug")
        op = val("op")

        if op in ["sync", "check", "integrate"]:
            con = db()
            p = con.execute("SELECT * FROM projects WHERE slug=?", (slug,)).fetchone()
            tenant = p["tenant"] if p else ""
            script = setting_value("CLOUDIF_PROJECT_INTEGRATION_SCRIPT", "/srv/cloudif/bin/cloudif-project-integrate.sh")
            con.close()

            action = "integrate" if op == "integrate" else op
            rc, out, err = run(["bash", "-lc", f"{script!r} {action!r} {slug!r} {tenant!r} {user['username']!r}"], 180)

            con = db()
            con.execute("UPDATE projects SET komodo_status=?, updated_at=? WHERE slug=?", ("ok" if rc == 0 else "erro", now_iso(), slug))
            con.commit()
            con.close()

            log_action(user["username"], f"project_{op}", slug, rc, out, err)
            return self.redirect("/?tab=git")

        if op == "edit_save":
            con = db()
            con.execute("""
              UPDATE projects
              SET name=?, description=?, repo_url=?, komodo_status=?, updated_at=?
              WHERE slug=?
            """, (val("name"), val("description"), val("repo_url"), val("komodo_status"), now_iso(), slug))
            con.commit()
            con.close()
            log_action(user["username"], "project_edit_save", slug, 0, "Projeto atualizado.", "")
            return self.redirect("/?tab=projetos")

    return Portal._old_do_POST_v21(self)

Portal._old_do_POST_v21 = Portal.do_POST
Portal.do_POST = do_POST_v21

# ===== CloudIF Portal v21 Wizard Visual Sync END =====


# CloudIF v58 integrations tab override BEGIN
import urllib.parse as _cloudif_v58_urlparse
import urllib.request as _cloudif_v58_urlrequest
import urllib.error as _cloudif_v58_urlerror

def _cloudif_v58_user_from_headers(handler):
    raw_groups = (
        handler.headers.get("X-authentik-groups")
        or handler.headers.get("X-Authentik-Groups")
        or ""
    )
    groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
    username = (
        handler.headers.get("X-authentik-username")
        or handler.headers.get("X-Authentik-Username")
        or handler.headers.get("X-Forwarded-User")
        or "portal"
    )
    email = (
        handler.headers.get("X-authentik-email")
        or handler.headers.get("X-Authentik-Email")
        or ""
    )

    try:
        admin = is_admin(groups)
    except Exception:
        admin = any(g.lower() in ["cloudif-tenants-admin", "cloudif-admin", "domain admins"] for g in groups)

    return {
        "username": username,
        "email": email,
        "groups": groups,
        "admin": admin,
    }

def _cloudif_v58_send_integrations(handler, parsed):
    import cloudif_git_komodo_module as gk

    qs = _cloudif_v58_urlparse.parse_qs(parsed.query)

    project = (
        qs.get("project", [""])[0]
        or getattr(gk, "DEFAULT_PROJECT", "sistema-de-biblioteca-teste")
    )
    tenant = (
        qs.get("tenant", [""])[0]
        or getattr(gk, "DEFAULT_TENANT", "iff1742962")
    )

    user = _cloudif_v58_user_from_headers(handler)
    actor = user.get("username") or "portal"

    body = gk.render_git_komodo_module(
        project=project,
        tenant=tenant,
        actor=actor,
        is_admin=bool(user.get("admin")),
    )

    try:
        html = page(user, "git", body)
    except Exception:
        html = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><title>Integrações CloudIF</title></head><body>""" + body + """</body></html>"""

    return handler.send_html(html)

def _cloudif_v58_parse_post(handler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length).decode("utf-8", "ignore")
    return _cloudif_v58_urlparse.parse_qs(raw)

def _cloudif_v58_redirect(handler, url):
    handler.send_response(303)
    handler.send_header("Location", url)
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()

if "Portal" in globals():
    if not hasattr(Portal, "_cloudif_v58_original_do_GET"):
        Portal._cloudif_v58_original_do_GET = Portal.do_GET

    if not hasattr(Portal, "_cloudif_v58_original_do_POST"):
        Portal._cloudif_v58_original_do_POST = Portal.do_POST

    def _cloudif_v58_do_GET(self):
        parsed = _cloudif_v58_urlparse.urlparse(self.path)
        qs = _cloudif_v58_urlparse.parse_qs(parsed.query)
        tab = (qs.get("tab", [""])[0] or "").lower()

        if tab == "git" or parsed.path.rstrip("/") in [
            "/cloudif/portal/git-komodo",
            "/git-komodo",
        ]:
            return _cloudif_v58_send_integrations(self, parsed)

        return Portal._cloudif_v58_original_do_GET(self)

    def _cloudif_v58_do_POST(self):
        parsed = _cloudif_v58_urlparse.urlparse(self.path)

        if parsed.path.rstrip("/") in [
            "/cloudif/portal/git-komodo/action",
            "/git-komodo/action",
            "/action/gitkomodo",
        ]:
            import cloudif_git_komodo_module as gk

            form = _cloudif_v58_parse_post(self)
            user = _cloudif_v58_user_from_headers(self)
            actor = user.get("username") or "portal"

            ok, msg, res = gk.handle_git_komodo_action(form, actor)

            def val(k, default=""):
                v = form.get(k, [default])
                return v[0] if isinstance(v, list) and v else default

            project = val("project", getattr(gk, "DEFAULT_PROJECT", "sistema-de-biblioteca-teste"))
            tenant = val("tenant", getattr(gk, "DEFAULT_TENANT", "iff1742962"))

            url = (
                "/cloudif/portal/?tab=git"
                + "&project=" + _cloudif_v58_urlparse.quote(project)
                + "&tenant=" + _cloudif_v58_urlparse.quote(tenant)
                + "&msg=" + _cloudif_v58_urlparse.quote(msg)
            )
            return _cloudif_v58_redirect(self, url)

        return Portal._cloudif_v58_original_do_POST(self)

    Portal.do_GET = _cloudif_v58_do_GET
    Portal.do_POST = _cloudif_v58_do_POST
# CloudIF v58 integrations tab override END



# CloudIF v61 modular global override BEGIN
import urllib.parse as _cm_urlparse

def _cm_user(handler):
    groups_raw = handler.headers.get("X-authentik-groups") or handler.headers.get("X-Authentik-Groups") or ""
    groups = [g.strip() for g in groups_raw.split(",") if g.strip()]
    username = handler.headers.get("X-authentik-username") or handler.headers.get("X-Forwarded-User") or "portal"
    email = handler.headers.get("X-authentik-email") or ""
    try:
        admin = is_admin(groups)
    except Exception:
        admin = any(g.lower() in ["cloudif-tenants-admin", "cloudif-admin", "domain admins"] for g in groups)
    return {"username": username, "email": email, "groups": groups, "admin": admin}

def _cm_send(handler, tab, body):
    user = _cm_user(handler)
    try:
        html = page(user, tab or "resumo", body)
    except Exception:
        html = "<!doctype html><html lang='pt-br'><head><meta charset='utf-8'><title>CloudIF</title></head><body>" + body + "</body></html>"
    return handler.send_html(html)

if "Portal" in globals():
    if not hasattr(Portal, "_cloudif_v61_previous_do_GET"):
        Portal._cloudif_v61_previous_do_GET = Portal.do_GET

    def _cloudif_v61_do_GET(self):
        parsed = _cm_urlparse.urlparse(self.path)
        qs = _cm_urlparse.parse_qs(parsed.query)
        tab = (qs.get("tab", ["resumo"])[0] or "resumo").lower()
        classic = (qs.get("classic", ["0"])[0] or "0") == "1"

        if classic:
            # Abre a página original preservada.
            return Portal._cloudif_v61_previous_do_GET(self)

        if parsed.path.rstrip("/") in ["", "/cloudif/portal", "/cloudif/portal/"] or parsed.path == "/":
            if tab in ["resumo", "projetos", "bancos", "git", "admin", "ajuda", "hardware"]:
                import cloudif_ui_modular as cm
                body = cm.render_tab(tab, _cm_user(self))
                return _cm_send(self, tab, body)

        return Portal._cloudif_v61_previous_do_GET(self)

    Portal.do_GET = _cloudif_v61_do_GET
# CloudIF v61 modular global override END



# CloudIF v81 project ACL POST override BEGIN
import urllib.parse as _cloudif_acl_urlparse

def _cloudif_acl_user_from_headers(handler):
    groups_raw = handler.headers.get("X-authentik-groups") or handler.headers.get("X-Authentik-Groups") or ""
    groups = [g.strip() for g in groups_raw.replace("|", ",").split(",") if g.strip()]
    username = handler.headers.get("X-authentik-username") or handler.headers.get("X-Authentik-Username") or handler.headers.get("X-Forwarded-User") or ""
    email = handler.headers.get("X-authentik-email") or handler.headers.get("X-Authentik-Email") or ""
    return {"username": username, "email": email, "groups": groups}

def _cloudif_acl_redirect(handler, url):
    handler.send_response(303)
    handler.send_header("Location", url)
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()

if "Portal" in globals():
    if not hasattr(Portal, "_cloudif_v81_previous_do_POST"):
        Portal._cloudif_v81_previous_do_POST = Portal.do_POST

    def _cloudif_v81_do_POST(self):
        parsed = _cloudif_acl_urlparse.urlparse(self.path)

        if parsed.path.rstrip("/") in ["/cloudif/portal/action/project_acl", "/action/project_acl"]:
            import cloudif_project_acl_module as project_acl

            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length).decode("utf-8", "ignore")
            form = _cloudif_acl_urlparse.parse_qs(raw)
            user = _cloudif_acl_user_from_headers(self)

            def val(k, default=""):
                v = form.get(k, [default])
                return v[0] if isinstance(v, list) and v else default

            slug = val("slug")

            try:
                msg = project_acl.handle_project_acl_action(form, user)
            except Exception as e:
                msg = "Erro: " + str(e)

            url = "/cloudif/portal/?tab=projetos"
            if slug:
                url += "&acl=" + _cloudif_acl_urlparse.quote(slug)
            url += "&msg=" + _cloudif_acl_urlparse.quote(msg)

            return _cloudif_acl_redirect(self, url)

        return Portal._cloudif_v81_previous_do_POST(self)

    Portal.do_POST = _cloudif_v81_do_POST
# CloudIF v81 project ACL POST override END



# CloudIF v84 AD/Samba4 JSON search API BEGIN
import json as _cloudif_ad_json
import re as _cloudif_ad_re
import subprocess as _cloudif_ad_subprocess
import urllib.parse as _cloudif_ad_urlparse

def _cloudif_ad_send_json(handler, payload, status=200):
    raw = _cloudif_ad_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)

def _cloudif_ad_user_from_headers(handler):
    groups_raw = handler.headers.get("X-authentik-groups") or handler.headers.get("X-Authentik-Groups") or ""
    groups = [g.strip() for g in groups_raw.replace("|", ",").split(",") if g.strip()]
    username = (
        handler.headers.get("X-authentik-username")
        or handler.headers.get("X-Authentik-Username")
        or handler.headers.get("X-Forwarded-User")
        or ""
    ).strip().lower()
    email = (
        handler.headers.get("X-authentik-email")
        or handler.headers.get("X-Authentik-Email")
        or ""
    ).strip().lower()

    try:
        admin = is_admin(groups)
    except Exception:
        admin = any(g.lower() in ["cloudif-tenants-admin", "cloudif-admin", "domain admins"] for g in groups)

    return {"username": username, "email": email, "groups": groups, "admin": admin}

def _cloudif_ad_can_manage_project(user, slug):
    if user.get("admin"):
        return True

    if not slug:
        return False

    try:
        row = project_row(slug) if "project_row" in globals() else None
        if row:
            owner = str(row.get("owner") or row.get("created_by") or row.get("username") or "").strip().lower()
            if owner and owner == user.get("username"):
                return True
    except Exception:
        pass

    try:
        visible = user_visible_projects(user.get("username", ""), user.get("groups", []))
        for p in visible:
            if str(p.get("slug") or "") == slug:
                return True
    except Exception:
        pass

    return False

def _cloudif_ad_run(cmd, timeout=12):
    try:
        p = _cloudif_ad_subprocess.run(
            cmd,
            text=True,
            stdout=_cloudif_ad_subprocess.PIPE,
            stderr=_cloudif_ad_subprocess.PIPE,
            timeout=timeout,
        )
        return p.returncode, p.stdout or "", p.stderr or ""
    except Exception as e:
        return 999, "", str(e)

def _cloudif_ad_parse_lines(text, kind):
    out = []
    seen = set()

    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue

        # Remove ruídos comuns.
        if line.lower().startswith(("warning", "error", "failed", "usage")):
            continue

        # samba-tool group list / user list geralmente retorna um nome por linha.
        label = line.split("\t")[0].strip()
        label = label.split(";")[0].strip()

        if not label:
            continue

        if len(label) > 120:
            continue

        # Mantém nomes AD usuais.
        if not _cloudif_ad_re.search(r"[A-Za-z0-9_.@\-]", label):
            continue

        key = (kind, label.lower())
        if key in seen:
            continue
        seen.add(key)

        out.append({
            "type": kind,
            "principal": label,
            "label": label,
        })

    return out

def _cloudif_ad_search_real(q, stype):
    q = (q or "").strip()
    stype = (stype or "all").strip().lower()

    if len(q) < 2:
        return []

    results = []

    # 1) wbinfo é leve e costuma funcionar em host Samba/Winbind.
    if stype in ["all", "user"]:
        rc, out, err = _cloudif_ad_run(["bash", "-lc", "wbinfo -u 2>/dev/null | head -n 2000"])
        if rc == 0 and out:
            results.extend(_cloudif_ad_parse_lines(out, "user"))

    if stype in ["all", "group"]:
        rc, out, err = _cloudif_ad_run(["bash", "-lc", "wbinfo -g 2>/dev/null | head -n 2000"])
        if rc == 0 and out:
            results.extend(_cloudif_ad_parse_lines(out, "group"))

    # 2) Fallback samba-tool.
    if not results and stype in ["all", "user"]:
        rc, out, err = _cloudif_ad_run(["bash", "-lc", "samba-tool user list 2>/dev/null | head -n 2000"])
        if rc == 0 and out:
            results.extend(_cloudif_ad_parse_lines(out, "user"))

    if not results and stype in ["all", "group"]:
        rc, out, err = _cloudif_ad_run(["bash", "-lc", "samba-tool group list 2>/dev/null | head -n 2000"])
        if rc == 0 and out:
            results.extend(_cloudif_ad_parse_lines(out, "group"))

    # 3) Filtro local por substring.
    ql = q.lower()
    filtered = []
    seen = set()

    for item in results:
        label = item["label"]
        if ql not in label.lower():
            continue

        key = (item["type"], label.lower())
        if key in seen:
            continue
        seen.add(key)
        filtered.append(item)

    return filtered[:50]

if "Portal" in globals():
    if not hasattr(Portal, "_cloudif_v84_previous_do_GET"):
        Portal._cloudif_v84_previous_do_GET = Portal.do_GET

    def _cloudif_v84_do_GET(self):
        parsed = _cloudif_ad_urlparse.urlparse(self.path)

        if parsed.path.rstrip("/") == "/cloudif/portal/api/ad-search":
            qs = _cloudif_ad_urlparse.parse_qs(parsed.query)
            q = (qs.get("q", [""])[0] or "").strip()
            stype = (qs.get("type", ["all"])[0] or "all").strip().lower()
            slug = (qs.get("slug", [""])[0] or "").strip()

            user = _cloudif_ad_user_from_headers(self)

            if not _cloudif_ad_can_manage_project(user, slug):
                return _cloudif_ad_send_json(self, {
                    "ok": False,
                    "error": "Sem permissão para pesquisar usuários/grupos para este projeto.",
                    "user": user.get("username") or "unknown",
                }, 403)

            try:
                items = _cloudif_ad_search_real(q, stype)
                return _cloudif_ad_send_json(self, {
                    "ok": True,
                    "query": q,
                    "type": stype,
                    "slug": slug,
                    "count": len(items),
                    "items": items,
                })
            except Exception as e:
                return _cloudif_ad_send_json(self, {
                    "ok": False,
                    "error": str(e),
                    "items": [],
                }, 500)

        return Portal._cloudif_v84_previous_do_GET(self)

    Portal.do_GET = _cloudif_v84_do_GET
# CloudIF v84 AD/Samba4 JSON search API END



# CloudIF v85 complete AD/Samba4 JSON search API BEGIN
import json as _cloudif_v85_json
import urllib.parse as _cloudif_v85_urlparse

def _cloudif_v85_json_response(handler, payload, status=200):
    raw = _cloudif_v85_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)

if "Portal" in globals():
    if not hasattr(Portal, "_cloudif_v85_previous_do_GET"):
        Portal._cloudif_v85_previous_do_GET = Portal.do_GET

    def _cloudif_v85_do_GET(self):
        parsed = _cloudif_v85_urlparse.urlparse(self.path)

        if parsed.path.rstrip("/") == "/cloudif/portal/api/ad-search":
            import cloudif_ad_search_module as adsearch

            qs = _cloudif_v85_urlparse.parse_qs(parsed.query)
            q = (qs.get("q", [""])[0] or "").strip()
            stype = (qs.get("type", ["all"])[0] or "all").strip().lower()
            slug = (qs.get("slug", [""])[0] or "").strip()
            diagnostics = (qs.get("diag", ["0"])[0] or "0") == "1"

            user = adsearch.user_from_headers(self.headers)

            if not adsearch.can_manage_project(user, slug):
                return _cloudif_v85_json_response(self, {
                    "ok": False,
                    "error": "Sem permissão para pesquisar usuários/grupos para este projeto.",
                    "user": user.get("username") or "unknown",
                    "slug": slug,
                    "hint": "A busca exige admin, dono do projeto ou permissão gerencial no projeto."
                }, 403)

            try:
                payload = adsearch.search_ad(q, stype, user=user, diagnostics=diagnostics)
                payload["slug"] = slug
                payload["user"] = user.get("username") or "unknown"
                return _cloudif_v85_json_response(self, payload, 200)
            except Exception as e:
                return _cloudif_v85_json_response(self, {
                    "ok": False,
                    "error": str(e),
                    "items": []
                }, 500)

        return Portal._cloudif_v85_previous_do_GET(self)

    Portal.do_GET = _cloudif_v85_do_GET
# CloudIF v85 complete AD/Samba4 JSON search API END



# CloudIF v86 directory JSON API BEGIN
import json as _cloudif_v86_json
import urllib.parse as _cloudif_v86_urlparse

def _cloudif_v86_send_json(handler, payload, status=200):
    raw = _cloudif_v86_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)

if "Portal" in globals():
    if not hasattr(Portal, "_cloudif_v86_previous_do_GET"):
        Portal._cloudif_v86_previous_do_GET = Portal.do_GET

    def _cloudif_v86_do_GET(self):
        parsed = _cloudif_v86_urlparse.urlparse(self.path)

        if parsed.path.rstrip("/") == "/cloudif/portal/api/ad-search":
            import cloudif_ad_directory_module as directory

            qs = _cloudif_v86_urlparse.parse_qs(parsed.query)
            q = (qs.get("q", [""])[0] or "").strip()
            stype = (qs.get("type", ["all"])[0] or "all").strip().lower()
            slug = (qs.get("slug", [""])[0] or "").strip()
            diag = (qs.get("diag", ["0"])[0] or "0") == "1"

            user = directory.user_from_headers(self.headers)

            if not directory.can_manage_project(user, slug):
                return _cloudif_v86_send_json(self, {
                    "ok": False,
                    "error": "Sem permissão para pesquisar usuários/grupos para este projeto.",
                    "user": user.get("username") or "unknown",
                    "slug": slug
                }, 403)

            try:
                payload = directory.search(q, stype, user=user, diagnostics=diag)
                payload["slug"] = slug
                payload["user"] = user.get("username") or "unknown"
                return _cloudif_v86_send_json(self, payload, 200)
            except Exception as e:
                return _cloudif_v86_send_json(self, {
                    "ok": False,
                    "error": str(e),
                    "items": []
                }, 500)

        return Portal._cloudif_v86_previous_do_GET(self)

    Portal.do_GET = _cloudif_v86_do_GET
# CloudIF v86 directory JSON API END



# CloudIF v89 final AD-search JSON endpoint BEGIN
import json as _cloudif_v89_json
import urllib.parse as _cloudif_v89_urlparse

def _cloudif_v89_send_json(handler, payload, status=200):
    raw = _cloudif_v89_json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)

if "Portal" in globals():
    if not hasattr(Portal, "_cloudif_v89_previous_do_GET"):
        Portal._cloudif_v89_previous_do_GET = Portal.do_GET

    def _cloudif_v89_do_GET(self):
        parsed = _cloudif_v89_urlparse.urlparse(self.path)
        clean_path = parsed.path.rstrip("/")

        # Aceita os dois formatos:
        # - caminho externo antes do rewrite
        # - caminho interno depois do proxy reverso remover /cloudif/portal
        if clean_path in ["/cloudif/portal/api/ad-search", "/api/ad-search"]:
            try:
                import cloudif_ad_directory_module as directory
            except Exception as e:
                return _cloudif_v89_send_json(self, {
                    "ok": False,
                    "error": "Falha ao importar módulo de diretório.",
                    "detail": str(e),
                    "items": []
                }, 500)

            qs = _cloudif_v89_urlparse.parse_qs(parsed.query)
            q = (qs.get("q", [""])[0] or "").strip()
            stype = (qs.get("type", ["all"])[0] or "all").strip().lower()
            slug = (qs.get("slug", [""])[0] or "").strip()
            diag = (qs.get("diag", ["0"])[0] or "0") == "1"

            try:
                user = directory.user_from_headers(self.headers)
            except Exception as e:
                return _cloudif_v89_send_json(self, {
                    "ok": False,
                    "error": "Falha ao ler usuário autenticado.",
                    "detail": str(e),
                    "items": []
                }, 500)

            try:
                allowed = directory.can_manage_project(user, slug)
            except Exception as e:
                return _cloudif_v89_send_json(self, {
                    "ok": False,
                    "error": "Falha ao verificar permissão no projeto.",
                    "detail": str(e),
                    "user": user.get("username") or "unknown",
                    "slug": slug,
                    "items": []
                }, 500)

            if not allowed:
                return _cloudif_v89_send_json(self, {
                    "ok": False,
                    "error": "Sem permissão para pesquisar usuários/grupos para este projeto.",
                    "user": user.get("username") or "unknown",
                    "slug": slug,
                    "items": []
                }, 403)

            try:
                payload = directory.search(q, stype, user=user, diagnostics=diag)
                payload["slug"] = slug
                payload["user"] = user.get("username") or "unknown"
                payload["path"] = clean_path
                return _cloudif_v89_send_json(self, payload, 200)
            except Exception as e:
                return _cloudif_v89_send_json(self, {
                    "ok": False,
                    "error": str(e),
                    "items": []
                }, 500)

        return Portal._cloudif_v89_previous_do_GET(self)

    Portal.do_GET = _cloudif_v89_do_GET
# CloudIF v89 final AD-search JSON endpoint END



# CloudIF v97 safe project_action POST BEGIN
import urllib.parse as _cloudif_v97_urlparse

def _cloudif_v97_redirect(handler, url):
    handler.send_response(303)
    handler.send_header("Location", url)
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()

if "Portal" in globals():
    if not hasattr(Portal, "_cloudif_v97_previous_do_POST"):
        Portal._cloudif_v97_previous_do_POST = Portal.do_POST

    def _cloudif_v97_do_POST(self):
        parsed = _cloudif_v97_urlparse.urlparse(self.path)
        clean_path = parsed.path.rstrip("/")

        if clean_path in ["/cloudif/portal/action/project_action", "/action/project_action", "/project_action"]:
            import cloudif_project_action_safe as safe_project

            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length).decode("utf-8", "ignore")
            form = _cloudif_v97_urlparse.parse_qs(raw)

            try:
                result = safe_project.handle_project_action(form, self.headers)
                slug = result.get("slug", "")
                msg = result.get("message", "Projeto salvo.")
                url = "/cloudif/portal/?tab=projetos"
                if slug:
                    url += "&project=" + _cloudif_v97_urlparse.quote(slug)
                url += "&msg=" + _cloudif_v97_urlparse.quote(msg)
                return _cloudif_v97_redirect(self, url)
            except Exception as e:
                url = "/cloudif/portal/?tab=projetos&msg=" + _cloudif_v97_urlparse.quote("Erro ao salvar projeto: " + str(e))
                return _cloudif_v97_redirect(self, url)

        return Portal._cloudif_v97_previous_do_POST(self)

    Portal.do_POST = _cloudif_v97_do_POST
# CloudIF v97 safe project_action POST END


# CloudIF security origin guard BEGIN
import urllib.parse as _cloudif_sec_urlparse

def _cloudif_security_reject(handler, message, status=403):
    body=("<!doctype html><html><body><h1>Acesso negado</h1><p>" + html.escape(message) + "</p></body></html>").encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def _cloudif_security_valid_origin(handler):
    origin=(handler.headers.get("Origin") or "").strip()
    referer=(handler.headers.get("Referer") or "").strip()
    host=(handler.headers.get("Host") or "").strip().lower()
    # Proxies confiáveis podem encaminhar o host público.
    forwarded=(handler.headers.get("X-Forwarded-Host") or "").split(",")[0].strip().lower()
    allowed={x for x in [host, forwarded, PUBLIC_HOST.lower()] if x}
    candidate=origin or referer
    if not candidate:
        # Compatibilidade com clientes internos antigos; a rede já restringe a origem ao NPM/host.
        return True
    try:
        parsed=_cloudif_sec_urlparse.urlparse(candidate)
        return parsed.netloc.lower() in allowed
    except Exception:
        return False

if "Portal" in globals() and not hasattr(Portal, "_cloudif_security_previous_do_POST"):
    Portal._cloudif_security_previous_do_POST=Portal.do_POST
    def _cloudif_security_do_POST(self):
        if not _cloudif_security_valid_origin(self):
            return _cloudif_security_reject(self, "Origem da requisição não autorizada.")
        return Portal._cloudif_security_previous_do_POST(self)
    Portal.do_POST=_cloudif_security_do_POST
# CloudIF security origin guard END

# CloudIF staging read-only guard BEGIN
def _cloudif_staging_do_POST(self):
    body=b"Staging read-only: POST disabled\n"
    self.send_response(405)
    self.send_header("Content-Type", "text/plain; charset=utf-8")
    self.send_header("Allow", "GET, HEAD")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)
Portal.do_POST=_cloudif_staging_do_POST
# CloudIF staging read-only guard END

if __name__ == "__main__":
    init_db()
    refresh_tenant_policies()
    print(f"CloudIF Portal v17 clean listening on {HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Portal).serve_forever()
