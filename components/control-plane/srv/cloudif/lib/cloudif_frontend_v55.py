import html
import json
import os
import sqlite3
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

DB = os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db")
KOMODO_AGENT = os.environ.get("CLOUDIF_KOMODO_AGENT_URL", "http://10.62.91.2:18098").rstrip("/")
PROJECT_ENSURE = os.environ.get("CLOUDIF_PROJECT_ENSURE", "/usr/local/sbin/cloudif-project-ensure.py")

FORGEJO_OIDC_URL = os.environ.get("CLOUDIF_FORGEJO_OIDC_URL", "https://cloudiff.duckdns.org/git/user/oauth2/Authentik/")
KOMODO_OIDC_URL = os.environ.get("CLOUDIF_KOMODO_OIDC_URL", "https://komodoiff.duckdns.org/auth/oidc/login")

DEFAULT_PROJECT = os.environ.get("CLOUDIF_DEFAULT_PROJECT", "sistema-de-biblioteca-teste")
DEFAULT_TENANT = os.environ.get("CLOUDIF_DEFAULT_TENANT", "iff1742962")

METRIC_NODES = [
    ("hospedagem", "http://10.62.92.7:18096/metrics"),
    ("forja", "http://10.62.91.2:18096/metrics"),
    ("mauricio", "http://10.62.91.3:18096/metrics"),
]

def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def h(s):
    return html.escape("" if s is None else str(s))

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def table_exists(table):
    con = db()
    ok = con.execute("select 1 from sqlite_master where type='table' and name=?", (table,)).fetchone() is not None
    con.close()
    return ok

def db_one(sql, params=()):
    con = db()
    row = con.execute(sql, params).fetchone()
    con.close()
    return dict(row) if row else None

def db_all(sql, params=()):
    con = db()
    rows = [dict(r) for r in con.execute(sql, params).fetchall()]
    con.close()
    return rows

def db_exec(sql, params=()):
    con = db()
    con.execute(sql, params)
    con.commit()
    con.close()

def http_json(method, url, payload=None, timeout=45):
    data = None
    headers = {"Accept": "application/json", "User-Agent": "CloudIF-Frontend-v55"}
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

def actor(headers):
    return (
        headers.get("X-authentik-username")
        or headers.get("X-Authentik-Username")
        or headers.get("X-authentik-email")
        or headers.get("X-Forwarded-User")
        or "portal"
    )

def groups(headers):
    return headers.get("X-authentik-groups") or headers.get("X-Authentik-Groups") or ""

def is_admin(headers):
    g = groups(headers).lower()
    u = actor(headers).lower()
    return (
        "cloudif-admin" in g
        or "cloudif-tenants-admin" in g
        or "admin" in g
        or u in ["admin", "akadmin"]
    )

