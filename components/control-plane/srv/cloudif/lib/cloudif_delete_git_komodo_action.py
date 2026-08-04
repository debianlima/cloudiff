# CloudIF v135b2 — ação segura para excluir Git/Komodo sem excluir tenant/banco
import html
import json
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path

DB_DEFAULT = "/var/lib/cloudif/portal/cloudif-portal.db"

DELETE_ALIASES = {
    "delete_project",
    "delete_git_komodo",
    "excluir_projeto",
    "excluir_git_komodo",
    "project_delete",
    "project_rollback",
    "rollback_project",
    "remove_project",
    "remove_git_komodo",
}

def h(x):
    return html.escape(str(x if x is not None else ""))

def read_env(path):
    data = {}
    p = Path(path)
    if not p.exists():
        return data
    for raw in p.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data

def db_path():
    env = read_env("/etc/cloudif/portal.env")
    return env.get("CLOUDIF_PORTAL_DB") or DB_DEFAULT

def forja_config():
    env1 = read_env("/etc/cloudif/forja-agent-client.env")
    env2 = read_env("/etc/cloudif/provision.env")
    url = (
        env1.get("FORJA_AGENT_URL")
        or env2.get("FORJA_AGENT_URL")
        or "http://10.62.91.2:18095"
    ).rstrip("/")
    token = env1.get("FORJA_AGENT_TOKEN") or env2.get("FORJA_AGENT_TOKEN") or ""
    return url, token

def form_get(form, key, default=""):
    try:
        if hasattr(form, "getvalue"):
            return form.getvalue(key) or default
        value = form.get(key, default)
        if isinstance(value, (list, tuple)):
            return value[0] if value else default
        return value
    except Exception:
        return default

def request_op(form):
    return (
        form_get(form, "op")
        or form_get(form, "action")
        or form_get(form, "cmd")
        or form_get(form, "operation")
        or ""
    ).strip()

def request_slug(form):
    return (
        form_get(form, "slug")
        or form_get(form, "project_slug")
        or form_get(form, "project")
        or form_get(form, "name")
        or ""
    ).strip()

def header_get(headers, key):
    if not headers:
        return ""
    candidates = [key, key.lower(), key.upper()]
    for k in candidates:
        try:
            v = headers.get(k)
            if v:
                return str(v)
        except Exception:
            pass
    return ""

def actor_variants(actor="", headers=None):
    vals = set()

    def add(v):
        v = str(v or "").strip()
        if not v:
            return
        vals.add(v)
        vals.add(v.lower())
        if "@" in v:
            vals.add(v.split("@", 1)[0])
            vals.add(v.split("@", 1)[0].lower())

    add(actor)

    for k in [
        "X-Authentik-Username",
        "X-Authentik-Email",
        "X-Forwarded-User",
        "X-Forwarded-Email",
        "Remote-User",
        "REMOTE_USER",
    ]:
        add(header_get(headers, k))

    return {v for v in vals if v}

def actor_groups(actor="", headers=None):
    raw = " ".join([
        str(actor or ""),
        header_get(headers, "X-Authentik-Groups"),
        header_get(headers, "X-Forwarded-Groups"),
        header_get(headers, "X-Authentik-Entitlements"),
    ])

    out = set()
    for sep in [",", ";", "|", " "]:
        raw = raw.replace(sep, "\n")
    for part in raw.splitlines():
        part = part.strip()
        if part:
            out.add(part)
            out.add(part.lower())
    return out

def policy_admin_group():
    try:
        con = sqlite3.connect(db_path())
        con.row_factory = sqlite3.Row
        tables = {r["name"] for r in con.execute("select name from sqlite_master where type='table'")}
        if "policy" in tables:
            cols = [r["name"] for r in con.execute("pragma table_info(policy)")]
            key_col = "key" if "key" in cols else ("name" if "name" in cols else "")
            val_col = "value" if "value" in cols else ("val" if "val" in cols else "")
            if key_col and val_col:
                row = con.execute(
                    f"select {val_col} as v from policy where {key_col}='CLOUDIF_ADMIN_GROUP' limit 1"
                ).fetchone()
                if row and row["v"]:
                    return str(row["v"])
    except Exception:
        pass
    finally:
        try:
            con.close()
        except Exception:
            pass
    return "CloudIF-Tenants-Admin"

