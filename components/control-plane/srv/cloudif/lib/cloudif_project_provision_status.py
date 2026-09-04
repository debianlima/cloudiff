#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

DB=Path(os.environ.get('CLOUDIF_PORTAL_DB','/var/lib/cloudif/portal/cloudif-portal.db'))
JOBDIR=Path(os.environ.get('CLOUDIF_PROJECT_JOB_DIR','/srv/cloudif/jobs'))
PROVISION_ROOT=Path(os.environ.get('CLOUDIF_PROJECT_PROVISION_ROOT','/srv/cloudif/provisioning/projects'))
ACTIVE_STATUSES={'queued','running'}
CORE_COMPONENTS=('forgejo','komodo','supabase')


def _load(path,default=None):
    try:
        value=json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else ({} if default is None else default)
    except Exception:
        return {} if default is None else default


def _connect():
    connection=sqlite3.connect(f'file:{DB}?mode=ro',uri=True,timeout=20)
    connection.row_factory=sqlite3.Row
    connection.execute('pragma busy_timeout=20000')
    return connection


def _project(slug):
    if not DB.exists():return None
    connection=_connect()
    try:return connection.execute('select * from projects where slug=?',(slug,)).fetchone()
    finally:connection.close()


def _publication(slug):
    if not DB.exists():return None
    connection=_connect()
    try:
        tables={row[0] for row in connection.execute("select name from sqlite_master where type='table'")}
        if 'project_publications' not in tables:return None
        row=connection.execute("select * from project_publications where project_slug=? and is_active=1 and status in ('published','active','ready') order by deploy_number desc limit 1",(slug,)).fetchone()
        if row:return dict(row)
        return None
    finally:connection.close()


def _public_number(slug):
    if not DB.exists():return 0
    connection=_connect()
    try:
        tables={row[0] for row in connection.execute("select name from sqlite_master where type='table'")}
        if 'project_public_ids' not in tables:return 0
        row=connection.execute('select public_number from project_public_ids where project_slug=?',(slug,)).fetchone()
        return int((row or [0])[0] or 0)
    finally:connection.close()


def _jobs(slug):
    rows=[]
    for path in JOBDIR.glob(f'project-provision-*-{slug}.json'):
        data=_load(path)
        if data:
            rows.append((path.stat().st_mtime,path,data))
    return sorted(rows,reverse=True,key=lambda item:item[0])


def latest_job(slug):
    rows=_jobs(slug)
    return rows[0] if rows else None


def active_job(slug):
    for _,path,data in _jobs(slug):
        if str(data.get('status') or '') in ACTIVE_STATUSES:return path,data
    return None,None


def _components(report):
    source=report.get('components') or {}
    return {name:{'ok':bool((source.get(name) or {}).get('ok')),'status':str((source.get(name) or {}).get('status') or 'pending')} for name in CORE_COMPONENTS}


def _core_ready(report):
    components=report.get('components') or {}
    return bool(report.get('ok') is True and all((components.get(name) or {}).get('ok') is True for name in CORE_COMPONENTS))


def _runtime_metadata(slug):
    root=PROVISION_ROOT/slug
    managed=_load(root/'managed-runtime.json')
    template=_load(root/'template-applied.json')
    runtime=str(managed.get('runtime_template') or template.get('runtime_template') or '').strip()
    php=str(managed.get('php_version') or template.get('php_version') or '').strip()
    layout=str(managed.get('layout') or template.get('runtime_layout') or 'managed-root-v1').strip()
    kind=str(template.get('template_kind') or '').strip()
    template_applied=bool(template and kind in {'links','onboarding'})
    source='durable' if (managed or template) else ''
    if not (runtime in {'node20','node22','node24'} and php in {'8.2','8.3','8.4'} and layout=='managed-root-v1' and kind in {'links','onboarding'}):
        for _,_,candidate in _jobs(slug):
            candidate_kind=str(candidate.get('template_kind') or '').strip()
            candidate_runtime=str(candidate.get('runtime_template') or '').strip()
            candidate_php=str(candidate.get('php_version') or '').strip()
            candidate_layout=str(candidate.get('runtime_layout') or 'managed-root-v1').strip()
            if candidate_kind in {'links','onboarding'} and candidate_runtime in {'node20','node22','node24'} and candidate_php in {'8.2','8.3','8.4'} and candidate_layout=='managed-root-v1':
                runtime,php,layout,kind=candidate_runtime,candidate_php,candidate_layout,candidate_kind
                source='job-fallback'
                break
    valid=runtime in {'node20','node22','node24'} and php in {'8.2','8.3','8.4'} and layout=='managed-root-v1' and kind in {'links','onboarding'}
    return {'valid':valid,'runtime_template':runtime,'php_version':php,'runtime_layout':layout,'template_kind':kind,'template_applied':template_applied,'source':source}


