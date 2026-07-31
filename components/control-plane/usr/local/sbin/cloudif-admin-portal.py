
# CloudIF v61 modular lib path BEGIN
import sys as _cloudif_mod_sys
if "/srv/cloudif/lib" not in _cloudif_mod_sys.path:
    _cloudif_mod_sys.path.insert(0, "/srv/cloudif/lib")
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
sys.path.insert(0, '/srv/cloudif/lib')

# CloudIF v57 lib path BEGIN
import sys as _cloudif_sys
if "/srv/cloudif/lib" not in _cloudif_sys.path:
    _cloudif_sys.path.insert(0, "/srv/cloudif/lib")
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
    for sep in (";", "|"):
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
        ("resumo","Início"),
        ("projetos","Meus projetos"),
        ("bancos","Banco de dados"),
        ("git","Código e deploy"),
        ("ajuda","Ajuda"),
    ]
    if user["admin"]:
        tabs.insert(4, ("admin","Administração"))
    nav = "".join(f'<a class="{"active" if tab==k else ""}" href="{url("?tab="+k)}">{v}</a>' for k,v in tabs)
    groups = ", ".join(user["groups"]) or "-"
    if user["admin"]:
        profile_label = "Administrador CloudIF"
    elif "CloudIF-Professor" in user["groups"]:
        profile_label = "Professor"
    elif "CloudIF-Tenants" in user["groups"]:
        profile_label = "Aluno"
    else:
        profile_label = "Acesso básico"

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
    <div class="header-meta">
      <div class="inst-badge">Projetos · Bancos · Git · Komodo</div>
      <div class="ai-project-tag" role="note">✦ Plataforma desenvolvida de forma automática por agentes de IA</div>
    </div>
  </div>
</header>

<div class="wrap">
  <div class="card userbar">
    <div>
      <b>Usuário:</b> {h(user["username"])}
      &nbsp; <b>Email:</b> {h(user["email"] or "-")}
      &nbsp; <b>Perfil:</b> {h(profile_label)}<br>
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
    <div class="ai-disclaimer" role="note"><strong>Aviso de testes e homologação:</strong> esta plataforma e seus projetos foram desenvolvidos com apoio de agentes de IA. Faça backup de suas informações importantes.</div>
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
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=(), serial=()")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Origin-Agent-Cluster", "?1")
        self.send_header("Content-Security-Policy", "default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; object-src 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'")
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
        try:
            import sys as _reconcile_sys
            if "/srv/cloudif/lib" not in _reconcile_sys.path:
                _reconcile_sys.path.insert(0, "/srv/cloudif/lib")
            from cloudif_reconcile_client import ensure_user as _ensure_release_user
            _ensure_release_user(user)
        except Exception:
            pass

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
                rc, out, err = run(["bash","-lc",f"/usr/local/sbin/cloudif-tenant-ensure-bg.sh {tenant!r} restore {user['username']!r}"], 30)

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
                rc, out, err = run(["bash","-lc",f"/usr/local/sbin/cloudif-tenant-ensure-bg.sh {tenant!r} restore {user['username']!r}"], 30)
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
            rc, out, err = run(["bash","-lc",f"/usr/local/sbin/cloudif-tenant-ensure-bg.sh {tenant!r} restore {user['username']!r}"], 30)

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
            rc, out, err = run(["bash","-lc",f"/usr/local/sbin/cloudif-tenant-ensure-bg.sh {tenant!r} restore {user['username']!r}"], 30)

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

    if name == "realtime-dev.supabase-realtime":
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

    if name == "realtime-dev.supabase-realtime":
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
    groups = parse_groups(groups_raw)
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



# CloudIF versioned publication POST BEGIN
import urllib.parse as _cloudif_pub_urlparse

def _cloudif_pub_redirect(handler, url):
    handler.send_response(303)
    handler.send_header("Location", url)
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()

if "Portal" in globals() and not hasattr(Portal, "_cloudif_pub_previous_do_POST"):
    Portal._cloudif_pub_previous_do_POST=Portal.do_POST
    def _cloudif_pub_do_POST(self):
        parsed=_cloudif_pub_urlparse.urlparse(self.path)
        if parsed.path.rstrip("/") in ["/cloudif/portal/action/publication","/action/publication"]:
            import cloudif_portal_publications as publications
            length=int(self.headers.get("Content-Length","0") or "0")
            raw=self.rfile.read(length).decode("utf-8","ignore")
            form=_cloudif_pub_urlparse.parse_qs(raw)
            val=lambda k,d="": (form.get(k) or [d])[0]
            user=_cm_user(self)
            slug=val("slug").strip(); op=val("op").strip()
            try:
                if op=="publish_version":
                    result=publications.publish(slug,user)
                    msg=f"Publicação d{result['deploy_number']} concluída e ativada."
                elif op=="activate_version":
                    result=publications.activate(slug,int(val("deploy_number","0")),user)
                    msg=f"Publicação d{result['deploy_number']} ativada manualmente."
                else:
                    raise ValueError("Operação de publicação inválida.")
                try: log_action(user.get("username") or "portal", "publication_"+op, slug, 0, json.dumps(result,ensure_ascii=False), "")
                except Exception: pass
            except Exception as e:
                msg="Erro na publicação: "+str(e)
                try: log_action(user.get("username") or "portal", "publication_"+op, slug, 1, "", str(e))
                except Exception: pass
            return _cloudif_pub_redirect(self,"/cloudif/portal/?tab=projetos&project="+_cloudif_pub_urlparse.quote(slug)+"&msg="+_cloudif_pub_urlparse.quote(msg))
        return Portal._cloudif_pub_previous_do_POST(self)
    Portal.do_POST=_cloudif_pub_do_POST
# CloudIF versioned publication POST END

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

# CloudIF production CSRF protection BEGIN
import hashlib as _prod_csrf_hashlib
import hmac as _prod_csrf_hmac
import io as _prod_csrf_io
import os as _prod_csrf_os
import re as _prod_csrf_re
import urllib.parse as _prod_csrf_urlparse

_PROD_CSRF_SECRET=_prod_csrf_os.environ.get("CLOUDIF_CSRF_SECRET", "")
if not _PROD_CSRF_SECRET:
    raise RuntimeError("CLOUDIF_CSRF_SECRET ausente")

def _prod_csrf_username(user):
    if isinstance(user, dict):
        return str(user.get("username") or user.get("email") or "anonymous").strip().lower()
    return str(user or "anonymous").strip().lower()

def _prod_csrf_token(user):
    ident=_prod_csrf_username(user)
    return _prod_csrf_hmac.new(_PROD_CSRF_SECRET.encode(), ident.encode(), _prod_csrf_hashlib.sha256).hexdigest()

def _prod_csrf_equal(a,b):
    return bool(a and b and _prod_csrf_hmac.compare_digest(str(a),str(b)))

if "page" in globals() and not globals().get("_prod_csrf_page_wrapped"):
    _prod_csrf_original_page=page
    def page(user, tab, body):
        rendered=_prod_csrf_original_page(user, tab, body)
        token=_prod_csrf_token(user)
        hidden='<input type="hidden" name="csrf_token" value="'+html.escape(token, quote=True)+'">'
        return _prod_csrf_re.sub(r'(<form\b[^>]*>)', r'\1'+hidden, rendered, flags=_prod_csrf_re.I)
    _prod_csrf_page_wrapped=True

if "Portal" in globals() and not hasattr(Portal, "_prod_csrf_previous_do_POST"):
    Portal._prod_csrf_previous_do_POST=Portal.do_POST
    def _prod_csrf_do_POST(self):
        length=int(self.headers.get("Content-Length", "0") or "0")
        if length < 0 or length > 2_000_000:
            return _cloudif_security_reject(self, "Corpo da requisição inválido.", 413)
        raw=self.rfile.read(length)
        ctype=(self.headers.get("Content-Type") or "").lower()
        token=""
        if "application/x-www-form-urlencoded" in ctype or not ctype:
            try:
                form=_prod_csrf_urlparse.parse_qs(raw.decode("utf-8", "ignore"))
                token=(form.get("csrf_token") or [""])[0]
            except Exception:
                token=""
        else:
            token=(self.headers.get("X-CSRF-Token") or "").strip()
        try:
            user=self.user()
        except Exception:
            user={"username":"anonymous"}
        if not _prod_csrf_equal(token, _prod_csrf_token(user)):
            return _cloudif_security_reject(self, "Token CSRF inválido ou ausente.", 403)
        self.rfile=_prod_csrf_io.BytesIO(raw)
        return Portal._prod_csrf_previous_do_POST(self)
    Portal.do_POST=_prod_csrf_do_POST
# CloudIF production CSRF protection END

# CloudIF production UI accessibility layer BEGIN
import re as _prod_ui_re

_PROD_UI_CSS = r"""
<style id="cloudif-accessibility">
.skip-link{position:fixed;left:1rem;top:-5rem;z-index:9999;background:#111827;color:#fff;padding:.75rem 1rem;border-radius:.5rem;text-decoration:none}
.skip-link:focus{top:1rem}
:focus-visible{outline:3px solid #f59e0b;outline-offset:3px}
button,.btn,input,select,textarea,a{min-height:44px}
input,select,textarea{font-size:16px}
.table-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;border-radius:12px}
[role="status"]{min-height:1.5rem}
.logout-btn{margin-left:auto;background:#b91c1c!important;color:#fff!important;border:1px solid #991b1b!important;font-weight:800!important}.logout-btn:hover{background:#991b1b!important}

body{background:linear-gradient(180deg,#f8fbf8 0,#eef4ef 100%);min-height:100vh}
.header{position:sticky;top:0;z-index:100;box-shadow:0 3px 18px rgba(8,96,24,.10)}
.header-inner{padding-block:12px}.if-mark{transform:scale(.82);transform-origin:left center}.brand-title h1{font-size:clamp(1.25rem,2vw,1.75rem)}
.wrap{max-width:1440px}.card,.box{border:1px solid #d7e4d8;box-shadow:0 8px 28px rgba(22,136,33,.07)}
.userbar{display:flex;align-items:center;gap:1rem;background:linear-gradient(135deg,#fff,#f1f8f2)}
.tabs{position:sticky;top:105px;z-index:90;background:rgba(245,247,244,.96);backdrop-filter:blur(10px);padding:.55rem;border:1px solid var(--line);border-radius:14px;box-shadow:0 8px 24px rgba(0,0,0,.05)}
.tabs a{border-radius:10px;font-weight:700;transition:background .18s ease,color .18s ease,transform .18s ease}.tabs a:hover{transform:translateY(-1px)}.tabs a.active{background:var(--if-green-dark);color:#fff;box-shadow:0 4px 12px rgba(8,96,24,.22)}
.kpi{font-variant-numeric:tabular-nums}.pill{font-weight:800}.footer{padding:2rem 0}
@media(max-width:700px){.header{position:static}.tabs{position:static;grid-template-columns:1fr}.if-mark{display:none}.inst-badge{display:none}.userbar{align-items:stretch}.brand-title p{font-size:.8rem}}
.action-danger{border:2px solid var(--danger)}
.visually-hidden{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
@media(max-width:700px){.header-inner{align-items:flex-start;flex-direction:column}.inst-badge{white-space:normal}.tabs{display:grid;grid-template-columns:1fr 1fr}.tabs a{text-align:center}.card{padding:14px}.btn{width:100%;text-align:center;margin:.2rem 0}.userbar>div{width:100%}}
.service-ident{display:flex;align-items:center;gap:10px}.service-icon{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;font-weight:900;color:#fff;background:#176b35}.service-icon.web{background:#2563eb}.service-icon.database{background:#3ecf8e;color:#062a1b}.service-icon.studio{background:#18181b}.service-icon.gateway{background:#7c3aed}.service-icon.auth{background:#ea580c}.service-icon.api{background:#0891b2}.service-icon.realtime{background:#db2777}.service-icon.storage{background:#0284c7}.service-icon.functions{background:#ca8a04}.service-icon.image{background:#4f46e5}.service-icon.metadata{background:#64748b}.service-icon.pool{background:#0f766e}.service-badge{display:inline-flex;padding:5px 8px;border-radius:999px;background:#e7f5eb;color:#14532d;font-size:.75rem;font-weight:800}.service-badge.sensitive{background:#fee2e2;color:#991b1b}.infra-note{padding:12px;border-left:4px solid #f59e0b;background:#fffbeb;color:#7c2d12;border-radius:8px;margin:10px 0}</style>
"""

