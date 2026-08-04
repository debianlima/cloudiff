"""Safe, asynchronous tenant/database deletion for CloudIFF."""
from __future__ import annotations

import csv
import gzip
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import uuid

BASE = Path(os.environ.get("CLOUDIF_BASE", "/srv/cloudif"))
TENANTS = BASE / "tenants"
REGISTRY = BASE / "registry" / "tenants.csv"
PORTAL_DB = Path(os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db"))
ONBOARDING_DB = Path(os.environ.get("CLOUDIF_ONBOARDING_DB", "/var/lib/cloudif/onboarding/onboarding.db"))
AUDIT_ROOT = BASE / "admin-tenant-deletions"
JOB_ROOT = AUDIT_ROOT / ".jobs"
JOB_RECEIPTS = AUDIT_ROOT / ".job-receipts"
LOCK_ROOT = Path("/run/cloudif-operation-locks")
ROUTER_RENDER = BASE / "bin" / "cloudif-render-router-sso.sh"
PROTECTED = frozenset({"akadmin"})
TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def _run(cmd, timeout=300, cwd=None, check=False, stdout=None):
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=stdout is None,
        stdout=stdout if stdout is not None else subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=check,
    )


def _atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    tmp.chmod(0o600)
    os.replace(tmp, path)


def _job_write(job_id, data):
    _atomic_json(JOB_ROOT / f"{job_id}.json", data)
    _atomic_json(JOB_RECEIPTS / f"{job_id}.json", data)


def job_status(job_id):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id or ""):
        return {"ok": False, "error": "invalid_job_id"}
    for path in (JOB_ROOT / f"{job_id}.json", JOB_RECEIPTS / f"{job_id}.json"):
        if path.exists():
            return json.loads(path.read_text())
    return {"ok": False, "error": "job_not_found"}


def _registry_rows():
    if not REGISTRY.exists():
        return [], []
    with REGISTRY.open(newline="", errors="ignore") as stream:
        reader = csv.DictReader(stream)
        return list(reader), list(reader.fieldnames or [])


def _linked_projects(tenant):
    if not PORTAL_DB.exists():
        return []
    con = sqlite3.connect(PORTAL_DB)
    con.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in con.execute(
            "SELECT slug,name,owner,status FROM projects WHERE tenant=? ORDER BY slug", (tenant,)
        )]
    except sqlite3.OperationalError:
        try:
            return [dict(row) for row in con.execute(
                "SELECT slug,name,owner FROM projects WHERE tenant=? ORDER BY slug", (tenant,)
            )]
        except sqlite3.OperationalError:
            return []
    finally:
        con.close()


def _compose_project_names(tenant, tdir):
    names = set()
    if tdir.is_dir():
        proc = _run(["docker", "compose", "--env-file", ".env", "ps", "-aq"], timeout=60, cwd=tdir)
        for cid in proc.stdout.splitlines():
            inspect = _run(["docker", "inspect", "--format", "{{index .Config.Labels \"com.docker.compose.project\"}}", cid], timeout=20)
            value = inspect.stdout.strip()
            if value:
                names.add(value)
    for fallback in (f"cloudif_{tenant}", f"cloudif-{tenant}", tenant):
        proc = _run(["docker", "ps", "-a", "--filter", f"label=com.docker.compose.project={fallback}", "-q"], timeout=20)
        if proc.stdout.strip():
            names.add(fallback)
    return sorted(names)


def _docker_resources(compose_projects):
    result = {"containers": [], "networks": [], "volumes": []}
    for project in compose_projects:
        for kind, command, fmt in (
            ("containers", ["docker", "ps", "-a", "--filter", f"label=com.docker.compose.project={project}"], "{{.ID}}|{{.Names}}|{{.Status}}"),
            ("networks", ["docker", "network", "ls", "--filter", f"label=com.docker.compose.project={project}"], "{{.ID}}|{{.Name}}"),
            ("volumes", ["docker", "volume", "ls", "--filter", f"label=com.docker.compose.project={project}"], "{{.Name}}"),
        ):
            proc = _run(command + ["--format", fmt], timeout=30)
            for line in proc.stdout.splitlines():
                if line and line not in result[kind]:
                    result[kind].append(line)
    return result