def status(slug):
    slug=str(slug or '').strip()
    project=_project(slug)
    if not project:return {'ok':False,'error':'project_not_found','slug':slug,'secrets_exposed':False}
    root=PROVISION_ROOT/slug
    report=_load(root/'provision-report.json')
    initial=_load(root/'initial-publication.json')
    publication=_publication(slug)
    runtime=_runtime_metadata(slug)
    latest=latest_job(slug)
    job=dict(latest[2]) if latest else {}
    components=_components(report)
    current_status=str(job.get('status') or '')
    current_step=str(job.get('current_step') or '')
    last_error=str(job.get('last_error') or '')
    updated=str(job.get('updated_at') or report.get('finished_at') or project['updated_at'] or '')
    source='job' if job else 'derived'

    publication_ready=bool(publication)
    core_ready=_core_ready(report)
    recoverable=bool(core_ready and not publication_ready and runtime['valid'] and current_status not in ACTIVE_STATUSES)

    if current_status in ACTIVE_STATUSES:
        derived=current_status
    elif publication_ready:
        derived='succeeded';current_step='complete';last_error=''
    elif current_status=='failed':
        derived='failed';current_step=current_step or 'initial-publication'
    elif current_status=='succeeded' and not publication_ready:
        derived='failed';current_step='initial-publication';last_error='A publicação inicial não está registrada, embora o job anterior tenha sido concluído.'
    elif core_ready:
        derived='failed';current_step='initial-publication';last_error='Infraestrutura pronta; a publicação inicial está pendente. Use “Retomar publicação”.'
    elif report:
        derived='failed';current_step='provision';last_error='O relatório técnico indica componentes incompletos.'
    else:
        derived='not_started';current_step='';last_error=''

    return {
        'ok':True,'slug':slug,'status':derived,'step':current_step,'current_step':current_step,
        'error':last_error,'last_error':last_error,'updated_at':updated,'tenant':str(project['tenant'] or ''),
        'runtime_template':runtime['runtime_template'],'php_version':runtime['php_version'],
        'runtime_layout':runtime['runtime_layout'],'components':components,'result':job.get('result') or {},
        'recoverable':recoverable,'recovery_action':'resume_initial_publication' if recoverable else '',
        'source':source,'publication':{'active':bool(publication),'initial_record':bool(initial.get('ok')),'public_number':_public_number(slug)},
        'secrets_exposed':False,
    }


def resume_material(slug,user,global_admin=False):
    slug=str(slug or '').strip();username=str((user or {}).get('username') or '').strip()
    project=_project(slug)
    if not project:raise LookupError('project_not_found')
    owner=str(project['owner'] or '').strip()
    if not global_admin and username.casefold()!=owner.casefold():raise PermissionError('project_owner_required')
    state=status(slug)
    if not state.get('recoverable'):raise RuntimeError('initial_publication_not_recoverable')
    running_path,running=active_job(slug)
    if running_path:raise RuntimeError('project_provision_already_running')
    runtime=_runtime_metadata(slug)
    if not runtime['valid']:raise RuntimeError('runtime_metadata_invalid')
    return {
        'action':'resume_initial_publication','slug':slug,'name':str(project['name'] or slug),
        'description':str(project['description'] or ''),'tenant':str(project['tenant'] or ''),
        'db_mode':'link' if project['tenant'] else 'skip','tenant_keepalive_hours':6,
        'create_repo':'0','setup_komodo':'0','template_kind':runtime['template_kind'],
        'runtime_template':runtime['runtime_template'],'runtime_layout':runtime['runtime_layout'],
        'php_version':runtime['php_version'],'role_profile':'project-admin','environment':'project',
        'status':'queued','current_step':'initial-publication' if runtime.get('template_applied') else 'template','last_error':'',
        'user':{'username':username,'email':str((user or {}).get('email') or ''),'groups':[str(x) for x in ((user or {}).get('groups') or [])]},
        'created_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'resume_from':'initial-publication' if runtime.get('template_applied') else 'template',
        'public_number':state['publication']['public_number'],'secrets_exposed':False,
    }
