#!/usr/bin/env python3
import html
import json
import os
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

DB = os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db")
PUBLIC_HOST = os.environ.get("CLOUDIF_PUBLIC_HOST", "cloudiff.duckdns.org")

DEFAULT_PROJECT = os.environ.get("CLOUDIF_DEFAULT_PROJECT", "sistema-de-biblioteca-teste")
DEFAULT_TENANT = os.environ.get("CLOUDIF_DEFAULT_TENANT", "iff1742962")

FORJA_ENV = "/etc/cloudif/forja-agent-client.env"
KOMODO_ENV = "/etc/cloudif/komodo-agent-client.env"
PORTAL_ENV = "/etc/cloudif/portal.env"

PROJECT_INTEGRATE = "/srv/cloudif/bin/cloudif-project-integrate.sh"

def h(x):
    return html.escape("" if x is None else str(x))

def read_env(path):
    data = {}
    try:
        for line in Path(path).read_text(errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    except Exception:
        pass
    return data

def refresh_public_host():
    global PUBLIC_HOST
    env = read_env(PORTAL_ENV)
    PUBLIC_HOST = env.get("CLOUDIF_PUBLIC_HOST", PUBLIC_HOST)

def db_rows(sql, params=()):
    try:
        con = sqlite3.connect(DB, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=15000")
        rows = [dict(r) for r in con.execute(sql, params).fetchall()]
        con.close()
        return rows
    except Exception:
        return []

def db_exec(sql, params=()):
    con = sqlite3.connect(DB, timeout=20)
    con.execute("PRAGMA busy_timeout=20000")
    cur = con.cursor()
    cur.execute(sql, params)
    con.commit()
    con.close()

def table_cols(table):
    try:
        con = sqlite3.connect(DB, timeout=10)
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
        con.close()
        return cols
    except Exception:
        return []

def discover_projects():
    queries = [
        "SELECT slug, name, tenant, repo_url, komodo_status FROM projects ORDER BY updated_at DESC LIMIT 100",
        "SELECT slug, title AS name, tenant, repo_url, komodo_status FROM projects ORDER BY updated_at DESC LIMIT 100",
        "SELECT slug, name, tenant, repo_url FROM projects ORDER BY slug LIMIT 100",
        "SELECT slug, name FROM projects ORDER BY slug LIMIT 100",
    ]
    for q in queries:
        rows = db_rows(q)
        if rows:
            return rows
    return []

def discover_tenants():
    queries = [
        "SELECT tenant, kong_http_port, always_alive, enabled FROM tenants ORDER BY tenant",
        "SELECT name AS tenant, kong_http_port, always_alive, enabled FROM tenants ORDER BY name",
        "SELECT slug AS tenant, kong_http_port, always_alive, enabled FROM tenants ORDER BY slug",
    ]
    for q in queries:
        rows = db_rows(q)
        if rows:
            return rows

    base = Path("/srv/cloudif/tenants")
    out = []
    if base.exists():
        for d in sorted(base.iterdir()):
            if d.is_dir():
                out.append({
                    "tenant": d.name,
                    "kong_http_port": "",
                    "always_alive": "",
                    "enabled": "",
                })
    return out

def run_cmd(cmd, timeout=180):
    try:
        p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        return {
            "ok": p.returncode == 0,
            "rc": p.returncode,
            "stdout": p.stdout[-12000:],
            "stderr": p.stderr[-12000:],
        }
    except Exception as e:
        return {"ok": False, "rc": 999, "stdout": "", "stderr": str(e)}

def http_json(url, method="GET", payload=None, token="", timeout=7):
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "CloudIF-Portal-Integracoes-v60",
    }

    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = "Bearer " + token

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

def agent_urls():
    fe = read_env(FORJA_ENV)
    ke = read_env(KOMODO_ENV)

    return {
        "forja_url": fe.get("FORJA_AGENT_URL", "http://10.62.91.2:18095").rstrip("/"),
        "forja_token": fe.get("FORJA_AGENT_TOKEN", ""),
        "komodo_url": ke.get("KOMODO_AGENT_URL", "http://10.62.91.2:18098").rstrip("/"),
        "komodo_token": ke.get("KOMODO_AGENT_TOKEN", ""),
    }

def status_forja():
    a = agent_urls()
    health = http_json(a["forja_url"] + "/health", token=a["forja_token"], timeout=5)
    status = http_json(a["forja_url"] + "/status", token=a["forja_token"], timeout=7)
    return health, status

def status_komodo():
    a = agent_urls()
    health = http_json(a["komodo_url"] + "/health", token=a["komodo_token"], timeout=5)
    status = http_json(a["komodo_url"] + "/status", token=a["komodo_token"], timeout=7)
    return health, status

def ok_any(*items):
    return any(bool(x.get("ok")) for x in items if isinstance(x, dict))

def infer_project_tenant(project, fallback_tenant=""):
    if fallback_tenant:
        return fallback_tenant

    for p in discover_projects():
        if p.get("slug") == project:
            return p.get("tenant") or ""

    return ""

def first_project():
    projects = discover_projects()
    if projects:
        return projects[0].get("slug") or DEFAULT_PROJECT
    return DEFAULT_PROJECT

def public_deploy_url(project, tenant):
    return (
        "/cloudiff/portal/deploy/"
        + "?project=" + urllib.parse.quote(project or "")
        + "&tenant=" + urllib.parse.quote(tenant or "")
    )

def public_supabase_studio_url(tenant):
    return f"https://{tenant}.{PUBLIC_HOST}/project/default"

def project_has_db(project):
    tenant = infer_project_tenant(project, "")
    return bool(tenant), tenant

def project_has_git(project_row):
    repo = project_row.get("repo_url") or ""
    return bool(repo), repo

def project_has_komodo(project_row):
    status = project_row.get("komodo_status") or ""
    repo = project_row.get("repo_url") or ""
    return bool(status and status != "-") or bool(repo), status or "-"

def css():
    return """
<style>
:root{
  --ci-green:#168821;
  --ci-green-dark:#0b6418;
  --ci-green-soft:#eef8f0;
  --ci-bg:#f7faf8;
  --ci-card:#ffffff;
  --ci-border:#d9e2dd;
  --ci-text:#1f2937;
  --ci-muted:#667085;
  --ci-disabled-bg:#f2f4f7;
  --ci-disabled-text:#8a94a6;
  --ci-danger:#b42318;
}
.ci-page{
  display:block;
}
.ci-hero{
  background:linear-gradient(180deg,#fff,#f7fbf8);
  border:1px solid var(--ci-border);
  border-radius:18px;
  padding:22px;
  margin-bottom:16px;
}
.ci-hero h2{
  margin:0;
  font-size:26px;
  color:var(--ci-text);
}
.ci-hero p{
  color:var(--ci-muted);
  margin:8px 0 0;
}
.ci-toolbar{
  display:flex;
  flex-wrap:wrap;
  gap:8px;
  margin-top:14px;
}
.ci-btn{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  gap:6px;
  padding:9px 12px;
  border-radius:10px;
  font-weight:700;
  font-size:14px;
  text-decoration:none !important;
  border:1px solid transparent;
  margin:3px;
  min-height:38px;
  cursor:pointer;
}
.ci-btn-primary{
  background:var(--ci-green);
  color:white !important;
  border-color:var(--ci-green);
}
.ci-btn-secondary{
  background:#fff;
  color:var(--ci-green-dark) !important;
  border-color:var(--ci-border);
}
.ci-btn-disabled{
  background:var(--ci-disabled-bg);
  color:var(--ci-disabled-text) !important;
  border-color:#e5e7eb;
  cursor:not-allowed;
}
.ci-btn-danger{
  background:#fff;
  color:var(--ci-danger) !important;
  border-color:#f2d3d0;
}
.ci-pill{
  display:inline-flex;
  align-items:center;
  border-radius:999px;
  padding:5px 10px;
  font-size:12px;
  font-weight:800;
}
.ci-pill-ok{
  background:var(--ci-green-soft);
  color:var(--ci-green-dark);
}
.ci-pill-off{
  background:var(--ci-disabled-bg);
  color:var(--ci-muted);
}
.ci-section{
  border:1px solid var(--ci-border);
  border-radius:18px;
  background:#fff;
  padding:18px;
  margin:16px 0;
}
.ci-section h3{
  margin:0 0 8px;
  font-size:20px;
}
.ci-muted{
  color:var(--ci-muted);
  font-size:14px;
}
.ci-card-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(330px,1fr));
  gap:16px;
}
.ci-project-card{
  background:#fff;
  border:1px solid var(--ci-border);
  border-radius:18px;
  box-shadow:0 8px 20px rgba(20,40,20,.04);
  padding:16px;
  position:relative;
  overflow:hidden;
}
.ci-project-card h4{
  margin:0;
  font-size:18px;
  color:var(--ci-text);
}
.ci-card-top{
  display:flex;
  justify-content:space-between;
  gap:10px;
  align-items:start;
}
.ci-menu{
  position:relative;
}
.ci-menu summary{
  list-style:none;
  cursor:pointer;
  border:1px solid var(--ci-border);
  border-radius:10px;
  padding:6px 10px;
  color:var(--ci-muted);
  background:#fff;
  font-weight:800;
}
.ci-menu summary::-webkit-details-marker{display:none}
.ci-menu-body{
  position:absolute;
  right:0;
  top:38px;
  background:#fff;
  border:1px solid var(--ci-border);
  border-radius:12px;
  box-shadow:0 12px 24px rgba(0,0,0,.12);
  padding:8px;
  z-index:5;
  min-width:220px;
}
.ci-menu-body a,
.ci-menu-body button{
  display:block;
  width:100%;
  text-align:left;
  background:#fff;
  border:0;
  padding:9px;
  border-radius:8px;
  color:var(--ci-text);
  text-decoration:none;
  cursor:pointer;
}
.ci-menu-body a:hover,
.ci-menu-body button:hover{
  background:#f5faf6;
}
.ci-resource{
  border-top:1px solid var(--ci-border);
  padding-top:12px;
  margin-top:12px;
}
.ci-resource-title{
  display:flex;
  justify-content:space-between;
  gap:8px;
  align-items:center;
}
.ci-actions{
  display:flex;
  gap:6px;
  flex-wrap:wrap;
  margin-top:10px;
}
.ci-wizard-steps{
  display:grid;
  grid-template-columns:repeat(3,1fr);
  gap:8px;
  margin:14px 0;
}
@media(max-width:900px){
  .ci-wizard-steps{grid-template-columns:1fr}
}
.ci-step{
  border:1px solid var(--ci-border);
  border-radius:14px;
  background:#fff;
  padding:12px;
}
.ci-step strong{
  display:block;
  color:var(--ci-green-dark);
}
.ci-step small{
  color:var(--ci-muted);
}
.ci-modal{
  display:none;
  position:fixed;
  inset:0;
  background:rgba(15,23,42,.45);
  z-index:9999;
  padding:30px;
  overflow:auto;
}
.ci-modal:target{
  display:block;
}
.ci-modal-card{
  max-width:820px;
  margin:30px auto;
  background:#fff;
  border-radius:20px;
  border:1px solid var(--ci-border);
  box-shadow:0 24px 60px rgba(0,0,0,.25);
  padding:22px;
}
.ci-modal-head{
  display:flex;
  justify-content:space-between;
  gap:12px;
  align-items:start;
}
.ci-close{
  text-decoration:none;
  font-size:24px;
  color:var(--ci-muted);
}
.ci-field{
  margin:12px 0;
}
.ci-field label{
  display:block;
  font-weight:800;
  margin-bottom:5px;
}
.ci-field input,
.ci-field textarea,
.ci-field select{
  width:100%;
  padding:10px;
  border:1px solid var(--ci-border);
  border-radius:10px;
}
.ci-choice-grid{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
  gap:12px;
}
.ci-choice{
  border:1px solid var(--ci-border);
  border-radius:16px;
  padding:16px;
  background:#fff;
}
.ci-choice h4{
  margin:0 0 8px;
}
.ci-table{
  width:100%;
  border-collapse:collapse;
}
.ci-table th,
.ci-table td{
  border-bottom:1px solid var(--ci-border);
  padding:10px;
  text-align:left;
}
.ci-table th{
  background:#f5faf6;
  color:var(--ci-green-dark);
}
.ci-inline-form{
  display:inline;
}
.ci-inline-form button{
  border:0;
}

/* CloudIF v135b3 */
.ci-menu-danger{
  color:#991b1b !important;
  background:#fff5f5 !important;
  border:0;
  width:100%;
  text-align:left;
  cursor:pointer;
}
.ci-menu-danger:hover{
  background:#fee2e2 !important;
}


/* CloudIF v136b1-safe — limpeza visual Git + Komodo */
.cm-banner,
.ci-hero {
  display: none !important;
}

/* Oculta seção Novo Projeto/fluxo guiado na aba Git + Komodo */
.ci-section:has(.ci-step-grid),
.ci-section:has(.ci-step-card) {
  display: none !important;
}

.ci-menu-body a[href*="tab=git"][href*="project="] {
  display: none !important;
}


/* CloudIF v137a-safe — camada empresarial */
.enterprise-panel,
.cm-section,
.ci-section,
.project-card,
.cm-card,
.ci-project-card {
  box-shadow: 0 8px 24px rgba(16,24,40,.06);
}

.cm-section-head,
.ci-card-top,
.cm-card-head,
.project-line {
  border-bottom: 1px solid rgba(223,232,221,.75);
  padding-bottom: 12px;
  margin-bottom: 12px;
}

.ci-actions,
.cm-actions,
.enterprise-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.ci-btn,
.cm-btn,
.btn {
  font-weight: 700;
  letter-spacing: .01em;
}

.ci-btn-primary,
.btn.blue,
.cm-primary {
  background: #168821 !important;
  color: #fff !important;
  border-color: #168821 !important;
}

.ci-btn-secondary,
.btn.light,
.cm-secondary {
  background: #fff !important;
  color: #1f2937 !important;
  border: 1px solid #d9e2dd !important;
}

.ci-menu-body,
.cm-menu-body {
  box-shadow: 0 12px 30px rgba(16,24,40,.16);
  border: 1px solid #d9e2dd;
}

.ci-menu-item,
.ci-menu-body a {
  display: block;
  width: 100%;
  padding: 9px 10px;
  border-radius: 8px;
  text-align: left;
  background: transparent;
  border: 0;
  color: #1f2937;
  text-decoration: none;
  font-weight: 700;
}

.ci-menu-item:hover,
.ci-menu-body a:hover {
  background: #eef8f0;
}

.ci-menu-danger {
  color: #b42318 !important;
  background: #fff5f5 !important;
}

.ci-resource,
.enterprise-resource {
  border: 1px solid #d9e2dd;
  border-radius: 14px;
  background: #fbfdfb;
  padding: 12px;
  margin-top: 12px;
}

.pill,
.ci-pill {
  font-weight: 800;
}

.cm-grid,
.ci-card-grid {
  align-items: stretch;
}

.cm-card,
.ci-project-card {
  min-height: 100%;
}

/* Ocultação mantida da limpeza v136 */
.cm-banner,
.ci-hero,
.ci-section:has(.ci-step-grid),
.ci-section:has(.ci-step-card) {
  display: none !important;
}


/* CloudIF v137b-safe — Design empresarial moderno */
:root{
  --cloudif-surface:#ffffff;
  --cloudif-surface-2:#f8faf8;
  --cloudif-soft:#eef8f0;
  --cloudif-soft-2:#f3f7f4;
  --cloudif-line:#d9e5dc;
  --cloudif-text:#1f2933;
  --cloudif-muted:#647067;
  --cloudif-brand:#168821;
  --cloudif-brand-2:#0f6f1a;
  --cloudif-danger:#b42318;
  --cloudif-warning:#b45309;
  --cloudif-blue:#1d4ed8;
  --cloudif-shadow:0 14px 38px rgba(16,24,40,.08);
  --cloudif-shadow-soft:0 8px 24px rgba(16,24,40,.055);
  --cloudif-radius:18px;
  --cloudif-radius-sm:12px;
}

/* Fundo e respiro geral */
body{
  background:
    radial-gradient(circle at top left, rgba(22,136,33,.08), transparent 32rem),
    linear-gradient(180deg,#f7faf7 0%,#eef4ef 100%) !important;
  color:var(--cloudif-text) !important;
}

.content,
.main,
.cm-page,
.ci-page{
  max-width:1420px;
}

/* Topo mais limpo */
.header{
  background:rgba(255,255,255,.94) !important;
  backdrop-filter: blur(10px);
  box-shadow:0 10px 30px rgba(16,24,40,.06);
  border-bottom:1px solid rgba(22,136,33,.22) !important;
}

.brand-title,
.brand h1{
  letter-spacing:-.03em;
}

/* Abas com aparência de produto */
.tabs{
  display:flex;
  gap:8px;
  flex-wrap:wrap;
  background:rgba(255,255,255,.72);
  border:1px solid var(--cloudif-line);
  border-radius:18px;
  padding:8px;
  box-shadow:var(--cloudif-shadow-soft);
}

.tabs a{
  border-radius:13px !important;
  border:0 !important;
  color:#304138 !important;
  font-weight:800;
  transition:.18s ease;
}

.tabs a:hover{
  background:var(--cloudif-soft) !important;
  transform:translateY(-1px);
}

.tabs a.active{
  background:linear-gradient(135deg,var(--cloudif-brand),var(--cloudif-brand-2)) !important;
  color:white !important;
  box-shadow:0 10px 24px rgba(22,136,33,.24);
}

/* Cards e seções */
.card,
.cm-card,
.ci-project-card,
.project-card,
.cm-section,
.ci-section,
.enterprise-panel{
  border:1px solid rgba(217,229,220,.92) !important;
  border-radius:var(--cloudif-radius) !important;
  background:rgba(255,255,255,.94) !important;
  box-shadow:var(--cloudif-shadow-soft) !important;
}

.card:hover,
.cm-card:hover,
.ci-project-card:hover,
.project-card:hover{
  box-shadow:var(--cloudif-shadow) !important;
  transform:translateY(-1px);
  transition:.18s ease;
}

.cm-card,
.ci-project-card,
.project-card{
  padding:18px !important;
}

.cm-card-head,
.ci-card-top,
.project-line,
.cm-section-head{
  border-bottom:1px solid rgba(217,229,220,.88);
  padding-bottom:12px;
  margin-bottom:14px;
}

/* Grid moderno */
.cm-grid,
.ci-card-grid,
.grid{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(320px,1fr));
  gap:16px;
  align-items:stretch;
}

/* Texto e metadados */
.small,
.ci-muted,
.cm-muted{
  color:var(--cloudif-muted) !important;
  line-height:1.45;
}

code{
  background:#f1f6f2;
  border:1px solid #dce9df;
  border-radius:8px;
  padding:2px 6px;
}

/* Badges */
.pill,
.ci-pill,
.badge{
  display:inline-flex;
  align-items:center;
  gap:6px;
  border-radius:999px !important;
  padding:6px 10px !important;
  font-size:.78rem;
  font-weight:900 !important;
  border:1px solid #dce9df;
  background:#f7fbf8;
  color:#31533a;
}

.pill.ok,
.ci-pill.ok,
.badge.ok{
  background:#e8f8eb !important;
  color:#0f6f1a !important;
  border-color:#bde8c5 !important;
}

/* Botões */
.btn,
.ci-btn,
.cm-btn,
button.btn{
  border-radius:12px !important;
  padding:9px 13px !important;
  font-weight:850 !important;
  letter-spacing:.005em;
  border:1px solid var(--cloudif-line) !important;
  transition:.16s ease;
  text-decoration:none !important;
}

.btn:hover,
.ci-btn:hover,
.cm-btn:hover,
button.btn:hover{
  transform:translateY(-1px);
  box-shadow:0 10px 22px rgba(16,24,40,.10);
}

.ci-btn-primary,
.btn.blue,
.cm-primary,
button[name="op"][value="publish_site"],
button[name="action"][value="publish_site"]{
  background:linear-gradient(135deg,var(--cloudif-brand),var(--cloudif-brand-2)) !important;
  color:white !important;
  border-color:transparent !important;
}

.ci-btn-secondary,
.btn.light,
.cm-secondary{
  background:white !important;
  color:#20312a !important;
}

.btn.gray,
.ci-btn.gray{
  background:#f4f7f5 !important;
  color:#33443a !important;
}

.btn.amber{
  background:#fff7ed !important;
  color:#9a3412 !important;
  border-color:#fed7aa !important;
}

/* Menus */
.ci-menu-body,
.cm-menu-body{
  border:1px solid var(--cloudif-line) !important;
  border-radius:14px !important;
  background:white !important;
  box-shadow:0 18px 45px rgba(16,24,40,.16) !important;
  padding:8px !important;
}

.ci-menu-body a,
.ci-menu-item{
  display:block !important;
  width:100% !important;
  border:0 !important;
  border-radius:10px !important;
  background:transparent !important;
  color:#20312a !important;
  font-weight:800 !important;
  padding:10px 12px !important;
  text-align:left !important;
  text-decoration:none !important;
  cursor:pointer;
}

.ci-menu-body a:hover,
.ci-menu-item:hover{
  background:var(--cloudif-soft) !important;
}

.ci-menu-danger{
  color:var(--cloudif-danger) !important;
  background:#fff5f5 !important;
}

/* Formulários */
input,
select,
textarea{
  border:1px solid var(--cloudif-line) !important;
  border-radius:12px !important;
  background:white !important;
}

select{
  padding:8px 10px !important;
}

/* Área de ações */
.cm-actions,
.ci-actions,
.enterprise-actions{
  display:flex !important;
  flex-wrap:wrap !important;
  gap:8px !important;
  align-items:center !important;
  padding-top:12px;
  border-top:1px solid rgba(217,229,220,.7);
}

/* Bancos/Tenants mais amigável */
.cm-page .cm-section{
  padding:22px !important;
}

.cm-page .cm-section-head h2{
  margin:0 0 4px 0;
  letter-spacing:-.02em;
}

.cm-page .cm-card h3{
  margin:0;
  font-size:1.14rem;
  letter-spacing:-.015em;
}

.cm-page .cm-card .small strong{
  color:#26352d;
}

.cm-page .cm-card form{
  margin-top:12px !important;
}

/* Remove/oculta blocos redundantes da aba Git + Komodo */
.cm-banner,
.ci-hero,
.ci-section:has(.ci-step-grid),
.ci-section:has(.ci-step-card),
.ci-section:has(input[name="name"]):has(input[name="slug"]),
.ci-section:has(form[action*="project_action"]):has(input[name="setup_git"]) {
  display:none !important;
}

.ci-menu-body a[href*="tab=git"][href*="project="]{
  display:none !important;
}

/* Remove qualquer resíduo de containers */
p:has(> .cloudif-containers-line),
.cloudif-containers-line{
  display:none !important;
}


</style>
"""

def pill(ok, ok_text="OK", bad_text="Indisponível"):
    return f'<span class="ci-pill {"ci-pill-ok" if ok else "ci-pill-off"}">{h(ok_text if ok else bad_text)}</span>'

def btn(label, href="", enabled=True, primary=True, target=False):
    if not enabled:
        return f'<span class="ci-btn ci-btn-disabled">{h(label)}</span>'
    cls = "ci-btn-primary" if primary else "ci-btn-secondary"
    target_attr = ' target="_blank" rel="noopener noreferrer"' if target else ""
    return f'<a class="ci-btn {cls}" href="{h(href)}"{target_attr}>{h(label)}</a>'

def form_btn(label, action, project, tenant, enabled=True, primary=True):
    if not enabled:
        return f'<span class="ci-btn ci-btn-disabled">{h(label)}</span>'

    cls = "ci-btn-primary" if primary else "ci-btn-secondary"
    return f"""
<style>
</style>
<script>
</script>

<script>
</script>


<script>
</script>


<form method="post" action="/cloudiff/portal/action/project_action" class="ci-inline-form">
  <input type="hidden" name="action" value="{h(action)}">
  <input type="hidden" name="project" value="{h(project)}">
  <input type="hidden" name="tenant" value="{h(tenant)}">
  <button class="ci-btn {cls}" type="submit">{h(label)}</button>
</form>
"""



# CloudIF v133 - integração Portal <-> Komodo Agent v132

def _v133_h(x):
    try:
        return h(x)
    except Exception:
        return html.escape(str(x if x is not None else ""))

def _v133_slug_from_form(form):
    for key in ["slug", "project_slug", "project", "name"]:
        try:
            v = form.getvalue(key) if hasattr(form, "getvalue") else form.get(key)
        except Exception:
            v = None
        if v:
            return str(v).strip()
    return ""

def _v133_actor_from_form(form, actor="portal"):
    return actor or "portal"

def _v133_komodo_agent():
    try:
        a = agents()
        return (a.get("komodo_url") or "http://10.62.91.2:18098").rstrip("/"), a.get("komodo_token") or ""
    except Exception:
        return "http://10.62.91.2:18098", ""

def _v133_http_json(method, url, payload=None, token="", timeout=90):
    headers = {
        "Accept": "application/json",
    }

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    # Komodo Agent atual aceita sem token em alguns endpoints, mas preservamos compatibilidade.
    if token:
        headers["X-CloudIF-Token"] = token
        headers["Authorization"] = "Bearer " + token

    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {"raw": raw}
            return {
                "ok": 200 <= r.status < 300,
                "status": r.status,
                "url": url,
                "data": body,
            }
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            body = {"raw": raw}
        return {
            "ok": False,
            "status": e.code,
            "url": url,
            "data": body,
        }
    except Exception as e:
        return {
            "ok": False,
            "status": 0,
            "url": url,
            "error": f"{type(e).__name__}: {e}",
        }

def v133_komodo_project_status(slug, repo_id="", stack_id="", timeout=40):
    base, token = _v133_komodo_agent()
    payload = {
        "project_slug": slug,
    }
    if repo_id:
        payload["repo_id"] = repo_id
    if stack_id:
        payload["stack_id"] = stack_id

    return _v133_http_json(
        "POST",
        base + "/komodo/project/status",
        payload=payload,
        token=token,
        timeout=timeout,
    )

def v133_komodo_deploy_full(slug, repo_id="", stack_id="", timeout=180):
    base, token = _v133_komodo_agent()
    payload = {
        "project_slug": slug,
        "deploy": True,
        "force_reclone": True,
        "force_clone": True,
        "wait_for_completion": True,
        "max_wait_seconds": 90,
        "poll_interval": 5,
        "reset_reclone_after": False,
    }
    if repo_id:
        payload["repo_id"] = repo_id
    if stack_id:
        payload["stack_id"] = stack_id

    return _v133_http_json(
        "POST",
        base + "/komodo/project/deploy-full",
        payload=payload,
        token=token,
        timeout=timeout,
    )

def v133_komodo_stack_action(slug, action, stack_id="", timeout=90):
    base, token = _v133_komodo_agent()
    payload = {
        "project_slug": slug,
    }
    if stack_id:
        payload["stack_id"] = stack_id

    endpoint = "/komodo/stack/pull" if action == "pull" else "/komodo/stack/deploy"

    return _v133_http_json(
        "POST",
        base + endpoint,
        payload=payload,
        token=token,
        timeout=timeout,
    )

def _v133_short_hash(x):
    x = str(x or "")
    return x[:8] if x else "-"

def _v133_status_pill(status):
    status = str(status or "desconhecido")
    ok = status in ["completed", "ready"]
    warn = status in ["in_progress", "needs_attention"]
    cls = "ok" if ok else ("warn" if warn else "muted")
    try:
        return pill(True if ok else False, status, status) if cls != "warn" else f'<span class="pill">{_v133_h(status)}</span>'
    except Exception:
        return f'<span class="pill {cls}">{_v133_h(status)}</span>'

def v133_render_komodo_status_box(slug):
    res = v133_komodo_project_status(slug, timeout=12)
    data = res.get("data") if isinstance(res, dict) else {}
    if not isinstance(data, dict):
        data = {}

    if not res.get("ok"):
        msg = data.get("error") or data.get("message") or res.get("error") or "Status indisponível"
        return f'''
<div class="ci-komodo-status ci-komodo-status-error">
  <h5>Komodo v132</h5>
  <p class="ci-muted">Não foi possível consultar o status agora.</p>
  <p class="ci-muted">HTTP: {_v133_h(res.get("status"))} - {_v133_h(msg)}</p>
</div>
'''

    repo = data.get("repo") or {}
    stack = data.get("stack") or {}
    action_state = data.get("action_state") or {}
    busy = data.get("busy") or {}

    deployed_services = stack.get("deployed_services") or stack.get("latest_services") or []
    if isinstance(deployed_services, list) and deployed_services:
        svc = ", ".join(
            str((x or {}).get("service_name") or (x or {}).get("container_name") or x)
            for x in deployed_services[:4]
        )
        if len(deployed_services) > 4:
            svc += " +" + str(len(deployed_services) - 4)
    else:
        svc = "-"

    missing = stack.get("missing_files") or []
    errors = stack.get("remote_errors") or []

    if isinstance(missing, list):
        missing_txt = ", ".join(map(str, missing)) if missing else "-"
    else:
        missing_txt = str(missing)

    if isinstance(errors, list):
        err_txt = "sem erros" if not errors else f"{len(errors)} erro(s)"
    else:
        err_txt = str(errors or "sem erros")

    return f'''
<div class="ci-komodo-status">
  <h5>Komodo v132</h5>
  <div class="ci-kv">
    <span>Status</span><strong>{_v133_h(data.get("deploy_status") or "-")}</strong>
    <span>Repo hash</span><code>{_v133_h(_v133_short_hash(repo.get("latest_hash")))}</code>
    <span>Stack hash</span><code>{_v133_h(_v133_short_hash(stack.get("latest_hash")))}</code>
    <span>Deploy hash</span><code>{_v133_h(_v133_short_hash(stack.get("deployed_hash")))}</code>
    <span>Mensagem</span><small>{_v133_h(stack.get("latest_message") or repo.get("latest_message") or "-")}</small>
    <span>Arquivos ausentes</span><small>{_v133_h(missing_txt)}</small>
    <span>Erros remotos</span><small>{_v133_h(err_txt)}</small>
    <span>Serviços</span><small>{_v133_h(svc)}</small>
    <span>Ações</span><small>repo busy={_v133_h((busy or {}).get("repo"))}; stack busy={_v133_h((busy or {}).get("stack"))}</small>
  </div>
</div>
'''

def v133_render_komodo_buttons(slug):
    return f'''
<div class="ci-actions">
  {form_btn("Status Komodo", "komodo_status", slug, "", enabled=True, primary=False)}
  {form_btn("Deploy completo", "komodo_deploy_full", slug, "", enabled=True, primary=True)}
  {form_btn("Pull Stack", "komodo_pull_stack", slug, "", enabled=True, primary=False)}
  {form_btn("Deploy Stack", "komodo_deploy_stack", slug, "", enabled=True, primary=False)}
</div>
'''

def v133_action_result_html(title, slug, res):
    data = res.get("data") if isinstance(res, dict) else {}
    if not isinstance(data, dict):
        data = {}

    repo = data.get("repo") or ((data.get("after") or {}).get("repo") if isinstance(data.get("after"), dict) else {}) or {}
    stack = data.get("stack") or ((data.get("after") or {}).get("stack") if isinstance(data.get("after"), dict) else {}) or {}

    deploy_status = data.get("deploy_status") or ((data.get("after") or {}).get("deploy_status") if isinstance(data.get("after"), dict) else "")
    if not deploy_status and isinstance(data.get("result"), dict):
        deploy_status = ((data.get("result") or {}).get("data") or {}).get("status")

    missing = stack.get("missing_files") if isinstance(stack, dict) else None
    errors = stack.get("remote_errors") if isinstance(stack, dict) else None

    return f'''
<div class="box">
  <h3>{_v133_h(title)}</h3>
  <p><strong>Projeto:</strong> <code>{_v133_h(slug)}</code></p>
  <p><strong>HTTP:</strong> {_v133_h(res.get("status"))} - <strong>ok:</strong> {_v133_h(res.get("ok"))}</p>
  <p><strong>Status deploy:</strong> {_v133_h(deploy_status or "-")}</p>
  <p><strong>Repo hash:</strong> <code>{_v133_h(_v133_short_hash(repo.get("latest_hash") if isinstance(repo, dict) else ""))}</code></p>
  <p><strong>Stack hash:</strong> <code>{_v133_h(_v133_short_hash(stack.get("latest_hash") if isinstance(stack, dict) else ""))}</code></p>
  <p><strong>Missing:</strong> {_v133_h(missing if missing is not None else "-")}</p>
  <p><strong>Erros:</strong> {_v133_h(errors if errors is not None else "-")}</p>
  <details>
    <summary>JSON completo</summary>
    <pre style="white-space:pre-wrap;max-height:420px;overflow:auto">{_v133_h(json.dumps(data, ensure_ascii=False, indent=2)[:12000])}</pre>
  </details>
  <p><a class="btn light" href="/cloudiff/portal/?tab=git">Voltar para Git + Komodo</a></p>
</div>
'''

# CloudIF v133 fim




# CloudIF v136b2-safe — helpers Git/Komodo
def _v136b2_safe_id(value):
    import re
    value = str(value or "")
    value = re.sub(r"[^A-Za-z0-9_]+", "_", value)
    value = value.strip("_")
    return value or "projeto"

def _v136b2_public_project_url(slug):
    slug = str(slug or "").strip()
    if not slug:
        return "#"
    return f"https://{slug}.cloudiff.duckdns.org"

def _v136b2_link_project_tenant_form(project, tenant):
    return f"""
<style>
</style>
<script>
</script>

<form method="post" action="/cloudiff/portal/action/project_action" style="margin:0">
  <input type="hidden" name="op" value="save">
  <input type="hidden" name="action" value="save">
  <input type="hidden" name="slug" value="{h(project)}">
  <input type="hidden" name="project" value="{h(project)}">
  <input type="hidden" name="name" value="{h(project)}">
  <input type="hidden" name="db_mode" value="link">
  <input type="hidden" name="tenant" value="{h(tenant)}">
  <input type="hidden" name="setup_git" value="1">
  <input type="hidden" name="setup_komodo" value="1">
  <button type="submit" class="ci-btn ci-btn-secondary">Selecionar</button>
</form>
"""



# CloudIF v138b-safe — CSS seguro Git + Komodo
def _cloudif_v138b_git_css():
    return """
<style>
/* CloudIF v138b-safe — remover blocos redundantes Git + Komodo */
.cm-banner,
.ci-hero,
.ci-section:has(.ci-step-grid),
.ci-section:has(.ci-step-card),
.ci-section:has(input[name="setup_git"]),
.ci-section:has(input[name="setup_komodo"]),
.ci-section:has(input[name="name"]):has(input[name="slug"]),
.cloudif-hidden-new-project {
  display: none !important;
}

.ci-menu-body a[href*="tab=git"][href*="project="] {
  display: none !important;
}

/* Reforço visual do menu */
.ci-menu-item {
  display: block;
  width: 100%;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: #20312a;
  font-weight: 800;
  padding: 10px 12px;
  text-align: left;
  text-decoration: none;
  cursor: pointer;
}

.ci-menu-danger {
  color: #b42318 !important;
  background: #fff5f5 !important;
}
</style>
"""


def render_project_card(p, forja_online, komodo_online):
    slug = p.get("slug") or DEFAULT_PROJECT
    name = p.get("name") or slug
    tenant = p.get("tenant") or ""
    repo_url = p.get("repo_url") or ""
    komodo_status = p.get("komodo_status") or ""

    has_db = bool(tenant)
    has_git = bool(repo_url)
    has_komodo = bool(komodo_status) or has_git

    return f"""
<style>
</style>
<script>
</script>

<div class="ci-project-card">
  <div class="ci-card-top">
    <div>
      <h4>{h(name)}</h4>
      <div class="ci-muted"><code>{h(slug)}</code></div>
    </div>

    <details class="ci-menu">
      <summary>⋮</summary>
      <div class="ci-menu-body">
        <button type="button" class="ci-menu-item" onclick="cloudifShowWizard('wiz_acl_{_v136b2_safe_id(slug)}')">Permissões</button>
        <a href="#modal-vincular-banco" onclick="cloudifSetProject('{h(slug)}','{h(tenant)}')">Vincular banco</a>
        <!-- CloudIF v135b3 delete git/komodo form -->
<form method="post" action="/cloudiff/portal/git-komodo/action" style="margin:0">
  <input type="hidden" name="op" value="delete_git_komodo">
  <input type="hidden" name="slug" value="{h(slug)}">
  <button type="submit" class="ci-menu-item ci-menu-danger">Excluir projeto</button>
</form>
      </div>
    </details>
  </div>

  <div class="ci-resource">
    <div class="ci-resource-title">
      <strong>Banco / Supabase</strong>
      {pill(has_db, "Vinculado", "Sem banco")}
    </div>

    {f'''
      <p class="ci-muted">Tenant: <code>{h(tenant)}</code></p>
      <div class="ci-actions">
        {btn("Abrir Studio", public_supabase_studio_url(tenant), True, False, True)}

      </div>
    ''' if has_db else f'''
      <p class="ci-muted">Nenhum banco vinculado.</p>
      <div class="ci-actions">
        {btn("+ Criar Novo Banco", "#modal-vincular-banco", True, True)}
        {btn("+ Vincular Banco Existente", "#modal-vincular-banco", True, False)}
      </div>
    '''}
  </div>

  <div class="ci-resource">
    <div class="ci-resource-title">
      <strong>Git / Deploy</strong>
      {pill(has_git or has_komodo, "Configurado", "Não configurado")}
    </div>

    {f'''
      <p class="ci-muted">Forgejo: {pill(forja_online, "Online", "Offline")} Komodo: {pill(komodo_online, "Online", "Offline")}</p>
      <div class="ci-actions">
        {form_btn("Publicar site", "publish_site", slug, tenant, enabled=forja_online, primary=True)}
        {btn("Abrir site", _v136b2_public_project_url(slug), True, False, True)}
      </div>
    ''' if (has_git or has_komodo) else f'''
      <p class="ci-muted">Repositório e deploy ainda não foram configurados.</p>
      <div class="ci-actions">
        {form_btn("Configurar Repositório e Deploy", "integrate", slug, tenant, enabled=(forja_online or komodo_online), primary=True)}
      </div>
    '''}
  </div>
</div>
"""

def render_project_cards(project, tenant, forja_online, komodo_online):
    projects = discover_projects()
    if not projects:
        projects = [{
            "slug": project or DEFAULT_PROJECT,
            "name": project or DEFAULT_PROJECT,
            "tenant": tenant or "",
            "repo_url": "",
            "komodo_status": "",
        }]

    cards = "\n".join(render_project_card(p, forja_online, komodo_online) for p in projects)

    return f"""
{_cloudif_v138b_git_css()}

<style>
</style>
<script>
</script>

<div class="ci-section">
  <h3>Projetos</h3>
  <p class="ci-muted">Cada projeto é uma casca independente. Banco, Git e Deploy podem ser acoplados depois.</p>
  <div class="ci-card-grid">
    {cards}
  </div>
</div>
"""

def render_wizard():
    return """
<div class="ci-section">
  <p class="ci-muted">Assistente em 3 etapas. As etapas de banco e deploy podem ser puladas.</p>

  <div class="ci-wizard-steps">
    <div class="ci-step">
      <strong>1. Detalhes</strong>
      <small>Cria somente a casca do projeto.</small>
    </div>
    <div class="ci-step">
      <strong>2. Banco/Tenant</strong>
      <small>Criar, vincular ou pular.</small>
    </div>
    <div class="ci-step">
      <strong>3. Deploy</strong>
      <small>Forgejo e Komodo opcionais.</small>
    </div>
  </div>

  <div class="ci-actions">
    <a class="ci-btn ci-btn-primary" href="#modal-novo-projeto">+ Abrir Wizard</a>
  </div>
</div>
"""

def render_modals(project, tenant):
    tenants = discover_tenants()
    tenant_rows = []

    for t in tenants:
        name = t.get("tenant") or t.get("name") or t.get("slug") or ""
        tenant_rows.append(f"""
<tr>
  <td><b>{h(name)}</b></td>
  <td>{h(t.get("kong_http_port") or "-")}</td>
  <td>{_v136b2_link_project_tenant_form(project, name)}</td>
</tr>
""")

    if not tenant_rows:
        tenant_rows.append("<tr><td colspan='3'>Nenhum tenant disponível.</td></tr>")

    return f"""
<style>
</style>
<script>
</script>

<div id="modal-novo-projeto" class="ci-modal">
  <div class="ci-modal-card">
    <div class="ci-modal-head">
      <div>
        <p class="ci-muted">Crie primeiro a casca do projeto. Banco e deploy são opcionais.</p>
      </div>
      <a class="ci-close" href="#">×</a>
    </div>

    <form method="post" action="/cloudiff/portal/action/project_action">
      <input type="hidden" name="action" value="create_project">

      <h4>Passo 1 — Detalhes</h4>
      <div class="ci-field">
        <label>Nome do projeto</label>
        <input name="name" placeholder="Ex: Sistema de Biblioteca">
      </div>

      <div class="ci-field">
        <label>Descrição</label>
        <textarea name="description" rows="3" placeholder="Objetivo pedagógico ou técnico do projeto"></textarea>
      </div>

      <h4>Passo 2 — Banco/Tenant</h4>
      <div class="ci-choice-grid">
        <label class="ci-choice">
          <input type="radio" name="db_mode" value="create">
          <h4>Criar Novo Tenant</h4>
          <p class="ci-muted">Cria um banco isolado para o projeto.</p>
        </label>

        <label class="ci-choice">
          <input type="radio" name="db_mode" value="link">
          <h4>Vincular Existente</h4>
          <p class="ci-muted">Usa um tenant já autorizado.</p>
        </label>

        <label class="ci-choice">
          <input type="radio" name="db_mode" value="skip" checked>
          <h4>Pular</h4>
          <p class="ci-muted">Projeto sem banco neste momento.</p>
        </label>
      </div>

      <div class="ci-field">
        <label>Tenant existente, se aplicável</label>
        <input name="tenant" placeholder="ex: aluno, iff1742962">
      </div>

      <h4>Passo 3 — Deploy</h4>
      <label><input type="checkbox" name="create_repo" value="1"> Criar repositório no Forgejo</label><br>
      <label><input type="checkbox" name="setup_komodo" value="1"> Configurar Komodo</label>

      <div class="ci-actions">
        <button class="ci-btn ci-btn-primary" type="submit">Finalizar Wizard</button>
        <a class="ci-btn ci-btn-secondary" href="#">Cancelar</a>
      </div>
    </form>
  </div>
</div>

<div id="modal-vincular-banco" class="ci-modal">
  <div class="ci-modal-card">
    <div class="ci-modal-head">
      <div>
        <h3>Vincular Banco Existente</h3>
        <p class="ci-muted">Selecione um tenant disponível para o projeto.</p>
      </div>
      <a class="ci-close" href="#">×</a>
    </div>

    <table class="ci-table">
      <thead>
        <tr>
          <th>Tenant</th>
          <th>Kong</th>
          <th>Ação</th>
        </tr>
      </thead>
      <tbody>{''.join(tenant_rows)}</tbody>
    </table>
  </div>
</div>

<div id="modal-permissoes" class="ci-modal">
  <div class="ci-modal-card">
    <div class="ci-modal-head">
      <div>
        <h3>Permissões</h3>
        <p class="ci-muted">Busca dinâmica em AD/Authentik com debounce de 500ms.</p>
      </div>
      <a class="ci-close" href="#">×</a>
    </div>

    <div class="ci-field">
      <label>Usuário ou grupo</label>
      <input id="ci-perm-search" placeholder="Digite parte do nome, matrícula, e-mail ou grupo">
    </div>

    <div id="ci-perm-results" class="ci-muted">Digite para pesquisar...</div>
  </div>
</div>

<script>
let cloudifPermTimer = null;

function cloudifSetProject(project, tenant){{
  window.cloudifCurrentProject = project;
  window.cloudifCurrentTenant = tenant;
}}

const permInput = document.getElementById('ci-perm-search');
if (permInput) {{
  permInput.addEventListener('input', function(){{
    clearTimeout(cloudifPermTimer);
    const q = this.value.trim();
    const box = document.getElementById('ci-perm-results');

    if (!q) {{
      box.innerHTML = 'Digite para pesquisar...';
      return;
    }}

    box.innerHTML = 'Pesquisando...';

    cloudifPermTimer = setTimeout(function(){{
      fetch('/ad-search?q=' + encodeURIComponent(q) + '&type=all')
        .then(r => r.text())
        .then(txt => {{
          box.innerHTML = txt || 'Nenhum resultado encontrado.';
        }})
        .catch(err => {{
          box.innerHTML = 'Erro ao consultar AD/Authentik.';
        }});
    }}, 500);
  }});
}}
</script>
"""

def render_git_komodo_module(project="", tenant="", actor="portal", is_admin=False):
    refresh_public_host()

    project = project or first_project() or DEFAULT_PROJECT
    tenant = infer_project_tenant(project, tenant)

    forja_health, forja_status = status_forja()
    komodo_health, komodo_status = status_komodo()

    forja_online = ok_any(forja_health, forja_status)
    komodo_online = ok_any(komodo_health, komodo_status)

    return (
        css()
        + f"""
<div class="ci-page">
  <div class="ci-hero">
    <h2>Integrações CloudIF</h2>
    <p>Projetos agora são modulares: banco, Git e deploy podem ser criados, vinculados ou pulados sob demanda.</p>

    <div class="ci-toolbar">
      {pill(forja_online, "Forgejo online", "Forgejo offline")}
      {pill(komodo_online, "Komodo online", "Komodo offline")}
      {pill(bool(os.path.exists(PROJECT_INTEGRATE)), "Script integração OK", "Script integração ausente")}
    </div>
  </div>

  {render_wizard()}
  {render_project_cards(project, tenant, forja_online, komodo_online)}
  {render_modals(project, tenant)}
</div>
"""
    )

def handle_git_komodo_action(form, actor="portal"):

    # CloudIF v137a publish_site bridge
    try:
        import sys as _cloudif_v137a_sys
        if "/srv/cloudif/lib" not in _cloudif_v137a_sys.path:
            _cloudif_v137a_sys.path.insert(0, "/srv/cloudif/lib")
        from cloudif_publish_site_action import handle_publish_site_action
        _cloudif_v137a_publish = handle_publish_site_action(form, actor=actor)
        if _cloudif_v137a_publish is not None:
            return _cloudif_v137a_publish
    except Exception as _cloudif_v137a_exc:
        return False, "Erro na ação Publicar site.", {
            "ok": False,
            "error": "publish_site_exception",
            "exception_type": type(_cloudif_v137a_exc).__name__,
            "message": str(_cloudif_v137a_exc),
        }


    try:
        from cloudif_delete_git_komodo_action import handle_delete_git_komodo
        _cloudif_v135b2_delete_result = handle_delete_git_komodo(form, actor=actor)
        if _cloudif_v135b2_delete_result is not None:
            return _cloudif_v135b2_delete_result
    except Exception as _cloudif_v135b2_exc:
        return f'<div class="card"><h2>Erro na ação Excluir Git/Komodo</h2><p>{type(_cloudif_v135b2_exc).__name__}: {_cloudif_v135b2_exc}</p><p><a class="btn" href="/cloudiff/portal/?tab=git">Voltar</a></p></div>'


    op = ""
    try:
        op = form.getvalue("op") if hasattr(form, "getvalue") else form.get("op", "")
    except Exception:
        op = ""

    slug = _v133_slug_from_form(form)

    if op in ["komodo_status", "komodo_deploy_full", "komodo_pull_stack", "komodo_deploy_stack"]:
        if not slug:
            return '<div class="box"><h3>Erro</h3><p>Slug do projeto não informado.</p><p><a class="btn light" href="/cloudiff/portal/?tab=git">Voltar</a></p></div>'

        if op == "komodo_status":
            res = v133_komodo_project_status(slug)
            return v133_action_result_html("Status Komodo", slug, res)

        if op == "komodo_deploy_full":
            res = v133_komodo_deploy_full(slug)
            return v133_action_result_html("Deploy completo Komodo", slug, res)

        if op == "komodo_pull_stack":
            res = v133_komodo_stack_action(slug, "pull")
            return v133_action_result_html("Pull Stack", slug, res)

        if op == "komodo_deploy_stack":
            res = v133_komodo_stack_action(slug, "deploy")
            return v133_action_result_html("Deploy Stack", slug, res)

    def val(k, default=""):
        v = form.get(k, default)
        if isinstance(v, list):
            return v[0] if v else default
        return v or default

    action = val("action")
    project = val("project", DEFAULT_PROJECT)
    tenant = infer_project_tenant(project, val("tenant", ""))

    if action in ["check", "sync", "integrate"]:
        if not os.path.exists(PROJECT_INTEGRATE):
            return False, f"Script não encontrado: {PROJECT_INTEGRATE}", {"missing": PROJECT_INTEGRATE}

        res = run_cmd([PROJECT_INTEGRATE, action, project, tenant, actor], timeout=180)
        ok = bool(res.get("ok"))
        reconcile = None
        if ok:
            try:
                import sys as _reconcile_sys
                if "/srv/cloudif/lib" not in _reconcile_sys.path:
                    _reconcile_sys.path.insert(0, "/srv/cloudif/lib")
                from cloudif_reconcile_client import enqueue as _enqueue_reconcile
                reconcile = _enqueue_reconcile(
                    "project.integrated" if action == "integrate" else "project.updated",
                    actor=actor,
                    project=project,
                    tenant=tenant,
                    payload={"source": "git_komodo_action", "action": action},
                    dedupe_seconds=0,
                )
                res["reconcile"] = reconcile
            except Exception as exc:
                res["reconcile_error"] = type(exc).__name__
        msg = "Ação concluída." if ok else "Ação falhou."
        if reconcile and reconcile.get("request_id"):
            msg += " Reconciliação " + reconcile["request_id"][:8] + " enfileirada."
        return ok, msg, res

    return False, "Ação inválida.", {"action": action, "project": project, "tenant": tenant}
