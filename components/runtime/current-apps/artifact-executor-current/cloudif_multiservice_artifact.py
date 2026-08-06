#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import hmac
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
from pathlib import Path, PurePosixPath
from typing import Any

STATIC_BASE = os.environ.get(
    'CLOUDIF_STATIC_BASE_IMAGE',
    'cgr.dev/chainguard/nginx@sha256:d36a7338ffc140bc1e3cd85e2eb9d3419cf8b03b848a2f26cc99db157f1f505d',
)
NODE24_BUILDER = os.environ.get(
    'CLOUDIF_NODE24_BUILDER_IMAGE',
    'node@sha256:a0b9bf06e4e6193cf7a0f58816cc935ff8c2a908f81e6f1a95432d679c54fbfd',
)
NODE24_RUNTIME = os.environ.get(
    'CLOUDIF_NODE24_RUNTIME_IMAGE',
    'gcr.io/distroless/nodejs24-debian12@sha256:6afed2f0373317ea4c66843fc7f1d4b4c88ef3e97254b2c5925793c2beb72809',
)
FORJA_URL = os.environ.get('CLOUDIF_FORJA_LOCAL_URL', 'http://127.0.0.1:18095').rstrip('/')
FORJA_TOKEN = (os.environ.get('FORJA_AGENT_TOKEN') or '').strip()
ARTIFACT_ROOT = Path(os.environ.get('CLOUDIF_MULTISERVICE_ARTIFACT_ROOT', '/srv/cloudif/artifacts/multiservice'))
TRIVY_CACHE = Path(os.environ.get('CLOUDIF_TRIVY_CACHE', '/srv/cloudif/scanners/trivy-cache'))
SCANNER_ENV = Path(os.environ.get('CLOUDIF_SCANNER_ENV', '/srv/cloudif/scanners/images.env'))
SIGNING_KEY = Path(os.environ.get('CLOUDIF_ARTIFACT_SIGNING_KEY', '/etc/cloudif/artifact-signing.key'))
SIGNING_PUBLIC_KEY = Path(os.environ.get('CLOUDIF_ARTIFACT_SIGNING_PUBLIC_KEY', '/etc/cloudif/artifact-signing.pub'))
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_UNPACKED = 256 * 1024 * 1024
MAX_FILES = 25000
MAX_SERVICES = 16
MAX_HOOKS = 32
SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
SERVICE_RE = re.compile(r'^[a-z][a-z0-9-]{0,31}$')
SHA_RE = re.compile(r'^[a-f0-9]{64}$')
REF_RE = re.compile(r'^[A-Za-z0-9._/-]{1,128}$')
PRIVATE_RE = re.compile(r'(?i)(?:^|/)(?:\.env(?:\..*)?|secrets?(?:\..*)?|credentials?(?:\..*)?|id_(?:rsa|ed25519)|.*\.(?:pem|key|p12|pfx|jks|keystore))$')
IGNORED = {'.git', 'node_modules', 'vendor', 'dist', 'build', 'out', '.next', '.nuxt', 'coverage', '.cache', '__pycache__', '.venv', 'venv', 'tmp', 'logs', 'artifacts'}


class ArtifactError(RuntimeError):
    def __init__(self, code: str, message: str, field: str = '', detail: Any = None, http_status: int = 422):
        super().__init__(code)
        self.code = code
        self.message = message
        self.field = field
        self.detail = detail
        self.http_status = http_status

    def as_dict(self) -> dict[str, Any]:
        result = {'code': self.code, 'message': self.message, 'field': self.field, 'documentation': 'multiservice-build-v1'}
        if self.detail is not None:
            result['detail'] = self.detail
        return result


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def load_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for raw in path.read_text(errors='ignore').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def safe_rel(value: Any, field: str, allow_dot: bool = True) -> str:
    text = str(value or '.').replace('\\', '/').strip().strip('/')
    if not text and allow_dot:
        return '.'
    if not text or len(text) > 240 or '\x00' in text:
        raise ArtifactError('invalid_path', 'O caminho deve ser relativo e ter até 240 caracteres.', field)
    path = PurePosixPath(text)
    if path.is_absolute() or '..' in path.parts or any(part in {'', '.'} for part in path.parts):
        raise ArtifactError('unsafe_path', 'O caminho não pode sair do repositório.', field)
    if path.parts[0] == '.git' or any(part in IGNORED for part in path.parts[:-1]) or PRIVATE_RE.search(text):
        raise ArtifactError('protected_path', 'O caminho pertence a uma área protegida, privada ou gerada.', field)
    return str(path)


