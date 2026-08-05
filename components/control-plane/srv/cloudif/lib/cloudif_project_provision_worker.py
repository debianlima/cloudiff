#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

LOG = Path('/var/log/cloudif/project-provision.log')


def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(time.strftime('%Y-%m-%dT%H:%M:%S%z') + ' ' + str(msg) + '\n')


def atomic_job(path, job):
    fd, tmp = tempfile.mkstemp(prefix='.project-job-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(job, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def set_state(path, job, status, step='', error='', result=None):
    job['status'] = status
    job['current_step'] = step
    job['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    job['last_error'] = error[:700]
    if result is not None:
        job['result'] = result
    atomic_job(path, job)


def run(cmd, timeout=180):
    log('RUN ' + ' '.join(cmd))
    p = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    log(f'RC={p.returncode}')
    if p.stdout:
        log('STDOUT ' + p.stdout[-4000:])
    if p.stderr:
        log('STDERR ' + p.stderr[-4000:])
    return p


def json_output(process, label):
    for line in reversed((process.stdout or '').splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    raise RuntimeError(label + '_invalid_json')


def require_timer(unit):
    p = run(['/bin/systemctl', 'enable', '--now', unit], 120)
    if p.returncode:
        raise RuntimeError(unit + '_enable_failed: ' + (p.stderr or p.stdout or '')[-420:])
    enabled = run(['/bin/systemctl', 'is-enabled', unit], 30)
    active = run(['/bin/systemctl', 'is-active', unit], 30)
    if enabled.returncode or enabled.stdout.strip() != 'enabled':
        raise RuntimeError(unit + '_not_enabled')
    if active.returncode or active.stdout.strip() != 'active':
        raise RuntimeError(unit + '_not_active')
    return {'unit': unit, 'enabled': True, 'active': True}


def persist_forgejo_result(slug,job):
    report_path = Path('/srv/cloudif/provisioning/projects') / slug / 'provision-report.json'
    report = json.loads(report_path.read_text())
    forgejo = (report.get('components') or {}).get('forgejo') or {}
    repo_url = str(forgejo.get('url') or '').strip()
    clone_url = str(forgejo.get('clone_url') or '').strip()
    repo_path = str(forgejo.get('repository_path') or '').strip()
    if not repo_url:
        return
    db = '/var/lib/cloudif/portal/cloudif-portal.db'
    con = sqlite3.connect(db)
    cols = {r[1] for r in con.execute('pragma table_info(projects)')}
    updates, params = [], []
    if 'repo_url' in cols:
        updates.append('repo_url=?')
        params.append(repo_url)
    if 'updated_at' in cols:
        updates.append("updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')")
    if updates:
        con.execute('update projects set ' + ','.join(updates) + ' where slug=?', params + [slug])
    icols = {r[1] for r in con.execute('pragma table_info(project_integrations)')}
    irow = con.execute('select rowid from project_integrations where project=?', (slug,)).fetchone() if 'project' in icols else None
    if irow:
        iupdates, iparams = [], []
        for col, val in (
            ('repo_url', repo_url),
            ('forgejo_repo_url', repo_url),
            ('clone_url', clone_url),
            ('repo_path', repo_path),
            ('forgejo_owner', repo_path.split('/', 1)[0] if '/' in repo_path else ''),
        ):
            if col in icols:
                iupdates.append(col + '=?')
                iparams.append(val)
        if iupdates:
            con.execute('update project_integrations set ' + ','.join(iupdates) + ' where project=?', iparams + [slug])
    con.commit()
    con.close()
    job['repo_url']=repo_url
    job['repo_clone_url'] = clone_url
    job['repo_path'] = repo_path


def verify_onboarding(slug):
    con = sqlite3.connect('/var/lib/cloudif/onboarding/onboarding.db')
    con.row_factory = sqlite3.Row
    row = con.execute(
        'select status,role_profile,environment from project_onboarding where project_slug=?',
        (slug,),
    ).fetchone()
    con.close()
    if not row or row['status'] != 'ready' or row['role_profile'] != 'project-admin' or row['environment'] != 'project':
        raise RuntimeError('onboarding_not_ready_project_admin')


def ensure_tenant_policy(job):
    tenant = str(job.get('tenant') or '').strip()
    if not tenant or str(job.get('db_mode') or '') != 'create':
        return {'ok': True, 'skipped': True, 'reason': 'tenant_not_created_by_job'}
    hours = int(job.get('tenant_keepalive_hours') or 6)
    p = run([
        '/usr/local/sbin/cloudif-tenant-policy-ensure.py',
        '--tenant', tenant,
        '--hours', str(hours),
    ], 120)
    if p.returncode:
        raise RuntimeError('tenant_availability_policy_failed: ' + (p.stderr or p.stdout or '')[-420:])
    data = json_output(p, 'tenant_availability_policy')
    if not data.get('ok') or not data.get('verified') or int(data.get('hours') or 0) != hours:
        raise RuntimeError('tenant_availability_policy_not_verified')
    return data


def ensure_backup_policy(slug):
    configured = run([
        '/usr/local/sbin/cloudif-project-backup.py','set-auto',
        '--slug', slug,
        '--enabled', '1', '--remote-requested', '1',
    ], 120)
    if configured.returncode:
        raise RuntimeError('backup_configuration_failed: ' + (configured.stderr or configured.stdout or '')[-420:])
    configured_data = json_output(configured, 'backup_configuration')
    settings = configured_data.get('settings') or {}
    if not configured_data.get('ok') or settings.get('enabled') is not True or settings.get('remote_requested') is not True:
        raise RuntimeError('backup_configuration_not_persisted')

    # Contract marker: systemctl ['enable','--now','cloudif-tenant-db-backup-v2.timer']
    timers = [
        require_timer('cloudif-project-backup-auto.timer'),
        require_timer('cloudif-tenant-db-backup-v2.timer'),
    ]

    checked = run([
        '/usr/local/sbin/cloudif-project-backup.py',
        'list', '--slug', slug,
    ], 120)
    if checked.returncode:
        raise RuntimeError('backup_policy_validation_failed: ' + (checked.stderr or checked.stdout or '')[-420:])
    checked_data = json_output(checked, 'backup_policy_validation')
    checked_settings = checked_data.get('settings') or {}
    if not checked_data.get('ok') or checked_settings.get('enabled') is not True or checked_settings.get('remote_requested') is not True:
        raise RuntimeError('backup_policy_not_verified')
    return {
        'ok': True,
        'enabled': True,
        'remote_requested': True,
        'timers': timers,
        'verified': True,
    }


def main():
    path = Path(sys.argv[1])
    job = json.loads(path.read_text())
    slug = str(job.get('slug') or '')
    lock_fd = int(os.environ.get('CLOUDIF_PROJECT_LOCK_FD', '-1'))
    if lock_fd >= 0:
        fcntl.flock(lock_fd,fcntl.LOCK_EX)
    set_state(path, job, 'running', 'provision')
    log(f'START job={path} slug={slug} tenant={job.get("tenant")}')
    result = {
        'project_slug': slug,
        'role_profile': 'project-admin',
        'provisioned': False,
    }
    try:
        candidates = [
            '/usr/local/sbin/cloudif-project-provision.sh',
            '/usr/local/sbin/cloudif-provision-project.sh',
        ]
        found = [c for c in candidates if Path(c).exists() and os.access(c, os.X_OK)]
        if not found:
            raise RuntimeError('external_provision_script_missing')
        provision_timeout = int(os.environ.get('CLOUDIF_PROJECT_PROVISION_TIMEOUT', '7200'))
        p = run([found[0], str(path)], provision_timeout)
        if p.returncode:
            detail = (p.stderr or p.stdout or '')[-420:]
            report_path = Path('/srv/cloudif/provisioning/projects') / slug / 'provision-report.json'
            try:
                report = json.loads(report_path.read_text())
                failures = []
                for name, component in (report.get('components') or {}).items():
                    if component.get('ok') is False:
                        actions = component.get('actions') or []
                        last = next((a for a in reversed(actions) if a.get('ok') is False), {})
                        failures.append(name + ': ' + str(last.get('message') or last.get('detail') or component.get('status') or 'falhou'))
                if failures:
                    detail = '; '.join(failures)[:700]
            except Exception:
                pass
            raise RuntimeError('project_provision_failed: ' + detail)

        persist_forgejo_result(slug,job)
        atomic_job(path, job)

        set_state(path,job,'running','onboarding-reconcile')
        p = run(['/bin/systemctl', 'start', 'cloudif-project-onboarding-reconcile.service'], 300)
        if p.returncode:
            raise RuntimeError('onboarding_reconcile_failed')
        verify_onboarding(slug)
        p = run(['/bin/systemctl', 'start', 'cloudif-project-capabilities.service'], 240)
        if p.returncode:
            raise RuntimeError('capabilities_reconcile_failed')

        set_state(path, job, 'running', 'tenant-availability-policy')
        result['tenant_policy'] = ensure_tenant_policy(job)

        set_state(path, job, 'running', 'backup-configuration')
        result['backup_policy'] = ensure_backup_policy(slug)

        if job.get('template_kind') in ('onboarding', 'links'):
            set_state(path, job, 'running', 'template')
            template_timeout = int(os.environ.get('CLOUDIF_PROJECT_TEMPLATE_TIMEOUT', '900'))
            p = run(['/usr/local/sbin/cloudif-project-template-apply.py', str(path)], template_timeout)
            if p.returncode:
                raise RuntimeError('template_apply_failed: ' + (p.stderr or p.stdout or '')[-420:])

            set_state(path, job, 'running', 'initial-publication')
            publication_timeout = int(os.environ.get('CLOUDIF_INITIAL_PUBLICATION_TIMEOUT', '9000'))
            p = run(['/usr/local/sbin/cloudif-project-initial-publish.py', str(path)], publication_timeout)
            if p.returncode:
                raise RuntimeError('initial_publication_failed: ' + (p.stderr or p.stdout or '')[-420:])
            result['initial_publication'] = json_output(p, 'initial_publication')

        result['provisioned'] = True
        set_state(path, job, 'succeeded', 'complete', result=result)
        log('SUCCEEDED slug=' + slug)
    except Exception as exc:
        set_state(path, job, 'failed', job.get('current_step') or 'unknown', type(exc).__name__ + ': ' + str(exc), result=result)
        log('FAILED slug=' + slug + ' ' + type(exc).__name__ + ': ' + str(exc))
        raise
    finally:
        if lock_fd >= 0:
            try:
                os.close(lock_fd)
            except OSError:
                pass


if __name__ == '__main__':
    main()