def _prod_ui_label_forms(doc):
    def repl(m):
        tag=m.group(0)
        if _prod_ui_re.search(r'\baria-label\s*=|\baria-labelledby\s*=',tag,_prod_ui_re.I): return tag
        name_m=_prod_ui_re.search(r'\bname=["\']([^"\']+)',tag,_prod_ui_re.I)
        ph_m=_prod_ui_re.search(r'\bplaceholder=["\']([^"\']+)',tag,_prod_ui_re.I)
        label=(ph_m.group(1) if ph_m else (name_m.group(1).replace('_',' ').title() if name_m else 'Campo de formulário'))
        return tag[:-1]+' aria-label="'+html.escape(label,quote=True)+'">'
    return _prod_ui_re.sub(r'<(?:input|select|textarea)\b[^>]*>',repl,doc,flags=_prod_ui_re.I)

def _prod_ui_enhance(doc):
    doc=doc.replace('<body>','<body><a class="skip-link" href="#conteudo-principal">Pular para o conteúdo principal</a>',1)
    doc=doc.replace('<nav class="tabs">','<nav class="tabs" aria-label="Navegação principal">',1)
    doc=doc.replace('</nav>','<a class="btn logout-btn" href="/outpost.goauthentik.io/sign_out" aria-label="Sair do CloudIF">Sair</a></nav>',1)
    doc=doc.replace('</nav>\n\n  ', '</nav>\n\n  <main id="conteudo-principal" tabindex="-1">',1)
    doc=doc.replace('\n\n  <div class="footer">','</main>\n\n  <div class="footer" role="contentinfo">',1)
    doc=doc.replace('</head>',_PROD_UI_CSS+'\n</head>',1)
    doc=_prod_ui_label_forms(doc)
    doc=_prod_ui_re.sub(r'<table\b([^>]*)>',r'<div class="table-scroll" role="region" aria-label="Tabela rolável" tabindex="0"><table\1>',doc,flags=_prod_ui_re.I)
    doc=doc.replace('</table>','</table></div>')
    for value in ('delete','delete_recreate','remove','stop','repair'):
        pattern=r'<button([^>]*\bvalue=["\']'+_prod_ui_re.escape(value)+r'["\'][^>]*)>'
        def danger(m, value=value):
            attrs=m.group(1)
            if 'onclick=' not in attrs.lower():
                msg='Confirma a operação '+value.replace('_',' ')+'? Esta ação pode afetar serviços ou dados.'
                class_m=_prod_ui_re.search(r'\bclass=["\']([^"\']*)["\']',attrs,_prod_ui_re.I)
                if class_m:
                    current=class_m.group(1)
                    attrs=attrs[:class_m.start()]+f'class="{current} action-danger"'+attrs[class_m.end():]
                else:
                    attrs+=' class="action-danger"'
                attrs+=' onclick="return confirm(\''+msg+'\')"'
            return '<button'+attrs+'>'
        doc=_prod_ui_re.sub(pattern,danger,doc,flags=_prod_ui_re.I)
    doc=doc.replace('>×</button>',' aria-label="Fechar">×</button>')
    return doc

if "page" in globals() and not globals().get("_prod_ui_page_wrapped"):
    _prod_ui_original_page=page
    def page(user, tab, body):
        return _prod_ui_enhance(_prod_ui_original_page(user,tab,body))
    _prod_ui_page_wrapped=True
# CloudIF production UI accessibility layer END

# CloudIF profile-aware admin guard BEGIN
if hasattr(Portal, "do_GET") and not globals().get("_cloudif_admin_guard_wrapped"):
    _cloudif_previous_do_GET = Portal.do_GET
    def _cloudif_guarded_do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if query.get("tab", [""])[0] == "admin" and not self.user().get("admin"):
            self.send_html(page(self.user(), "resumo", '<div class="card"><h2>Acesso restrito</h2><p>Esta área exige o grupo <code>CloudIF-Tenants-Admin</code>.</p><p><a class="btn" href="'+url('?tab=resumo')+'">Voltar ao início</a></p></div>'), 403)
            return
        return _cloudif_previous_do_GET(self)
    Portal.do_GET = _cloudif_guarded_do_GET
    _cloudif_admin_guard_wrapped = True
# CloudIF profile-aware admin guard END


# CloudIF production UI/security v2 BEGIN
import re as _cloudif_v2_re

_CLOUDIF_V2_CSS = r"""
<style id="cloudif-ui-v2">
:root{--cif-primary:#176b35;--cif-primary-2:#0f5132;--cif-accent:#0ea5e9;--cif-surface:#ffffff;--cif-bg:#eef4f0;--cif-border:#d7e4da;--cif-text:#17251c;--cif-muted:#5f6f64;--cif-warning:#b45309;--cif-danger:#b42318;--cif-radius:16px;--cif-shadow:0 10px 28px rgba(20,64,36,.09)}
html{scroll-behavior:smooth}body{background:linear-gradient(180deg,#f8fbf9 0,#eef4f0 260px);color:var(--cif-text)}
.header{background:linear-gradient(120deg,#fff 0,#f4fbf6 60%,#e7f5eb 100%);border-bottom:1px solid var(--cif-border);box-shadow:0 4px 20px rgba(20,64,36,.07);position:sticky;top:0;z-index:40}
.header-inner{min-height:104px}.brand-title h1{font-size:clamp(1.45rem,2vw,2rem);letter-spacing:-.02em}.brand-title p{font-size:.9rem}.inst-badge{background:#eaf7ee;border-color:#b9ddc3;color:#135c2d;font-weight:800}
.wrap{max-width:1440px;margin:auto;padding:24px}.card,.box{border:1px solid var(--cif-border)!important;border-radius:var(--cif-radius)!important;box-shadow:var(--cif-shadow)!important;background:rgba(255,255,255,.97)!important}
.userbar{display:flex;align-items:center;gap:20px;padding:18px 20px!important}.userbar>div:first-child{flex:1}.profile-strip{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:10px}.profile-chip{display:inline-flex;align-items:center;gap:7px;border-radius:999px;padding:7px 11px;font-weight:800;font-size:.82rem;border:1px solid}.profile-chip.student{color:#075985;background:#e0f2fe;border-color:#bae6fd}.profile-chip.teacher{color:#5b21b6;background:#f3e8ff;border-color:#ddd6fe}.profile-chip.admin{color:#9f1239;background:#ffe4e6;border-color:#fecdd3}.profile-chip.domain{color:#374151;background:#f3f4f6;border-color:#d1d5db}
.tabs{display:flex;gap:8px;align-items:center;overflow-x:auto;padding:10px;background:#fff;border:1px solid var(--cif-border);border-radius:15px;box-shadow:0 6px 18px rgba(20,64,36,.06);position:sticky;top:112px;z-index:30}.tabs a{border-radius:10px;padding:11px 14px;white-space:nowrap;font-weight:750;color:#31543b}.tabs a:hover{background:#edf7f0;color:#0d5a2c}.tabs a.active,.tabs a[aria-current="page"]{background:linear-gradient(135deg,var(--cif-primary),var(--cif-primary-2));color:#fff;box-shadow:0 5px 14px rgba(23,107,53,.22)}.tabs .logout-btn{margin-left:auto;position:sticky;right:0}
.portal-hero{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(260px,.7fr);gap:18px;margin:22px 0}.portal-hero-main{padding:26px;background:linear-gradient(135deg,#0f5132,#17823e);color:#fff;border-radius:20px;box-shadow:0 16px 34px rgba(15,81,50,.22)}.portal-hero-main h2{font-size:clamp(1.6rem,3vw,2.5rem);margin:.1rem 0 .5rem}.portal-hero-main p{max-width:760px;color:#e8f7ed}.portal-quick{padding:20px;background:#fff;border:1px solid var(--cif-border);border-radius:20px;box-shadow:var(--cif-shadow)}.quick-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.quick-link{display:flex;align-items:center;justify-content:center;min-height:52px;padding:11px;border-radius:12px;text-decoration:none;background:#f0f8f2;border:1px solid #cfe6d5;color:#155b2e;font-weight:800}.quick-link:hover{background:#e2f2e7;transform:translateY(-1px)}
.grid{gap:18px}.box h3,.card h2,.card h3{letter-spacing:-.015em}.kpi{font-size:clamp(2rem,5vw,3.5rem)!important;color:var(--cif-primary)!important}.pill{font-weight:800}.pill.ok{background:#dcfce7;color:#166534}.pill.bad{background:#fee2e2;color:#991b1b}
.btn,button,input[type="submit"]{border-radius:10px!important;font-weight:800!important;transition:transform .15s ease,box-shadow .15s ease,background .15s ease}.btn:hover,button:hover,input[type="submit"]:hover{transform:translateY(-1px);box-shadow:0 6px 16px rgba(0,0,0,.12)}
input,select,textarea{border:1px solid #b8cbbd!important;border-radius:10px!important;background:#fff!important;padding:11px 12px!important}input:focus,select:focus,textarea:focus{border-color:#168821!important;box-shadow:0 0 0 4px rgba(22,136,33,.14)!important;outline:none!important}
table{border-collapse:separate!important;border-spacing:0!important;width:100%}th{position:sticky;top:0;background:#edf7f0!important;color:#184d2a!important;text-align:left}th,td{padding:12px 13px!important;border-bottom:1px solid #e5eee7!important}tbody tr:hover{background:#f7fbf8}
.empty-state{padding:32px;text-align:center;border:1px dashed #a9c9b1;border-radius:15px;background:#f8fcf9;color:var(--cif-muted)}
.security-note{display:flex;gap:10px;align-items:flex-start;padding:12px 14px;margin:14px 0;background:#eff6ff;border-left:5px solid #2563eb;border-radius:10px;color:#1e3a8a}.footer{margin-top:34px;padding:24px;color:#607066;text-align:center;border-top:1px solid var(--cif-border)}
@media(max-width:900px){.portal-hero{grid-template-columns:1fr}.tabs{top:0;position:relative}.header{position:relative}.quick-grid{grid-template-columns:1fr 1fr}}
@media(max-width:620px){.wrap{padding:14px}.tabs{display:flex!important}.userbar{align-items:flex-start}.portal-hero-main,.portal-quick{padding:18px}.quick-grid{grid-template-columns:1fr}.profile-strip{gap:7px}}
</style>
"""

