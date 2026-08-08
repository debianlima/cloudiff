#!/usr/bin/env python3
import hashlib
import difflib
import hmac
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import yaml
from cloudif_multitech_detector import detect_components
from cloudif_change_set import (ChangeSetError, apply_changes, change_set_digest, clean_expired, load_sealed, normalize_changes, seal_change_set)
from cloudif_workspace_artifact import (ArtifactError, append_chunk, complete_artifact, read_artifact, resolve_artifact, start_artifact)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

TOKEN = os.environ['CLOUDIF_WORKSPACE_TOKEN']
HOST = os.environ.get('CLOUDIF_WORKSPACE_HOST', '127.0.0.1')
PORT = int(os.environ.get('CLOUDIF_WORKSPACE_PORT', '18206'))
IMAGE = os.environ.get('CLOUDIF_WORKSPACE_IMAGE', 'nginx@sha256:5f979dcfed4ce6461873f087e8c980d6e29b084b9e8776d9704a7e989b5f4898')
FORJA_URL = os.environ.get('CLOUDIF_FORJA_AGENT_URL', 'http://10.62.91.2:18095').rstrip('/')
FORJA_TOKEN = os.environ.get('CLOUDIF_FORJA_AGENT_TOKEN', '')
WORKROOT = os.environ.get('CLOUDIF_WORKSPACE_ROOT', '/var/lib/cloudif/workspaces')
ARTIFACT_ROOT = os.environ.get('CLOUDIF_WORKSPACE_ARTIFACT_ROOT', '/var/lib/cloudif/workspace-artifacts')
CHANGESET_ROOT = os.environ.get('CLOUDIF_WORKSPACE_CHANGESET_ROOT', '/var/lib/cloudif/workspace-change-sets')
PROJECT_CONFIG_URL = os.environ.get('CLOUDIF_PROJECT_CONFIG_URL', 'http://127.0.0.1:18219').rstrip('/')
PROJECT_CONFIG_TOKEN = os.environ.get('CLOUDIF_PROJECT_CONFIG_TOKEN', '')
SLUG = re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
TRACE = re.compile(r'^[A-Za-z0-9._:-]{1,128}$')
REF = re.compile(r'^[A-Za-z0-9._/-]{1,128}$')
ARCHIVE_MAX = 20 * 1024 * 1024
UNPACK_MAX = 50 * 1024 * 1024
FILE_MAX = 10 * 1024 * 1024
ENTRY_MAX = 5000

PROBE_SCRIPT = r'''set -eu
uid=$(id -u)
cap=$(awk '/^CapEff:/{print $2}' /proc/self/status)
if [ -e /var/run/docker.sock ];then ds=present;else ds=absent;fi
if touch /etc/cloudif-probe 2>/dev/null;then rw=allowed;else rw=denied;fi
if touch /tmp/cloudif-probe 2>/dev/null;then tw=ok;else tw=denied;fi
if wget -q -T 1 -O /tmp/net http://1.1.1.1 2>/dev/null;then net=available;else net=none;fi
printf 'uid=%s\ncap_eff=%s\ndocker_socket=%s\nroot_write=%s\ntmp_write=%s\nnetwork=%s\n' "$uid" "$cap" "$ds" "$rw" "$tw" "$net"
'''

PREVIEW_SCRIPT = r'''set -eu
nginx -g 'daemon off;' >/tmp/nginx-runtime.log 2>&1 &
pid=$!
cleanup(){ kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; }
trap cleanup EXIT
index_ok=0
for i in $(seq 1 40); do
  if wget -q -S -O /tmp/index.body http://127.0.0.1/ 2>/tmp/index.headers; then index_ok=1; break; fi
  sleep 0.1
done
health_ok=0
if wget -q -S -O /tmp/health.body http://127.0.0.1/health 2>/tmp/health.headers; then health_ok=1; fi
uid=$(id -u)
if [ -e /var/run/docker.sock ];then ds=present;else ds=absent;fi
if wget -q -T 1 -O /tmp/external http://1.1.1.1 2>/dev/null;then net=available;else net=none;fi
index_type=$(grep -i '^[[:space:]]*Content-Type:' /tmp/index.headers 2>/dev/null | head -n1 | sed -E 's/^[[:space:]]*[Cc]ontent-[Tt]ype:[[:space:]]*//;s/\r$//' || true)
health_type=$(grep -i '^[[:space:]]*Content-Type:' /tmp/health.headers 2>/dev/null | head -n1 | sed -E 's/^[[:space:]]*[Cc]ontent-[Tt]ype:[[:space:]]*//;s/\r$//' || true)
index_bytes=$(wc -c </tmp/index.body 2>/dev/null | tr -d ' ' || echo 0)
health_bytes=$(wc -c </tmp/health.body 2>/dev/null | tr -d ' ' || echo 0)
meaningful=0
if grep -Eiq '<!doctype|<html' /tmp/index.body 2>/dev/null && ! grep -Eiq 'Welcome to nginx' /tmp/index.body 2>/dev/null;then meaningful=1;fi
printf 'uid=%s
docker_socket=%s
network=%s
index_ok=%s
health_ok=%s
index_type=%s
health_type=%s
index_bytes=%s
health_bytes=%s
meaningful=%s
---INDEX---
' "$uid" "$ds" "$net" "$index_ok" "$health_ok" "$index_type" "$health_type" "$index_bytes" "$health_bytes" "$meaningful"
head -c 1024 /tmp/index.body 2>/dev/null || true
printf '
---HEALTH---
'
head -c 512 /tmp/health.body 2>/dev/null || true
printf '
---LOG---
'
head -c 2048 /tmp/nginx-runtime.log 2>/dev/null || true
'''

STATIC_TEST_SCRIPT = r'''set -eu
uid=$(id -u)
if [ -e /var/run/docker.sock ];then ds=present;else ds=absent;fi
if wget -q -T 1 -O /tmp/net http://1.1.1.1 2>/dev/null;then net=available;else net=none;fi
set +e
nginx -t >/tmp/nginx-test.out 2>&1
rc=$?
set -e
printf 'uid=%s\ndocker_socket=%s\nnetwork=%s\nnginx_rc=%s\n---OUTPUT---\n' "$uid" "$ds" "$net" "$rc"
head -c 4000 /tmp/nginx-test.out
exit 0
'''

PREPARE_SCRIPT = r'''set -eu
uid=$(id -u)
count=$(find /workspace -type f | wc -l | tr -d ' ')
if touch /workspace/.cloudif-write-probe 2>/dev/null;then ww=writable;rm -f /workspace/.cloudif-write-probe;else ww=readonly;fi
if [ -e /var/run/docker.sock ];then ds=present;else ds=absent;fi
if wget -q -T 1 -O /tmp/net http://1.1.1.1 2>/dev/null;then net=available;else net=none;fi
printf 'uid=%s\nfile_count=%s\nworkspace_write=%s\ndocker_socket=%s\nnetwork=%s\n' "$uid" "$count" "$ww" "$ds" "$net"
'''


def docker(*args: str, timeout: int = 12) -> str:
    p = subprocess.run(['/usr/bin/docker', *args], text=True, capture_output=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or 'docker_error')[:300])
    return p.stdout


def base_container_args(name: str, slug: str, trace: str) -> list[str]:
    return [
        'create', '--name', name,
        '--network', 'none', '--read-only',
        '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=16m',
        '--user', '65534:65534', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--pids-limit', '64',
        '--memory', '128m', '--memory-swap', '128m', '--cpus', '0.25',
        '--ulimit', 'nofile=64:64', '--ulimit', 'nproc=64:64',
        '--hostname', 'workspace',
        '--label', 'cloudif.managed=true', '--label', 'cloudif.project=' + slug,
        '--label', 'cloudif.trace=' + trace,
    ]


