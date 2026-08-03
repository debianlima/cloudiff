
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
        ("agentes","Agentes de IA"),
        ("capacidades","Capacidades"),
        ("reconciliacao","Reconciliação"),
        ("aprovacoes","Aprovações"),
        ("operacao-producao","Operação de produção"),
        ("bancos","Banco de dados"),
        ("git","Código e deploy"),
        ("ajuda","Ajuda"),
    ]
    if user["admin"]:
        tabs.insert(4, ("admin","Administração"))
    nav = "".join(f'<a class="{"active" if tab==k else ""}" href="{url("?tab="+k)}">{v}</a>' for k,v in tabs)
    nav += '<a href="/cloudiff/portal/control">Controle e monitoramento</a>'
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

def _project_effective_owner(project):
    def value(key):
        try:
            return project[key]
        except Exception:
            try:
                return project.get(key)
            except Exception:
                return None
    owner=str(value("owner") or value("created_by") or "").strip()
    if owner:
        return owner
    try:
        con=db()
        row=con.execute("SELECT created_by FROM project_publications WHERE project_slug=? AND is_active=1 ORDER BY id DESC LIMIT 1",(value("slug"),)).fetchone()
        con.close()
        if row:
            try:
                return str(row["created_by"] or "").strip()
            except Exception:
                return str(row[0] or "").strip()
    except Exception:
        pass
    return ""