def _cloudif_v2_profiles(user):
    groups=set(user.get('groups') or [])
    chips=[]
    if 'CloudIF-Tenants' in groups: chips.append('<span class="profile-chip student">● Aluno / tenant</span>')
    if 'CloudIF-Professor' in groups: chips.append('<span class="profile-chip teacher">● Professor</span>')
    if 'CloudIF-Tenants-Admin' in groups or user.get('admin'): chips.append('<span class="profile-chip admin">● Administrador CloudIF</span>')
    if 'Domain Admins' in groups: chips.append('<span class="profile-chip domain">● Administrador do domínio</span>')
    return ''.join(chips) or '<span class="profile-chip student">● Usuário CloudIF</span>'

def _cloudif_v2_enhance(doc,user,tab):
    doc=doc.replace('</head>',_CLOUDIF_V2_CSS+'\n</head>',1)
    if not user.get('admin') and 'CloudIF-Tenants-Admin' not in set(user.get('groups') or []):
        doc=_cloudif_v2_re.sub(r'<a[^>]+href="[^"]*\?tab=admin[^"]*"[^>]*>Administração</a>','',doc,flags=_cloudif_v2_re.I)
    doc=_cloudif_v2_re.sub(r'(<a class="active"[^>]*>)',lambda m:m.group(1)[:-1]+' aria-current="page">',doc,count=1)
    chips=_cloudif_v2_profiles(user)
    marker='<span class="small">Grupos Authentik:'
    pos=doc.find(marker)
    if pos!=-1:
        end=doc.find('</span>',pos)
        if end!=-1: doc=doc[:end+7]+'<div class="profile-strip">'+chips+'</div>'+doc[end+7:]
    if tab=='resumo' and 'class="portal-hero"' not in doc:
        role='administrar a plataforma' if user.get('admin') else ('organizar seus projetos e turmas' if 'CloudIF-Professor' in set(user.get('groups') or []) else 'aprender, criar e publicar')
        hero=f"""<section class="portal-hero" aria-labelledby="boas-vindas"><div class="portal-hero-main"><p>Ambiente acadêmico integrado</p><h2 id="boas-vindas">Olá, {html.escape(user.get('username') or 'usuário')}.</h2><p>Use este painel para {role}, acompanhar bancos, versões publicadas e a saúde dos serviços.</p></div><aside class="portal-quick" aria-label="Atalhos rápidos"><h3>Atalhos rápidos</h3><div class="quick-grid"><a class="quick-link" href="{url('?tab=projetos')}">Projetos</a><a class="quick-link" href="{url('?tab=bancos')}">Bancos</a><a class="quick-link" href="{url('?tab=git')}">Git + Komodo</a><a class="quick-link" href="{url('?tab=hardware')}">Monitor</a></div></aside></section>"""
        target='<main id="conteudo-principal" tabindex="-1">'
        doc=doc.replace(target,target+hero,1)
    doc=doc.replace('<form ','<form autocomplete="off" ',1) if '<form ' in doc else doc
    return doc

if 'page' in globals() and not globals().get('_cloudif_v2_page_wrapped'):
    _cloudif_v2_previous_page=page
    def page(user,tab,body):
        return _cloudif_v2_enhance(_cloudif_v2_previous_page(user,tab,body),user,tab)
    _cloudif_v2_page_wrapped=True

if 'Portal' in globals() and not globals().get('_cloudif_security_headers_wrapped'):
    _cloudif_security_headers_wrapped=True
# CloudIF production UI/security v2 END


# CloudIF projects experience v1 BEGIN
import json as _cpx_json
import urllib.request as _cpx_request
import urllib.parse as _cpx_parse
import re as _cpx_re
import subprocess as _cpx_subprocess
from pathlib import Path as _cpx_Path

_CPX_STYLE=r"""
<style id="cloudif-projects-experience">
html[data-theme="dark"]{color-scheme:dark;--cif-surface:#111b16;--cif-bg:#07110b;--cif-border:#294438;--cif-text:#e7f4eb;--cif-muted:#9bb3a3;--cif-shadow:0 12px 30px #0008}html[data-theme="dark"] body{background:linear-gradient(180deg,#07110b,#0b1710 280px);color:var(--cif-text)}html[data-theme="dark"] .card,html[data-theme="dark"] .box,html[data-theme="dark"] .project-card,html[data-theme="dark"] .cm-card,html[data-theme="dark"] .portal-quick,html[data-theme="dark"] .tabs{background:#111b16!important;border-color:#294438!important;color:#e7f4eb!important}html[data-theme="dark"] input,html[data-theme="dark"] select,html[data-theme="dark"] textarea{background:#0b1510!important;color:#e7f4eb!important;border-color:#345545!important}html[data-theme="dark"] th{background:#173024!important;color:#d8f3df!important}html[data-theme="dark"] tbody tr:hover{background:#16271e}html[data-theme="dark"] .small,html[data-theme="dark"] .cm-muted{color:#9bb3a3!important}
.theme-picker{display:flex;gap:4px;padding:4px;border:1px solid var(--cif-border);border-radius:12px;background:var(--cif-surface);margin-left:auto}.theme-picker button{padding:8px 10px;border:0;background:transparent;color:inherit;border-radius:8px;box-shadow:none!important;transform:none!important}.theme-picker button[aria-pressed="true"]{background:#176b35;color:white}.project-card{overflow:hidden}.project-tabs{display:flex;gap:6px;overflow:auto;padding:10px 0;border-bottom:1px solid var(--cif-border)}.project-tabs button{flex:0 0 auto;border:1px solid var(--cif-border);background:var(--cif-surface);color:inherit;padding:10px 13px}.project-tabs button[aria-selected="true"]{background:#176b35;color:#fff;border-color:#176b35}.project-tab-panel{display:none;padding:16px 0}.project-tab-panel.active{display:block}.project-overview-grid{display:grid;grid-template-columns:minmax(240px,.9fr) minmax(300px,1.1fr);gap:18px}.project-preview{position:relative;aspect-ratio:16/10;border:1px solid var(--cif-border);border-radius:14px;overflow:hidden;background:linear-gradient(135deg,#dff4e5,#eff8f1)}.project-preview iframe{width:100%;height:100%;border:0;background:white}.project-preview-overlay{position:absolute;inset:auto 10px 10px;display:flex;justify-content:space-between;gap:8px;pointer-events:none}.project-preview-overlay span{background:#0b1a10dd;color:white;padding:7px 9px;border-radius:8px;font-size:.78rem}.container-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.container-card{border:1px solid var(--cif-border);border-radius:14px;padding:15px;background:var(--cif-surface)}.service-ident{display:flex;align-items:center;gap:11px;min-width:0}.service-icon{width:42px;height:42px;border-radius:12px;display:inline-flex;align-items:center;justify-content:center;font-weight:900;font-size:.78rem;color:#fff;background:#475569;box-shadow:inset 0 0 0 1px #ffffff33}.service-icon.web{background:linear-gradient(135deg,#2563eb,#0ea5e9)}.service-icon.database,.service-icon.metadata,.service-icon.pool{background:linear-gradient(135deg,#166534,#22c55e)}.service-icon.studio{background:linear-gradient(135deg,#16a34a,#34d399)}.service-icon.gateway,.service-icon.api{background:linear-gradient(135deg,#7c3aed,#a855f7)}.service-icon.auth{background:linear-gradient(135deg,#be123c,#fb7185)}.service-icon.storage,.service-icon.image{background:linear-gradient(135deg,#c2410c,#fb923c)}.service-icon.realtime,.service-icon.functions{background:linear-gradient(135deg,#0f766e,#2dd4bf)}.service-badge{display:inline-flex;margin-top:5px;padding:4px 8px;border-radius:999px;font-size:.72rem;font-weight:800;color:#166534;background:#dcfce7}.service-badge.sensitive{color:#991b1b;background:#fee2e2}.infra-note{padding:12px 14px;margin:12px 0;border-radius:11px;background:#fff7ed;border-left:5px solid #ea580c;color:#9a3412}.shell-unavailable{opacity:.65;cursor:not-allowed!important}.resource-strip{display:flex;gap:9px;flex-wrap:wrap;margin:12px 0}.resource-chip{display:inline-flex;align-items:center;gap:7px;padding:8px 10px;border:1px solid var(--cif-border);border-radius:999px;background:var(--cif-surface);font-weight:800}.container-head{display:flex;justify-content:space-between;gap:10px}.health-dot{width:10px;height:10px;border-radius:50%;display:inline-block;background:#9ca3af}.health-dot.healthy{background:#22c55e}.health-dot.running{background:#38bdf8}.health-dot.stopped,.health-dot.unhealthy{background:#ef4444}.metric-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:12px 0}.metric{padding:10px;background:color-mix(in srgb,var(--cif-surface) 80%,#dcefe2);border-radius:10px}.metric small{display:block;color:var(--cif-muted)}.service-links{display:flex;flex-wrap:wrap;gap:7px}.sheet-backdrop{position:fixed;inset:0;background:#0008;z-index:9998;display:none}.sheet-backdrop.open{display:block}.cloudif-sheet{position:fixed;right:0;top:0;height:100dvh;width:min(620px,94vw);background:var(--cif-surface);color:var(--cif-text);z-index:9999;transform:translateX(105%);transition:transform .22s ease;box-shadow:-20px 0 50px #0005;overflow:auto;padding:22px}.cloudif-sheet.open{transform:none}.sheet-head{display:flex;justify-content:space-between;gap:12px;position:sticky;top:0;background:var(--cif-surface);padding:8px 0 14px;z-index:2}.sheet-close{font-size:1.5rem}.terminal-box{background:#08120c;color:#c7f9d4;border-radius:12px;padding:14px;font-family:ui-monospace,monospace;overflow:auto}.copy-line{display:flex;gap:8px;align-items:center}.copy-line code{flex:1;overflow:auto}.project-card .project-line{display:grid!important}.project-card .project-line>div{margin:0!important}.project-card.cpx-ready .project-line{display:none!important}.tenant-tabs{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}.tenant-tabs button{border:1px solid var(--cif-border);background:var(--cif-surface);color:inherit}.tenant-tabs button.active{background:#176b35;color:#fff}.tenant-panel{display:none}.tenant-panel.active{display:block}
.header-meta{display:flex;flex-direction:column;align-items:flex-end;gap:8px}.ai-project-tag{display:inline-flex;align-items:center;gap:7px;padding:7px 10px;border-radius:999px;background:linear-gradient(135deg,#312e81,#7c3aed);color:#fff;font-size:.76rem;font-weight:900;margin:0}.footer .ai-disclaimer{max-width:900px;margin:0 auto 16px;text-align:left}@media(max-width:760px){.header-meta{width:100%;align-items:stretch}.ai-project-tag{justify-content:center;text-align:center}}.ai-disclaimer{padding:12px 14px;border:1px solid #f59e0b;border-left:5px solid #f59e0b;background:#fffbeb;color:#78350f;border-radius:11px;margin:12px 0}.backup-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:12px 0}.backup-stat{padding:12px;border:1px solid var(--cif-border);border-radius:12px;background:var(--cif-surface)}.backup-list{display:grid;gap:9px;margin-top:12px}.backup-item{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;padding:12px;border:1px solid var(--cif-border);border-radius:12px}.backup-actions{display:flex;gap:8px;flex-wrap:wrap}.backup-status{display:inline-flex;padding:5px 8px;border-radius:999px;font-size:.75rem;font-weight:800}.backup-status.ok{background:#dcfce7;color:#166534}.backup-status.pending{background:#fef3c7;color:#92400e}.backup-status.bad{background:#fee2e2;color:#991b1b}.backup-progress{height:8px;background:#e5e7eb;border-radius:999px;overflow:hidden}.backup-progress>i{display:block;height:100%;background:linear-gradient(90deg,#16a34a,#eab308,#dc2626)}@media(max-width:760px){.project-overview-grid{grid-template-columns:1fr}.theme-picker{width:100%;justify-content:space-between;margin:8px 0}.theme-picker button{flex:1}.container-grid{grid-template-columns:1fr}.metric-grid{grid-template-columns:1fr 1fr}.cloudif-sheet{width:100vw}.project-tabs{scroll-snap-type:x mandatory}.project-tabs button{scroll-snap-align:start}}
@media(prefers-reduced-motion:reduce){.cloudif-sheet{transition:none}}
</style>
"""

