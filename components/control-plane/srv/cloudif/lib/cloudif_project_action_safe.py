#!/usr/bin/env python3
import json
import os
import fcntl
import uuid
import re
import sqlite3
import subprocess
import time
from pathlib import Path

DB = "/var/lib/cloudif/portal/cloudif-portal.db"
JOBDIR = Path("/srv/cloudif/jobs")
LOG = Path("/var/log/cloudif/project-provision.log")
LOCK_ROOT = Path("/run/cloudif-operation-locks")

def _log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%S%z") + " " + str(msg) + "\n")

def h(x):
    import html
    return html.escape("" if x is None else str(x))

def slugify(value, keep_dash=True):
    value = str(value or "").strip().lower()
    value = (
        value.replace("á","a").replace("à","a").replace("ã","a").replace("â","a")
             .replace("é","e").replace("ê","e")
             .replace("í","i")
             .replace("ó","o").replace("õ","o").replace("ô","o")
             .replace("ú","u")
             .replace("ç","c")
    )
    if keep_dash:
        value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    else:
        value = re.sub(r"[^a-z0-9]+", "", value)
    return value or "projeto"

def now_stamp():
    return time.strftime("%Y%m%d%H%M%S")

def user_from_headers(headers):
    groups_raw = headers.get("X-authentik-groups") or headers.get("X-Authentik-Groups") or ""
    groups = [g.strip() for g in groups_raw.replace("|", ",").split(",") if g.strip()]
    username = (
        headers.get("X-authentik-username")
        or headers.get("X-Authentik-Username")
        or headers.get("X-Forwarded-User")
        or ""
    ).strip()
    email = (
        headers.get("X-authentik-email")
        or headers.get("X-Authentik-Email")
        or ""
    ).strip()
    return {
        "username": username or (email.split("@")[0] if email else "unknown"),
        "email": email,
        "groups": groups,
    }

def val(form, key, default=""):
    v = form.get(key, default)
    if isinstance(v, list):
        return v[0] if v else default
    return v or default

def db():
    con = sqlite3.connect(DB, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=20000")
    return con

def tables(con):
    return [r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]

def cols(con, table):
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]

def pick(cols_, names):
    low = {c.lower(): c for c in cols_}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return ""

def generate_tenant(form, user):
    mode = val(form, "db_mode", "skip")
    posted = val(form, "tenant", "").strip()
    username = slugify(user.get("username") or "usuario", keep_dash=False)

    if mode == "skip":
        return ""

    if mode == "link":
        return posted

    if mode == "create":
        if posted:
            # O JS do wizard já deve ter gerado usuario-nome. Mantém se vier seguro.
            safe = slugify(posted, keep_dash=True)
            return safe

        suffix = (
            val(form, "tenant_suffix", "")
            or val(form, "tenant_name", "")
            or val(form, "tenant_new", "")
            or val(form, "name", "")
            or now_stamp()
        )
        suffix = slugify(suffix, keep_dash=False)
        if not suffix:
            suffix = now_stamp()
        return f"{username}-{suffix}"

    return posted

def ensure_tenant_record(con, tenant, user):
    if not tenant:
        return

    if "tenants" not in tables(con):
        return

    c = cols(con, "tenants")
    tenant_col = pick(c, ["tenant", "name", "slug"])
    if not tenant_col:
        return

    exists = con.execute(f"SELECT COUNT(*) FROM tenants WHERE {tenant_col}=?", (tenant,)).fetchone()[0]
    if exists:
        return

    values = {tenant_col: tenant}

    for col in c:
        low = col.lower()
        if low in ["owner", "created_by", "username", "user"]:
            values[col] = user.get("username", "")
        elif low in ["email", "owner_email"]:
            values[col] = user.get("email", "")
        elif low in ["status"]:
            values[col] = "pending"
        elif low in ["created_at", "updated_at"]:
            values[col] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    names = list(values)
    sql = f"INSERT INTO tenants ({','.join(names)}) VALUES ({','.join(['?']*len(names))})"
    con.execute(sql, [values[n] for n in names])