def preview(tenant):
    tenant = (tenant or "").strip().lower()
    if not TENANT_RE.fullmatch(tenant):
        return {"ok": False, "error": "invalid_tenant", "tenant": tenant}
    rows, _fields = _registry_rows()
    registry_row = next((row for row in rows if row.get("tenant") == tenant), None)
    tdir = TENANTS / tenant
    projects = _linked_projects(tenant)
    compose_projects = _compose_project_names(tenant, tdir)
    resources = _docker_resources(compose_projects)
    protected = tenant in PROTECTED
    present = bool(registry_row or tdir.exists() or resources["containers"] or resources["volumes"])
    blockers = []
    if protected:
        blockers.append("protected_platform_tenant")
    if projects:
        blockers.append("linked_projects")
    if not present:
        blockers.append("tenant_not_found")
    return {
        "ok": not blockers,
        "tenant": tenant,
        "protected": protected,
        "tenant_dir": str(tdir),
        "tenant_dir_present": tdir.is_dir(),
        "registry_present": registry_row is not None,
        "registry": registry_row or {},
        "linked_projects": projects,
        "compose_projects": compose_projects,
        "resources": resources,
        "blockers": blockers,
        "confirmation": f"EXCLUIR BANCO {tenant}",
        "backup_required": True,
    }


def _remove_registry_row(tenant, audit):
    rows, fields = _registry_rows()
    removed = [row for row in rows if row.get("tenant") == tenant]
    kept = [row for row in rows if row.get("tenant") != tenant]
    if REGISTRY.exists():
        shutil.copy2(REGISTRY, audit / "tenants.csv.before")
    if fields:
        tmp = REGISTRY.with_suffix(".tmp")
        with tmp.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(kept)
        os.replace(tmp, REGISTRY)
    return removed


def _delete_tenant_rows(db_path, tenant):
    if not db_path.exists():
        return {}
    con = sqlite3.connect(db_path, timeout=30)
    removed = {}
    try:
        con.execute("BEGIN IMMEDIATE")
        for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            columns = [row[1] for row in con.execute(f'PRAGMA table_info("{table}")')]
            tenant_columns = [column for column in columns if column in {"tenant", "tenant_slug", "db_tenant"}]
            if not tenant_columns:
                continue
            count = 0
            for column in tenant_columns:
                cur = con.execute(f'DELETE FROM "{table}" WHERE "{column}"=?', (tenant,))
                count += max(cur.rowcount, 0)
            if count:
                removed[table] = count
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return removed


def _tenant_reference_count(db_path, tenant):
    if not db_path.exists():
        return 0
    con = sqlite3.connect(db_path, timeout=30)
    total = 0
    try:
        for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            columns = [row[1] for row in con.execute(f'PRAGMA table_info("{table}")')]
            for column in (c for c in columns if c in {"tenant", "tenant_slug", "db_tenant"}):
                total += int(con.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}"=?', (tenant,)).fetchone()[0])
    finally:
        con.close()
    return total