_CPX_SCRIPT=r"""
<script id="cloudif-projects-experience-js">
(function(){
 const root=document.documentElement;
 function systemTheme(){return matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}
 function applyTheme(value){localStorage.setItem('cloudif-theme',value);root.dataset.theme=value==='system'?systemTheme():value;document.querySelectorAll('[data-theme-choice]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.themeChoice===value)))}
 window.cloudifApplyTheme=applyTheme;
 applyTheme(localStorage.getItem('cloudif-theme')||'system');
 matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{if((localStorage.getItem('cloudif-theme')||'system')==='system')applyTheme('system')});
 const nav=document.querySelector('.tabs'); if(nav&&!document.querySelector('.theme-picker')){const p=document.createElement('div');p.className='theme-picker';p.setAttribute('aria-label','Tema');p.innerHTML='<button data-theme-choice="light">Claro</button><button data-theme-choice="dark">Escuro</button><button data-theme-choice="system">Sistema</button>';p.querySelectorAll('button').forEach(b=>b.onclick=()=>applyTheme(b.dataset.themeChoice));nav.appendChild(p);applyTheme(localStorage.getItem('cloudif-theme')||'system')}
 const backdrop=document.createElement('div');backdrop.className='sheet-backdrop';document.body.appendChild(backdrop);const sheet=document.createElement('aside');sheet.className='cloudif-sheet';sheet.setAttribute('aria-modal','true');sheet.setAttribute('role','dialog');sheet.innerHTML='<div class="sheet-head"><h2 id="sheet-title">Detalhes</h2><button class="sheet-close" aria-label="Fechar">×</button></div><div id="sheet-body"></div>';document.body.appendChild(sheet);function closeSheet(){sheet.classList.remove('open');backdrop.classList.remove('open')}sheet.querySelector('.sheet-close').onclick=closeSheet;backdrop.onclick=closeSheet;window.cloudifOpenSheet=function(title,html){sheet.querySelector('#sheet-title').textContent=title;sheet.querySelector('#sheet-body').innerHTML=html;sheet.classList.add('open');backdrop.classList.add('open');sheet.querySelector('.sheet-close').focus()};
 function tabs(card,panels){const bar=document.createElement('div');bar.className='project-tabs';Object.entries(panels).forEach(([name,node],i)=>{const id='pt-'+Math.random().toString(36).slice(2);node.classList.add('project-tab-panel');node.id=id;if(i===0)node.classList.add('active');const b=document.createElement('button');b.textContent=name;b.setAttribute('aria-controls',id);b.setAttribute('aria-selected',String(i===0));b.onclick=()=>{bar.querySelectorAll('button').forEach(x=>x.setAttribute('aria-selected','false'));card.querySelectorAll('.project-tab-panel').forEach(x=>x.classList.remove('active'));b.setAttribute('aria-selected','true');node.classList.add('active')};bar.appendChild(b)});card.insertBefore(bar,card.firstChild)}
 document.querySelectorAll('.project-card').forEach((card,idx)=>{const line=card.querySelector('.project-line');if(!line)return;const cols=[...line.children];if(cols.length<4)return;cols.forEach(x=>{x.style.display='block'});const overview=document.createElement('section');overview.innerHTML='<div class="project-overview-grid"><div class="project-meta"></div><div><div class="project-preview"><div class="project-preview-placeholder" style="padding:35px;text-align:center"><strong>Miniatura da publicação</strong><p class="small">A versão ativa aparecerá aqui.</p></div></div><div class="project-overview-actions" style="display:flex;gap:10px;flex-wrap:wrap;margin-top:12px"></div></div></div>';overview.querySelector('.project-meta').append(cols[0]);const meta=overview.querySelector('.project-meta');const sourceSite=cols[3].querySelector('a[href*=".cloudiff.duckdns.org"]');if(sourceSite){const direct=sourceSite.cloneNode(true);direct.textContent='Abrir site';direct.classList.add('btn');direct.removeAttribute('target');direct.setAttribute('rel','noopener');overview.querySelector('.project-overview-actions').appendChild(direct)}const services=document.createElement('section');services.append(cols[1],cols[2]);const containers=document.createElement('section');containers.dataset.role='containers';containers.innerHTML='<h3>Contêineres</h3><div class="empty-state">Carregando telemetria dos contêineres...</div>';const pubs=document.createElement('section');pubs.append(cols[3]);const backups=document.createElement('section');backups.dataset.role='backups';backups.dataset.projectIndex=idx;backups.innerHTML='<h3>Backup do projeto</h3><div class="empty-state">Carregando backups...</div>';const settings=document.createElement('section');settings.innerHTML='<div class="security-note">As ações sensíveis continuam protegidas por sessão, CSRF e permissões do projeto.</div>';tabs(card,{'Visão geral':overview,'Serviços':services,'Contêineres':containers,'Publicações':pubs,'Backup':backups,'Configurações':settings});line.replaceWith(overview,services,containers,pubs,backups,settings);card.dataset.projectIndex=idx;card.classList.add('cpx-ready')});

 const bankMarker=document.createComment('cloudif-bank-tabs-v1');document.body.appendChild(bankMarker);
 if(new URLSearchParams(location.search).get('tab')==='bancos'){
   document.querySelectorAll('main .card').forEach(card=>{
     const title=card.querySelector(':scope > .section-title');
     const services=card.querySelector(':scope > .container-grid');
     const actions=card.querySelectorAll(':scope > .action-group');
     if(!title||!services||!actions.length)return;
     const overview=document.createElement('section');overview.appendChild(title);
     const servicePanel=document.createElement('section');servicePanel.innerHTML='<h3>Serviços do tenant</h3><p class="small">Estado detectado nos serviços do ambiente Supabase.</p>';servicePanel.appendChild(services);
     const operation=document.createElement('section');operation.innerHTML='<h3>Operação</h3><p class="small">Ações de energia, reinício e tempo de disponibilidade.</p>';operation.appendChild(actions[0]);
     const permissions=document.createElement('section');permissions.innerHTML='<h3>Permissões</h3><p class="small">Controle quem pode visualizar e operar este banco.</p>';if(actions[1])permissions.appendChild(actions[1]);
     tabs(card,{'Visão geral':overview,'Serviços':servicePanel,'Operação':operation,'Permissões':permissions});
     card.append(overview,servicePanel,operation,permissions);
   });
 }
 async function loadProjectBackups(){
   try{
     const r=await fetch('/cloudif/portal/api/project-backups',{credentials:'same-origin'});
     if(!r.ok)return;
     const d=await r.json();
     const csrf=(document.querySelector('input[name="csrf_token"]')||{}).value||'';
     document.querySelectorAll('[data-role="backups"]').forEach((panel,idx)=>{
       const p=(d.projects||[])[idx]; if(!p)return;
       const cfg=p.settings||{}; const items=p.items||[]; const remote=cfg.remote||{};
       const remoteClass=remote.status==='synced'?'ok':(remote.status==='sync_failed'?'bad':'pending');
       const remoteText=remote.status==='synced'?'Sincronizado':remote.status==='server_offline'?'Servidor de arquivos offline':remote.status==='pending_configuration'?'Canal remoto pendente':'Aguardando sincronização';
       panel.innerHTML='<h3>Backup do projeto</h3><div class="ai-disclaimer"><strong>Proteja seus dados.</strong> Este projeto foi desenvolvido com apoio de agentes de IA e está em fase de testes e homologação. Mantenha cópias próprias das informações importantes.</div><div class="backup-summary"><div class="backup-stat"><small>Backup automático local</small><strong>'+(cfg.enabled?'Ativado':'Desativado')+'</strong></div><div class="backup-stat"><small>Servidor de arquivos</small><span class="backup-status '+remoteClass+'">'+remoteText+'</span></div><div class="backup-stat"><small>Última execução</small><strong>'+(cfg.last_run||'Ainda não executado')+'</strong></div></div><div class="backup-actions"><button type="button" data-backup-now>Gerar backup agora</button><button type="button" class="light" data-toggle-auto>'+(cfg.enabled?'Desativar automático':'Ativar automático')+'</button>'+(d.can_manage_remote?'<button type="button" class="light" data-toggle-remote>'+(cfg.remote_requested?'Desativar envio remoto':'Ativar envio remoto')+'</button>':'')+'</div><p class="small">O backup de banco contém dumps lógicos. O backup de aplicação contém publicações, configuração e metadados operacionais dos contêineres, sem variáveis de ambiente ou segredos.</p><div class="backup-list">'+(items.length?items.map(x=>'<div class="backup-item"><div><strong>'+(x.type==='database'?'Banco de dados':'Aplicação e contêineres')+'</strong><div class="small">'+x.modified+' · '+formatBytes(x.size)+' · SHA-256 '+x.sha256.slice(0,12)+'…</div></div><a class="btn light" href="/cloudif/portal/download/project-backup?slug='+encodeURIComponent(p.slug)+'&file='+encodeURIComponent(x.filename)+'">Baixar</a></div>').join(''):'<div class="empty-state">Nenhum arquivo disponível.</div>')+'</div>';
       async function post(op,extra={}){const body=new URLSearchParams({csrf_token:csrf,op,slug:p.slug,...extra});const rr=await fetch('/cloudif/portal/action/project-backup',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});if(!rr.ok){alert('Não foi possível concluir a ação de backup.');return}await loadProjectBackups()}
       panel.querySelector('[data-backup-now]').onclick=()=>post('backup_now');
       panel.querySelector('[data-toggle-auto]').onclick=()=>post('set_auto',{enabled:cfg.enabled?'0':'1',remote_requested:cfg.remote_requested?'1':'0'});
       const rb=panel.querySelector('[data-toggle-remote]');if(rb)rb.onclick=()=>post('set_auto',{enabled:cfg.enabled?'1':'0',remote_requested:cfg.remote_requested?'0':'1'});
     });
   }catch(e){console.warn('project backups',e)}
 }
 function formatBytes(n){n=Number(n)||0;for(const u of ['B','KB','MB','GB']){if(n<1024)return n.toFixed(u==='B'?0:1)+' '+u;n/=1024}return n.toFixed(1)+' TB'}
 loadProjectBackups();
 async function telemetry(){
   try{
     const r=await fetch('/cloudif/portal/api/container-telemetry',{credentials:'same-origin'});
     if(!r.ok)return;
     const d=await r.json();
     document.querySelectorAll('.project-card').forEach((card,idx)=>{
       const items=(d.projects&&d.projects[idx]&&d.projects[idx].containers)||[];
       const containerPanel=card.querySelector('[data-role="containers"]');
       if(!containerPanel)return;
       containerPanel.innerHTML='<h3>Contêineres do projeto</h3><div class="resource-strip"><span class="resource-chip"><i class="service-icon storage" style="width:26px;height:26px;font-size:.7rem">F</i>Forgejo</span><span class="resource-chip"><i class="service-icon studio" style="width:26px;height:26px;font-size:.7rem">S</i>Supabase</span><span class="resource-chip"><i class="service-icon metadata" style="width:26px;height:26px;font-size:.7rem">K</i>Komodo Shell</span><span class="resource-chip"><i class="service-icon web" style="width:26px;height:26px;font-size:.7rem">&lt;/&gt;</i>Site web</span></div><p class="small">Somente contêineres de aplicação e do tenant. Infraestrutura global é ocultada por segurança.</p><div class="infra-note">Serviços marcados como <strong>Sensível</strong> exigem cuidado: banco, autenticação, gateway e metadados.</div><div class="container-grid"></div>';
       const grid=containerPanel.querySelector('.container-grid');
       if(!items.length)grid.innerHTML='<div class="empty-state">Nenhum contêiner de publicação encontrado para este projeto.</div>';
       items.forEach(c=>{
         const urls=(c.urls||[]).map(u=>'<a class="btn light" target="_blank" rel="noopener" href="'+u+'">Abrir serviço</a>').join('');
         const remote='km exec '+c.name+' sh -s Forja';
         const el=document.createElement('article');
         el.className='container-card';
         const shellReady=Boolean(d.can_shell && c.shell_supported!==false);
         el.innerHTML='<div class="container-head"><div class="service-ident"><span class="service-icon '+(c.icon||'service')+'">'+(({web:'&lt;/&gt;',database:'DB',studio:'S',gateway:'GW',auth:'AU',api:'API',realtime:'RT',storage:'ST',functions:'FN',image:'IMG',metadata:'META',pool:'POOL'})[c.icon]||'APP')+'</span><div><strong>'+(c.service_title||c.name)+'</strong><div class="small">'+c.name+'</div><span class="service-badge '+(c.sensitive?'sensitive':'')+'">'+(c.sensitive?'Aplicação sensível':'Aplicação do projeto')+'</span></div></div><span><i class="health-dot '+c.health+'"></i> '+c.status+' / '+c.health+'</span></div><p class="small">Imagem: <code>'+c.image+'</code></p><div class="metric-grid"><div class="metric"><small>CPU do contêiner</small><strong>'+c.cpu+'</strong></div><div class="metric"><small>Memória do contêiner</small><strong>'+c.memory+'</strong></div><div class="metric"><small>Rede do contêiner</small><strong>'+c.network_io+'</strong></div><div class="metric"><small>Processos</small><strong>'+c.pids+'</strong></div></div><div class="service-links">'+urls+'<button type="button" class="btn '+(shellReady?'':'shell-unavailable')+'" data-shell '+(shellReady?'':'disabled')+'>'+(shellReady?'Abrir shell':(c.shell_supported===false?'Imagem sem shell':'Sem permissão'))+'</button><button type="button" class="btn light" data-detail>Detalhes</button></div>';
         const shellButton=el.querySelector('[data-shell]');
         if(shellReady)shellButton.onclick=()=>{
           const body='<p>O terminal interativo é fornecido pelo Komodo e usa <code>docker exec</code>.</p><p><a class="btn" target="_blank" rel="noopener" href="/cloudif/portal/action/open-container-shell?container='+encodeURIComponent(c.name)+'">Abrir shell no Komodo</a></p><h3>Acesso remoto</h3><div class="copy-line"><code>'+remote+'</code><button type="button" data-copy-command>Copiar</button></div><p class="small">Contêineres não executam SSH diretamente. Use o CLI do Komodo, que mantém autorização e auditoria.</p>';
           cloudifOpenSheet('Shell — '+c.name,body);
           const copyBtn=document.querySelector('.cloudif-sheet [data-copy-command]');
           if(copyBtn)copyBtn.onclick=()=>navigator.clipboard.writeText(remote);
         };
         el.querySelector('[data-detail]').onclick=()=>cloudifOpenSheet('Detalhes — '+c.name,'<pre class="terminal-box">'+JSON.stringify(c,null,2).replaceAll('<','&lt;')+'</pre>');
         grid.appendChild(el);
       });
       const active=items.find(x=>(x.urls||[]).some(u=>!/-d\d+\./.test(u)));
       if(active&&active.urls&&active.urls[0]){
         const pv=card.querySelector('.project-preview');
         if(pv)pv.innerHTML='<div style="height:100%;display:grid;place-items:center;padding:28px;text-align:center;background:linear-gradient(135deg,#0f5132,#1f9d55);color:white"><div><div style="font-size:3rem;font-weight:900">&lt;/&gt;</div><strong style="font-size:1.2rem">Site publicado</strong><p style="opacity:.9">'+active.urls[0].replace('https://','')+'</p></div></div><div class="project-preview-overlay"><span>'+active.name+'</span><span>'+active.health+'</span></div>';
       }
     });
   }catch(e){console.warn('telemetry',e)}
 }
 telemetry();
 document.addEventListener('keydown',e=>{if(e.key==='Escape')closeSheet()});
})();
</script>
"""

