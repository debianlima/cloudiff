#!/usr/bin/env python3
import html
import sqlite3
import time
import urllib.parse
import urllib.request
import json
import os
from pathlib import Path

DB = "/var/lib/cloudif/portal/cloudif-portal.db"

PROJECT_COL_CANDIDATES = ["project_slug", "slug", "project", "project_id", "project_name"]
PRINCIPAL_COL_CANDIDATES = ["principal", "subject", "member", "identity", "username", "user", "email", "group_name", "group", "user_or_group"]
TYPE_COL_CANDIDATES = ["principal_type", "subject_type", "member_type", "identity_type", "type", "kind"]
ROLE_COL_CANDIDATES = ["role", "permission", "level", "access", "perfil"]
OWNER_COL_CANDIDATES = ["owner", "owner_username", "owner_email", "created_by", "creator", "user", "username", "email", "dono"]
ID_COL_CANDIDATES = ["id", "project_id"]

ACL_KEYWORDS = ["acl", "permission", "permissions", "permiss", "member", "members", "share", "policy", "policies", "access"]

def h(x):
    return html.escape("" if x is None else str(x))

def con():
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=20000")
    return c

def table_cols(c, table):
    return [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]

def pick(cols, candidates):
    low = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in low:
            return low[cand.lower()]
    return ""

def detect_acl_config():
    c = con()
    try:
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        candidates = []

        for table in tables:
            cols = table_cols(c, table)
            low_table = table.lower()
            low_cols = {x.lower(): x for x in cols}

            score = 0
            if any(k in low_table for k in ACL_KEYWORDS):
                score += 2

            project_col = pick(cols, PROJECT_COL_CANDIDATES)
            principal_col = pick(cols, PRINCIPAL_COL_CANDIDATES)
            type_col = pick(cols, TYPE_COL_CANDIDATES)
            role_col = pick(cols, ROLE_COL_CANDIDATES)
            id_col = pick(cols, ["id"])

            if project_col:
                score += 2
            if principal_col:
                score += 2
            if type_col:
                score += 1
            if role_col:
                score += 1

            if score >= 4:
                candidates.append({
                    "score": score,
                    "table": table,
                    "cols": cols,
                    "project_col": project_col,
                    "principal_col": principal_col,
                    "type_col": type_col,
                    "role_col": role_col,
                    "id_col": id_col,
                })

        if not candidates:
            raise RuntimeError("Nenhuma tabela real de ACL/permissões foi detectada no SQLite.")

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[0]
    finally:
        c.close()

def project_row(slug):
    c = con()
    try:
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        if "projects" not in tables:
            return {}

        cols = table_cols(c, "projects")
        slug_col = pick(cols, ["slug", "project_slug", "name"])
        if not slug_col:
            return {}

        row = c.execute(f"SELECT * FROM projects WHERE {slug_col}=? LIMIT 1", (slug,)).fetchone()
        return dict(row) if row else {}
    finally:
        c.close()

def project_owner(slug):
    row = project_row(slug)
    if not row:
        return ""

    low = {k.lower(): k for k in row.keys()}

    for cand in OWNER_COL_CANDIDATES:
        if cand.lower() in low and row.get(low[cand.lower()]):
            return str(row.get(low[cand.lower()]) or "")

    return ""

def current_actor(user=None):
    user = user or {}
    username = user.get("username") or user.get("name") or ""
    email = user.get("email") or ""
    return {
        "username": str(username),
        "email": str(email),
        "groups": user.get("groups") or [],
    }

def acl_rows(slug):
    cfg = detect_acl_config()
    c = con()
    try:
        table = cfg["table"]
        pcol = cfg["project_col"]
        rows = [dict(r) for r in c.execute(f"SELECT * FROM {table} WHERE {pcol}=? ORDER BY 1", (slug,)).fetchall()]
        return cfg, rows
    finally:
        c.close()

def normalize_acl_row(cfg, row):
    principal = row.get(cfg["principal_col"], "")
    ptype = row.get(cfg["type_col"], "") if cfg.get("type_col") else ""
    role = row.get(cfg["role_col"], "") if cfg.get("role_col") else ""
    rid = row.get(cfg["id_col"], "") if cfg.get("id_col") else ""

    if not ptype:
        txt = str(principal).lower()
        if "@" in txt:
            ptype = "user"
        elif "cloudif" in txt or "grupo" in txt or "group" in txt:
            ptype = "group"
        else:
            ptype = "principal"

    if not role:
        role = "access"

    return {
        "id": rid,
        "principal": str(principal),
        "type": str(ptype),
        "role": str(role),
    }