def normalize_command(value: Any, field: str) -> list[str] | None:
    if value is None or value == '':
        return None
    if not isinstance(value, list) or not value or len(value) > 32:
        raise ArtifactError('invalid_command', 'Comandos de build devem ser arrays argv com até 32 itens.', field)
    command = [str(item) for item in value]
    if any(not item or len(item) > 512 or '\x00' in item for item in command):
        raise ArtifactError('invalid_command', 'O comando contém argumentos inválidos.', field)
    joined = ' '.join(command)
    if re.search(r'(?i)(?:password|secret|token|api[_-]?key)=\S+|://[^/@:]+:[^/@]+@', joined):
        raise ArtifactError('secret_value_not_allowed', 'Comandos não podem conter valores secretos.', field)
    return command


def runtime_policy(service: dict[str, Any]) -> dict[str, Any]:
    runtime = service['runtime']
    version = str(service.get('version') or '')
    if runtime == 'static':
        return {'status': 'ready', 'builder': STATIC_BASE, 'runtimeImage': STATIC_BASE, 'reason': 'approved_static_digest'}
    if runtime == 'node' and version == '24':
        return {'status': 'ready', 'builder': NODE24_BUILDER, 'runtimeImage': NODE24_RUNTIME, 'reason': 'node24_homologated'}
    if runtime == 'node':
        return {'status': 'blocked', 'reason': 'node_version_not_homologated', 'allowedVersions': ['24']}
    if runtime == 'php':
        return {'status': 'blocked', 'reason': 'php_base_failed_security_scan', 'scannerCounts': {'HIGH': 17, 'CRITICAL': 1}}
    if runtime in {'docker', 'compose'}:
        return {'status': 'blocked', 'reason': 'custom_container_policy_not_enabled_in_phase4'}
    return {'status': 'blocked', 'reason': 'runtime_not_supported'}