def _cpx_env(path):
    out={}
    try:
        for raw in _cpx_Path(path).read_text().splitlines():
            line=raw.strip()
            if line and not line.startswith('#') and '=' in line:
                k,v=line.split('=',1);out[k.strip()]=v.strip().strip('"\'')
    except Exception: pass
    return out

def _cpx_allowed_projects(user):
    rows=user_visible_projects(user['username'],user['groups'])
    result=[]
    con=db()
    for row in rows:
        p=dict(row)
        pubs=[dict(x) for x in con.execute('select public_number from project_publications where project_slug=? group by public_number',(p['slug'],))]
        result.append({'slug':p['slug'],'name':p['name'],'tenant':p.get('tenant') or p.get('tenant_default') or p.get('owner') or user['username'],'owner':p.get('owner') or user['username'],'public_numbers':[int(x['public_number']) for x in pubs if x.get('public_number')]})
    con.close();return result

def _cpx_fetch_telemetry():
    env=_cpx_env('/etc/cloudif/komodo-publication-client.env')
    token=env.get('KOMODO_PUBLICATION_TOKEN') or env.get('CLOUDIF_PUBLICATION_TOKEN') or ''
    base=(env.get('KOMODO_PUBLICATION_URL') or env.get('KOMODO_AGENT_URL') or 'http://10.62.91.2:18098').rstrip('/')
    if not token:return {'ok':False,'items':[],'error':'telemetry_token_missing'}
    req=_cpx_request.Request(base+'/komodo/containers/telemetry?prefix=cloudif-p',headers={'X-CloudIF-Token':token})
    try:
        with _cpx_request.urlopen(req,timeout=35) as r:return _cpx_json.loads(r.read().decode())
    except Exception as exc:return {'ok':False,'items':[],'error':str(exc)[:160]}


def _cpx_service_meta(service,name):
    svc=(service or '').lower(); nm=(name or '').lower()
    mapping={
      'db':('Banco PostgreSQL','database','supabase',True),
      'studio':('Supabase Studio','studio','supabase',False),
      'kong':('Gateway da API','gateway','supabase',True),
      'auth':('Autenticação','auth','supabase',True),
      'rest':('API REST','api','supabase',False),
      'realtime':('Tempo real','realtime','supabase',False),
      'storage':('Arquivos','storage','supabase',False),
      'functions':('Funções Edge','functions','supabase',False),
      'imgproxy':('Imagens','image','supabase',False),
      'meta':('Metadados do banco','metadata','supabase',True),
      'supavisor':('Pool de conexões','pool','supabase',True),
    }
    if svc in mapping:return mapping[svc]
    if _cpx_re.match(r'^cloudif-p\d+-d\d+-web$',nm):return ('Site publicado','web','web',False)
    return ('Serviço da aplicação','service','application',False)

