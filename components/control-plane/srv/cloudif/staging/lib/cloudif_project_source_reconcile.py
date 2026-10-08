#!/usr/bin/env python3
"""Non-destructive reconciliation of CloudIFF project source repositories.

The portal/ACL database is authoritative for project existence and membership, while
Forgejo is authoritative for user source code.  This module only *adds* compatibility
files that are absent; it never deletes, moves or overwrites existing project files.
Legacy folders therefore remain available while projects become runnable by the current
managed-root runtime.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

FORJA_ENV = Path(os.environ.get('CLOUDIF_FORJA_CLIENT_ENV', '/etc/cloudif/forja-agent-client.env'))
STATE_ROOT = Path(os.environ.get('CLOUDIF_PROJECT_PROVISIONING_ROOT', '/srv/cloudif/provisioning/projects'))
MAX_ARCHIVE = 256 * 1024 * 1024
MAX_MIGRATED_TEXT = 1024 * 1024
TEXT_EXTENSIONS = {
    '.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.json', '.lock', '.md', '.txt',
    '.html', '.htm', '.css', '.scss', '.php', '.py', '.sh', '.yaml', '.yml', '.xml',
}
PLATFORM_FILES = {
    'docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml',
    'Dockerfile', 'Dockerfile.runtime', 'nginx.conf', 'apache-vhost.conf',
    'supervisor.conf', 'node-runner.sh', 'health.php', 'runtime.json', '.env',
}


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def read_env(path=FORJA_ENV):
    data = {}
    try:
        for raw in Path(path).read_text(errors='ignore').splitlines():
            line = raw.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                data[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return data


def _client():
    cfg = read_env()
    return (cfg.get('FORJA_AGENT_URL') or 'http://10.62.91.2:18095').rstrip('/'), cfg.get('FORJA_AGENT_TOKEN') or ''


def _headers(token, content_type=False):
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + token, 'X-CloudIF-Token': token}
    if content_type:
        headers['Content-Type'] = 'application/json'
    return headers


def _json_request(method, path, payload=None, timeout=45):
    base, token = _client()
    if not token:
        return {'ok': False, 'status': 0, 'error': 'forja_agent_token_missing'}
    data = None if payload is None else json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
    req = urllib.request.Request(base + path, data=data, method=method, headers=_headers(token, payload is not None))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            parsed = json.loads(raw or b'{}')
            return {'ok': 200 <= response.status < 300 and parsed.get('ok') is not False, 'status': response.status, 'data': parsed}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw or b'{}')
        except Exception:
            parsed = {'error': 'invalid_upstream_response'}
        return {'ok': False, 'status': exc.code, 'data': parsed}
    except Exception as exc:
        return {'ok': False, 'status': 0, 'error': type(exc).__name__}


def project_status(slug):
    return _json_request('GET', '/project/status?slug=' + urllib.parse.quote(str(slug), safe=''), timeout=30)


def fetch_archive(slug, ref='main'):
    base, token = _client()
    if not token:
        return {'ok': False, 'status': 0, 'error': 'forja_agent_token_missing'}
    query = urllib.parse.urlencode({'slug': str(slug), 'ref': str(ref)})
    req = urllib.request.Request(base + '/project/archive?' + query, headers=_headers(token))
    temporary = ''
    keep_temporary = False
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            digest = hashlib.sha256()
            total = 0
            fd, temporary = tempfile.mkstemp(prefix='cloudif-source-', suffix='.tar.gz')
            with os.fdopen(fd, 'wb') as stream:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_ARCHIVE:
                        return {'ok': False, 'status': 413, 'error': 'archive_too_large', 'bytes_read': total}
                    digest.update(chunk)
                    stream.write(chunk)
                stream.flush(); os.fsync(stream.fileno())
            keep_temporary = True
            return {
                'ok': response.status == 200,
                'status': response.status,
                'archive_path': temporary,
                'size': total,
                'sha256': digest.hexdigest(),
            }
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read() or b'{}')
        except Exception:
            detail = {}
        return {'ok': False, 'status': exc.code, 'data': detail}
    except Exception as exc:
        return {'ok': False, 'status': 0, 'error': type(exc).__name__}
    finally:
        if temporary and not keep_temporary:
            try: os.unlink(temporary)
            except FileNotFoundError: pass


def _normal_name(name, root_prefix=''):
    name = str(name or '').replace('\\', '/').lstrip('./')
    if root_prefix and name.startswith(root_prefix + '/'):
        name = name[len(root_prefix) + 1:]
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts:
        return ''
    return str(path)


def inspect_archive(source):
    """Return repository paths and bounded text contents from a streamed Forgejo tarball."""
    paths = set()
    text = {}
    if isinstance(source, (str, os.PathLike)):
        archive_ctx = tarfile.open(name=str(source), mode='r:gz')
    else:
        archive_ctx = tarfile.open(fileobj=io.BytesIO(source), mode='r:gz')
    with archive_ctx as archive:
        members = [member for member in archive.getmembers() if member.isfile()]
        first_parts = [PurePosixPath(member.name).parts[0] for member in members if PurePosixPath(member.name).parts]
        root_prefix = first_parts[0] if first_parts and all(part == first_parts[0] for part in first_parts) else ''
        for member in members:
            name = _normal_name(member.name, root_prefix)
            if not name:
                continue
            paths.add(name)
            wanted = (
                name in {'site/index.html', 'site/index.php'}
                or name.startswith('site/api/')
                or name in {'README.md', 'index.html', 'index.php'}
            )
            if not wanted or member.size > MAX_MIGRATED_TEXT:
                continue
            suffix = PurePosixPath(name).suffix.lower()
            if name.startswith('site/api/') and suffix not in TEXT_EXTENSIONS and PurePosixPath(name).name not in {'package.json', 'package-lock.json'}:
                continue
            fileobj = archive.extractfile(member)
            if not fileobj:
                continue
            blob = fileobj.read(MAX_MIGRATED_TEXT + 1)
            if len(blob) > MAX_MIGRATED_TEXT or b'\x00' in blob:
                continue
            try:
                text[name] = blob.decode('utf-8')
            except UnicodeDecodeError:
                continue
    return {'paths': paths, 'text': text}


def repository_snapshot(slug, ref='main'):
    archive = fetch_archive(slug, ref)
    if not archive.get('ok'):
        waiting = archive.get('status') in {404, 409, 425, 503}
        return {'ok': False, 'waiting': waiting, 'status': archive.get('status', 0), 'error': archive.get('error') or (archive.get('data') or {}).get('error') or 'archive_unavailable'}
    archive_path = archive.get('archive_path')
    try:
        inspected = inspect_archive(archive_path if archive_path else archive.get('raw', b''))
    except Exception as exc:
        return {'ok': False, 'waiting': False, 'status': 502, 'error': 'invalid_repository_archive', 'error_type': type(exc).__name__}
    finally:
        if archive_path:
            try: os.unlink(archive_path)
            except FileNotFoundError: pass
    return {'ok': True, 'waiting': False, 'status': 200, 'sha256': archive.get('sha256', ''), 'archive_size': archive.get('size', 0), **inspected}


def _redirect_index(slug):
    safe_slug = ''.join(ch for ch in str(slug) if ch.isalnum() or ch in '-_.')
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_slug} · compatibilidade CloudIFF</title>
<meta http-equiv="refresh" content="0; url=site/"><script>location.replace('site/'+location.search+location.hash)</script>
</head><body><p>Estrutura legada preservada. <a href="site/">Abrir aplicação</a>.</p></body></html>
'''


def _minimal_readme(slug, legacy=False):
    legacy_note = '\nA pasta `site/` é legada e foi preservada. A raiz contém somente a ponte de compatibilidade necessária ao runtime atual.\n' if legacy else ''
    return f'''# {slug}

Projeto CloudIFF reconciliado para o runtime gerenciado atual.{legacy_note}

## Estrutura suportada

- a raiz do repositório é a raiz lógica da aplicação;
- `api/server.js` pode fornecer a API Node.js opcional;
- Docker/Compose/Apache/Supervisor e segredos são gerados pela CloudIFF fora do Git;
- diretórios legados são mantidos e nunca removidos pela reconciliação automática.

> A reconciliação automática somente adiciona arquivos ausentes; código existente não é sobrescrito.
'''


def plan_snapshot(slug, snapshot):
    paths = set(snapshot.get('paths') or set())
    text = dict(snapshot.get('text') or {})
    legacy_site = any(path == 'site' or path.startswith('site/') for path in paths)
    root_entry = next((name for name in ('index.php', 'index.html') if name in paths), '')
    legacy_entry = next((name for name in ('site/index.php', 'site/index.html') if name in paths), '')
    actions = []
    skipped = []
    warnings = []

    # Current runtime serves repository root.  Keep site/ intact and add a root bridge only when needed.
    if not root_entry and legacy_entry:
        actions.append({'path': 'index.html', 'content': _redirect_index(slug), 'reason': 'legacy_site_root_bridge'})
    elif not root_entry and not legacy_entry:
        warnings.append('entrypoint_missing')

    # The managed runtime looks for api/ at repository root.  Copy only absent UTF-8 API source files.
    for source in sorted(path for path in paths if path.startswith('site/api/') and path in text):
        rel = source[len('site/') :]
        if rel in paths:
            skipped.append({'path': rel, 'reason': 'current_target_exists'})
            continue
        if PurePosixPath(rel).name.startswith('.env'):
            skipped.append({'path': rel, 'reason': 'secret_like_file_not_migrated'})
            continue
        actions.append({'path': rel, 'content': text[source], 'reason': 'legacy_api_copy', 'source_path': source})

    if 'README.md' not in paths:
        actions.append({'path': 'README.md', 'content': _minimal_readme(slug, legacy_site), 'reason': 'readme_missing'})

    legacy_platform = sorted(path for path in paths if PurePosixPath(path).name in PLATFORM_FILES or path.startswith('.cloudif/'))
    legacy_paths = sorted({path.split('/', 1)[0] + '/' for path in paths if '/' in path and path.split('/', 1)[0] in {'site', '.cloudif'}})
    layout = 'managed-root-v1' if root_entry else ('legacy-site-v1' if legacy_entry else 'unknown')
    return {
        'project': slug,
        'layout_before': layout,
        'legacy_site': legacy_site,
        'legacy_paths_preserved': legacy_paths,
        'legacy_platform_files_preserved': legacy_platform,
        'actions': actions,
        'skipped': skipped,
        'warnings': warnings,
        'destructive_actions': 0,
    }


def _repo_mapping(status, slug):
    data = status.get('data') if isinstance(status.get('data'), dict) else {}
    project = data.get('project') if isinstance(data.get('project'), dict) else {}
    forgejo = project.get('forgejo') if isinstance(project.get('forgejo'), dict) else {}
    owner = str(forgejo.get('owner') or project.get('forgejo_owner') or '').strip()
    repo = str(forgejo.get('repo') or '').strip()
    if '/' in repo:
        repo_owner, repo_name = repo.split('/', 1)
        owner = repo_owner or owner
        repo = repo_name
    return owner, repo or ('cloudif-' + str(slug))


def commit_text(slug, owner, repo, path, content, reason):
    payload = {
        'project_slug': slug,
        'owner': owner,
        'repo_owner': owner,
        'repo': repo,
        'repo_path': f'{owner}/{repo}',
        'path': path,
        'branch': 'main',
        'message': f'CloudIFF: reconciliar estrutura ({reason})',
        'source': 'project-source-reconcile',
        'content_b64': base64.b64encode(content.encode('utf-8')).decode('ascii'),
    }
    return _json_request('POST', '/project/file/commit', payload, timeout=120)


def _write_state(slug, report):
    try:
        directory = STATE_ROOT / str(slug)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / 'source-reconcile.json'
        descriptor, temporary = tempfile.mkstemp(prefix='.source-reconcile-', dir=str(directory))
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
                stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
            os.chmod(temporary, 0o600); os.replace(temporary, target)
        finally:
            try: os.unlink(temporary)
            except FileNotFoundError: pass
        report['state_file'] = str(target)
    except Exception as exc:
        report['state_write_error'] = type(exc).__name__
    return report


def reconcile_project(slug, apply=True):
    slug = str(slug or '').strip().lower()
    status = project_status(slug)
    if not status.get('ok'):
        waiting = status.get('status') in {404, 409, 425, 503}
        return _write_state(slug, {'ok': waiting, 'waiting': waiting, 'project': slug, 'generated_at': now(), 'error': 'project_status_unavailable', 'status': status.get('status', 0)})
    snapshot = repository_snapshot(slug)
    if not snapshot.get('ok'):
        return _write_state(slug, {'ok': bool(snapshot.get('waiting')), 'waiting': bool(snapshot.get('waiting')), 'project': slug, 'generated_at': now(), 'error': snapshot.get('error'), 'status': snapshot.get('status', 0)})

    plan = plan_snapshot(slug, snapshot)
    owner, repo = _repo_mapping(status, slug)
    report = {
        'ok': True,
        'waiting': False,
        'project': slug,
        'repo_owner': owner,
        'repo': repo,
        'generated_at': now(),
        'archive_sha256': snapshot.get('sha256', ''),
        'apply': bool(apply),
        **{k: v for k, v in plan.items() if k != 'project'},
        'applied': [],
        'failures': [],
    }
    if not owner:
        report.update({'ok': False, 'waiting': True, 'error': 'repo_owner_unresolved'})
        return _write_state(slug, report)

    if apply:
        for action in plan['actions']:
            result = commit_text(slug, owner, repo, action['path'], action['content'], action['reason'])
            if result.get('ok'):
                data = result.get('data') if isinstance(result.get('data'), dict) else {}
                report['applied'].append({'path': action['path'], 'reason': action['reason'], 'commit_sha': data.get('commit_sha', '')})
            else:
                report['failures'].append({'path': action['path'], 'reason': action['reason'], 'status': result.get('status', 0), 'error': result.get('error') or ((result.get('data') or {}).get('error') if isinstance(result.get('data'), dict) else '')})
        report['ok'] = not report['failures']
    report['changed'] = bool(report['applied'])
    report['planned_changes'] = len(plan['actions'])
    return _write_state(slug, report)
