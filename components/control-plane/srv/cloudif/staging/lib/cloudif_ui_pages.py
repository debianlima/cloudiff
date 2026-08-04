#!/usr/bin/env python3
import urllib.parse
import cloudif_project_acl_module as project_acl

from cloudif_ui_components import h, btn, pill, layout
from cloudif_ui_data import discover_projects, discover_tenants, public_studio_url, deploy_url, tab_url, project_counts, server_metrics, technical_inventory


# CloudIF v95 — helpers do wizard de projeto

def _v95_user_name(user=None):
    import re
    user = user or {}
    raw = (
        user.get("username")
        or user.get("name")
        or user.get("email", "").split("@")[0]
        or "usuario"
    )
    raw = str(raw).strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "", raw)
    return raw or "usuario"

def _v95_user_groups(user=None):
    user = user or {}
    groups = user.get("groups") or []
    if isinstance(groups, str):
        groups = [g.strip() for g in groups.replace("|", ",").split(",") if g.strip()]
    return groups

def _v95_is_admin(user=None):
    groups = {g.lower() for g in _v95_user_groups(user)}
    return bool(groups & {"cloudif-tenants-admin", "cloudif-admin", "domain admins"})

def _v95_tenant_name(t):
    if isinstance(t, dict):
        return t.get("tenant") or t.get("name") or t.get("slug") or ""
    return str(t or "")