def is_owner_principal(slug, principal, role="", user=None):
    principal_l = str(principal or "").strip().lower()
    role_l = str(role or "").strip().lower()
    owner_l = project_owner(slug).strip().lower()
    actor = current_actor(user)

    protected_roles = ["owner", "dono", "proprietario", "proprietário"]

    if role_l in protected_roles:
        return True

    if owner_l and principal_l == owner_l:
        return True

    if actor["username"] and principal_l == actor["username"].lower() and role_l in protected_roles:
        return True

    if actor["email"] and principal_l == actor["email"].lower() and role_l in protected_roles:
        return True

    return False

def sync_komodo_acl(slug):
    row=project_row(slug);owner=str(row.get('owner') or '').strip().lower()
    cfg,raw=acl_rows(slug);acl=[]
    for item in raw:
        n=normalize_acl_row(cfg,item);acl.append({'type':n['type'],'subject':n['principal']})
    env={}
    for path in ('/etc/cloudif/komodo-agent-client.env','/etc/cloudif/provision.env'):
        try:
            for line in Path(path).read_text().splitlines():
                if '=' in line and not line.lstrip().startswith('#'):
                    k,v=line.split('=',1);env[k.strip()]=v.strip().strip('"').strip("'")
        except Exception:pass
    base=(env.get('KOMODO_AGENT_URL') or 'http://10.62.91.2:18098').rstrip('/');token=env.get('KOMODO_AGENT_TOKEN') or ''
    if not token:return {'ok':False,'error':'komodo_agent_token_missing'}
    payload=json.dumps({'project':slug,'access':{'owner':owner,'acl':acl}}).encode()
    req=urllib.request.Request(base+'/komodo/project/authz-sync',data=payload,method='POST',headers={'Content-Type':'application/json','X-CloudIF-Token':token,'Authorization':'Bearer '+token})
    try:
        with urllib.request.urlopen(req,timeout=45) as r:return json.load(r)
    except Exception as exc:return {'ok':False,'error':'komodo_authz_sync_failed','detail':str(exc)[:300]}

def add_acl(slug, principal, principal_type="user", role="access", user=None):
    import time as _time

    principal = str(principal or "").strip()
    principal_type = str(principal_type or "user").strip()
    role = "access"

    if not principal:
        raise RuntimeError("Informe usuário ou grupo.")

    if principal_type not in ["user", "group"]:
        raise RuntimeError("Tipo de permissão inválido.")

    cfg = detect_acl_config()
    c = con()
    try:
        table = cfg["table"]
        cols = cfg["cols"]

        where = f"{cfg['project_col']}=? AND {cfg['principal_col']}=?"
        params = [slug, principal]

        if cfg.get("type_col"):
            where += f" AND {cfg['type_col']}=?"
            params.append(principal_type)

        existing = c.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0]

        if existing:
            raise RuntimeError("Permissão já existe. Remova primeiro para recriar.")

        values = {
            cfg["project_col"]: slug,
            cfg["principal_col"]: principal,
        }

        if cfg.get("type_col"):
            values[cfg["type_col"]] = principal_type

        if cfg.get("role_col"):
            values[cfg["role_col"]] = role

        for optional_col in ["created_at", "updated_at"]:
            if optional_col in cols:
                values[optional_col] = _time.strftime("%Y-%m-%dT%H:%M:%S%z")

        actor = current_actor(user)

        for optional_col in ["created_by", "updated_by"]:
            if optional_col in cols:
                values[optional_col] = actor.get("username") or actor.get("email") or "portal"

        colnames = list(values.keys())
        placeholders = ",".join(["?"] * len(colnames))
        sql = f"INSERT INTO {table} ({','.join(colnames)}) VALUES ({placeholders})"

        c.execute(sql, [values[x] for x in colnames])
        c.commit()
        sync=sync_komodo_acl(slug)
        if not sync.get('ok'):
            return "Permissão adicionada. Sincronização imediata com o Komodo pendente; reconciliação durável será enfileirada."
        return "Permissão adicionada."
    finally:
        c.close()