def ensure_project_acl_owner(con, slug, user):
    if "project_acl" not in tables(con):
        return

    c = cols(con, "project_acl")
    slug_col = pick(c, ["slug", "project_slug", "project"])
    type_col = pick(c, ["subject_type", "principal_type", "type"])
    subject_col = pick(c, ["subject", "principal", "user", "username"])
    role_col = pick(c, ["role", "permission", "access"])

    if not slug_col or not subject_col:
        return

    username = user.get("username", "")
    if not username:
        return

    params = [slug, username]
    where = f"{slug_col}=? AND {subject_col}=?"
    if type_col:
        where += f" AND {type_col}='user'"

    exists = con.execute(f"SELECT COUNT(*) FROM project_acl WHERE {where}", params).fetchone()[0]
    if exists:
        return

    values = {
        slug_col: slug,
        subject_col: username,
    }
    if type_col:
        values[type_col] = "user"
    if role_col:
        values[role_col] = "access"

    names = list(values)
    con.execute(
        f"INSERT INTO project_acl ({','.join(names)}) VALUES ({','.join(['?']*len(names))})",
        [values[n] for n in names]
    )

def upsert_project(form, user):
    action = val(form, "action", "create_project")
    name = val(form, "name", "").strip()
    description = val(form, "description", "").strip()
    posted_slug = val(form, "slug", "").strip()
    tenant = generate_tenant(form, user)

    slug = posted_slug or slugify(name or ("projeto-" + now_stamp()), keep_dash=True)
    if not slug:
        raise RuntimeError("Nome/slug do projeto não informado.")

    runtime_template = val(form, "runtime_template", "node22").strip().lower()
    allowed_runtimes = {"node20", "node22", "node24"}
    if runtime_template not in allowed_runtimes:
        raise ValueError("Tecnologia web não homologada.")
    php_version = val(form, "php_version", "8.3").strip()
    if php_version not in {"8.2", "8.3", "8.4"}:
        raise ValueError("Versão do PHP não homologada.")
    try:
        tenant_keepalive_hours = int(val(form, "tenant_keepalive_hours", "6") or "6")
    except (TypeError, ValueError):
        raise ValueError("Tempo inicial do banco inválido.")
    if not 1 <= tenant_keepalive_hours <= 24:
        raise ValueError("O tempo inicial do banco deve ficar entre 1 e 24 horas.")

    con = db()
    try:
        if "projects" not in tables(con):
            raise RuntimeError("Tabela projects não encontrada no SQLite.")

        c = cols(con, "projects")

        slug_col = pick(c, ["slug", "project_slug"])
        name_col = pick(c, ["name", "title"])
        desc_col = pick(c, ["description", "descr", "summary"])
        tenant_col = pick(c, ["tenant", "tenant_slug", "db_tenant"])
        owner_col = pick(c, ["owner", "created_by", "username", "user"])
        email_col = pick(c, ["email", "owner_email"])
        updated_col = pick(c, ["updated_at", "modified_at"])
        created_col = pick(c, ["created_at"])

        if not slug_col:
            raise RuntimeError("Tabela projects não possui coluna slug/project_slug.")

        exists = con.execute(f"SELECT COUNT(*) FROM projects WHERE {slug_col}=?", (slug,)).fetchone()[0]
        owner_project_count = 0
        if owner_col:
            owner_project_count = con.execute(
                f"SELECT COUNT(*) FROM projects WHERE {owner_col}=?",
                (user.get("username", ""),),
            ).fetchone()[0]
        template_kind = "onboarding" if (not exists and owner_project_count == 0) else ("links" if not exists else "none")

        values = {slug_col: slug}

        if name_col:
            values[name_col] = name or slug
        if desc_col:
            values[desc_col] = description
        if tenant_col:
            values[tenant_col] = tenant
        if owner_col:
            values[owner_col] = user.get("username", "")
        if email_col:
            values[email_col] = user.get("email", "")
        if updated_col:
            values[updated_col] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        if created_col and not exists:
            values[created_col] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

        if exists:
            set_cols = [k for k in values if k != slug_col]
            if set_cols:
                sql = f"UPDATE projects SET {','.join([k+'=?' for k in set_cols])} WHERE {slug_col}=?"
                con.execute(sql, [values[k] for k in set_cols] + [slug])
        else:
            names = list(values)
            sql = f"INSERT INTO projects ({','.join(names)}) VALUES ({','.join(['?']*len(names))})"
            con.execute(sql, [values[n] for n in names])

        ensure_tenant_record(con, tenant, user)
        ensure_project_acl_owner(con, slug, user)

        con.commit()
    finally:
        con.close()

    job = {
        "action": action,
        "slug": slug,
        "name": name or slug,
        "description": description,
        "tenant": tenant,
        "db_mode": val(form, "db_mode", "skip"),
        "tenant_keepalive_hours": tenant_keepalive_hours,
        "create_repo": val(form, "create_repo", "1"),
        "setup_komodo": val(form, "setup_komodo", "1"),
        "template_kind": template_kind,
        "runtime_template": runtime_template,
        "runtime_layout": "managed-root-v1",
        "php_version": php_version,
        "role_profile": "project-admin",
        "environment": "project",
        "status": "queued",
        "current_step": "queued",
        "last_error": "",
        "user": user,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }

    queued = queue_provision_job(job)

    reconcile = None
    try:
        import sys as _reconcile_sys
        if "/srv/cloudif/lib" not in _reconcile_sys.path:
            _reconcile_sys.path.insert(0, "/srv/cloudif/lib")
        from cloudif_reconcile_client import enqueue as _enqueue_reconcile
        reconcile = _enqueue_reconcile(
            "project.created" if action == "create_project" else "project.updated",
            actor=user.get("username") or "portal",
            username=user.get("username") or "",
            project=slug,
            tenant=tenant,
            payload={
                "source": "project_action",
                "create_repo": job.get("create_repo"),
                "setup_komodo": job.get("setup_komodo"),
                "db_mode": job.get("db_mode"),
                "runtime_template": job.get("runtime_template"),
                "runtime_layout": job.get("runtime_layout"),
            },
            dedupe_seconds=0,
        )
    except Exception as exc:
        _log("RECONCILE_ENQUEUE_ERROR " + type(exc).__name__)

    reconcile_suffix = ""
    if isinstance(reconcile, dict) and reconcile.get("request_id"):
        reconcile_suffix = " Reconciliação: " + reconcile["request_id"][:8] + " (" + reconcile.get("status", "queued") + ")."
    return {
        "slug": slug,
        "tenant": tenant,
        "reconcile": reconcile,
        "job_file": queued.get("job_file"),
        "deduplicated": bool(queued.get("deduplicated")),
        "message": ("Provisionamento já estava em andamento. " if queued.get("deduplicated") else "Projeto registrado. ") + "Acompanhe o estado do provisionamento; ele só será concluído após identidade, capacidades, conectores, template e publicação inicial." + reconcile_suffix,
    }