def is_global_admin(actor="", headers=None):
    groups = actor_groups(actor, headers)
    admin_group = policy_admin_group()
    admin_names = {
        admin_group,
        admin_group.lower(),
        "CloudIF-Tenants-Admin",
        "cloudif-tenants-admin",
        "Administrador",
        "administrador",
        "admin",
    }
    return bool(groups & admin_names)

def table_cols(con, table):
    try:
        return [r[1] for r in con.execute(f"pragma table_info({table})")]
    except Exception:
        return []

def is_project_owner(con, slug, variants):
    tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    if "projects" not in tables:
        return False

    cols = table_cols(con, "projects")
    if "slug" not in cols:
        return False

    owner_cols = [
        c for c in cols
        if c.lower() in {
            "owner", "owner_user", "owner_subject", "created_by",
            "created_by_user", "user", "username", "subject", "principal"
        }
    ]

    if not owner_cols:
        return False

    row = con.execute("select * from projects where slug=? limit 1", (slug,)).fetchone()
    if not row:
        return False

    for c in owner_cols:
        try:
            v = str(row[c] or "").strip()
        except Exception:
            v = ""
        if v and (v in variants or v.lower() in variants):
            return True
        if "@" in v and v.split("@", 1)[0].lower() in variants:
            return True

    return False

def is_project_admin_acl(con, slug, variants):
    tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    if "project_acl" not in tables:
        return False

    cols = table_cols(con, "project_acl")
    if "slug" not in cols:
        return False

    subject_cols = [c for c in cols if c.lower() in {"subject", "principal", "username", "user", "group_name", "name"}]
    role_cols = [c for c in cols if c.lower() in {"role", "permission", "permissao", "access", "level", "kind"}]

    if not subject_cols:
        return False

    rows = con.execute("select * from project_acl where slug=?", (slug,)).fetchall()

    for row in rows:
        subject_match = False
        for c in subject_cols:
            try:
                v = str(row[c] or "").strip()
            except Exception:
                v = ""
            if v and (v in variants or v.lower() in variants):
                subject_match = True
            if "@" in v and v.split("@", 1)[0].lower() in variants:
                subject_match = True

        if not subject_match:
            continue

        # Se houver coluna de papel/permissão, exige admin/owner/dono.
        # Se não houver, não concede admin automaticamente.
        if not role_cols:
            continue

        for c in role_cols:
            try:
                rv = str(row[c] or "").strip().lower()
            except Exception:
                rv = ""
            if rv in {"admin", "administrator", "owner", "dono", "dono_protegido", "protected_owner"}:
                return True

    return False

def can_delete_project(slug, actor="", headers=None):
    variants = actor_variants(actor, headers)

    if is_global_admin(actor, headers):
        return True, "admin global"

    try:
        con = sqlite3.connect(db_path())
        con.row_factory = sqlite3.Row
        try:
            if is_project_owner(con, slug, variants):
                return True, "dono do projeto"
            if is_project_admin_acl(con, slug, variants):
                return True, "admin do projeto"
        finally:
            con.close()
    except Exception as e:
        return False, f"erro ao checar permissão: {type(e).__name__}: {e}"

    return False, "usuário não é dono/admin do projeto"