def remove_acl(slug, principal, principal_type="", role="", user=None, row_id=""):
    principal = str(principal or "").strip()
    principal_type = str(principal_type or "").strip()
    role = str(role or "").strip()
    row_id = str(row_id or "").strip()

    if not principal and not row_id:
        raise RuntimeError("Permissão não informada.")

    if is_owner_principal(slug, principal, role, user):
        raise RuntimeError("Operação bloqueada: é proibido remover o próprio dono/proprietário do projeto.")

    cfg = detect_acl_config()
    c = con()
    try:
        table = cfg["table"]

        if row_id and cfg.get("id_col"):
            row = c.execute(f"SELECT * FROM {table} WHERE {cfg['id_col']}=? LIMIT 1", (row_id,)).fetchone()
            if row:
                nrow = normalize_acl_row(cfg, dict(row))
                if is_owner_principal(slug, nrow["principal"], nrow["role"], user):
                    raise RuntimeError("Operação bloqueada: é proibido remover o próprio dono/proprietário do projeto.")

            c.execute(f"DELETE FROM {table} WHERE {cfg['id_col']}=?", (row_id,))
            c.commit()
            sync=sync_komodo_acl(slug)
            if not sync.get('ok'):
                return "Permissão removida. Sincronização imediata com o Komodo pendente; reconciliação durável será enfileirada."
            return "Permissão removida."

        where = f"{cfg['project_col']}=? AND {cfg['principal_col']}=?"
        params = [slug, principal]

        if cfg.get("type_col") and principal_type:
            where += f" AND {cfg['type_col']}=?"
            params.append(principal_type)

        if cfg.get("role_col") and role:
            where += f" AND {cfg['role_col']}=?"
            params.append(role)

        c.execute(f"DELETE FROM {table} WHERE {where}", params)
        c.commit()
        sync=sync_komodo_acl(slug)
        if not sync.get('ok'):
            return "Permissão removida. Sincronização imediata com o Komodo pendente; reconciliação durável será enfileirada."
        return "Permissão removida."
    finally:
        c.close()

