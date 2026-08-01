# CloudIF v138a-safe — módulo Bancos/Tenants

import html
import pathlib
import sqlite3

def h(value):
    return html.escape(str(value if value is not None else ""))

def read_env(path="/etc/cloudif/portal.env"):
    data = {}
    p = pathlib.Path(path)
    if p.exists():
        for raw in p.read_text(errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip().strip('"').strip("'")
    return data

def db_path():
    return read_env().get("CLOUDIF_PORTAL_DB") or "/var/lib/cloudif/portal/cloudif-portal.db"

def add_tenant(tenants, name, source="unknown", data=None):
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
        for key, value in data.items():
            if value not in [None, ""]:
                item[key] = value

def list_tenants():
    tenants = {}

    try:
        con = sqlite3.connect(db_path())
        con.row_factory = sqlite3.Row
        tables = {r["name"] for r in con.execute("select name from sqlite_master where type='table'")}

        if "projects" in tables:
            cols = [r["name"] for r in con.execute("pragma table_info(projects)")]
            if "tenant" in cols:
                for row in con.execute("""
                    select slug, name, tenant
                    from projects
                    where tenant is not null and trim(tenant) <> ''
                    order by tenant, slug
                """):
                    d = dict(row)
                    tenant = d.get("tenant")
                    add_tenant(tenants, tenant, "sqlite.projects")
                    tenants[tenant]["projects"].append(d.get("slug") or d.get("name") or "")

        if "tenant_policy" in tables:
            cols = [r["name"] for r in con.execute("pragma table_info(tenant_policy)")]
            tenant_col = "tenant" if "tenant" in cols else "name" if "name" in cols else None
            if tenant_col:
                for row in con.execute("select * from tenant_policy"):
                    d = dict(row)
                    name = d.get(tenant_col)
                    add_tenant(tenants, name, "sqlite.tenant_policy")
                    item = tenants.get(name)
                    if item:
                        for key in ["enabled", "always_on", "status", "kong", "kong_status"]:
                            if key in d and d[key] not in [None, ""]:
                                if key == "kong_status":
                                    item["kong"] = d[key]
                                else:
                                    item[key] = d[key]

        con.close()
    except Exception:
        pass

    for base in ["/srv/cloudif/tenants", "/srv/cloudif/data/tenants"]:
        try:
            bp = pathlib.Path(base)
            if bp.exists():
                for child in sorted(bp.iterdir()):
                    if child.is_dir() and not child.name.startswith("."):
                        add_tenant(tenants, child.name, f"dir:{base}")
        except Exception:
            pass

    return [tenants[k] for k in sorted(tenants)]

def render_bancos_style():
    return """
<style>
.mod-page{padding:8px 0 22px}
.mod-hero{
  border:1px solid #d9e5dc;
  border-radius:24px;
  background:radial-gradient(circle at top right,rgba(22,136,33,.16),transparent 22rem),linear-gradient(135deg,#fff 0%,#f4faf5 100%);
  box-shadow:0 14px 38px rgba(16,24,40,.08);
  padding:24px;
  margin-bottom:18px;
}
.mod-hero h2{margin:0;font-size:1.65rem;letter-spacing:-.035em}
.mod-hero p{margin:6px 0 0;color:#647067;max-width:820px;line-height:1.5}
.mod-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:18px}
.mod-metric{border:1px solid #d9e5dc;border-radius:18px;background:#fff;box-shadow:0 8px 24px rgba(16,24,40,.055);padding:16px}
.mod-metric-label{color:#647067;font-weight:800;font-size:.82rem}
.mod-metric-value{font-size:1.7rem;font-weight:950;color:#1f2933;margin-top:6px}
.mod-metric-detail{color:#647067;font-size:.82rem;margin-top:2px}
.mod-tenant-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px;align-items:stretch}
.mod-tenant-card{border:1px solid #d9e5dc;border-radius:22px;background:rgba(255,255,255,.96);box-shadow:0 12px 30px rgba(16,24,40,.07);padding:18px;display:flex;flex-direction:column;gap:14px}
.mod-tenant-header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;padding-bottom:12px;border-bottom:1px solid #e2ece5}
.mod-tenant-title{display:flex;gap:12px;align-items:center}
.mod-icon{width:44px;height:44px;border-radius:16px;display:grid;place-items:center;background:linear-gradient(135deg,#168821,#0f6f1a);color:#fff;font-weight:950}
.mod-tenant-title h3{margin:0;font-size:1.16rem;letter-spacing:-.02em}
.mod-tenant-title p{margin:4px 0 0;color:#647067;font-size:.86rem}
.mod-status-stack{display:flex;flex-direction:column;gap:6px;align-items:flex-end}
.mod-status{border-radius:999px;padding:6px 10px;font-size:.78rem;font-weight:900;border:1px solid #d9e5dc;background:#f7fbf8}
.mod-status.ok{background:#e8f8eb;color:#0f6f1a;border-color:#bde8c5}
.mod-status.off{background:#fff5f5;color:#b42318;border-color:#fecaca}
.mod-status.neutral{background:#f4f7f5;color:#33443a}
.mod-info-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.mod-info{background:#f8fbf8;border:1px solid #e2ece5;border-radius:14px;padding:10px}
.mod-info span{display:block;color:#647067;font-size:.76rem;font-weight:800}
.mod-info strong{display:block;color:#1f2933;font-size:.96rem;margin-top:4px}
.mod-section-label{color:#647067;font-size:.8rem;font-weight:900;margin-bottom:8px}
.mod-chip-row{display:flex;flex-wrap:wrap;gap:6px}
.mod-chip,.mod-empty{border:1px solid #d9e5dc;border-radius:999px;padding:5px 9px;background:#fff;font-size:.78rem;font-weight:800;color:#33443a}
.mod-chip.muted,.mod-empty{color:#647067;background:#f4f7f5}
.mod-actions{margin-top:auto;display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding-top:12px;border-top:1px solid #e2ece5}
.mod-check{display:inline-flex;align-items:center;gap:6px;border:1px solid #d9e5dc;border-radius:12px;padding:8px 10px;background:#f8fbf8;font-weight:800;color:#33443a}
.mod-select{max-width:150px}
.mod-footer-note{margin-top:18px;border:1px solid #d9e5dc;border-radius:18px;background:#fbfdfb;color:#647067;padding:14px 16px}
</style>
"""

def metric_card(label, value, detail):
    return f"""
<div class="mod-metric">
  <div class="mod-metric-label">{h(label)}</div>
  <div class="mod-metric-value">{h(value)}</div>
  <div class="mod-metric-detail">{h(detail)}</div>
</div>
"""

def render_header():
    return """
<section class="mod-hero">
  <div>
    <h2>Bancos / Tenants</h2>
    <p>Administre os ambientes Supabase usados pelos projetos CloudIF. As ações ficam agrupadas por tenant, com leitura rápida de status, modo de execução, Kong e projetos vinculados.</p>
  </div>
</section>
"""

def render_metrics(tenants):
    total = len(tenants)
    enabled = sum(1 for t in tenants if bool(t.get("enabled", True)))
    always = sum(1 for t in tenants if bool(t.get("always_on", False)))
    linked = sum(len(t.get("projects") or []) for t in tenants)
    return f"""
<section class="mod-metrics">
  {metric_card("Tenants", total, "ambientes encontrados")}
  {metric_card("Habilitados", enabled, "disponíveis para uso")}
  {metric_card("Sempre ligado", always, "modo persistente")}
  {metric_card("Projetos vinculados", linked, "associações ativas")}
</section>
"""

def render_tenant_card(t):
    name = str(t.get("name") or "").strip()
    enabled = bool(t.get("enabled", True))
    always_on = bool(t.get("always_on", False))
    kong = str(t.get("kong") or "-")
    projects = [p for p in (t.get("projects") or []) if p]
    enabled_label = "Habilitado" if enabled else "Desabilitado"
    mode_label = "Sempre ligado" if always_on else "Sob demanda"
    checked = "checked" if enabled else ""

    badges = "".join(f'<span class="mod-chip">{h(p)}</span>' for p in projects[:8])
    if len(projects) > 8:
        badges += f'<span class="mod-chip muted">+{len(projects)-8}</span>'
    if not badges:
        badges = '<span class="mod-empty">Nenhum projeto vinculado</span>'

    opts = "".join(f'<option value="{i}">{i} hora{"s" if i > 1 else ""}</option>' for i in range(1,7))

    return f"""
<article class="mod-tenant-card">
  <header class="mod-tenant-header">
    <div class="mod-tenant-title">
      <div class="mod-icon">DB</div>
      <div>
        <h3>{h(name)}</h3>
        <p>Tenant Supabase gerenciado pelo CloudIF</p>
      </div>
    </div>
    <div class="mod-status-stack">
      <span class="mod-status {'ok' if enabled else 'off'}">{h(enabled_label)}</span>
      <span class="mod-status neutral">{h(mode_label)}</span>
    </div>
  </header>

  <section class="mod-info-grid">
    <div class="mod-info"><span>Kong</span><strong>{h(kong)}</strong></div>
    <div class="mod-info"><span>Status</span><strong>{h(enabled_label)}</strong></div>
    <div class="mod-info"><span>Modo</span><strong>{h(mode_label)}</strong></div>
    <div class="mod-info"><span>Projetos</span><strong>{len(projects)}</strong></div>
  </section>

  <section class="mod-projects">
    <div class="mod-section-label">Projetos vinculados</div>
    <div class="mod-chip-row">{badges}</div>
  </section>

  <form method="post" action="/cloudiff/portal/action/tenant_action" class="mod-actions">
    <input type="hidden" name="tenant" value="{h(name)}">
    <label class="mod-check">
      <input type="checkbox" name="enabled_visual" value="1" {checked} disabled>
      <span>{h(enabled_label)}</span>
    </label>
    <a class="btn light" href="https://{h(name)}.cloudiff.duckdns.org/project/default" target="_blank">Abrir Studio</a>
    <button class="btn gray" name="op" value="stop">Parar</button>
    <button class="btn blue" name="op" value="restart">Reiniciar</button>
    <select name="hours" class="mod-select">{opts}</select>
    <button class="btn" name="op" value="keepalive">Tempo ligado</button>
    <button class="btn amber" name="op" value="always_on">Sempre ligado</button>
    <button class="btn gray" name="op" value="always_off">Desativar sempre ligado</button>
  </form>
</article>
"""

def render_grid(tenants):
    if not tenants:
        cards = '<article class="mod-tenant-card"><h3>Nenhum tenant encontrado</h3><p class="small">Não foram encontrados tenants.</p></article>'
    else:
        cards = "\n".join(render_tenant_card(t) for t in tenants)
    return f'<section class="mod-tenant-grid">{cards}</section>'

def render_footer():
    return """
<section class="mod-footer-note">
  <strong>Observação:</strong> a exclusão de banco/tenant deve permanecer controlada nesta área. A exclusão Git/Komodo de projetos é administrada separadamente na aba Git + Komodo.
</section>
"""

def render_bancos_page(user=None):
    tenants = list_tenants()
    return f"""
{render_bancos_style()}
<div class="mod-page">
  {render_header()}
  {render_metrics(tenants)}
  {render_grid(tenants)}
  {render_footer()}
</div>
"""