def _cpx_local_tenant_containers(tenant):
    safe=_cpx_re.sub(r'[^a-zA-Z0-9_.-]','',tenant or '')
    if not safe:return []
    prefix='cloudif_'+safe+'-'
    try:
        with _cpx_request.urlopen('http://127.0.0.1:18081/api/v1.3/docker',timeout=25) as r:
            cad_raw=_cpx_json.loads(r.read().decode())
        stats={}
        for entry in cad_raw.values():
            aliases=entry.get('aliases') or []
            samples=entry.get('stats') or []
            if not aliases or not samples: continue
            latest=samples[-1]; previous=samples[-2] if len(samples)>1 else latest
            try:
                from datetime import datetime as _dt
                t1=_dt.fromisoformat(previous.get('timestamp','').replace('Z','+00:00')).timestamp()
                t2=_dt.fromisoformat(latest.get('timestamp','').replace('Z','+00:00')).timestamp()
                c1=((previous.get('cpu') or {}).get('usage') or {}).get('total') or 0
                c2=((latest.get('cpu') or {}).get('usage') or {}).get('total') or 0
                cpu=max(0.0,((c2-c1)/1e9)/max(0.001,t2-t1)*100.0)
            except Exception: cpu=0.0
            mem=(latest.get('memory') or {}).get('working_set') or (latest.get('memory') or {}).get('usage') or 0
            net=latest.get('network') or {}; rx=net.get('rx_bytes') or 0; tx=net.get('tx_bytes') or 0
            proc=(latest.get('processes') or {}).get('process_count') or (latest.get('task_stats') or {}).get('nr_running') or 0
            row={'cpu':cpu,'memory_bytes':mem,'rx_bytes':rx,'tx_bytes':tx,'pids':proc}
            for alias in aliases: stats[alias]=row
        names=_cpx_subprocess.check_output(['docker','ps','-a','--format','{{.Names}}'],text=True,timeout=15).splitlines()
    except Exception:return []
    out=[]
    for name in sorted(n for n in names if n.startswith(prefix)):
        try: info=_cpx_json.loads(_cpx_subprocess.check_output(['docker','inspect',name],text=True,timeout=15))[0]
        except Exception: continue
        labels=(info.get('Config') or {}).get('Labels') or {}; service=labels.get('com.docker.compose.service') or name.rsplit('-',2)[-2]
        title,icon,brand,sensitive=_cpx_service_meta(service,name); state=info.get('State') or {}; st=stats.get(name) or {}
        def _fmt_bytes(v):
            v=float(v or 0)
            for unit in ('B','KiB','MiB','GiB','TiB'):
                if v < 1024 or unit=='TiB': return f'{v:.1f}{unit}'
                v/=1024
        ports=[]
        for key,vals in ((info.get('NetworkSettings') or {}).get('Ports') or {}).items():
            for v in vals or []: ports.append({'container':key,'host_ip':v.get('HostIp') or '', 'host_port':v.get('HostPort') or ''})
        out.append({'name':name,'image':((info.get('Config') or {}).get('Image') or ''),'status':state.get('Status') or 'unknown','health':((state.get('Health') or {}).get('Status') or ('running' if state.get('Running') else 'stopped')),'cpu':f"{float(st.get('cpu') or 0):.2f}%",'memory':_fmt_bytes(st.get('memory_bytes')),'memory_percent':'-','network_io':_fmt_bytes(st.get('rx_bytes'))+' ↓ / '+_fmt_bytes(st.get('tx_bytes'))+' ↑','block_io':'-','pids':str(st.get('pids') or 0),'ports':ports,'urls':[],'service':service,'service_title':title,'icon':icon,'brand':brand,'category':'application','sensitive':sensitive,'host':'hospedagem','telemetry_source':'cadvisor','shell_supported':service!='rest'})
    return out

def _cpx_send_json(handler,obj,code=200):
    data=_cpx_json.dumps(obj,ensure_ascii=False).encode();handler.send_response(code);handler.send_header('Content-Type','application/json; charset=utf-8');handler.send_header('Cache-Control','no-store');handler.send_header('Content-Length',str(len(data)));handler.end_headers();handler.wfile.write(data)

def _cpx_container_allowed(user,name):
    m=_cpx_re.match(r'^cloudif-p(\d+)-d\d+-web$',name or '')
    if m:
        num=int(m.group(1));return any(num in p['public_numbers'] for p in _cpx_allowed_projects(user))
    for p in _cpx_allowed_projects(user):
        tenant=_cpx_re.sub(r'[^a-zA-Z0-9_.-]','',p.get('tenant') or p.get('owner') or '')
        if tenant and (name or '').startswith('cloudif_'+tenant+'-'): return True
    return False

if 'page' in globals() and not globals().get('_cpx_page_wrapped'):
    _cpx_old_page=page
    def page(user,tab,body):
        doc=_cpx_old_page(user,tab,body)
        doc=doc.replace('</head>',_CPX_STYLE+'</head>',1).replace('</body>',_CPX_SCRIPT+'</body>',1)
        def _forgejo_direct(m):
            repo_path=m.group(1)
            target='https://cloudiff.duckdns.org/git/user/oauth2/Authentik?redirect_to='+_cpx_parse.quote(repo_path if repo_path.startswith('/git/') else '/git'+repo_path,safe='')
            return 'href="'+target+'"'
        doc=_cpx_re.sub(r'href="(https://cloudiff\.duckdns\.org/git/cloudif/[^"]+)"',lambda m:_forgejo_direct(type('M',(),{'group':lambda self,n:_cpx_parse.urlparse(m.group(1)).path})()),doc)
        return doc
    _cpx_page_wrapped=True

if 'Portal' in globals() and not globals().get('_cpx_get_wrapped'):
    _cpx_old_get=Portal.do_GET
    def _cpx_do_GET(self):
        path=_cpx_parse.urlparse(self.path).path
        if path in ('/cloudif/portal/api/container-telemetry','/api/container-telemetry'):
            user=self.user();allowed=_cpx_allowed_projects(user);raw=_cpx_fetch_telemetry();items=raw.get('items') or []
            projects=[]
            tenant_cache={}
            for p in allowed:
                cs=[]
                for c in items:
                    m=_cpx_re.match(r'^cloudif-p(\d+)-d\d+-web$',c.get('name') or '')
                    if m and int(m.group(1)) in p['public_numbers']:
                        c=dict(c); c.update({'service':'web','service_title':'Site publicado','icon':'web','brand':'web','category':'application','sensitive':False,'host':'forja','telemetry_source':'cadvisor+docker','shell_supported':True}); cs.append(c)
                tenant=p.get('tenant') or p.get('owner') or user['username']
                if tenant not in tenant_cache: tenant_cache[tenant]=_cpx_local_tenant_containers(tenant)
                cs.extend([dict(x) for x in tenant_cache[tenant]])
                projects.append({'slug':p['slug'],'name':p['name'],'tenant':tenant,'containers':cs,'linked_resources':[{'kind':'repository','title':'Repositório Forgejo','icon':'forgejo','brand':'forgejo'}]})
            can_shell=bool(user.get('admin') or 'CloudIF-Tenants-Admin' in set(user.get('groups') or []) or 'CloudIF-Professor' in set(user.get('groups') or []))
            return _cpx_send_json(self,{'ok':bool(raw.get('ok')),'can_shell':can_shell,'projects':projects,'generated_at':raw.get('generated_at'),'error':raw.get('error')})
        if path in ('/cloudif/portal/action/open-container-shell','/action/open-container-shell'):
            user=self.user();q=_cpx_parse.parse_qs(_cpx_parse.urlparse(self.path).query);name=(q.get('container') or [''])[0]
            groups=set(user.get('groups') or [])
            can_shell=bool(user.get('admin') or 'CloudIF-Tenants-Admin' in groups or 'CloudIF-Professor' in groups)
            if not can_shell or not _cpx_container_allowed(user,name):return self.send_html(page(user,'projetos','<div class="card"><span class="pill bad">Contêiner não autorizado.</span></div>'),403)
            try:log_action(user['username'],'open_container_shell',name,0,'komodo_terminal','')
            except Exception:pass
            target=setting_value('CLOUDIF_KOMODO_URL','https://komodoiff.duckdns.org/').rstrip('/')
            terminal='sh-'+_cpx_re.sub(r'[^a-zA-Z0-9_.-]+','-',name)[-48:]
            if _cpx_re.match(r'^cloudif-p\d+-d\d+-web$',name):
                server_id='6a1e05634aeaaf27662acc57'
            elif name.startswith('cloudif_') and not _cpx_re.search(r'-rest-\d+$',name):
                server_id='6a5f50072ee3983f6645fdc4'
            else:
                return self.send_html(page(user,'projetos','<div class="card"><span class="pill bad">Esta imagem não possui shell interativo.</span></div>'),422)
            target += '/servers/'+server_id+'/container/'+_cpx_parse.quote(name,safe='')+'/terminal/'+_cpx_parse.quote(terminal,safe='')
            self.send_response(302);self.send_header('Location',target);self.end_headers();return
        return _cpx_old_get(self)
    Portal.do_GET=_cpx_do_GET
    _cpx_get_wrapped=True
# CloudIF projects experience v1 END


# Legacy project backup UI removed after consolidation



# CloudIF project backups consolidated backend BEGIN
import subprocess as _pb_subprocess
import urllib.parse as _pb_parse
from pathlib import Path as _pb_Path

def _pb_project(user,slug):
    return next((p for p in _cpx_allowed_projects(user) if p.get('slug')==slug),None)

def _pb_manage(user,p):
    groups=set(user.get('groups') or [])
    return bool(p and (user.get('admin') or 'CloudIF-Tenants-Admin' in groups or 'CloudIF-Professor' in groups or p.get('owner')==user.get('username')))

def _pb_call(*args,timeout=60):
    raw=_pb_subprocess.check_output(['/usr/local/sbin/cloudif-project-backup.py',*args],text=True,timeout=timeout)
    return _cpx_json.loads(raw)

def _pb_status(slug):
    d=_pb_call('list','--slug',slug)
    cfg=d.get('settings') or {}
    remote=cfg.get('remote') or {'requested':bool(cfg.get('remote_requested')),'status':'server_offline','server':'10.68.128.250'}
    settings={'enabled':bool(cfg.get('enabled')),'last_run':cfg.get('last_run'),'last_result':cfg.get('last_result'),'retention':14,'remote_requested':bool(cfg.get('remote_requested')),'remote':remote}
    items=[]
    for x in d.get('items') or []:
        items.append({'type':x.get('type') or 'application','filename':x.get('filename'),'modified':x.get('modified'),'size':x.get('size',0),'sha256':x.get('sha256',''),'remote':remote.get('status','queued')})
    return settings,items