def probe(slug: str, trace: str) -> tuple[dict, str]:
    name = 'cloudif-ws-' + uuid.uuid4().hex[:18]
    created = False
    try:
        cid = docker(*base_container_args(name, slug, trace), '--tmpfs', '/work:rw,nosuid,nodev,size=32m', IMAGE, '/bin/sh', '-c', PROBE_SCRIPT).strip()
        created = True
        inspect = json.loads(docker('inspect', cid))[0]
        try:
            out = docker('start', '-a', cid, timeout=8)
        except subprocess.TimeoutExpired:
            subprocess.run(['/usr/bin/docker', 'kill', cid], capture_output=True, timeout=3)
            raise RuntimeError('workspace_timeout')
        values = {}
        for line in out.splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                values[k] = v
        values['memory_limit_bytes'] = int(inspect['HostConfig']['Memory'])
        values['pids_limit'] = int(inspect['HostConfig']['PidsLimit'] or 0)
        return values, name
    finally:
        if created:
            subprocess.run(['/usr/bin/docker', 'rm', '-f', name], capture_output=True, timeout=5)


def fetch_archive(slug: str, ref: str) -> tuple[bytes, str]:
    query = urllib.parse.urlencode({'slug': slug, 'ref': ref})
    req = urllib.request.Request(
        FORJA_URL + '/project/archive?' + query,
        headers={
            'X-CloudIF-Token': FORJA_TOKEN,
            'Authorization': 'Bearer ' + FORJA_TOKEN,
            'Accept': 'application/gzip',
            'User-Agent': 'cloudif-workspace-broker/prepare',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            raw = response.read(ARCHIVE_MAX + 1)
            upstream_sha = (response.headers.get('X-CloudIF-SHA256') or '').strip().lower()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise FileNotFoundError('project_or_ref_not_found') from e
        raise RuntimeError('archive_upstream_error') from e
    if len(raw) > ARCHIVE_MAX:
        raise ValueError('archive_too_large')
    if raw[:2] != b'\x1f\x8b':
        raise ValueError('invalid_archive')
    digest = hashlib.sha256(raw).hexdigest()
    if upstream_sha and not hmac.compare_digest(upstream_sha, digest):
        raise ValueError('archive_hash_mismatch')
    return raw, digest


def safe_extract(raw: bytes, dest: str) -> tuple[list[str], int]:
    os.makedirs(dest, exist_ok=True)
    os.chmod(dest, 0o755)
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        members = archive.getmembers()
        if not members or len(members) > ENTRY_MAX:
            raise ValueError('invalid_entry_count')
        split_names: list[list[str]] = []
        for member in members:
            name = member.name.replace('\\', '/')
            parts = [x for x in name.split('/') if x not in ('', '.')]
            if (
                name.startswith('/') or '..' in parts or not parts or len(name) > 240
                or member.isdev() or member.issym() or member.islnk()
            ):
                raise ValueError('unsafe_archive_entry')
            split_names.append(parts)
        prefix = split_names[0][0] if all(parts and parts[0] == split_names[0][0] for parts in split_names) else ''
        files: list[str] = []
        total = 0
        root = os.path.realpath(dest)
        for member, parts in zip(members, split_names):
            rel_parts = parts[1:] if prefix and parts[0] == prefix else parts
            if not rel_parts:
                continue
            rel = '/'.join(rel_parts)
            target = os.path.realpath(os.path.join(dest, *rel_parts))
            if target != root and not target.startswith(root + os.sep):
                raise ValueError('archive_escape')
            if member.isdir():
                os.makedirs(target, exist_ok=True)
                os.chmod(target, 0o755)
                continue
            if not member.isfile():
                raise ValueError('unsupported_archive_entry')
            if member.size < 0 or member.size > FILE_MAX:
                raise ValueError('file_too_large')
            total += member.size
            if total > UNPACK_MAX:
                raise ValueError('archive_unpacked_too_large')
            os.makedirs(os.path.dirname(target), exist_ok=True)
            src = archive.extractfile(member)
            if src is None:
                raise ValueError('archive_read_error')
            with src, open(target, 'wb') as out:
                shutil.copyfileobj(src, out, 1024 * 1024)
            os.chmod(target, 0o644)
            files.append(rel)
        return sorted(files), total


def detect_technologies(files: list[str]) -> list[str]:
    names = set(files)
    basenames = {os.path.basename(x) for x in files}
    technologies: list[str] = []
    checks = [
        ('node', 'package.json'), ('python', 'pyproject.toml'), ('python', 'requirements.txt'),
        ('python', 'setup.py'), ('docker', 'Dockerfile'), ('docker-compose', 'docker-compose.yml'),
        ('docker-compose', 'compose.yml'), ('supabase', 'supabase/config.toml'),
        ('php', 'composer.json'), ('java', 'pom.xml'), ('java', 'build.gradle'),
    ]
    for label, marker in checks:
        if marker in names or marker in basenames:
            if label not in technologies:
                technologies.append(label)
    return technologies


def prepare_workspace(slug: str, ref: str, trace: str) -> tuple[dict, str, str]:
    os.makedirs(WORKROOT, exist_ok=True)
    run_dir = tempfile.mkdtemp(prefix='prepare-', dir=WORKROOT)
    name = 'cloudif-ws-' + uuid.uuid4().hex[:18]
    created = False
    try:
        raw, digest = fetch_archive(slug, ref)
        files, total = safe_extract(raw, run_dir)
        cid = docker(
            *base_container_args(name, slug, trace),
            '--mount', f'type=bind,src={run_dir},dst=/workspace,readonly',
            IMAGE, '/bin/sh', '-c', PREPARE_SCRIPT,
        ).strip()
        created = True
        inspect = json.loads(docker('inspect', cid))[0]
        out = docker('start', '-a', cid, timeout=10)
        values = {}
        for line in out.splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                values[k] = v
        return {
            'archive_sha256': digest,
            'archive_bytes': len(raw),
            'file_count': len(files),
            'total_bytes': total,
            'paths': files[:200],
            'paths_truncated': len(files) > 200,
            'technologies': detect_technologies(files),
            'container': values,
            'memory_limit_bytes': int(inspect['HostConfig']['Memory']),
            'pids_limit': int(inspect['HostConfig']['PidsLimit'] or 0),
        }, name, run_dir
    finally:
        if created:
            subprocess.run(['/usr/bin/docker', 'rm', '-f', name], capture_output=True, timeout=5)
        shutil.rmtree(run_dir, ignore_errors=True)


def project_config_validate(manifest_text: str) -> tuple[int, dict]:
    raw = json.dumps({'manifest': manifest_text}, ensure_ascii=False, separators=(',', ':')).encode()
    request = urllib.request.Request(
        PROJECT_CONFIG_URL + '/v1/manifest/validate', data=raw, method='POST',
        headers={'Authorization': 'Bearer ' + PROJECT_CONFIG_TOKEN, 'Content-Type': 'application/json', 'Accept': 'application/json'},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.load(error)
        except Exception:
            return error.code, {'ok': False, 'error': {'code': 'manifest_validation_unavailable'}}


def workspace_files(root: str) -> list[str]:
    files = []
    for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
        dirs[:] = [name for name in dirs if not os.path.islink(os.path.join(current, name))]
        for name in names:
            path = os.path.join(current, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            files.append(os.path.relpath(path, root).replace(os.sep, '/'))
    return sorted(files)


def validate_result_manifest(run_dir: str, files: list[str]) -> dict:
    manifest_path = 'cloudiff.yaml' if 'cloudiff.yaml' in files else 'cloudiff.yml' if 'cloudiff.yml' in files else ''
    if not manifest_path:
        return {'present': False, 'valid': None, 'requiredBeforeMultiserviceBuild': True}
    text = open(os.path.join(run_dir, manifest_path), encoding='utf-8').read()
    status, result = project_config_validate(text)
    if status == 422:
        raise ChangeSetError('manifest_validation_failed', 'O cloudiff.yaml resultante é inválido.', manifest_path, result.get('error'))
    if status != 200 or not result.get('valid'):
        raise RuntimeError('manifest_validator_unavailable')
    return {
        'present': True, 'path': manifest_path, 'valid': True,
        'manifestDigest': result.get('manifestDigest'), 'configDigest': result.get('configDigest'),
        'toolchainDigest': result.get('toolchainDigest'), 'serviceGraph': result.get('serviceGraph'),
        'warnings': result.get('warnings') or [], 'secretValuesIncluded': False,
    }


def validate_change_set_workspace(slug: str, ref: str, trace: str, title: str, description: str, changes, ttl_seconds: int = 3600) -> tuple[dict, str]:
    os.makedirs(WORKROOT, exist_ok=True)
    clean_expired(CHANGESET_ROOT)
    run_dir = tempfile.mkdtemp(prefix='change-set-', dir=WORKROOT)
    try:
        raw, archive_digest = fetch_archive(slug, ref)
        files, total = safe_extract(raw, run_dir)
        hold_until = int(time.time()) + max(300, min(int(ttl_seconds), 86400))
        def artifact_resolver(artifact_id):
            return resolve_artifact(ARTIFACT_ROOT, slug, artifact_id, hold_until=hold_until)
        def artifact_reader(artifact_id, expected_sha256, expected_size):
            return read_artifact(ARTIFACT_ROOT, slug, artifact_id, expected_sha256, expected_size)[1]
        normalized, content_bytes = normalize_changes(changes, artifact_resolver)
        applied, diff_lines = apply_changes(run_dir, normalized, artifact_reader)
        after_files = workspace_files(run_dir)
        detection = detect_components(run_dir, after_files)
        manifest_validation = validate_result_manifest(run_dir, after_files)
        inspection = {'technologies': detect_technologies(after_files), 'compose': validate_compose(run_dir, after_files), 'static': validate_static(run_dir, after_files)}
        title = str(title or '').strip()
        description = str(description or '').strip()
        if not (4 <= len(title) <= 160):
            raise ChangeSetError('invalid_title', 'O título deve ter entre 4 e 160 caracteres.', 'title', 'Normalizar estrutura do projeto')
        if len(description) > 4000:
            raise ChangeSetError('description_too_large', 'A descrição pode ter no máximo 4000 caracteres.', 'description')
        digest_value = change_set_digest(slug, ref, archive_digest, title, description, normalized)
        summary = {
            'operationCount': len(normalized),
            'createCount': sum(x['operation'] in {'create', 'mkdir'} for x in normalized),
            'updateCount': sum(x['operation'] == 'update' for x in normalized),
            'deleteCount': sum(x['operation'] == 'delete' for x in normalized),
            'contentBytes': content_bytes,
            'artifactCount': sum(bool(x.get('artifact_id')) for x in normalized),
            'filesAfter': len(after_files),
            'projectType': detection.get('projectType'),
            'componentCount': detection.get('componentCount'),
            'manifestValid': manifest_validation.get('valid'),
            'secretValuesIncluded': False,
        }
        sealed = seal_change_set(CHANGESET_ROOT, {
            'version': 1, 'project_slug': slug, 'ref': ref, 'trace_id': trace,
            'archive_sha256': archive_digest, 'title': title, 'description': description,
            'changes': normalized, 'change_set_digest': digest_value,
            'summary': summary, 'applied': applied,
            'detection': detection, 'manifest_validation': manifest_validation,
        }, ttl_seconds)
        public_changes = [{key: value for key, value in item.items() if key != 'content_base64'} for item in normalized]
        return {
            'workspace_id': sealed['workspace_id'], 'change_set_digest': digest_value,
            'expires_at': sealed['expires_at'], 'archive_sha256': archive_digest,
            'summary': summary, 'changes': public_changes, 'applied': applied,
            'diff': '\n'.join(diff_lines), 'diffTruncated': len(diff_lines) >= 4000,
            'detection': detection, 'manifestValidation': manifest_validation,
            'inspection': inspection, 'sideEffectFree': True, 'repositoryModified': False,
            'branchCreated': False, 'pullRequestCreated': False, 'secretValuesIncluded': False,
        }, run_dir
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def normalize_plan_workspace(slug: str, ref: str, trace: str, title: str, description: str, ttl_seconds: int = 3600) -> tuple[dict, str]:
    os.makedirs(WORKROOT, exist_ok=True)
    run_dir = tempfile.mkdtemp(prefix='normalize-', dir=WORKROOT)
    try:
        raw, archive_digest = fetch_archive(slug, ref)
        files, _ = safe_extract(raw, run_dir)
        detection = detect_components(run_dir, files)
        if detection.get('manifestPath'):
            return {
                'workspace_id': None, 'change_set_digest': None, 'archive_sha256': archive_digest,
                'summary': {'operationCount': 0, 'reason': 'manifest_already_present'},
                'detection': detection, 'manifestPath': detection['manifestPath'],
                'suggestionRequired': False, 'sideEffectFree': True, 'repositoryModified': False,
            }, run_dir
        proposal = detection.get('manifestProposal')
        if not proposal:
            raise ChangeSetError('manifest_proposal_unavailable', 'Não foi possível propor um manifesto para os componentes detectados.', 'repository')
        manifest = yaml.safe_dump(proposal, sort_keys=False, allow_unicode=True)
        change = {'operation': 'create', 'path': 'cloudiff.yaml', 'content_base64': __import__('base64').b64encode(manifest.encode()).decode()}
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
    result, result_dir = validate_change_set_workspace(slug, ref, trace, title or 'Adicionar manifesto CloudIFF', description or 'Adiciona a configuração versionada detectada pela plataforma.', [change], ttl_seconds)
    result['suggestionRequired'] = True
    result['generatedFiles'] = ['cloudiff.yaml']
    return result, result_dir


def resolve_change_set_workspace(slug: str, workspace_id: str, expected_digest: str) -> dict:
    sealed = load_sealed(CHANGESET_ROOT, workspace_id, expected_digest, slug)
    raw, current_archive = fetch_archive(slug, sealed['ref'])
    if current_archive != sealed['archive_sha256']:
        raise ChangeSetError('source_changed', 'A referência Forgejo mudou após a validação. Gere um novo workspace.', 'workspace_id', {'validated': sealed['archive_sha256'], 'current': current_archive})
    return {
        'workspace_id': workspace_id, 'project_slug': slug, 'ref': sealed['ref'],
        'archive_sha256': sealed['archive_sha256'], 'change_set_digest': sealed['change_set_digest'],
        'title': sealed['title'], 'description': sealed['description'], 'changes': sealed['changes'],
        'summary': sealed['summary'], 'expires_at': sealed['expires_at'],
        'sealed': True, 'sourceUnchanged': True, 'secretValuesIncluded': False,
    }


def detect_multiservice_workspace(slug: str, ref: str, trace: str) -> tuple[dict, str]:
    os.makedirs(WORKROOT, exist_ok=True)
    run_dir = tempfile.mkdtemp(prefix='detect-', dir=WORKROOT)
    try:
        raw, archive_digest = fetch_archive(slug, ref)
        files, total = safe_extract(raw, run_dir)
        detection = detect_components(run_dir, files)
        detection.update({
            'archiveSha256': archive_digest,
            'archiveBytes': len(raw),
            'unpackedBytes': total,
            'sourceRef': ref,
            'projectSlug': slug,
            'traceId': trace,
        })
        return detection, run_dir
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


COMPOSE_FILES = ('docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml')
SERVICE_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')
SENSITIVE_KEY = re.compile(r'(SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE_KEY|API_KEY|ACCESS_KEY)', re.I)
PLACEHOLDER = re.compile(r'^(|changeme|change-me|example|dummy|test|<.*>|\$\{.*\})$', re.I)


def _violation(items: list[dict], code: str, path: str, detail: str) -> None:
    items.append({'code': code, 'path': path, 'detail': detail})


def _warning(items: list[dict], code: str, path: str, detail: str) -> None:
    items.append({'code': code, 'path': path, 'detail': detail})


def _safe_relative(value: str) -> bool:
    value = value.replace('\\', '/')
    parts = [x for x in value.split('/') if x not in ('', '.')]
    return bool(parts) and not value.startswith('/') and '..' not in parts


def validate_compose(run_dir: str, files: list[str]) -> dict:
    violations: list[dict] = []
    warnings: list[dict] = []
    candidates = [x for x in COMPOSE_FILES if x in files]
    if not candidates:
        _violation(violations, 'compose_missing', '', 'Nenhum arquivo Compose na raiz do projeto')
        return {'present': False, 'valid': False, 'parser_ok': False, 'services': [], 'images': [], 'violations': violations, 'warnings': warnings}
    if len(candidates) > 1:
        _violation(violations, 'compose_ambiguous', '', 'Mais de um arquivo Compose na raiz')
    rel = candidates[0]
    path = os.path.join(run_dir, rel)
    try:
        raw = open(path, 'rb').read(FILE_MAX + 1)
        if len(raw) > FILE_MAX:
            raise ValueError('compose_too_large')
        text = raw.decode('utf-8')
        model = yaml.safe_load(text)
    except UnicodeDecodeError:
        _violation(violations, 'compose_encoding', rel, 'Compose não está em UTF-8')
        model = None
    except Exception as e:
        _violation(violations, 'compose_parse', rel, type(e).__name__)
        model = None
    services_out: list[str] = []
    images: list[str] = []
    if not isinstance(model, dict):
        _violation(violations, 'compose_model', rel, 'Modelo Compose deve ser um objeto')
    else:
        if 'include' in model:
            _violation(violations, 'compose_include', rel, 'include externo não é permitido')
        services = model.get('services')
        if not isinstance(services, dict) or not services:
            _violation(violations, 'services_missing', rel, 'services deve ser um objeto não vazio')
            services = {}
        if len(services) > 20:
            _violation(violations, 'services_limit', rel, 'Máximo de 20 serviços')
        for name, cfg in services.items():
            sp = f'{rel}:services.{name}'
            if not isinstance(name, str) or not SERVICE_NAME.fullmatch(name):
                _violation(violations, 'service_name', sp, 'Nome de serviço inválido')
                continue
            services_out.append(name)
            if not isinstance(cfg, dict):
                _violation(violations, 'service_model', sp, 'Serviço deve ser um objeto')
                continue
            if 'build' in cfg:
                _violation(violations, 'build_forbidden', sp + '.build', 'Build de imagem não é permitido neste perfil')
            image = cfg.get('image')
            if not isinstance(image, str) or not image.strip():
                _violation(violations, 'image_required', sp + '.image', 'Imagem explícita é obrigatória')
            else:
                images.append(image.strip())
                if '@sha256:' not in image:
                    _warning(warnings, 'image_not_digest_pinned', sp + '.image', 'Use imagem fixada por digest sha256 imutável')
            if cfg.get('privileged') is True:
                _violation(violations, 'privileged', sp + '.privileged', 'privileged não é permitido')
            for key in ('network_mode', 'pid', 'ipc'):
                if str(cfg.get(key, '')).lower() == 'host':
                    _violation(violations, 'host_namespace', sp + '.' + key, f'{key}=host não é permitido')
            if cfg.get('devices'):
                _violation(violations, 'devices', sp + '.devices', 'Devices do host não são permitidos')
            if cfg.get('cap_add'):
                _violation(violations, 'cap_add', sp + '.cap_add', 'Capabilities adicionais não são permitidas')
            for opt in cfg.get('security_opt') or []:
                if 'unconfined' in str(opt).lower():
                    _violation(violations, 'security_unconfined', sp + '.security_opt', 'Perfil unconfined não é permitido')
            if cfg.get('ports'):
                _warning(warnings, 'published_ports', sp + '.ports', 'Publicação de porta exige revisão de publicação')
            if cfg.get('command') is not None or cfg.get('entrypoint') is not None:
                _warning(warnings, 'custom_process', sp, 'command/entrypoint customizado exige revisão')
            env_files = cfg.get('env_file') or []
            if isinstance(env_files, (str, dict)):
                env_files = [env_files]
            for item in env_files:
                source = item.get('path', '') if isinstance(item, dict) else str(item)
                if not _safe_relative(source):
                    _violation(violations, 'env_file_path', sp + '.env_file', 'env_file deve ser relativo e permanecer no projeto')
            volumes = cfg.get('volumes') or []
            for idx, volume in enumerate(volumes):
                vp = f'{sp}.volumes[{idx}]'
                if isinstance(volume, str):
                    parts = volume.split(':')
                    source = parts[0] if len(parts) >= 2 else ''
                    target = parts[1] if len(parts) >= 2 else parts[0]
                    mode = parts[2] if len(parts) >= 3 else ''
                    if 'docker.sock' in source or 'docker.sock' in target:
                        _violation(violations, 'docker_socket', vp, 'Docker socket não é permitido')
                    if source.startswith('.'):
                        if not _safe_relative(source):
                            _violation(violations, 'bind_escape', vp, 'Bind relativo escapa do projeto')
                        if 'ro' not in mode.split(','):
                            _violation(violations, 'bind_writable', vp, 'Bind de projeto deve ser somente leitura')
                    elif source.startswith('/'):
                        _violation(violations, 'absolute_bind', vp, 'Bind absoluto não é permitido')
                    elif source:
                        _warning(warnings, 'named_volume', vp, 'Volume nomeado exige revisão de persistência')
                elif isinstance(volume, dict):
                    vtype = str(volume.get('type') or 'volume')
                    source = str(volume.get('source') or '')
                    target = str(volume.get('target') or '')
                    if 'docker.sock' in source or 'docker.sock' in target:
                        _violation(violations, 'docker_socket', vp, 'Docker socket não é permitido')
                    if vtype == 'bind':
                        if not _safe_relative(source):
                            _violation(violations, 'bind_escape', vp, 'Bind deve ser relativo ao projeto')
                        if volume.get('read_only') is not True:
                            _violation(violations, 'bind_writable', vp, 'Bind de projeto deve ser somente leitura')
                else:
                    _violation(violations, 'volume_model', vp, 'Volume inválido')
        networks = model.get('networks') or {}
        if isinstance(networks, dict):
            for name, cfg in networks.items():
                if isinstance(cfg, dict) and cfg.get('external') is True and name != 'cloudif-publications':
                    _violation(violations, 'external_network', f'{rel}:networks.{name}', 'Somente cloudif-publications pode ser externa')
    env = {'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': '/tmp', 'DOCKER_CONFIG': '/tmp/cloudif-no-docker-config'}
    cmd = ['/usr/bin/docker', 'compose', '--project-directory', run_dir, '-f', path, 'config', '--quiet', '--no-interpolate', '--no-env-resolution', '--no-path-resolution']
    try:
        parsed = subprocess.run(cmd, cwd=run_dir, env=env, text=True, capture_output=True, timeout=15)
        parser_ok = parsed.returncode == 0
        parser_error = (parsed.stderr or parsed.stdout or '')[:1000]
        if not parser_ok:
            _violation(violations, 'compose_cli', rel, parser_error or 'docker compose config falhou')
    except subprocess.TimeoutExpired:
        parser_ok = False
        parser_error = 'timeout'
        _violation(violations, 'compose_cli_timeout', rel, 'Validação Compose excedeu 15 segundos')
    return {'present': True, 'file': rel, 'valid': parser_ok and not violations, 'parser_ok': parser_ok, 'parser_error': parser_error, 'services': sorted(set(services_out)), 'images': sorted(set(images)), 'violations': violations, 'warnings': warnings}


def validate_static(run_dir: str, files: list[str]) -> dict:
    violations: list[dict] = []
    warnings: list[dict] = []
    static_ext = {'.html', '.css', '.js', '.json', '.svg'}
    checked = 0
    total = 0
    external_urls = 0
    secret_keys: list[str] = []
    for rel in files:
        lower = rel.lower()
        base = os.path.basename(rel)
        if lower.endswith(('.pem', '.key', '.p12', '.pfx')) or base in {'id_rsa', 'id_ed25519'}:
            _violation(violations, 'private_key_file', rel, 'Arquivo de chave privada não é permitido')
        path = os.path.join(run_dir, rel)
        if base == '.env':
            try:
                for raw in open(path, encoding='utf-8').read().splitlines():
                    if '=' not in raw or raw.lstrip().startswith('#'):
                        continue
                    key, value = raw.split('=', 1)
                    key = key.strip(); value = value.strip()
                    if SENSITIVE_KEY.search(key) and not PLACEHOLDER.fullmatch(value):
                        secret_keys.append(key)
                        _violation(violations, 'secret_in_env', rel + ':' + key, 'Valor sensível não deve ser versionado')
            except UnicodeDecodeError:
                _violation(violations, 'env_encoding', rel, '.env não está em UTF-8')
        ext = os.path.splitext(lower)[1]
        if ext not in static_ext:
            continue
        checked += 1
        raw = open(path, 'rb').read(FILE_MAX + 1)
        total += min(len(raw), FILE_MAX + 1)
        if len(raw) > FILE_MAX:
            _violation(violations, 'static_file_too_large', rel, 'Arquivo estático excede 10 MB')
            continue
        if b'\x00' in raw:
            _violation(violations, 'static_binary', rel, 'Arquivo estático contém bytes nulos')
            continue
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            _violation(violations, 'static_encoding', rel, 'Arquivo estático não está em UTF-8')
            continue
        external_urls += len(re.findall(r'https?://', text, re.I))
        if ext == '.html' and '<html' not in text.lower():
            _warning(warnings, 'html_fragment', rel, 'HTML não contém elemento <html>')
    if external_urls:
        _warning(warnings, 'external_urls', 'site', f'{external_urls} URL(s) externa(s) requerem revisão de conteúdo')
    return {'valid': not violations, 'checked_files': checked, 'checked_bytes': total, 'external_urls': external_urls, 'secret_keys': sorted(set(secret_keys)), 'violations': violations, 'warnings': warnings}


def validate_workspace(slug: str, ref: str) -> tuple[dict, str]:
    os.makedirs(WORKROOT, exist_ok=True)
    run_dir = tempfile.mkdtemp(prefix='validate-', dir=WORKROOT)
    try:
        raw, digest = fetch_archive(slug, ref)
        files, total = safe_extract(raw, run_dir)
        compose = validate_compose(run_dir, files)
        static = validate_static(run_dir, files)
        violations = compose['violations'] + static['violations']
        warnings = compose['warnings'] + static['warnings']
        result = {
            'valid': not violations and compose.get('parser_ok') is True,
            'archive_sha256': digest,
            'archive_bytes': len(raw),
            'file_count': len(files),
            'total_bytes': total,
            'technologies': detect_technologies(files),
            'compose': compose,
            'static': static,
            'violations': violations,
            'warnings': warnings,
        }
        return result, run_dir
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


NGINX_FORBIDDEN = [
    ('proxy_pass', re.compile(r'\bproxy_pass\b', re.I)),
    ('fastcgi_pass', re.compile(r'\bfastcgi_pass\b', re.I)),
    ('uwsgi_pass', re.compile(r'\buwsgi_pass\b', re.I)),
    ('scgi_pass', re.compile(r'\bscgi_pass\b', re.I)),
    ('grpc_pass', re.compile(r'\bgrpc_pass\b', re.I)),
    ('load_module', re.compile(r'\bload_module\b', re.I)),
    ('lua', re.compile(r'\b(?:content_by_lua|access_by_lua|rewrite_by_lua|lua_package_path)\b', re.I)),
    ('perl', re.compile(r'\bperl(?:_set)?\b', re.I)),
    ('ssl_certificate', re.compile(r'\bssl_certificate(?:_key)?\b', re.I)),
]


def validate_nginx_policy(run_dir: str, files: list[str]) -> dict:
    violations: list[dict] = []
    warnings: list[dict] = []
    if 'nginx.conf' not in files or not os.path.isdir(os.path.join(run_dir, 'site')):
        return {'applicable': False, 'valid': True, 'violations': [], 'warnings': [], 'reason': 'nginx_static_not_detected'}
    path = os.path.join(run_dir, 'nginx.conf')
    raw = open(path, 'rb').read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        _violation(violations, 'nginx_conf_too_large', 'nginx.conf', 'nginx.conf excede 1 MB')
        return {'applicable': True, 'valid': False, 'violations': violations, 'warnings': warnings}
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        _violation(violations, 'nginx_encoding', 'nginx.conf', 'nginx.conf não está em UTF-8')
        return {'applicable': True, 'valid': False, 'violations': violations, 'warnings': warnings}
    scrubbed = re.sub(r'#.*', '', text)
    for code, pattern in NGINX_FORBIDDEN:
        if pattern.search(scrubbed):
            _violation(violations, 'nginx_' + code, 'nginx.conf', f'Diretiva {code} não é permitida neste perfil')
    for match in re.finditer(r'\binclude\s+([^;]+);', scrubbed, re.I):
        target = match.group(1).strip().strip('"\'')
        _violation(violations, 'nginx_include', 'nginx.conf', f'include não é permitido: {target[:120]}')
    for match in re.finditer(r'\broot\s+([^;]+);', scrubbed, re.I):
        target = match.group(1).strip().strip('"\'')
        if target != '/usr/share/nginx/html':
            _violation(violations, 'nginx_root', 'nginx.conf', 'root deve ser /usr/share/nginx/html')
    listens = re.findall(r'\blisten\s+([^;]+);', scrubbed, re.I)
    if not listens:
        _warning(warnings, 'nginx_listen_missing', 'nginx.conf', 'Nenhuma diretiva listen encontrada')
    for value in listens:
        token = value.strip().split()[0]
        if token not in {'80', '0.0.0.0:80', '[::]:80'}:
            _violation(violations, 'nginx_listen', 'nginx.conf', 'Somente porta 80 é permitida no perfil estático')
    return {'applicable': True, 'valid': not violations, 'violations': violations, 'warnings': warnings}


def validate_preview_site(run_dir: str, files: list[str]) -> dict:
    violations: list[dict] = []
    warnings: list[dict] = []
    rel = 'site/index.html'
    if rel not in files:
        _violation(violations, 'preview_index_missing', rel, 'site/index.html é obrigatório')
        return {'valid': False, 'violations': violations, 'warnings': warnings}
    path = os.path.join(run_dir, rel)
    raw = open(path, 'rb').read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        _violation(violations, 'preview_index_too_large', rel, 'index.html excede 2 MB')
        return {'valid': False, 'violations': violations, 'warnings': warnings}
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        _violation(violations, 'preview_index_encoding', rel, 'index.html não está em UTF-8')
        return {'valid': False, 'violations': violations, 'warnings': warnings}
    lower = text.lower()
    if '<html' not in lower and '<!doctype' not in lower:
        _violation(violations, 'preview_index_malformed', rel, 'index.html não contém documento HTML reconhecível')
    if 'welcome to nginx' in lower:
        _violation(violations, 'preview_default_page', rel, 'Página padrão do Nginx não é aceita')
    if len(raw) < 32:
        _violation(violations, 'preview_index_too_small', rel, 'index.html não contém conteúdo significativo')
    return {'valid': not violations, 'bytes': len(raw), 'violations': violations, 'warnings': warnings}


def preview_static_workspace(slug: str, ref: str, trace: str) -> tuple[dict, str, str]:
    os.makedirs(WORKROOT, exist_ok=True)
    run_dir = tempfile.mkdtemp(prefix='preview-', dir=WORKROOT)
    name = 'cloudif-ws-' + uuid.uuid4().hex[:18]
    created = False
    try:
        raw, digest = fetch_archive(slug, ref)
        files, total = safe_extract(raw, run_dir)
        compose = validate_compose(run_dir, files)
        static = validate_static(run_dir, files)
        nginx_policy = validate_nginx_policy(run_dir, files)
        site = validate_preview_site(run_dir, files)
        violations = compose['violations'] + static['violations'] + nginx_policy['violations'] + site['violations']
        warnings = compose['warnings'] + static['warnings'] + nginx_policy['warnings'] + site['warnings']
        common = {
            'archive_sha256': digest, 'archive_bytes': len(raw), 'file_count': len(files),
            'total_bytes': total, 'technologies': detect_technologies(files),
            'compose': compose, 'static': static, 'nginx_policy': nginx_policy,
            'site': site, 'violations': violations, 'warnings': warnings,
            'published_ports': [], 'network_mode': 'none',
        }
        if not nginx_policy['applicable']:
            common.update({'applicable': False, 'valid': False, 'reason': nginx_policy.get('reason'), 'runtime': {'executed': False}})
            return common, name, run_dir
        if violations:
            common.update({'applicable': True, 'valid': False, 'runtime': {'executed': False}})
            return common, name, run_dir
        cid = docker(
            *base_container_args(name, slug, trace),
            '--tmpfs', '/var/cache/nginx:rw,nosuid,nodev,size=16m,mode=0755,uid=65534,gid=65534',
            '--tmpfs', '/run:rw,nosuid,nodev,size=4m,mode=0755,uid=65534,gid=65534',
            '--tmpfs', '/var/log/nginx:rw,nosuid,nodev,size=4m,mode=0755,uid=65534,gid=65534',
            '--mount', f'type=bind,src={os.path.join(run_dir,"nginx.conf")},dst=/etc/nginx/conf.d/default.conf,readonly',
            '--mount', f'type=bind,src={os.path.join(run_dir,"site")},dst=/usr/share/nginx/html,readonly',
            IMAGE, '/bin/sh', '-c', PREVIEW_SCRIPT,
        ).strip()
        created = True
        inspect = json.loads(docker('inspect', cid))[0]
        out = docker('start', '-a', cid, timeout=20)
        values: dict[str,str] = {}
        head = out.split('\n---INDEX---\n',1)[0]
        for line in head.splitlines():
            if '=' in line:
                k,v=line.split('=',1);values[k]=v
        index = out.split('\n---INDEX---\n',1)[1].split('\n---HEALTH---\n',1)[0] if '\n---INDEX---\n' in out else ''
        health = out.split('\n---HEALTH---\n',1)[1].split('\n---LOG---\n',1)[0] if '\n---HEALTH---\n' in out else ''
        log = out.split('\n---LOG---\n',1)[1] if '\n---LOG---\n' in out else ''
        runtime_ok = (
            values.get('index_ok') == '1' and values.get('health_ok') == '1'
            and values.get('meaningful') == '1' and values.get('network') == 'none'
            and values.get('docker_socket') == 'absent' and values.get('uid') not in (None,'0')
            and int(values.get('index_bytes') or 0) <= 2 * 1024 * 1024
            and 'text/html' in values.get('index_type','').lower()
        )
        common.update({
            'applicable': True, 'valid': runtime_ok,
            'runtime': {
                'executed': True, 'index_ok': values.get('index_ok') == '1',
                'health_ok': values.get('health_ok') == '1', 'meaningful_html': values.get('meaningful') == '1',
                'index_content_type': values.get('index_type',''), 'health_content_type': values.get('health_type',''),
                'index_bytes': int(values.get('index_bytes') or 0), 'health_bytes': int(values.get('health_bytes') or 0),
                'index_excerpt': index[:1024], 'health_excerpt': health[:512], 'log_excerpt': log[:2048],
            },
            'container': {'uid': values.get('uid'), 'network': values.get('network'), 'docker_socket': values.get('docker_socket')},
            'memory_limit_bytes': int(inspect['HostConfig']['Memory']), 'pids_limit': int(inspect['HostConfig']['PidsLimit'] or 0),
            'published_ports': sorted((inspect['HostConfig'].get('PortBindings') or {}).keys()),
            'network_mode': inspect['HostConfig'].get('NetworkMode'),
        })
        return common, name, run_dir
    finally:
        if created:
            subprocess.run(['/usr/bin/docker','rm','-f',name],capture_output=True,timeout=5)
        shutil.rmtree(run_dir,ignore_errors=True)


EDIT_PATH = re.compile(r'^site/[A-Za-z0-9][A-Za-z0-9._/-]{0,220}$')
EDIT_EXTENSIONS = {'.html', '.css', '.js', '.json', '.svg', '.txt'}


def apply_text_edit(run_dir: str, rel: str, expected_sha256: str, find_text: str, replace_text: str) -> dict:
    if not EDIT_PATH.fullmatch(rel) or '..' in rel.split('/') or os.path.splitext(rel.lower())[1] not in EDIT_EXTENSIONS:
        raise ValueError('edit_path_invalid')
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('expected_sha256_invalid')
    if not (1 <= len(find_text.encode('utf-8')) <= 4096) or len(replace_text.encode('utf-8')) > 4096:
        raise ValueError('edit_text_size')
    if '\x00' in find_text or '\x00' in replace_text:
        raise ValueError('edit_null_byte')
    root = os.path.realpath(run_dir)
    target = os.path.realpath(os.path.join(run_dir, *rel.split('/')))
    if not target.startswith(root + os.sep) or not os.path.isfile(target):
        raise ValueError('edit_file_missing')
    raw = open(target, 'rb').read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError('edit_file_too_large')
    current_sha = hashlib.sha256(raw).hexdigest()
    if not hmac.compare_digest(current_sha, expected_sha256):
        raise ValueError('edit_stale_sha256')
    try:
        before = raw.decode('utf-8')
    except UnicodeDecodeError as e:
        raise ValueError('edit_encoding') from e
    count = before.count(find_text)
    if count != 1:
        raise ValueError('edit_match_count')
    after = before.replace(find_text, replace_text, 1)
    after_raw = after.encode('utf-8')
    if len(after_raw) > 2 * 1024 * 1024:
        raise ValueError('edit_result_too_large')
    with open(target, 'wb') as out:
        out.write(after_raw)
    os.chmod(target, 0o644)
    diff = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/'+rel, tofile='b/'+rel, n=3))
    if len(diff.encode('utf-8')) > 32 * 1024:
        raise ValueError('edit_diff_too_large')
    return {
        'path': rel,
        'before_sha256': current_sha,
        'after_sha256': hashlib.sha256(after_raw).hexdigest(),
        'before_bytes': len(raw),
        'after_bytes': len(after_raw),
        'occurrences': count,
        'diff': diff,
    }


def edit_preview_workspace(slug: str, ref: str, trace: str, rel: str, expected_sha256: str, find_text: str, replace_text: str) -> tuple[dict, str, str]:
    os.makedirs(WORKROOT, exist_ok=True)
    run_dir = tempfile.mkdtemp(prefix='edit-preview-', dir=WORKROOT)
    name = 'cloudif-ws-' + uuid.uuid4().hex[:18]
    created = False
    try:
        raw, archive_digest = fetch_archive(slug, ref)
        files, total = safe_extract(raw, run_dir)
        edit = apply_text_edit(run_dir, rel, expected_sha256, find_text, replace_text)
        compose = validate_compose(run_dir, files)
        static = validate_static(run_dir, files)
        nginx_policy = validate_nginx_policy(run_dir, files)
        site = validate_preview_site(run_dir, files)
        violations = compose['violations'] + static['violations'] + nginx_policy['violations'] + site['violations']
        warnings = compose['warnings'] + static['warnings'] + nginx_policy['warnings'] + site['warnings']
        common = {
            'archive_sha256': archive_digest, 'archive_bytes': len(raw), 'file_count': len(files),
            'total_bytes': total, 'technologies': detect_technologies(files), 'edit': edit,
            'compose': compose, 'static': static, 'nginx_policy': nginx_policy, 'site': site,
            'violations': violations, 'warnings': warnings, 'published_ports': [], 'network_mode': 'none',
            'persisted': False,
        }
        if not nginx_policy['applicable'] or violations:
            common.update({'valid': False, 'runtime': {'executed': False}})
            return common, name, run_dir
        cid = docker(
            *base_container_args(name, slug, trace),
            '--tmpfs', '/var/cache/nginx:rw,nosuid,nodev,size=16m,mode=0755,uid=65534,gid=65534',
            '--tmpfs', '/run:rw,nosuid,nodev,size=4m,mode=0755,uid=65534,gid=65534',
            '--tmpfs', '/var/log/nginx:rw,nosuid,nodev,size=4m,mode=0755,uid=65534,gid=65534',
            '--mount', f'type=bind,src={os.path.join(run_dir,"nginx.conf")},dst=/etc/nginx/conf.d/default.conf,readonly',
            '--mount', f'type=bind,src={os.path.join(run_dir,"site")},dst=/usr/share/nginx/html,readonly',
            IMAGE, '/bin/sh', '-c', PREVIEW_SCRIPT,
        ).strip()
        created = True
        inspect = json.loads(docker('inspect', cid))[0]
        out = docker('start', '-a', cid, timeout=20)
        values: dict[str,str] = {}
        head = out.split('\n---INDEX---\n',1)[0]
        for line in head.splitlines():
            if '=' in line:
                k,v=line.split('=',1);values[k]=v
        index = out.split('\n---INDEX---\n',1)[1].split('\n---HEALTH---\n',1)[0] if '\n---INDEX---\n' in out else ''
        health = out.split('\n---HEALTH---\n',1)[1].split('\n---LOG---\n',1)[0] if '\n---HEALTH---\n' in out else ''
        log = out.split('\n---LOG---\n',1)[1] if '\n---LOG---\n' in out else ''
        runtime_ok = (
            values.get('index_ok') == '1' and values.get('health_ok') == '1'
            and values.get('meaningful') == '1' and values.get('network') == 'none'
            and values.get('docker_socket') == 'absent' and values.get('uid') not in (None,'0')
            and 'text/html' in values.get('index_type','').lower()
            and replace_text in index
        )
        common.update({
            'valid': runtime_ok,
            'runtime': {
                'executed': True, 'index_ok': values.get('index_ok') == '1',
                'health_ok': values.get('health_ok') == '1', 'meaningful_html': values.get('meaningful') == '1',
                'replacement_visible': replace_text in index,
                'index_content_type': values.get('index_type',''), 'health_content_type': values.get('health_type',''),
                'index_bytes': int(values.get('index_bytes') or 0), 'health_bytes': int(values.get('health_bytes') or 0),
                'index_excerpt': index[:1024], 'health_excerpt': health[:512], 'log_excerpt': log[:2048],
            },
            'container': {'uid': values.get('uid'), 'network': values.get('network'), 'docker_socket': values.get('docker_socket')},
            'memory_limit_bytes': int(inspect['HostConfig']['Memory']), 'pids_limit': int(inspect['HostConfig']['PidsLimit'] or 0),
            'published_ports': sorted((inspect['HostConfig'].get('PortBindings') or {}).keys()),
            'network_mode': inspect['HostConfig'].get('NetworkMode'),
        })
        return common, name, run_dir
    finally:
        if created:
            subprocess.run(['/usr/bin/docker','rm','-f',name],capture_output=True,timeout=5)
        shutil.rmtree(run_dir,ignore_errors=True)


def test_static_workspace(slug: str, ref: str, trace: str) -> tuple[dict, str, str]:
    os.makedirs(WORKROOT, exist_ok=True)
    run_dir = tempfile.mkdtemp(prefix='static-', dir=WORKROOT)
    name = 'cloudif-ws-' + uuid.uuid4().hex[:18]
    created = False
    try:
        raw, digest = fetch_archive(slug, ref)
        files, total = safe_extract(raw, run_dir)
        compose = validate_compose(run_dir, files)
        static = validate_static(run_dir, files)
        nginx_policy = validate_nginx_policy(run_dir, files)
        policy_violations = compose['violations'] + static['violations'] + nginx_policy['violations']
        common = {
            'archive_sha256': digest,
            'archive_bytes': len(raw),
            'file_count': len(files),
            'total_bytes': total,
            'technologies': detect_technologies(files),
            'compose': compose,
            'static': static,
            'nginx_policy': nginx_policy,
            'violations': policy_violations,
            'warnings': compose['warnings'] + static['warnings'] + nginx_policy['warnings'],
        }
        if not nginx_policy['applicable']:
            common.update({'applicable': False, 'valid': compose.get('valid') is True and static.get('valid') is True, 'reason': nginx_policy.get('reason')})
            return common, name, run_dir
        if policy_violations:
            common.update({'applicable': True, 'valid': False, 'nginx': {'executed': False, 'syntax_ok': False}})
            return common, name, run_dir
        cid = docker(
            *base_container_args(name, slug, trace),
            '--tmpfs', '/var/cache/nginx:rw,nosuid,nodev,size=16m,mode=0755,uid=65534,gid=65534',
            '--tmpfs', '/run:rw,nosuid,nodev,size=4m,mode=0755,uid=65534,gid=65534',
            '--tmpfs', '/var/log/nginx:rw,nosuid,nodev,size=4m,mode=0755,uid=65534,gid=65534',
            '--mount', f'type=bind,src={os.path.join(run_dir,"nginx.conf")},dst=/etc/nginx/conf.d/default.conf,readonly',
            '--mount', f'type=bind,src={os.path.join(run_dir,"site")},dst=/usr/share/nginx/html,readonly',
            IMAGE, '/bin/sh', '-c', STATIC_TEST_SCRIPT,
        ).strip()
        created = True
        inspect = json.loads(docker('inspect', cid))[0]
        out = docker('start', '-a', cid, timeout=15)
        marker = '\n---OUTPUT---\n'
        head, output = out.split(marker, 1) if marker in out else (out, '')
        values = {}
        for line in head.splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                values[k] = v
        syntax_ok = values.get('nginx_rc') == '0'
        common.update({
            'applicable': True,
            'valid': syntax_ok,
            'nginx': {'executed': True, 'syntax_ok': syntax_ok, 'output': output[:4000]},
            'container': values,
            'memory_limit_bytes': int(inspect['HostConfig']['Memory']),
            'pids_limit': int(inspect['HostConfig']['PidsLimit'] or 0),
        })
        return common, name, run_dir
    finally:
        if created:
            subprocess.run(['/usr/bin/docker', 'rm', '-f', name], capture_output=True, timeout=5)
        shutil.rmtree(run_dir, ignore_errors=True)


class H(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def sendj(self, code: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def sendb(self, code: int, raw: bytes, metadata: dict) -> None:
        self.send_response(code)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-CloudIF-Artifact-Id', str(metadata.get('artifact_id') or ''))
        self.send_header('X-CloudIF-Artifact-Sha256', str(metadata.get('sha256') or ''))
        self.send_header('X-CloudIF-Artifact-Size', str(metadata.get('size') or len(raw)))
        self.send_header('X-CloudIF-Artifact-Expires', str(metadata.get('expires_at') or 0))
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers(); self.wfile.write(raw)

    def auth(self) -> bool:
        return bool(TOKEN) and hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + TOKEN)

    def do_GET(self) -> None:
        if urlparse(self.path).path == '/health':
            try:
                docker('version', '--format', '{{.Server.Version}}', timeout=4)
                self.sendj(200, {'ok': True, 'service': 'cloudif-workspace-broker', 'profiles': ['probe', 'prepare', 'detect-multiservice', 'normalize-plan', 'artifact-upload', 'change-set-validate', 'change-set-resolve', 'validate', 'test-static', 'preview-static', 'edit-preview']})
            except Exception:
                self.sendj(503, {'ok': False, 'error': 'docker_unavailable'})
        else:
            self.sendj(404, {'ok': False, 'error': 'not_found'})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {'/v1/artifact/start','/v1/artifact/chunk','/v1/artifact/complete','/v1/artifact/read','/v1/probe', '/v1/prepare', '/v1/detect-multiservice', '/v1/normalize-plan', '/v1/change-set/validate', '/v1/change-set/resolve', '/v1/validate', '/v1/test-static', '/v1/preview-static', '/v1/edit-preview'}:
            self.sendj(404, {'ok': False, 'error': 'not_found'})
            return
        if not self.auth():
            self.sendj(401, {'ok': False, 'error': 'unauthorized'})
            return
        try:
            n = int(self.headers.get('Content-Length', '0'))
            maximum = 3 * 1024 * 1024 if path == '/v1/change-set/validate' else (384 * 1024 if path == '/v1/artifact/chunk' else 256 * 1024)
            assert 0 < n <= maximum
            data = json.loads(self.rfile.read(n))
            if not isinstance(data, dict):
                raise ValueError('invalid_request')
            if path == '/v1/artifact/start':
                required={'project_slug','trace_id','filename','expected_size','expected_sha256'}; allowed=required|{'ttl_seconds'}
            elif path == '/v1/artifact/chunk':
                required={'project_slug','trace_id','artifact_id','chunk_index','content_base64','chunk_sha256'}; allowed=required
            elif path == '/v1/artifact/complete':
                required={'project_slug','trace_id','artifact_id'}; allowed=required
            elif path == '/v1/artifact/read':
                required={'project_slug','trace_id','artifact_id','expected_sha256','expected_size'}; allowed=required
            elif path == '/v1/probe':
                required = {'project_slug', 'trace_id'}; allowed = required
            elif path == '/v1/edit-preview':
                required = {'project_slug','ref','trace_id','path','expected_sha256','find','replace'}; allowed = required
            elif path == '/v1/normalize-plan':
                required = {'project_slug','ref','trace_id'}; allowed = required | {'title','description','ttl_seconds'}
            elif path == '/v1/change-set/validate':
                required = {'project_slug','ref','trace_id','title','description','changes'}; allowed = required | {'ttl_seconds'}
            elif path == '/v1/change-set/resolve':
                required = {'project_slug','trace_id','workspace_id','change_set_digest'}; allowed = required
            else:
                required = {'project_slug', 'ref', 'trace_id'}; allowed = required
            if not required.issubset(data) or not set(data).issubset(allowed):
                raise ValueError('invalid_request_fields')
            slug = str(data['project_slug'])
            trace = str(data['trace_id'])
            assert SLUG.fullmatch(slug) and TRACE.fullmatch(trace)
            ref = str(data.get('ref') or 'main')
            edit_path = str(data.get('path') or '')
            expected_sha256 = str(data.get('expected_sha256') or '')
            find_text = str(data.get('find') or '')
            replace_text = str(data.get('replace') or '')
            title = str(data.get('title') or '')
            description = str(data.get('description') or '')
            changes = data.get('changes')
            ttl_seconds = int(data.get('ttl_seconds') or 3600)
            workspace_id = str(data.get('workspace_id') or '')
            expected_digest = str(data.get('change_set_digest') or '')
            artifact_id = str(data.get('artifact_id') or '')
            filename = str(data.get('filename') or '')
            artifact_expected_size = int(data.get('expected_size') or 0)
            artifact_expected_sha256 = str(data.get('expected_sha256') or '')
            chunk_index = int(data.get('chunk_index') or 0)
            chunk_content = data.get('content_base64')
            chunk_sha256 = str(data.get('chunk_sha256') or '')
            if path not in {'/v1/change-set/resolve','/v1/artifact/start','/v1/artifact/chunk','/v1/artifact/complete','/v1/artifact/read'}:
                assert REF.fullmatch(ref) and '..' not in ref and not ref.startswith('/') and not ref.endswith('/')
            if path in {'/v1/artifact/start','/v1/normalize-plan','/v1/change-set/validate'}: assert 300 <= ttl_seconds <= 86400
        except Exception:
            self.sendj(400, {'ok': False, 'error': {'code': 'invalid_request', 'message': 'A solicitação contém campos ausentes ou incompatíveis.'}})
            return
        started = time.monotonic()
        event_map = {
            '/v1/artifact/start':'workspace.artifact.start','/v1/artifact/chunk':'workspace.artifact.chunk','/v1/artifact/complete':'workspace.artifact.complete','/v1/artifact/read':'workspace.artifact.read',
            '/v1/probe':'workspace.probe','/v1/prepare':'workspace.prepare',
            '/v1/detect-multiservice':'workspace.detect-multiservice','/v1/normalize-plan':'workspace.normalize-plan',
            '/v1/change-set/validate':'workspace.change-set.validate','/v1/change-set/resolve':'workspace.change-set.resolve',
            '/v1/validate':'workspace.validate','/v1/test-static':'workspace.test-static',
            '/v1/preview-static':'workspace.preview-static','/v1/edit-preview':'workspace.edit-preview',
        }
        event = event_map[path]
        try:
            if path == '/v1/artifact/start':
                result=start_artifact(ARTIFACT_ROOT,slug,filename,artifact_expected_size,artifact_expected_sha256,ttl_seconds);run_dir='';name='';removed=True
            elif path == '/v1/artifact/chunk':
                result=append_chunk(ARTIFACT_ROOT,slug,artifact_id,chunk_index,chunk_content,chunk_sha256);run_dir='';name='';removed=True
            elif path == '/v1/artifact/complete':
                result=complete_artifact(ARTIFACT_ROOT,slug,artifact_id);run_dir='';name='';removed=True
            elif path == '/v1/artifact/read':
                meta,raw=read_artifact(ARTIFACT_ROOT,slug,artifact_id,artifact_expected_sha256,artifact_expected_size)
                print(json.dumps({'event': event, 'project_slug': slug, 'trace_id': trace, 'result':'success','artifact_id':artifact_id,'bytes':len(raw),'duration_ms':round((time.monotonic()-started)*1000,2)},separators=(',',':')),flush=True)
                self.sendb(200,raw,meta);return
            elif path == '/v1/probe':
                result, name = probe(slug, trace)
                run_dir = ''
                removed = subprocess.run(['/usr/bin/docker', 'inspect', name], capture_output=True).returncode != 0
            elif path == '/v1/prepare':
                result, name, run_dir = prepare_workspace(slug, ref, trace)
                removed = subprocess.run(['/usr/bin/docker', 'inspect', name], capture_output=True).returncode != 0
            elif path == '/v1/detect-multiservice':
                result, run_dir = detect_multiservice_workspace(slug, ref, trace)
                name = ''
                removed = True
            elif path == '/v1/normalize-plan':
                result, run_dir = normalize_plan_workspace(slug, ref, trace, title, description, ttl_seconds)
                name = ''
                removed = True
            elif path == '/v1/change-set/validate':
                result, run_dir = validate_change_set_workspace(slug, ref, trace, title, description, changes, ttl_seconds)
                name = ''
                removed = True
            elif path == '/v1/change-set/resolve':
                result = resolve_change_set_workspace(slug, workspace_id, expected_digest)
                run_dir = ''; name = ''; removed = True
            elif path == '/v1/validate':
                result, run_dir = validate_workspace(slug, ref)
                name = ''
                removed = True
            elif path == '/v1/test-static':
                result, name, run_dir = test_static_workspace(slug, ref, trace)
                removed = subprocess.run(['/usr/bin/docker', 'inspect', name], capture_output=True).returncode != 0
            elif path == '/v1/preview-static':
                result, name, run_dir = preview_static_workspace(slug, ref, trace)
                removed = subprocess.run(['/usr/bin/docker', 'inspect', name], capture_output=True).returncode != 0
            else:
                result, name, run_dir = edit_preview_workspace(slug, ref, trace, edit_path, expected_sha256, find_text, replace_text)
                removed = subprocess.run(['/usr/bin/docker', 'inspect', name], capture_output=True).returncode != 0
            temp_removed = not run_dir or not os.path.exists(run_dir)
            print(json.dumps({'event': event, 'project_slug': slug, 'trace_id': trace, 'result': 'success', 'duration_ms': round((time.monotonic() - started) * 1000, 2)}, separators=(',', ':')), flush=True)
            self.sendj(200, {'ok': True, 'result': result, 'container_removed': removed, 'temp_removed': temp_removed})
        except FileNotFoundError:
            self.sendj(404, {'ok': False, 'error': {'code': 'project_or_ref_not_found', 'message': 'O projeto ou a referência não foi encontrado.'}})
        except ArtifactError as e:
            self.sendj(422, {'ok': False, 'error': e.as_dict()})
        except ChangeSetError as e:
            self.sendj(422, {'ok': False, 'error': e.as_dict()})
        except ValueError as e:
            self.sendj(422, {'ok': False, 'error': {'code': str(e)[:160], 'message': 'A validação do workspace falhou.'}})
        except Exception as e:
            print(json.dumps({'event': event, 'project_slug': slug, 'trace_id': trace, 'result': 'error', 'error': type(e).__name__}, separators=(',', ':')), flush=True)
            self.sendj(503, {'ok': False, 'error': str(e)[:160]})


if __name__ == '__main__':
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