def _project_repo_identity(slug):
    identity={'owner':'','repo':'','repo_url':'','owner_kind':'user'}
    try:
        con=sqlite3.connect(db_path());con.row_factory=sqlite3.Row
        project=con.execute('select owner,repo_url,repo_name from projects where slug=?',(slug,)).fetchone()
        integration=None
        try: integration=con.execute('select repo_url,forgejo_repo_url,repo_name from project_integrations where project=?',(slug,)).fetchone()
        except sqlite3.DatabaseError: pass
        con.close()
        repo_url=''
        if integration: repo_url=str(integration['forgejo_repo_url'] or integration['repo_url'] or '')
        if not repo_url and project: repo_url=str(project['repo_url'] or '')
        repo=str((integration['repo_name'] if integration and 'repo_name' in integration.keys() else '') or (project['repo_name'] if project else '') or ('cloudif-'+slug))
        owner=str(project['owner'] or '').strip().lower() if project else ''
        try:
            parsed=urllib.parse.urlparse(repo_url)
            parts=[x for x in parsed.path.split('/') if x]
            if 'git' in parts:
                parts=parts[parts.index('git')+1:]
            if len(parts)>=2:
                owner=parts[-2];repo=parts[-1].removesuffix('.git')
        except Exception: pass
        identity.update({'owner':owner,'repo':repo,'repo_url':repo_url,'owner_kind':'user'})
    except Exception: pass
    return identity