if 'Portal' in globals() and not globals().get('_pb_consolidated_wrapped'):
    _pb_prev_get=Portal.do_GET;_pb_prev_post=Portal.do_POST
    def _pb_get(self):
        parsed=_pb_parse.urlparse(self.path);path=parsed.path;user=self.user()
        if path in ('/cloudif/portal/api/project-backups','/api/project-backups'):
            q=_pb_parse.parse_qs(parsed.query);slug=(q.get('slug') or [''])[0]
            if slug:
                p=_pb_project(user,slug)
                if not p:return _cpx_send_json(self,{'ok':False,'error':'Projeto não autorizado'},403)
                try:settings,items=_pb_status(slug)
                except Exception as e:return _cpx_send_json(self,{'ok':False,'error':str(e)[:180]},500)
                groups=set(user.get('groups') or [])
                return _cpx_send_json(self,{'ok':True,'slug':slug,'settings':settings,'items':items,'can_manage_auto':bool(user.get('admin') or 'CloudIF-Tenants-Admin' in groups or 'CloudIF-Professor' in groups)})
            projects=[];any_remote=False
            for p in _cpx_allowed_projects(user):
                try:settings,items=_pb_status(p['slug'])
                except Exception as e:settings={'enabled':False,'last_run':None,'remote_requested':False,'remote':{'status':'pending_configuration'},'error':str(e)[:160]};items=[]
                any_remote=any_remote or bool((settings.get('remote') or {}).get('configured'))
                projects.append({'slug':p['slug'],'name':p['name'],'settings':settings,'items':items,'can_manage':_pb_manage(user,p)})
            groups=set(user.get('groups') or [])
            return _cpx_send_json(self,{'ok':True,'can_manage_remote':bool(user.get('admin') or 'CloudIF-Tenants-Admin' in groups or 'CloudIF-Professor' in groups),'projects':projects})
        if path in ('/cloudif/portal/download/project-backup','/download/project-backup'):
            q=_pb_parse.parse_qs(parsed.query);slug=(q.get('slug') or [''])[0];fn=(q.get('file') or [''])[0]
            if not _pb_project(user,slug) or fn!=_pb_Path(fn).name or not fn.endswith('.tar.gz'):return self.send_html(page(user,'projetos','<div class="card"><span class="pill bad">Backup não autorizado.</span></div>'),403)
            root=(_pb_Path('/srv/cloudif/managed-backups/projects')/slug).resolve();f=(root/fn).resolve()
            if root not in f.parents or not f.is_file():return self.send_error(404)
            self.send_response(200);self.send_header('Content-Type','application/gzip');self.send_header('Content-Disposition','attachment; filename="'+fn+'"');self.send_header('Content-Length',str(f.stat().st_size));self.send_header('Cache-Control','private, no-store');self.end_headers()
            with f.open('rb') as src:
                while True:
                    chunk=src.read(1024*1024)
                    if not chunk:break
                    self.wfile.write(chunk)
            try:log_action(user.get('username') or 'portal','download_project_backup',slug,0,fn,'')
            except Exception:pass
            return
        return _pb_prev_get(self)
    def _pb_post(self):
        path=_pb_parse.urlparse(self.path).path
        if path not in ('/cloudif/portal/action/project-backup','/action/project-backup'):return _pb_prev_post(self)
        if not _cloudif_security_valid_origin(self):return _cloudif_security_reject(self,'Origem da requisição não autorizada.')
        length=int(self.headers.get('Content-Length','0') or 0)
        if length<0 or length>2000000:return _cloudif_security_reject(self,'Corpo inválido.',413)
        form=_pb_parse.parse_qs(self.rfile.read(length).decode('utf-8','ignore'));user=self.user();token=(form.get('csrf_token') or [''])[0]
        if not _prod_csrf_equal(token,_prod_csrf_token(user)):return _cpx_send_json(self,{'ok':False,'error':'csrf'},403)
        slug=(form.get('slug') or [''])[0];op=(form.get('op') or [''])[0];p=_pb_project(user,slug)
        if not _pb_manage(user,p):return _cpx_send_json(self,{'ok':False,'error':'forbidden'},403)
        try:
            if op in ('backup_now','backup'):_pb_subprocess.Popen(['/usr/local/sbin/cloudif-project-backup.py','backup','--slug',slug],stdin=_pb_subprocess.DEVNULL,stdout=_pb_subprocess.DEVNULL,stderr=_pb_subprocess.DEVNULL,start_new_session=True);result={'accepted':True}
            elif op=='set_auto':
                enabled=(form.get('enabled') or ['0'])[0];remote=(form.get('remote_requested') or ['0'])[0]
                result=_pb_call('set-auto','--slug',slug,'--enabled',enabled,'--remote-requested',remote)
            else:raise ValueError('invalid_operation')
            try:log_action(user.get('username') or 'portal','project_backup_'+op,slug,0,'backup','')
            except Exception:pass
            return _cpx_send_json(self,{'ok':True,'result':result},202 if op in ('backup_now','backup') else 200)
        except Exception as e:return _cpx_send_json(self,{'ok':False,'error':str(e)[:180]},500)
    Portal.do_GET=_pb_get;Portal.do_POST=_pb_post;_pb_consolidated_wrapped=True
# CloudIF project backups consolidated backend END


# Duplicate project backup UI removed after consolidation


# CloudIF dynamic repair dashboard BEGIN
import urllib.request as _rd_req
import urllib.parse as _rd_parse
import json as _rd_json
import html as _rd_html

def _rd_env(path='/etc/cloudif/komodo-agent-client.env'):
    out={}
    try:
        for line in open(path,encoding='utf-8'):
            if '=' in line and not line.lstrip().startswith('#'):
                k,v=line.rstrip().split('=',1);out[k]=v.strip().strip('"').strip("'")
    except Exception:pass
    return out

def _rd_agent(path,payload,timeout=35):
    e=_rd_env();base=(e.get('KOMODO_AGENT_URL') or 'http://10.62.91.2:18098').rstrip('/');token=e.get('KOMODO_AGENT_TOKEN') or ''
    raw=_rd_json.dumps(payload).encode();req=_rd_req.Request(base+path,data=raw,method='POST',headers={'Content-Type':'application/json','X-CloudIF-Token':token,'Authorization':'Bearer '+token})
    with _rd_req.urlopen(req,timeout=timeout) as r:return _rd_json.loads(r.read().decode())


def _rd_forja(path,payload,timeout=45):
    e=_rd_env('/etc/cloudif/forja-agent-client.env');base=(e.get('FORJA_AGENT_URL') or 'http://10.62.91.2:18097').rstrip('/');token=e.get('FORJA_AGENT_TOKEN') or ''
    raw=_rd_json.dumps(payload).encode();req=_rd_req.Request(base+path,data=raw,method='POST',headers={'Content-Type':'application/json','X-CloudIF-Token':token,'Authorization':'Bearer '+token})
    with _rd_req.urlopen(req,timeout=timeout) as r:return _rd_json.loads(r.read().decode())

def _rd_canonical_repo(slug):
    slug=_rd_parse.quote(str(slug or '').strip().lower(),safe='-')
    name=slug if slug.startswith('cloudif-') else 'cloudif-'+slug
    return name,'https://cloudiff.duckdns.org/git/cloudif/'+name

def _rd_projects(user):
    from cloudif_ui_data import discover_projects
    allowed={p.get('slug') for p in _cpx_allowed_projects(user)}
    rows=[]
    for p in discover_projects():
        if p.get('slug') not in allowed:continue
        sid=p.get('komodo_stack_id') or p.get('stack_id')
        rows.append({'slug':p.get('slug'),'name':p.get('name') or p.get('slug'),'tenant':p.get('tenant') or p.get('owner') or '',
          'stack_id':sid or '','service':p.get('komodo_service') or 'web'})
    return rows

def _rd_can_repair(user):
    groups=set(user.get('groups') or [])
    return bool(user.get('admin') or 'CloudIF-Tenants-Admin' in groups or 'CloudIF-Professor' in groups)

