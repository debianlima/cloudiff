#!/usr/bin/env python3
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

ONBOARDING_DB = '/var/lib/cloudif/onboarding/onboarding.db'
PORTAL_DB = '/var/lib/cloudif/portal/cloudif-portal.db'
OUTPUT = '/var/lib/cloudif/health/project-state-reconcile.json'
LOCK = '/run/lock/cloudif-project-state-reconcile.lock'
AGENT_REPORT = '/var/lib/cloudif/health/agent-controller.json'
CAP_REPORT = '/var/lib/cloudif/health/project-capabilities-v2.json'
JOB_DIR = '/srv/cloudif/jobs'
JOB_RETENTION_SECONDS = 7 * 24 * 3600
SOURCES = (
    '/srv/cloudif/app-pointers/agent-controller-current/cloudif-agent-controller.py',
    '/srv/cloudif/app-pointers/project-capabilities-current/cloudif-project-capabilities.py',
    '/srv/cloudif/app-pointers/agent-registry-current/cloudif-agent-registry.py',
    '/srv/cloudif/app-pointers/mcp-gateway-current/cloudif-mcp-gateway.py',
    '/etc/cloudif/project-capabilities-policy.json',
)


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def load_json(path, default=None):
    try:
        with open(path, encoding='utf-8') as stream:
            return json.load(stream)
    except Exception:
        return {} if default is None else default