def forja_rollback(slug, execute=False):
    base, token = forja_config()
    identity=_project_repo_identity(slug)
    payload = {
        "project_slug": slug,
        "execute": bool(execute),
        "owner": identity.get("owner") or "",
        "repo": identity.get("repo") or "",
        "repo_url": identity.get("repo_url") or "",
        "owner_kind": identity.get("owner_kind") or "user",
    }
    if execute:
        payload["confirm"] = f"ROLLBACK {slug}"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if token:
        headers["X-CloudIF-Token"] = token
        headers["Authorization"] = "Bearer " + token

    req = urllib.request.Request(
        base + "/project/rollback",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                data = json.loads(raw) if raw else {}
            except Exception:
                data = {"raw": raw}
            return {"ok": 200 <= r.status < 300, "status": r.status, "data": data}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {"raw": raw}
        return {"ok": False, "status": e.code, "data": data}
    except Exception as e:
        return {"ok": False, "status": 0, "error": f"{type(e).__name__}: {e}", "data": {}}

def clear_cache(slug):
    try:
        con = sqlite3.connect(db_path())
        try:
            con.execute("delete from project_runtime_status where slug=?", (slug,))
            con.commit()
        finally:
            con.close()
        return True
    except Exception:
        return False

def confirmation_page(slug, actor="", headers=None):
    allowed, reason = can_delete_project(slug, actor, headers)
    dry = forja_rollback(slug, execute=False) if allowed else {"ok": False, "data": {"message": "dry-run não executado sem permissão"}}

    if not allowed:
        return f'''
<div class="card">
  <h2>Exclusão não permitida</h2>
  <p>Projeto: <code>{h(slug)}</code></p>
  <p>Motivo: {h(reason)}</p>
  <p>Esta ação é permitida apenas para dono do projeto, admin do projeto ou admin global.</p>
  <p><a class="btn" href="/cloudiff/portal/?tab=git">Voltar</a></p>
</div>
'''

    return f'''
<div class="card">
  <h2>Confirmar exclusão Git/Komodo</h2>

  <p><strong>Projeto:</strong> <code>{h(slug)}</code></p>
  <p><strong>Permissão:</strong> {h(reason)}</p>

  <div class="alert" style="padding:12px;border:1px solid #f59e0b;border-radius:12px;background:#fffbeb">
    <strong>Atenção:</strong> isto removerá o repositório no Forgejo/Git e os vínculos/registros no Komodo.
    <br>
    O banco/tenant Supabase <strong>não será excluído aqui</strong>. Para excluir banco, use o menu <strong>Bancos / Tenants</strong>.
  </div>

  <h3>Dry-run remoto</h3>
  <pre style="white-space:pre-wrap;max-height:320px;overflow:auto">{h(json.dumps(dry.get("data"), ensure_ascii=False, indent=2)[:8000])}</pre>

  <form method="post" action="/cloudiff/portal/git-komodo/action">
    <input type="hidden" name="op" value="delete_git_komodo">
    <input type="hidden" name="slug" value="{h(slug)}">
    <input type="hidden" name="execute" value="1">

    <label>Digite exatamente: <code>EXCLUIR {h(slug)}</code></label>
    <input name="confirm_text" style="width:100%;padding:10px;border:1px solid #dfe8dd;border-radius:10px" placeholder="EXCLUIR {h(slug)}">

    <p style="margin-top:12px">
      <button class="btn danger" type="submit">Excluir Git/Komodo</button>
      <a class="btn light" href="/cloudiff/portal/?tab=git">Cancelar</a>
    </p>
  </form>
</div>
'''

def result_page(slug, res, actor="", reason=""):
    clear_ok = clear_cache(slug)

    return f'''
<div class="card">
  <h2>Resultado da exclusão Git/Komodo</h2>
  <p><strong>Projeto:</strong> <code>{h(slug)}</code></p>
  <p><strong>Permissão:</strong> {h(reason)}</p>
  <p><strong>HTTP remoto:</strong> {h(res.get("status"))}</p>
  <p><strong>OK remoto:</strong> {h(res.get("ok"))}</p>
  <p><strong>Cache local removido:</strong> {h(clear_ok)}</p>

  <details open>
    <summary>Resposta do Forja Agent</summary>
    <pre style="white-space:pre-wrap;max-height:420px;overflow:auto">{h(json.dumps(res.get("data"), ensure_ascii=False, indent=2)[:12000])}</pre>
  </details>

  <p>
    <a class="btn" href="/cloudiff/portal/?tab=git">Voltar para Git + Komodo</a>
    <a class="btn light" href="/cloudiff/portal/?tab=projetos">Voltar para Projetos</a>
  </p>
</div>
'''

def handle_delete_git_komodo(form, actor="portal", headers=None):
    op = request_op(form)
    if op not in DELETE_ALIASES:
        return None

    slug = request_slug(form)
    if not slug:
        return '''
<div class="card">
  <h2>Erro</h2>
  <p>Slug do projeto não informado.</p>
  <p><a class="btn" href="/cloudiff/portal/?tab=git">Voltar</a></p>
</div>
'''

    execute = str(form_get(form, "execute", "")).strip() in {"1", "true", "yes", "sim"}
    confirm_text = str(form_get(form, "confirm_text", "")).strip()

    allowed, reason = can_delete_project(slug, actor, headers)
    if not allowed:
        return f'''
<div class="card">
  <h2>Exclusão não permitida</h2>
  <p>Projeto: <code>{h(slug)}</code></p>
  <p>Motivo: {h(reason)}</p>
  <p>Esta ação é permitida apenas para dono do projeto, admin do projeto ou admin global.</p>
  <p><a class="btn" href="/cloudiff/portal/?tab=git">Voltar</a></p>
</div>
'''

    if not execute:
        return confirmation_page(slug, actor, headers)

    expected = f"EXCLUIR {slug}"
    if confirm_text != expected:
        return f'''
<div class="card">
  <h2>Confirmação inválida</h2>
  <p>Para excluir Git/Komodo do projeto <code>{h(slug)}</code>, digite exatamente:</p>
  <p><code>{h(expected)}</code></p>
  <p><a class="btn" href="/cloudiff/portal/?tab=git">Voltar</a></p>
</div>
'''

    res = forja_rollback(slug, execute=True)
    return result_page(slug, res, actor, reason)


# CloudIF v135b4 — wrapper seguro para impedir 502
def safe_handle_delete_git_komodo(form, actor="portal", headers=None):
    try:
        return handle_delete_git_komodo(form, actor=actor, headers=headers)
    except Exception as exc:
        return (
            '<div class="card">'
            '<h2>Erro controlado na exclusão Git/Komodo</h2>'
            '<p>' + h(type(exc).__name__) + ': ' + h(str(exc)) + '</p>'
            '<p>Nenhum recurso foi excluído.</p>'
            '<p><a class="btn" href="/cloudiff/portal/?tab=git">Voltar</a></p>'
            '</div>'
        )
