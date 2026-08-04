import glob
import html
import hashlib
import secrets
import json
import os
import shutil
import sqlite3
import subprocess
import threading
import time
import traceback
import uuid
import urllib.request
import urllib.error
from pathlib import Path

from cloudif_delete_git_komodo_action import forja_rollback

DB = Path('/var/lib/cloudif/portal/cloudif-portal.db')
ONBOARDING_DB = Path('/var/lib/cloudif/onboarding/onboarding.db')
AUDIT_ROOT = Path('/srv/cloudif/admin-project-deletions')
JOBS = Path('/srv/cloudif/jobs')
PROVISIONING = Path('/srv/cloudif/provisioning/projects')
AGENTS_DB = Path('/var/lib/cloudif/agents/agents.db')
NOTIFICATIONS_DB = Path('/var/lib/cloudif/notifications/notifications.db')
MONITOR_DB = Path('/var/lib/cloudif/monitoring/monitor.db')
ONBOARDING_SECRETS = Path('/var/lib/cloudif/onboarding/secrets')
JOB_ROOT = Path('/srv/cloudif/admin-project-deletions/.jobs')
WIZARD_ROOT = JOB_ROOT / '.wizard-tokens'


def issue_wizard_token(slug):
    WIZARD_ROOT.mkdir(parents=True, exist_ok=True)
    token=secrets.token_urlsafe(32)
    payload={'slug':slug,'created_at':time.time(),'expires_at':time.time()+900}
    target=WIZARD_ROOT/(hashlib.sha256(token.encode()).hexdigest()+'.json')
    target.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')))
    os.chmod(target,0o600)
    return token


def consume_wizard_token(slug, token):
    if not token or any(ch.isspace() for ch in token): return False
    target=WIZARD_ROOT/(hashlib.sha256(token.encode()).hexdigest()+'.json')
    try:
        payload=json.loads(target.read_text())
    except Exception:
        return False
    try: target.unlink()
    except FileNotFoundError: pass
    return payload.get('slug')==slug and float(payload.get('expires_at') or 0)>=time.time()


def _job_write(job_id, data):
    JOB_ROOT.mkdir(parents=True, exist_ok=True)
    target = JOB_ROOT / f'{job_id}.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    os.replace(temporary, target)


