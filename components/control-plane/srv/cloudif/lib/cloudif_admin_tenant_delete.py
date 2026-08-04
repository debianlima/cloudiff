"""Safe, asynchronous tenant/database deletion for CloudIFF."""
from __future__ import annotations

import csv
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
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


def _job_write(job_id, data):
    JOB_ROOT.mkdir(parents=True, exist_ok=True)
    JOB_ROOT.chmod(0o700)
    path = JOB_ROOT / f"{job_id}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    os.replace(tmp, path)


def job_status(job_id):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id or ""):
        return {"ok": False, "error": "invalid_job_id"}
    path = JOB_ROOT / f"{job_id}.json"
    if not path.exists():
        return {"ok": False, "error": "job_not_found"}
    return json.loads(path.read_text())


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

    stamp = time.strftime("%Y%m%d-%H%M%S")
    audit = AUDIT_ROOT / f"{stamp}-{time.time_ns() % 1_000_000_000:09d}-{tenant}"
    audit.mkdir(parents=True, exist_ok=False)
    audit.chmod(0o700)
    (audit / "preview.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    tdir = TENANTS / tenant
    if tdir.is_dir():
        shutil.make_archive(str(audit / "tenant-config"), "gztar", root_dir=tdir)
        (audit / "tenant-config.tar.gz").chmod(0o600)

    progress("Backup final", "running", "Gerando dump lógico protegido")
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
    progress("Registry e permissões", "done", f"{sum(portal_removed.values()) + sum(onboarding_removed.values())} registro(s)")

    progress("Diretório do tenant", "running", "Removendo configuração local")
    if tdir.exists():
        shutil.rmtree(tdir)
    progress("Diretório do tenant", "done", "Diretório removido")

    progress("Roteador", "running", "Renderizando rotas sem o tenant")
    router = _run([str(ROUTER_RENDER)], timeout=300)
    router_ok = router.returncode == 0
    progress("Roteador", "done" if router_ok else "failed", "Rotas atualizadas" if router_ok else router.stderr[-300:])

    final = preview(tenant)
    absent = "tenant_not_found" in (final.get("blockers") or []) and not final.get("tenant_dir_present") and not final.get("registry_present") and not any((final.get("resources") or {}).values())
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
        "router": {"ok": router_ok, "stdout": router.stdout[-1500:], "stderr": router.stderr[-1500:]},
        "final_preview": final,
        "audit_dir": str(audit),
    }
    if not result["ok"]:
        result["error"] = "tenant_delete_verification_failed"
    (audit / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


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

    job_id = uuid.uuid4().hex
    state = {"ok": True, "job_id": job_id, "tenant": tenant, "actor": actor, "status": "queued", "progress": 0, "current_step": "Validação", "steps": [], "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    _job_write(job_id, state)

    labels = ["Validação", "Backup final", "Containers e volumes", "Registry e permissões", "Diretório do tenant", "Roteador"]
    def update(label, status="running", detail=""):
        current = job_status(job_id)
        steps = current.setdefault("steps", [])
        item = next((x for x in steps if x.get("label") == label), None)
        if item is None:
            item = {"label": label}
            steps.append(item)
        item.update({"status": status, "detail": detail, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
        current["status"] = "running"
        current["current_step"] = label
        done = sum(1 for x in steps if x.get("status") in {"done", "failed"})
        current["progress"] = min(95, round(done * 100 / len(labels)))
        _job_write(job_id, current)

    def worker():
        try:
            result = execute(tenant, confirmation, actor, update)
            current = job_status(job_id)
            current.update({"status": "succeeded" if result.get("ok") else "failed", "progress": 100, "result": result, "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
            if not result.get("ok"):
                current["error"] = result.get("error", "tenant_delete_failed")
            _job_write(job_id, current)
        except Exception as exc:
            current = job_status(job_id)
            current.update({"status": "failed", "progress": 100, "error": type(exc).__name__, "detail": str(exc)[:500], "traceback": traceback.format_exc(limit=10), "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
            _job_write(job_id, current)
        finally:
            lock.unlink(missing_ok=True)

    threading.Thread(target=worker, name=f"tenant-delete-{job_id[:8]}", daemon=False).start()
    return state


def render_panel(csrf_token, selected=""):
    tenants = []
    rows, _fields = _registry_rows()
    for row in rows:
        tenant = (row.get("tenant") or "").strip()
        if tenant:
            tenants.append(tenant)
    options = "".join(
        f'<option value="{tenant}"{" selected" if tenant == selected else ""}>{tenant}</option>'
        for tenant in sorted(set(tenants))
    )
    return f'''
<section class="card tenant-delete-tool">
  <div class="section-title"><div><h2>Excluir banco e tenant</h2><p>Operação destrutiva, separada da exclusão de projetos.</p></div><span class="pill warn">Backup obrigatório</span></div>
  <div class="help"><strong>Proteções:</strong> o tenant administrativo não pode ser removido; tenants vinculados a projetos são bloqueados; um dump lógico final é criado antes dos volumes serem apagados.</div>
  <form id="tenant-delete-preview-form">
    <input type="hidden" name="csrf_token" value="{csrf_token}">
    <label>Tenant</label>
    <select name="tenant" required><option value="">Selecione</option>{options}</select>
    <button class="btn red" type="submit">Analisar remoção</button>
  </form>
  <div id="tenant-delete-preview" hidden></div>
  <div id="tenant-delete-progress" hidden aria-live="polite"></div>
</section>
<style>
.tenant-delete-tool{{display:grid;gap:16px}}.tenant-delete-tool form{{display:grid;gap:10px;max-width:620px}}.tenant-delete-preview-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:14px 0}}.tenant-delete-preview-grid>div{{padding:12px;border:1px solid var(--c-border,#dce3ed);border-radius:10px;background:#f5faf6}}.tenant-delete-steps{{display:grid;gap:8px;padding:0;list-style:none}}.tenant-delete-steps li{{display:grid;grid-template-columns:auto 1fr;gap:8px 12px;align-items:center;padding:10px;border:1px solid var(--c-border,#dce3ed);border-radius:10px}}.tenant-delete-steps small{{grid-column:2;color:#111}}.tenant-delete-confirmation{{display:grid;gap:10px;max-width:720px}}.tenant-delete-confirmation input{{font-family:ui-monospace,monospace}}.tenant-delete-tool progress{{height:12px;accent-color:#8fb8e8}}
</style>
<script>
(() => {{
 const form=document.getElementById('tenant-delete-preview-form'); if(!form)return;
 const previewBox=document.getElementById('tenant-delete-preview'); const progressBox=document.getElementById('tenant-delete-progress');
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}}[c]));
 const portal='/cloudiff/portal/';
 async function jsonFetch(url,options={{}}){{
   const r=await fetch(url,{{credentials:'same-origin',...options}});
   const type=(r.headers.get('content-type')||'').toLowerCase();
   const text=await r.text();
   if(!type.includes('application/json')){{const e=new Error(`A operação não chegou ao serviço de exclusão (HTTP ${{r.status}}). Atualize a página e tente novamente.`);e.status=r.status;throw e}}
   let data;try{{data=JSON.parse(text)}}catch(_e){{throw new Error('O serviço de exclusão retornou uma resposta incompleta.')}}
   if(!r.ok){{const e=new Error(data.detail||data.error||`HTTP ${{r.status}}`);e.status=r.status;e.payload=data;throw e}}
   return data
 }}
 function initialTimeline(title,detail){{
   progressBox.hidden=false;
   progressBox.innerHTML=`<div class="section-title"><div><h3>Remoção do banco</h3><p>${{esc(title)}}</p></div><strong>0%</strong></div><progress max="100" value="0" style="width:100%"></progress><ol class="tenant-delete-steps"><li><span class="pill warn">Executando</span><strong>${{esc(title)}}</strong><small>${{esc(detail)}}</small></li></ol>`;
 }}
 function drawJob(job){{
   progressBox.hidden=false;
   const steps=(job.steps||[]).map(x=>`<li><span class="pill ${{x.status==='done'?'ok':x.status==='failed'?'bad':'warn'}}">${{x.status==='done'?'Concluído':x.status==='failed'?'Falhou':'Executando'}}</span><strong>${{esc(x.label)}}</strong><small>${{esc(x.detail||'')}}</small></li>`).join('');
   const terminal=job.status==='succeeded'?'<p class="pill ok">Banco removido e ambiente atualizado com sucesso.</p>':job.status==='failed'?`<p class="pill bad">Falha: ${{esc(job.error||job.detail||job.result?.error||'não identificada')}}</p>`:'';
   progressBox.innerHTML=`<div class="section-title"><div><h3>Remoção do banco</h3><p>${{esc(job.current_step||'Preparando')}}</p></div><strong>${{Number(job.progress||0)}}%</strong></div><progress max="100" value="${{Number(job.progress||0)}}" style="width:100%"></progress><ol class="tenant-delete-steps">${{steps}}</ol>${{terminal}}`;
 }}
 async function poll(id,attempt=0){{
   try{{
     const job=await jsonFetch(`${{portal}}?api=admin-delete-tenant-status&job_id=${{encodeURIComponent(id)}}`,{{headers:{{Accept:'application/json'}}}});
     drawJob(job);
     if(job.status==='queued'||job.status==='running')setTimeout(()=>poll(id,0),1200)
   }}catch(e){{
     const transient=[0,502,503,504].includes(Number(e.status||0));
     if(transient&&attempt<20){{
       const note=document.createElement('p');note.className='pill warn';note.textContent='A exclusão continua no servidor. Reconectando para recuperar o progresso…';progressBox.appendChild(note);setTimeout(()=>poll(id,attempt+1),1500);return
     }}
     progressBox.hidden=false;progressBox.insertAdjacentHTML('beforeend',`<p class="pill bad">${{esc(e.message)}}</p>`)
   }}
 }}
 form.addEventListener('submit',async e=>{{
   e.preventDefault();
   const fd=new FormData(form),tenant=String(fd.get('tenant')||'');
   previewBox.hidden=false;previewBox.innerHTML='<p class="pill warn">Analisando tenant, vínculos, containers e volumes…</p>';
   initialTimeline('Análise de segurança','Conferindo se o banco pode ser removido. Nenhuma alteração foi feita ainda.');
   try{{
     const p=await jsonFetch(`${{portal}}?api=admin-delete-tenant-preview&tenant=${{encodeURIComponent(tenant)}}`,{{headers:{{Accept:'application/json'}}}});
     const r=p.resources||{{}},blocked=(p.blockers||[]).length>0;
     previewBox.innerHTML=`<div class="tenant-delete-preview-grid"><div><small>Projetos vinculados</small><strong>${{(p.linked_projects||[]).length}}</strong></div><div><small>Containers</small><strong>${{(r.containers||[]).length}}</strong></div><div><small>Volumes</small><strong>${{(r.volumes||[]).length}}</strong></div><div><small>Diretório</small><strong>${{p.tenant_dir_present?'Presente':'Ausente'}}</strong></div></div>${{blocked?`<p class="pill bad">Bloqueado: ${{esc((p.blockers||[]).join(', '))}}</p>`:`<div class="tenant-delete-confirmation"><p class="pill warn">A próxima etapa cria um backup final antes de remover containers e volumes.</p><label>Digite exatamente <strong>${{esc(p.confirmation)}}</strong></label><input id="tenant-delete-confirm" autocomplete="off"><button id="tenant-delete-start" class="btn red" type="button" disabled>Excluir banco definitivamente</button><p id="tenant-delete-confirm-status" class="small">Aguardando a confirmação exata.</p></div>`}}`;
     if(blocked){{progressBox.hidden=true;return}}
     const input=document.getElementById('tenant-delete-confirm'),start=document.getElementById('tenant-delete-start'),confirmStatus=document.getElementById('tenant-delete-confirm-status');
     input.addEventListener('input',()=>{{const valid=input.value===p.confirmation;start.disabled=!valid;confirmStatus.textContent=valid?'Confirmação validada. Pronto para iniciar.':'Aguardando a confirmação exata.';confirmStatus.className=valid?'small pill ok':'small'}});
     start.onclick=async()=>{{
       const confirmation=input.value;if(confirmation!==p.confirmation)return;
       start.disabled=true;input.disabled=true;
       initialTimeline('Solicitação enviada','Criando o processo de exclusão e reservando o tenant para evitar operações simultâneas.');
       const csrf=String(fd.get('csrf_token')||'');
       const body=new URLSearchParams({{tenant,confirmation,csrf_token:csrf}});
       try{{
         const job=await jsonFetch(portal,{{method:'POST',headers:{{Accept:'application/json','Content-Type':'application/x-www-form-urlencoded;charset=UTF-8','X-CSRF-Token':csrf,'X-CloudIF-Action':'admin-delete-tenant'}},body}});
         drawJob(job);poll(job.job_id)
       }}catch(err){{
         progressBox.insertAdjacentHTML('beforeend',`<p class="pill bad">${{esc(err.message)}}</p>`);start.disabled=false;input.disabled=false
       }}
     }}
   }}catch(err){{previewBox.innerHTML=`<p class="pill bad">${{esc(err.message)}}</p>`;progressBox.hidden=true}}
 }})
}})();
</script>
'''