def _latest_active_project_job(slug):
    candidates = sorted(JOBDIR.glob(f"project-provision-*-{slug}.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("status") in {"queued", "running"}:
            return path, data
    return None, None


def _project_provision_unit(job_id):
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(job_id or ""))[:32].strip("-")
    return "cloudif-project-provision-" + (safe or uuid.uuid4().hex[:16])


def _start_project_provision_unit(job_file, lock_path, job_id):
    unit = _project_provision_unit(job_id)
    cmd = [
        "/usr/bin/systemd-run",
        "--quiet",
        "--collect",
        f"--unit={unit}",
        "--property=Type=exec",
        "--property=RuntimeMaxSec=4h",
        "--property=NoNewPrivileges=true",
        "--setenv=PYTHONPATH=/srv/cloudif/lib",
        "/usr/bin/flock",
        "-x",
        str(lock_path),
        "/usr/bin/python3",
        "/srv/cloudif/lib/cloudif_project_provision_worker.py",
        str(job_file),
    ]
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    if result.returncode:
        raise RuntimeError("project_provision_systemd_start_failed: " + (result.stderr or result.stdout or "")[-500:])
    return unit + ".service"


def queue_provision_job(job):
    JOBDIR.mkdir(parents=True, exist_ok=True)
    LOCK_ROOT.mkdir(parents=True, exist_ok=True)
    lock_path = LOCK_ROOT / f"project-{job['slug']}.lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        existing_path, existing = _latest_active_project_job(job['slug'])
        if existing_path:
            _log(f"DEDUP {existing_path}")
            return {"job_file": str(existing_path), "deduplicated": True, "job": existing}
        raise RuntimeError("project_provision_already_running")

    try:
        job_id = uuid.uuid4().hex
        job["job_id"] = job_id
        job["project_lock"] = str(lock_path)
        job["systemd_unit"] = _project_provision_unit(job_id) + ".service"
        job_file = JOBDIR / f"project-provision-{job_id}-{job['slug']}.json"
        job_file.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        worker = Path("/srv/cloudif/lib/cloudif_project_provision_worker.py")
        if not worker.exists():
            raise RuntimeError("project_provision_worker_missing")

        _log(f"QUEUE {job_file} unit={job['systemd_unit']}")
        actual_unit = _start_project_provision_unit(job_file, lock_path, job_id)
        if actual_unit != job["systemd_unit"]:
            raise RuntimeError("project_provision_unit_mismatch")
    finally:
        os.close(lock_fd)

    return {"job_file": str(job_file), "deduplicated": False, "job": job}

WORKER_CODE = r'''#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from pathlib import Path

LOG = Path("/var/log/cloudif/project-provision.log")

def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%S%z") + " " + str(msg) + "\n")

def run(cmd, timeout=180):
    log("RUN " + " ".join(cmd))
    try:
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        log(f"RC={p.returncode}")
        if p.stdout:
            log("STDOUT " + p.stdout[-4000:])
        if p.stderr:
            log("STDERR " + p.stderr[-4000:])
        return p.returncode
    except subprocess.TimeoutExpired:
        log("TIMEOUT " + " ".join(cmd))
        return 124
    except Exception as e:
        log("ERROR " + repr(e))
        return 999

def main():
    job_file = Path(sys.argv[1])
    job = json.loads(job_file.read_text(encoding="utf-8"))
    log(f"START job={job_file} slug={job.get('slug')} tenant={job.get('tenant')}")

    candidates = [
        "/usr/local/sbin/cloudif-project-provision.sh",
        "/usr/local/sbin/cloudif-provision-project.sh",
        "/root/cloudif-project-provision.sh",
        "/root/cloudif-provision-project.sh",
    ]

    found = [c for c in candidates if Path(c).exists() and os.access(c, os.X_OK)]

    if not found:
        log("NO_EXTERNAL_PROVISION_SCRIPT_FOUND metadata_saved_only")
        log("DONE")
        return

    # Executa apenas o primeiro script real encontrado, com timeout, passando o JSON do job.
    rc = run([found[0], str(job_file)], timeout=int(os.environ.get('CLOUDIF_PROJECT_PROVISION_TIMEOUT', '7200')))
    if rc == 0 and job.get("template_kind") in ["onboarding", "links"]:
        trc = run(["/usr/local/sbin/cloudif-project-template-apply.py", str(job_file)], timeout=int(os.environ.get('CLOUDIF_PROJECT_TEMPLATE_TIMEOUT', '900')))
        log(f"TEMPLATE_RC={trc}")
        if trc == 0:
            prc = run(["/usr/local/sbin/cloudif-project-initial-publish.py", str(job_file)], timeout=int(os.environ.get('CLOUDIF_INITIAL_PUBLICATION_TIMEOUT', '9000')))
            log(f"INITIAL_PUBLISH_RC={prc}")
    log("DONE")

if __name__ == "__main__":
    main()
'''

def check_project(form, headers):
    """Atualiza somente estado observado; nunca reenfileira nem reescreve configuração."""
    slug = val(form, "slug", "").strip()
    if not slug:
        raise ValueError("Projeto não informado.")
    con = db()
    try:
        row = con.execute("SELECT slug,tenant,repo_url,komodo_status FROM projects WHERE slug=?", (slug,)).fetchone()
        if not row:
            raise LookupError("Projeto não encontrado.")

        import cloudif_project_provision_status as provision_status
        state = provision_status.status(slug)
        components = state.get("components") or {}
        forge = components.get("forgejo") or {"ok": False, "status": "pending"}
        komodo = components.get("komodo") or {"ok": False, "status": "pending"}
        supabase = components.get("supabase") or {"ok": False, "status": "pending"}
        tenant = str(row["tenant"] or "")
        database = (
            {"ok": bool(supabase.get("ok")), "status": str(supabase.get("status") or "pending")}
            if tenant
            else {"ok": True, "status": "not_applicable"}
        )
        observed = {
            "repository": {"ok": bool(forge.get("ok")), "status": str(forge.get("status") or "pending")},
            "database": database,
            "container": {"ok": bool(komodo.get("ok")), "status": str(komodo.get("status") or "pending")},
        }

        report_path = provision_status.PROVISION_ROOT / slug / "provision-report.json"
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
        report_forge = ((report.get("components") or {}).get("forgejo") or {})
        repo_url = str(report_forge.get("url") or row["repo_url"] or "")
        komodo_status = str(row["komodo_status"] or "not_configured")
        if report:
            komodo_status = "running" if observed["container"]["ok"] else str(observed["container"]["status"] or komodo_status)

        con.execute(
            "UPDATE projects SET repo_url=?,komodo_status=?,updated_at=? WHERE slug=?",
            (repo_url,komodo_status,time.strftime("%Y-%m-%dT%H:%M:%S%z"),slug),
        )
        con.commit()
        return {
            "slug": slug,
            "tenant": tenant,
            "checked": True,
            "observed": observed,
            "all_ok": all(item["ok"] for item in observed.values()),
            "message": "Estado atualizado sem alterar a configuração do projeto.",
        }
    finally:
        con.close()

def resume_initial_publication(form, user):
    from cloudif_project_provision_status import resume_material
    slug=val(form,'slug','').strip()
    groups={str(item).strip().lower() for item in (user.get('groups') or [])}
    global_admin=bool(groups.intersection({'cloudif-tenants-admin','cloudif-professor','domain admins'}))
    job=resume_material(slug,user,global_admin=global_admin)
    queued=queue_provision_job(job)
    return {
        'slug':slug,'tenant':job.get('tenant') or '',
        'job_file':queued.get('job_file'),'deduplicated':bool(queued.get('deduplicated')),
        'message':('A retomada já estava em andamento.' if queued.get('deduplicated') else 'Publicação inicial enfileirada para retomada.'),
        'resume_only':True,'secrets_exposed':False,
    }


def handle_project_action(form, headers):

    # CloudIF v135b4 delete_git_komodo via project_action
    try:
        import sys as _cloudif_v135b4_sys
        if "/srv/cloudif/lib" not in _cloudif_v135b4_sys.path:
            _cloudif_v135b4_sys.path.insert(0, "/srv/cloudif/lib")

        from cloudif_delete_git_komodo_action import handle_delete_git_komodo
        _cloudif_v135b4_res = handle_delete_git_komodo(form, actor="portal", headers=headers)
        if _cloudif_v135b4_res is not None:
            return _cloudif_v135b4_res
    except Exception as _cloudif_v135b4_exc:
        return (
            '<div class="card">'
            '<h2>Erro controlado na ação Excluir Git/Komodo</h2>'
            '<p>' + type(_cloudif_v135b4_exc).__name__ + ': ' + str(_cloudif_v135b4_exc) + '</p>'
            '<p><a class="btn" href="/cloudiff/portal/?tab=git">Voltar</a></p>'
            '</div>'
        )

    action = val(form, "action", "").strip() or val(form, "op", "").strip()
    if action == "check":
        return check_project(form, headers)
    user = user_from_headers(headers)
    if action == 'resume_initial_publication':
        return resume_initial_publication(form,user)
    return upsert_project(form, user)