def normalize_services(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not (1 <= len(value) <= MAX_SERVICES):
        raise ArtifactError('invalid_services', 'services deve conter entre 1 e 16 serviços.', 'services')
    result: list[dict[str, Any]] = []
    names: set[str] = set()
    ports: dict[int, str] = {}
    for index, raw in enumerate(value):
        field = f'services.{index}'
        if not isinstance(raw, dict):
            raise ArtifactError('invalid_service', 'Cada serviço deve ser um objeto.', field)
        name = str(raw.get('name') or '').strip()
        runtime = str(raw.get('runtime') or '').strip().lower()
        if not SERVICE_RE.fullmatch(name) or name in names:
            raise ArtifactError('invalid_service_name', 'O nome do serviço é inválido ou duplicado.', field + '.name')
        names.add(name)
        path = safe_rel(raw.get('path') or '.', field + '.path')
        publish = safe_rel(raw.get('publish') or '.', field + '.publish') if raw.get('publish') is not None else None
        version = str(raw.get('version') or '') or None
        port = int(raw.get('port') or 0) or None
        if port is not None:
            if not (1024 <= port <= 65535):
                raise ArtifactError('invalid_port', 'A porta deve estar entre 1024 e 65535.', field + '.port')
            if port in ports:
                raise ArtifactError('duplicate_internal_port', f'A porta {port} também pertence a {ports[port]}.', field + '.port')
            ports[port] = name
        hooks = raw.get('hookSteps') or raw.get('hookScripts') or []
        if not isinstance(hooks, list) or len(hooks) > MAX_HOOKS:
            raise ArtifactError('invalid_hooks', 'hookSteps deve ser uma lista com até 32 itens.', field + '.hookSteps')
        normalized_hooks=[]
        for item in hooks:
            if isinstance(item,dict):
                phase=str(item.get('phase') or '').strip()
                if phase not in {'preBuild','postBuild'}:
                    raise ArtifactError('invalid_hook_phase','O hook deve usar preBuild ou postBuild.',field+'.hookSteps')
                normalized_hooks.append({'phase':phase,'path':safe_rel(item.get('path'),field+'.hookSteps')})
            else:
                normalized_hooks.append({'phase':'preBuild','path':safe_rel(item,field+'.hookScripts')})
        hooks=normalized_hooks
        service = {
            'name': name, 'path': path, 'runtime': runtime, 'version': version,
            'install': normalize_command(raw.get('install'), field + '.install'),
            'build': normalize_command(raw.get('build'), field + '.build'),
            'start': normalize_command(raw.get('start'), field + '.start'),
            'publish': publish, 'port': port,
            'healthcheck': str(raw.get('healthcheck') or '') or None,
            'hookSteps': hooks,
            'excludePaths': [safe_rel(item, field + '.excludePaths') for item in (raw.get('excludePaths') or [])],
        }
        service['policy'] = runtime_policy(service)
        result.append(service)
    return result


def validate_request(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ArtifactError('invalid_request', 'A solicitação deve ser um objeto.', http_status=400)
    required = {'job_id', 'project_slug', 'ref', 'archive_sha256', 'config_revision', 'config_digest', 'toolchain_digest', 'plan_digest', 'services', 'trace_id'}
    if not required.issubset(payload):
        missing = sorted(required - set(payload))
        raise ArtifactError('required_field_missing', 'Campos obrigatórios estão ausentes.', detail={'missing': missing}, http_status=400)
    slug = str(payload.get('project_slug') or '').strip()
    ref = str(payload.get('ref') or '').strip()
    archive_sha = str(payload.get('archive_sha256') or '').strip().lower()
    config_digest = str(payload.get('config_digest') or '').strip().lower()
    toolchain_digest = str(payload.get('toolchain_digest') or '').strip().lower()
    plan_digest = str(payload.get('plan_digest') or '').strip().lower()
    job_id = str(payload.get('job_id') or '').strip()
    trace_id = str(payload.get('trace_id') or '').strip()
    if not SLUG_RE.fullmatch(slug):
        raise ArtifactError('invalid_project_slug', 'project_slug é inválido.', 'project_slug', http_status=400)
    if not REF_RE.fullmatch(ref) or '..' in ref or ref.startswith('/') or ref.endswith('/'):
        raise ArtifactError('invalid_ref', 'ref deve ser uma referência relativa.', 'ref', http_status=400)
    for field, value in (('archive_sha256', archive_sha), ('config_digest', config_digest), ('toolchain_digest', toolchain_digest), ('plan_digest', plan_digest)):
        if not SHA_RE.fullmatch(value):
            raise ArtifactError('invalid_digest', f'{field} deve ter 64 caracteres hexadecimais.', field, http_status=400)
    if not re.fullmatch(r'build_[a-f0-9]{24}', job_id) or not trace_id or len(trace_id) > 128:
        raise ArtifactError('invalid_job_identity', 'job_id ou trace_id é inválido.', http_status=400)
    revision = int(payload.get('config_revision') or 0)
    if revision < 1:
        raise ArtifactError('configuration_required', 'O projeto precisa de uma configuração aprovada antes do build.', 'config_revision')
    services = normalize_services(payload.get('services'))
    blocked = [{'service': item['name'], **item['policy']} for item in services if item['policy']['status'] != 'ready']
    if blocked:
        raise ArtifactError('runtime_policy_blocked', 'Um ou mais serviços não possuem base homologada.', 'services', blocked)
    return {
        'job_id': job_id, 'project_slug': slug, 'ref': ref, 'archive_sha256': archive_sha,
        'config_revision': revision, 'config_digest': config_digest,
        'toolchain_digest': toolchain_digest, 'plan_digest': plan_digest,
        'services': services, 'trace_id': trace_id,
    }


def fetch_archive(slug: str, ref: str, expected_sha: str) -> bytes:
    if not FORJA_TOKEN:
        raise ArtifactError('forja_token_missing', 'O executor não possui credencial interna para archive.', http_status=503)
    query = urllib.parse.urlencode({'project_slug': slug, 'ref': ref})
    request = urllib.request.Request(
        FORJA_URL + '/project/archive?' + query,
        headers={'Authorization': 'Bearer ' + FORJA_TOKEN, 'X-CloudIF-Token': FORJA_TOKEN, 'Accept': 'application/x-tar'},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read(MAX_ARCHIVE + 1)
            header_sha = str(response.headers.get('X-Archive-SHA256') or '').strip().lower()
    except urllib.error.HTTPError as error:
        raise ArtifactError('archive_fetch_failed', 'O archive Forgejo não pôde ser obtido.', detail={'httpStatus': error.code}, http_status=502) from error
    if len(raw) > MAX_ARCHIVE:
        raise ArtifactError('archive_too_large', 'O archive excede 64 MiB.')
    actual = sha256(raw)
    if not hmac.compare_digest(actual, expected_sha) or (header_sha and not hmac.compare_digest(header_sha, expected_sha)):
        raise ArtifactError('archive_digest_mismatch', 'O archive mudou após o plano de build.', detail={'expected': expected_sha, 'actual': actual}, http_status=409)
    return raw


def safe_extract(raw: bytes, destination: Path) -> list[str]:
    archive_path = destination / 'source.tar'
    archive_path.write_bytes(raw)
    with tarfile.open(archive_path, 'r:*') as archive:
        members = archive.getmembers()
        if not members or len(members) > MAX_FILES:
            raise ArtifactError('archive_file_limit', 'O archive está vazio ou excede 25.000 entradas.')
        roots = {PurePosixPath(member.name).parts[0] for member in members if PurePosixPath(member.name).parts}
        strip_root = len(roots) == 1
        total = 0
        files: list[str] = []
        for member in members:
            path = PurePosixPath(member.name)
            parts = path.parts[1:] if strip_root else path.parts
            if not parts:
                continue
            if any(part in {'', '.', '..'} for part in parts) or member.issym() or member.islnk() or member.isdev():
                raise ArtifactError('unsafe_archive_entry', 'O archive contém caminhos, links ou dispositivos inseguros.')
            rel = '/'.join(parts)
            if rel.startswith('.git/') or PRIVATE_RE.search(rel):
                continue
            target = destination / 'source' / rel
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                continue
            total += int(member.size or 0)
            if total > MAX_UNPACKED:
                raise ArtifactError('archive_unpacked_limit', 'O archive excede 256 MiB descompactado.')
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = archive.extractfile(member)
            if stream is None:
                raise ArtifactError('archive_read_failed', 'Uma entrada do archive não pôde ser lida.')
            with target.open('wb') as handle:
                shutil.copyfileobj(stream, handle, length=1024 * 1024)
            os.chmod(target, 0o755 if rel.endswith('.sh') else 0o644)
            files.append(rel)
    archive_path.unlink(missing_ok=True)
    return sorted(files)


def run(command: list[str], timeout: int = 900, cwd: Path | None = None, capture: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(command, cwd=str(cwd) if cwd else None, text=True, stdout=subprocess.PIPE if capture else None, stderr=subprocess.STDOUT if capture else None, timeout=timeout)
    if result.returncode:
        output = (result.stdout or '')[-12000:]
        code = 'dependency_proxy_required' if any(text in output.lower() for text in ('network is unreachable', 'eai_again', 'enetwork', 'failed to fetch', 'unable to resolve')) else 'container_build_failed'
        raise ArtifactError(code, 'O build do container falhou.' if code == 'container_build_failed' else 'A instalação exige um registry de dependências interno; saída livre para internet permanece bloqueada.', detail={'command': command[:4], 'outputTail': output[-2000:]}, http_status=409)
    return result


def dockerfile_run(command: list[str] | None) -> str:
    if not command:
        return ''
    return 'RUN ' + json.dumps(command, ensure_ascii=False) + '\n'


def copy_hooks(source: Path, context: Path, hooks: list[str]) -> list[dict[str, Any]]:
    records = []
    hooks_root = context / 'hooks'
    for index, rel in enumerate(hooks):
        source_path = source / rel
        if not source_path.is_file() or source_path.is_symlink():
            raise ArtifactError('hook_script_not_found', f'O script {rel} não existe no snapshot.', 'hookScripts')
        raw = source_path.read_bytes()
        if len(raw) > 256 * 1024 or b'\x00' in raw:
            raise ArtifactError('invalid_hook_script', f'O script {rel} deve ser texto e ter até 256 KiB.', 'hookScripts')
        target = hooks_root / f'{index:02d}-{Path(rel).name}'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw); os.chmod(target, 0o755)
        records.append({'path': rel, 'sha256': sha256(raw), 'size': len(raw), 'imagePath': '/opt/cloudiff/hooks/' + target.name})
    return records


def hook_dockerfile_runs(hooks: list[dict[str, Any]], phase: str) -> str:
    lines=[]
    for hook in hooks:
        if hook.get('phase')==phase:
            lines.append('RUN '+json.dumps([hook['imagePath']],ensure_ascii=False))
    return ('\n'.join(lines)+'\n') if lines else ''


def scanner_images() -> tuple[str, str]:
    env = load_env(SCANNER_ENV)
    syft = env.get('SYFT_IMAGE', '')
    trivy = env.get('TRIVY_IMAGE', '')
    if '@sha256:' not in syft or '@sha256:' not in trivy:
        raise ArtifactError('scanner_images_not_pinned', 'As imagens Syft e Trivy devem estar fixadas por digest.', http_status=503)
    return syft, trivy


def scan_image(image: str, output_dir: Path, prefix: str) -> dict[str, Any]:
    syft, trivy = scanner_images()
    output_dir.mkdir(parents=True, exist_ok=True)
    sbom = output_dir / f'{prefix}-sbom.cdx.json'
    scan = output_dir / f'{prefix}-trivy.json'
    with sbom.open('wb') as handle:
        result = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '-v', '/var/run/docker.sock:/var/run/docker.sock', syft, image, '-o', 'cyclonedx-json'], stdout=handle, stderr=subprocess.PIPE, timeout=300)
    if result.returncode:
        raise ArtifactError('sbom_failed', 'A geração do SBOM falhou.', detail=(result.stderr or b'')[-1000:].decode(errors='replace'), http_status=502)
    with scan.open('wb') as handle:
        result = subprocess.run([
            'docker', 'run', '--rm', '--network', 'none',
            '-v', '/var/run/docker.sock:/var/run/docker.sock',
            '-v', f'{TRIVY_CACHE}:/root/.cache/trivy', trivy,
            'image', '--skip-db-update', '--scanners', 'vuln', '--format', 'json',
            '--severity', 'UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL', image,
        ], stdout=handle, stderr=subprocess.PIPE, timeout=420)
    if result.returncode:
        raise ArtifactError('scanner_failed', 'O scanner offline falhou.', detail=(result.stderr or b'')[-1000:].decode(errors='replace'), http_status=502)
    sbom_data = json.loads(sbom.read_text())
    scan_data = json.loads(scan.read_text())
    counts: dict[str, int] = {}
    for scan_result in scan_data.get('Results') or []:
        for vulnerability in scan_result.get('Vulnerabilities') or []:
            severity = str(vulnerability.get('Severity') or 'UNKNOWN').upper()
            counts[severity] = counts.get(severity, 0) + 1
    blocked = bool(counts.get('HIGH') or counts.get('CRITICAL'))
    return {
        'sbomPath': str(sbom), 'sbomSha256': sha256(sbom.read_bytes()),
        'sbomComponents': len(sbom_data.get('components') or []),
        'scannerPath': str(scan), 'scannerSha256': sha256(scan.read_bytes()),
        'scannerCounts': counts, 'scannerBlocked': blocked,
        'scannerPolicy': 'block-high-critical', 'scannerOfflineCache': True,
    }


def sign_provenance(output_dir: Path, provenance: dict[str, Any], prefix: str) -> dict[str, Any]:
    if not SIGNING_KEY.is_file() or not SIGNING_PUBLIC_KEY.is_file():
        raise ArtifactError('signing_key_missing', 'A chave de assinatura do executor não está configurada.', http_status=503)
    path = output_dir / f'{prefix}-provenance.json'
    signature = output_dir / f'{prefix}-provenance.sig'
    path.write_bytes(canonical(provenance))
    run(['openssl', 'pkeyutl', '-sign', '-rawin', '-inkey', str(SIGNING_KEY), '-in', str(path), '-out', str(signature)], timeout=30)
    run(['openssl', 'pkeyutl', '-verify', '-rawin', '-pubin', '-inkey', str(SIGNING_PUBLIC_KEY), '-in', str(path), '-sigfile', str(signature)], timeout=30)
    return {'provenancePath': str(path), 'provenanceSha256': sha256(path.read_bytes()), 'signaturePath': str(signature), 'signatureSha256': sha256(signature.read_bytes()), 'signatureVerified': True, 'signatureAlgorithm': 'Ed25519'}


def inspect_image(image: str) -> dict[str, Any]:
    data = json.loads(run(['docker', 'image', 'inspect', image], timeout=30).stdout)[0]
    config = data.get('Config') or {}
    return {
        'image': image, 'imageId': data.get('Id'), 'repoDigests': data.get('RepoDigests') or [],
        'user': config.get('User') or '', 'labels': config.get('Labels') or {},
        'created': data.get('Created'), 'size': data.get('Size'), 'immutableReference': data.get('Id'),
    }


def build_toolchain(request: dict[str, Any], service: dict[str, Any], source: Path, output_dir: Path) -> dict[str, Any]:
    hook_material=[]
    for item in service.get('hookSteps') or []:
        script=source/item['path']
        if not script.is_file() or script.is_symlink():
            raise ArtifactError('hook_script_not_found',f'O script {item["path"]} não existe no snapshot.','hookSteps')
        raw=script.read_bytes()
        if len(raw)>256*1024 or b'\x00' in raw:
            raise ArtifactError('invalid_hook_script',f'O script {item["path"]} deve ser texto e ter até 256 KiB.','hookSteps')
        hook_material.append({'phase':item['phase'],'path':item['path'],'sha256':sha256(raw)})
    material = {
        'project':request['project_slug'],'service':service['name'],
        'configRevision':request['config_revision'],'configDigest':request['config_digest'],
        'requestedToolchainDigest':request['toolchain_digest'],
        'runtime':service['runtime'],'version':service.get('version'),
        'hooks':[{'phase':item['phase'],'path':item['path'],'sha256':item['sha256']} for item in hook_material],
        'policy':service['policy'],'sourceArchiveBound':False,
    }
    effective=sha256(canonical(material))
    image = f"cloudif-toolchain/{request['project_slug']}-{service['name']}:{effective[:16]}"
    output = output_dir / service['name'] / 'toolchain'
    output.mkdir(parents=True, exist_ok=True)
    if subprocess.run(['docker', 'image', 'inspect', image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        built = False
        inspected_existing=inspect_image(image)
        if (inspected_existing.get('labels') or {}).get('org.cloudiff.toolchain-digest')!=effective:
            raise ArtifactError('immutable_image_conflict','A tag imutável da toolchain já existe com outro digest.',detail={'image':image})
        hooks=[{'phase':item['phase'],'path':item['path'],'sha256':item['sha256'],'imagePath':'/opt/cloudiff/hooks/'+f'{index:02d}-{Path(item["path"]).name}'} for index,item in enumerate(hook_material)]
    else:
        context = output / 'context'
        context.mkdir(parents=True, exist_ok=True)
        hooks = copy_hooks(source, context, [item['path'] for item in service.get('hookSteps') or []])
        for record,item in zip(hooks,service.get('hookSteps') or []):
            record['phase']=item['phase']
        if service['runtime']=='static' and hooks:
            raise ArtifactError('static_hook_runtime_required','Hooks em serviço estático exigem uma toolchain com runtime de scripts.')
        base = service['policy']['builder']
        dockerfile = [f'FROM {base}']
        dockerfile.append('LABEL ' + ' '.join([
            f'org.cloudiff.kind="toolchain"', f'org.cloudiff.project="{request["project_slug"]}"',
            f'org.cloudiff.service="{service["name"]}"', f'org.cloudiff.config-revision="{request["config_revision"]}"',
            f'org.cloudiff.config-digest="{request["config_digest"]}"', f'org.cloudiff.toolchain-digest="{effective}"',
        ]))
        if hooks:
            dockerfile.append('USER 0')
            dockerfile.append('COPY hooks/ /opt/cloudiff/hooks/')
        dockerfile.append('WORKDIR /workspace')
        pre=hook_dockerfile_runs(hooks,'preBuild').strip()
        post=hook_dockerfile_runs(hooks,'postBuild').strip()
        if pre: dockerfile.extend(pre.splitlines())
        if post: dockerfile.extend(post.splitlines())
        dockerfile.append('USER 65532:65532' if service['runtime'] == 'static' else 'USER node')
        (context / 'Dockerfile').write_text('\n'.join(dockerfile) + '\n')
        run(['docker', 'build', '--pull=false', '--network', 'none', '--no-cache=false', '-t', image, str(context)], timeout=900)
        built = True
    proof_command = ['docker', 'run', '--rm', '--network', 'none', '--read-only', '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', image]
    if service['runtime'] == 'node':
        proof_command += ['node', '--version']
        proof = run(proof_command, timeout=60).stdout.strip()
        if not proof.startswith('v24.'):
            raise ArtifactError('toolchain_runtime_proof_failed', 'A toolchain Node não executou Node 24.', detail=proof)
    else:
        proof = 'static-image-inspection-only'
    scan = scan_image(image, output, 'toolchain')
    if scan['scannerBlocked']:
        raise ArtifactError('toolchain_scanner_blocked', 'A toolchain contém vulnerabilidades HIGH ou CRITICAL.', detail=scan['scannerCounts'])
    inspected = inspect_image(image)
    provenance = {
        'kind': 'cloudiff-toolchain-v1', 'effectiveToolchainDigest': effective,
        'material': material, 'image': inspected, 'scan': {key: value for key, value in scan.items() if not key.endswith('Path')},
        'hooks': hooks, 'builtAt': int(time.time()), 'secretsIncluded': False,
    }
    signature = sign_provenance(output, provenance, 'toolchain')
    return {
        'service': service['name'], 'runtime': service['runtime'], 'version': service.get('version'),
        'effectiveToolchainDigest': effective, 'built': built, 'reused': not built,
        'image': inspected, 'hooks': hooks, 'runtimeProof': proof,
        **scan, **signature, 'secretsIncluded': False,
    }


def copy_context(source: Path, target: Path, exclude_paths: list[str] | None = None) -> None:
    if not source.is_dir() or source.is_symlink():
        raise ArtifactError('service_path_not_found', 'O diretório do serviço não existe no snapshot.')
    excluded={PurePosixPath(item).parts[0] for item in (exclude_paths or []) if item and item!='.'}
    total = 0; count = 0
    for current, dirs, files in os.walk(source, topdown=True, followlinks=False):
        dirs[:] = [name for name in dirs if name not in IGNORED and name not in excluded and not os.path.islink(os.path.join(current, name))]
        rel_current = Path(current).relative_to(source)
        for name in files:
            src = Path(current) / name
            if src.is_symlink() or not src.is_file():
                continue
            rel = (rel_current / name).as_posix()
            if PRIVATE_RE.search(rel):
                continue
            size = src.stat().st_size
            total += size; count += 1
            if total > MAX_UNPACKED or count > MAX_FILES:
                raise ArtifactError('service_context_limit', 'O contexto do serviço excede os limites de build.')
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def build_application(request: dict[str, Any], service: dict[str, Any], source: Path, toolchain: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output = output_dir / service['name'] / 'application'
    context = output / 'context'
    context.mkdir(parents=True, exist_ok=True)
    service_source = source if service['path'] == '.' else source / service['path']
    copy_context(service_source, context / 'source', service.get('excludePaths') or [])
    app_material = {
        'project': request['project_slug'], 'service': service['name'],
        'configRevision': request['config_revision'], 'configDigest': request['config_digest'],
        'archiveSha256': request['archive_sha256'], 'toolchainImageId': toolchain['image']['imageId'],
        'install': service.get('install'), 'build': service.get('build'), 'start': service.get('start'),
        'publish': service.get('publish'), 'port': service.get('port'), 'healthcheck': service.get('healthcheck'),
    }
    app_digest = sha256(canonical(app_material))
    image = f"cloudif-app/{request['project_slug']}-{service['name']}:{app_digest[:16]}"
    pre_hooks=hook_dockerfile_runs(toolchain.get('hooks') or [],'preBuild')
    post_hooks=hook_dockerfile_runs(toolchain.get('hooks') or [],'postBuild')
    if subprocess.run(['docker','image','inspect',image],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
        existing=inspect_image(image)
        if (existing.get('labels') or {}).get('org.cloudiff.application-digest')!=app_digest:
            raise ArtifactError('immutable_image_conflict','A tag imutável da aplicação já existe com outro digest.',detail={'image':image})
    if service['runtime'] == 'static':
        publish = service.get('publish') or '.'
        publish_path = context / 'source' if publish == '.' else context / 'source' / publish
        if not publish_path.is_dir():
            raise ArtifactError('publish_directory_missing', f'O diretório publicável {publish} não existe.', f'services.{service["name"]}.publish')
        site = context / 'site'; shutil.copytree(publish_path, site, dirs_exist_ok=True)
        for metadata in ('cloudiff.yaml','cloudiff.yml','Dockerfile','docker-compose.yml','docker-compose.yaml','compose.yml','compose.yaml'):
            target=site/metadata
            if target.is_file(): target.unlink()
        for hook in service.get('hookSteps') or []:
            hook_path=site/hook['path']
            if hook_path.is_file(): hook_path.unlink()
        dockerfile = f'''FROM {toolchain['image']['image']}\nLABEL org.cloudiff.kind="application" org.cloudiff.project="{request['project_slug']}" org.cloudiff.service="{service['name']}" org.cloudiff.config-revision="{request['config_revision']}" org.cloudiff.config-digest="{request['config_digest']}" org.cloudiff.archive-sha256="{request['archive_sha256']}" org.cloudiff.application-digest="{app_digest}"\nCOPY site/ /usr/share/nginx/html/\nUSER 65532:65532\nEXPOSE 8080\n'''
    elif service['runtime'] == 'node':
        install = dockerfile_run(service.get('install'))
        build = dockerfile_run(service.get('build'))
        publish = service.get('publish')
        if publish and not service.get('start'):
            dockerfile = f'''FROM {toolchain['image']['image']} AS build\nUSER node\nWORKDIR /workspace\nCOPY --chown=node:node source/ ./\n{pre_hooks}{install}{build}{post_hooks}FROM {STATIC_BASE}\nLABEL org.cloudiff.kind="application" org.cloudiff.project="{request['project_slug']}" org.cloudiff.service="{service['name']}" org.cloudiff.config-revision="{request['config_revision']}" org.cloudiff.config-digest="{request['config_digest']}" org.cloudiff.archive-sha256="{request['archive_sha256']}" org.cloudiff.application-digest="{app_digest}"\nCOPY --from=build /workspace/{publish} /usr/share/nginx/html/\nUSER 65532:65532\nEXPOSE 8080\n'''
        else:
            if not service.get('start') or not service.get('port'):
                raise ArtifactError('node_start_configuration_required', 'Serviços Node sem artefato estático exigem start e port.', f'services.{service["name"]}')
            runtime_args=service['start']
            if runtime_args[0] in {'node','nodejs'}:
                runtime_args=runtime_args[1:]
            if not runtime_args:
                raise ArtifactError('distroless_start_required','A imagem distroless exige um arquivo de entrada após node.',f'services.{service["name"]}.start')
            dockerfile = f'''FROM {toolchain['image']['image']} AS build
USER node
WORKDIR /workspace
COPY --chown=node:node source/ ./
{install}{build}FROM {service['policy']['runtimeImage']}
WORKDIR /app
COPY --from=build /workspace /app
LABEL org.cloudiff.kind="application" org.cloudiff.project="{request['project_slug']}" org.cloudiff.service="{service['name']}" org.cloudiff.config-revision="{request['config_revision']}" org.cloudiff.config-digest="{request['config_digest']}" org.cloudiff.archive-sha256="{request['archive_sha256']}" org.cloudiff.application-digest="{app_digest}"
USER 65532:65532
EXPOSE {service['port']}
CMD {json.dumps(runtime_args, ensure_ascii=False)}
'''
    else:
        raise ArtifactError('runtime_policy_blocked', 'O runtime não está habilitado para application build.')
    (context / 'Dockerfile').write_text(dockerfile)
    run(['docker', 'build', '--pull=false', '--network', 'none', '--no-cache=false', '-t', image, str(context)], timeout=1200)
    scan = scan_image(image, output, 'application')
    if scan['scannerBlocked']:
        raise ArtifactError('application_scanner_blocked', 'A imagem da aplicação contém vulnerabilidades HIGH ou CRITICAL.', detail=scan['scannerCounts'])
    inspected = inspect_image(image)
    expected_user = '65532:65532'
    if inspected['user'] not in {expected_user, '65532', '65532:65532'}:
        raise ArtifactError('application_user_policy_failed', 'A imagem final não usa o usuário não privilegiado esperado.', detail={'actual': inspected['user'], 'expected': expected_user})
    provenance = {
        'kind': 'cloudiff-application-v1', 'applicationDigest': app_digest,
        'material': app_material, 'image': inspected,
        'scan': {key: value for key, value in scan.items() if not key.endswith('Path')},
        'builtAt': int(time.time()), 'secretsIncluded': False,
    }
    signature = sign_provenance(output, provenance, 'application')
    return {
        'service': service['name'], 'runtime': service['runtime'],
        'containerPort': 8080 if service['runtime'] == 'static' or (service.get('publish') and not service.get('start')) else service.get('port'),
        'healthcheck': service.get('healthcheck') or ('/__cloudif_health' if service['runtime'] == 'static' else '/'),
        'applicationDigest': app_digest, 'image': inspected, **scan, **signature,
        'runtimeProof': 'deferred-to-isolated-preview', 'secretsIncluded': False,
    }


def build_multiservice(payload: Any) -> dict[str, Any]:
    request = validate_request(payload)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    job_dir = ARTIFACT_ROOT / request['job_id']
    if job_dir.exists():
        result_path = job_dir / 'result.json'
        if result_path.is_file():
            existing = json.loads(result_path.read_text())
            if existing.get('planDigest') == request['plan_digest']:
                existing['idempotent'] = True
                return existing
        raise ArtifactError('job_id_conflict', 'O job_id já foi usado com outro plano.', 'job_id', http_status=409)
    job_dir.mkdir(parents=True, mode=0o700)
    try:
        raw = fetch_archive(request['project_slug'], request['ref'], request['archive_sha256'])
        source_root = job_dir / 'source-work'
        source_root.mkdir(mode=0o700)
        files = safe_extract(raw, source_root)
        source = source_root / 'source'
        toolchains = []
        applications = []
        for service in request['services']:
            toolchain = build_toolchain(request, service, source, job_dir)
            toolchains.append(toolchain)
            applications.append(build_application(request, service, source, toolchain, job_dir))
        result = {
            'ok': True, 'jobId': request['job_id'], 'projectSlug': request['project_slug'],
            'configRevision': request['config_revision'], 'configDigest': request['config_digest'],
            'toolchainDigest': request['toolchain_digest'], 'archiveSha256': request['archive_sha256'],
            'planDigest': request['plan_digest'], 'serviceCount': len(request['services']),
            'toolchains': toolchains, 'applications': applications,
            'sourceFiles': len(files), 'sourceRemoved': True,
            'networkPolicy': 'none', 'scannerPolicy': 'block-high-critical',
            'signaturesVerified': all(item.get('signatureVerified') for item in toolchains + applications),
            'secretsIncluded': False, 'idempotent': False,
            'completedAt': int(time.time()),
        }
        shutil.rmtree(source_root, ignore_errors=True)
        (job_dir / 'result.json').write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
        os.chmod(job_dir / 'result.json', 0o600)
        return result
    except Exception:
        shutil.rmtree(job_dir / 'source-work', ignore_errors=True)
        raise