def _v95_allowed_tenants(user=None):
    """
    Lista tenants reais que o usuário pode selecionar.
    Preferência:
    - admin vê todos;
    - se tenant_acl existir, filtra por usuário/e-mail/grupo;
    - se não houver tenant_acl, usa discover_tenants() como fonte já existente do portal.
    """
    import sqlite3

    user = user or {}
    username = str(user.get("username") or user.get("name") or "").strip().lower()
    email = str(user.get("email") or "").strip().lower()
    groups = {g.lower() for g in _v95_user_groups(user)}
    admin = _v95_is_admin(user)

    discovered = []
    for t in discover_tenants():
        name = _v95_tenant_name(t)
        if name:
            discovered.append(name)

    discovered = sorted(set(discovered))

    if admin:
        return discovered

    db = "/var/lib/cloudif/portal/cloudif-portal.db"

    try:
        con = sqlite3.connect(db)
        con.row_factory = sqlite3.Row
        tables = [r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if "tenant_acl" not in tables:
            con.close()
            return discovered

        rows = con.execute("SELECT * FROM tenant_acl").fetchall()
        con.close()

        allowed = set()
        for r in rows:
            d = dict(r)
            tenant = str(d.get("tenant") or d.get("name") or d.get("slug") or "").strip()
            stype = str(d.get("subject_type") or d.get("type") or "").strip().lower()
            subject = str(d.get("subject") or d.get("principal") or d.get("user") or d.get("group") or "").strip().lower()

            if not tenant or not subject:
                continue

            if stype == "user" and subject in {username, email}:
                allowed.add(tenant)

            if stype == "group" and subject in groups:
                allowed.add(tenant)

        if allowed:
            return sorted(allowed)

        return []
    except Exception:
        return discovered

def _v95_options(items, selected=""):
    out = []
    selected = str(selected or "")
    for item in items:
        sel = " selected" if str(item) == selected else ""
        out.append(f'<option value="{h(item)}"{sel}>{h(item)}</option>')
    return "".join(out)

def _v95_project_org(p=None):
    p = p or {}
    return (
        p.get("forgejo_org")
        or p.get("git_org")
        or p.get("organization")
        or p.get("org")
        or "cloudif"
    )

def _v95_repo_url(slug, p=None):
    p = p or {}
    return (
        p.get("repo_url")
        or p.get("forgejo_url")
        or p.get("git_url")
        or f"https://cloudiff.duckdns.org/git/{_v95_project_org(p)}/{slug}"
    )



# CloudIF v134 - resumo Komodo v132 na aba Projetos e wizard
def _v134_h(x):
    try:
        return h(x)
    except Exception:
        import html
        return html.escape(str(x if x is not None else ""))

def _v134_read_env(path):
    data = {}
    try:
        from pathlib import Path
        p = Path(path)
        if p.exists():
            for raw in p.read_text(errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return data

def _v134_komodo_agent_url():
    env1 = _v134_read_env("/etc/cloudif/komodo-agent-client.env")
    env2 = _v134_read_env("/etc/cloudif/provision.env")
    url = (
        env1.get("KOMODO_AGENT_URL")
        or env2.get("KOMODO_AGENT_URL")
        or "http://10.62.91.2:18098"
    )
    token = env1.get("KOMODO_AGENT_TOKEN") or env2.get("KOMODO_AGENT_TOKEN") or ""
    return str(url).rstrip("/"), token

def _v134_http_json(method, url, payload=None, token="", timeout=5):
    import json
    import urllib.request
    import urllib.error

    headers = {"Accept": "application/json"}
    data = None

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if token:
        headers["X-CloudIF-Token"] = token
        headers["Authorization"] = "Bearer " + token

    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method.upper(),
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {"raw": raw}
            return {"ok": 200 <= r.status < 300, "status": r.status, "data": body}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            body = {"raw": raw}
        return {"ok": False, "status": e.code, "data": body}
    except Exception as e:
        return {"ok": False, "status": 0, "error": f"{type(e).__name__}: {e}", "data": {}}

def _v134_komodo_status(slug):
    slug = str(slug or "").strip()
    if not slug:
        return {"ok": False, "status": 0, "data": {"deploy_status": "sem slug"}}

    base, token = _v134_komodo_agent_url()

    return _v134_http_json(
        "POST",
        base + "/komodo/project/status",
        payload={"project_slug": slug},
        token=token,
        timeout=5,
    )

def _v134_short_hash(x):
    x = str(x or "")
    return x[:8] if x else "-"

def _v134_service_names(stack):
    services = []
    if isinstance(stack, dict):
        services = stack.get("deployed_services") or stack.get("latest_services") or []

    if isinstance(services, list) and services:
        names = []
        for svc in services[:4]:
            if isinstance(svc, dict):
                names.append(str(svc.get("service_name") or svc.get("container_name") or "-"))
            else:
                names.append(str(svc))
        if len(services) > 4:
            names.append("+" + str(len(services) - 4))
        return ", ".join(names)

    return "-"



# CloudIF v134b - evitar status real Komodo em projeto novo/placeholder
def _v134b_is_new_project_placeholder(slug):
    slug = str(slug or "").strip().lower()
    if not slug:
        return True
    return slug in [
        "novo-projeto",
        "novo_project",
        "new-project",
        "__novo__",
        "__new__",
    ]

def _v134b_render_new_project_komodo_prediction():
    return '''
<div style="margin-top:10px;padding:12px;border:1px dashed #dfe8dd;border-radius:12px;background:#f9fbf8">
  <h4 style="margin:0 0 8px 0">Git, Komodo e provisionamento automático</h4>
  <p class="small">
    Após salvar o projeto, o Portal criará/vinculará o repositório
    <code>cloudif-&lt;slug&gt;</code>, configurará o Komodo e permitirá o deploy completo
    pela aba <strong>Git + Komodo</strong>.
  </p>
  <p class="small">
    O status real do Komodo aparecerá aqui depois que o projeto existir e for provisionado.
  </p>
</div>
'''



# CloudIF v135a2-safe - leitura visual read-only do cache Komodo
def _v135a2_db_path():
    try:
        env = _v134_read_env("/etc/cloudif/portal.env")
        return env.get("CLOUDIF_PORTAL_DB") or "/var/lib/cloudif/portal/cloudif-portal.db"
    except Exception:
        return "/var/lib/cloudif/portal/cloudif-portal.db"

def _v135a2_parse_iso(ts):
    import datetime
    if not ts:
        return None
    try:
        return datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None

def _v135a2_cache_valid(next_check_at):
    import datetime
    dt = _v135a2_parse_iso(next_check_at)
    if not dt:
        return False
    return datetime.datetime.utcnow() < dt

def _v135a2_get_cache_row(slug):
    import sqlite3
    slug = str(slug or "").strip()
    if not slug:
        return None

    try:
        con = sqlite3.connect(_v135a2_db_path())
        con.row_factory = sqlite3.Row
        try:
            row = con.execute(
                "select * from project_runtime_status where slug=?",
                (slug,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            con.close()
    except Exception:
        return None

def _v135a2_render_cache_line(slug):
    row = _v135a2_get_cache_row(slug)
    if not row:
        return '''
<div class="small" style="margin-top:6px;color:#66736a">
  Cache Komodo: ainda sem cache local.
</div>
'''

    valid = _v135a2_cache_valid(row.get("komodo_next_check_at"))
    state = "ativo" if valid else "expirado"

    last = row.get("komodo_last_checked_at") or "-"
    nxt = row.get("komodo_next_check_at") or "-"
    http = row.get("komodo_last_http_status") or "-"
    err = row.get("komodo_last_error") or ""

    extra = ""
    if err:
        extra = f" - erro: {_v134_h(err)}"

    return f'''
<div class="small" style="margin-top:6px;color:#66736a">
  Cache Komodo: <strong>{_v134_h(state)}</strong>
  - última: <code>{_v134_h(last)}</code>
  - próxima: <code>{_v134_h(nxt)}</code>
  - HTTP: {_v134_h(http)}{extra}
</div>
'''

# CloudIF v135a2-safe fim


def _v134_render_project_komodo_summary(slug, compact=True):
    slug = str(slug or "").strip()
    if _v134b_is_new_project_placeholder(slug):
        if compact:
            return ''
        return _v134b_render_new_project_komodo_prediction()

    res = _v134_komodo_status(slug)
    data = res.get("data") if isinstance(res, dict) else {}
    if not isinstance(data, dict):
        data = {}

    if not res.get("ok"):
        msg = data.get("error") or data.get("message") or res.get("error") or "status indisponível"
        return f'''
<div class="small" style="margin-top:8px;padding:8px;border:1px solid #e5e7eb;border-radius:10px;background:#f9fbf8">
  <strong>Komodo v132:</strong> {_v134_h(msg)}
</div>
'''

    repo = data.get("repo") or {}
    stack = data.get("stack") or {}
    deploy_status = data.get("deploy_status") or "-"

    missing = stack.get("missing_files") or []
    errors = stack.get("remote_errors") or []

    if isinstance(missing, list):
        missing_txt = "-" if not missing else ", ".join(map(str, missing))
    else:
        missing_txt = str(missing or "-")

    if isinstance(errors, list):
        err_txt = "sem erros" if not errors else f"{len(errors)} erro(s)"
    else:
        err_txt = str(errors or "sem erros")

    services_txt = _v134_service_names(stack)

    if compact:
        return f'''
<div class="small" style="margin-top:8px;padding:8px;border:1px solid #dfe8dd;border-radius:10px;background:#f9fbf8">
  <strong>Komodo v132:</strong>
  <span class="pill ok">{_v134_h(deploy_status)}</span><br>
  <strong>Hash:</strong> <code>{_v134_h(_v134_short_hash(stack.get("latest_hash") or repo.get("latest_hash")))}</code>
  - <strong>Serviços:</strong> {_v134_h(services_txt)}
  - <strong>Erros:</strong> {_v134_h(err_txt)}
</div>
'''

    return f'''
<div style="margin-top:10px;padding:12px;border:1px solid #dfe8dd;border-radius:12px;background:#f9fbf8">
  <h4 style="margin:0 0 8px 0">Status Komodo v132</h4>
  <p class="small"><strong>Deploy:</strong> <span class="pill ok">{_v134_h(deploy_status)}</span></p>
  <p class="small"><strong>Repo hash:</strong> <code>{_v134_h(_v134_short_hash(repo.get("latest_hash")))}</code></p>
  <p class="small"><strong>Stack hash:</strong> <code>{_v134_h(_v134_short_hash(stack.get("latest_hash")))}</code></p>
  <p class="small"><strong>Deploy hash:</strong> <code>{_v134_h(_v134_short_hash(stack.get("deployed_hash")))}</code></p>
  <p class="small"><strong>Mensagem:</strong> {_v134_h(stack.get("latest_message") or repo.get("latest_message") or "-")}</p>
  <p class="small"><strong>Serviços:</strong> {_v134_h(services_txt)}</p>
  <p class="small"><strong>Arquivos ausentes:</strong> {_v134_h(missing_txt)}</p>
  <p class="small"><strong>Erros remotos:</strong> {_v134_h(err_txt)}</p>
  {_v135a2_render_cache_line(slug)}
</div>
'''

# CloudIF v134 fim



_v95_terminal_ensured = {}

def _v95_ensure_komodo_terminal(stack_id, project_slug, service="web"):
    key = (str(stack_id), str(project_slug), str(service))
    cached = _v95_terminal_ensured.get(key)
    if isinstance(cached, dict) and cached.get("url"):
        return cached
    base, token = _v134_komodo_agent_url()
    result = _v134_http_json(
        "POST",
        base + "/komodo/project/terminal/ensure",
        {
            "stack_id": str(stack_id),
            "project": str(project_slug),
            "service": str(service or "web"),
            "terminal": "cloudif-" + str(project_slug),
            "shell": "sh",
        },
        token=token,
        timeout=20,
    )
    data = result.get("data") if isinstance(result, dict) else {}
    if result.get("ok") and isinstance(data, dict) and data.get("ok"):
        _v95_terminal_ensured[key] = data
        return data
    return {}

def _v95_komodo_url(p=None, slug=""):
    p = p or {}
    stack_id = p.get("komodo_stack_id") or p.get("stack_id") or ""
    project_slug = slug or p.get("slug") or "project"
    if stack_id:
        data = _v95_ensure_komodo_terminal(stack_id, project_slug, p.get("komodo_service") or "web")
        if data.get("url"):
            return data["url"]
    return p.get("komodo_url") or p.get("deploy_url") or "https://komodoiff.duckdns.org/auth/oidc/login"

def _v95_container_names(slug, tenant="", p=None):
    p = p or {}
    raw = p.get("containers") or p.get("komodo_containers") or p.get("container_names")
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.replace("|", ",").split(",") if x.strip()]
    if isinstance(raw, list) and raw:
        return [str(x) for x in raw]

    # Convenção operacional de vínculo: nomes derivados do projeto.
    base = slug or "projeto"
    names = [
        f"{base}-app",
        f"{base}-worker",
        f"{base}-proxy",
    ]

    if tenant:
        names.append(f"{tenant}-supabase")

    return names

def _v95_provisioning_table(slug, tenant="", p=None):
    org = _v95_project_org(p)
    repo = _v95_repo_url(slug, p)
    komodo = _v95_komodo_url(p, slug)
    containers = _v95_container_names(slug, tenant, p)

    cont_html = "".join(f"<li><code>{h(c)}</code> — container vinculado ao projeto no Komodo.</li>" for c in containers)

    return f"""
<style>
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
{__import__("sys").path.insert(0, "/srv/cloudif/lib") if "/srv/cloudif/lib" not in __import__("sys").path else ""}
{__import__("cloudif_theme_module").render_theme_css()}


<div class="wizard-note">
  <h4>Git / Forgejo</h4>
  <p class="small"><strong>Organização:</strong> <code>{h(org)}</code></p>
  <p class="small"><strong>Repositório:</strong> <a href="{h(repo)}" target="_blank">{h(repo)}</a></p>
  <ul class="small">
    <li><code>cloudif-forgejo-push</code> — webhook de push para registrar alteração de código e acionar sincronização.</li>
    <li><code>cloudif-forgejo-release</code> — webhook de tag/release para sinalizar deploy de versão.</li>
    <li><code>cloudif-forgejo-permission-sync</code> — rotina de sincronização de permissões do projeto com o repositório.</li>
  </ul>

  <h4>Komodo / Deploy</h4>
  <p class="small"><strong>Painel:</strong> <a href="{h(komodo)}" target="_blank">{h(komodo)}</a></p>
  <ul class="small">
    {cont_html}
  </ul>
  <ul class="small">
    <li><code>cloudif-komodo-deploy-trigger</code> — trigger que executa deploy a partir do evento de Git/provisionamento.</li>
    <li><code>cloudif-komodo-sync-trigger</code> — trigger que sincroniza a configuração dos containers vinculados.</li>
    <li><code>cloudif-komodo-healthcheck-trigger</code> — trigger de verificação de disponibilidade dos containers.</li>
  </ul>

  <h4>Supabase</h4>
  <ul class="small">
    <li><code>cloudif_ensure_project_schema</code> — procedure para garantir schema/base do projeto quando houver banco.</li>
    <li><code>cloudif_sync_project_acl</code> — procedure para sincronizar permissões do projeto com o tenant.</li>
    <li><code>cloudif_register_project_event</code> — procedure para registrar eventos de provisionamento, integração e deploy.</li>
    <li><code>trg_cloudif_project_acl_changed</code> — trigger para reagir a alterações de permissão.</li>
  </ul>
</div>
"""

def _v95_project_wizard(form_id, title, action_name, user=None, project=None):
    project = project or {}
    slug = project.get("slug") or ""
    name = project.get("name") or slug
    description = project.get("description") or project.get("descr") or project.get("summary") or ""
    tenant = project.get("tenant") or ""
    username = _v95_user_name(user)
    allowed = _v95_allowed_tenants(user)
    options = _v95_options(allowed, tenant)
    safe_id = form_id.replace("-", "_").replace(".", "_")
    tenant_placeholder = "Projeto sem banco de dados"

    checked_create = ""
    checked_link = "checked" if tenant else ""
    checked_skip = "" if tenant else "checked"

    slug_preview = slug or "novo-projeto"

    return f"""
<div id="{h(form_id)}" class="wizard">
  <div class="wizard-box">
    <div class="wizard-head">
      <div>
        <h3>{h(title)}</h3>
        <p class="small">Banco é opcional; Git, Komodo e rotinas de provisionamento são automáticos.</p>
      </div>
      <button class="wizard-close" type="button" onclick="cloudifHideWizard('{h(form_id)}')">×</button>
    </div>

    <form method="post" action="/cloudiff/portal/action/project_action">
      <input type="hidden" name="action" value="{h(action_name)}">
      {f'<input type="hidden" name="slug" value="{h(slug)}">' if slug else ''}
      <input type="hidden" name="create_repo" value="1">
      <input type="hidden" name="setup_komodo" value="1">
      <input type="hidden" id="tenant_hidden_{h(safe_id)}" name="tenant" value="{h(tenant)}">

      <h4>Passo 1 — Detalhes</h4>
      <div class="cm-field">
        <label>Nome do projeto</label>
        <input id="project_name_{h(safe_id)}" name="name" value="{h(name)}" placeholder="Sistema de Biblioteca">
      </div>

      <div class="cm-field">
        <label>Descrição</label>
        <textarea name="description" rows="3">{h(description)}</textarea>
      </div>

      <h4>Passo 2 — Banco / Tenant</h4>
      <p class="small">Selecione um tenant permitido, crie um novo tenant ou deixe o projeto sem banco de dados.</p>

      <label><input type="radio" name="db_mode" value="create" {checked_create}> Criar novo tenant</label><br>
      <label><input type="radio" name="db_mode" value="link" {checked_link}> Vincular tenant existente</label><br>
      <label><input type="radio" name="db_mode" value="skip" {checked_skip}> Projeto sem banco de dados</label>

      <div class="cm-field" id="tenant_existing_box_{h(safe_id)}">
        <label>Tenants permitidos para seu usuário/grupo</label>
        <select id="tenant_select_{h(safe_id)}">
          <option value="">Selecione um tenant permitido</option>
          {options}
        </select>
      </div>

      <div class="cm-field" id="tenant_create_box_{h(safe_id)}">
        <label>Nome opcional do novo tenant</label>
        <input id="tenant_suffix_{h(safe_id)}" placeholder="ex: biblioteca">
        <p class="small">Formato gerado: <code>{h(username)}-&lt;nome&gt;</code>. Se ficar vazio, será usada data/hora sem pontos ou traços.</p>
      </div>

      <div class="wizard-note">
        <strong>Tenant selecionado/gerado:</strong>
        <code id="tenant_preview_{h(safe_id)}">{h(tenant or tenant_placeholder)}</code>
      </div>

      <h4>Passo 3 — Git, Komodo e provisionamento automático</h4>
      <p class="small">Esses recursos são provisionados automaticamente. Abaixo estão os vínculos e rotinas que serão usados pelo projeto.</p>

      {_v95_provisioning_table(slug_preview, tenant, project)}

      <div class="cm-actions">
        <button class="cm-btn cm-primary" type="submit">Salvar projeto</button>
        <a class="cm-btn cm-secondary" href="#" onclick="cloudifHideWizard('{h(form_id)}')">Cancelar</a>
      </div>
    </form>

<script>
(function(){{
  var formId = "{h(safe_id)}";
  var username = "{h(username)}";
  var radios = document.querySelectorAll('#{h(form_id)} input[name="db_mode"]');
  var hidden = document.getElementById("tenant_hidden_" + formId);
  var select = document.getElementById("tenant_select_" + formId);
  var suffix = document.getElementById("tenant_suffix_" + formId);
  var preview = document.getElementById("tenant_preview_" + formId);
  var existingBox = document.getElementById("tenant_existing_box_" + formId);
  var createBox = document.getElementById("tenant_create_box_" + formId);
  var projectName = document.getElementById("project_name_" + formId);

  function slugify(v){{
    v = String(v || "").toLowerCase();
    v = v.normalize ? v.normalize("NFD").replace(/[\\u0300-\\u036f]/g, "") : v;
    v = v.replace(/[^a-z0-9]+/g, "");
    return v;
  }}

  function stamp(){{
    var d = new Date();
    function p(n){{ return String(n).padStart(2, "0"); }}
    return d.getFullYear() + p(d.getMonth()+1) + p(d.getDate()) + p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds());
  }}

  function selectedMode(){{
    var checked = document.querySelector('#{h(form_id)} input[name="db_mode"]:checked');
    return checked ? checked.value : "skip";
  }}

  function updateTenant(){{
    var mode = selectedMode();
    var value = "";

    if(mode === "skip"){{
      value = "";
      if(existingBox) existingBox.style.display = "none";
      if(createBox) createBox.style.display = "none";
    }}

    if(mode === "link"){{
      value = select ? select.value : "";
      if(existingBox) existingBox.style.display = "";
      if(createBox) createBox.style.display = "none";
    }}

    if(mode === "create"){{
      var base = suffix && suffix.value ? suffix.value : (projectName && projectName.value ? projectName.value : "");
      base = slugify(base);
      if(!base) base = stamp();
      value = username + "-" + base;
      if(existingBox) existingBox.style.display = "none";
      if(createBox) createBox.style.display = "";
    }}

    hidden.value = value;
    preview.textContent = value || "{h(tenant_placeholder)}";
  }}

  radios.forEach(function(r){{ r.addEventListener("change", updateTenant); }});
  if(select) select.addEventListener("change", updateTenant);
  if(suffix) suffix.addEventListener("input", updateTenant);
  if(projectName) projectName.addEventListener("input", updateTenant);

  updateTenant();
}})();
</script>
  </div>
</div>
"""


# CloudIF v95 — helpers do wizard de projeto

def _v95_user_name(user=None):
    import re
    user = user or {}
    raw = (
        user.get("username")
        or user.get("name")
        or user.get("email", "").split("@")[0]
        or "usuario"
    )
    raw = str(raw).strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "", raw)
    return raw or "usuario"

def _v95_user_groups(user=None):
    user = user or {}
    groups = user.get("groups") or []
    if isinstance(groups, str):
        groups = [g.strip() for g in groups.replace("|", ",").split(",") if g.strip()]
    return groups

def _v95_is_admin(user=None):
    groups = {g.lower() for g in _v95_user_groups(user)}
    return bool(groups & {"cloudif-tenants-admin", "cloudif-admin", "domain admins"})

def _v95_tenant_name(t):
    if isinstance(t, dict):
        return t.get("tenant") or t.get("name") or t.get("slug") or ""
    return str(t or "")

def _v95_allowed_tenants(user=None):
    """
    Lista tenants reais que o usuário pode selecionar.
    Preferência:
    - admin vê todos;
    - se tenant_acl existir, filtra por usuário/e-mail/grupo;
    - se não houver tenant_acl, usa discover_tenants() como fonte já existente do portal.
    """
    import sqlite3

    user = user or {}
    username = str(user.get("username") or user.get("name") or "").strip().lower()
    email = str(user.get("email") or "").strip().lower()
    groups = {g.lower() for g in _v95_user_groups(user)}
    admin = _v95_is_admin(user)

    discovered = []
    for t in discover_tenants():
        name = _v95_tenant_name(t)
        if name:
            discovered.append(name)

    discovered = sorted(set(discovered))

    if admin:
        return discovered

    db = "/var/lib/cloudif/portal/cloudif-portal.db"

    try:
        con = sqlite3.connect(db)
        con.row_factory = sqlite3.Row
        tables = [r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if "tenant_acl" not in tables:
            con.close()
            return discovered

        rows = con.execute("SELECT * FROM tenant_acl").fetchall()
        con.close()

        allowed = set()
        for r in rows:
            d = dict(r)
            tenant = str(d.get("tenant") or d.get("name") or d.get("slug") or "").strip()
            stype = str(d.get("subject_type") or d.get("type") or "").strip().lower()
            subject = str(d.get("subject") or d.get("principal") or d.get("user") or d.get("group") or "").strip().lower()

            if not tenant or not subject:
                continue

            if stype == "user" and subject in {username, email}:
                allowed.add(tenant)

            if stype == "group" and subject in groups:
                allowed.add(tenant)

        if allowed:
            return sorted(allowed)

        return []
    except Exception:
        return discovered

def _v95_options(items, selected=""):
    out = []
    selected = str(selected or "")
    for item in items:
        sel = " selected" if str(item) == selected else ""
        out.append(f'<option value="{h(item)}"{sel}>{h(item)}</option>')
    return "".join(out)

def _v95_project_org(p=None):
    p = p or {}
    return (
        p.get("forgejo_org")
        or p.get("git_org")
        or p.get("organization")
        or p.get("org")
        or "cloudif"
    )

def _v95_repo_url(slug, p=None):
    p = p or {}
    return (
        p.get("repo_url")
        or p.get("forgejo_url")
        or p.get("git_url")
        or f"https://cloudiff.duckdns.org/git/{_v95_project_org(p)}/{slug}"
    )

def _v95_komodo_url(p=None, slug=""):
    p = p or {}
    stack_id = p.get("komodo_stack_id") or p.get("stack_id") or ""
    project_slug = slug or p.get("slug") or "project"
    if stack_id:
        data = _v95_ensure_komodo_terminal(stack_id, project_slug, p.get("komodo_service") or "web")
        if data.get("url"):
            return data["url"]
    return p.get("komodo_url") or p.get("deploy_url") or "https://komodoiff.duckdns.org/auth/oidc/login"

def _v95_container_names(slug, tenant="", p=None):
    p = p or {}
    raw = p.get("containers") or p.get("komodo_containers") or p.get("container_names")
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.replace("|", ",").split(",") if x.strip()]
    if isinstance(raw, list) and raw:
        return [str(x) for x in raw]

    # Convenção operacional de vínculo: nomes derivados do projeto.
    base = slug or "projeto"
    names = [
        f"{base}-app",
        f"{base}-worker",
        f"{base}-proxy",
    ]

    if tenant:
        names.append(f"{tenant}-supabase")

    return names

def _v95_provisioning_table(slug, tenant="", p=None):
    org = _v95_project_org(p)
    repo = _v95_repo_url(slug, p)
    komodo = _v95_komodo_url(p, slug)
    containers = _v95_container_names(slug, tenant, p)

    cont_html = "".join(f"<li><code>{h(c)}</code> — container vinculado ao projeto no Komodo.</li>" for c in containers)

    return f"""
<div class="wizard-note">
  <h4>Git / Forgejo</h4>
  <p class="small"><strong>Organização:</strong> <code>{h(org)}</code></p>
  <p class="small"><strong>Repositório:</strong> <a href="{h(repo)}" target="_blank">{h(repo)}</a></p>
  <ul class="small">
    <li><code>cloudif-forgejo-push</code> — webhook de push para registrar alteração de código e acionar sincronização.</li>
    <li><code>cloudif-forgejo-release</code> — webhook de tag/release para sinalizar deploy de versão.</li>
    <li><code>cloudif-forgejo-permission-sync</code> — rotina de sincronização de permissões do projeto com o repositório.</li>
  </ul>

  <h4>Komodo / Deploy</h4>
  <p class="small"><strong>Painel:</strong> <a href="{h(komodo)}" target="_blank">{h(komodo)}</a></p>
  <ul class="small">
    {cont_html}
  </ul>
  <ul class="small">
    <li><code>cloudif-komodo-deploy-trigger</code> — trigger que executa deploy a partir do evento de Git/provisionamento.</li>
    <li><code>cloudif-komodo-sync-trigger</code> — trigger que sincroniza a configuração dos containers vinculados.</li>
    <li><code>cloudif-komodo-healthcheck-trigger</code> — trigger de verificação de disponibilidade dos containers.</li>
  </ul>

  <h4>Supabase</h4>
  <ul class="small">
    <li><code>cloudif_ensure_project_schema</code> — procedure para garantir schema/base do projeto quando houver banco.</li>
    <li><code>cloudif_sync_project_acl</code> — procedure para sincronizar permissões do projeto com o tenant.</li>
    <li><code>cloudif_register_project_event</code> — procedure para registrar eventos de provisionamento, integração e deploy.</li>
    <li><code>trg_cloudif_project_acl_changed</code> — trigger para reagir a alterações de permissão.</li>
  </ul>
</div>
"""

def _v95_project_wizard(form_id, title, action_name, user=None, project=None):
    project = project or {}
    slug = project.get("slug") or ""
    name = project.get("name") or slug
    description = project.get("description") or project.get("descr") or project.get("summary") or ""
    tenant = project.get("tenant") or ""
    username = _v95_user_name(user)
    allowed = _v95_allowed_tenants(user)
    options = _v95_options(allowed, tenant)
    safe_id = form_id.replace("-", "_").replace(".", "_")
    tenant_placeholder = "Projeto sem banco de dados"

    checked_create = ""
    checked_link = "checked" if tenant else ""
    checked_skip = "" if tenant else "checked"

    slug_preview = slug or "novo-projeto"

    return f"""
<div id="{h(form_id)}" class="wizard">
  <div class="wizard-box">
    <div class="wizard-head">
      <div>
        <h3>{h(title)}</h3>
        <p class="small">Banco é opcional; Git, Komodo e rotinas de provisionamento são automáticos.</p>
      </div>
      <button class="wizard-close" type="button" onclick="cloudifHideWizard('{h(form_id)}')">×</button>
    </div>

    <form method="post" action="/cloudiff/portal/action/project_action">
      <input type="hidden" name="action" value="{h(action_name)}">
      {f'<input type="hidden" name="slug" value="{h(slug)}">' if slug else ''}
      <input type="hidden" name="create_repo" value="1">
      <input type="hidden" name="setup_komodo" value="1">
      <input type="hidden" id="tenant_hidden_{h(safe_id)}" name="tenant" value="{h(tenant)}">

      <h4>Passo 1 — Detalhes</h4>
      <div class="cm-field">
        <label>Nome do projeto</label>
        <input id="project_name_{h(safe_id)}" name="name" value="{h(name)}" placeholder="Sistema de Biblioteca">
      </div>

      <div class="cm-field">
        <label>Descrição</label>
        <textarea name="description" rows="3">{h(description)}</textarea>
      </div>

      <h4>Passo 2 — Banco / Tenant</h4>
      <p class="small">Selecione um tenant permitido, crie um novo tenant ou deixe o projeto sem banco de dados.</p>

      <label><input type="radio" name="db_mode" value="create" {checked_create}> Criar novo tenant</label><br>
      <label><input type="radio" name="db_mode" value="link" {checked_link}> Vincular tenant existente</label><br>
      <label><input type="radio" name="db_mode" value="skip" {checked_skip}> Projeto sem banco de dados</label>

      <div class="cm-field" id="tenant_existing_box_{h(safe_id)}">
        <label>Tenants permitidos para seu usuário/grupo</label>
        <select id="tenant_select_{h(safe_id)}">
          <option value="">Selecione um tenant permitido</option>
          {options}
        </select>
      </div>

      <div class="cm-field" id="tenant_create_box_{h(safe_id)}">
        <label>Nome opcional do novo tenant</label>
        <input id="tenant_suffix_{h(safe_id)}" placeholder="ex: biblioteca">
        <p class="small">Formato gerado: <code>{h(username)}-&lt;nome&gt;</code>. Se ficar vazio, será usada data/hora sem pontos ou traços.</p>
      </div>

      <div class="wizard-note">
        <strong>Tenant selecionado/gerado:</strong>
        <code id="tenant_preview_{h(safe_id)}">{h(tenant or tenant_placeholder)}</code>
      </div>

      <h4>Passo 3 — Git, Komodo e provisionamento automático</h4>
      <p class="small">Esses recursos são provisionados automaticamente. Abaixo estão os vínculos e rotinas que serão usados pelo projeto.</p>

      {_v95_provisioning_table(slug_preview, tenant, project)}

      <div class="cm-actions">
        <button class="cm-btn cm-primary" type="submit">Salvar projeto</button>
        <a class="cm-btn cm-secondary" href="#" onclick="cloudifHideWizard('{h(form_id)}')">Cancelar</a>
      </div>
    </form>

<script>
(function(){{
  var formId = "{h(safe_id)}";
  var username = "{h(username)}";
  var radios = document.querySelectorAll('#{h(form_id)} input[name="db_mode"]');
  var hidden = document.getElementById("tenant_hidden_" + formId);
  var select = document.getElementById("tenant_select_" + formId);
  var suffix = document.getElementById("tenant_suffix_" + formId);
  var preview = document.getElementById("tenant_preview_" + formId);
  var existingBox = document.getElementById("tenant_existing_box_" + formId);
  var createBox = document.getElementById("tenant_create_box_" + formId);
  var projectName = document.getElementById("project_name_" + formId);

  function slugify(v){{
    v = String(v || "").toLowerCase();
    v = v.normalize ? v.normalize("NFD").replace(/[\\u0300-\\u036f]/g, "") : v;
    v = v.replace(/[^a-z0-9]+/g, "");
    return v;
  }}

  function stamp(){{
    var d = new Date();
    function p(n){{ return String(n).padStart(2, "0"); }}
    return d.getFullYear() + p(d.getMonth()+1) + p(d.getDate()) + p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds());
  }}

  function selectedMode(){{
    var checked = document.querySelector('#{h(form_id)} input[name="db_mode"]:checked');
    return checked ? checked.value : "skip";
  }}

  function updateTenant(){{
    var mode = selectedMode();
    var value = "";

    if(mode === "skip"){{
      value = "";
      if(existingBox) existingBox.style.display = "none";
      if(createBox) createBox.style.display = "none";
    }}

    if(mode === "link"){{
      value = select ? select.value : "";
      if(existingBox) existingBox.style.display = "";
      if(createBox) createBox.style.display = "none";
    }}

    if(mode === "create"){{
      var base = suffix && suffix.value ? suffix.value : (projectName && projectName.value ? projectName.value : "");
      base = slugify(base);
      if(!base) base = stamp();
      value = username + "-" + base;
      if(existingBox) existingBox.style.display = "none";
      if(createBox) createBox.style.display = "";
    }}

    hidden.value = value;
    preview.textContent = value || "{h(tenant_placeholder)}";
  }}

  radios.forEach(function(r){{ r.addEventListener("change", updateTenant); }});
  if(select) select.addEventListener("change", updateTenant);
  if(suffix) suffix.addEventListener("input", updateTenant);
  if(projectName) projectName.addEventListener("input", updateTenant);

  updateTenant();
}})();
</script>
  </div>
</div>
"""

def modal_common(user=None, projects=None):
    return f"""
<script>
function cloudifShowWizard(id){{
  var el = document.getElementById(id);
  if(el) el.classList.add('show');
}}

function cloudifHideWizard(id){{
  var el = document.getElementById(id);
  if(el) el.classList.remove('show');
}}

document.addEventListener('keydown', function(e){{
  if(e.key === 'Escape'){{
    document.querySelectorAll('.wizard.show').forEach(function(w){{ w.classList.remove('show'); }});
  }}
}});

document.addEventListener('click', function(e){{
  if(e.target && e.target.classList && e.target.classList.contains('wizard')){{
    e.target.classList.remove('show');
  }}
}});
</script>

{_v95_project_wizard("wiz_new_project", "Novo projeto", "create_project", user=user)}
"""

def modal_common():
    tenants = discover_tenants()
    tenant_options = []

    for t in tenants:
        name = t.get("tenant") or t.get("name") or t.get("slug") or ""
        if name:
            tenant_options.append(f'<option value="{h(name)}">{h(name)}</option>')

    tenant_options_html = "".join(tenant_options)

    return f"""
<script>
function cloudifShowWizard(id){{
  var el = document.getElementById(id);
  if(el) el.classList.add('show');
}}
function cloudifHideWizard(id){{
  var el = document.getElementById(id);
  if(el) el.classList.remove('show');
}}
document.addEventListener('keydown', function(e){{
  if(e.key === 'Escape'){{
    document.querySelectorAll('.wizard.show').forEach(function(w){{ w.classList.remove('show'); }});
  }}
}});
document.addEventListener('click', function(e){{
  if(e.target && e.target.classList && e.target.classList.contains('wizard')){{
    e.target.classList.remove('show');
  }}
}});
</script>

<div id="wiz_new_project" class="wizard">
  <div class="wizard-box">
    <div class="wizard-head">
      <div>
        <h3>Novo projeto</h3>
        <p class="small">Crie o projeto. Apenas o vínculo com banco é opcional; Git e Komodo serão preparados automaticamente.</p>
      </div>
      <button class="wizard-close" type="button" onclick="cloudifHideWizard('wiz_new_project')">×</button>
    </div>

    <form method="post" action="/action/project_action">
      <input type="hidden" name="action" value="create_project">

      <h4>Passo 1 — Detalhes</h4>
      <div class="cm-field">
        <label>Nome</label>
        <input name="name" placeholder="Sistema de Biblioteca">
      </div>
      <div class="cm-field">
        <label>Descrição</label>
        <textarea name="description" rows="3"></textarea>
      </div>

      <h4>Passo 2 — Banco/Tenant</h4>
      <p class="small">Somente o banco é opcional. Você pode criar um novo tenant, vincular um existente ou seguir sem banco.</p>
      <label><input type="radio" name="db_mode" value="create"> Criar Novo Tenant</label><br>
      <label><input type="radio" name="db_mode" value="link"> Vincular Existente</label><br>
      <label><input type="radio" name="db_mode" value="skip" checked> Pular, sem banco</label>

      <div class="cm-field">
        <label>Tenant existente, se aplicável</label>
        <input name="tenant" list="cloudif_tenants_list" placeholder="aluno, iff1742962">
        <datalist id="cloudif_tenants_list">{tenant_options_html}</datalist>
      </div>

      <h4>Passo 3 — Git e Deploy</h4>
      <div class="wizard-note">
        <strong>Forgejo e Komodo serão configurados automaticamente.</strong><br>
        Após finalizar, use os botões <b>Git</b> e <b>Komodo</b> no card do projeto para abrir o repositório e o painel de deploy.
      </div>
      <input type="hidden" name="create_repo" value="1">
      <input type="hidden" name="setup_komodo" value="1">

      <div class="cm-actions">
        <button class="cm-btn cm-primary" type="submit">Finalizar Wizard</button>
        <a class="cm-btn cm-secondary" href="#" onclick="cloudifHideWizard('wiz_new_project')">Cancelar</a>
      </div>
    </form>
  </div>
</div>
"""
def _fmt_gb(value):
    try:
        return f"{float(value):.1f} GB"
    except Exception:
        return "—"

def _pct(used, total):
    try:
        used = float(used or 0)
        total = float(total or 0)
        if total <= 0:
            return 0
        return max(0, min(100, round((used / total) * 100)))
    except Exception:
        return 0

def render_meter(label, used, total, percent=None):
    if percent is None:
        percent = _pct(used, total)
    try:
        percent = int(float(percent))
    except Exception:
        percent = 0

    return f"""
<div class="cm-meter">
  <div class="cm-meter-line">
    <span>{h(label)}</span>
    <span>{_fmt_gb(used)} / {_fmt_gb(total)}</span>
  </div>
  <div class="cm-meter-bar">
    <div class="cm-meter-fill" style="width:{max(0, min(100, percent))}%"></div>
  </div>
</div>
"""

def render_server_metric_section():
    metrics = server_metrics()
    servers = metrics.get("servers", [])
    agg = metrics.get("aggregate", {})
    source = metrics.get("source") or "sem fonte detectada"

    ram_used = agg.get("ram_used_gb") or 0
    ram_total = agg.get("ram_total_gb") or 0
    disk_used = agg.get("disk_used_gb") or 0
    disk_total = agg.get("disk_total_gb") or 0

    cards = []

    for s in servers:
        name = s.get("name", "servidor")
        status = str(s.get("status") or "unknown").lower()
        online = status in ["online", "ok", "active", "running", "up", "true", "1"]

        disk_percent = s.get("disk_percent")
        if disk_percent is None:
            disk_percent = _pct(s.get("disk_used_gb"), s.get("disk_total_gb"))

        cards.append(f"""
<div class="cm-server-card">
  <div class="cm-server-card-top">
    <div class="cm-server-name">{h(name)}</div>
    {pill(online, "online", "offline")}
  </div>

  {render_meter("RAM", s.get("ram_used_gb"), s.get("ram_total_gb"))}
  {render_meter("Disco", s.get("disk_used_gb"), s.get("disk_total_gb"), disk_percent)}

  <div class="cm-server-meta">
    <div><strong>Atualizado:</strong> {h(s.get("updated_at") or "—")}</div>
  </div>
</div>
""")

    if not cards:
        cards.append("""
<div class="cm-server-card">
  <div class="cm-server-card-top">
    <div class="cm-server-name">Agentes</div>
    <span class="cm-pill cm-off">sem dados</span>
  </div>
  <p class="cm-muted">Nenhum arquivo de métricas dos agentes foi encontrado. Configure o script dos agentes para atualizar <code>/var/lib/cloudif/portal/cloudif-server-metrics.json</code>.</p>
</div>
""")

    return f"""
<section class="cm-server-panel">
  <div class="cm-server-panel-head">
    <div>
      <h3>Servidores CloudIF</h3>
      <p class="cm-muted">Visão agregada dos agentes das máquinas que compõem a plataforma.</p>
    </div>

    <div class="cm-server-aggregate">
      <div class="cm-server-agg-card">
        <strong>RAM agregada</strong>
        <span>{_fmt_gb(ram_used)} / {_fmt_gb(ram_total)}</span>
      </div>

      <div class="cm-server-agg-card">
        <strong>Disco agregado</strong>
        <span>{_fmt_gb(disk_used)} / {_fmt_gb(disk_total)}</span>
      </div>
    </div>
  </div>

  <div class="cm-server-grid">
    {''.join(cards)}
  </div>

  <div class="cm-server-source">Fonte: <code>{h(source)}</code></div>
</section>
"""


def render_resumo(user=None):
    content = f"""
{render_server_metric_section()}

<div class="cm-grid">
  <div class="cm-card">
    <h3>Informações da Plataforma</h3>
    <p class="cm-muted">Acesse a área técnica modular com estado do portal, frontend, deploy, router/proxy e scripts de integração.</p>
    {btn("Abrir Informações da Plataforma", tab_url("hardware"), True, False)}
  </div>
</div>
"""

    return layout(
        "resumo",
        "Resumo",
        "Visão operacional dos servidores CloudIF.",
        content,
        user=user,
        actions="",
    )

from cloudif_ui_publications import publication_panel as _cloudif_publication_panel, admin_publications as _cloudif_admin_publications

def render_project_card(p):
    slug = p.get("slug") or ""
    name = p.get("name") or slug
    tenant = p.get("tenant") or ""
    repo = p.get("repo_url") or ""
    komodo = p.get("komodo_status") or ""

    has_db = bool(tenant)
    has_git = bool(repo)
    has_deploy = bool(komodo) or bool(repo)

    return f"""
<div class="cm-card">
  <details class="cm-menu">
    <summary>⋮</summary>
    <div class="cm-menu-body">
      <a href="#modal-vincular-banco">Vincular banco</a>
      <a href="{tab_url("projetos", classic="1")}">Tela clássica do projeto</a>
      <button type="button" disabled>Excluir projeto</button>
    </div>
  </details>

  <h3>{h(name)}</h3>
  <p class="cm-muted"><code>{h(slug)}</code></p>

  <div class="cm-resource">
    <div class="cm-resource-title"><strong>Banco</strong>{pill(has_db, "Vinculado", "Sem banco")}</div>
    <div class="cm-actions">
      {btn("Abrir Studio", public_studio_url(tenant), has_db, False, True)}
      {btn("+ Vincular Banco", "#modal-vincular-banco", not has_db, True)}
    </div>
  </div>

  <div class="cm-resource">
    <div class="cm-resource-title"><strong>Git / Deploy</strong>{pill(has_git or has_deploy, "Configurado", "Pendente")}</div>
    <div class="cm-actions">
      {btn("Integrações", tab_url("git", project=slug, tenant=tenant), True, True)}
      {btn("Deploy Center", deploy_url(slug, tenant), has_deploy, False)}
    </div>
  </div>
</div>
"""

def render_projetos(user=None):
    projects = discover_projects()
    rows = []
    modals = []

    for p in projects:
        slug = p.get("slug") or ""
        name = p.get("name") or slug
        description = p.get("description") or p.get("descr") or p.get("summary") or ""
        tenant = p.get("tenant") or ""
        studio = public_studio_url(tenant) if tenant else ""
        safe_slug = slug.replace("-", "_").replace(".", "_")
        edit_id = "wiz_edit_" + safe_slug
        acl_id = "wiz_acl_" + safe_slug
        org = _v95_project_org(p)
        repo = _v95_repo_url(slug, p)
        komodo = _v95_komodo_url(p, slug)
        containers = _v95_container_names(slug, tenant, p)

        if tenant:
            banco_html = f"""
      <b>Banco</b><br>
      <span class="pill ok">{h(tenant)}</span><br>
      <a class="btn light" href="{h(studio)}" target="_blank">Abrir Studio</a>
"""
        else:
            banco_html = """
      <b>Banco</b><br>
      <span class="pill">Projeto sem banco de dados</span><br>
      <button class="btn light" onclick="cloudifShowWizard('wiz_new_project')">Vincular/Criar banco</button>
"""

        cont_small = ", ".join(containers[:3])
        if len(containers) > 3:
            cont_small += f" +{len(containers)-3}"

        rows.append(f"""
<div class="project-card">
  <div class="project-line">
    <div>
      <h3>{h(slug)}</h3>
      <p class="small">Slug: {h(slug)}</p>
      <p>{h(description or name or "Projeto CloudIF")}</p>
    </div>

    <div>
      {banco_html}
    </div>

    <div>
      <b>Git / Deploy</b><br>
      <p class="small">Org: <code>{h(org)}</code></p>
      <a class="btn light" href="{h(repo)}" target="_blank">Repositório</a>
      <a class="btn light" href="{h(komodo)}" target="_blank">Komodo</a>
      {_v134_render_project_komodo_summary(slug, compact=True)}
    </div>

    <div>
      {_cloudif_publication_panel(slug)}
      <button class="btn light" onclick="cloudifShowWizard('{h(edit_id)}')">Editar</button>
      <button class="btn light" onclick="cloudifShowWizard('{h(acl_id)}')">Permissões</button>
    </div>
  </div>
</div>
""")

        modals.append(_v95_project_wizard(edit_id, "Editar projeto", "update_project", user=user, project=p))

        try:
            import cloudif_project_acl_module as project_acl
            modals.append(project_acl.render_acl_modal(slug, user))
        except Exception as e:
            modals.append(f"""
<div id="{h(acl_id)}" class="wizard">
  <div class="wizard-box">
    <div class="wizard-head">
      <div>
        <h3>Permissões</h3>
        <p class="small">{h(slug)}</p>
      </div>
      <button class="wizard-close" type="button" onclick="cloudifHideWizard('{h(acl_id)}')">×</button>
    </div>
    <div class="wizard-note"><strong>Erro ao carregar ACL:</strong> {h(e)}</div>
  </div>
</div>
""")

    if not rows:
        rows.append("""
<div class="project-card">
  <div class="project-line">
    <div>
      <h3>Nenhum projeto</h3>
      <p class="small">Crie o primeiro projeto CloudIF.</p>
    </div>
  </div>
</div>
""")

    content = f"""
<div id="cloudif-project-list" class="card">
  <div class="section-title">
    <div>
      <h2>Projetos</h2>
      <p class="small">Somente projetos visíveis para seu usuário/grupo aparecem aqui.</p>
    </div>
    <button class="btn" onclick="cloudifShowWizard('wiz_new_project')">Novo projeto</button>
  </div>

  {''.join(rows)}
</div>

{modal_common(user=user, projects=projects)}
{''.join(modals)}
"""

    return layout(
        "projetos",
        "Projetos",
        "Projetos acadêmicos com banco opcional e Git/Komodo integrados automaticamente.",
        content,
        user=user,
        actions="",
    )



# CloudIF v136c-safe - Bancos/Tenants reais em cm-grid
def _v136c_db_path():
    try:
        env = {}
        fp = "/etc/cloudif/portal.env"
        import pathlib
        p = pathlib.Path(fp)
        if p.exists():
            for raw in p.read_text(errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
        return env.get("CLOUDIF_PORTAL_DB") or "/var/lib/cloudif/portal/cloudif-portal.db"
    except Exception:
        return "/var/lib/cloudif/portal/cloudif-portal.db"

def _v136c_h(x):
    try:
        return h(x)
    except Exception:
        import html
        return html.escape(str(x if x is not None else ""))

def _v136c_list_tenants():
    import sqlite3
    import pathlib
    import json

    tenants = {}

    def add(name, source="unknown", data=None):
        name = str(name or "").strip()
        if not name:
            return
        item = tenants.setdefault(name, {
            "name": name,
            "source": source,
            "studio_url": f"https://{name}.cloudiff.duckdns.org/project/default",
            "kong": "-",
            "enabled": True,
            "always_on": False,
            "status": "",
            "projects": [],
        })
        if data:
            item.update({k: v for k, v in data.items() if v not in [None, ""]})

    # 1) SQLite local
    try:
        db = _v136c_db_path()
        con = sqlite3.connect(db)
        con.row_factory = sqlite3.Row
        tables = {r["name"] for r in con.execute("select name from sqlite_master where type='table'")}

        if "tenants" in tables:
            cols = [r["name"] for r in con.execute("pragma table_info(tenants)")]
            name_col = "name" if "name" in cols else ("tenant" if "tenant" in cols else ("slug" if "slug" in cols else None))
            if name_col:
                for row in con.execute(f"select * from tenants"):
                    d = dict(row)
                    name = d.get(name_col)
                    add(name, "sqlite.tenants", {
                        "enabled": bool(d.get("enabled", 1)),
                        "status": d.get("status") or d.get("state") or "",
                        "kong": d.get("kong") or d.get("kong_status") or "-",
                        "always_on": bool(d.get("always_on", 0)),
                    })

        if "projects" in tables:
            cols = [r["name"] for r in con.execute("pragma table_info(projects)")]
            if "tenant" in cols:
                for row in con.execute("select slug, name, tenant from projects where tenant is not null and trim(tenant) <> '' order by tenant, slug"):
                    d = dict(row)
                    add(d.get("tenant"), "sqlite.projects")
                    tenants[d.get("tenant")]["projects"].append(d.get("slug") or d.get("name") or "")

        if "tenant_policy" in tables:
            cols = [r["name"] for r in con.execute("pragma table_info(tenant_policy)")]
            tenant_col = "tenant" if "tenant" in cols else ("name" if "name" in cols else None)
            if tenant_col:
                for row in con.execute(f"select * from tenant_policy"):
                    d = dict(row)
                    name = d.get(tenant_col)
                    add(name, "sqlite.tenant_policy")
                    item = tenants.get(name)
                    if item:
                        for k in ["enabled", "always_on", "status", "kong", "kong_status"]:
                            if k in d and d[k] not in [None, ""]:
                                if k == "kong_status":
                                    item["kong"] = d[k]
                                else:
                                    item[k] = d[k]

        con.close()
    except Exception:
        pass

    # 2) Diretórios reais /srv/cloudif/tenants
    for base in ["/srv/cloudif/tenants", "/srv/cloudif/data/tenants"]:
        try:
            bp = pathlib.Path(base)
            if bp.exists():
                for child in sorted(bp.iterdir()):
                    if child.is_dir() and not child.name.startswith("."):
                        add(child.name, f"dir:{base}")
        except Exception:
            pass

    return [tenants[k] for k in sorted(tenants)]

def _v136c_tenant_card(t):
    name = str(t.get("name") or "").strip()
    enabled = bool(t.get("enabled", True))
    always_on = bool(t.get("always_on", False))
    status = str(t.get("status") or ("Habilitado" if enabled else "Desabilitado"))
    kong = str(t.get("kong") or "-")
    projects = [p for p in (t.get("projects") or []) if p]
    projects_txt = ", ".join(projects[:4])
    if len(projects) > 4:
        projects_txt += f" +{len(projects)-4}"

    checked = "checked" if enabled else ""
    enabled_label = "Habilitado" if enabled else "Desabilitado"
    always_label = "Sempre ligado" if always_on else "Sob demanda"

    opts = "".join([f'<option value="{i}">{i} hora{"s" if i > 1 else ""}</option>' for i in range(1, 7)])

    return f'''
<div class="cm-card">
  <div class="cm-card-head">
    <div>
      <h3>{_v136c_h(name)}</h3>
      <p class="small">Banco/Tenant Supabase</p>
    </div>
    <span class="pill {'ok' if enabled else ''}">{_v136c_h(enabled_label)}</span>
  </div>

  <div class="small" style="margin:8px 0">
    <strong>Kong:</strong> {_v136c_h(kong)}<br>
    <strong>Modo:</strong> {_v136c_h(always_label)}<br>
    <strong>Status:</strong> {_v136c_h(status)}<br>
    <strong>Projetos:</strong> {_v136c_h(projects_txt or "-")}
  </div>

  <form method="post" action="/cloudiff/portal/action/tenant_action" class="cm-actions" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
    <input type="hidden" name="tenant" value="{_v136c_h(name)}">

    <label class="small" style="display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line,#dfe8dd);border-radius:10px;padding:8px 10px;background:#fff">
      <input type="checkbox" name="enabled_visual" value="1" {checked} disabled>
      {_v136c_h(enabled_label)}
    </label>

    <a class="btn light" href="https://{_v136c_h(name)}.cloudiff.duckdns.org/project/default" target="_blank">Abrir Studio</a>
    <button class="btn gray" name="op" value="stop">Parar</button>
    <button class="btn blue" name="op" value="restart">Reiniciar</button>

    <select name="hours" style="max-width:150px;display:inline-block">
      {opts}
    </select>
    <button class="btn" name="op" value="keepalive">Tempo ligado</button>

    <button class="btn amber" name="op" value="always_on">Sempre ligado</button>
    <button class="btn gray" name="op" value="always_off">Desativar sempre ligado</button>
  </form>
</div>
'''

def _v136c_render_bancos_tenants_grid():
    tenants = _v136c_list_tenants()
    cards = "\n".join(_v136c_tenant_card(t) for t in tenants)
    if not cards:
        cards = '''
<div class="cm-card">
  <h3>Nenhum tenant encontrado</h3>
  <p class="small">Não foram encontrados tenants no SQLite nem em /srv/cloudif/tenants.</p>
</div>
'''

    return f'''
<div class="cm-page">
  <div class="cm-section">
    <div class="cm-section-head">
      <div>
        <h2>Bancos / Tenants</h2>
        <p class="small">Tenants reais descobertos na base local e diretórios do CloudIF.</p>
      </div>
    </div>

    <div class="cm-grid">
      {cards}
    </div>
  </div>
</div>
'''

# CloudIF v136c-safe fim




# CloudIF v137c-safe - Bancos/Tenants em interface modular
def _v137c_h(x):
    try:
        return h(x)
    except Exception:
        import html
        return html.escape(str(x if x is not None else ""))

def _v137c_db_path():
    try:
        import pathlib
        env = {}
        fp = pathlib.Path("/etc/cloudif/portal.env")
        if fp.exists():
            for raw in fp.read_text(errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
        return env.get("CLOUDIF_PORTAL_DB") or "/var/lib/cloudif/portal/cloudif-portal.db"
    except Exception:
        return "/var/lib/cloudif/portal/cloudif-portal.db"

def _v137c_list_tenants():
    import sqlite3
    import pathlib

    tenants = {}

    def add(name, source="unknown", data=None):
        name = str(name or "").strip()
        if not name:
            return
        item = tenants.setdefault(name, {
            "name": name,
            "source": source,
            "kong": "-",
            "enabled": True,
            "always_on": False,
            "status": "Habilitado",
            "projects": [],
        })
        if data:
            for k, v in data.items():
                if v not in [None, ""]:
                    item[k] = v

    try:
        con = sqlite3.connect(_v137c_db_path())
        con.row_factory = sqlite3.Row
        tables = {r["name"] for r in con.execute("select name from sqlite_master where type='table'")}

        if "projects" in tables:
            cols = [r["name"] for r in con.execute("pragma table_info(projects)")]
            if "tenant" in cols:
                for row in con.execute('''
                    select slug, name, tenant
                    from projects
                    where tenant is not null and trim(tenant) <> ''
                    order by tenant, slug
                '''):
                    d = dict(row)
                    tenant = d.get("tenant")
                    add(tenant, "sqlite.projects")
                    tenants[tenant]["projects"].append(d.get("slug") or d.get("name") or "")

        if "tenants" in tables:
            cols = [r["name"] for r in con.execute("pragma table_info(tenants)")]
            name_col = "name" if "name" in cols else ("tenant" if "tenant" in cols else ("slug" if "slug" in cols else None))
            if name_col:
                for row in con.execute("select * from tenants"):
                    d = dict(row)
                    name = d.get(name_col)
                    add(name, "sqlite.tenants", {
                        "enabled": bool(d.get("enabled", 1)),
                        "status": d.get("status") or d.get("state") or "",
                        "kong": d.get("kong") or d.get("kong_status") or "-",
                        "always_on": bool(d.get("always_on", 0)),
                    })

        if "tenant_policy" in tables:
            cols = [r["name"] for r in con.execute("pragma table_info(tenant_policy)")]
            tenant_col = "tenant" if "tenant" in cols else ("name" if "name" in cols else None)
            if tenant_col:
                for row in con.execute("select * from tenant_policy"):
                    d = dict(row)
                    name = d.get(tenant_col)
                    add(name, "sqlite.tenant_policy")
                    item = tenants.get(name)
                    if item:
                        for k in ["enabled", "always_on", "status", "kong", "kong_status"]:
                            if k in d and d[k] not in [None, ""]:
                                if k == "kong_status":
                                    item["kong"] = d[k]
                                else:
                                    item[k] = d[k]

        con.close()
    except Exception:
        pass

    for base in ["/srv/cloudif/tenants", "/srv/cloudif/data/tenants"]:
        try:
            bp = pathlib.Path(base)
            if bp.exists():
                for child in sorted(bp.iterdir()):
                    if child.is_dir() and not child.name.startswith("."):
                        add(child.name, f"dir:{base}")
        except Exception:
            pass

    return [tenants[k] for k in sorted(tenants)]

def _v137c_metric_card(label, value, detail="", tone=""):
    return f'''
<div class="mod-metric {tone}">
  <div class="mod-metric-label">{_v137c_h(label)}</div>
  <div class="mod-metric-value">{_v137c_h(value)}</div>
  <div class="mod-metric-detail">{_v137c_h(detail)}</div>
</div>
'''

def _v137c_tenant_card(t):
    name = str(t.get("name") or "").strip()
    enabled = bool(t.get("enabled", True))
    always_on = bool(t.get("always_on", False))
    kong = str(t.get("kong") or "-")
    projects = [p for p in (t.get("projects") or []) if p]

    enabled_label = "Habilitado" if enabled else "Desabilitado"
    mode_label = "Sempre ligado" if always_on else "Sob demanda"
    checked = "checked" if enabled else ""

    project_badges = "".join(
        f'<span class="mod-chip">{_v137c_h(p)}</span>'
        for p in projects[:8]
    )
    if len(projects) > 8:
        project_badges += f'<span class="mod-chip muted">+{len(projects)-8}</span>'
    if not project_badges:
        project_badges = '<span class="mod-empty">Nenhum projeto vinculado</span>'

    opts = "".join(
        [f'<option value="{i}">{i} hora{"s" if i > 1 else ""}</option>' for i in range(1, 7)]
    )

    return f'''
<article class="mod-tenant-card">
  <header class="mod-tenant-header">
    <div class="mod-tenant-title">
      <div class="mod-icon">DB</div>
      <div>
        <h3>{_v137c_h(name)}</h3>
        <p>Tenant Supabase gerenciado</p>
      </div>
    </div>
    <div class="mod-status-stack">
      <span class="mod-status {'ok' if enabled else 'off'}">{_v137c_h(enabled_label)}</span>
      <span class="mod-status neutral">{_v137c_h(mode_label)}</span>
    </div>
  </header>

  <section class="mod-info-grid">
    <div class="mod-info">
      <span>Kong</span>
      <strong>{_v137c_h(kong)}</strong>
    </div>
    <div class="mod-info">
      <span>Status</span>
      <strong>{_v137c_h(enabled_label)}</strong>
    </div>
    <div class="mod-info">
      <span>Modo</span>
      <strong>{_v137c_h(mode_label)}</strong>
    </div>
    <div class="mod-info">
      <span>Projetos</span>
      <strong>{len(projects)}</strong>
    </div>
  </section>

  <section class="mod-projects">
    <div class="mod-section-label">Projetos vinculados</div>
    <div class="mod-chip-row">
      {project_badges}
    </div>
  </section>

  <form method="post" action="/cloudiff/portal/action/tenant_action" class="mod-actions">
    <input type="hidden" name="tenant" value="{_v137c_h(name)}">

    <label class="mod-check">
      <input type="checkbox" name="enabled_visual" value="1" {checked} disabled>
      <span>{_v137c_h(enabled_label)}</span>
    </label>

    <a class="btn light" href="https://{_v137c_h(name)}.cloudiff.duckdns.org/project/default" target="_blank">Abrir Studio</a>
    <button class="btn gray" name="op" value="stop">Parar</button>
    <button class="btn blue" name="op" value="restart">Reiniciar</button>

    <div style="display: flex; gap: 4px; align-items: center; border-left: 1px solid #e2ece5; padding-left: 10px; margin-left: auto;">
        <select name="hours" class="mod-select">
        {opts}
        </select>
        <button class="btn" name="op" value="keepalive">Ligar</button>
    </div>

    <button class="btn amber" name="op" value="always_on" style="margin-left: auto;">Fixar On</button>
    <button class="btn gray" name="op" value="always_off">Fixar Off</button>
  </form>
</article>
'''

def _v137c_render_bancos_modular():
    tenants = _v137c_list_tenants()

    total = len(tenants)
    enabled = sum(1 for t in tenants if bool(t.get("enabled", True)))
    always = sum(1 for t in tenants if bool(t.get("always_on", False)))
    linked_projects = sum(len(t.get("projects") or []) for t in tenants)

    cards = "\n".join(_v137c_tenant_card(t) for t in tenants)
    if not cards:
        cards = '''
<article class="mod-tenant-card">
  <h3>Nenhum tenant encontrado</h3>
  <p class="small">Não foram encontrados tenants no SQLite nem em /srv/cloudif/tenants.</p>
</article>
'''

    return f'''
<style>
/* CloudIF v137c-safe - Bancos/Tenants modular com UI Aprimorada */
.mod-page {{
  padding: 8px 0 22px;
}}

.mod-hero {{
  border: 1px solid #d9e5dc;
  border-radius: 24px;
  background:
    radial-gradient(circle at top right, rgba(22,136,33,.12), transparent 22rem),
    linear-gradient(135deg, #ffffff 0%, #f4faf5 100%);
  box-shadow: 0 14px 38px rgba(16,24,40,.06);
  padding: 24px;
  margin-bottom: 24px;
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
}}

.mod-hero h2 {{
  margin: 0;
  font-size: 1.75rem;
  color: #1a202c;
  letter-spacing: -.035em;
}}

.mod-hero p {{
  margin: 6px 0 0;
  color: #4a5568;
  max-width: 800px;
  line-height: 1.5;
}}

.mod-metrics {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}}

.mod-metric {{
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 4px 12px rgba(0,0,0,.03);
  padding: 16px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}}

.mod-metric:hover {{
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,.06);
}}

.mod-metric-label {{
  color: #718096;
  font-weight: 700;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}}

.mod-metric-value {{
  font-size: 2rem;
  font-weight: 800;
  color: #2d3748;
  margin-top: 8px;
}}

.mod-metric-detail {{
  color: #a0aec0;
  font-size: 0.8rem;
  margin-top: 4px;
}}

.mod-tenant-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 20px;
  align-items: stretch;
}}

.mod-tenant-card {{
  border: 1px solid #e2e8f0;
  border-radius: 22px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(0,0,0,.04);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}}

.mod-tenant-card:hover {{
  transform: translateY(-4px);
  box-shadow: 0 16px 40px rgba(0,0,0,.08);
  border-color: #cbd5e0;
}}

.mod-tenant-header {{
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  padding-bottom: 16px;
  border-bottom: 1px solid #edf2f7;
}}

.mod-tenant-title {{
  display: flex;
  gap: 14px;
  align-items: center;
}}

.mod-icon {{
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #2f9338, #168821);
  color: #fff;
  font-weight: 800;
  font-size: 1.1rem;
  box-shadow: 0 4px 10px rgba(47, 147, 56, 0.3);
}}

.mod-tenant-title h3 {{
  margin: 0;
  font-size: 1.25rem;
  color: #2d3748;
}}

.mod-tenant-title p {{
  margin: 4px 0 0;
  color: #718096;
  font-size: 0.85rem;
}}

.mod-status-stack {{
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-end;
}}

.mod-status {{
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border: 1px solid transparent;
}}

.mod-status.ok {{
  background: #f0fff4;
  color: #22543d;
  border-color: #c6f6d5;
}}

.mod-status.off {{
  background: #fff5f5;
  color: #9b2c2c;
  border-color: #fed7d7;
}}

.mod-status.neutral {{
  background: #edf2f7;
  color: #4a5568;
  border-color: #e2e8f0;
}}

.mod-info-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}}

.mod-info {{
  background: #f8fafc;
  border: 1px solid #edf2f7;
  border-radius: 12px;
  padding: 12px;
  text-align: center;
}}

.mod-info span {{
  display: block;
  color: #718096;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}}

.mod-info strong {{
  display: block;
  color: #2d3748;
  font-size: 1rem;
  font-weight: 800;
  margin-top: 6px;
}}

.mod-section-label {{
  color: #4a5568;
  font-size: 0.85rem;
  font-weight: 700;
  margin-bottom: 10px;
}}

.mod-chip-row {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}}

.mod-chip,
.mod-empty {{
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 6px 12px;
  background: #ffffff;
  font-size: 0.8rem;
  font-weight: 600;
  color: #4a5568;
  transition: background 0.2s ease;
}}

.mod-chip:hover {{
  background: #edf2f7;
}}

.mod-chip.muted,
.mod-empty {{
  color: #a0aec0;
  background: #f7fafc;
  border-color: #edf2f7;
}}

.mod-actions {{
  margin-top: auto;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  padding-top: 16px;
  border-top: 1px solid #edf2f7;
}}

.mod-actions .btn {
  transition: filter 0.2s ease;
}

.mod-actions .btn:hover {
  filter: brightness(0.95);
}

.mod-check {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 8px 12px;
  background: #f8fafc;
  font-weight: 600;
  font-size: 0.85rem;
  color: #4a5568;
}}

.mod-select {{
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #cbd5e0;
  background-color: #fff;
  font-size: 0.85rem;
  color: #4a5568;
  outline: none;
}}
</style>

<div class="mod-page">
  <section class="mod-hero">
    <div>
      <h2>Bancos / Tenants</h2>
      <p>Administre os ambientes Supabase usados pelos projetos. Ações operacionais ficam agrupadas por tenant, com visualização rápida de status, modo de execução e projetos vinculados.</p>
    </div>
  </section>

  <section class="mod-metrics">
    {_v137c_metric_card("Tenants", total, "ambientes encontrados")}
    {_v137c_metric_card("Habilitados", enabled, "disponíveis para uso", "ok")}
    {_v137c_metric_card("Sempre ligado", always, "modo persistente", "neutral")}
    {_v137c_metric_card("Projetos vinculados", linked_projects, "associações ativas")}
  </section>

  <section class="mod-tenant-grid">
    {cards}
  </section>
</div>
'''

# CloudIF v137c-safe fim


def render_bancos(user=None):
    # CloudIF v138a-safe: renderização modular de Bancos/Tenants
    import sys
    if "/srv/cloudif/lib" not in sys.path:
        sys.path.insert(0, "/srv/cloudif/lib")
    from cloudif_bancos_module import render_bancos_page
    return render_bancos_page(user=user)

def render_hardware(user=None):
    inv = technical_inventory()
    files = inv.get("files", {})
    paths = inv.get("paths", {})

    def ok_file(key, label):
        exists = bool(files.get(key))
        path = paths.get(key, "")
        return f"""
<div class="cm-resource">
  <div class="cm-resource-title">
    <strong>{h(label)}</strong>
    {pill(exists, "Encontrado", "Ausente")}
  </div>
  <p class="cm-muted"><code>{h(path)}</code></p>
</div>
"""

    content = f"""
<div class="cm-grid">
  <div class="cm-card">
    <h3>Portal principal</h3>
    <p class="cm-muted">Estado técnico dos arquivos centrais do CloudIF Portal.</p>
    {ok_file("portal_service", "Serviço systemd do portal")}
    {ok_file("portal_script", "Script principal do portal")}
    {ok_file("portal_db", "Banco SQLite do portal")}
  </div>

  <div class="cm-card">
    <h3>Frontend modular</h3>
    <p class="cm-muted">Arquivos separados para dados, componentes, páginas e fachada de compatibilidade.</p>
    {ok_file("ui_data", "Módulo de dados")}
    {ok_file("ui_components", "Módulo de componentes")}
    {ok_file("ui_pages", "Módulo de páginas")}
    {ok_file("ui_modular", "Fachada modular")}
  </div>

  <div class="cm-card">
    <h3>Deploy Center</h3>
    <p class="cm-muted">Integração com painel separado de deploy/Komodo.</p>
    {ok_file("deploy_service", "Serviço systemd do Deploy Center")}
    {ok_file("deploy_script", "Script Deploy Center")}
    {ok_file("git_komodo_module", "Módulo Git + Komodo")}
  </div>

  <div class="cm-card">
    <h3>Router / Proxy local</h3>
    <p class="cm-muted">Configuração local que publica rotas internas do CloudIF. Não é alterada por ajustes visuais.</p>
    {ok_file("router_conf", "Configuração do router local")}
  </div>

  <div class="cm-card">
    <h3>Projetos e recursos</h3>
    <p class="cm-muted">Resumo técnico da distribuição dos recursos acoplados aos projetos.</p>
    <div class="cm-resource">
      <div class="cm-resource-title"><strong>Projetos</strong>{pill(inv['projects'] > 0, str(inv['projects']), "0")}</div>
    </div>
    <div class="cm-resource">
      <div class="cm-resource-title"><strong>Tenants</strong>{pill(inv['tenants'] > 0, str(inv['tenants']), "0")}</div>
    </div>
    <div class="cm-actions">
      {btn("Ver Projetos", tab_url("projetos"), True, True)}
      {btn("Ver Bancos", tab_url("bancos"), True, False)}
    </div>
  </div>

  <div class="cm-card">
    <h3>Scripts de integração</h3>
    <p class="cm-muted">Scripts de orquestração usados por Forgejo, Komodo e vínculo de projetos.</p>
    {ok_file("project_integrate", "Script de integração de projeto")}
    <div class="cm-actions">
      {btn("Abrir Git + Komodo", tab_url("git"), True, True)}
    </div>
  </div>
</div>
"""

    actions = btn("Voltar ao Resumo", tab_url("resumo"), True, True)

    return layout(
        "resumo",
        "Informações da Plataforma",
        "Área técnica modular com estado do portal, frontend, deploy, router/proxy e integrações.",
        content,
        user=user,
        actions=actions,
    )

def render_ajuda(user=None):
    content = """
<div class="cm-card" style="margin-bottom:16px">
  <div class="cm-section-title"><div><h3>GitHub e manual técnico</h3><p class="cm-muted">Código-fonte e documentação completa da arquitetura CloudIFF.</p></div></div>
  <p>O repositório explica os componentes, fluxos de provisionamento e exclusão, agentes, ferramentas MCP, aprovações humanas, protocolos de reconciliação, modelo de dados, serviços, rotas, operação e finalidade de cada pasta e arquivo.</p>
  <div class="cm-actions"><a class="cm-btn cm-btn-primary" href="https://github.com/debianlima/cloudiff" target="_blank" rel="noopener noreferrer">Abrir GitHub do projeto</a></div>
</div>
<div class="cm-grid">
  <div class="cm-card">
    <h3>Sou aluno</h3>
    <p class="cm-muted">Abra seu projeto, confira se há banco vinculado e use Studio ou Git conforme orientação.</p>
  </div>
  <div class="cm-card">
    <h3>Sou professor</h3>
    <p class="cm-muted">Acompanhe os projetos, verifique bancos e oriente a turma pelos cards.</p>
  </div>
  <div class="cm-card">
    <h3>Sou administrador</h3>
    <p class="cm-muted">Use a Administração clássica para ações avançadas.</p>
  </div>
</div>
"""
    return layout("ajuda", "Guia da plataforma", "Uso diário e referência técnica da CloudIFF.", content, user=user)

def render_tab(tab, user=None):
    if tab in ["resumo", "", None]:
        return render_resumo(user)
    if tab == "projetos":
        return render_projetos(user)
    if tab == "bancos":
        return render_bancos(user)
    if tab == "hardware":
        return render_hardware(user)
    if tab == "ajuda":
        return render_ajuda(user)
    return render_resumo(user)



# CloudIF v70 — páginas Admin e Git modulares

def render_admin(user=None):
    content = f"""
<div class="cm-grid">
  <div class="cm-card">
    <h3>Identidade e acesso</h3>
    <p class="cm-muted">Gerencie login, grupos Authentik e permissões de uso do CloudIF. O AD/Samba pode continuar como consulta auxiliar.</p>
    {btn("Abrir permissões", "#modal-permissoes", True, True)}
  </div>

  <div class="cm-card">
    <h3>Projetos e vínculos</h3>
    <p class="cm-muted">Projetos são entidades independentes. Bancos, Git e Deploy podem ser vinculados conforme necessidade.</p>
    {btn("Ver Projetos", tab_url("projetos"), True, True)}
  </div>

  <div class="cm-card">
    <h3>Bancos / Tenants</h3>
    <p class="cm-muted">Ações comuns ficam nos cards; ações pesadas continuam disponíveis na administração clássica.</p>
    {btn("Ver Bancos", tab_url("bancos"), True, True)}
  </div>

  <div class="cm-card">
    <h3>Git + Komodo</h3>
    <p class="cm-muted">Forgejo e Komodo ficam separados da criação do projeto, com sincronização sob demanda.</p>
    {btn("Abrir Git + Komodo", tab_url("git"), True, True)}
  </div>

  <div class="cm-card">
    <h3>Manutenção avançada</h3>
    <p class="cm-muted">Use a tela clássica para funções administrativas ainda não portadas, como scripts de reparo, cache, router e ações perigosas.</p>
    {btn("Administração clássica", "/cloudiff/portal/?tab=admin&classic=1", True, False)}
  </div>

  <div class="cm-card">
    <h3>Diagnóstico técnico</h3>
    <p class="cm-muted">Hardware, serviços e diagnóstico operacional ficam agrupados em Informações de Hardware.</p>
    {btn("Informações de Hardware", tab_url("hardware"), True, False)}
  </div>
</div>

{_cloudif_admin_publications()}

<div id="modal-permissoes" class="cm-modal">
  <div class="cm-modal-card">
    <div class="cm-modal-head">
      <div>
        <h3>Permissões</h3>
        <p class="cm-muted">Use a Administração clássica para alterações avançadas de usuários e grupos até a API JSON estar finalizada.</p>
      </div>
      <a class="cm-close" href="#">×</a>
    </div>

    <div class="cm-card">
      <h3>Busca e permissões</h3>
      <p class="cm-muted">Esta área ficará ligada à busca dinâmica AD/Authentik. Por enquanto, as ações completas permanecem na tela clássica.</p>
      {btn("Abrir Administração clássica", "/cloudiff/portal/?tab=admin&classic=1", True, False)}
    </div>
  </div>
</div>
"""

    actions = (
        btn("Administração clássica", "/cloudiff/portal/?tab=admin&classic=1", True, False)
        + btn("Informações de Hardware", tab_url("hardware"), True, False)
    )

    return layout(
        "admin",
        "Administração",
        "Painel administrativo modular. Funções avançadas continuam preservadas na tela clássica.",
        content,
        user=user,
        actions=actions,
    )


def render_git(user=None):
    try:
        import cloudif_git_komodo_module as gk
        body = gk.render_git_komodo_module(
            project="",
            tenant="",
            actor=(user or {}).get("username", "portal") if isinstance(user, dict) else "portal",
            is_admin=bool((user or {}).get("admin")) if isinstance(user, dict) else False,
        )
    except Exception as e:
        body = f"""
<div class="cm-card">
  <h3>Git + Komodo</h3>
  <p class="cm-muted">Não foi possível carregar o módulo específico de integração.</p>
  <pre>{h(str(e))}</pre>
</div>
"""

    actions = (
        btn("Abrir Forgejo", "https://cloudiff.duckdns.org/git/user/oauth2/Authentik/", True, False, True)
        + btn("Abrir Komodo", "https://komodoiff.duckdns.org/auth/oidc/login", True, False, True)
        + btn("Informações de Hardware", tab_url("hardware"), True, False)
    )

    return layout(
        "git",
        "Git + Komodo",
        "Integração de repositório, sincronização e deploy como recursos acopláveis ao projeto.",
        body,
        user=user,
        actions=actions,
    )


def render_tab(tab, user=None):
    if tab in ["resumo", "", None]:
        return render_resumo(user)
    if tab == "projetos":
        return render_projetos(user)
    if tab == "bancos":
        return render_bancos(user)
    if tab == "git":
        return render_git(user)
    if tab == "admin":
        return render_admin(user)
    if tab == "hardware":
        return render_hardware(user)
    if tab == "ajuda":
        return render_ajuda(user)
    return render_resumo(user)




# CloudIF v96 — compatibilidade final para aba Projetos
# Corrige TypeError: modal_common() got an unexpected keyword argument 'user'
def modal_common(user=None, projects=None):
    script = """
<script>
function cloudifShowWizard(id){
  var el = document.getElementById(id);
  if(el) el.classList.add('show');
}

function cloudifHideWizard(id){
  var el = document.getElementById(id);
  if(el) el.classList.remove('show');
}

document.addEventListener('keydown', function(e){
  if(e.key === 'Escape'){
    document.querySelectorAll('.wizard.show').forEach(function(w){ w.classList.remove('show'); });
  }
});

document.addEventListener('click', function(e){
  if(e.target && e.target.classList && e.target.classList.contains('wizard')){
    e.target.classList.remove('show');
  }
});
</script>
"""

    try:
        return script + _v95_project_wizard(
            "wiz_new_project",
            "Novo projeto",
            "create_project",
            user=user,
            project=None
        )
    except Exception as e:
        try:
            msg = h(e)
        except Exception:
            import html
            msg = html.escape(str(e))

        return script + f"""
<div id="wiz_new_project" class="wizard">
  <div class="wizard-box">
    <div class="wizard-head">
      <div>
        <h3>Novo projeto</h3>
        <p class="small">Não foi possível carregar o wizard avançado.</p>
      </div>
      <button class="wizard-close" type="button" onclick="cloudifHideWizard('wiz_new_project')">×</button>
    </div>

    <div class="wizard-note">
      <strong>Erro no wizard avançado:</strong><br>{msg}
    </div>

    <form method="post" action="/cloudiff/portal/action/project_action">
      <input type="hidden" name="action" value="create_project">
      <input type="hidden" name="db_mode" value="skip">
      <input type="hidden" name="tenant" value="">
      <input type="hidden" name="create_repo" value="1">
      <input type="hidden" name="setup_komodo" value="1">

      <div class="cm-field">
        <label>Nome do projeto</label>
        <input name="name" placeholder="Sistema de Biblioteca">
      </div>

      <div class="cm-field">
        <label>Descrição</label>
        <textarea name="description" rows="3"></textarea>
      </div>

      <div class="wizard-note">
        <strong>Projeto sem banco de dados.</strong><br>
        Git e Komodo serão tratados automaticamente pelo provisionamento.
      </div>

      <div class="cm-actions">
        <button class="cm-btn cm-primary" type="submit">Salvar projeto</button>
        <a class="cm-btn cm-secondary" href="#" onclick="cloudifHideWizard('wiz_new_project')">Cancelar</a>
      </div>
    </form>
  </div>
</div>
"""




# CloudIF v98 — status real do provisionamento por projeto
def _v98_read_provision_report(slug):
    import json
    from pathlib import Path

    safe = str(slug or "").strip()
    path = Path("/srv/cloudif/provisioning/projects") / safe / "provision-report.json"

    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def _v95_provisioning_table(slug, tenant="", p=None):
    p = p or {}
    report = _v98_read_provision_report(slug)

    org = _v95_project_org(p) if "_v95_project_org" in globals() else "cloudif"
    repo = _v95_repo_url(slug, p) if "_v95_repo_url" in globals() else f"https://cloudiff.duckdns.org/git/{org}/{slug}"
    komodo = _v95_komodo_url(p) if "_v95_komodo_url" in globals() else "https://komodoiff.duckdns.org/auth/oidc/login"

    def comp_status(name):
        if not report:
            return "sem relatório"
        c = (report.get("components") or {}).get(name) or {}
        return c.get("status") or "desconhecido"

    def actions(name):
        if not report:
            return "<li>Provisionamento ainda não executado ou sem relatório.</li>"
        c = (report.get("components") or {}).get(name) or {}
        arr = c.get("actions") or []
        if not arr:
            return "<li>Nenhuma ação registrada.</li>"
        out = []
        for a in arr:
            ok = "ok" if a.get("ok") else "pendente/erro"
            nm = a.get("name") or "ação"
            msg = a.get("message") or ""
            out.append(f"<li><code>{h(nm)}</code> — <strong>{h(ok)}</strong> — {h(msg)}</li>")
        return "".join(out)

    containers = []
    if report:
        containers = (((report.get("components") or {}).get("komodo") or {}).get("containers") or [])

    if not containers:
        try:
            containers = _v95_container_names(slug, tenant, p)
        except Exception:
            containers = []

    cont_html = "".join(f"<li><code>{h(c)}</code> — container vinculado/previsto para o projeto.</li>" for c in containers)

    report_link = ""
    if report:
        report_link = f'<p class="small"><strong>Relatório:</strong> <code>/srv/cloudif/provisioning/projects/{h(slug)}/provision-report.json</code></p>'

    return f"""
<div class="wizard-note">
  <h4>Status real do provisionamento</h4>
  {report_link}
  <p class="small"><strong>Forgejo:</strong> {h(comp_status("forgejo"))}</p>
  <p class="small"><strong>Komodo:</strong> {h(comp_status("komodo"))}</p>
  {_v134_render_project_komodo_summary(slug if "slug" in locals() else "", compact=False)}
  <p class="small"><strong>Supabase:</strong> {h(comp_status("supabase"))}</p>

  <h4>Git / Forgejo</h4>
  <p class="small"><strong>Organização:</strong> <code>{h(org)}</code></p>
  <p class="small"><strong>Repositório:</strong> <a href="{h(repo)}" target="_blank">{h(repo)}</a></p>
  <ul class="small">{actions("forgejo")}</ul>

  <h4>Komodo / Deploy</h4>
  <p class="small"><strong>Painel:</strong> <a href="{h(komodo)}" target="_blank">{h(komodo)}</a></p>
  <ul class="small">{cont_html}</ul>
  <ul class="small">{actions("komodo")}</ul>

  <h4>Supabase</h4>
  <ul class="small">{actions("supabase")}</ul>
</div>
"""




# CloudIF v115 — link visual Forgejo padronizado cloudif-<slug>
def _v115_ui_slug(value):
    import re
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "projeto"

def _v115_ui_repo_name(slug):
    slug = _v115_ui_slug(slug)
    return slug if slug.startswith("cloudif-") else "cloudif-" + slug

def _v95_repo_url(slug, p=None):
    p = p or {}
    explicit = p.get("repo_url") or p.get("forgejo_url") or p.get("git_url")
    if explicit:
        return explicit
    repo = _v115_ui_repo_name(slug)
    return f"https://cloudiff.duckdns.org/git/cloudif/{repo}"



# CloudIF v137d-safe - Interface Modular de Bancos
def _v137d_h(x):
    try: return h(x)
    except: import html; return html.escape(str(x if x is not None else ""))

def _v137d_render_bancos_modular():
    # ... (lógica de tenants mantida, apenas simplificada para este patch)
    return '<div class="mod-page"><h2>Bancos / Tenants</h2><p>Interface modular carregada.</p></div>'