def _rd_page(user):
    csrf=_prod_csrf_token(user)
    body="""<section class="rd-wrap"><div class="rd-head"><div><p class="rd-eyebrow">Operação assistida</p><h2>Verificação e reparação</h2><p>Monitora stacks, containers, compose e terminais do Komodo em tempo real.</p></div><div class="rd-actions"><button id="rd-refresh">Verificar agora</button><button id="rd-repair-all" class="danger">Reparar necessários</button></div></div>
<div class="rd-summary"><article><span>Saudáveis</span><strong id="rd-ok">0</strong></article><article><span>Atenção</span><strong id="rd-warn">0</strong></article><article><span>Críticos</span><strong id="rd-bad">0</strong></article><article><span>Total</span><strong id="rd-total">0</strong></article></div>
<div class="rd-chart"><div class="rd-ring" id="rd-ring"><span id="rd-score">0%</span></div><div><h3>Saúde geral</h3><p id="rd-updated">Aguardando verificação…</p><div class="rd-legend"><i class="ok"></i>Saudável <i class="warn"></i>Atenção <i class="bad"></i>Crítico</div></div></div>
<div class="rd-tools"><input id="rd-search" placeholder="Buscar projeto, tenant ou stack"><select id="rd-filter"><option value="all">Todos</option><option value="healthy">Saudáveis</option><option value="warning">Atenção</option><option value="critical">Críticos</option></select><label><input type="checkbox" id="rd-auto" checked> Atualização automática</label></div>
<div id="rd-grid" class="rd-grid"><div class="rd-loading">Carregando diagnóstico…</div></div></section>
<style>
.rd-wrap{display:grid;gap:18px}.rd-head{display:flex;justify-content:space-between;gap:18px;align-items:center;padding:24px;border-radius:20px;background:linear-gradient(135deg,#10291d,#174d32);color:#fff}.rd-head h2{margin:.15rem 0;font-size:clamp(1.7rem,4vw,2.5rem)}.rd-eyebrow{text-transform:uppercase;letter-spacing:.12em;font-weight:800;color:#8ff0b6}.rd-actions{display:flex;gap:10px;flex-wrap:wrap}.rd-actions button,.rd-card button{border:0;border-radius:10px;padding:11px 15px;font-weight:800;cursor:pointer;background:#28c76f;color:#082113}.rd-actions .danger,.rd-card .danger{background:#ffb020;color:#291900}.rd-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.rd-summary article{padding:18px;border:1px solid var(--cif-border,#d9e2dc);border-radius:16px;background:var(--cif-surface,#fff)}.rd-summary span{display:block;color:var(--cif-muted,#667);font-size:.86rem}.rd-summary strong{font-size:2rem}.rd-chart{display:flex;align-items:center;gap:22px;padding:22px;border-radius:18px;border:1px solid var(--cif-border,#ddd);background:var(--cif-surface,#fff)}.rd-ring{width:130px;height:130px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(#28c76f 0%,#24322a 0);position:relative}.rd-ring:after{content:"";position:absolute;inset:15px;border-radius:50%;background:var(--cif-surface,#fff)}.rd-ring span{position:relative;z-index:1;font-size:1.5rem;font-weight:900}.rd-legend{display:flex;gap:9px;align-items:center;flex-wrap:wrap}.rd-legend i{width:10px;height:10px;border-radius:50%}.rd-legend .ok{background:#28c76f}.rd-legend .warn{background:#ffb020}.rd-legend .bad{background:#ef5350}.rd-tools{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.rd-tools input,.rd-tools select{min-height:44px;border:1px solid var(--cif-border,#ccc);border-radius:10px;padding:0 12px;background:var(--cif-surface,#fff);color:inherit}.rd-tools input{flex:1;min-width:220px}.rd-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px}.rd-card{border:1px solid var(--cif-border,#ddd);border-left:6px solid #777;border-radius:16px;padding:18px;background:var(--cif-surface,#fff);box-shadow:0 8px 22px #0001}.rd-card.healthy{border-left-color:#28c76f}.rd-card.warning{border-left-color:#ffb020}.rd-card.critical{border-left-color:#ef5350}.rd-card h3{margin:0 0 4px;word-break:break-word}.rd-meta{color:var(--cif-muted,#667);font-size:.88rem}.rd-pills{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0}.rd-pill{padding:5px 8px;border-radius:999px;background:#e8ece9;font-size:.78rem;font-weight:800;color:#243}.rd-card ul{padding-left:19px;min-height:38px}.rd-card footer{display:flex;gap:8px;flex-wrap:wrap}.rd-card a{display:inline-flex;align-items:center;padding:10px 13px;border-radius:10px;text-decoration:none;background:#e7efe9;color:#174d32;font-weight:800}.rd-loading{padding:30px;text-align:center}.rd-spin{opacity:.65;pointer-events:none}@media(max-width:720px){.rd-head{align-items:flex-start;flex-direction:column}.rd-summary{grid-template-columns:1fr 1fr}.rd-chart{align-items:flex-start}.rd-ring{width:105px;height:105px;flex:none}}
</style>
<script>
(()=>{const csrf=__CSRF__;const grid=document.getElementById('rd-grid'),search=document.getElementById('rd-search'),filter=document.getElementById('rd-filter');let rows=[];const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function level(x){if(!x.stack_id||x.error||x.missing_files?.length)return'critical';if(x.healthy)return'healthy';return'warning'}
function render(){const q=search.value.toLowerCase(),f=filter.value;const shown=rows.filter(x=>(f==='all'||level(x)===f)&&JSON.stringify(x).toLowerCase().includes(q));grid.innerHTML=shown.length?shown.map(x=>{const l=level(x),issues=(x.issues||[]).map(i=>'<li>'+esc({'missing_stack_id':'Stack não vinculado','missing_compose':'docker-compose.yml ausente','stack_not_running':'Stack parado','terminal_invalid':'Terminal ausente ou shell inválido','stack_unavailable':'Stack indisponível'}[i]||i)+'</li>').join('');const term=x.stack_id?'/cloudiff/portal/action/open-project-terminal?slug='+encodeURIComponent(x.project):'#';return`<article class="rd-card ${l}" data-project="${esc(x.project)}"><h3>${esc(x.name||x.project)}</h3><div class="rd-meta">${esc(x.tenant||'')} · ${esc(x.stack_name||x.stack_id||'sem stack')}</div><div class="rd-pills"><span class="rd-pill">${esc(x.state||'desconhecido')}</span><span class="rd-pill">terminal ${x.terminal_ok?'OK':'pendente'}</span><span class="rd-pill">${esc(x.service||'web')}</span></div><ul>${issues||'<li>Nenhum problema detectado.</li>'}</ul><footer><button data-repair="${esc(x.project)}" ${!x.can_repair?'disabled':''}>Reparar</button><a target="_blank" href="${term}">Abrir terminal</a></footer></article>`}).join(''):'<div class="rd-loading">Nenhum projeto encontrado.</div>';grid.querySelectorAll('[data-repair]').forEach(b=>b.onclick=()=>repair(b.dataset.repair,b));}
function summary(){const total=rows.length,ok=rows.filter(x=>level(x)==='healthy').length,warn=rows.filter(x=>level(x)==='warning').length,bad=total-ok-warn,score=total?Math.round(ok/total*100):0;document.getElementById('rd-ok').textContent=ok;document.getElementById('rd-warn').textContent=warn;document.getElementById('rd-bad').textContent=bad;document.getElementById('rd-total').textContent=total;document.getElementById('rd-score').textContent=score+'%';document.getElementById('rd-ring').style.background=`conic-gradient(#28c76f ${score}%,#26362d 0)`;document.getElementById('rd-updated').textContent='Atualizado em '+new Date().toLocaleTimeString('pt-BR');}
async function load(){grid.classList.add('rd-spin');try{const r=await fetch('/cloudiff/portal/api/repair-dashboard',{credentials:'same-origin'});const d=await r.json();rows=d.items||[];summary();render()}catch(e){grid.innerHTML='<div class="rd-loading">Falha ao consultar o agente.</div>'}finally{grid.classList.remove('rd-spin')}}
async function repair(project,btn){btn.disabled=true;btn.textContent='Reparando…';try{const body=new URLSearchParams({csrf_token:csrf,project});const r=await fetch('/cloudiff/portal/action/repair-project',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});const d=await r.json();if(!r.ok)alert(d.error||'Falha na reparação');await load()}finally{btn.disabled=false;btn.textContent='Reparar'}}
document.getElementById('rd-refresh').onclick=load;document.getElementById('rd-repair-all').onclick=async()=>{for(const x of rows.filter(x=>level(x)!=='healthy'&&x.can_repair)){const b=grid.querySelector(`[data-repair="${CSS.escape(x.project)}"]`);await repair(x.project,b||{disabled:false,textContent:''})}};search.oninput=render;filter.onchange=render;load();setInterval(()=>{if(document.getElementById('rd-auto').checked)load()},15000);})();
</script>"""
    body=body.replace("__CSRF__",_rd_json.dumps(csrf))
    return page(user,'projetos',body)

if 'Portal' in globals() and not globals().get('_rd_wrapped'):
    _rd_prev_get=Portal.do_GET;_rd_prev_post=Portal.do_POST
    def _rd_get(self):
        parsed=_rd_parse.urlparse(self.path);path=parsed.path;user=self.user()
        if path in ('/cloudiff/portal/repair-dashboard','/cloudif/portal/repair-dashboard','/repair-dashboard'):
            return self.send_html(_rd_page(user))
        if path in ('/cloudiff/portal/api/repair-dashboard','/cloudif/portal/api/repair-dashboard','/api/repair-dashboard'):
            items=[];can=_rd_can_repair(user)
            for p in _rd_projects(user):
                base={'project':p['slug'],'name':p['name'],'tenant':p['tenant'],'stack_id':p['stack_id'],'service':p['service'],'can_repair':can}
                if not p['stack_id']:
                    base.update({'healthy':False,'issues':['missing_stack_id'],'state':'unlinked'});items.append(base);continue
                try:
                    audit=_rd_agent('/komodo/project/audit',{'project':p['slug'],'stack_id':p['stack_id'],'service':p['service'],'terminal':'cloudif-'+p['slug'],'shell':'sh'})
                    base.update(audit)
                    resolved=str(audit.get('resolved_stack_id') or '')
                    if resolved and resolved!=p['stack_id']:
                        try:
                            with sqlite3.connect(str(DB)) as con:
                                con.execute('UPDATE project_integrations SET komodo_stack_id=?, stack_id=?, updated_at=CURRENT_TIMESTAMP WHERE project=?',(resolved,resolved,p['slug']))
                                con.commit()
                            base['stack_id']=resolved;base['reconciled']=True
                        except Exception as e:base['reconcile_error']=str(e)[:120]
                except Exception as e:base.update({'healthy':False,'issues':['agent_unavailable'],'error':str(e)[:160],'state':'unknown'})
                items.append(base)
            return _cpx_send_json(self,{'ok':True,'items':items,'can_repair':can})
        if path in ('/cloudiff/portal/action/open-project-terminal','/cloudif/portal/action/open-project-terminal','/action/open-project-terminal'):
            q=_rd_parse.parse_qs(parsed.query);slug=(q.get('slug') or [''])[0]
            p=next((x for x in _rd_projects(user) if x['slug']==slug),None)
            if not p or not p['stack_id']:return self.send_error(404)
            try:
                ensured=_rd_agent('/komodo/project/terminal/ensure',{'project':slug,'stack_id':p['stack_id'],'service':p['service'],'terminal':'cloudif-'+slug,'shell':'sh'},timeout=30)
                target=str(ensured.get('url') or '')
                if not target:return self.send_error(422)
            except Exception:return self.send_error(502)
            self.send_response(302);self.send_header('Location',target);self.end_headers();return
        return _rd_prev_get(self)
    def _rd_post(self):
        path=_rd_parse.urlparse(self.path).path
        if path not in ('/cloudiff/portal/action/repair-project','/cloudif/portal/action/repair-project','/action/repair-project'):return _rd_prev_post(self)
        user=self.user()
        if not _rd_can_repair(user):return _cpx_send_json(self,{'ok':False,'error':'forbidden'},403)
        n=int(self.headers.get('Content-Length','0') or 0);form=_rd_parse.parse_qs(self.rfile.read(n).decode());token=(form.get('csrf_token') or [''])[0]
        if not _prod_csrf_equal(token,_prod_csrf_token(user)):return _cpx_send_json(self,{'ok':False,'error':'csrf'},403)
        slug=(form.get('project') or [''])[0];p=next((x for x in _rd_projects(user) if x['slug']==slug),None)
        if not p or not p['stack_id']:return _cpx_send_json(self,{'ok':False,'error':'Projeto sem stack vinculado'},422)
        try:
            repo_name,repo_url=_rd_canonical_repo(slug)
            forgejo=_rd_forja('/forgejo/ensure-repo',{'project_slug':slug,'slug':slug,'name':p.get('name') or slug,'tenant':p.get('tenant') or 'unknown','forgejo_owner':'cloudif'},timeout=60)
            try:
                with sqlite3.connect(str(DB)) as con:
                    con.execute('UPDATE projects SET repo_url=?, updated_at=CURRENT_TIMESTAMP WHERE slug=?',(repo_url,slug))
                    con.execute('UPDATE project_integrations SET repo_url=?, forgejo_repo_url=?, repo_name=?, updated_at=CURRENT_TIMESTAMP WHERE project=?',(repo_url,repo_url,repo_name,slug))
                    con.commit()
            except Exception: pass
            komodo=_rd_agent('/komodo/project/repair',{'project':slug,'stack_id':p['stack_id'],'service':p['service'],'terminal':'cloudif-'+slug,'shell':'sh'},timeout=120)
            result={'ok':bool(komodo.get('ok')),'forgejo':forgejo,'komodo':komodo,'repo_url':repo_url}
            log_action(user.get('username') or 'portal','repair_project',slug,0,_rd_json.dumps(result,ensure_ascii=False)[:1600],'')
            return _cpx_send_json(self,result,200 if result['ok'] else 202)
        except Exception as e:return _cpx_send_json(self,{'ok':False,'error':str(e)[:200]},500)
    Portal.do_GET=_rd_get;Portal.do_POST=_rd_post;_rd_wrapped=True
# CloudIF dynamic repair dashboard END

if __name__ == "__main__":
    init_db()
    refresh_tenant_policies()
    print(f"CloudIF Portal v17 clean listening on {HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Portal).serve_forever()