def job_status(job_id):
    if not job_id or any(ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-' for ch in job_id):
        return {'ok': False, 'error': 'invalid_job_id'}
    path = JOB_ROOT / f'{job_id}.json'
    if not path.exists():
        return {'ok': False, 'error': 'job_not_found'}
    state=json.loads(path.read_text())
    if state.get('status')=='failed' and state.get('error')=='project_not_found':
        slug=str(state.get('slug') or '')
        previous={}
        for result_path in sorted(AUDIT_ROOT.glob(f'*-{slug}/result.json'),key=lambda x:x.stat().st_mtime,reverse=True):
            try:
                candidate=json.loads(result_path.read_text())
                if candidate.get('ok') is True: previous=candidate;break
            except Exception: pass
        if previous:
            state.update({'status':'succeeded','progress':100,'current_step':'Concluído','error':'','already_deleted':True,'result':{'ok':True,'already_deleted':True,'slug':slug,'tenant_preserved':previous.get('tenant_preserved') or '','message':'Projeto já excluído; resíduos verificados.'},'steps':[{'label':'Validação','status':'done','detail':'Projeto já excluído; resíduos verificados.'}]})
    return state


def start_job(slug, confirmation, actor):
    JOB_ROOT.mkdir(parents=True, exist_ok=True)
    lock_path = JOB_ROOT / f'.{slug}.lock'
    lock_fd = None
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(lock_fd, f'{os.getpid()} {time.time()}\n'.encode())
    except FileExistsError:
        for candidate in sorted(JOB_ROOT.glob('*.json'), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                existing = json.loads(candidate.read_text())
            except Exception:
                continue
            if existing.get('slug') == slug and existing.get('status') in {'queued', 'running'}:
                existing['deduplicated'] = True
                return existing
        try:
            if time.time() - lock_path.stat().st_mtime > 900:
                lock_path.unlink()
                return start_job(slug, confirmation, actor)
        except FileNotFoundError:
            return start_job(slug, confirmation, actor)
        return {'ok': False, 'error': 'project_delete_already_running', 'slug': slug}
    finally:
        if lock_fd is not None:
            os.close(lock_fd)

    job_id = uuid.uuid4().hex
    state = {
        'ok': True, 'job_id': job_id, 'slug': slug, 'actor': actor,
        'status': 'queued', 'current_step': 'Validação', 'progress': 0,
        'steps': [], 'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    }
    _job_write(job_id, state)

    def update(label, status='running', detail=''):
        current = job_status(job_id)
        steps = current.setdefault('steps', [])
        existing = next((item for item in steps if item.get('label') == label), None)
        if existing is None:
            existing = {'label': label}
            steps.append(existing)
        existing.update({'status': status, 'detail': detail, 'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S%z')})
        current['current_step'] = label
        done = sum(1 for item in steps if item.get('status') in {'done', 'failed'})
        current['progress'] = min(95, done * 11)
        current['status'] = 'running'
        _job_write(job_id, current)

    def worker():
        try:
            result = execute(slug, confirmation, actor, progress=update)
            current = job_status(job_id)
            current.update({
                'status': 'succeeded' if result.get('ok') else 'failed',
                'progress': 100, 'result': result,
                'finished_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            })
            if not result.get('ok'):
                current['error'] = result.get('error') or 'delete_failed'
            _job_write(job_id, current)
        except Exception as exc:
            current = job_status(job_id)
            current.update({
                'status': 'failed', 'progress': 100,
                'error': type(exc).__name__, 'detail': str(exc)[:500],
                'traceback': traceback.format_exc(limit=8),
                'finished_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            })
            _job_write(job_id, current)
        finally:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    threading.Thread(target=worker, name=f'project-delete-{job_id[:8]}', daemon=False).start()
    return state


def h(value):
    return html.escape(str(value if value is not None else ''), quote=True)


def _rows(db, table, key, slug):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in con.execute(f'SELECT * FROM {table} WHERE {key}=?', (slug,))]
    except sqlite3.DatabaseError:
        return []
    finally:
        con.close()


def projects():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in con.execute(
            "SELECT slug,name,owner,tenant,repo_url,komodo_status,status FROM projects ORDER BY lower(name),slug"
        )]
    finally:
        con.close()


def preview(slug):
    project = _rows(DB, 'projects', 'slug', slug)
    if not project:
        previous={}
        for result_path in sorted(AUDIT_ROOT.glob(f'*-{slug}/result.json'),key=lambda x:x.stat().st_mtime,reverse=True):
            try:
                candidate=json.loads(result_path.read_text())
                if candidate.get('ok') is True: previous=candidate;break
            except Exception: pass
        if previous:
            return {'ok':True,'already_deleted':True,'slug':slug,'tenant_preserved':previous.get('tenant_preserved') or '','message':'Projeto já excluído; resíduos verificados.','finished_at':previous.get('finished_at') or ''}
        return {'ok': False, 'error': 'project_not_found', 'slug': slug}
    tenant = str(project[0].get('tenant') or '')
    local = {}
    con = sqlite3.connect(DB)
    try:
        for table, in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            cols = {row[1] for row in con.execute(f'PRAGMA table_info({table})')}
            key = next((candidate for candidate in ('slug', 'project_slug', 'project') if candidate in cols), None)
            if not key:
                continue
            count = con.execute(f'SELECT COUNT(*) FROM {table} WHERE {key}=?', (slug,)).fetchone()[0]
            if count:
                local[table] = count
    finally:
        con.close()
    remote = forja_rollback(slug, execute=False)
    return {
        'ok': True,
        'slug': slug,
        'project': project[0],
        'tenant_preserved': tenant,
        'local_rows': local,
        'jobs': sorted(glob.glob(str(JOBS / f'*{slug}*'))),
        'provisioning_path': str(PROVISIONING / slug) if (PROVISIONING / slug).exists() else '',
        'remote_preview': remote,
    }


def _delete_rows(con, slug):
    removed = {}
    tables = [row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    # Dependents first; projects last.
    tables = [t for t in tables if t != 'projects'] + (['projects'] if 'projects' in tables else [])
    for table in tables:
        cols = {row[1] for row in con.execute(f'PRAGMA table_info({table})')}
        key = next((candidate for candidate in ('slug', 'project_slug', 'project') if candidate in cols), None)
        if not key:
            continue
        try:
            count = con.execute(f'DELETE FROM {table} WHERE {key}=?', (slug,)).rowcount
            if count:
                removed[table] = count
        except sqlite3.DatabaseError:
            continue
    return removed


def _env(path):
    data={}
    p=Path(path)
    if not p.exists(): return data
    for raw in p.read_text(errors='ignore').splitlines():
        line=raw.strip()
        if line and not line.startswith('#') and '=' in line:
            k,v=line.split('=',1);data[k.strip()]=v.strip().strip('"').strip("'")
    return data


def _post_json(url, token, payload, timeout=90, host=''):
    headers={'Accept':'application/json','Content-Type':'application/json'}
    if host: headers['Host']=host
    if token: headers.update({'X-CloudIF-Token':token,'Authorization':'Bearer '+token})
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers=headers,method='POST')
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:
            return {'ok':200 <= response.status < 300,'status':response.status,'data':json.loads(response.read() or b'{}')}
    except urllib.error.HTTPError as exc:
        raw=exc.read().decode('utf-8','replace')
        try: data=json.loads(raw)
        except Exception: data={'raw':raw[:2000]}
        return {'ok':False,'status':exc.code,'error':'HTTPError','detail':str(exc)[:300],'data':data}
    except Exception as exc:
        return {'ok':False,'status':0,'error':type(exc).__name__,'detail':str(exc)[:300]}


def _destroy_runtime(slug, tenant):
    cfg=_env('/etc/cloudif/komodo-agent-client.env')
    return _post_json((cfg.get('KOMODO_AGENT_URL') or 'http://10.62.91.2:18098').rstrip('/')+'/komodo/stack/destroy',cfg.get('KOMODO_AGENT_TOKEN',''),{'project':slug,'tenant':tenant,'actor':'admin-project-delete'})


def _unpublish(public_number):
    if not public_number: return {'ok':True,'skipped':True}
    cfg=_env('/etc/cloudif/npm-publisher-client.env')
    return _post_json('http://10.62.91.3/unpublish',cfg.get('NPM_PUBLISHER_TOKEN',''),{'public_number':int(public_number)},host='cloudif-publisher.internal')

def _backup_if_exists(source, destination):
    source=Path(source)
    if source.exists():
        shutil.copy2(source,destination)
        os.chmod(destination,0o600)


def _delete_agent_identity(slug):
    if not AGENTS_DB.exists(): return {'clients':0,'usage':0,'client_ids':[]}
    con=sqlite3.connect(AGENTS_DB)
    try:
        con.execute('BEGIN IMMEDIATE')
        rows=con.execute("SELECT client_id,project_slugs_json FROM clients WHERE client_id LIKE 'project-%'").fetchall()
        matches=[]
        for client_id,raw in rows:
            try: projects=json.loads(raw or '[]')
            except Exception: projects=[]
            if slug in projects: matches.append(client_id)
        usage=0
        for client_id in matches:
            usage += con.execute('DELETE FROM usage WHERE client_id=?',(client_id,)).rowcount
        clients=0
        for client_id in matches:
            clients += con.execute("DELETE FROM clients WHERE client_id=? AND client_id LIKE 'project-%'",(client_id,)).rowcount
        con.commit()
        return {'clients':clients,'usage':usage,'client_ids':matches}
    except Exception:
        con.rollback();raise
    finally: con.close()


def _delete_onboarding_state(slug):
    out={'project_onboarding':0,'onboarding_events':0,'credential_rotations':0,'secret_file':False}
    if ONBOARDING_DB.exists():
        con=sqlite3.connect(ONBOARDING_DB)
        try:
            con.execute('BEGIN IMMEDIATE')
            for table in ('credential_rotations','onboarding_events','project_onboarding'):
                cols={r[1] for r in con.execute(f'PRAGMA table_info({table})')}
                if 'project_slug' in cols:
                    out[table]=con.execute(f'DELETE FROM {table} WHERE project_slug=?',(slug,)).rowcount
            con.commit()
        except Exception:
            con.rollback();raise
        finally: con.close()
    secret=ONBOARDING_SECRETS/f'{slug}.json'
    if secret.exists():
        secret.unlink();out['secret_file']=True
    return out


BACKUP_STATE = Path('/var/lib/cloudif/portal/project-backup-settings.json')
BACKUP_ROOT = Path('/srv/cloudif/managed-backups/projects')


def _delete_backup_state(slug):
    out={'settings_removed':False,'files_removed':False}
    if BACKUP_STATE.exists():
        try:
            data=json.loads(BACKUP_STATE.read_text())
        except Exception:
            data={}
        projects=data.get('projects') or {}
        if slug in projects:
            projects.pop(slug,None);data['projects']=projects
            tmp=BACKUP_STATE.with_name(BACKUP_STATE.name+'.tmp')
            tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');os.chmod(tmp,0o600);os.replace(tmp,BACKUP_STATE)
            out['settings_removed']=True
    root=BACKUP_ROOT/slug
    if root.exists():
        shutil.rmtree(root);out['files_removed']=True
    return out


def _delete_observability(slug):
    out={'notifications':0,'monitor_latest':0,'monitor_samples':0}
    if NOTIFICATIONS_DB.exists():
        con=sqlite3.connect(NOTIFICATIONS_DB)
        try:
            con.execute('BEGIN IMMEDIATE')
            out['notifications']=con.execute('DELETE FROM notifications WHERE project_slug=?',(slug,)).rowcount
            con.commit()
        except Exception:
            con.rollback();raise
        finally: con.close()
    if MONITOR_DB.exists():
        con=sqlite3.connect(MONITOR_DB)
        try:
            con.execute('BEGIN IMMEDIATE')
            out['monitor_latest']=con.execute('DELETE FROM latest WHERE slug=?',(slug,)).rowcount
            out['monitor_samples']=con.execute('DELETE FROM samples WHERE slug=?',(slug,)).rowcount
            con.commit()
        except Exception:
            con.rollback();raise
        finally: con.close()
    return out

def _latest_successful_delete(slug):
    candidates=sorted(AUDIT_ROOT.glob(f'*-{slug}/result.json'),key=lambda x:x.stat().st_mtime,reverse=True)
    for path in candidates:
        try:
            data=json.loads(path.read_text())
            if data.get('ok') is True: return data
        except Exception: pass
    return {}


def _recover_tenant(slug):
    previous=_latest_successful_delete(slug)
    tenant=str(previous.get('tenant_preserved') or '')
    if tenant: return tenant
    for path in sorted(JOBS.glob(f'*{slug}*.json'),key=lambda x:x.stat().st_mtime,reverse=True):
        try:
            data=json.loads(path.read_text());tenant=str(data.get('tenant') or '')
            if tenant:return tenant
        except Exception:pass
    return ''


def _cleanup_already_deleted(slug, actor, progress):
    tenant=_recover_tenant(slug)
    progress('Validação','done','Projeto já removido do Portal; verificando resíduos')
    progress('Stack e runtime','running','Verificando containers e stack órfãos')
    runtime=_destroy_runtime(slug,tenant)
    progress('Stack e runtime','done' if runtime.get('ok') else 'failed','Resíduos removidos' if runtime.get('ok') else 'Ainda há resíduos')
    remote=forja_rollback(slug,execute=True)
    agent_identity=_delete_agent_identity(slug); onboarding_state=_delete_onboarding_state(slug); observability=_delete_observability(slug); backup_state=_delete_backup_state(slug)
    removed_paths=[]
    for candidate in glob.glob(str(JOBS / f'*{slug}*')):
        try: os.remove(candidate);removed_paths.append(candidate)
        except FileNotFoundError: pass
    provision_dir=PROVISIONING/slug
    if provision_dir.exists(): shutil.rmtree(provision_dir);removed_paths.append(str(provision_dir))
    ok=bool(runtime.get('ok') and remote.get('ok'))
    return {'ok':ok,'already_deleted':True,'slug':slug,'actor':actor,'tenant_preserved':tenant,'runtime_destroy':runtime,'remote':remote,'agent_identity':agent_identity,'onboarding_state':onboarding_state,'observability':observability,'backup_state':backup_state,'removed_paths':removed_paths,'message':'Projeto já excluído; resíduos verificados e removidos.' if ok else 'Projeto já excluído do Portal, mas ainda há resíduos a verificar.','finished_at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}


def execute(slug, confirmation, actor, progress=None):
    progress = progress or (lambda *args, **kwargs: None)
    progress('Validação', 'running', 'Conferindo confirmação e projeto')
    expected = f'EXCLUIR {slug}'
    if confirmation != expected:
        return {'ok': False, 'error': 'invalid_confirmation', 'expected': expected}
    plan = preview(slug)
    if not plan.get('ok') and plan.get('error')=='project_not_found':
        return _cleanup_already_deleted(slug,actor,progress)
    progress('Validação', 'done' if plan.get('ok') else 'failed', 'Projeto localizado' if plan.get('ok') else 'Projeto não encontrado')
    if not plan.get('ok'):
        return plan
    public_rows=_rows(DB,'project_public_ids','project_slug',slug)
    public_number=int(public_rows[0].get('public_number')) if public_rows else 0
    stamp = time.strftime('%Y%m%d-%H%M%S')
    audit = AUDIT_ROOT / f'{stamp}-{time.time_ns() % 1000000000:09d}-{slug}'
    audit.mkdir(parents=True, exist_ok=False)
    _backup_if_exists(DB, audit / 'cloudif-portal.db')
    _backup_if_exists(ONBOARDING_DB, audit / 'onboarding.db')
    _backup_if_exists(AGENTS_DB, audit / 'agents.db')
    _backup_if_exists(NOTIFICATIONS_DB, audit / 'notifications.db')
    _backup_if_exists(MONITOR_DB, audit / 'monitor.db')
    secret_path=ONBOARDING_SECRETS/f'{slug}.json'
    if secret_path.exists(): _backup_if_exists(secret_path,audit/'onboarding-secret.json')
    (audit / 'preview.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')

    progress('Publicação e aliases', 'running', 'Removendo publicação')
    publication = _unpublish(public_number)
    progress('Publicação e aliases', 'done' if publication.get('ok') else 'failed', f"HTTP {publication.get('status') or '-'}")
    if not publication.get('ok'):
        result={'ok':False,'error':'publication_delete_failed','publication':publication,'audit_dir':str(audit)}
        (audit/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    progress('Stack e runtime', 'running', 'Removendo stack sem tocar no banco')
    runtime = _destroy_runtime(slug, plan.get('tenant_preserved') or '')
    progress('Stack e runtime', 'done' if runtime.get('ok') else 'failed', f"HTTP {runtime.get('status') or '-'}")
    if not runtime.get('ok'):
        result={'ok':False,'error':'runtime_destroy_failed','runtime':runtime,'publication':publication,'audit_dir':str(audit)}
        (audit/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    progress('Forgejo e agentes', 'running', 'Removendo repositório e estados dos agentes')
    remote = forja_rollback(slug, execute=True)
    progress('Forgejo e agentes', 'done' if remote.get('ok') else 'failed', f"HTTP {remote.get('status') or '-'}")
    if not remote.get('ok'):
        result = {'ok': False, 'error': 'remote_delete_failed', 'remote': remote, 'audit_dir': str(audit)}
        (audit / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        return result

    progress('Registros do Portal', 'running', 'Removendo vínculos e ACLs')
    con = sqlite3.connect(DB)
    try:
        con.execute('BEGIN IMMEDIATE')
        removed = _delete_rows(con, slug)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

    progress('Registros do Portal', 'done', f'{sum(removed.values()) if removed else 0} registro(s)')
    progress('Identidade e onboarding', 'running', 'Removendo identidade, onboarding e credenciais')
    agent_identity = _delete_agent_identity(slug)
    onboarding_state = _delete_onboarding_state(slug)
    onboarding_removed = onboarding_state.get('project_onboarding',0)
    observability = _delete_observability(slug)
    backup_state = _delete_backup_state(slug)
    progress('Identidade e onboarding', 'done', 'Estados e backup do projeto removidos')

    removed_paths = []
    for candidate in glob.glob(str(JOBS / f'*{slug}*')):
        try:
            os.remove(candidate)
            removed_paths.append(candidate)
        except FileNotFoundError:
            pass
    provision_dir = PROVISIONING / slug
    if provision_dir.exists():
        shutil.rmtree(provision_dir)
        removed_paths.append(str(provision_dir))

    progress('Reconciliação', 'running', 'Solicitando reconciliação em segundo plano')
    subprocess.Popen(['systemctl', 'start', '--no-block', 'cloudif-project-state-reconcile.service'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    progress('Reconciliação', 'done', 'Solicitada sem bloquear a exclusão')
    result = {
        'ok': True,
        'slug': slug,
        'actor': actor,
        'tenant_preserved': plan.get('tenant_preserved') or '',
        'publication': publication,
        'runtime_destroy': runtime,
        'remote': remote,
        'removed_rows': removed,
        'onboarding_removed': onboarding_removed,
        'agent_identity': agent_identity,
        'onboarding_state': onboarding_state,
        'observability': observability,
        'backup_state': backup_state,
        'removed_paths': removed_paths,
        'audit_dir': str(audit),
        'finished_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'secrets_exposed': False,
    }
    (audit / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def _stage(label, ok, detail=''):
    state='Concluído' if ok else 'Pendente ou falhou'
    cls='ok' if ok else 'bad'
    return f'<li><span class="pill {cls}">{h(state)}</span><strong>{h(label)}</strong><small>{h(detail)}</small></li>'


def _result_stages(result):
    if not result: return ''
    publication=result.get('publication') or {}
    runtime=result.get('runtime_destroy') or result.get('runtime') or {}
    remote=result.get('remote') or {}
    forge=((remote.get('data') or {}).get('forgejo') or {})
    removed=result.get('removed_rows') or {}
    items=[
        _stage('Publicação e aliases', publication.get('ok') is True, f"HTTP {publication.get('status') or '-'}"),
        _stage('Stack e repositório Komodo', runtime.get('ok') is True, f"HTTP {runtime.get('status') or '-'}"),
        _stage('Repositório Forgejo', forge.get('deleted') is True, f"HTTP {forge.get('status') or '-'}"),
        _stage('Registros do Portal', bool(removed) or result.get('ok') is True, f"{sum(removed.values()) if removed else 0} registros"),
        _stage('Identidade do agente', (result.get('agent_identity') or {}).get('clients',0) >= 0 and result.get('ok') is True, f"{(result.get('agent_identity') or {}).get('clients',0)} cliente(s)"),
        _stage('Onboarding e credencial', result.get('onboarding_removed',0) >= 0 and result.get('ok') is True, f"{result.get('onboarding_removed',0)} registro(s)"),
        _stage('Observabilidade', result.get('ok') is True, f"{sum((result.get('observability') or {}).values())} registro(s)"),
        _stage('Reconciliação', result.get('ok') is True, 'Solicitada após a exclusão'),
    ]
    return '<ol class="admin-delete-steps">'+''.join(items)+'</ol>'

def render(csrf_token, selected='', result=None):
    rows = projects()
    options = ''.join(
        f'<option value="{h(p["slug"])}"{" selected" if p["slug"] == selected else ""}>{h(p.get("name") or p["slug"])} — {h(p["slug"])}</option>'
        for p in rows
    )
    result_html = ''
    if result is not None:
        cls = 'ok' if result.get('ok') else 'bad'
        title = ('Projeto já excluído' if result.get('already_deleted') else 'Projeto excluído') if result.get('ok') else 'Exclusão não concluída'
        result_html = (
            f'<section class="card"><span class="pill {cls}">{h(title)}</span>'
            f'{_result_stages(result)}<details><summary>Relatório técnico</summary><pre style="white-space:pre-wrap;overflow:auto;max-height:420px">{h(json.dumps(result, ensure_ascii=False, indent=2))}</pre></details></section>'
        )
    selected_preview = preview(selected) if selected else None
    wizard_token = issue_wizard_token(selected) if selected_preview and selected_preview.get('ok') and not selected_preview.get('already_deleted') else ''
    preview_html = ''
    if selected_preview:
        if selected_preview.get('already_deleted'):
            preview_html = f'<section class="card"><span class="pill ok">Projeto já excluído</span><p>{h(selected_preview.get("message"))}</p><p class="small">Tenant preservado: <strong>{h(selected_preview.get("tenant_preserved") or "não informado")}</strong></p></section>'
        else:
            preview_html = f'<pre style="white-space:pre-wrap;overflow:auto;max-height:360px">{h(json.dumps(selected_preview, ensure_ascii=False, indent=2))}</pre>'
    return f'''
<section class="card admin-delete-project">
  <div class="section-title"><div><h1>Excluir projeto</h1><p>Remoção administrativa de Portal, Forgejo, Komodo, onboarding, jobs e artefatos. O tenant/banco é preservado.</p></div><span class="pill bad">Ação irreversível</span></div>
  <form method="get" action="/cloudiff/portal/">
    <input type="hidden" name="tab" value="admin-excluir-projeto">
    <label>Projeto<select name="slug" required><option value="">Selecione</option>{options}</select></label>
    <button class="btn light" type="submit">Gerar prévia</button>
  </form>
  {preview_html}
  {f'''<form id="admin-delete-form" method="post" action="/cloudiff/portal/action/admin-delete-project">
    <input type="hidden" name="csrf_token" value="{h(csrf_token)}">
    <input type="hidden" name="slug" value="{h(selected)}">
    <input type="hidden" name="wizard_token" value="{h(wizard_token)}">
    <label>Digite exatamente <code>EXCLUIR {h(selected)}</code><input name="confirm_text" required autocomplete="off"></label>
    <button class="btn danger" type="submit">Excluir projeto definitivamente</button><div id="admin-delete-progress" hidden aria-live="polite"></div>
  </form>''' if selected_preview and selected_preview.get('ok') and not selected_preview.get('already_deleted') else ''}
</section>{result_html}
<script>
(() => {{
 const form=document.getElementById('admin-delete-form'); if(!form)return;
 const box=document.getElementById('admin-delete-progress'); const button=form.querySelector('button[type=submit]');
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
 function draw(job){{
  box.hidden=false;
  const steps=(job.steps||[]).map(x=>`<li><span class="pill ${{x.status==='done'?'ok':x.status==='failed'?'bad':'muted'}}">${{x.status==='done'?'Concluído':x.status==='failed'?'Falhou':'Executando'}}</span><strong>${{esc(x.label)}}</strong><small>${{esc(x.detail||'')}}</small></li>`).join('');
  box.innerHTML=`<div class="section-title"><div><h3>Exclusão em andamento</h3><p>${{esc(job.current_step||'Preparando')}}</p></div><strong>${{Number(job.progress||0)}}%</strong></div><progress max="100" value="${{Number(job.progress||0)}}" style="width:100%"></progress><ol class="admin-delete-steps">${{steps}}</ol>${{job.status==='failed'?`<p class="pill bad">Falha: ${{esc(job.error||job.detail||'não identificada')}}</p>`:''}}`;
 }}
 async function poll(id){{
  const response=await fetch(`/cloudiff/portal/api/admin-delete-project-status?job_id=${{encodeURIComponent(id)}}`,{{headers:{{Accept:'application/json'}},credentials:'same-origin'}}); const type=(response.headers.get('content-type')||'').toLowerCase(); if(!type.includes('application/json'))throw new Error(`Resposta inválida do servidor (HTTP ${{response.status}})`); const job=await response.json(); if(!response.ok)throw new Error(job.error||`HTTP ${{response.status}}`); draw(job);
  if(job.status==='queued'||job.status==='running') return setTimeout(()=>poll(id),1000);
  button.disabled=false; button.textContent=job.status==='succeeded'?'Exclusão concluída':'Tentar novamente';
 }}
 form.addEventListener('submit',async event=>{{
  event.preventDefault(); if(!confirm('Confirma a exclusão definitiva? O banco será preservado.'))return;
  button.disabled=true; button.textContent='Iniciando…'; box.hidden=false; box.innerHTML='<p>Preparando exclusão…</p>';
  const formData=new FormData(form); formData.set('async','1'); const csrf=(formData.get('csrf_token')||'').toString(); const data=new URLSearchParams(); for(const [key,value] of formData.entries())data.append(key,String(value));
  try{{ const response=await fetch(form.action,{{method:'POST',body:data,credentials:'same-origin',headers:{{Accept:'application/json','Content-Type':'application/x-www-form-urlencoded;charset=UTF-8','X-CSRF-Token':csrf}}}}); const type=(response.headers.get('content-type')||'').toLowerCase(); const text=await response.text(); let job; try{{job=type.includes('application/json')?JSON.parse(text):{{error:text.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim().slice(0,240)||`HTTP ${{response.status}}`}};}}catch(_e){{job={{error:`Resposta inválida do servidor (HTTP ${{response.status}})`}};}} if(!response.ok)throw new Error(job.error||job.detail||`HTTP ${{response.status}}`); draw(job); poll(job.job_id); }}
  catch(error){{box.innerHTML=`<p class="pill bad">${{esc(error.message)}}</p>`;button.disabled=false;button.textContent='Tentar novamente';}}
 }});
}})();
</script>
'''