def load_json_text(raw):
    try:
        value = json.loads(raw or '{}')
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def sha_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def atomic_write(path, data, mode=0o600):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.state-', dir=directory)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, separators=(',', ':'))
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def onboarding_rows():
    connection = sqlite3.connect(f'file:{ONBOARDING_DB}?mode=ro', uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        columns = {row[1] for row in connection.execute('pragma table_info(project_onboarding)')}
        wanted = ['project_slug', 'client_id', 'owner_user', 'tenant', 'role_profile', 'environment', 'rate_per_minute', 'daily_quota', 'status', 'scopes_json', 'connectors_json']
        selected = [name for name in wanted if name in columns]
        return [dict(row) for row in connection.execute('select ' + ','.join(selected) + ' from project_onboarding order by project_slug')]
    finally:
        connection.close()


def portal_slugs():
    connection = sqlite3.connect(f'file:{PORTAL_DB}?mode=ro', uri=True, timeout=10)
    try:
        return {str(row[0]) for row in connection.execute("select slug from projects where trim(slug)<>''")}
    finally:
        connection.close()


def source_state(rows):
    portal = portal_slugs()
    onboarding = {str(row.get('project_slug') or '') for row in rows}
    onboarding.discard('')
    return portal, sorted(onboarding - portal), sorted(portal - onboarding)


def fingerprint(rows):
    portal, orphans, missing = source_state(rows)
    payload = {
        'projects': rows,
        'portal_projects': sorted(portal),
        'onboarding_orphans': orphans,
        'onboarding_missing': missing,
        'sources': {path: sha_file(path) for path in SOURCES if os.path.isfile(path)},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest(), payload['sources']



def reconcile_jobs(portal_projects):
    directory = Path(JOB_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    now_epoch = time.time()
    grouped = {}
    removed = []
    kept = []
    for path in directory.glob('project-provision-*.json'):
        try:
            job = load_json(path, {})
            slug = str(job.get('slug') or '')
            status = str(job.get('status') or 'unknown')
            updated = path.stat().st_mtime
            grouped.setdefault(slug, []).append((updated, path, status))
        except Exception as exc:
            removed.append({'path': path.name, 'reason': 'invalid_job', 'error': type(exc).__name__})
            try: path.unlink()
            except FileNotFoundError: pass
    for slug, items in grouped.items():
        items.sort(reverse=True)
        if not slug or slug not in portal_projects:
            for _, path, status in items:
                try: path.unlink()
                except FileNotFoundError: pass
                removed.append({'path': path.name, 'project_slug': slug, 'status': status, 'reason': 'orphan_project'})
            continue
        active = [item for item in items if item[2] in ('queued', 'running')]
        completed = [item for item in items if item[2] not in ('queued', 'running')]
        for index, (updated, path, status) in enumerate(active):
            if index == 0:
                kept.append({'path': path.name, 'project_slug': slug, 'status': status, 'reason': 'active_latest'})
            elif now_epoch - updated > 3600:
                try: path.unlink()
                except FileNotFoundError: pass
                removed.append({'path': path.name, 'project_slug': slug, 'status': status, 'reason': 'stale_duplicate_active'})
            else:
                kept.append({'path': path.name, 'project_slug': slug, 'status': status, 'reason': 'recent_duplicate_active'})
        for index, (updated, path, status) in enumerate(completed):
            if index == 0:
                kept.append({'path': path.name, 'project_slug': slug, 'status': status, 'reason': 'latest_history'})
            elif now_epoch - updated > JOB_RETENTION_SECONDS:
                try: path.unlink()
                except FileNotFoundError: pass
                removed.append({'path': path.name, 'project_slug': slug, 'status': status, 'reason': 'expired_history'})
            else:
                kept.append({'path': path.name, 'project_slug': slug, 'status': status, 'reason': 'retained_history'})
    return {'ok': True, 'removed': removed, 'kept': kept, 'removed_count': len(removed), 'kept_count': len(kept)}

def parallel_reconcile():
    units = ('cloudif-project-capabilities.service', 'cloudif-agent-controller.service')
    processes = []
    started = {}
    for unit in units:
        started[unit] = time.monotonic()
        processes.append((unit, subprocess.Popen(['/bin/systemctl', 'start', unit], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)))
    results = []
    for unit, process in processes:
        try:
            _, stderr = process.communicate(timeout=180)
        except subprocess.TimeoutExpired:
            process.kill()
            _, stderr = process.communicate()
            process.returncode = 124
        state = subprocess.run(['/bin/systemctl', 'show', unit, '-p', 'Result', '--value'], text=True, capture_output=True, timeout=10).stdout.strip()
        results.append({
            'unit': unit,
            'ok': process.returncode == 0 and state in ('success', ''),
            'result': state or 'unknown',
            'duration_ms': round((time.monotonic() - started[unit]) * 1000),
            'stderr': stderr.strip()[:240] if process.returncode else '',
        })
    return results


def build_report(rows, fingerprint_value, sources, components, changed, job_reconciliation):
    portal, orphans, missing = source_state(rows)
    active_rows = [row for row in rows if str(row.get('project_slug') or '') in portal]
    agent = load_json(AGENT_REPORT)
    capabilities = load_json(CAP_REPORT)
    agent_map = {item.get('project_slug'): item for item in agent.get('results') or []}
    capability_map = {item.get('project_slug'): item for item in capabilities.get('projects') or []}
    projects = []
    catalog_tools = int(capabilities.get('catalog_tools') or 0)
    for row in active_rows:
        slug = row.get('project_slug')
        agent_state = agent_map.get(slug, {})
        capability_state = capability_map.get(slug, {})
        connectors = load_json_text(row.get('connectors_json'))
        connector_states = {key: (value.get('status') if isinstance(value, dict) else str(value)) for key, value in connectors.items()}
        onboarding_ok = row.get('status') == 'ready'
        agent_ok = agent_state.get('status') in ('aligned', 'corrected')
        capability_ok = capability_state.get('scope_match') is True and int(capability_state.get('tool_count') or 0) == catalog_tools
        projects.append({
            'project_slug': slug,
            'client_id': row.get('client_id'),
            'onboarding': 'ready' if onboarding_ok else row.get('status') or 'unknown',
            'agent': 'aligned' if agent_ok else agent_state.get('status') or 'missing',
            'capabilities': 'aligned' if capability_ok else 'drift',
            'tool_count': int(capability_state.get('tool_count') or 0),
            'connectors': connector_states,
            'overall': 'ready' if onboarding_ok and agent_ok and capability_ok else 'attention',
            'token_rotated': False,
        })
    components_ok = all(component.get('ok') for component in components)
    state_ok = all(project['overall'] == 'ready' for project in projects)
    security_ok = agent.get('tokens_rotated') == 0 and agent.get('tokens_returned') == 0 and capabilities.get('effects_executed') is False
    all_ok = components_ok and state_ok and security_ok and not orphans and not missing
    previous = load_json(OUTPUT)
    return {
        'ok': all_ok,
        'generated_at': now(),
        'last_success_at': now() if all_ok else previous.get('last_success_at'),
        'fingerprint': fingerprint_value,
        'changed': changed,
        'execution_mode': 'parallel',
        'source_of_truth': 'portal',
        'components': components,
        'job_reconciliation': job_reconciliation,
        'projects_count': len(projects),
        'projects_ready': sum(1 for project in projects if project['overall'] == 'ready'),
        'agents_aligned': sum(1 for project in projects if project['agent'] == 'aligned'),
        'capabilities_aligned': sum(1 for project in projects if project['capabilities'] == 'aligned'),
        'catalog_tools': catalog_tools,
        'onboarding_orphans': orphans,
        'onboarding_missing': missing,
        'blockers': ([{'kind': 'onboarding_orphan', 'project_slug': slug} for slug in orphans] + [{'kind': 'onboarding_missing', 'project_slug': slug} for slug in missing]),
        'future_project_template': {
            'automatic_onboarding': True,
            'automatic_agent_identity': True,
            'automatic_capabilities': True,
            'default_role_profile': 'project-admin',
            'default_environment': 'project',
            'production_effects_enabled': False,
        },
        'sources': sources,
        'projects': projects,
        'tokens_rotated': 0,
        'tokens_returned': 0,
        'effects_executed': False,
        'secrets_exposed': False,
    }


def main(force=False):
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    with open(LOCK, 'w', encoding='utf-8') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'ok': True, 'changed': False, 'execution_mode': 'locked', 'message': 'reconciliation already running'}, separators=(',', ':')))
            return 0
        rows = onboarding_rows()
        fingerprint_value, sources = fingerprint(rows)
        previous = load_json(OUTPUT)
        portal, orphans, missing = source_state(rows)
        if not force and previous.get('ok') is True and previous.get('fingerprint') == fingerprint_value and not orphans and not missing:
            job_reconciliation = reconcile_jobs(portal)
            previous['generated_at'] = now()
            previous['changed'] = bool(job_reconciliation.get('removed_count'))
            previous['execution_mode'] = 'maintenance' if previous['changed'] else 'noop'
            previous['last_checked_at'] = previous['generated_at']
            previous['job_reconciliation'] = job_reconciliation
            atomic_write(OUTPUT, previous)
            print(json.dumps({'ok': True, 'changed': previous['changed'], 'projects': len(portal), 'fingerprint': fingerprint_value, 'execution_mode': previous['execution_mode'], 'job_reconciliation': job_reconciliation, 'tokens_rotated': 0}, separators=(',', ':')))
            return 0
        job_reconciliation = reconcile_jobs(portal)
        components = parallel_reconcile()
        report = build_report(rows, fingerprint_value, sources, components, True, job_reconciliation)
        atomic_write(OUTPUT, report)
        print(json.dumps({'ok': report['ok'], 'changed': True, 'projects': report['projects_count'], 'ready': report['projects_ready'], 'onboarding_orphans': orphans, 'onboarding_missing': missing, 'components': components, 'tokens_rotated': 0}, separators=(',', ':')))
        return 0 if report['ok'] else 1


def selftest():
    rows = onboarding_rows()
    fingerprint_value, sources = fingerprint(rows)
    assert len(fingerprint_value) == 64
    assert all('project_slug' in row for row in rows)
    print(json.dumps({'ok': True, 'projects': len(rows), 'fingerprint_length': len(fingerprint_value), 'source_count': len(sources), 'parallel_components': 2, 'tokens_rotated': 0, 'effects_executed': False}, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--selftest', action='store_true')
    arguments = parser.parse_args()
    raise SystemExit(selftest() if arguments.selftest else main(arguments.force))