def current_state(project):
    row = db_one("select * from deploy_state where project=?", (project,))
    return row or {
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

def save_state(project, tenant, mode, actor_name, commit_sha="", commit_message="", response=None):
    db_exec("""
      insert into deploy_state(project,tenant,mode,commit_sha,commit_short,commit_message,actor,updated_at,response_json)
      values(?,?,?,?,?,?,?,?,?)
      on conflict(project) do update set
        tenant=excluded.tenant,
        mode=excluded.mode,
        commit_sha=excluded.commit_sha,
        commit_short=excluded.commit_short,
        commit_message=excluded.commit_message,
        actor=excluded.actor,
        updated_at=excluded.updated_at,
        response_json=excluded.response_json
    """, (
        project, tenant, mode, commit_sha or "", (commit_sha or "")[:7],
        commit_message or "", actor_name or "", now(),
        json.dumps(response or {}, ensure_ascii=False)
    ))

def record(project, tenant, actor_name, action, status, message, commit_sha="", mode="", response=None):
    db_exec("""
      insert into deployments(created_at,project,tenant,actor,action,status,message,commit_sha,commit_short,mode,response_json)
      values(?,?,?,?,?,?,?,?,?,?,?)
    """, (
        now(), project, tenant, actor_name, action, status, message or "",
        commit_sha or "", (commit_sha or "")[:7], mode or "",
        json.dumps(response or {}, ensure_ascii=False)
    ))

def audit(actor_name, project, action, status, message, request=None, response=None):
    db_exec("""
      insert into project_audit(created_at,actor,project,action,status,message,request_json,response_json)
      values(?,?,?,?,?,?,?,?)
    """, (
        now(), actor_name or "", project or "", action or "", status or "", message or "",
        json.dumps(request or {}, ensure_ascii=False),
        json.dumps(response or {}, ensure_ascii=False)
    ))

def get_projects():
    rows = []
    try:
        rows = db_all("select * from projects order by updated_at desc, slug asc limit 200")
    except Exception:
        rows = []

    if not rows:
        rows = [{
            "slug": DEFAULT_PROJECT,
            "name": "Sistema de Biblioteca Teste",
            "tenant_default": DEFAULT_TENANT,
            "repo_url": "https://cloudiff.duckdns.org/git/cloudif/cloudif-sistema-de-biblioteca-teste.git",
            "status": "integrado",
            "updated_at": now(),
        }]

    return rows

def get_tenants():
    tenants = []

    try:
        rows = db_all("select distinct tenant from project_tenants where tenant <> '' order by tenant")
        tenants += [r["tenant"] for r in rows if r.get("tenant")]
    except Exception:
        pass

    try:
        rows = db_all("select distinct tenant_default as tenant from projects where tenant_default <> '' order by tenant_default")
        tenants += [r["tenant"] for r in rows if r.get("tenant")]
    except Exception:
        pass

    if DEFAULT_TENANT not in tenants:
        tenants.append(DEFAULT_TENANT)

    clean = []
    for t in tenants:
        if t and t not in clean:
            clean.append(t)

    return clean

def get_metrics():
    out = []
    for name, url in METRIC_NODES:
        res = http_json("GET", url, timeout=5)
        data = res.get("data") if res.get("ok") else {}
        out.append({"name": name, "ok": bool(res.get("ok") and data.get("ok")), "data": data, "error": res.get("error", "")})
    return out

def get_komodo_status():
    return http_json("GET", KOMODO_AGENT + "/status", timeout=20)

def get_commits(project):
    url = KOMODO_AGENT + "/komodo/project/commits?project=" + urllib.parse.quote(project) + "&limit=20"
    res = http_json("GET", url, timeout=35)
    if res.get("ok") and isinstance(res.get("data"), dict):
        return res["data"].get("items", []), res
    return [], res

def stack_info(status, project):
    name = project if project.startswith("cloudif-") else "cloudif-" + project
    data = status.get("data", {}) if isinstance(status, dict) else {}
    stacks = ((data.get("stacks") or {}).get("data")) or []
    for st in stacks:
        if st.get("name") == name:
            return st
    return stacks[0] if stacks else {}

def recent_deployments(project=None, limit=30):
    if project:
        return db_all("select * from deployments where project=? order by id desc limit ?", (project, limit))
    return db_all("select * from deployments order by id desc limit ?", (limit,))

def recent_audit(limit=50):
    return db_all("select * from project_audit order by id desc limit ?", (limit,))

def project_permissions(project):
    try:
        return db_all("select * from project_permissions where project=? order by subject_type, subject_value", (project,))
    except Exception:
        return []

def project_tenants(project):
    try:
        return db_all("select * from project_tenants where project=? order by tenant", (project,))
    except Exception:
        return []

def action_project_ensure(form, actor_name):
    project = form.get("project", DEFAULT_PROJECT).strip() or DEFAULT_PROJECT
    name = form.get("name", project).strip() or project
    tenant = form.get("tenant", "").strip()
    repo_url = form.get("repo_url", "").strip()

    allow_users = [x.strip() for x in (form.get("allow_users", "") or "").split(",") if x.strip()]
    allow_groups = [x.strip() for x in (form.get("allow_groups", "") or "").split(",") if x.strip()]

    cmd = [
        PROJECT_ENSURE,
        "--project", project,
        "--name", name,
        "--tenant", tenant,
        "--repo-url", repo_url,
        "--actor", actor_name,
    ]

    for u in allow_users:
        cmd += ["--allow-user", u]
    for g in allow_groups:
        cmd += ["--allow-group", g]

    request = {
        "project": project,
        "name": name,
        "tenant": tenant,
        "repo_url": repo_url,
        "allow_users": allow_users,
        "allow_groups": allow_groups,
    }

    try:
        r = subprocess.run(cmd, text=True, capture_output=True, timeout=180)
        stdout = r.stdout or ""
        stderr = r.stderr or ""

        try:
            start = stdout.find("{")
            parsed = json.loads(stdout[start:]) if start >= 0 else {"stdout": stdout[-6000:], "stderr": stderr[-2000:]}
        except Exception:
            parsed = {"stdout": stdout[-6000:], "stderr": stderr[-2000:]}

        ok = r.returncode == 0
        status = "ok" if ok else "failed"
        msg = "Projeto criado/atualizado e integrações reaplicadas." if ok else "Falha ao criar/atualizar projeto."

        audit(actor_name, project, "project.ensure", status, msg, request, parsed)

        return ok, msg, parsed, project, tenant
    except Exception as e:
        res = {"error": str(e)}
        audit(actor_name, project, "project.ensure", "failed", str(e), request, res)
        return False, str(e), res, project, tenant

def action_rollback_filecontents(form, actor_name):
    project = form.get("project", DEFAULT_PROJECT)
    tenant = form.get("tenant", DEFAULT_TENANT)
    commit = form.get("commit", "")
    message = form.get("message", "")

    payload = {"project": project, "tenant": tenant, "actor": actor_name, "commit": commit}
    res = http_json("POST", KOMODO_AGENT + "/komodo/stack/rollback-filecontents", payload, timeout=150)
    ok = bool(res.get("ok") and isinstance(res.get("data"), dict) and res["data"].get("ok"))
    status = "ok" if ok else "failed"
    msg = (res.get("data") or {}).get("message") or ("Rollback solicitado." if ok else "Rollback falhou.")

    record(project, tenant, actor_name, "rollback-filecontents", status, msg, commit, "rollback_filecontents", res)
    audit(actor_name, project, "rollback-filecontents", status, msg, payload, res)

    if ok:
        save_state(project, tenant, "rollback_filecontents", actor_name, commit, message, res)

    return ok, msg, res, project, tenant

def action_return_git_main(form, actor_name):
    project = form.get("project", DEFAULT_PROJECT)
    tenant = form.get("tenant", DEFAULT_TENANT)

    payload = {"project": project, "tenant": tenant, "actor": actor_name}
    res = http_json("POST", KOMODO_AGENT + "/komodo/stack/return-git-main", payload, timeout=150)
    ok = bool(res.get("ok") and isinstance(res.get("data"), dict) and res["data"].get("ok"))
    status = "ok" if ok else "failed"
    msg = (res.get("data") or {}).get("message") or ("Retorno ao Git main solicitado." if ok else "Retorno ao Git main falhou.")

    record(project, tenant, actor_name, "return-git-main", status, msg, "", "git_main", res)
    audit(actor_name, project, "return-git-main", status, msg, payload, res)

    if ok:
        save_state(project, tenant, "git_main", actor_name, "", "Git main", res)

    return ok, msg, res, project, tenant

def action_stack(form, actor_name):
    action = form.get("action", "")
    project = form.get("project", DEFAULT_PROJECT)
    tenant = form.get("tenant", DEFAULT_TENANT)

    payload = {"project": project, "tenant": tenant, "actor": actor_name}
    res = http_json("POST", KOMODO_AGENT + "/komodo/stack/" + action, payload, timeout=150)
    ok = bool(res.get("ok") and isinstance(res.get("data"), dict) and res["data"].get("ok"))
    status = "ok" if ok else "failed"
    msg = (res.get("data") or {}).get("message") or ("Ação enviada." if ok else "Ação falhou.")

    record(project, tenant, actor_name, action, status, msg, "", current_state(project).get("mode", ""), res)
    audit(actor_name, project, action, status, msg, payload, res)

    return ok, msg, res, project, tenant

def action_tenant_placeholder(form, actor_name):
    action = form.get("action", "")
    tenant = form.get("tenant", "")
    project = form.get("project", "")
    msg = "Ação de tenant registrada no front-end v55. Vincular backend definitivo de tenants na próxima etapa."
    res = {"ok": False, "message": msg, "action": action, "tenant": tenant, "project": project}
    audit(actor_name, project, action, "pending", msg, form, res)
    return False, msg, res, project or DEFAULT_PROJECT, tenant or DEFAULT_TENANT

def handle_action(form, headers):
    actor_name = actor(headers)
    action = form.get("action", "")

    if action == "project-ensure":
        return action_project_ensure(form, actor_name)

    if action == "rollback-filecontents":
        return action_rollback_filecontents(form, actor_name)

    if action == "return-git-main":
        return action_return_git_main(form, actor_name)

    if action in ["deploy", "deploy-if-changed", "pull", "start", "stop", "restart", "destroy"]:
        return action_stack(form, actor_name)

    if action.startswith("tenant-") or action.startswith("permission-"):
        return action_tenant_placeholder(form, actor_name)

    project = form.get("project", DEFAULT_PROJECT)
    tenant = form.get("tenant", DEFAULT_TENANT)
    return False, "Ação inválida.", {"action": action}, project, tenant

def nav(view):
    items = [
        ("resumo", "Resumo"),
        ("projetos", "Projetos"),
        ("tenants", "Bancos / Tenants"),
        ("git-komodo", "Git / Komodo / Deploy"),
        ("admin", "Administração"),
        ("auditoria", "Auditoria"),
        ("ajuda", "Ajuda"),
        ("simulacao", "Simulação"),
    ]

    links = []
    for key, label in items:
        active = "active" if key == view else ""
        links.append(f'<a class="{active}" href="/cloudiff/portal/?view={h(key)}">{h(label)}</a>')
    return "\n".join(links)

def render_layout(view, body, headers, msg=""):
    user = actor(headers)
    grp = groups(headers)
    notice = f'<div class="notice">{h(msg)}</div>' if msg else ""

    return f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CloudIF Portal</title>
<style>
:root {{
  --if-green:#17882c;
  --if-green-dark:#0f5f1f;
  --if-red:#c8191e;
  --if-gray:#f4f6f5;
  --if-text:#1f2937;
  --muted:#6b7280;
  --card:white;
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0;
  font-family:Arial, Helvetica, sans-serif;
  background:var(--if-gray);
  color:var(--if-text);
}}
.shell {{
  display:grid;
  grid-template-columns:280px 1fr;
  min-height:100vh;
}}
aside {{
  background:#ffffff;
  border-right:1px solid #e5e7eb;
  padding:18px;
  position:sticky;
  top:0;
  height:100vh;
}}
.brand {{
  display:flex;
  gap:12px;
  align-items:center;
  margin-bottom:18px;
  border-bottom:4px solid var(--if-green);
  padding-bottom:14px;
}}
.logo-grid {{
  width:38px;
  display:grid;
  grid-template-columns:repeat(2, 14px);
  gap:4px;
}}
.logo-grid span {{
  width:14px;
  height:14px;
  background:var(--if-green);
  border-radius:3px;
}}
.logo-grid span.red {{
  background:var(--if-red);
  border-radius:50%;
}}
.brand h1 {{
  font-size:20px;
  margin:0;
}}
.brand small {{
  color:var(--muted);
}}
nav a {{
  display:block;
  padding:11px 12px;
  color:#111827;
  text-decoration:none;
  border-radius:10px;
  margin-bottom:5px;
  font-weight:bold;
}}
nav a.active, nav a:hover {{
  background:#e8f5e9;
  color:var(--if-green-dark);
}}
.userbox {{
  background:#f9fafb;
  border:1px solid #e5e7eb;
  border-radius:12px;
  padding:12px;
  margin-top:18px;
  font-size:13px;
}}
main {{
  padding:24px;
  max-width:1400px;
  width:100%;
}}
.card {{
  background:var(--card);
  border-radius:14px;
  box-shadow:0 8px 24px rgba(0,0,0,.08);
  padding:20px;
  margin-bottom:18px;
}}
.grid {{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(250px,1fr));
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
input, select, textarea {{
  padding:9px;
  border:1px solid #d1d5db;
  border-radius:8px;
  width:100%;
}}
label {{
  font-weight:bold;
  display:block;
  margin-top:8px;
}}
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
.wizard {{
  display:none;
}}
.wizard.open {{
  display:block;
}}
.step {{
  border-left:4px solid var(--if-green);
  padding-left:14px;
  margin:16px 0;
}}
@media(max-width:900px) {{
  .shell {{ grid-template-columns:1fr; }}
  aside {{ position:relative; height:auto; }}
}}
</style>
<script>
function toggleWizard(id) {{
  const el = document.getElementById(id);
  if (el) el.classList.toggle('open');
}}
function showStep(prefix, n) {{
  document.querySelectorAll('[data-step-group="'+prefix+'"]').forEach(x => x.style.display='none');
  const el = document.getElementById(prefix+'-step-'+n);
  if (el) el.style.display='block';
}}
</script>
</head>
<body>
<div class="shell">
<aside>
  <div class="brand">
    <div class="logo-grid">
      <span></span><span class="red"></span>
      <span></span><span></span>
      <span></span><span></span>
    </div>
    <div>
      <h1>CloudIF</h1>
      <small>Portal integrado</small>
    </div>
  </div>
  <nav>{nav(view)}</nav>
  <div class="userbox">
    <strong>Usuário</strong><br>{h(user)}<br><br>
    <strong>Grupos</strong><br><small>{h(grp or "-")}</small>
  </div>
</aside>
<main>
{notice}
{body}
</main>
</div>
</body>
</html>"""

def render_resumo(headers):
    projects = get_projects()
    tenants = get_tenants()
    metrics = get_metrics()
    status = get_komodo_status()

    metric_boxes = []
    for m in metrics:
        data = m.get("data") or {}
        mem = data.get("memory") or {}
        disk = data.get("disk_root") or {}
        docker = data.get("docker") or {}
        ok = m.get("ok")
        klass = "ok" if ok else "err"

        def gb(x):
            try:
                return f"{int(x)/(1024**3):.1f} GB"
            except Exception:
                return "-"

        metric_boxes.append(f"""
        <div class="box">
          <strong>{h(m['name'])}</strong><br>
          <span class="badge {klass}">{'online' if ok else 'offline'}</span><br><br>
          Memória: <code>{h(gb(mem.get('used')))} / {h(gb(mem.get('total')))}</code><br>
          Disco /: <code>{h(gb(disk.get('used')))} / {h(gb(disk.get('size')))}</code><br>
          Containers: <code>{h(docker.get('count', '-'))}</code>
        </div>
        """)

    komodo_ok = bool(status.get("ok") and status.get("data", {}).get("ok"))
    komodo_badge = "ok" if komodo_ok else "err"

    return f"""
<section class="card">
  <h1>Resumo</h1>
  <p>Visão única do ambiente CloudIF, respeitando autenticação, permissões, projetos, tenants, Git, Komodo e deploy.</p>
  <div class="grid">
    <div class="box">
      <strong>Projetos visíveis</strong><br>
      <span class="badge info">{len(projects)}</span>
    </div>
    <div class="box">
      <strong>Tenants/Bancos</strong><br>
      <span class="badge info">{len(tenants)}</span>
    </div>
    <div class="box">
      <strong>Komodo Agent</strong><br>
      <span class="badge {komodo_badge}">{'online' if komodo_ok else 'offline'}</span>
    </div>
  </div>
</section>

<section class="card">
  <h2>Hardware e serviços</h2>
  <div class="grid">{''.join(metric_boxes)}</div>
</section>

<section class="card">
  <h2>Projetos recentes</h2>
  <table>
    <thead><tr><th>Projeto</th><th>Tenant</th><th>Status</th><th>Ações</th></tr></thead>
    <tbody>
      {''.join(f'''
      <tr>
        <td><code>{h(p.get("slug"))}</code><br><small>{h(p.get("name"))}</small></td>
        <td>{h(p.get("tenant_default") or "-")}</td>
        <td><span class="badge info">{h(p.get("status") or "-")}</span></td>
        <td>
          <a class="linkbtn" href="/cloudiff/portal/?view=git-komodo&project={h(p.get("slug"))}&tenant={h(p.get("tenant_default") or DEFAULT_TENANT)}">Abrir</a>
        </td>
      </tr>''' for p in projects)}
    </tbody>
  </table>
</section>
"""

def render_projetos(headers, qs):
    projects = get_projects()
    admin = is_admin(headers)

    rows = []
    for p in projects:
        slug = p.get("slug", "")
        tenant = p.get("tenant_default") or DEFAULT_TENANT
        perms = project_permissions(slug)
        pts = project_tenants(slug)
        rows.append(f"""
        <tr>
          <td><code>{h(slug)}</code><br><small>{h(p.get("name"))}</small></td>
          <td>{h(tenant)}</td>
          <td>{h(p.get("repo_url") or "-")}</td>
          <td>{h(len(perms))} permissões<br>{h(len(pts))} tenants</td>
          <td>
            <a class="linkbtn" href="/cloudiff/portal/?view=git-komodo&project={h(slug)}&tenant={h(tenant)}">Git/Komodo</a>
            <button class="btn secondary" onclick="toggleWizard('wizard-{h(slug)}')">Editar</button>
          </td>
        </tr>
        <tr><td colspan="5">
          <div id="wizard-{h(slug)}" class="wizard">
            {project_wizard(slug, p.get("name") or slug, tenant, p.get("repo_url") or "", admin)}
          </div>
        </td></tr>
        """)

    if not rows:
        rows.append("<tr><td colspan='5'>Nenhum projeto encontrado.</td></tr>")

    new_box = ""
    if admin:
        new_box = f"""
        <section class="card">
          <button class="btn" onclick="toggleWizard('wizard-new')">Novo projeto</button>
          <div id="wizard-new" class="wizard">
            {project_wizard("", "", "", "", admin)}
          </div>
        </section>
        """

    return f"""
<section class="card">
  <h1>Projetos</h1>
  <p>O projeto é o objeto central. Ao criar ou editar, o portal deve executar o fluxo completo: permissões, tenant Supabase, Forgejo, webhooks e Komodo Stack.</p>
</section>

{new_box}

<section class="card">
  <h2>Projetos visíveis</h2>
  <table>
    <thead><tr><th>Projeto</th><th>Tenant padrão</th><th>Repositório</th><th>Vínculos</th><th>Ações</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</section>
"""

def project_wizard(slug, name, tenant, repo_url, admin):
    if not admin:
        return "<p>Somente administradores podem criar ou editar projetos.</p>"

    suggested_repo = repo_url or ("https://cloudiff.duckdns.org/git/cloudif/cloudif-" + (slug or "novo-projeto") + ".git")

    return f"""
<form method="post" action="/cloudiff/portal/action">
  <input type="hidden" name="action" value="project-ensure">

  <div class="step" data-step-group="project">
    <h3>1. Dados do projeto</h3>
    <label>Slug do projeto</label>
    <input name="project" value="{h(slug)}" placeholder="sistema-de-biblioteca-teste">
    <label>Nome</label>
    <input name="name" value="{h(name)}" placeholder="Sistema de Biblioteca">
  </div>

  <div class="step" data-step-group="project">
    <h3>2. Permissões</h3>
    <label>Usuários permitidos, separados por vírgula</label>
    <input name="allow_users" placeholder="iff1742962, aluno2">
    <label>Grupos permitidos, separados por vírgula</label>
    <input name="allow_groups" value="CloudIF-Tenants-Admin">
  </div>

  <div class="step" data-step-group="project">
    <h3>3. Banco / Tenant</h3>
    <label>Tenant Supabase</label>
    <input name="tenant" value="{h(tenant)}" placeholder="vazio para projeto sem banco">
    <small>Projetos sem banco podem usar apenas Git/Komodo. Um tenant pode ser vinculado a mais de um projeto.</small>
  </div>

  <div class="step" data-step-group="project">
    <h3>4. Git / Komodo</h3>
    <label>URL do repositório Forgejo</label>
    <input name="repo_url" value="{h(suggested_repo)}">
    <small>Ao confirmar, o portal chama project.ensure para criar/atualizar Forgejo, webhooks, Komodo e Supabase.</small>
  </div>

  <button class="btn">Confirmar e aplicar integrações</button>
</form>
"""

def render_tenants(headers, qs):
    admin = is_admin(headers)
    tenants = get_tenants()
    project = qs.get("project", [DEFAULT_PROJECT])[0] or DEFAULT_PROJECT

    cards = []
    for t in tenants:
        start_disabled = ""
        always_disabled = "" if admin else "disabled"

        cards.append(f"""
        <div class="box">
          <h3>{h(t)}</h3>
          <p><span class="badge info">tenant</span></p>
          <div class="actions">
            <form method="post" action="/cloudiff/portal/action">
              <input type="hidden" name="action" value="tenant-start">
              <input type="hidden" name="tenant" value="{h(t)}">
              <input type="hidden" name="project" value="{h(project)}">
              <button class="btn" {start_disabled}>Iniciar</button>
            </form>
            <form method="post" action="/cloudiff/portal/action">
              <input type="hidden" name="action" value="tenant-stop">
              <input type="hidden" name="tenant" value="{h(t)}">
              <input type="hidden" name="project" value="{h(project)}">
              <button class="btn warn">Parar</button>
            </form>
            <form method="post" action="/cloudiff/portal/action">
              <input type="hidden" name="action" value="tenant-repair">
              <input type="hidden" name="tenant" value="{h(t)}">
              <input type="hidden" name="project" value="{h(project)}">
              <button class="btn secondary">Reparar</button>
            </form>
            <form method="post" action="/cloudiff/portal/action">
              <input type="hidden" name="action" value="tenant-keepalive">
              <input type="hidden" name="tenant" value="{h(t)}">
              <input type="hidden" name="project" value="{h(project)}">
              <button class="btn secondary" {always_disabled}>Sempre vivo</button>
            </form>
          </div>

          <h4>Permissões do tenant</h4>
          <form method="post" action="/cloudiff/portal/action">
            <input type="hidden" name="action" value="permission-tenant-add">
            <input type="hidden" name="tenant" value="{h(t)}">
            <input type="hidden" name="project" value="{h(project)}">
            <label>Usuário ou grupo</label>
            <input name="subject" placeholder="usuário, matrícula ou grupo">
            <button class="btn secondary">Vincular permissão</button>
          </form>
        </div>
        """)

    return f"""
<section class="card">
  <h1>Bancos / Tenants</h1>
  <p>O tenant pode ser usado por mais de um projeto. Ações administrativas avançadas só aparecem habilitadas para admin.</p>
  <div class="grid">{''.join(cards)}</div>
</section>
"""

def render_git_komodo(headers, qs):
    project = qs.get("project", [DEFAULT_PROJECT])[0] or DEFAULT_PROJECT
    tenant = qs.get("tenant", [DEFAULT_TENANT])[0] or DEFAULT_TENANT

    commits, commits_res = get_commits(project)
    status = get_komodo_status()
    st = stack_info(status, project)
    info = st.get("info", {}) if isinstance(st, dict) else {}
    state = current_state(project)
    history = recent_deployments(project)

    is_file_contents = bool(info.get("file_contents"))
    komodo_mode = "rollback por conteúdo" if is_file_contents else "Git/branch"
    portal_mode = {"git_main": "Git main", "rollback_filecontents": "Rollback por conteúdo"}.get(state.get("mode"), state.get("mode") or "Git main")

    missing = info.get("missing_files") or []
    services = info.get("services") or []

    commit_rows = []
    for c in commits:
        sha = c.get("sha", "")
        short = c.get("short") or sha[:7]
        msg = (c.get("message") or "").splitlines()[0]
        author = c.get("author", "")
        date = c.get("date", "")
        url = c.get("html_url", "")

        commit_rows.append(f"""
        <tr>
          <td><code>{h(short)}</code></td>
          <td>{h(msg)}</td>
          <td>{h(author)}<br><small>{h(date)}</small></td>
          <td>
            <a class="linkbtn" href="{h(url)}" target="_blank">Abrir commit</a>
            <form method="post" action="/cloudiff/portal/action" style="display:inline">
              <input type="hidden" name="action" value="rollback-filecontents">
              <input type="hidden" name="project" value="{h(project)}">
              <input type="hidden" name="tenant" value="{h(tenant)}">
              <input type="hidden" name="commit" value="{h(sha)}">
              <input type="hidden" name="message" value="{h(msg)}">
              <button class="btn danger">Rollback para este commit</button>
            </form>
          </td>
        </tr>
        """)

    if not commit_rows:
        commit_rows.append(f"<tr><td colspan='4'>Não foi possível listar commits. Resposta: <code>{h(commits_res)}</code></td></tr>")

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
        klass = "ok" if r.get("status") == "ok" else "err"
        hist_rows.append(f"""
        <tr>
          <td>{h(r.get("created_at"))}</td>
          <td>{h(r.get("actor"))}</td>
          <td>{h(r.get("action"))}</td>
          <td><span class="badge {klass}">{h(r.get("status"))}</span></td>
          <td><code>{h(r.get("commit_short"))}</code></td>
          <td>{h(r.get("mode"))}</td>
          <td>{h(r.get("message"))}</td>
        </tr>
        """)

    if not hist_rows:
        hist_rows.append("<tr><td colspan='7'>Nenhum histórico registrado ainda.</td></tr>")

    state_class = "ok" if info.get("state") == "running" else "err"

    return f"""
<section class="card">
  <h1>Git / Komodo / Deploy</h1>
  <p>Módulo integrado ao portal principal. Os botões antigos de checar/sincronizar/integrar foram substituídos por status e ações reais de deploy.</p>

  <div class="grid">
    <div class="box">
      <strong>Projeto</strong><br>
      <code>{h(project)}</code><br><br>
      <strong>Tenant</strong><br>
      <code>{h(tenant)}</code>
    </div>

    <div class="box">
      <strong>Modo registrado no Portal</strong><br>
      <span class="badge info">{h(portal_mode)}</span><br><br>
      <strong>Commit registrado</strong><br>
      <code>{h(state.get("commit_short") or "-")}</code><br>
      <small>{h(state.get("commit_message") or "")}</small><br>
      <small>Atualizado por {h(state.get("actor") or "-")} em {h(state.get("updated_at") or "-")}</small>
    </div>

    <div class="box">
      <strong>Estado Komodo</strong><br>
      <span class="badge {state_class}">{h(info.get("state") or "desconhecido")}</span>
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
    <a class="linkbtn" href="{h(FORGEJO_OIDC_URL)}" target="_blank">Abrir Git</a>
    <a class="linkbtn" href="{h(KOMODO_OIDC_URL)}" target="_blank">Abrir Komodo</a>

    <form method="post" action="/cloudiff/portal/action">
      <input type="hidden" name="action" value="return-git-main">
      <input type="hidden" name="project" value="{h(project)}">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      <button class="btn secondary">Voltar ao Git main</button>
    </form>

    <form method="post" action="/cloudiff/portal/action">
      <input type="hidden" name="action" value="deploy">
      <input type="hidden" name="project" value="{h(project)}">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      <button class="btn">Deploy atual</button>
    </form>

    <form method="post" action="/cloudiff/portal/action">
      <input type="hidden" name="action" value="deploy-if-changed">
      <input type="hidden" name="project" value="{h(project)}">
      <input type="hidden" name="tenant" value="{h(tenant)}">
      <button class="btn secondary">Deploy se alterado</button>
    </form>
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
  <p>O rollback baixa o <code>docker-compose.yml</code> do commit escolhido no Forgejo e aplica a Stack em modo <code>file_contents</code>. O commit aplicado fica registrado no SQLite do Portal.</p>
  <table>
    <thead><tr><th>Commit</th><th>Mensagem</th><th>Autor/Data</th><th>Ações</th></tr></thead>
    <tbody>{''.join(commit_rows)}</tbody>
  </table>
</section>

<section class="card">
  <h2>Histórico de deploy/rollback</h2>
  <table>
    <thead><tr><th>Data</th><th>Usuário</th><th>Ação</th><th>Status</th><th>Commit</th><th>Modo</th><th>Mensagem</th></tr></thead>
    <tbody>{''.join(hist_rows)}</tbody>
  </table>
</section>
"""

def render_admin(headers):
    admin = is_admin(headers)
    if not admin:
        return "<section class='card'><h1>Administração</h1><p>Área restrita a administradores.</p></section>"

    flags = [
        ("Grupo admin", "CloudIF-Tenants-Admin"),
        ("Grupo base dos usuários", "cloudiff"),
        ("Permitir projeto sem banco", "sim"),
        ("Permitir aluno criar banco", "conforme política"),
        ("Sempre vivo", "somente admin"),
        ("Rollback", "file_contents + registro SQLite"),
    ]

    return f"""
<section class="card">
  <h1>Administração</h1>
  <p>Parâmetros de regra de negócio consolidados do CloudIF.</p>
  <table>
    <thead><tr><th>Parâmetro</th><th>Valor / Regra</th></tr></thead>
    <tbody>
      {''.join(f'<tr><td>{h(k)}</td><td>{h(v)}</td></tr>' for k,v in flags)}
    </tbody>
  </table>
</section>
"""

def render_auditoria(headers):
    rows = recent_audit(80)
    body = []
    for r in rows:
        klass = "ok" if r.get("status") == "ok" else "err"
        body.append(f"""
        <tr>
          <td>{h(r.get("created_at"))}</td>
          <td>{h(r.get("actor"))}</td>
          <td>{h(r.get("project"))}</td>
          <td>{h(r.get("action"))}</td>
          <td><span class="badge {klass}">{h(r.get("status"))}</span></td>
          <td>{h(r.get("message"))}</td>
        </tr>
        """)
    if not body:
        body.append("<tr><td colspan='6'>Nenhum registro de auditoria.</td></tr>")

    return f"""
<section class="card">
  <h1>Auditoria</h1>
  <table>
    <thead><tr><th>Data</th><th>Usuário</th><th>Projeto</th><th>Ação</th><th>Status</th><th>Mensagem</th></tr></thead>
    <tbody>{''.join(body)}</tbody>
  </table>
</section>
"""

def render_ajuda(headers):
    return """
<section class="card">
  <h1>Ajuda</h1>
  <h2>Como o CloudIF funciona</h2>
  <p>O Portal CloudIF organiza projetos, tenants Supabase, Forgejo e Komodo em um fluxo único.</p>

  <h3>Criação de projeto</h3>
  <p>Ao criar ou editar projeto, o portal chama <code>project.ensure</code>, que garante permissões, tenant, hooks Supabase, repo/webhook Forgejo e stack Komodo.</p>

  <h3>Deploy</h3>
  <p>O deploy usa Komodo com Git Provider Account apontando para o Forgejo privado.</p>

  <h3>Rollback</h3>
  <p>O rollback usa <code>file_contents</code>: o agente baixa o <code>docker-compose.yml</code> do commit escolhido e aplica no Komodo. O Portal registra o commit, pois o Komodo não mostra hash nesse modo.</p>

  <h3>Bancos / Tenants</h3>
  <p>Um tenant pode estar vinculado a mais de um projeto. Aluno opera apenas o que tem permissão. Admin executa ações avançadas.</p>
</section>
"""

def render_simulacao(headers):
    return """
<section class="card">
  <h1>Simulação do software funcionando</h1>
  <p>Esta tela simula o fluxo ideal do CloudIF para validar navegação e regras de negócio antes de mexer em produção.</p>

  <div class="grid">
    <div class="box">
      <h3>1. Usuário acessa</h3>
      <p>Authentik envia usuário e grupos ao portal. O menu mostra somente o que o usuário pode ver.</p>
      <span class="badge ok">autenticado</span>
    </div>
    <div class="box">
      <h3>2. Cria projeto</h3>
      <p>Wizard coleta projeto, permissões, tenant e Git/Komodo.</p>
      <span class="badge info">wizard</span>
    </div>
    <div class="box">
      <h3>3. project.ensure</h3>
      <p>Supabase, Forgejo e Komodo são vinculados automaticamente.</p>
      <span class="badge ok">automático</span>
    </div>
    <div class="box">
      <h3>4. Deploy</h3>
      <p>Komodo puxa o repo privado do Forgejo e sobe a Stack.</p>
      <span class="badge ok">running</span>
    </div>
    <div class="box">
      <h3>5. Rollback</h3>
      <p>Usuário escolhe commit; Portal aplica file_contents e registra histórico.</p>
      <span class="badge info">commit controlado</span>
    </div>
    <div class="box">
      <h3>6. Auditoria</h3>
      <p>Todas as ações ficam registradas com data, usuário, projeto, ação e resultado.</p>
      <span class="badge ok">rastreável</span>
    </div>
  </div>
</section>
"""

def render(view, headers, qs, msg=""):
    if view == "resumo":
        body = render_resumo(headers)
    elif view == "projetos":
        body = render_projetos(headers, qs)
    elif view == "tenants":
        body = render_tenants(headers, qs)
    elif view == "git-komodo":
        body = render_git_komodo(headers, qs)
    elif view == "admin":
        body = render_admin(headers)
    elif view == "auditoria":
        body = render_auditoria(headers)
    elif view == "ajuda":
        body = render_ajuda(headers)
    elif view == "simulacao":
        body = render_simulacao(headers)
    else:
        body = render_resumo(headers)
        view = "resumo"

    return render_layout(view, body, headers, msg)