def render_acl_modal(slug, user=None):
    modal_id = "wiz_acl_" + slug.replace("-", "_").replace(".", "_")

    try:
        cfg, rows_raw = acl_rows(slug)
        rows = [normalize_acl_row(cfg, r) for r in rows_raw]
        owner = project_owner(slug)
        detected = f"{cfg['table']} ({cfg['project_col']}, {cfg['principal_col']})"
        error = ""
    except Exception as e:
        rows = []
        owner = ""
        detected = ""
        error = str(e)

    if error:
        body = f"""
<p class="small">Não foi possível carregar a ACL real deste projeto.</p>
<div class="wizard-note">
  <strong>Erro:</strong><br>{h(error)}
</div>
<p class="small">Nenhum dado de exemplo foi exibido.</p>
"""
    else:
        table_rows = []

        for r in rows:
            protected = is_owner_principal(slug, r["principal"], r["role"], user)
            remove_button = (
                '<span class="pill">dono protegido</span>'
                if protected else
                f"""
<form method="post" action="/cloudiff/portal/action/project_acl" style="display:inline">
  <input type="hidden" name="op" value="remove">
  <input type="hidden" name="slug" value="{h(slug)}">
  <input type="hidden" name="row_id" value="{h(r["id"])}">
  <input type="hidden" name="principal" value="{h(r["principal"])}">
  <input type="hidden" name="principal_type" value="{h(r["type"])}">
  <input type="hidden" name="role" value="access">
  <button class="btn light" type="submit">Remover</button>
</form>
"""
            )

            table_rows.append(f"""
<tr>
  <td>{h(r["type"])}</td>
  <td><strong>{h(r["principal"])}</strong></td>
  <td>access</td>
  <td>{remove_button}</td>
</tr>
""")

        if not table_rows:
            table_rows.append('<tr><td colspan="4" class="small">Nenhuma permissão cadastrada para este projeto.</td></tr>')

        body = f"""
<div class="acl-modal-meta">
  <div><span>Fonte de permissões</span><strong><code>{h(detected)}</code></strong></div>
  {f'<div><span>Proprietário protegido</span><strong>{h(owner)}</strong></div>' if owner else ''}
</div>

<section class="acl-modal-section acl-current-section">
  <div class="acl-modal-section-head">
    <div><h4>Permissões atuais</h4><p>Usuários e grupos com acesso ao projeto.</p></div>
    <span class="acl-count">{len(rows)} acesso{'' if len(rows)==1 else 's'}</span>
  </div>
<table class="cm-table acl-current-table">
  <thead>
    <tr>
      <th>Tipo</th>
      <th>Usuário/Grupo</th>
      <th>Permissão</th>
      <th>Ação</th>
    </tr>
  </thead>
  <tbody>
    {''.join(table_rows)}
  </tbody>
</table>
</section>

<section class="acl-modal-section acl-add-section">
  <div class="acl-modal-section-head">
    <div><h4>Adicionar permissão</h4><p>Pesquise uma identidade real no diretório institucional.</p></div>
  </div>

<div class="cm-field acl-search-field">
  <label>Buscar usuário ou grupo</label>
  <input id="acl_search_{h(modal_id)}" placeholder="Digite login, matrícula, nome completo ou grupo" autocomplete="off">
  <div id="acl_results_{h(modal_id)}" class="acl-search-results"></div>
  <div class="acl-search-help">Clique em um resultado para preencher automaticamente o usuário/grupo e o tipo de permissão.</div>
</div>

<form class="acl-add-form" method="post" action="/cloudiff/portal/action/project_acl" onsubmit="return cloudifValidateAclSelection_{h(modal_id)}()">
  <input type="hidden" name="op" value="add">
  <input type="hidden" name="slug" value="{h(slug)}">
  <input type="hidden" name="role" value="access">
  <input type="hidden" id="acl_principal_hidden_{h(modal_id)}" name="principal" required>
  <input type="hidden" id="acl_principal_type_hidden_{h(modal_id)}" name="principal_type" required>

  <div class="acl-selection-grid">
  <div class="cm-field">
    <label>Tipo identificado</label>
    <select id="acl_principal_type_view_{h(modal_id)}" disabled>
      <option value="">Selecione na busca</option>
      <option value="user">Usuário</option>
      <option value="group">Grupo</option>
    </select>
  </div>

  <div class="cm-field">
    <label>Usuário ou grupo selecionado</label>
    <input id="acl_principal_{h(modal_id)}" disabled placeholder="Selecione um resultado da busca">
  </div>
  </div>

  <div class="cm-actions acl-form-actions">
    <button class="cm-btn cm-primary" type="submit">Adicionar permissão</button>
  </div>
</form>
</section>

<script>
(function(){{
  var search = document.getElementById("acl_search_{h(modal_id)}");
  var principalView = document.getElementById("acl_principal_{h(modal_id)}");
  var principalHidden = document.getElementById("acl_principal_hidden_{h(modal_id)}");
  var typeView = document.getElementById("acl_principal_type_view_{h(modal_id)}");
  var typeHidden = document.getElementById("acl_principal_type_hidden_{h(modal_id)}");
  var results = document.getElementById("acl_results_{h(modal_id)}");
  var timer = null;
  var projectSlug = "{h(slug)}";

  if(!search || !principalView || !principalHidden || !typeView || !typeHidden || !results) return;

  function esc(v){{
    return String(v || '').replace(/[&<>"']/g, function(c){{
      return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c];
    }});
  }}

  function attr(v){{
    return esc(v).replace(/"/g, '&quot;');
  }}

  function cleanPrincipal(txt){{
    txt = (txt || "").trim();
    if(!txt) return "";
    return txt.split(/\\s+/)[0];
  }}

  function renderMessage(msg){{
    results.innerHTML =
      '<div class="acl-result-dropdown">' +
        '<div class="acl-result-item" role="note">' +
          '<div class="acl-result-meta">' + esc(msg) + '</div>' +
        '</div>' +
      '</div>';
  }}

  function selectPrincipal(txt, typ){{
    txt = cleanPrincipal(txt);
    typ = (typ || "").trim();

    if(!txt) return;

    principalView.value = txt;
    principalHidden.value = txt;

    if(typ){{
      typeView.value = typ;
      typeHidden.value = typ;
    }}

    results.innerHTML = "";
    search.value = txt;
  }}

  function renderItems(arr){{
    if(!arr || !arr.length){{
      renderMessage("Nenhum resultado encontrado no diretório real.");
      return;
    }}

    results.innerHTML = '<div class="acl-result-dropdown">' + arr.map(function(x){{
      var label = x.principal || x.username || x.samaccountname || x.sAMAccountName || x.uid || x.cn || x.name || x.email || x.group || x.label || "";
      var type = x.type || "";
      var full = x.full_name || x.displayName || x.display_name || x.cn || x.name || "";
      var mail = x.mail || x.email || "";
      var source = x.source || "";
      var groups = Array.isArray(x.groups) ? x.groups : [];

      var groupHtml = groups.length
        ? '<div class="acl-result-groups">' + groups.slice(0, 8).map(function(g){{
            return '<span class="acl-result-group">' + esc(g) + '</span>';
          }}).join('') + (groups.length > 8 ? '<span class="acl-result-group">+' + (groups.length - 8) + '</span>' : '') + '</div>'
        : '<div class="acl-result-groups"><span class="acl-result-group">sem grupos retornados</span></div>';

      return '<button type="button" class="acl-result-item" data-principal="' + attr(label) + '" data-type="' + attr(type) + '">' +
        '<div class="acl-result-main">' +
          '<span class="acl-result-principal">' + esc(label) + '</span>' +
          '<span class="acl-result-type">' + esc(type || "principal") + '</span>' +
        '</div>' +
        '<div class="acl-result-meta">' +
          (full ? '<div><strong>Nome completo:</strong> ' + esc(full) + '</div>' : '<div><strong>Nome completo:</strong> não retornado</div>') +
          (mail ? '<div><strong>E-mail:</strong> ' + esc(mail) + '</div>' : '') +
          (source ? '<div><strong>Fonte:</strong> ' + esc(source) + '</div>' : '') +
        '</div>' +
        groupHtml +
      '</button>';
    }}).join('') + '</div>';
  }}

  results.addEventListener("click", function(ev){{
    var item = ev.target.closest ? ev.target.closest(".acl-result-item[data-principal]") : null;
    if(!item) return;

    ev.preventDefault();
    ev.stopPropagation();

    var txt = item.getAttribute("data-principal") || "";
    var typ = item.getAttribute("data-type") || "";

    selectPrincipal(txt, typ);
  }}, true);

  window.cloudifValidateAclSelection_{h(modal_id)} = function(){{
    if(!principalHidden.value || !typeHidden.value){{
      renderMessage("Selecione um usuário ou grupo no resultado da busca antes de adicionar a permissão.");
      return false;
    }}
    return true;
  }};

  search.addEventListener("input", function(){{
    clearTimeout(timer);
    var q = search.value.trim();

    principalView.value = "";
    principalHidden.value = "";
    typeView.value = "";
    typeHidden.value = "";

    if(!q){{
      results.innerHTML = "";
      return;
    }}

    results.innerHTML = '<div class="acl-result-dropdown"><div class="acl-result-item" role="note"><div class="acl-result-meta">Pesquisando...</div></div></div>';

    timer = setTimeout(function(){{
      var endpoint = new URL("api/ad-search", window.location.href);
      endpoint.searchParams.set("q", q);
      endpoint.searchParams.set("type", "all");
      endpoint.searchParams.set("slug", projectSlug);

      fetch(endpoint.toString(), {{
        headers: {{"Accept": "application/json"}},
        credentials: "same-origin"
      }})
        .then(function(r){{
          var ct = r.headers.get("content-type") || "";
          if(ct.indexOf("application/json") < 0){{
            throw new Error("A API retornou uma resposta não JSON. A tela legada não será exibida aqui.");
          }}
          return r.json();
        }})
        .then(function(data){{
          if(data && data.ok === false){{
            renderMessage(data.error || "Busca não autorizada.");
            return;
          }}

          var arr = Array.isArray(data) ? data : (data.items || data.results || []);
          renderItems(arr);
        }})
        .catch(function(err){{
          renderMessage(err && err.message ? err.message : "Busca indisponível.");
        }});
    }}, 500);
  }});

  // Autoabre este modal após redirect de ADD/REMOVE: ?acl=<slug>&msg=...
  (function(){{
    var params = new URLSearchParams(window.location.search);
    var acl = params.get("acl");
    if(acl !== "{h(slug)}") return;

    if(typeof cloudifShowWizard === "function"){{
      cloudifShowWizard("{h(modal_id)}");
    }}

    var msg = params.get("msg");
    if(msg){{
      var box = document.getElementById("{h(modal_id)}");
      if(box){{
        var notice = document.createElement("div");
        notice.className = "wizard-note";
        notice.innerHTML = "<strong>Resultado:</strong> " + esc(msg);
        var head = box.querySelector(".wizard-head");
        if(head && head.parentNode){{
          head.parentNode.insertBefore(notice, head.nextSibling);
        }}
      }}
    }}
  }})();
}})();
</script>
"""

    return f"""
<style>
#{h(modal_id)} .wizard-box{{width:min(880px,100%);overflow:hidden}}
#{h(modal_id)} .wizard-head{{align-items:center;padding:22px 24px}}
#{h(modal_id)} .wizard-head h3{{font-size:1.3rem}}
#{h(modal_id)} .wizard-head p{{margin:4px 0 0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.75rem}}
#{h(modal_id)} .acl-modal-content{{display:grid;gap:18px;padding:20px 24px 24px}}
#{h(modal_id)} .acl-modal-meta{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
#{h(modal_id)} .acl-modal-meta>div{{display:grid;gap:4px;padding:12px 14px;border:1px solid var(--c-border,#dce3ed);border-radius:10px;background:var(--c-surface-2,#f8fafc);min-width:0}}
#{h(modal_id)} .acl-modal-meta span{{font-size:.68rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--c-muted,#64748b)}}
#{h(modal_id)} .acl-modal-meta strong{{font-size:.82rem;overflow-wrap:anywhere}}
#{h(modal_id)} .acl-modal-section{{display:grid;gap:14px;padding:16px;border:1px solid var(--c-border,#dce3ed);border-radius:12px;background:var(--c-surface,#fff)}}
#{h(modal_id)} .acl-modal-section-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}}
#{h(modal_id)} .acl-modal-section-head h4{{margin:0;font-size:.98rem}}
#{h(modal_id)} .acl-modal-section-head p{{margin:3px 0 0;color:var(--c-muted,#64748b);font-size:.78rem}}
#{h(modal_id)} .acl-count{{flex:none;padding:4px 8px;border-radius:999px;background:var(--c-surface-2,#f1f5f9);color:var(--c-muted,#64748b);font-size:.7rem;font-weight:800}}
#{h(modal_id)} .acl-current-table{{margin:0}}
#{h(modal_id)} .acl-current-table td,#{h(modal_id)} .acl-current-table th{{vertical-align:middle}}
#{h(modal_id)} .acl-search-field{{position:relative;margin:0}}
#{h(modal_id)} .acl-search-help{{margin-top:6px;font-size:.72rem;color:var(--c-muted,#64748b)}}
#{h(modal_id)} .acl-selection-grid{{display:grid;grid-template-columns:minmax(180px,.7fr) minmax(0,1.3fr);gap:12px}}
#{h(modal_id)} .acl-add-form{{display:grid;gap:12px}}
#{h(modal_id)} .acl-form-actions{{display:flex;justify-content:flex-end;margin:2px 0 0}}
#{h(modal_id)} .acl-form-actions .cm-btn{{width:auto;min-width:170px}}
#{h(modal_id)} .pill{{white-space:nowrap}}
@media(max-width:700px){{
  #{h(modal_id)} .wizard-head{{padding:18px}}
  #{h(modal_id)} .acl-modal-content{{padding:16px;gap:14px}}
  #{h(modal_id)} .acl-modal-meta,#{h(modal_id)} .acl-selection-grid{{grid-template-columns:1fr}}
  #{h(modal_id)} .acl-current-section{{overflow-x:auto}}
  #{h(modal_id)} .acl-current-table{{min-width:620px}}
  #{h(modal_id)} .acl-form-actions .cm-btn{{width:100%}}
}}
</style>
<div id="{h(modal_id)}" class="wizard">
  <div class="wizard-box">
    <div class="wizard-head">
      <div>
        <h3>Gerenciar permissões</h3>
        <p>{h(slug)}</p>
      </div>
      <button class="wizard-close" type="button" aria-label="Fechar" onclick="cloudifHideWizard('{h(modal_id)}')">×</button>
    </div>
    <div class="acl-modal-content">{body}</div>
  </div>
</div>
"""

def handle_project_acl_action(form, user=None):
    def val(k, default=""):
        v = form.get(k, default)
        if isinstance(v, list):
            return v[0] if v else default
        return v or default

    op = val("op")
    slug = val("slug")

    if not slug:
        raise RuntimeError("Projeto não informado.")

    if op == "add":
        return add_acl(
            slug=slug,
            principal=val("principal"),
            principal_type=val("principal_type", "user"),
            role="access",
            user=user,
        )

    if op == "remove":
        return remove_acl(
            slug=slug,
            principal=val("principal"),
            principal_type=val("principal_type"),
            role="access",
            row_id=val("row_id"),
            user=user,
        )

    raise RuntimeError("Operação inválida.")