def _purge_platform_database_tenant(tenant, audit):
    """Remove metadados centrais associados ao tenant excluído."""
    container = os.environ.get("SUPABASE_DB_CONTAINER", "supabase-db")
    db_user = os.environ.get("SUPABASE_DB_USER", "postgres")
    db_name = os.environ.get("SUPABASE_DB_NAME", "postgres")
    tenant_literal = "'" + str(tenant).replace("'", "''") + "'"
    sql = f"""
BEGIN;
CREATE TEMP TABLE cloudif_deleted_slugs AS
  SELECT slug FROM cloudif.project_registry WHERE tenant = {tenant_literal};
DELETE FROM cloudif.project_acl WHERE slug IN (SELECT slug FROM cloudif_deleted_slugs);
DELETE FROM cloudif.project_events WHERE slug IN (SELECT slug FROM cloudif_deleted_slugs);
DELETE FROM cloudif.project_registry WHERE tenant = {tenant_literal};
COMMIT;
"""
    # Use stdin so the transaction remains atomic and no SQL reaches argv/logs.
    proc = subprocess.run(
        ["docker", "exec", "-i", container, "psql", "-U", db_user, "-d", db_name, "-v", "ON_ERROR_STOP=1"],
        input=sql, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False,
    )
    result = {"ok": proc.returncode == 0, "stdout": proc.stdout[-1000:], "stderr": proc.stderr[-1000:]}
    (audit / "platform-db-cleanup.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def _backup_database(tdir, audit):
    proc = _run(["docker", "compose", "--env-file", ".env", "ps", "-q", "db"], timeout=60, cwd=tdir)
    cid = proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else ""
    if not cid:
        return {"ok": False, "error": "database_container_not_found"}
    target = audit / "database-final.sql.gz"
    with gzip.open(target, "wb", compresslevel=6) as stream:
        dump = subprocess.run(
            ["docker", "exec", cid, "sh", "-lc", 'pg_dumpall -U "${POSTGRES_USER:-postgres}"'],
            stdout=stream,
            stderr=subprocess.PIPE,
            timeout=3600,
            check=False,
        )
    if dump.returncode != 0 or not target.exists() or target.stat().st_size < 128:
        target.unlink(missing_ok=True)
        return {"ok": False, "error": "database_backup_failed", "detail": dump.stderr.decode("utf-8", "ignore")[:500]}
    target.chmod(0o600)
    return {"ok": True, "path": str(target), "bytes": target.stat().st_size}


def _remove_labeled_resources(compose_projects):
    removed = {"containers": [], "networks": [], "volumes": [], "errors": []}
    for project in compose_projects:
        for cid in _run(["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"], timeout=30).stdout.splitlines():
            proc = _run(["docker", "rm", "-f", cid], timeout=120)
            (removed["containers"] if proc.returncode == 0 else removed["errors"]).append(cid if proc.returncode == 0 else {"container": cid, "detail": proc.stderr[:300]})
        for name in _run(["docker", "network", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"], timeout=30).stdout.splitlines():
            proc = _run(["docker", "network", "rm", name], timeout=60)
            (removed["networks"] if proc.returncode == 0 else removed["errors"]).append(name if proc.returncode == 0 else {"network": name, "detail": proc.stderr[:300]})
        for name in _run(["docker", "volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"], timeout=30).stdout.splitlines():
            proc = _run(["docker", "volume", "rm", name], timeout=120)
            (removed["volumes"] if proc.returncode == 0 else removed["errors"]).append(name if proc.returncode == 0 else {"volume": name, "detail": proc.stderr[:300]})
    return removed


def execute(tenant, confirmation, actor, progress=None):
    progress = progress or (lambda *_args, **_kwargs: None)
    progress("Validação", "running", "Conferindo tenant, vínculos e proteção")
    plan = preview(tenant)
    if not plan.get("ok"):
        progress("Validação", "failed", ", ".join(plan.get("blockers") or [plan.get("error", "invalid")]))
        return {"ok": False, "error": "tenant_delete_blocked", "preview": plan}
    expected = plan["confirmation"]
    if confirmation != expected:
        progress("Validação", "failed", "Texto de confirmação incorreto")
        return {"ok": False, "error": "confirmation_mismatch", "expected": expected}
    progress("Validação", "done", "Tenant sem projetos vinculados")
    progress("Backup final", "running", "Arquivando configuração e gerando dump lógico protegido")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    audit = AUDIT_ROOT / f"{stamp}-{time.time_ns() % 1_000_000_000:09d}-{tenant}"
    audit.mkdir(parents=True, exist_ok=False)
    audit.chmod(0o700)
    (audit / "preview.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    tdir = TENANTS / tenant
    if tdir.is_dir():
        shutil.make_archive(str(audit / "tenant-config"), "gztar", root_dir=tdir)
        (audit / "tenant-config.tar.gz").chmod(0o600)

    backup = _backup_database(tdir, audit)
    if not backup.get("ok"):
        progress("Backup final", "failed", backup.get("error", "Falha no backup"))
        result = {"ok": False, "error": "backup_required_failed", "backup": backup, "audit_dir": str(audit)}
        (audit / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return result
    progress("Backup final", "done", f"{backup['bytes']} bytes protegidos")

    progress("Containers e volumes", "running", "Derrubando Compose e removendo dados")
    down = _run(["docker", "compose", "--env-file", ".env", "down", "-v", "--remove-orphans"], timeout=900, cwd=tdir)
    cleanup = _remove_labeled_resources(plan.get("compose_projects") or [])
    after_resources = _docker_resources(plan.get("compose_projects") or [])
    runtime_ok = not any(after_resources.values()) and not cleanup.get("errors")
    progress("Containers e volumes", "done" if runtime_ok else "failed", "Runtime removido" if runtime_ok else "Restaram recursos Docker")
    if not runtime_ok:
        result = {"ok": False, "error": "runtime_cleanup_failed", "down": {"rc": down.returncode, "stderr": down.stderr[-1000:]}, "cleanup": cleanup, "remaining": after_resources, "audit_dir": str(audit)}
        (audit / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return result

    progress("Registry e permissões", "running", "Removendo cadastro, ACL e políticas")
    registry_removed = _remove_registry_row(tenant, audit)
    portal_removed = _delete_tenant_rows(PORTAL_DB, tenant)
    onboarding_removed = _delete_tenant_rows(ONBOARDING_DB, tenant)
    platform_removed = _purge_platform_database_tenant(tenant, audit)
    if not platform_removed.get("ok"):
        progress("Registry e permissões", "failed", "Falha ao limpar metadados centrais")
        result = {"ok": False, "error": "platform_metadata_cleanup_failed", "platform_removed": platform_removed, "audit_dir": str(audit)}
        (audit / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return result
    progress("Registry e permissões", "done", f"{sum(portal_removed.values()) + sum(onboarding_removed.values())} registro(s) locais e metadados centrais")

    progress("Diretório do tenant", "running", "Removendo configuração local")
    if tdir.exists():
        shutil.rmtree(tdir)
    progress("Diretório do tenant", "done", "Diretório removido")

    progress("Roteador", "running", "Renderizando rotas sem o tenant")
    router = _run([str(ROUTER_RENDER)], timeout=300)
    router_ok = router.returncode == 0
    progress("Roteador", "done" if router_ok else "failed", "Rotas atualizadas" if router_ok else router.stderr[-300:])

    final = preview(tenant)
    portal_residual = _tenant_reference_count(PORTAL_DB, tenant)
    onboarding_residual = _tenant_reference_count(ONBOARDING_DB, tenant)
    absent = (
        "tenant_not_found" in (final.get("blockers") or [])
        and not final.get("tenant_dir_present")
        and not final.get("registry_present")
        and not any((final.get("resources") or {}).values())
        and portal_residual == 0
        and onboarding_residual == 0
    )
    result = {
        "ok": bool(router_ok and absent),
        "tenant": tenant,
        "actor": actor,
        "backup": backup,
        "down": {"rc": down.returncode, "stdout": down.stdout[-1500:], "stderr": down.stderr[-1500:]},
        "cleanup": cleanup,
        "registry_removed": registry_removed,
        "portal_removed": portal_removed,
        "onboarding_removed": onboarding_removed,
        "platform_removed": platform_removed,
        "router": {"ok": router_ok, "stdout": router.stdout[-1500:], "stderr": router.stderr[-1500:]},
        "final_preview": final,
        "final_references": {"portal": portal_residual, "onboarding": onboarding_residual},
        "audit_dir": str(audit),
    }
    if not result["ok"]:
        result["error"] = "tenant_delete_verification_failed"
    (audit / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def _job_unit(job_id):
    return f"cloudif-tenant-delete-{job_id[:12]}.service"


def _worker_update(job_id, label, status="running", detail=""):
    labels = ["Validação", "Backup final", "Containers e volumes", "Registry e permissões", "Diretório do tenant", "Roteador"]
    current = job_status(job_id)
    steps = current.setdefault("steps", [])
    item = next((x for x in steps if x.get("label") == label), None)
    if item is None:
        item = {"label": label}
        steps.append(item)
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    item.update({"status": status, "detail": detail, "updated_at": now})
    current["status"] = "running"
    current["current_step"] = label
    current["updated_at"] = now
    done = sum(1 for x in steps if x.get("status") in {"done", "failed"})
    current["progress"] = min(95, round(done * 100 / len(labels)))
    _job_write(job_id, current)


def run_job_worker(job_id):
    current = job_status(job_id)
    if not current.get("ok"):
        return 2
    tenant = current.get("tenant") or ""
    actor = current.get("actor") or "portal"
    lock = JOB_ROOT / f".{tenant}.lock"
    LOCK_ROOT.mkdir(parents=True, exist_ok=True)
    tenant_lock_fd = os.open(LOCK_ROOT / f"tenant-{tenant}.lock", os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(tenant_lock_fd, fcntl.LOCK_EX)
    try:
        current.update({
            "status": "running",
            "unit": _job_unit(job_id),
            "worker_pid": os.getpid(),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        _job_write(job_id, current)
        confirmation = f"EXCLUIR BANCO {tenant}"
        result = execute(tenant, confirmation, actor, lambda label, status="running", detail="": _worker_update(job_id, label, status, detail))
        current = job_status(job_id)
        current.update({
            "status": "succeeded" if result.get("ok") else "failed",
            "progress": 100,
            "result": result,
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "receipt_retention_days": 30,
        })
        if not result.get("ok"):
            current["error"] = result.get("error", "tenant_delete_failed")
        _job_write(job_id, current)
        return 0 if result.get("ok") else 1
    except Exception as exc:
        current = job_status(job_id)
        current.update({
            "status": "failed", "progress": 100,
            "error": type(exc).__name__, "detail": str(exc)[:500],
            "traceback": traceback.format_exc(limit=10),
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        _job_write(job_id, current)
        return 1
    finally:
        lock.unlink(missing_ok=True)
        try:
            os.close(tenant_lock_fd)
        except OSError:
            pass


def _launch_worker(job_id):
    unit = _job_unit(job_id)
    cmd = [
        "systemd-run", "--quiet", "--collect", f"--unit={unit}",
        "--property=Type=exec", "--property=TimeoutStartSec=infinity",
        "--property=KillMode=process", "--property=Nice=10",
        sys.executable, str(Path(__file__).resolve()), "--worker", job_id,
    ]
    proc = _run(cmd, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"worker_launch_failed: {proc.stderr[-500:]}")
    return unit


def start_job(tenant, confirmation, actor):
    tenant = (tenant or "").strip().lower()
    JOB_ROOT.mkdir(parents=True, exist_ok=True)
    lock = JOB_ROOT / f".{tenant}.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    except FileExistsError:
        for path in sorted(JOB_ROOT.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                current = json.loads(path.read_text())
            except Exception:
                continue
            if current.get("tenant") == tenant and current.get("status") in {"queued", "running"}:
                current["deduplicated"] = True
                return current
        if lock.exists() and time.time() - lock.stat().st_mtime > 1800:
            lock.unlink()
            return start_job(tenant, confirmation, actor)
        return {"ok": False, "error": "tenant_delete_already_running", "tenant": tenant}

    expected = f"EXCLUIR BANCO {tenant}"
    if confirmation != expected:
        lock.unlink(missing_ok=True)
        return {"ok": False, "error": "confirmation_mismatch", "expected": expected}

    job_id = uuid.uuid4().hex
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    state = {
        "ok": True, "job_id": job_id, "tenant": tenant, "actor": actor,
        "status": "queued", "progress": 0, "current_step": "Validação",
        "steps": [], "started_at": now, "updated_at": now,
        "unit": _job_unit(job_id),
    }
    _job_write(job_id, state)
    try:
        _launch_worker(job_id)
    except Exception as exc:
        state.update({"status": "failed", "progress": 100, "error": "worker_launch_failed", "detail": str(exc)[:500], "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
        _job_write(job_id, state)
        lock.unlink(missing_ok=True)
        return state
    return state


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        raise SystemExit(run_job_worker(sys.argv[2]))


def render_panel(csrf_token, selected=""):
    rows, _fields = _registry_rows()
    tenants = sorted({(row.get("tenant") or "").strip() for row in rows if (row.get("tenant") or "").strip()})
    options = "".join(
        f'<option value="{tenant}"{" selected" if tenant == selected else ""}>{tenant}</option>'
        for tenant in tenants
    )
    return f"""
<section class="card tenant-delete-tool">
  <div class="section-title"><div><h2>Excluir banco e tenant</h2><p>Operação destrutiva, separada da exclusão de projetos.</p></div><span class="pill warn">Backup obrigatório</span></div>
  <div class="help"><strong>Proteções:</strong> o tenant administrativo não pode ser removido; tenants vinculados a projetos são bloqueados; um dump lógico final é criado antes dos volumes serem apagados.</div>
  <form id="tenant-delete-preview-form">
    <input type="hidden" name="csrf_token" value="{csrf_token}">
    <label>Tenant<select name="tenant" required><option value="">Selecione</option>{options}</select></label>
    <button class="btn red" type="submit">Abrir wizard de exclusão</button>
  </form>
  <div id="tenant-delete-modal" class="tenant-delete-modal" hidden aria-hidden="true">
    <div class="tenant-delete-backdrop" data-delete-close></div>
    <section class="tenant-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="tenant-delete-title">
      <header><div><span class="tenant-delete-kicker">Exclusão definitiva</span><h2 id="tenant-delete-title">Preparando análise</h2><p id="tenant-delete-subtitle">Nenhuma alteração foi feita.</p></div><button type="button" class="btn light" data-delete-close>Fechar</button></header>
      <div id="tenant-delete-modal-body" class="tenant-delete-modal-body"></div>
      <footer id="tenant-delete-modal-footer"></footer>
    </section>
  </div>
</section>
<style>
.tenant-delete-tool{{display:grid;gap:16px}}.tenant-delete-tool form{{display:grid;gap:10px;max-width:620px}}body.tenant-delete-modal-open{{overflow:hidden}}.tenant-delete-modal{{position:fixed;inset:0;z-index:10000;display:grid;place-items:center;padding:24px}}.tenant-delete-modal[hidden]{{display:none}}.tenant-delete-backdrop{{position:absolute;inset:0;background:rgba(15,23,42,.62);backdrop-filter:blur(2px)}}.tenant-delete-dialog{{position:relative;z-index:1;display:grid;grid-template-rows:auto minmax(0,1fr) auto;width:min(900px,100%);max-height:88vh;overflow:hidden;border:1px solid #cfe3f8;border-radius:18px;background:#fff;box-shadow:0 28px 90px rgba(15,23,42,.35)}}.tenant-delete-dialog>header{{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;padding:22px 24px;border-bottom:1px solid #dbeafe;background:#f5faff}}.tenant-delete-dialog h2{{margin:4px 0}}.tenant-delete-dialog header p{{margin:0;color:#111}}.tenant-delete-kicker{{font-size:.72rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:#111}}.tenant-delete-modal-body{{display:grid;gap:16px;padding:22px 24px;overflow:auto}}.tenant-delete-dialog>footer{{display:flex;justify-content:flex-end;gap:10px;padding:16px 24px;border-top:1px solid #dbeafe}}.tenant-delete-preview-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}}.tenant-delete-preview-grid>div{{padding:13px;border:1px solid #cfe3f8;border-radius:11px;background:#f5faff}}.tenant-delete-preview-grid small{{display:block;color:#111}}.tenant-delete-confirmation{{display:grid;gap:10px}}.tenant-delete-confirmation input{{font-family:ui-monospace,monospace}}.tenant-delete-timeline{{display:grid;gap:9px;margin:0;padding:0;list-style:none}}.tenant-delete-step{{display:grid;grid-template-columns:26px 1fr auto;gap:12px;align-items:center;padding:12px;border:1px solid #dbeafe;border-radius:11px}}.tenant-delete-step.pending{{opacity:.58}}.tenant-delete-step.running{{background:#edf6ff;border-color:#8fb8e8}}.tenant-delete-step.done{{background:#f0fdf4;border-color:#bbf7d0}}.tenant-delete-step.failed{{background:#fef2f2;border-color:#fecaca}}.tenant-delete-step-icon{{width:24px;height:24px;display:grid;place-items:center;border-radius:999px;background:#e5e7eb;color:#111;font-size:.72rem;font-weight:900}}.tenant-delete-step.running .tenant-delete-step-icon{{background:#8fb8e8}}.tenant-delete-step.done .tenant-delete-step-icon{{background:#86efac}}.tenant-delete-step.failed .tenant-delete-step-icon{{background:#fca5a5}}.tenant-delete-step small{{display:block;color:#111;margin-top:2px}}.tenant-delete-dots{{display:inline-flex;gap:4px;align-items:center}}.tenant-delete-dots i{{width:5px;height:5px;border-radius:999px;background:#111;animation:tenant-delete-pulse 1.1s infinite ease-in-out}}.tenant-delete-dots i:nth-child(2){{animation-delay:.18s}}.tenant-delete-dots i:nth-child(3){{animation-delay:.36s}}@keyframes tenant-delete-pulse{{0%,80%,100%{{opacity:.25;transform:translateY(0)}}40%{{opacity:1;transform:translateY(-3px)}}}}.tenant-delete-live{{display:flex;gap:10px;align-items:center;padding:12px;border:1px solid #cfe3f8;border-radius:11px;background:#edf6ff}}.tenant-delete-progress-wrap{{display:grid;gap:7px}}.tenant-delete-progress-wrap progress{{width:100%;height:12px;accent-color:#8fb8e8}}.tenant-delete-terminal{{padding:14px;border-radius:11px}}.tenant-delete-terminal.ok{{background:#f0fdf4;border:1px solid #bbf7d0}}.tenant-delete-terminal.bad{{background:#fef2f2;border:1px solid #fecaca}}@media(max-width:700px){{.tenant-delete-modal{{padding:0}}.tenant-delete-dialog{{width:100%;height:100%;max-height:none;border-radius:0}}.tenant-delete-step{{grid-template-columns:26px 1fr}}.tenant-delete-step>.pill{{grid-column:2;justify-self:start}}}}
</style>
<script>
(() => {{
 const form=document.getElementById('tenant-delete-preview-form');if(!form)return;
 const modal=document.getElementById('tenant-delete-modal'),body=document.getElementById('tenant-delete-modal-body'),footer=document.getElementById('tenant-delete-modal-footer'),title=document.getElementById('tenant-delete-title'),subtitle=document.getElementById('tenant-delete-subtitle');
 const portal='/cloudiff/portal/',labels=['Validação','Backup final','Containers e volumes','Registry e permissões','Diretório do tenant','Roteador'];
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
 let activeJob='',terminal=false,lastJob=null;
 const dots=()=>'<span class="tenant-delete-dots" aria-label="Executando"><i></i><i></i><i></i></span>';
 function openModal(){{modal.hidden=false;modal.setAttribute('aria-hidden','false');document.body.classList.add('tenant-delete-modal-open')}}
 function closeModal(){{if(activeJob&&!terminal)return;modal.hidden=true;modal.setAttribute('aria-hidden','true');document.body.classList.remove('tenant-delete-modal-open')}}
 modal.querySelectorAll('[data-delete-close]').forEach(x=>x.onclick=closeModal);
 async function jsonFetch(url,options={{}}){{const r=await fetch(url,{{credentials:'same-origin',...options}}),type=(r.headers.get('content-type')||'').toLowerCase(),text=await r.text();if(!type.includes('application/json')){{const e=new Error(`A operação não chegou ao serviço de exclusão (HTTP ${{r.status}}).`);e.status=r.status;throw e}}let data;try{{data=JSON.parse(text)}}catch(_e){{throw new Error('O serviço retornou uma resposta incompleta.')}}if(!r.ok){{const e=new Error(data.detail||data.error||`HTTP ${{r.status}}`);e.status=r.status;throw e}}return data}}
 function timeline(job={{}}){{const known=new Map((job.steps||[]).map(x=>[x.label,x]));return labels.map((label,index)=>{{const item=known.get(label)||{{status:'pending',detail:'Aguardando etapa anterior.'}},status=item.status||'pending',icon=status==='done'?'✓':status==='failed'?'!':status==='running'?dots():String(index+1),badge=status==='done'?'Concluído':status==='failed'?'Falhou':status==='running'?'Executando':'Aguardando';return `<li class="tenant-delete-step ${{status}}"><span class="tenant-delete-step-icon">${{icon}}</span><div><strong>${{esc(label)}}</strong><small>${{esc(item.detail||'')}}</small></div><span class="pill ${{status==='done'?'ok':status==='failed'?'bad':'muted'}}">${{badge}}</span></li>`}}).join('')}}
 function preparing(message,detail){{title.textContent='Exclusão iniciada';subtitle.textContent=message;body.innerHTML=`<div class="tenant-delete-live">${{dots()}}<div><strong>${{esc(message)}}</strong><small>${{esc(detail)}}</small></div></div><div class="tenant-delete-progress-wrap"><progress max="100" value="2"></progress><small>O servidor está preparando a operação.</small></div><ol class="tenant-delete-timeline">${{timeline({{steps:[{{label:'Validação',status:'running',detail}}]}})}}</ol>`;footer.innerHTML='<button class="btn light" type="button" disabled>Aguarde…</button>'}}
 function drawJob(job){{lastJob=job;activeJob=['queued','running'].includes(job.status)?job.job_id||activeJob:'';terminal=!activeJob;const progress=Number(job.progress||0),failed=job.status==='failed',done=job.status==='succeeded';title.textContent=done?'Banco removido':failed?'A exclusão falhou':'Exclusão em andamento';subtitle.textContent=done?'Backup protegido e ambiente atualizado.':failed?'O processo foi interrompido com segurança.':job.current_step||'Preparando próxima etapa.';const live=!failed&&!done?`<div class="tenant-delete-live">${{dots()}}<div><strong>${{esc(job.current_step||'Executando')}}</strong><small>O servidor continua trabalhando. Não feche esta janela.</small></div></div>`:'';const terminalBox=done?'<div class="tenant-delete-terminal ok"><strong>Exclusão concluída.</strong><p>O backup final foi criado antes da remoção dos dados.</p></div>':failed?`<div class="tenant-delete-terminal bad"><strong>Não foi possível concluir.</strong><p>${{esc(job.error||job.detail||job.result?.error||'Falha não identificada.')}}</p></div>`:'';body.innerHTML=`${{live}}<div class="tenant-delete-progress-wrap"><progress max="100" value="${{progress}}"></progress><small>${{progress}}% concluído</small></div><ol class="tenant-delete-timeline">${{timeline(job)}}</ol>${{terminalBox}}`;footer.innerHTML=terminal?'<button class="btn" type="button" data-finish>Fechar</button>':'<button class="btn light" type="button" disabled>Exclusão em andamento…</button>';footer.querySelector('[data-finish]')?.addEventListener('click',()=>{{closeModal();location.reload()}})}}
 function showReconnect(attempt){{
   title.textContent='Confirmando conclusão';
   subtitle.textContent='O roteador está sendo atualizado. Recuperando o resultado final…';
   const banner=`<div class="tenant-delete-live" data-delete-reconnect>${{dots()}}<div><strong>Reconectando ao processo</strong><small>Tentativa ${{attempt+1}} de 75. As etapas já concluídas foram preservadas.</small></div></div>`;
   const previous=body.querySelector('[data-delete-reconnect]');
   if(previous)previous.outerHTML=banner;else body.insertAdjacentHTML('afterbegin',banner);
   footer.innerHTML='<button class="btn light" type="button" disabled>Confirmando resultado…</button>';
 }}
 async function poll(id,attempt=0){{
   const urls=[`${{portal}}?api=admin-delete-tenant-status&job_id=${{encodeURIComponent(id)}}`,`/cloudiff/portal/api/admin-delete-tenant-status?job_id=${{encodeURIComponent(id)}}`];
   try{{
     const job=await jsonFetch(urls[attempt%2],{{headers:{{Accept:'application/json','Cache-Control':'no-store'}}}});
     drawJob(job);
     if(['queued','running'].includes(job.status))setTimeout(()=>poll(id,0),1000);
   }}catch(e){{
     const transient=[0,404,408,425,429,500,502,503,504].includes(Number(e.status||0));
     if(transient&&attempt<75){{showReconnect(attempt);setTimeout(()=>poll(id,attempt+1),1200);return}}
     activeJob='';terminal=true;
     if(lastJob){{
       drawJob(lastJob);
       title.textContent='Resultado ainda não confirmado';
       subtitle.textContent='A operação pode ter terminado no servidor. Atualize a página para recuperar o recibo.';
       body.insertAdjacentHTML('beforeend',`<div class="tenant-delete-terminal bad"><strong>Não foi possível confirmar o resultado.</strong><p>${{esc(e.message)}}</p></div>`);
       footer.innerHTML='<button class="btn" type="button" data-finish>Fechar e atualizar</button>';
       footer.querySelector('[data-finish]').onclick=()=>location.reload();
       return;
     }}
     drawJob({{status:'failed',progress:0,error:e.message,steps:[{{label:'Validação',status:'failed',detail:e.message}}]}});
   }}
 }}
 form.addEventListener('submit',async e=>{{
   e.preventDefault();
   const fd=new FormData(form),tenant=String(fd.get('tenant')||'').trim();
   if(!tenant)return;
   activeJob='';terminal=false;openModal();
   preparing('Analisando o banco selecionado','Conferindo vínculos, containers, volumes e proteções. Nenhuma alteração foi feita.');
   try{{
     const p=await jsonFetch(`${{portal}}?api=admin-delete-tenant-preview&tenant=${{encodeURIComponent(tenant)}}`,{{headers:{{Accept:'application/json'}}}});
     const r=p.resources||{{}},blocked=(p.blockers||[]).length>0;
     title.textContent='Confirmar exclusão definitiva';
     subtitle.textContent=blocked?'Este banco não pode ser removido.':'Revise os recursos e confirme somente quando estiver seguro.';
     body.innerHTML=`<div class="tenant-delete-preview-grid"><div><small>Projetos vinculados</small><strong>${{(p.linked_projects||[]).length}}</strong></div><div><small>Containers</small><strong>${{(r.containers||[]).length}}</strong></div><div><small>Volumes</small><strong>${{(r.volumes||[]).length}}</strong></div><div><small>Diretório</small><strong>${{p.tenant_dir_present?'Presente':'Ausente'}}</strong></div></div>${{blocked?`<div class="tenant-delete-terminal bad"><strong>Exclusão bloqueada.</strong><p>${{esc((p.blockers||[]).join(', '))}}</p></div>`:`<div class="tenant-delete-confirmation"><div class="tenant-delete-terminal bad"><strong>Esta ação é irreversível.</strong><p>O sistema criará um backup final antes de parar os serviços e apagar os volumes.</p></div><label>Digite exatamente <strong>${{esc(p.confirmation)}}</strong><input id="tenant-delete-confirm" autocomplete="off"></label><p id="tenant-delete-confirm-status">Aguardando a confirmação exata.</p></div>`}}`;
     if(blocked){{
       terminal=true;
       footer.innerHTML='<button class="btn" type="button" data-close-blocked>Fechar</button>';
       footer.querySelector('[data-close-blocked]').onclick=closeModal;
       return;
     }}
     footer.innerHTML='<button class="btn light" type="button" data-cancel>Cancelar</button><button id="tenant-delete-start" class="btn red" type="button" disabled>Excluir banco definitivamente</button>';
     const input=document.getElementById('tenant-delete-confirm'),start=document.getElementById('tenant-delete-start'),status=document.getElementById('tenant-delete-confirm-status');
     footer.querySelector('[data-cancel]').onclick=closeModal;
     input.addEventListener('input',()=>{{
       const valid=input.value===p.confirmation;
       start.disabled=!valid;
       status.textContent=valid?'Confirmação validada. Clique no botão vermelho para iniciar.':'Aguardando a confirmação exata.';
       status.className=valid?'pill ok':'';
     }});
     start.onclick=async()=>{{
       if(input.value!==p.confirmation)return;
       start.disabled=true;footer.querySelector('[data-cancel]').disabled=true;input.disabled=true;
       preparing('Exclusão iniciada','Criando o job, bloqueando operações simultâneas e preparando o backup final.');
       const csrf=String(fd.get('csrf_token')||''),requestBody=new URLSearchParams({{tenant,confirmation:input.value,csrf_token:csrf}});
       try{{
         const job=await jsonFetch(portal,{{method:'POST',headers:{{Accept:'application/json','Content-Type':'application/x-www-form-urlencoded;charset=UTF-8','X-CSRF-Token':csrf,'X-CloudIF-Action':'admin-delete-tenant'}},body:requestBody}});
         activeJob=job.job_id;drawJob(job);poll(job.job_id);
       }}catch(err){{
         activeJob='';terminal=true;
         drawJob({{status:'failed',progress:100,error:err.message,steps:[{{label:'Validação',status:'failed',detail:err.message}}]}});
       }}
     }};
   }}catch(err){{
     activeJob='';terminal=true;
     title.textContent='Não foi possível analisar';subtitle.textContent='Nenhuma alteração foi feita.';
     body.innerHTML=`<div class="tenant-delete-terminal bad"><strong>Falha na análise.</strong><p>${{esc(err.message)}}</p></div>`;
     footer.innerHTML='<button class="btn" type="button" data-error-close>Fechar</button>';
     footer.querySelector('[data-error-close]').onclick=closeModal;
   }}
 }});
}})();
</script>
"""