def render_projects(user):
    rows = user_visible_projects(user["username"], user["groups"])
    tenants = visible_tenants(user["username"], user["groups"])

    allow_git_only = setting_bool("CLOUDIF_ALLOW_GIT_ONLY_PROJECT", True)
    tenant_opts = ""
    if allow_git_only:
        tenant_opts += '<option value="">Nenhum tenant vinculado</option>'
    tenant_opts += "".join(f'<option value="{h(t.get("tenant"))}">{h(t.get("tenant"))}</option>' for t in tenants)

    cards = []
    for p in rows:
        forgejo = p["repo_url"] or setting_value("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git")
        komodo = setting_value("CLOUDIF_KOMODO_URL", "https://komodoiff.duckdns.org/")
        edit_id = "edit_" + re.sub(r"[^a-zA-Z0-9_]+", "_", p["slug"])

        cards.append(f"""
<div class="project-card" data-project-owner="{h(_project_effective_owner(p))}">
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
      <h2>Gestão de projetos</h2>
      <p class="small">Apenas projetos que você pode acessar aparecem aqui.</p>
    </div>
    <button class="btn" onclick="togglePanel('new_project')">Novo projeto</button>
  </div>

  <div id="new_project" class="wizard-panel">
    <div class="help">
      Informe os dados do projeto e vincule um tenant quando necessário.
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
    import datetime as _db96_dt
    tenants = visible_tenants(user["username"], user["groups"])
    blocks = []
    con = db()

    def keepalive_active(value):
        if not value:
            return False
        try:
            stamp = str(value).replace('Z', '+00:00')
            parsed = _db96_dt.datetime.fromisoformat(stamp)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=_db96_dt.timezone.utc)
            return parsed > _db96_dt.datetime.now(_db96_dt.timezone.utc)
        except Exception:
            return False

    for t in tenants:
        tenant = t.get("tenant") or ""
        pol = con.execute("SELECT * FROM tenant_policy WHERE tenant=?", (tenant,)).fetchone()
        always_alive = bool(pol and pol["always_alive"])
        keepalive_until = (pol["keepalive_until"] if pol else None) or ""
        timed_active = (not always_alive) and keepalive_active(keepalive_until)
        automatic_active = not always_alive and not timed_active
        services = compose_services(tenant)
        running = tenant_is_running(tenant)
        hours = "".join(f'<option value="{i}">{i} hora{"s" if i > 1 else ""}</option>' for i in range(1, max_keepalive_hours()+1))
        studio_link = supabase_studio_url(tenant)
        acl_id = "acl_" + re.sub(r"[^a-zA-Z0-9_]+", "_", tenant)

        chips = []
        for service in services:
            chips.append(f"""
<div class="container-chip">
  <span class="container-name">{h(service['service'])}</span>
  {status_badge(service.get('status'))}
</div>""")

        def mode_card(css_class, title, description, badge, controls):
            return f"""<section class="db96-mode {css_class}">
<div class="db96-mode-head"><span class="db96-check">{'✓' if css_class == 'active' else '○'}</span><div><h3>{title}</h3><p>{description}</p></div><span class="db96-mode-badge">{badge}</span></div>
<div class="db96-mode-controls">{controls}</div>
</section>"""

        timed_controls = f"""<label class="db96-hours"><span>Duração</span><select name="hours">{hours}</select></label>
<button class="btn {'db96-current' if timed_active else 'gray'}" name="op" value="keepalive" {'disabled aria-disabled="true"' if timed_active else ''}>{'Ativo agora' if timed_active else ('Iniciar temporariamente' if not running else 'Usar esta duração')}</button>"""
        timed_desc = f"Ligado até {h(keepalive_until)}." if timed_active else "Mantém o banco ligado pelo período escolhido e depois volta ao modo automático."
        modes = [mode_card('active' if timed_active else 'inactive','Por tempo determinado',timed_desc,'ATIVO AGORA' if timed_active else 'INATIVO',timed_controls)]

        if user["admin"]:
            always_op = 'always_on' if running else 'always_on_start'
            always_controls = f"""<button class="btn {'db96-current' if always_alive else 'gray'}" name="op" value="{always_op}" {'disabled aria-disabled="true"' if always_alive else ''}>{'Ativo agora' if always_alive else 'Ativar sempre ligado'}</button>"""
            modes.append(mode_card('active' if always_alive else 'inactive','Sempre ligado','Mantém o banco disponível continuamente, sem desligamento automático.','ATIVO AGORA' if always_alive else 'INATIVO',always_controls))
            automatic_controls = f"""<button class="btn {'db96-current' if automatic_active else 'gray'}" name="op" value="always_off" {'disabled aria-disabled="true"' if automatic_active else ''}>{'Ativo agora' if automatic_active else 'Ativar desligamento automático'}</button>"""
            modes.append(mode_card('active' if automatic_active else 'inactive','Desligamento automático','O banco pode ser desligado quando não houver uma duração temporária ou política permanente ativa.','ATIVO AGORA' if automatic_active else 'INATIVO',automatic_controls))
        else:
            modes.append(mode_card('active' if automatic_active else 'inactive','Desligamento automático','Política padrão para economizar recursos quando não existe uma duração ativa.','ATIVO AGORA' if automatic_active else 'GERENCIADO','<span class="db96-readonly">Gerenciado pela plataforma</span>'))

        operational = []
        if running:
            operational.append(f'<a class="btn light db96-studio" href="{h(studio_link)}" target="_blank">Abrir Studio</a>')
            operational.append('<button class="btn gray" name="op" value="stop">Parar banco</button>')
            operational.append('<button class="btn blue" name="op" value="restart">Reiniciar banco</button>')
        else:
            operational.append('<button class="btn" name="op" value="start">Iniciar banco</button>')
            operational.append('<span class="btn light db96-disabled" aria-disabled="true">Studio disponível após iniciar</span>')
            if user["admin"] or setting_bool("CLOUDIF_STUDENT_CAN_REPAIR", True):
                operational.append('<button class="btn red" name="op" value="repair">Reparar banco</button>')
            if user["admin"] and setting_bool("CLOUDIF_ALLOW_ADMIN_DELETE_TENANT", False):
                operational.append('<button class="btn red" name="op" value="delete">Apagar banco</button><button class="btn red" name="op" value="delete_recreate">Apagar e recriar</button>')

        blocks.append(f"""
<article class="card db96-card" data-tenant="{h(tenant)}" data-running="{'true' if running else 'false'}" data-active-mode="{'always' if always_alive else ('timed' if timed_active else 'automatic')}">
  <div class="db96-hero">
    <div><span class="db96-eyebrow">Banco de dados</span><h2>{h(tenant)}</h2><p>Escolha uma política de disponibilidade. Somente uma opção fica ativa por vez.</p></div>
    <div class="db96-runtime {'running' if running else 'stopped'}"><span class="db96-runtime-dot"></span><strong>{'Banco em execução' if running else 'Banco parado'}</strong><small>{'Serviços disponíveis' if running else 'Aguardando inicialização'}</small></div>
  </div>
  <form method="post" action="{url('/action/tenant_action')}" class="db96-form">
    <input type="hidden" name="tenant" value="{h(tenant)}">
    <section class="db96-section"><div class="db96-section-title"><div><span>1</span><h3>Política de disponibilidade</h3></div><p>O cartão verde é a opção ativa.</p></div><div class="db96-modes">{''.join(modes)}</div></section>
    <section class="db96-section"><div class="db96-section-title"><div><span>2</span><h3>Ações do banco</h3></div><p>Controles operacionais separados da política.</p></div><div class="db96-actions">{''.join(operational)}</div></section>
  </form>
  <details class="db96-details"><summary>Serviços detectados e permissões</summary><div class="container-grid">{''.join(chips) or '<div class="container-chip"><span class="container-name">sem serviços detectados</span><span class="pill muted">-</span></div>'}</div><div class="action-group"><button class="btn light" type="button" onclick="togglePanel('{acl_id}')">Permissões do banco</button><div id="{acl_id}" class="wizard-panel">{tenant_acl_html(tenant, user)}</div></div></details>
</article>""")

    con.close()
    return f"""
<style id="cloudif-db-state-design">
.db96-card{{overflow:hidden;padding:0!important;border-radius:24px!important}}.db96-hero{{display:grid;grid-template-columns:1fr auto;gap:22px;align-items:center;padding:26px 28px;background:#f7f9f8;border-bottom:1px solid var(--cif-border)}}.db96-eyebrow{{font-size:.76rem;font-weight:900;text-transform:uppercase;letter-spacing:.12em;color:#17803d}}.db96-hero h2{{font-size:clamp(1.65rem,4vw,2.25rem);margin:5px 0}}.db96-hero p{{margin:0;color:var(--cif-muted)}}.db96-runtime{{min-width:190px;padding:15px 17px;border-radius:16px;display:grid;grid-template-columns:14px 1fr;column-gap:9px;align-items:center;border:1px solid}}.db96-runtime.running{{background:#e9fbea;border-color:#9bddaa;color:#14532d}}.db96-runtime.stopped{{background:#f3f4f6;border-color:#d1d5db;color:#4b5563}}.db96-runtime-dot{{width:12px;height:12px;border-radius:50%;grid-row:1/3}}.db96-runtime.running .db96-runtime-dot{{background:#22c55e;box-shadow:0 0 0 5px #bbf7d0}}.db96-runtime.stopped .db96-runtime-dot{{background:#9ca3af;box-shadow:0 0 0 5px #e5e7eb}}.db96-runtime small{{opacity:.72}}.db96-form{{padding:4px 28px 24px}}.db96-section{{padding:22px 0;border-bottom:1px solid var(--cif-border)}}.db96-section-title{{display:flex;justify-content:space-between;gap:14px;align-items:center;margin-bottom:14px}}.db96-section-title>div{{display:flex;align-items:center;gap:10px}}.db96-section-title span{{width:29px;height:29px;border-radius:9px;display:grid;place-items:center;background:#176b35;color:#fff;font-weight:900}}.db96-section-title h3,.db96-section-title p{{margin:0}}.db96-section-title p{{color:var(--cif-muted);font-size:.86rem}}.db96-modes{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}}.db96-mode{{border-radius:17px;padding:17px;border:2px solid;transition:.18s ease;min-width:0}}.db96-mode.active{{background:#eaf7ed;border-color:#2ca44f;box-shadow:0 12px 26px rgba(34,139,70,.13)}}.db96-mode.inactive{{background:#f5f6f7;border-color:#d8dde0;color:#687078}}.db96-mode-head{{display:grid;grid-template-columns:28px 1fr auto;gap:9px;align-items:start}}.db96-check{{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;font-weight:900}}.db96-mode.active .db96-check{{background:#1f9d45;color:#fff}}.db96-mode.inactive .db96-check{{background:#e1e5e8;color:#889096}}.db96-mode h3{{margin:1px 0 5px;font-size:1rem}}.db96-mode p{{margin:0;font-size:.84rem;line-height:1.45}}.db96-mode-badge{{padding:5px 8px;border-radius:999px;font-size:.68rem;font-weight:900;white-space:nowrap}}.db96-mode.active .db96-mode-badge{{background:#167c37;color:#fff}}.db96-mode.inactive .db96-mode-badge{{background:#e2e5e7;color:#6b7378}}.db96-mode-controls{{display:grid;gap:9px;margin-top:15px}}.db96-hours span{{display:block;font-size:.76rem;font-weight:800;margin-bottom:5px}}.db96-hours select{{width:100%;margin:0}}.db96-current,.db96-current:disabled{{background:#19863c!important;color:#fff!important;border-color:#19863c!important;opacity:1!important;cursor:default!important;box-shadow:none!important}}.db96-readonly{{display:block;padding:11px;border-radius:10px;background:#e2e5e7;color:#626b70;text-align:center;font-weight:800}}.db96-actions{{display:flex;gap:10px;flex-wrap:wrap}}.db96-actions .btn{{min-width:170px;background:#2563eb!important;color:#fff!important;border-color:#2563eb!important}}.db96-actions .btn.gray{{background:#eef1f3!important;color:#38434a!important;border-color:#cfd5d9!important}}.db96-actions .btn.red{{background:#b42318!important;color:#fff!important;border-color:#b42318!important}}.db96-studio{{background:#2563eb!important;color:#fff!important;border-color:#2563eb!important}}.db96-disabled{{opacity:.55;pointer-events:none}}.db96-details{{margin:0 28px 26px;padding:15px 17px;border:1px solid var(--cif-border);border-radius:14px;background:var(--cif-surface)}}.db96-details summary{{cursor:pointer;font-weight:850;color:#31543b}}.db96-details[open] summary{{margin-bottom:14px}}@media(max-width:720px){{.db96-hero{{grid-template-columns:1fr;padding:21px 20px}}.db96-runtime{{min-width:0}}.db96-form{{padding:3px 20px 20px}}.db96-section-title{{align-items:flex-start;flex-direction:column}}.db96-modes{{grid-template-columns:1fr}}.db96-mode-head{{grid-template-columns:28px 1fr}}.db96-mode-badge{{grid-column:2;justify-self:start}}.db96-actions{{display:grid;grid-template-columns:1fr}}.db96-actions .btn{{width:100%;min-width:0}}.db96-details{{margin:0 20px 20px}}}}
</style>
<div class="help db97-legend"><b>Como interpretar:</b> verde significa a política ativa; cinza significa opção inativa; azul é ação principal; vermelho é ação destrutiva.</div>
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
        tenant_opts += '<option value="">Nenhum tenant vinculado</option>'
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
<div class="project-card" data-project-owner="{h(_project_effective_owner(p))}">
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
      <h2>Gestão de projetos</h2>
      <p class="small">Apenas projetos que você pode acessar aparecem aqui.</p>
    </div>
    <button class="btn" onclick="togglePanel('new_project')">Novo projeto</button>
  </div>

  <div id="new_project" class="wizard-panel">
    <div class="help">
      Informe os dados do projeto e vincule um tenant quando necessário.
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
        tenant_opts += '<option value="">Nenhum tenant vinculado</option>'
    tenant_opts += "".join(f'<option value="{h(t.get("tenant"))}">{h(t.get("tenant"))}</option>' for t in tenants)

    cards = []
    for p in rows:
        forgejo = direct_oidc_url("forgejo", p["repo_url"] or setting_value("CLOUDIF_FORGEJO_URL", "https://cloudiff.duckdns.org/git"))
        komodo = direct_oidc_url("komodo", setting_value("CLOUDIF_KOMODO_URL", "https://komodoiff.duckdns.org/"))
        studio = supabase_studio_url(p["tenant"]) if p["tenant"] else ""
        edit_id = "edit_" + re.sub(r"[^a-zA-Z0-9_]+", "_", p["slug"])

        studio_btn = f'<a class="btn light" href="{h(studio)}" target="_blank">Abrir Studio</a>' if p["tenant"] else ""

        cards.append(f"""
<div class="project-card" data-project-owner="{h(_project_effective_owner(p))}">
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
      <h2>Gestão de projetos</h2>
      <p class="small">Apenas projetos que você pode acessar aparecem aqui.</p>
    </div>
    <button class="btn" onclick="togglePanel('new_project')">Novo projeto</button>
  </div>

  <div id="new_project" class="wizard-panel">
    <div class="help">Informe os dados do projeto e vincule um tenant quando necessário.</div>
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
        tenant_opts += '<option value="">Nenhum tenant vinculado</option>'
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

        cards.append((_project_effective_owner(p),p['name'],p['slug'],p['description'],f"""
<div class="project-card" data-project-owner="{h(_project_effective_owner(p))}">
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
</div>"""))

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

    owner_groups={}
    for owner,name,slug,description,markup in cards:
        key=owner or 'Sem usuário vinculado'
        owner_groups.setdefault(key,[]).append((name,slug,description,markup))
    ordered_owners=sorted(owner_groups,key=lambda x:(0 if x==user['username'] else 1,x.lower()))
    grouped_projects=[]
    for owner in ordered_owners:
        label='Meus projetos' if owner==user['username'] else f'Projetos de {owner}'
        items=owner_groups[owner]
        entries=[]
        for name,slug,description,markup in items:
            subtitle=slug+(f' · {description}' if description else '')
            entries.append(
                f'<details class="project-entry" data-project-slug="{h(slug)}">'
                f'<summary class="project-entry-summary"><span><strong>{h(name)}</strong><small>{h(subtitle)}</small></span><em>Abrir projeto</em></summary>'
                f'{markup}</details>'
            )
        grouped_projects.append(
            f'<details class="project-owner-group"'+(' open' if owner==user['username'] else '')+'>'
            f'<summary><span>{h(label)}</span><small>{len(items)} projeto'+('' if len(items)==1 else 's')+'</small></summary>'
            f'<div class="project-owner-group-body">{"".join(entries)}</div></details>'
        )
    grouped_projects_html='<div class="project-owner-groups">'+''.join(grouped_projects)+'</div>' if grouped_projects else '<div class="box">Nenhum projeto visível ainda.</div>'

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

<div id="cloudif-project-list" class="card" data-current-user="{h(user['username'])}">
  <div class="section-title">
    <div>
      <h2>Projetos por usuário</h2>
      <p class="small">Abra um grupo para visualizar os projetos vinculados a cada usuário.</p>
    </div>
    <button class="btn" onclick="cloudifShowWizard('wiz_new_project')">Novo projeto</button>
  </div>

  {grouped_projects_html}
</div>

<div id="wiz_new_project" class="wizard-panel cloudif-wizard">
  <div class="card">
    <h2>Novo projeto</h2>
    <div class="help">Informe os dados do projeto e, quando necessário, vincule um tenant existente.</div>
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
    import datetime as _db96_dt
    tenants = visible_tenants(user["username"], user["groups"])
    blocks = []
    con = db()

    def keepalive_active(value):
        if not value:
            return False
        try:
            stamp = str(value).replace('Z', '+00:00')
            parsed = _db96_dt.datetime.fromisoformat(stamp)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=_db96_dt.timezone.utc)
            return parsed > _db96_dt.datetime.now(_db96_dt.timezone.utc)
        except Exception:
            return False

    for t in tenants:
        tenant = t.get("tenant") or ""
        pol = con.execute("SELECT * FROM tenant_policy WHERE tenant=?", (tenant,)).fetchone()
        always_alive = bool(pol and pol["always_alive"])
        keepalive_until = (pol["keepalive_until"] if pol else None) or ""
        timed_active = (not always_alive) and keepalive_active(keepalive_until)
        automatic_active = not always_alive and not timed_active
        services = compose_services(tenant)
        running = tenant_is_running(tenant)
        hours = "".join(f'<option value="{i}">{i} hora{"s" if i > 1 else ""}</option>' for i in range(1, max_keepalive_hours()+1))
        studio_link = supabase_studio_url(tenant)
        acl_id = "acl_" + re.sub(r"[^a-zA-Z0-9_]+", "_", tenant)

        chips = []
        for service in services:
            chips.append(f"""
<div class="container-chip">
  <span class="container-name">{h(service['service'])}</span>
  {status_badge(service.get('status'))}
</div>""")

        def mode_card(css_class, title, description, badge, controls):
            return f"""<section class="db96-mode {css_class}">
<div class="db96-mode-head"><span class="db96-check">{'✓' if css_class == 'active' else '○'}</span><div><h3>{title}</h3><p>{description}</p></div><span class="db96-mode-badge">{badge}</span></div>
<div class="db96-mode-controls">{controls}</div>
</section>"""

        timed_controls = f"""<label class="db96-hours"><span>Duração</span><select name="hours">{hours}</select></label>
<button class="btn {'db96-current' if timed_active else 'gray'}" name="op" value="keepalive" {'disabled aria-disabled="true"' if timed_active else ''}>{'Ativo agora' if timed_active else ('Iniciar temporariamente' if not running else 'Usar esta duração')}</button>"""
        timed_desc = f"Ligado até {h(keepalive_until)}." if timed_active else "Mantém o banco ligado pelo período escolhido e depois volta ao modo automático."
        modes = [mode_card('active' if timed_active else 'inactive','Por tempo determinado',timed_desc,'ATIVO AGORA' if timed_active else 'INATIVO',timed_controls)]

        if user["admin"]:
            always_op = 'always_on' if running else 'always_on_start'
            always_controls = f"""<button class="btn {'db96-current' if always_alive else 'gray'}" name="op" value="{always_op}" {'disabled aria-disabled="true"' if always_alive else ''}>{'Ativo agora' if always_alive else 'Ativar sempre ligado'}</button>"""
            modes.append(mode_card('active' if always_alive else 'inactive','Sempre ligado','Mantém o banco disponível continuamente, sem desligamento automático.','ATIVO AGORA' if always_alive else 'INATIVO',always_controls))
            automatic_controls = f"""<button class="btn {'db96-current' if automatic_active else 'gray'}" name="op" value="always_off" {'disabled aria-disabled="true"' if automatic_active else ''}>{'Ativo agora' if automatic_active else 'Ativar desligamento automático'}</button>"""
            modes.append(mode_card('active' if automatic_active else 'inactive','Desligamento automático','O banco pode ser desligado quando não houver uma duração temporária ou política permanente ativa.','ATIVO AGORA' if automatic_active else 'INATIVO',automatic_controls))
        else:
            modes.append(mode_card('active' if automatic_active else 'inactive','Desligamento automático','Política padrão para economizar recursos quando não existe uma duração ativa.','ATIVO AGORA' if automatic_active else 'GERENCIADO','<span class="db96-readonly">Gerenciado pela plataforma</span>'))

        operational = []
        if running:
            operational.append(f'<a class="btn light db96-studio" href="{h(studio_link)}" target="_blank">Abrir Studio</a>')
            operational.append('<button class="btn gray" name="op" value="stop">Parar banco</button>')
            operational.append('<button class="btn blue" name="op" value="restart">Reiniciar banco</button>')
        else:
            operational.append('<button class="btn" name="op" value="start">Iniciar banco</button>')
            operational.append('<span class="btn light db96-disabled" aria-disabled="true">Studio disponível após iniciar</span>')
            if user["admin"] or setting_bool("CLOUDIF_STUDENT_CAN_REPAIR", True):
                operational.append('<button class="btn red" name="op" value="repair">Reparar banco</button>')
            if user["admin"] and setting_bool("CLOUDIF_ALLOW_ADMIN_DELETE_TENANT", False):
                operational.append('<button class="btn red" name="op" value="delete">Apagar banco</button><button class="btn red" name="op" value="delete_recreate">Apagar e recriar</button>')

        blocks.append(f"""
<article class="card db96-card" data-tenant="{h(tenant)}" data-running="{'true' if running else 'false'}" data-active-mode="{'always' if always_alive else ('timed' if timed_active else 'automatic')}">
  <div class="db96-hero">
    <div><span class="db96-eyebrow">Banco de dados</span><h2>{h(tenant)}</h2><p>Escolha uma política de disponibilidade. Somente uma opção fica ativa por vez.</p></div>
    <div class="db96-runtime {'running' if running else 'stopped'}"><span class="db96-runtime-dot"></span><strong>{'Banco em execução' if running else 'Banco parado'}</strong><small>{'Serviços disponíveis' if running else 'Aguardando inicialização'}</small></div>
  </div>
  <form method="post" action="{url('/action/tenant_action')}" class="db96-form">
    <input type="hidden" name="tenant" value="{h(tenant)}">
    <section class="db96-section"><div class="db96-section-title"><div><span>1</span><h3>Política de disponibilidade</h3></div><p>O cartão verde é a opção ativa.</p></div><div class="db96-modes">{''.join(modes)}</div></section>
    <section class="db96-section"><div class="db96-section-title"><div><span>2</span><h3>Ações do banco</h3></div><p>Controles operacionais separados da política.</p></div><div class="db96-actions">{''.join(operational)}</div></section>
  </form>
  <details class="db96-details"><summary>Serviços detectados e permissões</summary><div class="container-grid">{''.join(chips) or '<div class="container-chip"><span class="container-name">sem serviços detectados</span><span class="pill muted">-</span></div>'}</div><div class="action-group"><button class="btn light" type="button" onclick="togglePanel('{acl_id}')">Permissões do banco</button><div id="{acl_id}" class="wizard-panel">{tenant_acl_html(tenant, user)}</div></div></details>
</article>""")

    con.close()
    return f"""
<style id="cloudif-db-state-design">
.db96-card{{overflow:hidden;padding:0!important;border-radius:24px!important}}.db96-hero{{display:grid;grid-template-columns:1fr auto;gap:22px;align-items:center;padding:26px 28px;background:linear-gradient(135deg,#f7fbf8,#edf7f0);border-bottom:1px solid var(--cif-border)}}.db96-eyebrow{{font-size:.76rem;font-weight:900;text-transform:uppercase;letter-spacing:.12em;color:#17803d}}.db96-hero h2{{font-size:clamp(1.65rem,4vw,2.25rem);margin:5px 0}}.db96-hero p{{margin:0;color:var(--cif-muted)}}.db96-runtime{{min-width:190px;padding:15px 17px;border-radius:16px;display:grid;grid-template-columns:14px 1fr;column-gap:9px;align-items:center;border:1px solid}}.db96-runtime.running{{background:#e9fbea;border-color:#9bddaa;color:#14532d}}.db96-runtime.stopped{{background:#f3f4f6;border-color:#d1d5db;color:#4b5563}}.db96-runtime-dot{{width:12px;height:12px;border-radius:50%;grid-row:1/3}}.db96-runtime.running .db96-runtime-dot{{background:#22c55e;box-shadow:0 0 0 5px #bbf7d0}}.db96-runtime.stopped .db96-runtime-dot{{background:#9ca3af;box-shadow:0 0 0 5px #e5e7eb}}.db96-runtime small{{opacity:.72}}.db96-form{{padding:4px 28px 24px}}.db96-section{{padding:22px 0;border-bottom:1px solid var(--cif-border)}}.db96-section-title{{display:flex;justify-content:space-between;gap:14px;align-items:center;margin-bottom:14px}}.db96-section-title>div{{display:flex;align-items:center;gap:10px}}.db96-section-title span{{width:29px;height:29px;border-radius:9px;display:grid;place-items:center;background:#176b35;color:#fff;font-weight:900}}.db96-section-title h3,.db96-section-title p{{margin:0}}.db96-section-title p{{color:var(--cif-muted);font-size:.86rem}}.db96-modes{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}}.db96-mode{{border-radius:17px;padding:17px;border:2px solid;transition:.18s ease;min-width:0}}.db96-mode.active{{background:linear-gradient(145deg,#e9faed,#d9f5e1);border-color:#2ca44f;box-shadow:0 12px 26px rgba(34,139,70,.13)}}.db96-mode.inactive{{background:#f5f6f7;border-color:#d8dde0;color:#687078}}.db96-mode-head{{display:grid;grid-template-columns:28px 1fr auto;gap:9px;align-items:start}}.db96-check{{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;font-weight:900}}.db96-mode.active .db96-check{{background:#1f9d45;color:#fff}}.db96-mode.inactive .db96-check{{background:#e1e5e8;color:#889096}}.db96-mode h3{{margin:1px 0 5px;font-size:1rem}}.db96-mode p{{margin:0;font-size:.84rem;line-height:1.45}}.db96-mode-badge{{padding:5px 8px;border-radius:999px;font-size:.68rem;font-weight:900;white-space:nowrap}}.db96-mode.active .db96-mode-badge{{background:#167c37;color:#fff}}.db96-mode.inactive .db96-mode-badge{{background:#e2e5e7;color:#6b7378}}.db96-mode-controls{{display:grid;gap:9px;margin-top:15px}}.db96-hours span{{display:block;font-size:.76rem;font-weight:800;margin-bottom:5px}}.db96-hours select{{width:100%;margin:0}}.db96-current,.db96-current:disabled{{background:#19863c!important;color:#fff!important;border-color:#19863c!important;opacity:1!important;cursor:default!important;box-shadow:none!important}}.db96-readonly{{display:block;padding:11px;border-radius:10px;background:#e2e5e7;color:#626b70;text-align:center;font-weight:800}}.db96-actions{{display:flex;gap:10px;flex-wrap:wrap}}.db96-actions .btn{{min-width:170px}}.db96-studio{{background:#e3f5e7!important;color:#155b2e!important}}.db96-disabled{{opacity:.55;pointer-events:none}}.db96-details{{margin:0 28px 26px;padding:15px 17px;border:1px solid var(--cif-border);border-radius:14px;background:var(--cif-surface)}}.db96-details summary{{cursor:pointer;font-weight:850;color:#31543b}}.db96-details[open] summary{{margin-bottom:14px}}@media(max-width:720px){{.db96-hero{{grid-template-columns:1fr;padding:21px 20px}}.db96-runtime{{min-width:0}}.db96-form{{padding:3px 20px 20px}}.db96-section-title{{align-items:flex-start;flex-direction:column}}.db96-modes{{grid-template-columns:1fr}}.db96-mode-head{{grid-template-columns:28px 1fr}}.db96-mode-badge{{grid-column:2;justify-self:start}}.db96-actions{{display:grid;grid-template-columns:1fr}}.db96-actions .btn{{width:100%;min-width:0}}.db96-details{{margin:0 20px 20px}}}}
</style>
<div class="help db97-legend"><b>Como interpretar:</b> verde significa a política ativa; cinza significa opção inativa; azul é ação principal; vermelho é ação destrutiva.</div>
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

        if parsed.path.rstrip("/") in ["/cloudiff/portal/action/project_acl", "/cloudif/portal/action/project_acl", "/action/project_acl"]:
            import cloudif_project_acl_module as project_acl

            if '_cloudif_security_valid_origin' in globals() and not _cloudif_security_valid_origin(self):
                return _cloudif_security_reject(self,'Origem da requisição não autorizada.',403)
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length < 0 or length > 200000:
                return _cloudif_security_reject(self,'Corpo da requisição inválido.',413)
            raw = self.rfile.read(length).decode("utf-8", "ignore")
            form = _cloudif_acl_urlparse.parse_qs(raw)
            user = _cloudif_acl_user_from_headers(self)
            portal_user=self.user()
            token=(form.get('csrf_token') or [''])[0]
            if '_prod_csrf_token' in globals() and not _prod_csrf_equal(token,_prod_csrf_token(portal_user)):
                return _cloudif_security_reject(self,'Token CSRF inválido ou ausente.',403)

            def val(k, default=""):
                v = form.get(k, [default])
                return v[0] if isinstance(v, list) and v else default

            slug = val("slug")

            try:
                msg = project_acl.handle_project_acl_action(form, user)
            except Exception as e:
                msg = "Erro: " + str(e)

            url = "/cloudiff/portal/?tab=projetos"
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
        if clean_path in ["/cloudiff/portal/api/ad-search", "/cloudif/portal/api/ad-search", "/api/ad-search"]:
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

        if clean_path in ["/cloudiff/portal/action/project_action", "/cloudif/portal/action/project_action", "/action/project_action", "/project_action"]:
            import cloudif_project_action_safe as safe_project

            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length).decode("utf-8", "ignore")
            form = _cloudif_v97_urlparse.parse_qs(raw)

            try:
                result = safe_project.handle_project_action(form, self.headers)
                slug = result.get("slug", "")
                msg = result.get("message", "Projeto salvo.")
                url = "/cloudiff/portal/?tab=projetos"
                if slug:
                    url += "&project=" + _cloudif_v97_urlparse.quote(slug)
                url += "&msg=" + _cloudif_v97_urlparse.quote(msg)
                return _cloudif_v97_redirect(self, url)
            except Exception as e:
                url = "/cloudiff/portal/?tab=projetos&msg=" + _cloudif_v97_urlparse.quote("Erro ao salvar projeto: " + str(e))
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
        if parsed.path.rstrip("/") in ["/cloudiff/portal/action/publication","/cloudif/portal/action/publication","/action/publication"]:
            import cloudif_portal_publications as publications
            length=int(self.headers.get("Content-Length","0") or "0")
            raw=self.rfile.read(length).decode("utf-8","ignore")
            form=_cloudif_pub_urlparse.parse_qs(raw)
            val=lambda k,d="": (form.get(k) or [d])[0]
            user=self.user()
            slug=val("slug").strip(); op=val("op").strip()
            try:
                if op=="publish_version":
                    result=publications.enqueue_publish(slug,user)
                    msg=f"Publicação enfileirada. Job {result['job_id']}."
                elif op=="set_alias":
                    result=publications.set_alias(slug,val("alias"),user)
                    msg=f"Endereço {result['hostname']} salvo."
                elif op=="acknowledge_job":
                    result=publications.acknowledge_job(slug,int(val("job_id","0")),user)
                    msg="Confirmação fechada."
                elif op=="activate_version":
                    result=publications.activate(slug,int(val("deploy_number","0")),user)
                    msg=f"Publicação d{result['deploy_number']} ativada manualmente."
                elif op=="rollback_production":
                    result=publications.rollback_production(slug,user)
                    msg=f"Rollback de produção concluído para a release {result.get('to_release_id')}."
                else:
                    raise ValueError("Operação de publicação inválida.")
                try: log_action(user.get("username") or "portal", "publication_"+op, slug, 0, json.dumps(result,ensure_ascii=False), "")
                except Exception: pass
            except Exception as e:
                msg="Erro na publicação: "+str(e)
                try: log_action(user.get("username") or "portal", "publication_"+op, slug, 1, "", str(e))
                except Exception: pass
            return _cloudif_pub_redirect(self,"/cloudiff/portal/?tab=publicacao&project="+_cloudif_pub_urlparse.quote(slug)+"&msg="+_cloudif_pub_urlparse.quote(msg))
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
    host=(handler.headers.get("Host") or "").split(":",1)[0].strip().lower().rstrip(".")
    forwarded=(handler.headers.get("X-Forwarded-Host") or "").split(",")[0].split(":",1)[0].strip().lower().rstrip(".")
    public=(PUBLIC_HOST or "cloudiff.duckdns.org").split(":",1)[0].strip().lower().rstrip(".")
    candidate=origin or referer
    fetch_site=(handler.headers.get("Sec-Fetch-Site") or "").strip().lower()
    fetch_mode=(handler.headers.get("Sec-Fetch-Mode") or "").strip().lower()
    cloudif_request_host=(host==public or host.endswith("."+public) or forwarded==public or forwarded.endswith("."+public))
    if not candidate:
        # Clientes internos legados continuam protegidos pela rede, CSRF e ACL.
        return True
    # Chrome móvel pode enviar Origin:null em submissões de formulário/top-level navigation.
    # Só aceitamos esse caso quando o próprio navegador confirma contexto same-origin/same-site,
    # o host pertence ao domínio CloudIF e as demais camadas (CSRF/ACL) permanecem obrigatórias.
    if candidate.lower()=="null":
        return cloudif_request_host and fetch_site in ("same-origin","same-site") and fetch_mode in ("navigate","same-origin","cors","no-cors")
    try:
        parsed=_cloudif_sec_urlparse.urlparse(candidate)
        candidate_host=(parsed.hostname or "").strip().lower().rstrip(".")
        if not candidate_host or parsed.username or parsed.password:
            return False
        # Navegadores públicos só podem originar de HTTPS no domínio CloudIF ou subdomínio real dele.
        cloudif_same_site=(candidate_host==public or candidate_host.endswith("."+public))
        if parsed.scheme.lower()=="https" and cloudif_same_site and (parsed.port in (None,443)):
            return True
        # HTTP é aceito apenas para chamadas internas exatas do próprio host/proxy.
        exact_internal={x for x in (host,forwarded,"127.0.0.1","localhost") if x}
        return parsed.scheme.lower()=="http" and candidate_host in exact_internal
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
        hero=f"""<section class="portal-hero" aria-labelledby="boas-vindas"><div class="portal-hero-main"><p>Ambiente acadêmico integrado</p><h2 id="boas-vindas">Olá, {html.escape(user.get('username') or 'usuário')}.</h2><p>Use este painel para {role}, acompanhar bancos, versões publicadas e a saúde dos serviços.</p></div><aside class="portal-quick" aria-label="Atalhos rápidos"><h3>Atalhos rápidos</h3><div class="quick-grid"><a class="quick-link" href="{url('?tab=projetos')}">Projetos</a><a class="quick-link" href="{url('?tab=aprovacoes')}">Aprovações</a><a class="quick-link" href="{url('?tab=bancos')}">Bancos</a><a class="quick-link" href="{url('?tab=git')}">Git + Komodo</a><a class="quick-link" href="/cloudiff/portal/control">Monitor</a></div></aside></section>"""
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
.theme-picker{display:flex;gap:4px;padding:4px;border:1px solid var(--cif-border);border-radius:12px;background:var(--cif-surface);margin-left:auto}.theme-picker button{padding:8px 10px;border:0;background:transparent;color:inherit;border-radius:8px;box-shadow:none!important;transform:none!important}.theme-picker button[aria-pressed="true"]{background:#176b35;color:white}.project-card{overflow:hidden}.project-options-hint{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:12px 14px;margin-bottom:10px;border:1px solid var(--cif-border);border-radius:12px;background:#f7f9f8}.project-options-hint span{color:var(--cif-muted);font-size:.86rem}.db97-legend{border-left:4px solid #2563eb;background:#f8fafc;color:#334155}.project-tabs{display:flex;gap:6px;overflow:auto;padding:10px 0;border-bottom:1px solid var(--cif-border)}.project-tabs button{flex:0 0 auto;border:1px solid var(--cif-border);background:var(--cif-surface);color:inherit;padding:10px 13px}.project-tabs button[aria-selected="true"]{background:#176b35;color:#fff;border-color:#176b35}.project-tab-panel{display:none;padding:16px 0}.project-tab-panel.active{display:block}.project-overview-grid{display:grid;grid-template-columns:minmax(240px,.9fr) minmax(300px,1.1fr);gap:18px}.project-preview{position:relative;aspect-ratio:16/10;border:1px solid var(--cif-border);border-radius:14px;overflow:hidden;background:linear-gradient(135deg,#dff4e5,#eff8f1)}.project-preview iframe{width:100%;height:100%;border:0;background:white}.project-preview-overlay{position:absolute;inset:auto 10px 10px;display:flex;justify-content:space-between;gap:8px;pointer-events:none}.project-preview-overlay span{background:#0b1a10dd;color:white;padding:7px 9px;border-radius:8px;font-size:.78rem}.container-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.container-card{border:1px solid var(--cif-border);border-radius:14px;padding:15px;background:var(--cif-surface)}.project-service-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.project-service-grid>div{padding:14px;border:1px solid var(--cif-border);border-radius:12px}.project-site-action{margin-top:12px}.framework-status{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:14px;padding:12px;border:1px solid var(--cif-border);border-radius:12px}.framework-status span{color:var(--cif-muted)}.container-categories{display:grid;gap:18px}.container-category{display:grid;gap:10px}.container-category h4{margin:0}.project-agent-actions{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}.project-agent-panel>.project-card{border:1px solid var(--cif-border);border-radius:14px;padding:14px}.backup-more{margin-top:12px}.backup-more>summary{cursor:pointer;font-weight:800}.service-ident{display:flex;align-items:center;gap:11px;min-width:0}.service-icon{width:42px;height:42px;border-radius:12px;display:inline-flex;align-items:center;justify-content:center;font-weight:900;font-size:.78rem;color:#fff;background:#475569;box-shadow:inset 0 0 0 1px #ffffff33}.service-icon.web{background:linear-gradient(135deg,#2563eb,#0ea5e9)}.service-icon.database,.service-icon.metadata,.service-icon.pool{background:linear-gradient(135deg,#166534,#22c55e)}.service-icon.studio{background:linear-gradient(135deg,#16a34a,#34d399)}.service-icon.gateway,.service-icon.api{background:linear-gradient(135deg,#7c3aed,#a855f7)}.service-icon.auth{background:linear-gradient(135deg,#be123c,#fb7185)}.service-icon.storage,.service-icon.image{background:linear-gradient(135deg,#c2410c,#fb923c)}.service-icon.realtime,.service-icon.functions{background:linear-gradient(135deg,#0f766e,#2dd4bf)}.service-badge{display:inline-flex;margin-top:5px;padding:4px 8px;border-radius:999px;font-size:.72rem;font-weight:800;color:#166534;background:#dcfce7}.service-badge.sensitive{color:#991b1b;background:#fee2e2}.infra-note{padding:12px 14px;margin:12px 0;border-radius:11px;background:#fff7ed;border-left:5px solid #ea580c;color:#9a3412}.shell-unavailable{opacity:.65;cursor:not-allowed!important}.resource-strip{display:flex;gap:9px;flex-wrap:wrap;margin:12px 0}.resource-chip{display:inline-flex;align-items:center;gap:7px;padding:8px 10px;border:1px solid var(--cif-border);border-radius:999px;background:var(--cif-surface);font-weight:800}.container-head{display:flex;justify-content:space-between;gap:10px}.health-dot{width:10px;height:10px;border-radius:50%;display:inline-block;background:#9ca3af}.health-dot.healthy{background:#22c55e}.health-dot.running{background:#38bdf8}.health-dot.stopped,.health-dot.unhealthy{background:#ef4444}.metric-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:12px 0}.metric{padding:10px;background:color-mix(in srgb,var(--cif-surface) 80%,#dcefe2);border-radius:10px}.metric small{display:block;color:var(--cif-muted)}.service-links{display:flex;flex-wrap:wrap;gap:7px}.sheet-backdrop{position:fixed;inset:0;background:#0008;z-index:9998;display:none}.sheet-backdrop.open{display:block}.cloudif-sheet{position:fixed;right:0;top:0;height:100dvh;width:min(620px,94vw);background:var(--cif-surface);color:var(--cif-text);z-index:9999;transform:translateX(105%);transition:transform .22s ease;box-shadow:-20px 0 50px #0005;overflow:auto;padding:22px}.cloudif-sheet.open{transform:none}.sheet-head{display:flex;justify-content:space-between;gap:12px;position:sticky;top:0;background:var(--cif-surface);padding:8px 0 14px;z-index:2}.sheet-close{font-size:1.5rem}.terminal-box{background:#08120c;color:#c7f9d4;border-radius:12px;padding:14px;font-family:ui-monospace,monospace;overflow:auto}.copy-line{display:flex;gap:8px;align-items:center}.copy-line code{flex:1;overflow:auto}.project-card .project-line{display:grid!important}.project-card .project-line>div{margin:0!important}.project-card.cpx-ready .project-line{display:none!important}.tenant-tabs{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}.tenant-tabs button{border:1px solid var(--cif-border);background:var(--cif-surface);color:inherit}.tenant-tabs button.active{background:#176b35;color:#fff}.tenant-panel{display:none}.tenant-panel.active{display:block}
.header-meta{display:flex;flex-direction:column;align-items:flex-end;gap:8px}.ai-project-tag{display:inline-flex;align-items:center;gap:7px;padding:7px 10px;border-radius:999px;background:linear-gradient(135deg,#312e81,#7c3aed);color:#fff;font-size:.76rem;font-weight:900;margin:0}.footer .ai-disclaimer{max-width:900px;margin:0 auto 16px;text-align:left}@media(max-width:760px){.header-meta{width:100%;align-items:stretch}.ai-project-tag{justify-content:center;text-align:center}}.ai-disclaimer{padding:12px 14px;border:1px solid #f59e0b;border-left:5px solid #f59e0b;background:#fffbeb;color:#78350f;border-radius:11px;margin:12px 0}.backup-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:12px 0}.backup-stat{padding:12px;border:1px solid var(--cif-border);border-radius:12px;background:var(--cif-surface)}.backup-list{display:grid;gap:9px;margin-top:12px}.backup-item{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;padding:12px;border:1px solid var(--cif-border);border-radius:12px}.backup-actions{display:flex;gap:8px;flex-wrap:wrap}.backup-status{display:inline-flex;padding:5px 8px;border-radius:999px;font-size:.75rem;font-weight:800}.backup-status.ok{background:#dcfce7;color:#166534}.backup-status.pending{background:#fef3c7;color:#92400e}.backup-status.bad{background:#fee2e2;color:#991b1b}.backup-progress{height:8px;background:#e5e7eb;border-radius:999px;overflow:hidden}.backup-progress>i{display:block;height:100%;background:linear-gradient(90deg,#16a34a,#eab308,#dc2626)}@media(max-width:760px){.project-overview-grid{grid-template-columns:1fr}.theme-picker{width:100%;justify-content:space-between;margin:8px 0}.theme-picker button{flex:1}.container-grid{grid-template-columns:1fr}.metric-grid{grid-template-columns:1fr 1fr}.cloudif-sheet{width:100vw}.project-tabs{scroll-snap-type:x mandatory}.project-tabs button{scroll-snap-align:start}}
@media(prefers-reduced-motion:reduce){.cloudif-sheet{transition:none}}
.project-card.cpx-ready{padding:0!important;border-radius:16px!important;overflow:hidden;background:var(--cif-surface)!important}
.project-card.cpx-ready>.project-options-hint{display:none;margin:0;border:0;border-radius:0;padding:15px 16px;background:var(--cif-surface);cursor:pointer}
.project-card.cpx-ready>.project-options-hint strong{font-size:1rem}
.project-card.cpx-ready>.project-options-hint span{margin-left:auto}
.project-card.cpx-ready>.project-options-hint:after{content:'Abrir projeto';font-size:.76rem;font-weight:800;color:#176b35}
.project-card.cpx-ready.is-open>.project-options-hint:after{content:'Fechar projeto'}
.project-card.cpx-ready>.project-tabs,.project-card.cpx-ready>.project-tab-panel{display:none}
.project-card.cpx-ready.is-open>.project-tabs{display:flex;padding:10px 16px 0;margin:0;border-top:1px solid var(--cif-border)}
.project-card.cpx-ready.is-open>.project-tab-panel.active{display:block;padding:18px 16px}
.project-card.cpx-ready.is-open{box-shadow:0 14px 32px rgba(20,55,34,.10)}
.project-card.cpx-ready .project-service-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.project-service-card{display:grid;gap:8px;padding:15px;border:1px solid var(--cif-border);border-radius:13px;background:var(--cif-surface)}
.project-service-card>span{font-size:.72rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--cif-muted)}
.project-service-card strong{font-size:.95rem}
.project-service-card .service-links{margin-top:auto}
.project-framework-note{display:grid;gap:6px;margin-top:14px;padding:14px;border:1px solid var(--cif-border);border-radius:13px;background:var(--cif-surface)}
.project-framework-note p{margin:0;color:var(--cif-muted);font-size:.84rem}
.project-agent-panel>.project-card{padding:0;border:0}
.project-agent-panel>.project-card>.section-title{margin-top:0}
#project-identities{display:none}
.project-owner-groups{display:grid;gap:14px;margin-top:16px}
.project-owner-group{border:1px solid var(--cif-border);border-radius:15px;background:var(--cif-surface);overflow:hidden}
.project-owner-group>summary{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;cursor:pointer;font-weight:850;list-style:none}
.project-owner-group>summary::-webkit-details-marker{display:none}
.project-owner-group>summary:after{content:'Abrir';font-size:.76rem;color:#176b35}
.project-owner-group[open]>summary:after{content:'Fechar'}
.project-owner-group-body{display:grid;gap:10px;padding:0 12px 12px}
.project-owner-group .project-card{margin:0}
.project-entry{border:1px solid var(--cif-border);border-radius:14px;background:var(--cif-surface);overflow:hidden}
.project-entry>summary{list-style:none}.project-entry>summary::-webkit-details-marker{display:none}
.project-entry-summary{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:15px 16px;cursor:pointer}
.project-entry-summary span{display:grid;gap:3px;min-width:0}.project-entry-summary strong{font-size:1rem}.project-entry-summary small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--cif-muted)}
.project-entry-summary em{font-style:normal;font-size:.76rem;font-weight:800;color:#176b35;white-space:nowrap}
.project-entry[open]>.project-entry-summary{border-bottom:1px solid var(--cif-border);background:#f7faf8}.project-entry[open]>.project-entry-summary em{font-size:0}.project-entry[open]>.project-entry-summary em:after{content:'Fechar projeto';font-size:.76rem}
.project-entry>.project-card{border:0!important;border-radius:0!important;box-shadow:none!important;margin:0!important}
.project-entry:not([open])>.project-card{display:none!important}
.project-entry[open]>.project-card{display:block!important;padding:0!important}
.project-entry[open]>.project-card>.project-line{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:12px;padding:16px}
.project-entry[open]>.project-card>.project-line>div{min-width:0;padding:14px;border:1px solid var(--cif-border);border-radius:12px;background:var(--cif-surface)}
.project-entry[open]>.project-card.cpx-ready>.project-line{display:none!important}
.project-entry[open]>.project-card.cpx-ready>.project-tabs{display:flex!important;padding:10px 16px 0;margin:0;border-top:0}
.project-entry[open]>.project-card.cpx-ready>.project-tab-panel.active{display:block!important;padding:18px 16px}
.project-runtime-inspection{display:grid;gap:12px;margin-top:14px;padding:14px;border:1px solid var(--cif-border);border-radius:13px;background:var(--cif-surface)}
.project-runtime-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.project-runtime-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.project-runtime-grid>div{padding:11px;border:1px solid var(--cif-border);border-radius:10px;background:color-mix(in srgb,var(--cif-surface) 88%,#e5efe8)}
.project-runtime-grid span{display:block;font-size:.72rem;color:var(--cif-muted);margin-bottom:4px}
.project-runtime-evidence{display:flex;gap:6px;flex-wrap:wrap}
.project-runtime-evidence code{padding:5px 7px;border-radius:7px;background:#edf3ef;font-size:.74rem}
.project-runtime-actions{display:flex;gap:8px;flex-wrap:wrap}
.project-runtime-selector{display:flex;align-items:end;gap:10px;flex-wrap:wrap}.project-runtime-selector label{display:grid;gap:6px;min-width:220px}.project-runtime-selector select{min-height:40px}
.project-runtime-note{margin:0;color:var(--cif-muted);font-size:.82rem}
.project-service-grid.publication-information{grid-template-columns:repeat(3,minmax(0,1fr))}
.project-service-grid.publication-information>article{display:grid;gap:5px;padding:14px;border:1px solid var(--cif-border);border-radius:12px;min-width:0;background:var(--cif-surface)}
.technology-wizard-backdrop{position:fixed;inset:0;z-index:1300;display:grid;place-items:center;padding:24px;background:rgba(10,18,13,.58)}
.technology-wizard-backdrop[hidden]{display:none}
.technology-wizard{width:min(720px,100%);max-height:90vh;overflow:auto;padding:22px;border-radius:18px;background:var(--cif-surface);box-shadow:0 24px 70px rgba(0,0,0,.28)}
.technology-wizard>header,.technology-wizard>footer{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.technology-wizard>header span{font-size:.72rem;color:var(--cif-muted);text-transform:uppercase;letter-spacing:.08em}.technology-wizard>header h2{margin:4px 0 0}.technology-wizard>header button{border:0;background:transparent;font-size:1.7rem;cursor:pointer}
.technology-wizard-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;padding:0;margin:22px 0 10px;list-style:none}.technology-wizard-steps li{padding:9px;border-radius:9px;background:#edf3ef;font-size:.76rem}.technology-wizard-steps li.done{font-weight:800;color:#176b35}.technology-wizard progress{width:100%;margin-bottom:20px}.technology-wizard [data-tech-body]{display:grid;gap:14px}.technology-wizard [data-tech-body]>section{padding:14px;border:1px solid var(--cif-border);border-radius:12px}.technology-wizard>footer{margin-top:20px;justify-content:flex-end}
@media(max-width:760px){.project-service-grid.publication-information{grid-template-columns:1fr}.technology-wizard-steps{grid-template-columns:1fr 1fr}}
@media(max-width:760px){.project-card.cpx-ready .project-service-grid{grid-template-columns:1fr}.project-card.cpx-ready>.project-options-hint{align-items:flex-start;flex-direction:column}.project-card.cpx-ready>.project-options-hint span{margin-left:0}.project-card.cpx-ready>.project-options-hint:after{margin-top:4px}}
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
 const techBackdrop=document.createElement('div');techBackdrop.className='technology-wizard-backdrop';techBackdrop.hidden=true;techBackdrop.innerHTML='<section class="technology-wizard" role="dialog" aria-modal="true" aria-labelledby="technology-wizard-title"><header><div><span>Alteração controlada</span><h2 id="technology-wizard-title">Plano de tecnologia</h2></div><button type="button" data-tech-close aria-label="Fechar">×</button></header><ol class="technology-wizard-steps"><li>1. Ambiente</li><li>2. Plano</li><li>3. Validações</li><li>4. Rollback</li></ol><progress max="4" value="1"></progress><div data-tech-body><p>Preparando inspeção…</p></div><footer><button type="button" class="btn gray" data-tech-close>Fechar</button></footer></section>';document.body.appendChild(techBackdrop);techBackdrop.querySelectorAll('[data-tech-close]').forEach(b=>b.onclick=()=>{techBackdrop.hidden=true});function openTechnologyWizard(){techBackdrop.hidden=false;techBackdrop.querySelector('progress').value=1;techBackdrop.querySelector('[data-tech-body]').innerHTML='<p>Inspecionando o ambiente atual…</p>';techBackdrop.querySelectorAll('.technology-wizard-steps li').forEach(x=>x.classList.remove('done'))}function renderTechnologyPlan(p){const files=(p.files||[]).map(x=>'<li><code>'+x+'</code></li>').join('');const checks=(p.validation||[]).map(x=>'<li>'+x+'</li>').join('');techBackdrop.querySelector('progress').value=4;techBackdrop.querySelectorAll('.technology-wizard-steps li').forEach(x=>x.classList.add('done'));techBackdrop.querySelector('[data-tech-body]').innerHTML='<section><span>Tecnologia</span><h3>'+p.operation+' '+p.technology+' '+p.version+'</h3></section><section><h3>Arquivos previstos</h3><ul>'+files+'</ul></section><section><h3>Validações</h3><ul>'+checks+'</ul></section><section><h3>Rollback</h3><p>'+p.rollback+'</p></section><p class="project-runtime-note">Nenhuma alteração foi aplicada. Próxima etapa: proposta no Forgejo.</p>'};
 const backdrop=document.createElement('div');backdrop.className='sheet-backdrop';document.body.appendChild(backdrop);const sheet=document.createElement('aside');sheet.className='cloudif-sheet';sheet.setAttribute('aria-modal','true');sheet.setAttribute('role','dialog');sheet.innerHTML='<div class="sheet-head"><h2 id="sheet-title">Detalhes</h2><button class="sheet-close" aria-label="Fechar">×</button></div><div id="sheet-body"></div>';document.body.appendChild(sheet);function closeSheet(){sheet.classList.remove('open');backdrop.classList.remove('open')}sheet.querySelector('.sheet-close').onclick=closeSheet;backdrop.onclick=closeSheet;window.cloudifOpenSheet=function(title,html){sheet.querySelector('#sheet-title').textContent=title;sheet.querySelector('#sheet-body').innerHTML=html;sheet.classList.add('open');backdrop.classList.add('open');sheet.querySelector('.sheet-close').focus()};
 function tabs(card,panels){const bar=document.createElement('div');bar.className='project-tabs';Object.entries(panels).forEach(([name,node],i)=>{const id='pt-'+Math.random().toString(36).slice(2);node.classList.add('project-tab-panel');node.id=id;if(i===0)node.classList.add('active');const b=document.createElement('button');b.textContent=name;b.setAttribute('aria-controls',id);b.setAttribute('aria-selected',String(i===0));b.onclick=()=>{bar.querySelectorAll('button').forEach(x=>x.setAttribute('aria-selected','false'));card.querySelectorAll('.project-tab-panel').forEach(x=>x.classList.remove('active'));b.setAttribute('aria-selected','true');node.classList.add('active')};bar.appendChild(b)});card.insertBefore(bar,card.firstChild)}
 const identityCards=[...document.querySelectorAll('#project-identities article.project-card')];
 const identityBySlug=new Map(identityCards.map(x=>[((x.querySelector('h3')||{}).textContent||'').trim(),x]));
 const list=document.getElementById('cloudif-project-list');
 const projectCards=list?[...list.querySelectorAll('.project-entry > .project-card')]:[];
 projectCards.forEach((card,idx)=>{const line=card.querySelector('.project-line');if(!line)return;const cols=[...line.children];if(cols.length<4)return;const slugText=(cols[0].querySelector('.small')||{}).textContent||'';const slug=slugText.replace(/^Slug:\s*/i,'').trim();const name=((cols[0].querySelector('h3')||{}).textContent||slug).trim();const description=[...cols[0].querySelectorAll('p')].find(x=>!x.classList.contains('small'));const bankLink=cols[1].querySelector('a');const bankName=((cols[1].querySelector('.pill')||{}).textContent||'Sem banco').trim();const links=[...cols[2].querySelectorAll('a')];const gitLink=links.find(a=>/Git/i.test(a.textContent));const komodoLink=links.find(a=>/Komodo/i.test(a.textContent));
 const services=document.createElement('section');services.className='project-services-panel';services.innerHTML='<div class="section-title"><div><h3>Serviços</h3><p class="small">Acessos vinculados exclusivamente a este projeto.</p></div></div><div class="publication-information project-service-grid"></div><div class="project-site-action"></div><div class="project-runtime-inspection" data-role="runtime-inspection"><div class="project-runtime-head"><div><span>Framework e runtime</span><strong>Inspeção ainda não executada</strong></div><button type="button" class="btn light" data-runtime-refresh>Inspecionar ambiente</button></div><p class="project-runtime-note">A inspeção consulta o repositório sincronizado e os containers vinculados ao projeto.</p></div>';const serviceGrid=services.querySelector('.project-service-grid');function service(title,value,link,label){const el=document.createElement('article');el.className='project-service-card';el.innerHTML='<span>'+title+'</span><strong>'+value+'</strong><div class="service-links"></div>';if(link){const a=link.cloneNode(true);a.textContent=label;el.querySelector('.service-links').appendChild(a)}return el}serviceGrid.append(service('Banco vinculado',bankName,bankLink,'Abrir Studio'),service('Repositório Forge',gitLink?'Forgejo':'Nenhum repositório vinculado',gitLink,'Abrir repositório'),service('Komodo Publicação SSH','Container de publicação',komodoLink,'Acessar SSH'));
 const containers=document.createElement('section');containers.dataset.role='containers';containers.innerHTML='<h3>Containers</h3><div class="empty-state">Carregando containers do projeto...</div>';const pubs=document.createElement('section');pubs.className='project-publication-actions';pubs.innerHTML='<div class="section-title"><div><h3>Publicação e acesso</h3><p class="small">Sincronização, integração, edição e permissões do projeto.</p></div></div>';pubs.append(cols[3]);const backups=document.createElement('section');backups.dataset.role='backups';backups.dataset.projectIndex=idx;backups.innerHTML='<h3>Backups</h3><div class="empty-state">Carregando backups...</div>';const agent=document.createElement('section');agent.className='project-agent-panel';agent.innerHTML='<div class="section-title"><div><h3>Agente IA e MCP</h3><p class="small">Gere a credencial, conecte agentes e consulte as funções autorizadas deste projeto.</p></div></div><div class="project-agent-actions"><a class="btn light" href="/cloudiff/portal/?tab=agentes">Conectar agente</a><a class="btn light" href="/cloudiff/portal/?tab=documentacao-mcp">Ver funções MCP</a></div>';const identity=identityBySlug.get(slug);if(identity)agent.append(identity);else agent.insertAdjacentHTML('beforeend','<div class="empty-state">Identidade MCP ainda não disponível para este projeto.</div>');tabs(card,{'Serviços':services,'Containers':containers,'Publicação':pubs,'Backups':backups,'Agente IA e MCP':agent});line.replaceWith(services,containers,pubs,backups,agent);card.dataset.projectIndex=idx;card.dataset.projectSlug=slug;card.classList.add('cpx-ready');const entry=card.closest('.project-entry');if(entry){entry.addEventListener('toggle',()=>{if(entry.open){document.querySelectorAll('.project-entry[open]').forEach(x=>{if(x!==entry)x.open=false});card.scrollIntoView({block:'nearest',behavior:'smooth'})}})}const runtimePanel=services.querySelector('[data-role="runtime-inspection"]');async function loadRuntime(){if(!runtimePanel||runtimePanel.dataset.loading==='1')return;runtimePanel.dataset.loading='1';const button=runtimePanel.querySelector('[data-runtime-refresh]');if(button){button.disabled=true;button.textContent='Inspecionando…'}try{const response=await fetch('/cloudiff/portal/api/project-runtime-inspection?slug='+encodeURIComponent(slug),{credentials:'same-origin'});const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||'inspection_failed');const d=data.detection||{},repo=data.repository||{},r=d.runtimes||{},e=d.evidence||[];const values=Object.entries(r).map(([k,v])=>'<div><span>'+k.toUpperCase()+'</span><strong>'+v+'</strong></div>').join('');const external=data.external_server||{};runtimePanel.innerHTML='<div class="project-runtime-head"><div><span>Tecnologia web</span><strong>'+(d.framework||'Não identificado')+'</strong></div><button type="button" class="btn light" data-runtime-refresh>Atualizar inspeção</button></div><div class="project-runtime-grid"><div><span>Último commit</span><strong>'+(repo.commit?repo.commit.slice(0,12):'—')+'</strong></div><div><span>Servidor web externo</span><strong>'+(external.label||'Não publicado')+'</strong>'+(external.url?'<a class="btn light" href="'+external.url+'" target="_blank" rel="noopener">Abrir site</a>':'')+'</div><div><span>Servidor web interno</span><strong>'+(d.server||'Não detectado')+'</strong></div><div><span>Containers inspecionados</span><strong>'+((data.containers||[]).length)+'</strong></div>'+values+'</div><div class="project-runtime-evidence">'+e.map(x=>'<code>'+x+'</code>').join('')+'</div><div class="project-runtime-selector"><label><span>Tecnologia homologada</span><select data-runtime-template><option value="">Selecionar</option><option value="node20">Node.js 20</option><option value="node22">Node.js 22</option><option value="node24">Node.js 24</option><option value="php83-apache">PHP 8.3 + Apache</option><option value="static-nginx">Site estático + Nginx</option><option value="remove-runtime">Remover runtime atual</option></select></label><button type="button" class="btn light" data-runtime-plan>Gerar plano</button></div><p class="project-runtime-note">O plano é somente leitura e não altera o container. Instalação, troca ou remoção exigem proposta no Forgejo, build validado e rollback.</p>';runtimePanel.querySelector('[data-runtime-refresh]').onclick=loadRuntime;const planButton=runtimePanel.querySelector('[data-runtime-plan]');if(planButton)planButton.onclick=async()=>{const template=(runtimePanel.querySelector('[data-runtime-template]')||{}).value||'';if(!template)return;openTechnologyWizard();planButton.disabled=true;planButton.textContent='Gerando…';try{const response=await fetch('/cloudiff/portal/api/project-runtime-plan?slug='+encodeURIComponent(slug)+'&template='+encodeURIComponent(template),{credentials:'same-origin'});const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||'plan_failed');const p=data.plan||{};const files=(p.files||[]).map(x=>'<li><code>'+x+'</code></li>').join('');const checks=(p.validation||[]).map(x=>'<li>'+x+'</li>').join('');renderTechnologyPlan(p)}catch(error){techBackdrop.querySelector('[data-tech-body]').innerHTML='<p>Não foi possível gerar o plano homologado.</p>'}finally{planButton.disabled=false;planButton.textContent='Gerar plano'}}}catch(error){runtimePanel.innerHTML='<div class="project-runtime-head"><div><span>Framework e runtime</span><strong>Falha na inspeção</strong></div><button type="button" class="btn light" data-runtime-refresh>Tentar novamente</button></div><p class="project-runtime-note">Não foi possível consultar o ambiente real deste projeto.</p>';runtimePanel.querySelector('[data-runtime-refresh]').onclick=loadRuntime}finally{runtimePanel.dataset.loading='0'}}const runtimeButton=runtimePanel&&runtimePanel.querySelector('[data-runtime-refresh]');if(runtimeButton)runtimeButton.onclick=loadRuntime;if(entry)entry.addEventListener('toggle',()=>{if(entry.open&&runtimePanel&&!runtimePanel.dataset.loaded){runtimePanel.dataset.loaded='1';loadRuntime()}})});const identitySection=document.querySelector('#project-identities');if(identitySection)identitySection.remove();

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
       panel.innerHTML='<h3>Backup do projeto</h3><div class="ai-disclaimer"><strong>Proteja seus dados.</strong> Este projeto foi desenvolvido com apoio de agentes de IA e está em fase de testes e homologação. Mantenha cópias próprias das informações importantes.</div><div class="backup-summary"><div class="backup-stat"><small>Backup automático local</small><strong>'+(cfg.enabled?'Ativado':'Desativado')+'</strong></div><div class="backup-stat"><small>Servidor de arquivos</small><span class="backup-status '+remoteClass+'">'+remoteText+'</span></div><div class="backup-stat"><small>Última execução</small><strong>'+(cfg.last_run||'Ainda não executado')+'</strong></div></div><div class="backup-actions"><button type="button" data-backup-now>Gerar backup agora</button><button type="button" class="light" data-toggle-auto>'+(cfg.enabled?'Desativar automático':'Ativar automático')+'</button>'+(d.can_manage_remote?'<button type="button" class="light" data-toggle-remote>'+(cfg.remote_requested?'Desativar envio remoto':'Ativar envio remoto')+'</button>':'')+'</div><p class="small">O backup de banco contém dumps lógicos. O backup de aplicação contém publicações, configuração e metadados operacionais dos contêineres, sem variáveis de ambiente ou segredos.</p><div class="backup-list">'+(items.length?items.slice(0,5).map(backupItem).join(''):'<div class="empty-state">Nenhum arquivo disponível.</div>')+'</div>'+(items.length>5?'<details class="backup-more"><summary>Ver todos os backups ('+items.length+')</summary><div class="backup-list">'+items.slice(5).map(backupItem).join('')+'</div></details>':'');function backupItem(x){return '<div class="backup-item"><div><strong>'+(x.type==='database'?'Banco de dados':'Aplicação e containers')+'</strong><div class="small">'+x.modified+' · '+formatBytes(x.size)+' · SHA-256 '+x.sha256.slice(0,12)+'…</div></div><a class="btn light" href="/cloudif/portal/download/project-backup?slug='+encodeURIComponent(p.slug)+'&file='+encodeURIComponent(x.filename)+'">Baixar</a></div>'}
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
       containerPanel.innerHTML='<div class="section-title"><div><h3>Containers do projeto</h3><p class="small">Agrupados por função e vínculo com a publicação.</p></div></div><div class="container-categories"></div>';
       const categories=containerPanel.querySelector('.container-categories');
       const categoryOrder=['Banco de dados','Publicação ativa','Publicações inativas','Sistema'];
       const categoryNodes={};categoryOrder.forEach(name=>{const section=document.createElement('section');section.className='container-category';section.innerHTML='<h4>'+name+'</h4><div class="container-grid"></div>';categoryNodes[name]=section});
       if(!items.length)categories.innerHTML='<div class="empty-state">Nenhum container vinculado a este projeto.</div>';
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
         const databaseIcons=['database','studio','gateway','auth','api','realtime','storage','functions','image','metadata','pool'];const hasStable=(c.urls||[]).some(u=>!/-d\d+\./.test(u));const hasVersion=(c.urls||[]).length>0;const category=databaseIcons.includes(c.icon)?'Banco de dados':(hasStable?'Publicação ativa':(hasVersion?'Publicações inativas':'Sistema'));categoryNodes[category].querySelector('.container-grid').appendChild(el);
       });
       categoryOrder.forEach(name=>{if(categoryNodes[name].querySelector('.container-card'))categories.appendChild(categoryNodes[name])});
       const active=items.find(x=>(x.urls||[]).some(u=>!/-d\d+\./.test(u)));
       if(active&&active.urls&&active.urls[0]){const action=card.querySelector('.project-site-action');if(action)action.innerHTML='<a class="btn" target="_blank" rel="noopener" href="'+active.urls[0]+'">Abrir site</a>'}
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
        if path in ('/cloudiff/portal/api/project-runtime-inspection','/api/project-runtime-inspection'):
            user=self.user();q=_cpx_parse.parse_qs(_cpx_parse.urlparse(self.path).query);slug=(q.get('slug') or [''])[0]
            project=next((p for p in _cpx_allowed_projects(user) if p.get('slug')==slug),None)
            if not project:return _cpx_send_json(self,{'ok':False,'error':'project_not_authorized'},403)
            try:
                result=_rd_agent('/komodo/project/runtime-inspect',{'project':slug,'public_numbers':project.get('public_numbers') or []},timeout=45)
                repository=result.setdefault('repository',{})
                try:
                    con=db();project_row=con.execute("SELECT repo_url FROM projects WHERE slug=?",(slug,)).fetchone();row=con.execute("SELECT stable_hostname,version_hostname FROM project_publications WHERE project_slug=? AND is_active=1 ORDER BY id DESC LIMIT 1",(slug,)).fetchone();con.close()
                except Exception:
                    project_row=None;row=None
                repository['url']=str((project_row['repo_url'] if project_row else '') or '')
                repository['provider']='Forgejo'
                host=((row['stable_hostname'] or row['version_hostname']) if row else '')
                result['external_server']={'label':'Proxy HTTPS CloudIFF','url':('https://'+host) if host else ''}
            except Exception as exc:
                return _cpx_send_json(self,{'ok':False,'error':'runtime_inspection_failed','detail':type(exc).__name__},502)
            return _cpx_send_json(self,result,200 if result.get('ok') else 502)
        if path in ('/cloudiff/portal/api/project-runtime-plan','/api/project-runtime-plan'):
            user=self.user();q=_cpx_parse.parse_qs(_cpx_parse.urlparse(self.path).query);slug=(q.get('slug') or [''])[0];template=(q.get('template') or [''])[0]
            project=next((p for p in _cpx_allowed_projects(user) if p.get('slug')==slug),None)
            if not project:return _cpx_send_json(self,{'ok':False,'error':'project_not_authorized'},403)
            catalog={
              'node20':{'technology':'Node.js','version':'20','operation':'instalar ou atualizar','files':['Dockerfile','package.json'],'validation':['node --version','npm --version','build do projeto'],'rollback':'reverter o commit da proposta Forgejo'},
              'node22':{'technology':'Node.js','version':'22','operation':'instalar ou atualizar','files':['Dockerfile','package.json'],'validation':['node --version','npm --version','build do projeto'],'rollback':'reverter o commit da proposta Forgejo'},
              'node24':{'technology':'Node.js','version':'24','operation':'instalar ou atualizar','files':['Dockerfile','package.json'],'validation':['node --version','npm --version','build do projeto','SBOM e scanner homologado'],'rollback':'reverter o commit da proposta Forgejo'},
              'php83-apache':{'technology':'PHP + Apache','version':'8.3','operation':'instalar ou substituir','files':['Dockerfile','apache-vhost.conf','composer.json'],'validation':['php --version','apache2 -v','healthcheck HTTP'],'rollback':'reverter o commit da proposta Forgejo'},
              'static-nginx':{'technology':'Site estático + Nginx','version':'estável homologada','operation':'instalar ou substituir','files':['Dockerfile','nginx.conf'],'validation':['nginx -v','nginx -t','healthcheck HTTP'],'rollback':'reverter o commit da proposta Forgejo'},
              'remove-runtime':{'technology':'Runtime de aplicação','version':'—','operation':'remover','files':['Dockerfile','compose.yaml','manifesto do projeto'],'validation':['build limpo','healthcheck HTTP','ausência do binário removido'],'rollback':'reverter o commit da proposta Forgejo'},
            }
            selected=catalog.get(template)
            if not selected:return _cpx_send_json(self,{'ok':False,'error':'template_not_allowed'},400)
            return _cpx_send_json(self,{'ok':True,'side_effect_free':True,'project_slug':slug,'template':template,'plan':selected,'next_step':'criar proposta Forgejo para revisão e aprovação','applied':False,'secrets_exposed':False})
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


# CloudIF control dashboard proxy BEGIN
import urllib.request as _ctl_req
import urllib.error as _ctl_err
import urllib.parse as _ctl_parse
if 'Portal' in globals() and not globals().get('_ctl_dashboard_wrapped'):
    _ctl_prev_get=Portal.do_GET
    def _ctl_dashboard_get(self):
        parsed=_ctl_parse.urlparse(self.path); path=parsed.path
        routes={
          '/cloudiff/portal/control':'/',
          '/cloudiff/portal/control/':'/',
          '/cloudiff/portal/control/api/dashboard':'/api/dashboard',
          '/cloudiff/portal/control/manifest.webmanifest':'/manifest.webmanifest',
          '/cloudiff/portal/control/sw.js':'/sw.js',
          '/cloudiff/portal/control/icon.svg':'/icon.svg',
          '/cloudif/portal/control':'/',
          '/cloudif/portal/control/':'/',
        }
        target=routes.get(path)
        if target is None:return _ctl_prev_get(self)
        static=path.endswith(('/manifest.webmanifest','/sw.js','/icon.svg'))
        if static:
            username='static-resource';groups=''
        else:
            username=(self.headers.get('X-authentik-username') or self.headers.get('X-Authentik-Username') or '').strip()
            if not username:return self.send_error(401)
            groups=self.headers.get('X-authentik-groups') or self.headers.get('X-Authentik-Groups') or ''
        user=self.user()
        req=_ctl_req.Request('http://127.0.0.1:18200'+target,headers={
          'X-authentik-username':username,
          'X-authentik-groups':groups,
          'X-Forwarded-Proto':'https',
          'X-Forwarded-Host':self.headers.get('Host','cloudiff.duckdns.org'),
        })
        try:
            with _ctl_req.urlopen(req,timeout=12) as r:
                body=r.read(); code=r.status; ctype=r.headers.get('Content-Type','text/html; charset=utf-8')
        except _ctl_err.HTTPError as e:
            body=e.read(); code=e.code; ctype=e.headers.get('Content-Type','application/json')
        except Exception:
            return self.send_html(page(user,'resumo','<section class="card"><h2>Monitoramento temporariamente indisponível</h2><p>Tente novamente em alguns instantes.</p></section>'),503)
        static=path.endswith(('/manifest.webmanifest','/sw.js','/icon.svg'))
        self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Cache-Control','private, max-age=3600' if static else 'private, no-store');self.send_header('Service-Worker-Allowed','/cloudiff/portal/control/' if path.endswith('/sw.js') else '/');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
    Portal.do_GET=_ctl_dashboard_get;_ctl_dashboard_wrapped=True
# CloudIF control dashboard proxy END


# CloudIF access telemetry ingest BEGIN
import sqlite3 as _ati_sqlite3
import json as _ati_json
import hmac as _ati_hmac
import time as _ati_time
import os as _ati_os
import urllib.parse as _ati_urlparse
_ATI_DB=_ati_os.environ.get('CLOUDIF_ACCESS_INGEST_DB','/var/lib/cloudif/access-ingest/access.db')
_ATI_TOKEN=_ati_os.environ.get('CLOUDIF_ACCESS_INGEST_TOKEN','')
_ATI_ALLOWED={x.strip() for x in _ati_os.environ.get('CLOUDIF_ACCESS_INGEST_ALLOWED','127.0.0.1,10.62.91.3').split(',') if x.strip()}
def _ati_conn(ro=False):
    u=f'file:{_ATI_DB}?mode=ro' if ro else _ATI_DB
    c=_ati_sqlite3.connect(u,uri=ro,timeout=20);c.row_factory=_ati_sqlite3.Row;c.execute('pragma busy_timeout=20000');return c
def _ati_init():
    _ati_os.makedirs(_ati_os.path.dirname(_ATI_DB),exist_ok=True)
    c=_ati_conn();c.execute('pragma journal_mode=delete');c.executescript('create table if not exists snapshots(id integer primary key autoincrement,received_at text not null,source_host text not null,window_days integer not null,summary_json text not null,hosts_json text not null,routes_json text not null);create index if not exists idx_snapshots_received on snapshots(received_at desc);');c.commit();c.close()
def _ati_send(handler,code,data):
    raw=_ati_json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();handler.send_response(code);handler.send_header('Content-Type','application/json');handler.send_header('Cache-Control','no-store');handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('Content-Length',str(len(raw)));handler.end_headers();handler.wfile.write(raw)
def _ati_auth(handler):
    return handler.client_address[0] in _ATI_ALLOWED and bool(_ATI_TOKEN) and _ati_hmac.compare_digest(handler.headers.get('Authorization',''),'Bearer '+_ATI_TOKEN)
_ati_init()
if 'Portal' in globals() and not globals().get('_ati_wrapped'):
    _ati_prev_get=Portal.do_GET;_ati_prev_post=Portal.do_POST
    def _ati_get(self):
        path=_ati_urlparse.urlparse(self.path).path
        if path not in {'/cloudiff/internal/access-latest','/cloudif/internal/access-latest'}:return _ati_prev_get(self)
        if not _ati_auth(self):return _ati_send(self,403 if self.client_address[0] not in _ATI_ALLOWED else 401,{'ok':False,'error':'unauthorized'})
        c=_ati_conn(True);r=c.execute('select * from snapshots order by id desc limit 1').fetchone();c.close();return _ati_send(self,200,{'ok':True,'snapshot':dict(r) if r else None})
    def _ati_post(self):
        path=_ati_urlparse.urlparse(self.path).path
        if path not in {'/cloudiff/internal/access-ingest','/cloudif/internal/access-ingest'}:return _ati_prev_post(self)
        if not _ati_auth(self):return _ati_send(self,403 if self.client_address[0] not in _ATI_ALLOWED else 401,{'ok':False,'error':'unauthorized'})
        try:
            n=int(self.headers.get('Content-Length','0'));assert 0<n<=2000000
            d=_ati_json.loads(self.rfile.read(n));assert isinstance(d.get('summary'),dict) and isinstance(d.get('hosts'),list) and isinstance(d.get('routes'),list)
            c=_ati_conn();c.execute('insert into snapshots(received_at,source_host,window_days,summary_json,hosts_json,routes_json) values(?,?,?,?,?,?)',(_ati_time.strftime('%Y-%m-%dT%H:%M:%SZ',_ati_time.gmtime()),str(d.get('source_host') or 'proxy'),int(d.get('window_days') or 7),_ati_json.dumps(d['summary'],separators=(',',':')),_ati_json.dumps(d['hosts'],separators=(',',':')),_ati_json.dumps(d['routes'],separators=(',',':'))));c.execute('delete from snapshots where id not in (select id from snapshots order by id desc limit 1000)');c.commit();c.close();return _ati_send(self,202,{'ok':True})
        except Exception:return _ati_send(self,400,{'ok':False,'error':'invalid_payload'})
    Portal.do_GET=_ati_get;Portal.do_POST=_ati_post;_ati_wrapped=True
# CloudIF access telemetry ingest END

# CloudIF project identities and immediate onboarding BEGIN
import urllib.request as _oi_request, urllib.error as _oi_error, json as _oi_json, subprocess as _oi_subprocess
import cloudif_project_identity_panel as _oi_panel_module

def _oi_cfg(key,default=''):
    return os.environ.get(key) or setting_value(key,default)
def _oi_all():
    return _oi_panel_module.fetch(_oi_cfg('CLOUDIF_ONBOARDING_URL','http://127.0.0.1:18208'),_oi_cfg('CLOUDIF_ONBOARDING_API_TOKEN',''))
def _oi_visible(user):
    allowed={x['slug'] for x in user_visible_projects(user['username'],user['groups'])}
    return _oi_panel_module.visible(_oi_all(),allowed)
def _oi_panel(user):
    try:return _oi_panel_module.render(_oi_visible(user),_prod_csrf_token(user))
    except Exception:return '<section class="card"><h2>Identidades e conexões</h2><p class="pill bad">Onboarding temporariamente indisponível.</p></section>'
def _oi_send_json(handler,data,code=200):
    body=_oi_json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();handler.send_response(code);handler.send_header('Content-Type','application/json');handler.send_header('Cache-Control','no-store');handler.send_header('Pragma','no-cache');handler.send_header('Content-Length',str(len(body)));handler.end_headers();handler.wfile.write(body)
def _oi_can_rotate(user,slug):
    rows=user_visible_projects(user['username'],user['groups'])
    row=next((dict(x) for x in rows if x['slug']==slug),None)
    if not row:return False
    groups=set(user.get('groups') or [])
    return bool(user.get('admin') or row.get('owner')==user.get('username') or 'CloudIF-Tenants-Admin' in groups or 'CloudIF-Professor' in groups)
if 'render_projects' in globals() and not globals().get('_oi_render_wrapped'):
    _oi_prev_render=render_projects
    def render_projects(user):return _oi_prev_render(user)+_oi_panel(user)
    _oi_render_wrapped=True
if 'Portal' in globals() and not globals().get('_oi_portal_wrapped'):
    _oi_prev_get=Portal.do_GET;_oi_prev_post=Portal.do_POST
    def _oi_get(self):
        path=urllib.parse.urlparse(self.path).path.rstrip('/')
        if path in ('/cloudiff/portal/api/project-identities','/cloudif/portal/api/project-identities','/api/project-identities'):
            try:data={'ok':True,'projects':_oi_visible(self.user()),'secrets_exposed':False}
            except Exception:data={'ok':False,'error':'onboarding_unavailable'}
            body=_oi_json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();self.send_response(200 if data['ok'] else 503);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        return _oi_prev_get(self)
    def _oi_trigger():
        try:
            _oi_subprocess.run(['/usr/bin/systemctl','start','cloudif-control-plane-sync.service'],timeout=30,check=True)
            token=_oi_cfg('CLOUDIF_ONBOARDING_API_TOKEN','');req=_oi_request.Request(_oi_cfg('CLOUDIF_ONBOARDING_URL','http://127.0.0.1:18208')+'/v1/reconcile',data=b'{}',method='POST',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'});_oi_request.urlopen(req,timeout=240).read()
        except Exception as e:print('onboarding-trigger',type(e).__name__,flush=True)
    def _oi_post(self):
        path=urllib.parse.urlparse(self.path).path.rstrip('/')
        if path in ('/cloudiff/portal/action/rotate-project-credential','/cloudif/portal/action/rotate-project-credential'):
            if not _cloudif_security_valid_origin(self):return _oi_send_json(self,{'ok':False,'error':'origin_denied'},403)
            length=int(self.headers.get('Content-Length','0') or '0')
            if length<0 or length>200000:return _oi_send_json(self,{'ok':False,'error':'invalid_body'},413)
            try:form=urllib.parse.parse_qs(self.rfile.read(length).decode('utf-8','ignore'))
            except Exception:return _oi_send_json(self,{'ok':False,'error':'invalid_form'},400)
            val=lambda k,d='':(form.get(k) or [d])[0]
            user=self.user();slug=val('slug').strip();reason=val('reason').strip()
            if not _prod_csrf_equal(val('csrf_token'),_prod_csrf_token(user)):return _oi_send_json(self,{'ok':False,'error':'csrf_denied'},403)
            if not _oi_can_rotate(user,slug):return _oi_send_json(self,{'ok':False,'error':'project_denied'},403)
            payload=_oi_json.dumps({'requested_by':user['username'],'reason':reason or 'Rotação solicitada pelo painel do projeto'},separators=(',',':')).encode()
            req=_oi_request.Request(_oi_cfg('CLOUDIF_ONBOARDING_URL','http://127.0.0.1:18208')+'/v1/projects/'+urllib.parse.quote(slug,safe='')+'/rotate-credential',data=payload,method='POST',headers={'Authorization':'Bearer '+_oi_cfg('CLOUDIF_ONBOARDING_API_TOKEN',''),'Content-Type':'application/json','Accept':'application/json'})
            try:
                with _oi_request.urlopen(req,timeout=60) as r:data=_oi_json.load(r);code=r.status
            except _oi_error.HTTPError as e:
                try:data=_oi_json.load(e)
                except Exception:data={'ok':False,'error':'rotation_failed'}
                code=e.code
            except Exception:return _oi_send_json(self,{'ok':False,'error':'rotation_unavailable'},503)
            if code!=200 or not data.get('ok') or not data.get('token'):return _oi_send_json(self,{'ok':False,'error':data.get('error') or 'rotation_failed'},code if code in (400,403,404,409) else 502)
            return _oi_send_json(self,{'ok':True,'project_slug':slug,'client_id':data['client_id'],'rotation_id':data['rotation_id'],'token':data['token'],'one_time_delivery':True,'status':'active'},200)
        if path.endswith('/action/create_project'):
            if not _cloudif_security_valid_origin(self):
                return _cloudif_security_reject(self,'Origem da requisição não autorizada.')
            length=int(self.headers.get('Content-Length','0') or '0')
            if length<0 or length>2_000_000:return _cloudif_security_reject(self,'Corpo da requisição inválido.',413)
            raw=self.rfile.read(length)
            try:form=urllib.parse.parse_qs(raw.decode('utf-8','ignore'))
            except Exception:return _cloudif_security_reject(self,'Formulário inválido.',400)
            user=self.user();token=(form.get('csrf_token') or [''])[0]
            if not _prod_csrf_equal(token,_prod_csrf_token(user)):
                return _cloudif_security_reject(self,'Token CSRF inválido ou ausente.',403)
            val=lambda k,d='':(form.get(k) or [d])[0]
            name=val('name').strip();tenant=val('tenant').strip();desc=val('description')
            if not name:return _cloudif_security_reject(self,'Nome do projeto é obrigatório.',400)
            slug=slugify(name)
            if tenant and not tenant_visible(tenant,user['username'],user['groups']):
                return _cloudif_security_reject(self,'Sem permissão no tenant.',403)
            if not tenant and not setting_bool('CLOUDIF_ALLOW_GIT_ONLY_PROJECT',True):
                return _cloudif_security_reject(self,'Projeto sem banco desabilitado.',403)
            con=db();con.execute('''INSERT INTO projects(slug,name,tenant,owner,description,created_at,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET name=excluded.name,tenant=excluded.tenant,description=excluded.description,updated_at=excluded.updated_at''',(slug,name,tenant,user['username'],desc,now_iso(),now_iso()));con.execute('INSERT OR IGNORE INTO project_acl(slug,subject_type,subject) VALUES(?,?,?)',(slug,'user',user['username']));con.commit();con.close()
            log_action(user['username'],'create_project',slug,0,'tenant='+tenant,'')
            _oi_trigger()
            return self.redirect('/?tab=projetos&project='+urllib.parse.quote(slug))
        return _oi_prev_post(self)
    Portal.do_GET=_oi_get;Portal.do_POST=_oi_post;_oi_portal_wrapped=True
# CloudIF project identities and immediate onboarding END



# CloudIF human approvals BEGIN
import cloudif_approval_panel as _ap_panel

def _ap_cfg(key,default=''):
    return os.environ.get(key) or setting_value(key,default)
def _ap_raw():
    code,data=_ap_panel.request(_ap_cfg('CLOUDIF_APPROVAL_URL','http://127.0.0.1:18204'),_ap_cfg('CLOUDIF_APPROVAL_TOKEN',''),'GET','/v1/approvals?status=all')
    if code!=200 or not data.get('ok'):raise RuntimeError('approval_api_unavailable')
    return data.get('approvals') or []
def _ap_visible(user):
    slugs={x['slug'] for x in user_visible_projects(user['username'],user['groups'])}
    return _ap_panel.filter_rows(_ap_raw(),slugs)
def _ap_can_decide(user):
    groups=set(user.get('groups') or [])
    return bool(user.get('admin') or 'CloudIF-Tenants-Admin' in groups or 'CloudIF-Professor' in groups)
def _ap_human_role(user):
    groups=set(user.get('groups') or [])
    if user.get('admin') or 'CloudIF-Tenants-Admin' in groups:return 'admin'
    if 'CloudIF-Professor' in groups:return 'professor'
    return 'aluno'
def _ap_render(user):
    try:return _ap_panel.render(_ap_visible(user),_prod_csrf_token(user),_ap_can_decide(user))
    except Exception:return '<section class="card"><h2>Aprovações humanas</h2><p class="pill bad">Serviço de aprovações temporariamente indisponível.</p></section>'
# Dedicated project-context tab; not appended to Todos os projetos.
if 'Portal' in globals() and not globals().get('_ap_portal_wrapped'):
    _ap_prev_get=Portal.do_GET;_ap_prev_post=Portal.do_POST
    def _ap_send_json(self,code,data):
        body=_ap_json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    import json as _ap_json
    def _ap_get(self):
        path=urllib.parse.urlparse(self.path).path.rstrip('/')
        if path in ('/cloudiff/portal/api/approvals','/cloudif/portal/api/approvals','/api/approvals'):
            try:return _ap_send_json(self,200,{'ok':True,'approvals':_ap_visible(self.user()),'metadata_sanitized':True,'secrets_exposed':False,'can_decide':_ap_can_decide(self.user())})
            except Exception:return _ap_send_json(self,503,{'ok':False,'error':'approval_api_unavailable'})
        return _ap_prev_get(self)
    def _ap_post(self):
        path=urllib.parse.urlparse(self.path).path.rstrip('/')
        if path.endswith('/action/approval'):
            if not _cloudif_security_valid_origin(self):return _cloudif_security_reject(self,'Origem da requisição não autorizada.')
            length=int(self.headers.get('Content-Length','0') or '0')
            if length<0 or length>200000:return _cloudif_security_reject(self,'Corpo da requisição inválido.',413)
            form=urllib.parse.parse_qs(self.rfile.read(length).decode('utf-8','ignore'));val=lambda k,d='':(form.get(k) or [d])[0]
            user=self.user()
            if not _prod_csrf_equal(val('csrf_token'),_prod_csrf_token(user)):return _cloudif_security_reject(self,'Token CSRF inválido ou ausente.',403)
            if not _ap_can_decide(user):return _cloudif_security_reject(self,'Perfil sem permissão para decidir aprovações.',403)
            aid=val('approval_id').strip();operation=val('operation').strip();reason=val('rejection_reason').strip()
            rows={x['approval_id']:x for x in _ap_visible(user)};item=rows.get(aid)
            if not item or item.get('status') not in ('pending','pending_second'):return _cloudif_security_reject(self,'Aprovação não encontrada, expirada ou já decidida.',409)
            if operation=='approve':endpoint='/v1/approvals/'+urllib.parse.quote(aid)+'/approve';payload={'approved_by':user['username'],'approver_role':_ap_human_role(user)}
            elif operation=='reject' and 4<=len(reason)<=500:endpoint='/v1/approvals/'+urllib.parse.quote(aid)+'/reject';payload={'rejected_by':user['username'],'rejection_reason':reason}
            else:return _cloudif_security_reject(self,'Decisão inválida.',400)
            code,data=_ap_panel.request(_ap_cfg('CLOUDIF_APPROVAL_URL','http://127.0.0.1:18204'),_ap_cfg('CLOUDIF_APPROVAL_TOKEN',''),'POST',endpoint,payload)
            if code!=200 or not data.get('ok'):return _cloudif_security_reject(self,'A decisão não pôde ser registrada.',409)
            log_action(user['username'],'approval_'+operation,aid,0,item['project_slug'],'')
            return self.redirect('/cloudiff/portal/?tab=aprovacoes')
        return _ap_prev_post(self)
    Portal.do_GET=_ap_get;Portal.do_POST=_ap_post;_ap_portal_wrapped=True
# CloudIF human approvals END



# CloudIF transaction observability BEGIN
import cloudif_transaction_panel as _tx_panel

def _tx_cfg(key,default=''):
    return os.environ.get(key) or setting_value(key,default)
def _tx_visible(user):
    rows=[]
    for prj in user_visible_projects(user['username'],user['groups']):
        try:
            d=_tx_panel.fetch(_tx_cfg('CLOUDIF_MONITOR_URL','http://127.0.0.1:18199'),_tx_cfg('CLOUDIF_MONITOR_TOKEN',''),prj['slug'])
            if d.get('ok') and d.get('project_slug')==prj['slug'] and d.get('sanitized') is True and d.get('secrets_exposed') is False:rows.append(d)
        except Exception:pass
    return rows
def _tx_render(user):return _tx_panel.render(_tx_visible(user))
# Dedicated project-context tab; not appended to Todos os projetos.
if 'Portal' in globals() and not globals().get('_tx_portal_wrapped'):
    _tx_prev_get=Portal.do_GET
    def _tx_get(self):
        path=urllib.parse.urlparse(self.path).path.rstrip('/')
        if path in ('/cloudiff/portal/api/transactions','/cloudif/portal/api/transactions','/api/transactions'):
            try:
                rows=_tx_visible(self.user());body=_ap_json.dumps({'ok':True,'projects':rows,'project_scoped':True,'secrets_exposed':False},ensure_ascii=False,separators=(',',':')).encode();code=200
            except Exception:
                body=b'{"ok":false,"error":"transaction_monitor_unavailable"}';code=503
            self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        return _tx_prev_get(self)
    Portal.do_GET=_tx_get;_tx_portal_wrapped=True
# CloudIF transaction observability END



# CloudIF promotion history BEGIN
import cloudif_promotion_panel as _ph_panel
def _ph_data():return _ph_panel.fetch(os.environ.get('CLOUDIF_MONITOR_URL','http://127.0.0.1:18199'),os.environ.get('CLOUDIF_MONITOR_TOKEN',''))
def _ph_render(user):
    slugs={x['slug'] for x in user_visible_projects(user['username'],user['groups'])}
    return _ph_panel.render(_ph_data()) if 'sistema-de-biblioteca-teste' in slugs else ''
# Dedicated project-context tab; not appended to Todos os projetos.
if 'Portal' in globals() and not globals().get('_ph_portal_wrapped'):
    _ph_prev_get=Portal.do_GET
    def _ph_get(self):
        path=urllib.parse.urlparse(self.path).path.rstrip('/')
        if path in ('/cloudiff/portal/api/promotions','/cloudif/portal/api/promotions','/api/promotions'):
            try:
                slugs={x['slug'] for x in user_visible_projects(self.user()['username'],self.user()['groups'])}
                if 'sistema-de-biblioteca-teste' not in slugs:raise PermissionError()
                body=json.dumps(_ph_data(),ensure_ascii=False,separators=(',',':')).encode();code=200
            except PermissionError:body=b'{"ok":false,"error":"project_not_allowed"}';code=403
            except Exception:body=b'{"ok":false,"error":"promotion_monitor_unavailable"}';code=503
            self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        return _ph_prev_get(self)
    Portal.do_GET=_ph_get;_ph_portal_wrapped=True
# CloudIF promotion history END



# CloudIF asynchronous reconciliation tab BEGIN
import cloudif_reconcile_panel as _rec
if 'Portal' in globals() and not globals().get('_rec_tab_wrapped'):
    _rec_prev_get=Portal.do_GET
    def _rec_get(self):
        parsed=urllib.parse.urlparse(self.path);path=parsed.path.rstrip('/');tab=(urllib.parse.parse_qs(parsed.query).get('tab') or [''])[0]
        if path in ('','/cloudiff/portal','/cloudif/portal') and tab=='reconciliacao':return self.send_html(page(self.user(),'reconciliacao',_rec.render()))
        if path in ('/cloudiff/portal/api/reconciliation','/cloudif/portal/api/reconciliation','/api/reconciliation'):
            try:data=_rec.data();code=200
            except Exception:data={'ok':False,'error':'reconciliation_unavailable','secrets_exposed':False};code=503
            raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        return _rec_prev_get(self)
    Portal.do_GET=_rec_get;_rec_tab_wrapped=True
# CloudIF asynchronous reconciliation tab END

# CloudIF project capabilities tab BEGIN
import cloudif_project_capabilities_panel as _cap
if 'Portal' in globals() and not globals().get('_cap_tab_wrapped'):
    _cap_prev_get=Portal.do_GET
    def _cap_get(self):
        parsed=urllib.parse.urlparse(self.path);path=parsed.path.rstrip('/');tab=(urllib.parse.parse_qs(parsed.query).get('tab') or [''])[0]
        if path in ('','/cloudiff/portal','/cloudif/portal') and tab=='capacidades':
            return self.send_html(page(self.user(),'capacidades',_cap.render()))
        if path in ('/cloudiff/portal/api/project-capabilities','/cloudif/portal/api/project-capabilities','/api/project-capabilities'):
            try:data=_cap.data();code=200 if data.get('ok') else 503
            except Exception:data={'ok':False,'error':'capabilities_unavailable','secrets_exposed':False};code=503
            raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        return _cap_prev_get(self)
    Portal.do_GET=_cap_get;_cap_tab_wrapped=True
# CloudIF project capabilities tab END

# CloudIF approvals dedicated tab BEGIN
if 'Portal' in globals() and not globals().get('_ap_tab_wrapped'):
    _ap_tab_prev_get=Portal.do_GET
    def _ap_tab_get(self):
        parsed=urllib.parse.urlparse(self.path);path=parsed.path.rstrip('/');tab=(urllib.parse.parse_qs(parsed.query).get('tab') or [''])[0]
        if path in ('','/cloudiff/portal','/cloudif/portal') and tab=='aprovacoes':
            user=self.user();return self.send_html(page(user,'aprovacoes',_ap_render(user)))
        return _ap_tab_prev_get(self)
    Portal.do_GET=_ap_tab_get;_ap_tab_wrapped=True
# CloudIF approvals dedicated tab END

# CloudIF AI agents guide BEGIN
import cloudif_ai_agents_guide as _aig
def _aig_data(user):return _aig.guide_data(_oi_visible(user))
def _aig_render(user):return _aig.render(_oi_visible(user),_prod_csrf_token(user))
if 'Portal' in globals() and not globals().get('_aig_wrapped'):
    _aig_prev_get=Portal.do_GET
    def _aig_get(self):
        parsed=urllib.parse.urlparse(self.path);path=parsed.path.rstrip('/');tab=(urllib.parse.parse_qs(parsed.query).get('tab') or [''])[0]
        if path in ('','/cloudiff/portal','/cloudif/portal') and tab=='agentes':
            user=self.user();return self.send_html(page(user,'agentes',_aig_render(user)))
        if path in ('/cloudiff/portal/api/agent-guide','/cloudif/portal/api/agent-guide','/api/agent-guide'):
            try:data=_aig_data(self.user());code=200
            except Exception:data={'ok':False,'error':'agent_guide_unavailable','secrets_exposed':False};code=503
            raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        return _aig_prev_get(self)
    Portal.do_GET=_aig_get;_aig_wrapped=True
# CloudIF AI agents guide END

# CloudIF unique focused sections BEGIN
import cloudif_portal_sections98 as _focus98
_FOCUS98_TABS={'opcoes-projeto','gestao-agentes','documentacao-mcp','monitor-saude','monitor-transacoes','monitor-promocoes','monitor-filas','monitor-telemetria','ajuda','ajuda-token','ajuda-clientes','ajuda-aprovacoes','ajuda-ferramentas','admin-usuarios','admin-politicas','admin-identidades','admin-configuracoes','admin-auditoria','admin-manutencao'}
def _focus98_render(tab,user):
    if tab=='opcoes-projeto':return _focus98.options_project()
    if tab=='gestao-agentes':return _focus98.agent_management()
    if tab=='documentacao-mcp':return _focus98.documentation_mcp()
    if tab.startswith('monitor-'):return _focus98.monitor(tab)
    if tab.startswith('ajuda'):return _focus98.help_page(tab)
    if tab.startswith('admin-'):
        groups=set(user.get('groups') or [])
        if not (user.get('admin') or 'CloudIF-Tenants-Admin' in groups):return '<section class="card"><h1>Acesso negado</h1><p>Área restrita à administração.</p></section>'
        return _focus98.admin_page(tab)
    raise KeyError(tab)
if 'Portal' in globals() and not globals().get('_focus98_wrapped'):
    _focus98_prev_get=Portal.do_GET
    def _focus98_get(self):
        parsed=urllib.parse.urlparse(self.path);path=parsed.path.rstrip('/');tab=(urllib.parse.parse_qs(parsed.query).get('tab') or [''])[0]
        if path in ('','/cloudiff/portal','/cloudif/portal') and tab in _FOCUS98_TABS:
            user=self.user();return self.send_html(page(user,tab,_focus98_render(tab,user)))
        if path in ('/cloudiff/portal/api/navigation','/cloudif/portal/api/navigation','/api/navigation'):
            user=self.user();raw=json.dumps({'ok':True,'policy':'one_item_one_route_one_purpose','primary_groups':['Início','Meus Projetos','Agentes de IA','Monitoramento','Administração' if user.get('admin') or 'CloudIF-Tenants-Admin' in set(user.get('groups') or []) else None,'Ajuda'],'unique_routes_required':True,'secrets_exposed':False},ensure_ascii=False,separators=(',',':')).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        return _focus98_prev_get(self)
    Portal.do_GET=_focus98_get;_focus98_wrapped=True
# CloudIF unique focused sections END

# CloudIF hierarchical enterprise navigation BEGIN
import re as _nav95_re
_NAV95_CSS=r"""
<style id="cloudif-enterprise-navigation">
.tabs.enterprise-nav{display:flex;align-items:center;gap:7px;overflow:visible;padding:8px;position:sticky;top:112px;z-index:80;background:rgba(255,255,255,.97);backdrop-filter:blur(16px);border:1px solid #d7e4da;border-radius:16px;box-shadow:0 12px 30px rgba(20,64,36,.10)}
.enterprise-nav>a,.enterprise-nav summary{display:flex;align-items:center;gap:8px;min-height:44px;padding:10px 13px;border-radius:11px;color:#31543b;font-weight:800;text-decoration:none;cursor:pointer;white-space:nowrap;list-style:none}
.enterprise-nav summary::-webkit-details-marker{display:none}.enterprise-nav summary::after{content:'⌄';font-size:.85rem;opacity:.65;transition:transform .18s ease}.enterprise-nav details[open]>summary::after{transform:rotate(180deg)}
.enterprise-nav>a:hover,.enterprise-nav summary:hover{background:#edf7f0;color:#0d5a2c}.enterprise-nav>a.active,.enterprise-nav details.active>summary{background:linear-gradient(135deg,#176b35,#0f5132);color:#fff;box-shadow:0 5px 14px rgba(23,107,53,.22)}
.enterprise-nav details{position:relative}.enterprise-submenu{position:absolute;left:0;top:calc(100% + 9px);min-width:290px;padding:9px;border:1px solid #d7e4da;border-radius:15px;background:#fff;box-shadow:0 20px 44px rgba(15,61,34,.18);display:grid;gap:3px;z-index:200}.enterprise-submenu.wide{min-width:330px}.enterprise-submenu a{display:grid;grid-template-columns:34px 1fr;gap:10px;align-items:center;min-height:48px;padding:9px 11px;border-radius:10px;text-decoration:none;color:#264a32}.enterprise-submenu a:hover{background:#eef8f1}.enterprise-submenu a.active{background:#176b35;color:#fff}.enterprise-submenu .nav-icon{width:32px;height:32px;border-radius:9px;display:grid;place-items:center;background:#e4f3e8;font-size:.86rem;font-weight:900;color:#176b35}.enterprise-submenu a.active .nav-icon{background:#ffffff22;color:#fff}.enterprise-submenu strong{display:block}.enterprise-submenu small{display:block;margin-top:2px;color:#708178;font-weight:600}.enterprise-submenu a.active small{color:#e5f6e9}.enterprise-nav .logout-btn{margin-left:auto;position:static!important}
.nav-mobile-label{display:none}.nav-divider{height:1px;background:#e3ece5;margin:5px 4px}.nav-admin-lock{font-size:.72rem;padding:3px 7px;border-radius:999px;background:#fef3c7;color:#92400e;margin-left:auto}
@media(max-width:1050px){.tabs.enterprise-nav{overflow-x:auto;overflow-y:visible}.enterprise-submenu{position:fixed;left:18px;right:18px;top:auto;min-width:0;max-height:70vh;overflow:auto}}
@media(max-width:700px){.tabs.enterprise-nav{display:grid!important;grid-template-columns:1fr;position:relative;top:0;overflow:visible}.enterprise-nav details{width:100%}.enterprise-nav>a,.enterprise-nav summary{width:100%;justify-content:space-between}.enterprise-submenu,.enterprise-submenu.wide{position:static;min-width:0;margin-top:5px;box-shadow:none;background:#f8fcf9}.enterprise-nav .logout-btn{margin:4px 0 0!important}.nav-mobile-label{display:inline}}
</style>
"""
_NAV95_SCRIPT=r"""
<script id="cloudif-enterprise-navigation-js">
(function(){
 function closeOthers(current){document.querySelectorAll('.enterprise-nav details[open]').forEach(d=>{if(d!==current)d.removeAttribute('open')})}
 document.addEventListener('click',e=>{const s=e.target.closest('.enterprise-nav summary');if(s)closeOthers(s.parentElement);else if(!e.target.closest('.enterprise-nav'))document.querySelectorAll('.enterprise-nav details[open]').forEach(d=>d.removeAttribute('open'))});
 document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelectorAll('.enterprise-nav details[open]').forEach(d=>d.removeAttribute('open'))});
 function activateProjectSection(){
  const q=new URLSearchParams(location.search),section=q.get('section');if(!section)return;
  const map={containers:'Contêineres',backups:'Backup',services:'Serviços',publications:'Publicações',options:'Visão geral'};const label=map[section];if(!label)return;
  let tries=0;const timer=setInterval(()=>{tries++;const buttons=[...document.querySelectorAll('.project-tabs button')];const target=buttons.find(b=>b.textContent.trim()===label);if(target){target.click();target.scrollIntoView({behavior:'smooth',block:'center'});clearInterval(timer)}else if(tries>30)clearInterval(timer)},150);
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',activateProjectSection);else activateProjectSection();
})();
</script>
"""
def _nav95_link(tab,label,icon,desc,href,current):
    target=href or '/cloudiff/portal/?tab='+tab
    cls='active' if current==tab else 'submenu-link'
    return f'<a class="{cls}" href="{html.escape(target,quote=True)}"><span class="nav-icon">{icon}</span><span><strong>{html.escape(label)}</strong><small>{html.escape(desc)}</small></span></a>'
def _nav95_group(label,icon,items,current,active_tabs,wide=False):
    active=current in active_tabs
    links=''.join(_nav95_link(*item,current) for item in items)
    return f'<details class="{"active" if active else ""}"><summary><span>{icon}</span>{html.escape(label)}</summary><div class="enterprise-submenu {"wide" if wide else ""}">{links}</div></details>'
def _nav141_section(title,items,current):
    links=''.join(_nav95_link(*item,current) for item in items)
    return f'<section class="system-menu-section"><h3>{html.escape(title)}</h3>{links}</section>'
def _nav141_system_group(sections,current,active_tabs):
    active=current in active_tabs
    body=''.join(_nav141_section(title,items,current) for title,items in sections if items)
    return f'<details class="system-menu {"active" if active else ""}"><summary><span class="primary-nav-icon">⚙</span><span>Sistema</span></summary><div class="enterprise-submenu system-mega-menu">{body}</div></details>'
def _nav95_render(user,current):
    deploy=[('publicacao','Publicar','', 'Versões, produção e rollback',None),('git','Código','', 'Repositórios e infraestrutura',None)]
    monitor=[('monitor-saude','Status','', 'Saúde dos serviços',None),('monitor-transacoes','Atividades','', 'Operações recentes',None),('monitor-promocoes','Histórico','', 'Deploys e rollbacks',None),('monitor-filas','Filas','', 'Workers e processamento',None),('monitor-telemetria','Métricas','', 'Telemetria da plataforma',None)]
    platform=[('resumo','Visão geral','', 'Resumo da plataforma',None),('opcoes-projeto','Recursos','', 'Serviços, contêineres e backups',None),('operacao-producao','Produção','', 'Janelas e incidentes',None)]
    automation=[('agentes','IA','', 'Conectar agentes',None),('gestao-agentes','Agentes','', 'Identidades e estado',None),('capacidades','Ferramentas','', 'Capacidades por projeto',None),('reconciliacao','Automação','', 'Filas e reconciliação',None),('aprovacoes','Aprovações','', 'Decisões humanas',None),('documentacao-mcp','MCP','', 'Protocolo e documentação',None)]
    help_items=[('ajuda','Ajuda','', 'Primeiros passos',None),('ajuda-token','Tokens','', 'Rotação e armazenamento',None),('ajuda-conectar','Clientes','', 'ChatGPT, Claude e Llama',None),('ajuda-aprovacoes','Papéis','', 'Como aprovações funcionam',None),('ajuda-ferramentas','Referência','', 'Ferramentas MCP',None)]
    administration=[]
    groups={str(x) for x in (user.get('groups') or [])}
    if user.get('admin') or groups.intersection({'CloudIF-Tenants-Admin','CloudIF-Professor'}):
        administration=[('admin-usuarios','Usuários','', 'Contas, grupos e perfis',None),('admin-politicas','Acessos','', 'Políticas e permissões',None),('admin-identidades','Identidades','', 'Clientes e identidades AGIA',None),('admin-configuracoes','Configurações','', 'Parâmetros e integrações',None),('admin-auditoria','Auditoria','', 'Histórico administrativo',None),('admin-manutencao','Manutenção','', 'Diagnóstico controlado',None)]
    sections=[('Plataforma',platform),('IA e automação',automation),('Administração',administration),('Ajuda',help_items)]
    all_system={x[0] for _,items in sections for x in items}
    out='<nav class="tabs enterprise-nav ui141-nav ui143-nav" aria-label="Navegação principal">'
    out+=_nav95_link('projetos','Projetos','', '',None,current)
    out+=_nav95_link('bancos','Banco','', '',None,current)
    out+=_nav95_group('Publicar','',deploy,current,{x[0] for x in deploy},True)
    out+=_nav95_group('Monitorar','',monitor,current,{x[0] for x in monitor},True)
    out+=_nav141_system_group(sections,current,all_system).replace('<span>Sistema</span>','<span>Mais</span>')
    out+='<a class="btn logout-btn" href="/outpost.goauthentik.io/sign_out" aria-label="Sair do CloudIF">Sair</a></nav>'
    return out
if 'page' in globals() and not globals().get('_nav95_wrapped'):
    _nav95_prev_page=page
    def page(user,tab,body):
        doc=_nav95_prev_page(user,tab,body)
        nav=_nav95_render(user,tab)
        doc=_nav95_re.sub(r'<nav class="tabs"[^>]*>.*?</nav>',nav,doc,count=1,flags=_nav95_re.S|_nav95_re.I)
        doc=doc.replace('</head>',_NAV95_CSS+'</head>',1).replace('</body>',_NAV95_SCRIPT+'</body>',1)
        return doc
    _nav95_wrapped=True
# CloudIF hierarchical enterprise navigation END

# CloudIF professional clear UI BEGIN
_UI141_CSS='<style id="cloudif-ui141">\n:root{--ui141-bg:#f4f7f5;--ui141-surface:#fff;--ui141-surface-soft:#f8faf9;--ui141-border:#dbe5df;--ui141-text:#17251d;--ui141-muted:#64736a;--ui141-primary:#126b36;--ui141-primary-strong:#0b5128;--ui141-blue:#2563eb;--ui141-warning:#b7791f;--ui141-danger:#b42318;--ui141-shadow:0 12px 32px rgba(20,55,34,.08)}\nbody{background:linear-gradient(180deg,#eef5f0 0,#f6f8f7 260px,#f4f7f5 100%);color:var(--ui141-text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.5}\n.header{border-bottom:1px solid var(--ui141-border)!important;background:rgba(255,255,255,.96)!important;box-shadow:0 4px 18px rgba(20,55,34,.05)}\n.header-inner{max-width:1440px!important;padding:14px 24px!important}.if-mark{transform:scale(.68);transform-origin:left center;margin-right:-18px}.brand{gap:12px!important}.brand-title h1{font-size:1.35rem!important;letter-spacing:-.02em}.brand-title p{font-size:.82rem!important;color:var(--ui141-muted)!important}.header-meta{gap:5px!important}.inst-badge{font-size:.72rem!important;padding:6px 10px!important}.ai-project-tag{font-size:.68rem!important;padding:5px 9px!important;background:#eef2ff!important;color:#4338ca!important;border:1px solid #d8ddff!important}\n.wrap{max-width:1440px!important;margin:18px auto!important;padding:0 22px!important}.card,.box,.project-card,.cm-card{border-color:var(--ui141-border)!important;box-shadow:var(--ui141-shadow)!important}.card{border-radius:18px!important}.box,.project-card,.cm-card{border-radius:16px!important}\n.userbar{padding:12px 16px!important;align-items:center!important;background:rgba(255,255,255,.92)!important}.userbar>div:first-child{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.userbar>div:first-child b{font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;color:var(--ui141-muted)}.userbar .small{width:100%;margin-top:-4px}.userbar .btn{min-height:38px!important;padding:7px 11px!important;font-size:.82rem!important}\n.tabs.enterprise-nav.ui141-nav{top:88px!important;border-radius:14px!important;padding:7px!important;gap:5px!important;box-shadow:0 10px 28px rgba(20,55,34,.10)!important}.ui141-nav>a,.ui141-nav summary{min-height:42px!important;padding:9px 12px!important;font-size:.88rem!important}.ui141-nav .primary-nav-icon{display:inline-grid;place-items:center;width:22px;height:22px}.ui141-nav .logout-btn{background:#f3f5f4!important;color:#34443a!important;border:1px solid var(--ui141-border)!important}\n.enterprise-submenu{border-color:var(--ui141-border)!important;box-shadow:0 22px 50px rgba(13,48,29,.18)!important}.enterprise-submenu:not(.system-mega-menu){min-width:310px!important}.system-mega-menu{right:0!important;left:auto!important;width:min(760px,calc(100vw - 44px))!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:8px 14px!important;padding:16px!important;max-height:min(72vh,680px);overflow:auto}.system-menu-section{min-width:0}.system-menu-section h3{margin:2px 7px 7px;padding-bottom:7px;border-bottom:1px solid var(--ui141-border);font-size:.72rem;text-transform:uppercase;letter-spacing:.09em;color:var(--ui141-muted)}.system-menu-section>a{display:grid!important}.enterprise-submenu a{min-height:54px!important}.enterprise-submenu strong{font-size:.86rem}.enterprise-submenu small{font-size:.74rem;line-height:1.3}\nh1,h2,h3{letter-spacing:-.02em}h2{font-size:clamp(1.3rem,2.2vw,1.75rem);margin-top:.2rem}h3{font-size:1rem}.small,.cm-muted{color:var(--ui141-muted)!important}\n.grid{gap:16px!important}.grid2{gap:16px!important}.box{padding:16px!important;background:var(--ui141-surface)!important}.kpi{font-size:2rem!important;letter-spacing:-.04em}.project-card{padding:18px!important;background:#fff!important}.project-line{gap:18px!important}.project-card h3{margin-top:0!important}\n.btn,button,input[type="submit"]{min-height:42px!important;padding:9px 14px!important;border-radius:10px!important;box-shadow:none!important}.btn{background:var(--ui141-primary)!important}.btn.blue{background:var(--ui141-blue)!important}.btn.red{background:var(--ui141-danger)!important}.btn.amber{background:var(--ui141-warning)!important}.btn.light{background:#edf7f0!important;color:#155b2e!important;border:1px solid #cfe5d5!important}.btn.gray{background:#eef1ef!important;color:#35463b!important;border:1px solid #d7dfda!important}.btn:hover,button:hover,input[type="submit"]:hover{transform:none!important;filter:brightness(.97);box-shadow:0 5px 14px rgba(20,55,34,.10)!important}\ninput,select,textarea{border-color:#cfdad3!important;border-radius:10px!important;min-height:42px!important;background:#fff!important}input:focus,select:focus,textarea:focus{outline:3px solid rgba(37,99,235,.15);border-color:#4f7ed9!important}\ntable{border:1px solid var(--ui141-border);border-radius:14px!important}th{background:#f0f5f2!important;color:#34483b!important;text-transform:uppercase;letter-spacing:.035em;font-size:.72rem!important}td,th{padding:11px 12px!important}.pill{padding:5px 9px!important;font-size:.72rem!important}.help,.warn,.ai-disclaimer{border-radius:12px!important}\ndetails:not(.enterprise-nav details){border-color:var(--ui141-border)!important;background:#fff!important}.footer{border-top:1px solid var(--ui141-border);padding-top:20px;color:var(--ui141-muted)!important}\n@media(max-width:980px){.header-inner{padding:12px 18px!important}.wrap{padding:0 16px!important}.tabs.enterprise-nav.ui141-nav{top:0!important;position:relative!important;overflow:visible!important}.system-mega-menu{position:fixed!important;left:16px!important;right:16px!important;width:auto!important;grid-template-columns:1fr 1fr!important}}\n@media(max-width:700px){.header-inner{gap:8px!important}.if-mark{display:none!important}.brand-title h1{font-size:1.2rem!important}.header-meta{display:none!important}.wrap{padding:0 12px!important;margin-top:12px!important}.userbar{display:grid!important;gap:10px!important}.userbar>div:first-child{display:block!important}.userbar>div:first-child b{display:inline!important}.tabs.enterprise-nav.ui141-nav{display:grid!important;grid-template-columns:1fr 1fr!important;gap:6px!important}.ui141-nav>a,.ui141-nav summary{justify-content:center!important;text-align:center!important}.ui141-nav details{width:auto!important}.ui141-nav .logout-btn{grid-column:1/-1!important}.enterprise-submenu,.enterprise-submenu.wide,.system-mega-menu{position:static!important;width:auto!important;max-height:none!important;grid-template-columns:1fr!important;margin-top:6px!important;grid-column:1/-1!important}.system-menu{grid-column:1/-1}.system-menu>summary{justify-content:center!important}.system-menu-section h3{margin-top:8px}.card{padding:14px!important}.grid,.grid2{grid-template-columns:1fr!important}.btn{width:100%;text-align:center}.project-line{grid-template-columns:1fr!important}}\n@media(max-width:420px){.tabs.enterprise-nav.ui141-nav{grid-template-columns:1fr!important}.system-menu{grid-column:auto}.ui141-nav .logout-btn{grid-column:auto!important}}\n</style>'
if 'page' in globals() and not globals().get('_ui141_wrapped'):
    _ui141_prev_page=page
    def page(user,tab,body):
        doc=_ui141_prev_page(user,tab,body)
        return doc.replace('</head>',_UI141_CSS+'</head>',1)
    _ui141_wrapped=True
# CloudIF professional clear UI END

# CloudIF human-centered UI BEGIN
_UI142_ASSETS='<style id="cloudif-ui142">\n.page-context{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin:2px 0 16px;padding:4px 2px}.page-context h1{margin:0;font-size:clamp(1.45rem,2.7vw,2rem);letter-spacing:-.035em}.page-context p{margin:4px 0 0;color:var(--ui141-muted);max-width:760px}.page-context-badge{flex:none;background:#eaf4ed;color:#175d31;border:1px solid #cfe1d4;border-radius:999px;padding:7px 11px;font-size:.75rem;font-weight:750}\n.project-toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:14px 0 18px;padding:12px;background:#f6f9f7;border:1px solid var(--ui141-border);border-radius:14px}.project-search{flex:1;min-width:230px;position:relative}.project-search input{width:100%;padding-left:38px!important}.project-search:before{content:\'⌕\';position:absolute;left:13px;top:8px;color:#6b7a70;font-size:1.2rem;z-index:1}.project-count{font-size:.8rem;color:var(--ui141-muted);font-weight:700}.view-toggle{display:flex;gap:4px;background:#e9efeb;padding:4px;border-radius:10px}.view-toggle button{min-height:34px!important;padding:6px 9px!important;background:transparent!important;color:#415148!important}.view-toggle button.active{background:white!important;color:#145b2e!important;box-shadow:0 2px 8px rgba(20,55,34,.08)!important}\n#cloudif-project-list>.project-card{transition:border-color .15s ease,box-shadow .15s ease;background:white!important}.project-card:hover{border-color:#b9d0c0!important;box-shadow:0 12px 28px rgba(20,55,34,.09)!important}.project-card[hidden]{display:none!important}.project-card .project-line{grid-template-columns:minmax(260px,1.45fr) minmax(120px,.55fr) minmax(180px,.8fr) minmax(145px,.55fr)!important}.project-card h3{font-size:1.04rem;margin-bottom:4px!important}.project-card .small{font-size:.76rem}.project-card .project-manage{margin:0!important;padding:0!important;border:0!important;background:transparent!important}.project-card .project-manage>summary{list-style:none;display:flex;align-items:center;justify-content:center;min-height:40px;padding:8px 11px;border-radius:10px;background:#eef5f0;color:#145b2e;font-size:.82rem}.project-card .project-manage>summary::-webkit-details-marker{display:none}.project-card .project-manage[open]>summary{background:#dcecdf}.project-card .project-manage-panel{position:absolute;right:18px;margin-top:6px;width:min(430px,calc(100vw - 40px));z-index:20;background:white;border:1px solid var(--ui141-border);border-radius:13px;box-shadow:0 18px 42px rgba(15,48,29,.18);padding:12px}.project-card{position:relative}.project-manage-panel form{display:flex;gap:6px;flex-wrap:wrap}.project-manage-panel .btn,.project-manage-panel button{width:auto!important;min-height:36px!important;padding:7px 10px!important;font-size:.78rem!important}\n.projects-compact .project-card{padding:11px!important;margin:8px 0!important}.projects-compact .project-card p:not(.small){display:none}.projects-compact .project-line{grid-template-columns:minmax(240px,1.6fr) .5fr .75fr .45fr!important}.projects-compact .btn{min-height:34px!important;padding:6px 9px!important;font-size:.76rem!important}\n.admin-global-disclosure{margin:0 0 16px!important;border-radius:16px!important;background:#fff!important;box-shadow:var(--ui141-shadow)!important}.admin-global-disclosure>summary{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:14px 16px;color:var(--ui141-text)!important}.admin-global-disclosure>summary:after{content:\'Mostrar recursos\';font-size:.75rem;color:var(--ui141-muted);font-weight:650}.admin-global-disclosure[open]>summary:after{content:\'Ocultar recursos\'}.admin-global-disclosure .cm-card{border:0!important;box-shadow:none!important;margin:0!important;padding-top:0!important}\n.cloudif-wizard>.card{max-width:980px;margin-inline:auto}.cloudif-wizard>.card>h2{padding-bottom:10px;border-bottom:1px solid var(--ui141-border)}\nbody.ui142-tab-bancos main>details:not([open]),body.ui142-tab-publicacao main>details:not([open]){background:#fff}.ui142-empty{padding:26px;text-align:center;color:var(--ui141-muted);border:1px dashed #cdd9d1;border-radius:14px;background:#fbfcfb}\n@media(max-width:980px){.project-card .project-line,.projects-compact .project-line{grid-template-columns:1fr 1fr!important}.project-card .project-line>div:first-child{grid-column:1/-1}.project-card .project-manage-panel{position:fixed;left:16px;right:16px;bottom:16px;width:auto;max-height:60vh;overflow:auto}}\n@media(max-width:700px){.page-context{align-items:flex-start;flex-direction:column;margin-bottom:12px}.page-context-badge{display:none}.project-toolbar{position:sticky;top:6px;z-index:25;box-shadow:0 8px 18px rgba(20,55,34,.10)}.project-search{min-width:100%}.view-toggle{width:100%}.view-toggle button{flex:1}.project-card .project-line,.projects-compact .project-line{grid-template-columns:1fr!important}.project-card .project-line>div:first-child{grid-column:auto}.project-card .project-line>div{padding-top:8px;border-top:1px solid #edf1ee}.project-card .project-line>div:first-child{padding-top:0;border-top:0}.project-card .project-manage>summary{width:100%}.project-manage-panel form{display:grid;grid-template-columns:1fr 1fr}.project-manage-panel .btn,.project-manage-panel button{width:100%!important}.admin-global-disclosure>summary{align-items:flex-start;flex-direction:column}}\nbody.ui142-tab-projetos #cloudif-project-list>.project-card>.project-line{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:14px!important;align-items:start!important}body.ui142-tab-projetos #cloudif-project-list>.project-card>.project-line>div{min-width:0!important;margin:0!important;padding:16px!important;border:1px solid var(--ui141-border)!important;border-radius:12px!important;background:var(--ui141-surface)!important}body.ui142-tab-projetos #cloudif-project-list>.project-card>.project-line>div:nth-child(-n+3){min-height:168px}body.ui142-tab-projetos #cloudif-project-list>.project-card>.project-line>div:nth-child(4){display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:14px!important;padding:0!important;border:0!important;background:transparent!important}body.ui142-tab-projetos #cloudif-project-list .publication-manager-resource{display:contents!important}body.ui142-tab-projetos #cloudif-project-list .publication-information,body.ui142-tab-projetos #cloudif-project-list .publication-alias,body.ui142-tab-projetos #cloudif-project-list .publication-active-card,body.ui142-tab-projetos #cloudif-project-list .publication-versions,body.ui142-tab-projetos #cloudif-project-list .publication-manager-resource>.cm-actions{min-width:0!important;margin:0!important;padding:16px!important;border:1px solid var(--ui141-border)!important;border-radius:12px!important;background:var(--ui141-surface)!important}body.ui142-tab-projetos #cloudif-project-list .publication-information{grid-template-columns:repeat(2,minmax(0,1fr))!important}body.ui142-tab-projetos #cloudif-project-list .publication-alias{display:grid!important;align-content:start!important;gap:12px!important}body.ui142-tab-projetos #cloudif-project-list .publication-active-card,body.ui142-tab-projetos #cloudif-project-list .publication-manager-resource>.cm-actions{display:flex!important;align-items:center!important;justify-content:space-between!important;gap:10px!important;flex-wrap:wrap!important}body.ui142-tab-projetos #cloudif-project-list .publication-versions{grid-column:1/-1!important}@media(max-width:900px){body.ui142-tab-projetos #cloudif-project-list>.project-card>.project-line,body.ui142-tab-projetos #cloudif-project-list>.project-card>.project-line>div:nth-child(4){grid-template-columns:1fr!important}body.ui142-tab-projetos #cloudif-project-list .publication-versions{grid-column:auto!important}}\n</style><script id="cloudif-ui142-script">\n(function(){\n const titles={\n  projetos:[\'Projetos\',\'Crie, encontre e gerencie seus projetos sem misturar configurações avançadas.\'],\n  bancos:[\'Banco de dados\',\'Tenants Supabase, disponibilidade, permissões e operações de banco.\'],\n  publicacao:[\'Deploy\',\'Builds, versões, publicação, ativação e rollback em um único fluxo.\'],\n  git:[\'Código e infraestrutura\',\'Forgejo, repositórios, stacks e integração com Komodo.\'],\n  \'monitor-saude\':[\'Saúde da plataforma\',\'Visão rápida dos serviços e componentes essenciais.\'],\n  \'monitor-transacoes\':[\'Transações\',\'Acompanhe operações e eventos por projeto.\'],\n  \'monitor-promocoes\':[\'Deploys e rollbacks\',\'Histórico de promoções, ativações e reversões.\'],\n  \'monitor-filas\':[\'Filas\',\'Workers, retries, leases e dead-letter.\'],\n  \'monitor-telemetria\':[\'Telemetria\',\'Métricas e sinais operacionais consolidados.\'],\n  resumo:[\'Visão geral\',\'Resumo da plataforma e atalhos para as ações mais frequentes.\'],\n  \'admin-usuarios\':[\'Usuários e perfis\',\'Identidades, grupos e papéis administrativos.\']\n };\n const params=new URLSearchParams(location.search),tab=params.get(\'tab\')||\'resumo\';\n document.body.classList.add(\'ui142-tab-\'+tab);const legacyRoot=document.querySelector(\'.legacy-content\');if(legacyRoot)legacyRoot.classList.add(\'ui142-tab-\'+tab);\n const main=document.querySelector(\'main#conteudo-principal\');\n if(main && titles[tab]){\n  const section=document.createElement(\'section\');section.className=\'page-context\';\n  section.innerHTML=\'<div><h1>\'+titles[tab][0]+\'</h1><p>\'+titles[tab][1]+\'</p></div><span class="page-context-badge">CloudIF</span>\';\n  main.insertBefore(section,main.firstChild);\n }\n const admin=document.getElementById(\'admin-recursos-globais\');\n if(admin && admin.parentNode){\n  const d=document.createElement(\'details\');d.className=\'admin-global-disclosure\';\n  const sum=document.createElement(\'summary\');sum.innerHTML=\'<span><strong>Administração global</strong><br><small>Servidores Komodo e tenants Supabase</small></span>\';\n  admin.parentNode.insertBefore(d,admin);d.appendChild(sum);d.appendChild(admin);\n }\n if(tab===\'projetos\'){const banner=document.querySelector(\'.cm-page>.cm-banner\');if(banner)banner.remove();}\n const list=document.getElementById(\'cloudif-project-list\');\n if(list){\n  const cards=[...list.querySelectorAll(\':scope > .project-card\')];\n  const title=list.querySelector(\'.section-title\');\n  if(title){\n   const toolbar=document.createElement(\'div\');toolbar.className=\'project-toolbar\';\n   toolbar.innerHTML=\'<label class="project-search"><span class="sr-only">Buscar projeto</span><input type="search" id="project-filter" placeholder="Buscar por nome, slug ou descrição"></label><span class="project-count" id="project-count"></span><div class="view-toggle" aria-label="Densidade da lista"><button type="button" data-view="comfortable" class="active">Confortável</button><button type="button" data-view="compact">Compacta</button></div>\';\n   title.after(toolbar);\n   const input=toolbar.querySelector(\'#project-filter\'),count=toolbar.querySelector(\'#project-count\');\n   function filter(){const q=(input.value||\'\').toLowerCase().trim();let visible=0;cards.forEach(c=>{const hit=!q||c.textContent.toLowerCase().includes(q);c.hidden=!hit;if(hit)visible++;});count.textContent=visible+\' de \'+cards.length+\' projetos\';}\n   input.addEventListener(\'input\',filter);filter();\n   toolbar.querySelectorAll(\'[data-view]\').forEach(b=>b.addEventListener(\'click\',()=>{toolbar.querySelectorAll(\'[data-view]\').forEach(x=>x.classList.remove(\'active\'));b.classList.add(\'active\');list.classList.toggle(\'projects-compact\',b.dataset.view===\'compact\');localStorage.setItem(\'cloudif-project-view\',b.dataset.view);}));\n   const saved=localStorage.getItem(\'cloudif-project-view\');if(saved===\'compact\')toolbar.querySelector(\'[data-view="compact"]\').click();\n  }\n  cards.forEach(card=>{\n   const line=card.querySelector(\'.project-line\');if(!line||line.children.length<4)return;\n   const actions=line.children[3];\n   const d=document.createElement(\'details\');d.className=\'project-manage\';\n   const sum=document.createElement(\'summary\');sum.textContent=\'Gerenciar\';\n   const panel=document.createElement(\'div\');panel.className=\'project-manage-panel\';\n   while(actions.firstChild)panel.appendChild(actions.firstChild);\n   d.appendChild(sum);d.appendChild(panel);actions.appendChild(d);\n   d.addEventListener(\'toggle\',()=>{if(d.open)document.querySelectorAll(\'.project-manage[open]\').forEach(x=>{if(x!==d)x.open=false;});});\n  });\n  document.addEventListener(\'click\',e=>{if(!e.target.closest(\'.project-manage\'))document.querySelectorAll(\'.project-manage[open]\').forEach(x=>x.open=false);});\n }\n document.querySelectorAll(\'main details\').forEach(d=>{if(!d.classList.contains(\'system-menu\')&&!d.hasAttribute(\'data-keep-open\'))d.open=false;});\n})();\n</script>'
if 'page' in globals() and not globals().get('_ui142_wrapped'):
    _ui142_prev_page=page
    def page(user,tab,body):
        doc=_ui142_prev_page(user,tab,body)
        return doc.replace('</body>',_UI142_ASSETS+'</body>',1)
    _ui142_wrapped=True
# CloudIF human-centered UI END

# CloudIF modern navigation palette BEGIN
_UI143_CSS='<style id="cloudif-ui143">\n:root{--ui143-bg:#f6f7fb;--ui143-surface:#ffffff;--ui143-surface-soft:#f8fafc;--ui143-border:#e2e8f0;--ui143-text:#0f172a;--ui143-muted:#64748b;--ui143-primary:#2563eb;--ui143-primary-hover:#1d4ed8;--ui143-success:#16a34a;--ui143-warning:#d97706;--ui143-danger:#dc2626;--ui143-shadow:0 8px 24px rgba(15,23,42,.07)}\nbody{background:var(--ui143-bg)!important;color:var(--ui143-text)!important}.header{background:#fff!important;border-bottom:1px solid var(--ui143-border)!important;box-shadow:none!important}.header-inner{padding-block:10px!important}.brand-title h1{color:var(--ui143-text)!important}.brand-title p,.small,.cm-muted{color:var(--ui143-muted)!important}.inst-badge{background:#eff6ff!important;color:#1d4ed8!important;border-color:#bfdbfe!important}.ai-project-tag{background:#f5f3ff!important;color:#6d28d9!important;border-color:#ddd6fe!important}\n.wrap{margin-top:14px!important}.card,.box,.project-card,.cm-card,.admin-global-disclosure{background:#fff!important;border-color:var(--ui143-border)!important;box-shadow:var(--ui143-shadow)!important}.card,.box,.project-card,.cm-card{border-radius:14px!important}.userbar{background:#fff!important;border-color:var(--ui143-border)!important;box-shadow:none!important}\n.tabs.enterprise-nav.ui143-nav{top:72px!important;padding:5px!important;gap:4px!important;border:1px solid var(--ui143-border)!important;border-radius:12px!important;background:rgba(255,255,255,.96)!important;box-shadow:0 6px 18px rgba(15,23,42,.08)!important}.ui143-nav>a,.ui143-nav summary{min-height:36px!important;padding:7px 11px!important;border-radius:8px!important;font-size:.82rem!important;font-weight:650!important;color:#334155!important}.ui143-nav>a small,.ui143-nav>details>summary small,.ui143-nav>a .nav-icon,.ui143-nav>details>summary .primary-nav-icon{display:none!important}.ui143-nav>a:hover,.ui143-nav summary:hover{background:#f1f5f9!important;color:#0f172a!important}.ui143-nav>a.active,.ui143-nav details.active>summary{background:#eff6ff!important;color:#1d4ed8!important}.ui143-nav .logout-btn{margin-left:auto!important;min-height:34px!important;background:transparent!important;color:#64748b!important;border:0!important}.ui143-nav .logout-btn:hover{background:#fef2f2!important;color:#b91c1c!important}\n.enterprise-submenu{border:1px solid var(--ui143-border)!important;border-radius:12px!important;background:#fff!important;box-shadow:0 18px 40px rgba(15,23,42,.14)!important}.enterprise-submenu:not(.system-mega-menu){min-width:260px!important}.enterprise-submenu a{min-height:44px!important;padding:8px 10px!important;border-radius:8px!important}.enterprise-submenu a:hover{background:#f8fafc!important}.enterprise-submenu strong{font-size:.82rem!important;color:#0f172a!important}.enterprise-submenu small{font-size:.7rem!important;color:#64748b!important}.system-mega-menu{width:min(680px,calc(100vw - 32px))!important;padding:12px!important;gap:8px 12px!important}.system-menu-section h3{font-size:.67rem!important;color:#94a3b8!important;border-color:#e2e8f0!important;margin-bottom:5px!important}\n.page-context h1{font-size:clamp(1.35rem,2.4vw,1.8rem)!important;color:#0f172a!important}.page-context p{color:#64748b!important}.page-context-badge{background:#eff6ff!important;color:#1d4ed8!important;border-color:#bfdbfe!important}.project-toolbar{background:#fff!important;border-color:var(--ui143-border)!important;box-shadow:none!important}.project-search:before{color:#94a3b8!important}.view-toggle{background:#f1f5f9!important}.view-toggle button{color:#64748b!important}.view-toggle button.active{color:#1d4ed8!important;background:#fff!important}\n.btn,button,input[type="submit"]{border-radius:8px!important}.btn{background:var(--ui143-primary)!important}.btn:hover,button:hover,input[type="submit"]:hover{background:var(--ui143-primary-hover)!important;box-shadow:none!important}.btn.light{background:#eff6ff!important;color:#1d4ed8!important;border-color:#bfdbfe!important}.btn.gray{background:#f1f5f9!important;color:#475569!important;border-color:#e2e8f0!important}.btn.amber{background:var(--ui143-warning)!important}.btn.red{background:var(--ui143-danger)!important}.pill.ok,.ok{background:#f0fdf4!important;color:#15803d!important;border-color:#bbf7d0!important}.pill.warn,.warn{background:#fffbeb!important;color:#b45309!important;border-color:#fde68a!important}.pill.bad,.bad{background:#fef2f2!important;color:#b91c1c!important;border-color:#fecaca!important}.pill.info{background:#eff6ff!important;color:#1d4ed8!important;border-color:#bfdbfe!important}\ninput,select,textarea{border-color:#cbd5e1!important;background:#fff!important;color:#0f172a!important}.project-card:hover{border-color:#93c5fd!important;box-shadow:0 8px 22px rgba(37,99,235,.08)!important}.project-card .project-manage>summary{background:#f1f5f9!important;color:#334155!important}.project-card .project-manage[open]>summary{background:#eff6ff!important;color:#1d4ed8!important}.project-manage-panel{border-color:var(--ui143-border)!important;box-shadow:0 18px 42px rgba(15,23,42,.16)!important}\ntable{border-color:var(--ui143-border)!important}th{background:#f8fafc!important;color:#475569!important}.footer{border-color:var(--ui143-border)!important;color:#94a3b8!important}\n@media(max-width:700px){.tabs.enterprise-nav.ui143-nav{top:0!important;grid-template-columns:repeat(2,minmax(0,1fr))!important}.ui143-nav .logout-btn{margin-left:0!important}.system-mega-menu{padding:9px!important}.enterprise-submenu strong{font-size:.86rem!important}}\n</style>'
if 'page' in globals() and not globals().get('_ui143_wrapped'):
    _ui143_prev_page=page
    def page(user,tab,body):
        doc=_ui143_prev_page(user,tab,body)
        return doc.replace('</head>',_UI143_CSS+'</head>',1)
    _ui143_wrapped=True
# CloudIF modern navigation palette END

# CloudIF readable modern colors BEGIN
_UI144_CSS='<style id="cloudif-ui144">\n:root{\n --c-bg:#f7f8fc;--c-surface:#ffffff;--c-surface-2:#f1f5f9;--c-surface-3:#e8eef6;\n --c-text:#172033;--c-text-strong:#0f172a;--c-muted:#5d6b82;--c-faint:#8b98aa;\n --c-border:#dce3ed;--c-border-strong:#c7d2e0;\n --c-primary:#4f46e5;--c-primary-hover:#4338ca;--c-primary-soft:#eef2ff;--c-primary-border:#c7d2fe;\n --c-accent:#0891b2;--c-accent-soft:#ecfeff;\n --c-success:#15803d;--c-success-soft:#f0fdf4;--c-success-border:#bbf7d0;\n --c-warning:#b45309;--c-warning-soft:#fffbeb;--c-warning-border:#fde68a;\n --c-danger:#b91c1c;--c-danger-soft:#fef2f2;--c-danger-border:#fecaca;\n --c-info:#1d4ed8;--c-info-soft:#eff6ff;--c-info-border:#bfdbfe;\n --c-shadow-sm:0 1px 2px rgba(15,23,42,.05);--c-shadow:0 8px 22px rgba(15,23,42,.07);\n}\nhtml{color-scheme:light}body{background:var(--c-bg)!important;color:var(--c-text)!important}\n.header,.userbar,.card,.box,.project-card,.cm-card,.admin-global-disclosure,.project-toolbar,.enterprise-submenu,.project-manage-panel{background:var(--c-surface)!important;color:var(--c-text)!important;border-color:var(--c-border)!important}\n.header{box-shadow:var(--c-shadow-sm)!important}.card,.box,.project-card,.cm-card,.admin-global-disclosure{box-shadow:var(--c-shadow)!important}\nh1,h2,h3,h4,.brand-title h1{color:var(--c-text-strong)!important}.small,.cm-muted,.brand-title p,.page-context p,.project-count,.enterprise-submenu small,.system-menu-section h3,.footer{color:var(--c-muted)!important}\na{color:var(--c-primary)}a:hover{color:var(--c-primary-hover)}\n.tabs.enterprise-nav.ui143-nav{background:rgba(255,255,255,.97)!important;border-color:var(--c-border)!important;box-shadow:0 6px 20px rgba(15,23,42,.08)!important}\n.ui143-nav>a,.ui143-nav summary{color:#3f4c62!important}.ui143-nav>a:hover,.ui143-nav summary:hover{background:var(--c-surface-2)!important;color:var(--c-text-strong)!important}.ui143-nav>a.active,.ui143-nav details.active>summary{background:var(--c-primary-soft)!important;color:var(--c-primary)!important;box-shadow:inset 0 0 0 1px var(--c-primary-border)}\n.enterprise-submenu a:hover{background:var(--c-surface-2)!important}.enterprise-submenu strong{color:var(--c-text-strong)!important}.system-menu-section h3{border-color:var(--c-border)!important}\n.btn,button,input[type="submit"]{background:var(--c-primary)!important;color:#fff!important;border-color:transparent!important}.btn:hover,button:hover,input[type="submit"]:hover{background:var(--c-primary-hover)!important;color:#fff!important}.btn.light{background:var(--c-primary-soft)!important;color:var(--c-primary)!important;border-color:var(--c-primary-border)!important}.btn.gray{background:var(--c-surface-2)!important;color:#475569!important;border-color:var(--c-border)!important}.btn.blue{background:var(--c-info)!important}.btn.amber{background:var(--c-warning)!important}.btn.red{background:var(--c-danger)!important}.logout-btn{background:transparent!important;color:var(--c-muted)!important}.logout-btn:hover{background:var(--c-danger-soft)!important;color:var(--c-danger)!important}\ninput,select,textarea{background:var(--c-surface)!important;color:var(--c-text-strong)!important;border-color:var(--c-border-strong)!important}input::placeholder,textarea::placeholder{color:var(--c-faint)!important}input:focus,select:focus,textarea:focus{border-color:var(--c-primary)!important;outline:3px solid rgba(79,70,229,.14)!important}\n.project-toolbar,.view-toggle,.project-card .project-manage>summary{background:var(--c-surface-2)!important}.view-toggle button{background:transparent!important;color:var(--c-muted)!important}.view-toggle button.active{background:var(--c-surface)!important;color:var(--c-primary)!important;box-shadow:var(--c-shadow-sm)!important}.project-card:hover{border-color:#a5b4fc!important;box-shadow:0 10px 26px rgba(79,70,229,.09)!important}.project-card .project-manage[open]>summary{background:var(--c-primary-soft)!important;color:var(--c-primary)!important}\n.page-context-badge,.inst-badge{background:var(--c-primary-soft)!important;color:var(--c-primary)!important;border-color:var(--c-primary-border)!important}.ai-project-tag{background:var(--c-accent-soft)!important;color:#0e7490!important;border-color:#a5f3fc!important}\n.pill.ok,.ok{background:var(--c-success-soft)!important;color:var(--c-success)!important;border-color:var(--c-success-border)!important}.pill.warn,.warn{background:var(--c-warning-soft)!important;color:var(--c-warning)!important;border-color:var(--c-warning-border)!important}.pill.bad,.bad{background:var(--c-danger-soft)!important;color:var(--c-danger)!important;border-color:var(--c-danger-border)!important}.pill.info{background:var(--c-info-soft)!important;color:var(--c-info)!important;border-color:var(--c-info-border)!important}\ntable{border-color:var(--c-border)!important;background:var(--c-surface)!important}th{background:var(--c-surface-2)!important;color:#46546a!important;border-color:var(--c-border)!important}td{border-color:var(--c-border)!important}tr:hover td{background:#fafbff!important}\n.help,.ai-disclaimer{background:var(--c-info-soft)!important;color:#1e3a8a!important;border-color:var(--c-info-border)!important}.warn{background:var(--c-warning-soft)!important}.footer{border-color:var(--c-border)!important}\n@media(prefers-color-scheme:dark){\n html{color-scheme:dark}:root{--c-bg:#0d1320;--c-surface:#151d2b;--c-surface-2:#1d2737;--c-surface-3:#273347;--c-text:#dbe4f0;--c-text-strong:#f8fafc;--c-muted:#a3b0c2;--c-faint:#718096;--c-border:#2a3648;--c-border-strong:#3a485e;--c-primary:#818cf8;--c-primary-hover:#a5b4fc;--c-primary-soft:#252955;--c-primary-border:#4f46a5;--c-shadow-sm:0 1px 2px rgba(0,0,0,.22);--c-shadow:0 10px 28px rgba(0,0,0,.25)}\n body{background:var(--c-bg)!important}.tabs.enterprise-nav.ui143-nav{background:rgba(21,29,43,.97)!important}.ui143-nav>a,.ui143-nav summary{color:#c2cede!important}.ui143-nav>a:hover,.ui143-nav summary:hover{color:#fff!important}.ui143-nav>a.active,.ui143-nav details.active>summary{color:#c7d2fe!important}.enterprise-submenu strong{color:#f8fafc!important}.btn.light{color:#c7d2fe!important}.btn.gray{color:#dbe4f0!important}.project-card:hover{border-color:#6366f1!important;box-shadow:0 10px 28px rgba(0,0,0,.28)!important}.pill.ok,.ok{background:#12301f!important;color:#86efac!important;border-color:#166534!important}.pill.warn,.warn{background:#35230d!important;color:#fcd34d!important;border-color:#854d0e!important}.pill.bad,.bad{background:#351519!important;color:#fca5a5!important;border-color:#991b1b!important}.pill.info{background:#172554!important;color:#93c5fd!important;border-color:#1d4ed8!important}tr:hover td{background:#1a2434!important}.help,.ai-disclaimer{background:#172554!important;color:#bfdbfe!important;border-color:#1d4ed8!important}\n}\n@media(max-width:700px){.tabs.enterprise-nav.ui143-nav{background:var(--c-surface)!important}.project-toolbar{background:var(--c-surface)!important}}\n</style>'
if 'page' in globals() and not globals().get('_ui144_wrapped'):
    _ui144_prev_page=page
    def page(user,tab,body):
        doc=_ui144_prev_page(user,tab,body)
        return doc.replace('</head>',_UI144_CSS+'</head>',1)
    _ui144_wrapped=True
# CloudIF readable modern colors END


# CloudIF project 3x2 fallback layout BEGIN
_UI145_CSS=r'''<style id="cloudif-ui145">
body.ui142-tab-projetos #cloudif-project-list>.project-card{padding:18px!important;overflow:visible!important}
body.ui142-tab-projetos #cloudif-project-list>.project-card>.project-line{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:14px!important;align-items:start!important}
body.ui142-tab-projetos #cloudif-project-list>.project-card>.project-line>div{min-width:0!important;margin:0!important;padding:16px!important;border:1px solid var(--c-border,#dce3ed)!important;border-radius:12px!important;background:var(--c-surface,#fff)!important}
body.ui142-tab-projetos #cloudif-project-list>.project-card>.project-line>div:nth-child(-n+3){min-height:168px}
body.ui142-tab-projetos #cloudif-project-list>.project-card>.project-line>div:nth-child(4){display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:14px!important;padding:0!important;border:0!important;background:transparent!important}
body.ui142-tab-projetos #cloudif-project-list .publication-manager-resource{display:contents!important}
body.ui142-tab-projetos #cloudif-project-list .publication-information,
body.ui142-tab-projetos #cloudif-project-list .publication-alias,
body.ui142-tab-projetos #cloudif-project-list .publication-active-card,
body.ui142-tab-projetos #cloudif-project-list .publication-versions,
body.ui142-tab-projetos #cloudif-project-list .publication-manager-resource>.cm-actions{min-width:0!important;margin:0!important;padding:16px!important;border:1px solid var(--c-border,#dce3ed)!important;border-radius:12px!important;background:var(--c-surface,#fff)!important}
body.ui142-tab-projetos #cloudif-project-list .publication-information{grid-template-columns:repeat(2,minmax(0,1fr))!important}
body.ui142-tab-projetos #cloudif-project-list .publication-alias{display:grid!important;align-content:start!important;gap:12px!important}
body.ui142-tab-projetos #cloudif-project-list .publication-active-card,
body.ui142-tab-projetos #cloudif-project-list .publication-manager-resource>.cm-actions{display:flex!important;align-items:center!important;justify-content:space-between!important;gap:10px!important;flex-wrap:wrap!important}
body.ui142-tab-projetos #cloudif-project-list .publication-versions{grid-column:1/-1!important}
body.ui142-tab-projetos #cloudif-project-list>.project-card>.project-line>div:nth-child(4)>.btn{width:auto!important;justify-self:start!important}
@media(max-width:900px){body.ui142-tab-projetos #cloudif-project-list>.project-card>.project-line,body.ui142-tab-projetos #cloudif-project-list>.project-card>.project-line>div:nth-child(4){grid-template-columns:1fr!important}body.ui142-tab-projetos #cloudif-project-list .publication-versions{grid-column:auto!important}}
</style>'''
if 'page' in globals() and not globals().get('_ui145_wrapped'):
    _ui145_prev_page=page
    def page(user,tab,body):
        doc=_ui145_prev_page(user,tab,body)
        return doc.replace('</head>',_UI145_CSS+'</head>',1)
    _ui145_wrapped=True
# CloudIF project 3x2 fallback layout END

# CloudIF unique AGIA, monitoring and help routes BEGIN
import cloudif_unique_pages98 as _u98
if 'Portal' in globals() and not globals().get('_u98_wrapped'):
    _u98_prev_get=Portal.do_GET
    def _u98_get(self):
        parsed=urllib.parse.urlparse(self.path);path=parsed.path.rstrip('/');tab=(urllib.parse.parse_qs(parsed.query).get('tab') or [''])[0]
        if path in ('','/cloudiff/portal','/cloudif/portal'):
            mapping={
              'gestao-agentes':('gestao-agentes',_u98.agent_management),
              'documentacao-mcp':('documentacao-mcp',_u98.mcp_docs),
              'monitor-saude':('monitor-saude',lambda:_u98.monitor('saude')),
              'monitor-transacoes':('monitor-transacoes',lambda:_u98.monitor('transacoes')),
              'monitor-promocoes':('monitor-promocoes',lambda:_u98.monitor('promocoes')),
              'monitor-filas':('monitor-filas',lambda:_u98.monitor('filas')),
              'monitor-telemetria':('monitor-telemetria',lambda:_u98.monitor('telemetria')),
              'ajuda-token':('ajuda-token',lambda:_u98.help_page('token')),
              'ajuda-conectar':('ajuda-conectar',lambda:_u98.help_page('conectar')),
              'ajuda-aprovacoes':('ajuda-aprovacoes',lambda:_u98.help_page('aprovacoes')),
              'ajuda-ferramentas':('ajuda-ferramentas',lambda:_u98.help_page('ferramentas'))}
            if tab=='ajuda-conectar' and tab in mapping:
                key,fn=mapping[tab];return self.send_html(page(self.user(),key,fn()))
        return _u98_prev_get(self)
    Portal.do_GET=_u98_get;_u98_wrapped=True
# CloudIF unique AGIA, monitoring and help routes END

# CloudIF AGIA lifecycle API BEGIN
if 'Portal' in globals() and not globals().get('_agia99_wrapped'):
    _agia99_prev_get=Portal.do_GET
    def _agia99_get(self):
        parsed=urllib.parse.urlparse(self.path);path=parsed.path.rstrip('/')
        if path in ('/cloudiff/portal/api/agia-lifecycle','/cloudif/portal/api/agia-lifecycle','/api/agia-lifecycle'):
            try:
                src=json.load(open('/var/lib/cloudif/health/project-state-reconcile.json'))
                data={k:src.get(k) for k in ('ok','generated_at','last_success_at','changed','execution_mode','projects_count','projects_ready','agents_aligned','capabilities_aligned','catalog_tools','future_project_template','projects','tokens_rotated','tokens_returned','effects_executed','secrets_exposed')}
                data['ok']=data.get('ok') is True;data['secrets_exposed']=False;code=200 if data['ok'] else 503
            except Exception:data={'ok':False,'error':'agia_lifecycle_unavailable','secrets_exposed':False};code=503
            raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        return _agia99_prev_get(self)
    Portal.do_GET=_agia99_get;_agia99_wrapped=True
# CloudIF AGIA lifecycle API END


# CloudIF production operations read-only panel BEGIN
import cloudif_production_operations_panel as _ops128
if 'Portal' in globals() and not globals().get('_ops128_wrapped'):
    _ops128_prev_get=Portal.do_GET
    def _ops128_json(self,data,code=200):
        raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def _ops128_get(self):
        parsed=urllib.parse.urlparse(self.path);path=parsed.path.rstrip('/');tab=(urllib.parse.parse_qs(parsed.query).get('tab') or [''])[0]
        if path in ('','/cloudiff/portal','/cloudif/portal') and tab=='operacao-producao':
            user=self.user();slugs={x['slug'] for x in user_visible_projects(user['username'],user['groups'])}
            if 'atalhos-cloudif-iff1860746' not in slugs:return self.send_html(page(user,'operacao-producao','<section class="card"><h2>Operação de produção</h2><p class="pill bad">Projeto não autorizado.</p></section>'),403)
            return self.send_html(page(user,'operacao-producao',_ops128.render(user,_prod_csrf_token(user))))
        if path in ('/cloudiff/portal/api/production-operations','/cloudif/portal/api/production-operations','/api/production-operations'):
            user=self.user();slugs={x['slug'] for x in user_visible_projects(user['username'],user['groups'])}
            if 'atalhos-cloudif-iff1860746' not in slugs:return _ops128_json(self,{'ok':False,'error':'forbidden','secrets_exposed':False},403)
            try:return _ops128_json(self,_ops128.data(),200)
            except Exception:return _ops128_json(self,{'ok':False,'error':'production_operations_unavailable','secrets_exposed':False},503)
        return _ops128_prev_get(self)
    Portal.do_GET=_ops128_get;_ops128_wrapped=True
# CloudIF production operations read-only panel END

# CloudIF production operations safe actions BEGIN
import tempfile as _ops129_tempfile, hashlib as _ops129_hashlib, datetime as _ops129_dt
if 'Portal' in globals() and not globals().get('_ops129_post_wrapped'):
    _ops129_prev_post=Portal.do_POST
    def _ops129_atomic(path,obj):
        fd,tmp=_ops129_tempfile.mkstemp(prefix='production-targets.',dir='/etc/cloudif')
        with os.fdopen(fd,'w') as f:json.dump(obj,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    def _ops129_post(self):
        path=urllib.parse.urlparse(self.path).path.rstrip('/')
        actions={'/cloudiff/portal/action/production-window-schedule','/cloudif/portal/action/production-window-schedule','/cloudiff/portal/action/production-window-cancel','/cloudif/portal/action/production-window-cancel','/cloudiff/portal/action/production-alert-ack','/cloudif/portal/action/production-alert-ack'}
        if path not in actions:return _ops129_prev_post(self)
        if not _cloudif_security_valid_origin(self):return _cloudif_security_reject(self,'Origem da requisição não autorizada.')
        n=int(self.headers.get('Content-Length','0') or 0)
        if n<0 or n>200000:return _cloudif_security_reject(self,'Corpo da requisição inválido.',413)
        form=urllib.parse.parse_qs(self.rfile.read(n).decode('utf-8','ignore'));val=lambda k,d='':(form.get(k) or [d])[0].strip();user=self.user()
        if not _prod_csrf_equal(val('csrf_token'),_prod_csrf_token(user)):return _cloudif_security_reject(self,'Token CSRF inválido ou ausente.',403)
        if not user.get('admin'):return _cloudif_security_reject(self,'Restrito a administrador.',403)
        cfgpath='/etc/cloudif/production-targets.json';allcfg=json.load(open(cfgpath));cfg=allcfg['atalhos-cloudif-iff1860746']
        if path.endswith('production-window-schedule'):
            try:
                st=_ops129_dt.datetime.fromisoformat(val('start_at')).replace(tzinfo=_ops129_dt.timezone.utc);en=_ops129_dt.datetime.fromisoformat(val('end_at')).replace(tzinfo=_ops129_dt.timezone.utc);now=_ops129_dt.datetime.now(_ops129_dt.timezone.utc)
            except Exception:return _cloudif_security_reject(self,'Data ou hora inválida.',400)
            dur=int((en-st).total_seconds());owner=val('owner');esc=val('escalation')
            if st<now+_ops129_dt.timedelta(minutes=5) or dur<300 or dur>1800 or not owner or not esc:return _cloudif_security_reject(self,'A janela deve começar em pelo menos 5 minutos e durar entre 5 e 30 minutos.',400)
            w={'id':'window-'+st.strftime('%Y%m%dT%H%M%SZ'),'start_at':st.strftime('%Y-%m-%dT%H:%M:%SZ'),'end_at':en.strftime('%Y-%m-%dT%H:%M:%SZ'),'timezone':'UTC','max_duration_seconds':dur,'auto_reseal':True,'owner':owner[:100],'escalation':esc[:100],'status':'scheduled'}
            canon={k:w[k] for k in ('id','start_at','end_at','timezone','max_duration_seconds','auto_reseal','owner','escalation')};w['digest_sha256']=_ops129_hashlib.sha256(json.dumps(canon,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            cfg.update({'change_window':w,'change_window_open':False,'activation_allowed':False,'enabled':False,'production_effects_enabled':False,'change_owner':owner[:100],'change_escalation':esc[:100]});_ops129_atomic(cfgpath,allcfg);log_action(user['username'],'production_window_schedule','atalhos-cloudif-iff1860746',0,w['id']+' digest='+w['digest_sha256'],'')
        elif path.endswith('production-window-cancel'):
            w=cfg.get('change_window') or {};w['status']='cancelled';cfg.update({'change_window':w,'change_window_open':False,'activation_allowed':False,'enabled':False,'production_effects_enabled':False});_ops129_atomic(cfgpath,allcfg);log_action(user['username'],'production_window_cancel','atalhos-cloudif-iff1860746',0,str(w.get('id') or ''),'')
        else:
            aid=val('alert_id');comment=val('comment')
            if not aid or len(comment)<3 or len(comment)>300:return _cloudif_security_reject(self,'Alerta ou comentário inválido.',400)
            known=set()
            try:
                for line in open('/var/lib/cloudif/production-window-guard/alerts.jsonl'):
                    try:known.add(str(json.loads(line).get('alert_id')))
                    except Exception:pass
            except Exception:pass
            if aid not in known:return _cloudif_security_reject(self,'Alerta não encontrado.',404)
            ack={'at':int(time.time()),'alert_id':aid,'actor':user['username'],'comment':comment,'action':'acknowledged','secrets_exposed':False}
            with open('/var/lib/cloudif/production-window-guard/acknowledgements.jsonl','a') as f:f.write(json.dumps(ack,separators=(',',':'))+'\n')
            log_action(user['username'],'production_alert_ack',aid,0,comment,'')
        subprocess.run(['/usr/bin/systemctl','start','cloudif-production-window-guard.service'],timeout=30,check=False)
        return self.redirect('/?tab=operacao-producao')
    Portal.do_POST=_ops129_post;_ops129_post_wrapped=True
# CloudIF production operations safe actions END

# CloudIF incident lifecycle safe actions BEGIN
if 'Portal' in globals() and not globals().get('_ops130_post_wrapped'):
    _ops130_prev_post=Portal.do_POST
    def _ops130_post(self):
        path=urllib.parse.urlparse(self.path).path.rstrip('/')
        valid={'/cloudiff/portal/action/production-incident-assign','/cloudif/portal/action/production-incident-assign','/cloudiff/portal/action/production-incident-escalate','/cloudif/portal/action/production-incident-escalate','/cloudiff/portal/action/production-incident-mitigate','/cloudif/portal/action/production-incident-mitigate','/cloudiff/portal/action/production-incident-close','/cloudif/portal/action/production-incident-close'}
        if path not in valid:return _ops130_prev_post(self)
        if not _cloudif_security_valid_origin(self):return _cloudif_security_reject(self,'Origem da requisição não autorizada.')
        n=int(self.headers.get('Content-Length','0') or 0)
        if n<0 or n>200000:return _cloudif_security_reject(self,'Corpo da requisição inválido.',413)
        form=urllib.parse.parse_qs(self.rfile.read(n).decode('utf-8','ignore'));val=lambda k,d='':(form.get(k) or [d])[0].strip();user=self.user()
        if not _prod_csrf_equal(val('csrf_token'),_prod_csrf_token(user)):return _cloudif_security_reject(self,'Token CSRF inválido ou ausente.',403)
        if not user.get('admin'):return _cloudif_security_reject(self,'Restrito a administrador.',403)
        alert_id=val('alert_id');comment=val('comment');assignee=val('assignee')[:100]
        if not alert_id or len(comment)<3 or len(comment)>500:return _cloudif_security_reject(self,'Alerta ou comentário inválido.',400)
        known=set()
        try:
            for line in open('/var/lib/cloudif/production-window-guard/alerts.jsonl'):
                try:known.add(str(json.loads(line).get('alert_id')))
                except Exception:pass
        except Exception:pass
        if alert_id not in known:return _cloudif_security_reject(self,'Alerta não encontrado.',404)
        action=path.rsplit('-',1)[-1];status={'assign':'assigned','escalate':'escalated','mitigate':'mitigated','close':'closed'}[action]
        if action=='assign' and not assignee:return _cloudif_security_reject(self,'Responsável obrigatório.',400)
        event={'at':int(time.time()),'alert_id':alert_id,'actor':user['username'],'action':status,'status':status,'assignee':assignee or None,'comment':comment,'production_effects':False,'secrets_exposed':False}
        with open('/var/lib/cloudif/production-window-guard/incidents.jsonl','a') as f:f.write(json.dumps(event,separators=(',',':'))+'\n')
        log_action(user['username'],'production_incident_'+action,alert_id,0,(assignee+' ' if assignee else '')+comment,'')
        return self.redirect('/?tab=operacao-producao')
    Portal.do_POST=_ops130_post;_ops130_post_wrapped=True
# CloudIF incident lifecycle safe actions END

# CloudIF unified publication page BEGIN
import cloudif_publication_panel as _pub110
if 'Portal' in globals() and not globals().get('_pub110_wrapped'):
    _pub110_prev_get=Portal.do_GET
    def _pub110_json(self,data,code=200):
        raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def _pub110_get(self):
        parsed=urllib.parse.urlparse(self.path);path=parsed.path.rstrip('/');tab=(urllib.parse.parse_qs(parsed.query).get('tab') or [''])[0]
        if path in ('','/cloudiff/portal','/cloudif/portal') and tab=='publicacao':
            user=self.user();return self.send_html(page(user,'publicacao',_pub110.render(user_visible_projects(user['username'],user['groups']))))
        if path in ('/cloudiff/portal/api/publication','/cloudif/portal/api/publication','/api/publication'):
            try:
                user=self.user();data=_pub110.data(user_visible_projects(user['username'],user['groups']));code=200
            except Exception:data={'ok':False,'error':'publication_unavailable','secrets_exposed':False};code=503
            return _pub110_json(self,data,code)
        return _pub110_prev_get(self)
    Portal.do_GET=_pub110_get;_pub110_wrapped=True
# CloudIF unified publication page END

# CloudIF unified tenant/project action control BEGIN
if 'Portal' in globals() and not globals().get('_tenant_control134_wrapped'):
    _tenant_control134_prev_post=Portal.do_POST
    def _tenant_control134_post(self):
        path=urllib.parse.urlparse(self.path).path.rstrip('/')
        if path not in ('/cloudiff/portal/action/project_action','/cloudif/portal/action/project_action','/action/project_action','/project_action'):
            return _tenant_control134_prev_post(self)
        if not _cloudif_security_valid_origin(self):
            return _cloudif_security_reject(self,'Origem da requisição não autorizada.',403)
        length=int(self.headers.get('Content-Length','0') or 0)
        if length<0 or length>2_000_000:
            return _cloudif_security_reject(self,'Corpo da requisição inválido.',413)
        raw=self.rfile.read(length)
        try:form=urllib.parse.parse_qs(raw.decode('utf-8','ignore'))
        except Exception:return _cloudif_security_reject(self,'Formulário inválido.',400)
        val=lambda k,d='':(form.get(k) or [d])[0]
        user=self.user()
        if not _prod_csrf_equal(val('csrf_token'),_prod_csrf_token(user)):
            return _cloudif_security_reject(self,'Token CSRF inválido ou ausente.',403)
        action=val('action').strip() or val('op').strip();slug=val('slug').strip()
        groups={str(x).strip().lower() for x in (user.get('groups') or [])}
        global_admin=bool(user.get('admin') or groups.intersection({'cloudif-tenants-admin','cloudif-professor'}))
        if slug and action not in ('create_project','create'):
            visible={str(x['slug']) for x in user_visible_projects(user['username'],user['groups'])}
            if slug not in visible and not global_admin:
                return _cloudif_security_reject(self,'Projeto não autorizado para esta identidade.',403)
        import cloudif_project_action_safe as safe_project
        try:
            result=safe_project.handle_project_action(form,self.headers)
            if isinstance(result,str):
                return self.send_html(page(user,'projetos',result),200)
            target=str(result.get('slug') or slug);msg=str(result.get('message') or 'Projeto salvo.')
            log_action(user['username'],'project_action',target,0,json.dumps({'action':action,'global_admin':global_admin},separators=(',',':')),'')
            return self.redirect('/?tab=projetos&project='+urllib.parse.quote(target)+'&msg='+urllib.parse.quote(msg))
        except PermissionError as e:
            log_action(user['username'],'project_action',slug,1,'',str(e));return _cloudif_security_reject(self,str(e),403)
        except Exception as e:
            log_action(user['username'],'project_action',slug,1,'',type(e).__name__+': '+str(e));return self.redirect('/?tab=projetos&project='+urllib.parse.quote(slug)+'&msg='+urllib.parse.quote('Erro ao salvar projeto: '+str(e)))
    Portal.do_POST=_tenant_control134_post;_tenant_control134_wrapped=True
# CloudIF unified tenant/project action control END

# CloudIF unified administrative resource visibility BEGIN
if 'page' in globals() and not globals().get('_admin_resources139_wrapped'):
    _admin_resources139_prev_page=page
    def _admin_resources139_is_global(user):
        groups={str(x).strip().lower() for x in (user.get('groups') or [])}
        return bool(user.get('admin') or groups.intersection({'cloudif-tenants-admin','cloudif-professor'}))
    def _admin_resources139_panel(user):
        if not _admin_resources139_is_global(user): return ''
        tenants=[]
        try:
            for entry in sorted(os.listdir('/srv/cloudif/tenants')):
                base=os.path.join('/srv/cloudif/tenants',entry)
                if os.path.isdir(base) and os.path.isfile(os.path.join(base,'.env')) and re.match(r'^[a-z0-9][a-z0-9-]{1,62}$',entry):tenants.append(entry)
        except Exception: pass
        cards=''.join(
          '<article class="cm-resource"><div class="cm-resource-title"><strong>'+html.escape(t)+'</strong><span class="pill ok">Tenant</span></div>'
          '<p class="cm-muted">Studio, PostgreSQL, API e serviços do tenant.</p><div class="cm-actions">'
          '<a class="btn" target="_blank" rel="noopener" href="https://'+html.escape(t)+'.cloudiff.duckdns.org/project/default">Abrir Studio</a>'
          '<a class="btn light" target="_blank" rel="noopener" href="https://'+html.escape(t)+'.cloudiff.duckdns.org/">Abrir tenant</a></div></article>' for t in tenants)
        if not cards:cards='<p class="empty-state">Nenhum tenant provisionado.</p>'
        return ('<section class="cm-card" id="admin-recursos-globais"><div class="cm-resource-title"><div><h2>Administração global</h2>'
          '<p class="cm-muted">Visão consolidada para CloudIF-Tenants-Admin e CloudIF-Professor.</p></div><span class="pill ok">Acesso global</span></div>'
          '<div class="cm-actions admin-tool-shortcuts"><a class="btn" target="_blank" rel="noopener" href="https://komodoiff.duckdns.org/servers"><span aria-hidden="true">SV</span> Servidores</a>'
          '<a class="btn light" target="_blank" rel="noopener" href="https://komodoiff.duckdns.org/containers"><span aria-hidden="true">CT</span> Containers</a>'
          '<a class="btn light" href="#admin-tenants"><span aria-hidden="true">DB</span> Tenants</a>'
          '<a class="btn light" target="_blank" rel="noopener" href="https://cloudiff.duckdns.org/git/explore/repos"><span aria-hidden="true">GT</span> Repositórios</a></div>'
          '<h3 id="admin-tenants">Tenants Supabase</h3><div class="cm-grid">'+cards+'</div></section>')
    def page(user,tab,body):
        if tab=='admin-manutencao': body=_admin_resources139_panel(user)+body
        return _admin_resources139_prev_page(user,tab,body)
    _admin_resources139_wrapped=True
# CloudIF unified administrative resource visibility END

# CloudIF definitive project management renderer BEGIN
_PM197_CSS=r'''<style id="cloudif-project-management-final">
.project-management-final{display:grid;gap:18px}.project-management-final__head{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}.project-management-final__head h2{margin:0}.project-management-final__head p{margin:4px 0 0;color:var(--c-muted,var(--ui141-muted))}
.project-owner-final{margin:0!important;padding:0!important;border:0!important;background:transparent!important}.project-owner-final>summary{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 2px;color:var(--c-text-strong,#0f172a)!important}.project-owner-final__body{display:grid;gap:12px}
.project-final{margin:0!important;padding:0!important;border:1px solid var(--c-border,#dce3ed)!important;border-radius:14px!important;background:var(--c-surface,#fff)!important;overflow:hidden}.project-final>summary{list-style:none;display:flex;align-items:center;justify-content:space-between;gap:18px;padding:16px 18px;color:var(--c-text-strong,#0f172a)!important}.project-final>summary::-webkit-details-marker{display:none}.project-final>summary span{display:grid;gap:3px;min-width:0}.project-final>summary small{color:var(--c-muted,#64748b);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.project-final>summary em{font-style:normal;font-size:.78rem;font-weight:800;color:var(--c-primary,#4f46e5);white-space:nowrap}.project-final[open]>summary{border-bottom:1px solid var(--c-border,#dce3ed);background:var(--c-surface-2,#f1f5f9)}.project-final[open]>summary em{font-size:0}.project-final[open]>summary em:after{content:'Fechar projeto';font-size:.78rem}
.project-final__grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;padding:16px}.project-final__section{display:grid;align-content:start;gap:9px;min-width:0;padding:16px;border:1px solid var(--c-border,#dce3ed);border-radius:12px;background:var(--c-surface,#fff)}.project-final__section h3{margin:0;font-size:.92rem}.project-final__section p{margin:0}.project-final__meta{color:var(--c-muted,#64748b);font-size:.78rem;overflow-wrap:anywhere}.project-final__actions{display:flex;gap:8px;flex-wrap:wrap}.project-final__actions form{display:flex;gap:8px;flex-wrap:wrap;margin:0}.project-final__actions .btn{margin:0!important;width:auto!important}.project-final__status{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.project-final__status strong{font-size:.86rem}.project-management-final .cloudif-wizard{display:none}
@media(max-width:820px){.project-final__grid{grid-template-columns:1fr}.project-management-final__head{align-items:flex-start}.project-final>summary{align-items:flex-start}.project-final__actions,.project-final__actions form{display:grid;grid-template-columns:1fr;width:100%}.project-final__actions .btn{width:100%!important;text-align:center}}
</style>'''

def _pm197_owner(project):
    try:return _project_effective_owner(project)
    except Exception:
        try:return str(project['owner'] or project['created_by'] or '').strip()
        except Exception:return ''

def _pm197_render(user):
    rows=user_visible_projects(user['username'],user['groups']);tenants=visible_tenants(user['username'],user['groups'])
    tenant_opts='<option value="">Nenhum tenant vinculado</option>' if setting_bool('CLOUDIF_ALLOW_GIT_ONLY_PROJECT',True) else ''
    tenant_opts+=''.join(f'<option value="{h(t.get("tenant"))}">{h(t.get("tenant"))}</option>' for t in tenants)
    groups={};wizards=[]
    csrf_token=_prod_csrf_token(user) if '_prod_csrf_token' in globals() else ''
    import cloudif_project_acl_module as project_acl_module
    try:
        runtime_projects={item.get('slug'):item for item in _rd_projects(user)}
    except Exception:
        runtime_projects={}
    for p in rows:
        owner=_pm197_owner(p) or 'Sem usuário vinculado';slug=p['slug'];safe=re.sub(r'[^a-zA-Z0-9_]+','_',slug)
        forge_target=str(p['repo_url'] or '').strip()
        runtime_project=runtime_projects.get(slug) or {}
        terminal_target=url('/action/open-project-terminal')+'?slug='+urllib.parse.quote(slug,safe='') if runtime_project.get('stack_id') else ''
        studio=supabase_studio_url(p['tenant']) if p['tenant'] else ''
        acl_id='wiz_acl_'+safe
        bank_action=f'<a class="btn light" href="{h(studio)}" target="_blank" rel="noopener">Abrir Studio</a>' if studio else '<span class="project-final__meta">Sem Studio vinculado</span>'
        repo_action=f'<a class="btn light" href="{h(forge_target)}" target="_blank" rel="noopener">Abrir repositório</a>' if forge_target else '<span class="project-final__meta">Nenhum repositório vinculado</span>'
        terminal_action=f'<a class="btn light" href="{h(terminal_target)}" target="_blank" rel="noopener">Acessar SSH</a>' if terminal_target else '<span class="project-final__meta">SSH indisponível: projeto sem stack vinculado</span>'
        markup=f'''<details class="project-final" data-project-slug="{h(slug)}" data-project-owner="{h(owner)}"><summary><span><strong>{h(p['name'])}</strong><small>{h(slug)} · {h(p['description'] or 'Sem descrição')}</small></span><em>Abrir projeto</em></summary><div class="project-final__grid">
<section class="project-final__section"><h3>Projeto</h3><p><strong>{h(p['name'])}</strong></p><p class="project-final__meta">Slug: {h(slug)}</p><p>{h(p['description'] or 'Sem descrição.')}</p></section>
<section class="project-final__section"><h3>Banco vinculado</h3><p><strong>{h(p['tenant'] or 'Nenhum tenant vinculado')}</strong></p><div class="project-final__actions">{bank_action}</div></section>
<section class="project-final__section"><h3>Repositório Forge</h3><p><strong>Forgejo</strong></p><p class="project-final__meta">{h(forge_target)}</p><div class="project-final__actions">{repo_action}</div></section>
<section class="project-final__section"><h3>Komodo Publicação SSH</h3><p><strong>{'Stack '+h(runtime_project.get('stack_id')) if runtime_project.get('stack_id') else 'Container não vinculado'}</strong></p><p class="project-final__meta">Serviço: {h(runtime_project.get('service') or 'web')} · Status: {h(p['komodo_status'] or 'não configurado')}</p><div class="project-final__actions">{terminal_action}</div></section>
<section class="project-final__section"><h3>Estado técnico</h3><div class="project-final__status"><span class="pill {'ok' if p['tenant'] else 'muted'}">{'Banco vinculado' if p['tenant'] else 'Sem banco'}</span><span class="pill {'ok' if p['repo_url'] else 'muted'}">{'Repositório vinculado' if p['repo_url'] else 'Sem repositório'}</span></div><p class="project-final__meta">Use “Checar” para atualizar o estado real do projeto.</p></section>
<section class="project-final__section"><h3>Ações do projeto</h3><p class="project-final__meta"><strong>Checar projeto</strong> verifica repositório, banco e vínculo do container sem alterar a configuração. <strong>Permissões</strong> controla quem pode acessar este projeto.</p><div class="project-final__actions"><form method="post" action="{url('/action/project_action')}"><input type="hidden" name="csrf_token" value="{h(csrf_token)}"><input type="hidden" name="slug" value="{h(slug)}"><button class="btn gray" name="op" value="check">Checar projeto</button></form><button class="btn light" type="button" onclick="cloudifShowWizard('{acl_id}')">Gerenciar permissões</button></div></section>
</div></details>'''
        groups.setdefault(owner,[]).append(markup)
        acl_modal=project_acl_module.render_acl_modal(slug,user)
        acl_modal=acl_modal.replace('class="wizard"','class="wizard cloudif-wizard"',1)
        acl_modal=acl_modal.replace('<input type="hidden" name="op" value="add">','<input type="hidden" name="op" value="add"><input type="hidden" name="csrf_token" value="'+h(csrf_token)+'">',1)
        acl_modal=acl_modal.replace('<input type="hidden" name="op" value="remove">','<input type="hidden" name="op" value="remove"><input type="hidden" name="csrf_token" value="'+h(csrf_token)+'">')
        wizards.append(acl_modal)
    owner_html=[]
    for owner in sorted(groups,key=lambda x:(0 if x==user['username'] else 1,x.lower())):
        label='Meus projetos' if owner==user['username'] else f'Projetos de {owner}';items=groups[owner]
        owner_html.append(f'<details class="project-owner-final"'+(' open' if owner==user['username'] else '')+f'><summary><span>{h(label)}</span><small>{len(items)} projeto'+('' if len(items)==1 else 's')+f'</small></summary><div class="project-owner-final__body">{"".join(items)}</div></details>')
    return f'''{_PM197_CSS}<script>function cloudifShowWizard(id){{const list=document.getElementById('cloudif-project-list');if(list)list.hidden=true;document.querySelectorAll('.cloudif-wizard').forEach(x=>x.style.display='none');const target=document.getElementById(id);if(target){{target.style.display='block';target.scrollIntoView({{block:'start'}})}}}}function cloudifCancelWizard(){{document.querySelectorAll('.cloudif-wizard').forEach(x=>x.style.display='none');const list=document.getElementById('cloudif-project-list');if(list)list.hidden=false}}function cloudifHideWizard(id){{const target=document.getElementById(id);if(target)target.style.display='none';const list=document.getElementById('cloudif-project-list');if(list)list.hidden=false}}document.addEventListener('toggle',e=>{{const d=e.target;if(d.matches&&d.matches('.project-final[open]'))document.querySelectorAll('.project-final[open]').forEach(x=>{{if(x!==d)x.open=false}})}},true);</script>
<section id="cloudif-project-list" class="card project-management-final"><header class="project-management-final__head"><div><h2>Projetos por usuário</h2><p>Abra um projeto para consultar recursos e executar ações.</p></div><button class="btn" type="button" onclick="cloudifShowWizard('pm197_new')">Novo projeto</button></header>{''.join(owner_html) if owner_html else '<div class="box">Nenhum projeto visível.</div>'}</section>
<div id="pm197_new" class="wizard-panel cloudif-wizard"><div class="card"><h2>Novo projeto</h2><form method="post" action="{url('/action/create_project')}"><label>Nome do projeto</label><input name="name" required><label>Descrição</label><textarea name="description"></textarea><label>Banco/Tenant Supabase</label><select name="tenant">{tenant_opts}</select><button class="btn" type="submit">Criar projeto</button><button class="btn gray" type="button" onclick="cloudifCancelWizard()">Cancelar</button></form></div></div>{''.join(wizards)}'''

render_projects=_pm197_render
if 'page' in globals() and not globals().get('_pm197_page_wrapped'):
    _pm197_prev_page=page
    def page(user,tab,body):
        return _pm197_prev_page(user,tab,body).replace('</head>',_PM197_CSS+'</head>',1)
    _pm197_page_wrapped=True
# CloudIF definitive project management renderer END
# CloudIF definitive project route override BEGIN
if 'Portal' in globals() and not globals().get('_pm197_route_wrapped'):
    _pm197_prev_get=Portal.do_GET
    def _pm197_get(self):
        parsed=urllib.parse.urlparse(self.path)
        tab=(urllib.parse.parse_qs(parsed.query).get('tab') or [''])[0]
        if tab=='projetos' and parsed.path.rstrip('/') in ('','/cloudiff/portal','/cloudif/portal'):
            user=self.user()
            doc=page(user,'projetos',_pm197_render(user))
            if 'cloudif-project-management-final' not in doc:
                doc=doc.replace('</head>',_PM197_CSS+'</head>',1)
            return self.send_html(doc)
        return _pm197_prev_get(self)
    Portal.do_GET=_pm197_get
    _pm197_route_wrapped=True
# CloudIF definitive project route override END

if __name__ == "__main__":
    init_db()
    refresh_tenant_policies()
    print(f"CloudIF Portal v17 clean listening on {HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Portal).serve_forever()
