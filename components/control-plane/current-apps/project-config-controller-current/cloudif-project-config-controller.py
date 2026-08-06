#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import re
import shlex
import sqlite3
import time
import urllib.parse
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema
import yaml

HOST = os.environ.get('CLOUDIF_PROJECT_CONFIG_HOST', '127.0.0.1')
PORT = int(os.environ.get('CLOUDIF_PROJECT_CONFIG_PORT', '18219'))
TOKEN = os.environ.get('CLOUDIF_PROJECT_CONFIG_TOKEN', '')
STATE_DB = Path(os.environ.get('CLOUDIF_PROJECT_CONFIG_DB', '/var/lib/cloudif/project-config/config.db'))
CONTROL_DB = Path(os.environ.get('CLOUDIF_PROJECT_SNAPSHOT_DB', '/var/lib/cloudif/control-plane/control-plane.db'))
SCHEMA_PATH = Path(os.environ.get('CLOUDIF_PROJECT_MANIFEST_SCHEMA', '/etc/cloudif/schemas/cloudiff-v1.schema.json'))
MAX_BODY = 2_097_152
SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
ENV_RE = re.compile(r'^[A-Z_][A-Z0-9_]{0,127}$')
SERVICE_RE = re.compile(r'^[a-z][a-z0-9-]{0,31}$')
SHELL_META_RE = re.compile(r'(?:&&|\|\||[;|<>`]|\$\(|\$\{|\n|\r)')
SECRET_NAME_RE = re.compile(r'(?i)(?:password|secret|token|private|jwt|service[_-]?role|api[_-]?key|access[_-]?key|smtp[_-]?pass|signing[_-]?key)')
SENSITIVE_VALUE_RE = re.compile(
    r'(?i)(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|'
    r'\bBearer\s+[A-Za-z0-9._~-]{12,}|'
    r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}|'
    r'[a-z][a-z0-9+.-]*://[^/@:]{1,128}:[^/@]{1,512}@|'
    r'(?:--|_)(?:password|secret|token|api[-_]?key)=\S+)'
)
TOOLCHAIN_HOOKS = {'preBuild', 'postBuild'}
RUNTIME_DEFAULTS = {'static': None, 'node': '24', 'php': '8.4', 'docker': None, 'compose': None}
RUNTIME_ALLOWED_VERSIONS = {
    'node': {'20', '22', '24'},
    'php': {'8.2', '8.3', '8.4'},
}
DOC_BASE = 'manifest-v1'


@dataclass
class ManifestResult:
    valid: bool
    normalized: dict[str, Any] | None
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    manifest_digest: str | None
    config_digest: str | None
    toolchain_digest: str | None
    service_graph: dict[str, Any] | None


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def now() -> int:
    return int(time.time())


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))


def db_conn() -> sqlite3.Connection:
    STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(STATE_DB, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute('pragma busy_timeout=20000')
    return conn


def init_db() -> None:
    conn = db_conn()
    conn.execute('pragma journal_mode=delete')
    conn.executescript('''
    create table if not exists projects(
      project_slug text primary key,
      current_revision integer not null default 0,
      manifest_digest text,
      config_digest text,
      toolchain_digest text,
      membership_revision integer not null default 0,
      observation_status text not null default 'unconfigured',
      updated_at integer not null
    );
    create table if not exists revisions(
      project_slug text not null,
      revision integer not null,
      source text not null,
      manifest_json text not null,
      overrides_json text not null,
      effective_json text not null,
      manifest_digest text not null,
      config_digest text not null,
      toolchain_digest text not null,
      created_by text not null,
      created_at integer not null,
      primary key(project_slug,revision)
    );
    create table if not exists plans(
      plan_digest text primary key,
      project_slug text not null,
      expected_revision integer not null,
      source text not null,
      manifest_json text not null,
      overrides_json text not null,
      effective_json text not null,
      manifest_digest text not null,
      config_digest text not null,
      toolchain_digest text not null,
      summary_json text not null,
      created_by text not null,
      created_at integer not null,
      expires_at integer not null,
      consumed_at integer
    );
    create table if not exists reconciliation_events(
      event_id text primary key,
      project_slug text not null,
      event_type text not null,
      config_revision integer not null,
      membership_revision integer not null,
      status text not null,
      details_json text not null,
      created_at integer not null,
      finished_at integer
    );
    create index if not exists idx_project_config_events on reconciliation_events(project_slug,created_at desc);
    create index if not exists idx_project_config_plans on plans(project_slug,created_at desc);
    ''')
    conn.commit()
    conn.close()
    os.chmod(STATE_DB, 0o600)


def project_exists(slug: str) -> dict[str, Any]:
    if not SLUG_RE.fullmatch(slug):
        raise ValueError('invalid_project_slug')
    conn = sqlite3.connect(f'file:{CONTROL_DB}?mode=ro', uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    row = conn.execute('select project_id,slug,name,owner,tenant,status from projects where slug=?', (slug,)).fetchone()
    conn.close()
    if not row:
        raise LookupError('project_not_found')
    return dict(row)


def looks_sensitive_value(name: str, value: Any) -> bool:
    if value in {None, ''}:
        return False
    return bool(SECRET_NAME_RE.search(str(name)) or (isinstance(value, str) and SENSITIVE_VALUE_RE.search(value)))


def sanitize_details(value: Any, key: str = '') -> Any:
    if SECRET_NAME_RE.search(str(key)):
        return '<redacted>'
    if isinstance(value, dict):
        return {str(name): sanitize_details(item, str(name)) for name, item in value.items()}
    if isinstance(value, list):
        return [sanitize_details(item, key) for item in value[:256]]
    if isinstance(value, str):
        if SENSITIVE_VALUE_RE.search(value):
            return '<redacted>'
        return value[:4096]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:4096]


def structured_error(code: str, message: str, field: str = '', expected_type: str = '', allowed: list[Any] | None = None, example: Any = None, documentation: str = DOC_BASE) -> dict[str, Any]:
    error = {
        'code': code,
        'message': message,
        'field': field,
        'expectedType': expected_type,
        'allowedValues': allowed or [],
        'documentation': documentation,
    }
    if example is not None:
        error['example'] = example
    return error


def parse_manifest(value: Any) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if isinstance(value, dict):
        return copy.deepcopy(value), []
    if not isinstance(value, str) or not value.strip():
        return None, [structured_error(
            'required_field_missing',
            'O campo manifest é obrigatório e deve conter YAML, JSON ou um objeto.',
            'manifest', 'string|object',
            example={'manifest': 'version: 1\nruntime: static\npublish: .'},
        )]
    if len(value.encode()) > 1_048_576:
        return None, [structured_error('manifest_too_large', 'O manifesto excede 1 MiB.', 'manifest', 'string')]
    try:
        parsed = yaml.safe_load(value)
    except yaml.YAMLError as exc:
        marker = getattr(exc, 'problem_mark', None)
        suffix = f' Linha {marker.line + 1}, coluna {marker.column + 1}.' if marker else ''
        return None, [structured_error('invalid_yaml', 'O manifesto YAML é inválido.' + suffix, 'manifest', 'valid YAML')]
    if not isinstance(parsed, dict):
        return None, [structured_error('manifest_root_not_object', 'A raiz do manifesto deve ser um objeto.', 'manifest', 'object')]
    return parsed, []


def schema_errors(document: dict[str, Any]) -> list[dict[str, Any]]:
    validator = jsonschema.Draft202012Validator(load_schema())
    errors: list[dict[str, Any]] = []
    for issue in sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path)):
        path = '.'.join(str(part) for part in issue.absolute_path)
        code = 'schema_validation_failed'
        expected = ''
        allowed: list[Any] = []
        example: Any = None
        if issue.validator == 'required':
            missing = next((name for name in issue.validator_value if name not in issue.instance), '')
            path = '.'.join(filter(None, [path, missing]))
            code = 'required_field_missing'
            expected = 'required field'
        elif issue.validator == 'type':
            code = 'invalid_field_type'
            expected = '|'.join(issue.validator_value) if isinstance(issue.validator_value, list) else str(issue.validator_value)
        elif issue.validator == 'enum':
            code = 'invalid_field_value'
            allowed = list(issue.validator_value)
        elif issue.validator == 'additionalProperties':
            code = 'unknown_field'
        elif issue.validator == 'pattern':
            code = 'invalid_field_format'
            expected = str(issue.validator_value)
        errors.append(structured_error(code, issue.message, path, expected, allowed, example))
    return errors


def safe_relative_path(value: str, field: str, errors: list[dict[str, Any]]) -> str:
    text = str(value or '.').replace('\\', '/').strip()
    path = PurePosixPath(text)
    if text.startswith('/') or '..' in path.parts or '\x00' in text:
        errors.append(structured_error('unsafe_path', 'O caminho deve ser relativo e não pode sair do repositório.', field, 'relative path'))
        return text
    normalized = str(path)
    return '.' if normalized in {'', '.'} else normalized


def normalize_command(value: Any, field: str, errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        args = [str(item) for item in value]
    elif isinstance(value, str):
        if SHELL_META_RE.search(value):
            errors.append(structured_error(
                'implicit_shell_not_allowed',
                'Comandos com operadores de shell não são permitidos diretamente. Use um script versionado e declare o shell.',
                field, 'argv array',
                example=['npm', 'run', 'build'],
                documentation='manifest-v1#commands',
            ))
            return None
        try:
            args = shlex.split(value, posix=True)
        except ValueError:
            errors.append(structured_error('invalid_command', 'O comando não pôde ser interpretado.', field, 'string|array'))
            return None
        warnings.append(structured_error(
            'command_string_normalized',
            'O comando em texto foi convertido para uma lista de argumentos. Prefira arrays no manifesto.',
            field, 'argv array',
            example=args,
            documentation='manifest-v1#commands',
        ))
    else:
        errors.append(structured_error('invalid_field_type', 'O comando deve ser texto ou lista de argumentos.', field, 'string|array'))
        return None
    if not args or any(not item or len(item) > 512 or '\x00' in item for item in args):
        errors.append(structured_error('invalid_command', 'O comando contém um argumento vazio ou inválido.', field, 'argv array'))
        return None
    if any(SENSITIVE_VALUE_RE.search(item) for item in args):
        errors.append(structured_error('secret_value_not_allowed', 'O comando contém um valor que parece ser segredo. Use uma referência de ambiente protegida.', field, 'argv array', documentation='manifest-v1#secrets'))
        return None
    return args


def normalize_hook(hook: dict[str, Any], field: str, errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    result = copy.deepcopy(hook)
    if 'run' in hook:
        result['run'] = normalize_command(hook.get('run'), field + '.run', errors, warnings)
    if result.get('script'):
        result['script'] = safe_relative_path(result['script'], field + '.script', errors)
    result.setdefault('timeoutSeconds', 120)
    result.setdefault('network', 'none')
    result.setdefault('continueOnError', False)
    return result


def shorthand_to_services(document: dict[str, Any]) -> dict[str, Any]:
    if 'services' in document:
        return copy.deepcopy(document)
    runtime = document.get('runtime')
    if document.get('dockerfile'):
        runtime = 'docker'
    elif document.get('compose'):
        runtime = 'compose'
    service: dict[str, Any] = {'path': document.get('path', '.'), 'runtime': runtime or 'static'}
    for key in ('publish', 'dockerfile', 'compose'):
        if key in document:
            service[key] = document[key]
    result = {key: copy.deepcopy(value) for key, value in document.items() if key not in {'runtime', 'path', 'publish', 'dockerfile', 'compose'}}
    result.setdefault('project', {})
    result['project'].setdefault('type', 'single-service')
    result['project'].setdefault('primaryService', 'web')
    result['services'] = {'web': service}
    return result


def find_cycle(graph: dict[str, list[str]]) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []
    def visit(node: str) -> list[str]:
        if node in visiting:
            start = stack.index(node)
            return stack[start:] + [node]
        if node in visited:
            return []
        visiting.add(node); stack.append(node)
        for dependency in graph.get(node, []):
            cycle = visit(dependency)
            if cycle:
                return cycle
        stack.pop(); visiting.remove(node); visited.add(node)
        return []
    for node in graph:
        cycle = visit(node)
        if cycle:
            return cycle
    return []


def normalize_manifest(document: dict[str, Any]) -> ManifestResult:
    errors = schema_errors(document)
    warnings: list[dict[str, Any]] = []
    if errors:
        return ManifestResult(False, None, errors, warnings, None, None, None, None)
    normalized = shorthand_to_services(document)
    project = normalized.setdefault('project', {})
    services: dict[str, dict[str, Any]] = normalized['services']
    project.setdefault('type', 'multi-service' if len(services) > 1 else 'single-service')
    project.setdefault('primaryService', next(iter(services)))
    normalized.setdefault('toolchain', {})
    normalized['toolchain'].setdefault('runtimes', {})
    normalized['toolchain'].setdefault('systemPackages', [])
    normalized['toolchain'].setdefault('rebuildOnChange', True)
    normalized.setdefault('environment', {'variables': {}, 'required': {}})
    normalized['environment'].setdefault('variables', {})
    normalized['environment'].setdefault('required', {})
    normalized.setdefault('hooks', {})
    for phase in ('preBuild', 'postBuild', 'preDeploy', 'postDeploy'):
        normalized['hooks'].setdefault(phase, [])
        normalized['hooks'][phase] = [normalize_hook(item, f'hooks.{phase}.{index}', errors, warnings) for index, item in enumerate(normalized['hooks'][phase])]
    graph: dict[str, list[str]] = {}
    ports: dict[int, str] = {}
    routes: dict[str, str] = {}
    all_required = set(normalized['environment']['required'])
    for name, service in services.items():
        service.setdefault('path', '.')
        service['path'] = safe_relative_path(service['path'], f'services.{name}.path', errors)
        runtime = service['runtime']
        service.setdefault('version', RUNTIME_DEFAULTS.get(runtime))
        if runtime in RUNTIME_ALLOWED_VERSIONS and service.get('version') not in RUNTIME_ALLOWED_VERSIONS[runtime]:
            errors.append(structured_error(
                'runtime_version_not_allowed',
                f'A versão {service.get("version")} não é permitida para {runtime}.',
                f'services.{name}.version', 'string', sorted(RUNTIME_ALLOWED_VERSIONS[runtime]),
            ))
        for command in ('install', 'build', 'start'):
            if command in service:
                service[command] = normalize_command(service[command], f'services.{name}.{command}', errors, warnings)
        for path_key in ('publish', 'dockerfile', 'compose'):
            if path_key in service:
                service[path_key] = safe_relative_path(service[path_key], f'services.{name}.{path_key}', errors)
        if runtime == 'static':
            service.setdefault('publish', '.')
            if service.get('start'):
                errors.append(structured_error('incompatible_field', 'Serviços estáticos não usam start.', f'services.{name}.start'))
        elif runtime == 'node':
            if not service.get('start') and not service.get('publish'):
                warnings.append(structured_error('node_start_or_publish_missing', 'O serviço Node não declara start nem diretório publicável.', f'services.{name}', documentation='manifest-v1#node'))
        elif runtime == 'php':
            service.setdefault('publish', 'public')
        elif runtime == 'docker':
            service.setdefault('dockerfile', 'Dockerfile')
        elif runtime == 'compose':
            service.setdefault('compose', 'docker-compose.yml')
        graph[name] = list(service.get('dependsOn') or [])
        for dependency in graph[name]:
            if dependency not in services:
                errors.append(structured_error('unknown_service_dependency', f'O serviço {dependency} não existe.', f'services.{name}.dependsOn', 'service name', sorted(services)))
            if dependency == name:
                errors.append(structured_error('self_dependency', 'Um serviço não pode depender de si mesmo.', f'services.{name}.dependsOn'))
        port = service.get('port')
        if port:
            if port in ports:
                errors.append(structured_error('duplicate_internal_port', f'A porta {port} também é usada por {ports[port]}.', f'services.{name}.port'))
            else:
                ports[port] = name
        for route in service.get('routes') or []:
            route_path = route['path'].rstrip('/') or '/'
            if route_path in routes:
                errors.append(structured_error('duplicate_route', f'A rota {route_path} também é usada por {routes[route_path]}.', f'services.{name}.routes'))
            else:
                routes[route_path] = name
        service.setdefault('dependsOn', [])
        service.setdefault('routes', [])
        service.setdefault('environment', {'required': [], 'variables': {}})
        service['environment'].setdefault('required', [])
        service['environment'].setdefault('variables', {})
        for variable, value in service['environment']['variables'].items():
            if looks_sensitive_value(variable, value):
                errors.append(structured_error(
                    'secret_value_not_allowed',
                    f'A variável {variable} do serviço {name} parece conter um segredo. Use secretRef em environment.required.',
                    f'services.{name}.environment.variables.{variable}', 'secret reference',
                    example={variable: {'secretRef': 'provider.secret_name'}},
                    documentation='manifest-v1#secrets',
                ))
        for variable in service['environment']['required']:
            if variable not in all_required and variable not in service['environment']['variables'] and variable not in normalized['environment']['variables']:
                errors.append(structured_error('required_variable_not_declared', f'A variável {variable} não possui valor nem referência declarada.', f'services.{name}.environment.required'))
    if project['primaryService'] not in services:
        errors.append(structured_error('primary_service_not_found', 'O serviço principal não existe.', 'project.primaryService', 'service name', sorted(services)))
    cycle = find_cycle(graph)
    if cycle:
        errors.append(structured_error('service_dependency_cycle', 'O grafo de serviços contém um ciclo: ' + ' → '.join(cycle), 'services.*.dependsOn'))
    for variable, value in normalized['environment']['variables'].items():
        if looks_sensitive_value(variable, value):
            errors.append(structured_error(
                'secret_value_not_allowed',
                f'A variável {variable} parece conter um segredo. Use secretRef em environment.required.',
                f'environment.variables.{variable}', 'secret reference',
                example={variable: {'secretRef': 'provider.secret_name'}},
                documentation='manifest-v1#secrets',
            ))
    for variable, spec in normalized['environment']['required'].items():
        for service_name in spec.get('services') or []:
            if service_name not in services:
                errors.append(structured_error('unknown_service_reference', f'O serviço {service_name} não existe.', f'environment.required.{variable}.services', 'service name', sorted(services)))
        spec.setdefault('required', True)
        spec.setdefault('services', list(services))
    if errors:
        return ManifestResult(False, normalized, errors, warnings, None, None, None, None)
    toolchain_material = {
        'runtimes': {
            name: {'runtime': service['runtime'], 'version': service.get('version')}
            for name, service in sorted(services.items())
        },
        'declaredRuntimes': normalized['toolchain']['runtimes'],
        'systemPackages': sorted(normalized['toolchain']['systemPackages']),
        'buildHooks': {phase: normalized['hooks'][phase] for phase in sorted(TOOLCHAIN_HOOKS)},
    }
    graph_summary = {
        'primaryService': project['primaryService'],
        'serviceCount': len(services),
        'services': [
            {
                'name': name,
                'path': service['path'],
                'runtime': service['runtime'],
                'version': service.get('version'),
                'port': service.get('port'),
                'publish': service.get('publish'),
                'healthcheck': service.get('healthcheck'),
                'dependsOn': service['dependsOn'],
            }
            for name, service in sorted(services.items())
        ],
        'edges': [
            {'from': name, 'to': dependency}
            for name, dependencies in sorted(graph.items())
            for dependency in dependencies
        ],
    }
    manifest_digest = digest(normalized)
    config_digest = digest({'manifest': normalized, 'variables': normalized['environment']})
    toolchain_digest = digest(toolchain_material)
    return ManifestResult(True, normalized, [], warnings, manifest_digest, config_digest, toolchain_digest, graph_summary)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def validate_overrides(overrides: Any) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if overrides is None:
        return errors
    if not isinstance(overrides, dict):
        return [structured_error('invalid_field_type', 'O campo overrides deve ser um objeto.', 'overrides', 'object')]
    allowed = {'environment', 'hooks', 'services', 'toolchain', 'project'}
    for key in overrides:
        if key not in allowed:
            errors.append(structured_error('override_field_not_allowed', f'O campo {key} não pode ser alterado pelo Portal.', f'overrides.{key}', allowed=sorted(allowed)))
    environment = overrides.get('environment') or {}
    variables = environment.get('variables') if isinstance(environment, dict) else None
    if isinstance(variables, dict):
        for name, value in variables.items():
            if not ENV_RE.fullmatch(str(name)):
                errors.append(structured_error('invalid_environment_name', f'O nome {name} é inválido.', f'overrides.environment.variables.{name}'))
            if looks_sensitive_value(str(name), value):
                errors.append(structured_error('secret_value_not_allowed', f'A variável {name} deve usar secretRef.', f'overrides.environment.variables.{name}'))
    return errors


def validate_manifest(manifest: Any, overrides: Any = None) -> ManifestResult:
    document, errors = parse_manifest(manifest)
    if errors or document is None:
        return ManifestResult(False, None, errors, [], None, None, None, None)
    override_errors = validate_overrides(overrides)
    if override_errors:
        return ManifestResult(False, None, override_errors, [], None, None, None, None)
    merged = deep_merge(document, overrides or {})
    return normalize_manifest(merged)


def current_project(slug: str) -> dict[str, Any]:
    project = project_exists(slug)
    conn = db_conn()
    row = conn.execute('select * from projects where project_slug=?', (slug,)).fetchone()
    revision = None
    if row and int(row['current_revision']) > 0:
        revision = conn.execute('select * from revisions where project_slug=? and revision=?', (slug, row['current_revision'])).fetchone()
    events = conn.execute('select * from reconciliation_events where project_slug=? order by created_at desc limit 20', (slug,)).fetchall()
    conn.close()
    if not row:
        return {
            'ok': True,
            'project': project,
            'configured': False,
            'currentRevision': 0,
            'membershipRevision': 0,
            'observationStatus': 'unconfigured',
            'events': [],
            'secretsExposed': False,
        }
    data = {
        'ok': True,
        'project': project,
        'configured': bool(revision),
        'currentRevision': int(row['current_revision']),
        'manifestDigest': row['manifest_digest'],
        'configDigest': row['config_digest'],
        'toolchainDigest': row['toolchain_digest'],
        'membershipRevision': int(row['membership_revision']),
        'observationStatus': row['observation_status'],
        'updatedAt': int(row['updated_at']),
        'events': [
            {
                'eventId': item['event_id'], 'eventType': item['event_type'], 'status': item['status'],
                'configRevision': int(item['config_revision']), 'membershipRevision': int(item['membership_revision']),
                'createdAt': int(item['created_at']), 'finishedAt': item['finished_at'],
                'details': json.loads(item['details_json'] or '{}'),
            }
            for item in events
        ],
        'secretsExposed': False,
    }
    if revision:
        effective = json.loads(revision['effective_json'])
        data['configuration'] = effective
        data['source'] = revision['source']
        data['createdBy'] = revision['created_by']
        data['createdAt'] = int(revision['created_at'])
    return data


def plan_configuration(slug: str, manifest: Any, overrides: Any, expected_revision: int, actor: str, source: str, ttl_seconds: int = 900) -> dict[str, Any]:
    project_exists(slug)
    current = current_project(slug)
    actual = int(current['currentRevision'])
    if expected_revision != actual:
        raise RuntimeError(f'revision_conflict:{actual}')
    result = validate_manifest(manifest, overrides)
    if not result.valid:
        return {'ok': False, 'error': {'code': 'validation_failed', 'message': 'A configuração contém erros.', 'violations': result.errors}, 'warnings': result.warnings}
    manifest_document, _ = parse_manifest(manifest)
    effective = result.normalized or {}
    summary = {
        'projectSlug': slug,
        'fromRevision': actual,
        'toRevision': actual + 1,
        'serviceCount': result.service_graph['serviceCount'] if result.service_graph else 0,
        'services': [item['name'] for item in result.service_graph['services']] if result.service_graph else [],
        'primaryService': result.service_graph['primaryService'] if result.service_graph else None,
        'toolchainChanged': current.get('toolchainDigest') != result.toolchain_digest,
        'configurationChanged': current.get('configDigest') != result.config_digest,
        'requiresToolchainBuild': current.get('toolchainDigest') != result.toolchain_digest,
        'requiresNewApplicationBuild': current.get('configDigest') != result.config_digest,
        'secretReferences': sorted((effective.get('environment') or {}).get('required', {})),
        'secretValuesIncluded': False,
    }
    material = {
        'projectSlug': slug,
        'expectedRevision': expected_revision,
        'source': source,
        'manifest': manifest_document,
        'overrides': overrides or {},
        'effective': effective,
        'manifestDigest': result.manifest_digest,
        'configDigest': result.config_digest,
        'toolchainDigest': result.toolchain_digest,
    }
    plan_digest = digest(material)
    created = now(); expires = created + max(60, min(int(ttl_seconds), 86400))
    conn = db_conn()
    conn.execute('''insert or replace into plans(plan_digest,project_slug,expected_revision,source,manifest_json,overrides_json,effective_json,manifest_digest,config_digest,toolchain_digest,summary_json,created_by,created_at,expires_at,consumed_at)
                    values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,null)''', (
        plan_digest, slug, expected_revision, source,
        json.dumps(manifest_document, ensure_ascii=False, separators=(',', ':')),
        json.dumps(overrides or {}, ensure_ascii=False, separators=(',', ':')),
        json.dumps(effective, ensure_ascii=False, separators=(',', ':')),
        result.manifest_digest, result.config_digest, result.toolchain_digest,
        json.dumps(summary, ensure_ascii=False, separators=(',', ':')),
        actor, created, expires,
    ))
    conn.commit(); conn.close()
    return {
        'ok': True, 'sideEffectFree': True, 'projectSlug': slug,
        'expectedRevision': expected_revision, 'nextRevision': expected_revision + 1,
        'planDigest': plan_digest, 'expiresAt': expires,
        'manifestDigest': result.manifest_digest, 'configDigest': result.config_digest,
        'toolchainDigest': result.toolchain_digest, 'serviceGraph': result.service_graph,
        'summary': summary, 'warnings': result.warnings,
        'approvalRequired': True, 'secretValuesIncluded': False,
    }


def apply_configuration(slug: str, plan_digest: str, expected_revision: int, actor: str) -> dict[str, Any]:
    project_exists(slug)
    conn = db_conn(); conn.execute('begin immediate')
    row = conn.execute('select * from plans where plan_digest=? and project_slug=?', (plan_digest, slug)).fetchone()
    if not row:
        conn.rollback(); conn.close(); raise LookupError('plan_not_found')
    if row['consumed_at']:
        existing = conn.execute('select * from revisions where project_slug=? and config_digest=? order by revision desc limit 1', (slug, row['config_digest'])).fetchone()
        conn.commit(); conn.close()
        if existing:
            return {'ok': True, 'idempotent': True, 'projectSlug': slug, 'revision': int(existing['revision']), 'configDigest': existing['config_digest'], 'toolchainDigest': existing['toolchain_digest']}
        raise RuntimeError('plan_already_consumed')
    if int(row['expires_at']) < now():
        conn.rollback(); conn.close(); raise RuntimeError('plan_expired')
    project_row = conn.execute('select * from projects where project_slug=?', (slug,)).fetchone()
    actual = int(project_row['current_revision']) if project_row else 0
    if expected_revision != actual or int(row['expected_revision']) != actual:
        conn.rollback(); conn.close(); raise RuntimeError(f'revision_conflict:{actual}')
    revision = actual + 1
    created = now()
    conn.execute('''insert into revisions(project_slug,revision,source,manifest_json,overrides_json,effective_json,manifest_digest,config_digest,toolchain_digest,created_by,created_at)
                    values(?,?,?,?,?,?,?,?,?,?,?)''', (
        slug, revision, row['source'], row['manifest_json'], row['overrides_json'], row['effective_json'],
        row['manifest_digest'], row['config_digest'], row['toolchain_digest'], actor, created,
    ))
    conn.execute('''insert into projects(project_slug,current_revision,manifest_digest,config_digest,toolchain_digest,membership_revision,observation_status,updated_at)
                    values(?,?,?,?,?,0,'observed',?)
                    on conflict(project_slug) do update set current_revision=excluded.current_revision,manifest_digest=excluded.manifest_digest,config_digest=excluded.config_digest,toolchain_digest=excluded.toolchain_digest,observation_status='observed',updated_at=excluded.updated_at''', (
        slug, revision, row['manifest_digest'], row['config_digest'], row['toolchain_digest'], created,
    ))
    event_id = 'evt_' + uuid.uuid4().hex
    details = {'mode': 'observation', 'configurationApplied': True, 'runtimeChanged': False, 'containersChanged': False, 'secretValuesIncluded': False}
    conn.execute('''insert into reconciliation_events(event_id,project_slug,event_type,config_revision,membership_revision,status,details_json,created_at,finished_at)
                    values(?,?,?, ?,0,'observed',?,?,?)''', (
        event_id, slug, 'configuration.applied', revision, json.dumps(details, separators=(',', ':')), created, created,
    ))
    conn.execute('update plans set consumed_at=? where plan_digest=?', (created, plan_digest))
    conn.commit(); conn.close()
    return {
        'ok': True, 'idempotent': False, 'projectSlug': slug, 'revision': revision,
        'manifestDigest': row['manifest_digest'], 'configDigest': row['config_digest'],
        'toolchainDigest': row['toolchain_digest'], 'eventId': event_id,
        'observationMode': True, 'runtimeChanged': False, 'containersChanged': False,
        'secretValuesIncluded': False,
    }


def record_event(slug: str, event_type: str, details: dict[str, Any]) -> dict[str, Any]:
    project_exists(slug)
    if event_type not in {'project.created', 'project.updated', 'project.member.added', 'project.member.removed', 'publication.created', 'publication.updated', 'manifest.changed', 'configuration.changed'}:
        raise ValueError('invalid_event_type')
    conn = db_conn(); conn.execute('begin immediate')
    row = conn.execute('select * from projects where project_slug=?', (slug,)).fetchone()
    revision = int(row['current_revision']) if row else 0
    membership = int(row['membership_revision']) if row else 0
    if event_type in {'project.member.added', 'project.member.removed'}:
        membership += 1
    event_id = 'evt_' + uuid.uuid4().hex
    safe_details = sanitize_details(details)
    safe_details.update({'mode': 'observation', 'runtimeChanged': False, 'containersChanged': False, 'secretValuesIncluded': False})
    if not row:
        conn.execute('insert into projects(project_slug,current_revision,membership_revision,observation_status,updated_at) values(?,0,? ,?,?)', (slug, membership, 'unconfigured', now()))
    else:
        conn.execute('update projects set membership_revision=?,updated_at=? where project_slug=?', (membership, now(), slug))
    created = now()
    conn.execute('''insert into reconciliation_events(event_id,project_slug,event_type,config_revision,membership_revision,status,details_json,created_at,finished_at)
                    values(?,?,?,?,?,'observed',?,?,?)''', (
        event_id, slug, event_type, revision, membership,
        json.dumps(safe_details, ensure_ascii=False, separators=(',', ':')), created, created,
    ))
    conn.commit(); conn.close()
    return {'ok': True, 'eventId': event_id, 'projectSlug': slug, 'eventType': event_type, 'configRevision': revision, 'membershipRevision': membership, 'observationMode': True, 'runtimeChanged': False, 'containersChanged': False}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_json(self, status: int, value: dict[str, Any]) -> None:
        raw = json.dumps(value, ensure_ascii=False, separators=(',', ':'), default=str).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def authenticated(self) -> bool:
        return bool(TOKEN) and hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + TOKEN)

    def read_body(self) -> dict[str, Any]:
        size = int(self.headers.get('Content-Length', '0') or '0')
        if size < 0 or size > MAX_BODY:
            raise ValueError('request_too_large')
        body = json.loads(self.rfile.read(size) if size else b'{}')
        if not isinstance(body, dict):
            raise ValueError('invalid_request')
        return body

    def do_GET(self) -> None:
        if self.path == '/health':
            try:
                conn = db_conn(); revisions = conn.execute('select count(*) from revisions').fetchone()[0]; conn.close()
                return self.send_json(200, {'ok': True, 'service': 'cloudif-project-config-controller', 'schemaVersion': 1, 'mode': 'observation', 'revisions': revisions, 'secretsExposed': False})
            except Exception:
                return self.send_json(503, {'ok': False, 'error': {'code': 'service_unavailable'}})
        if not self.authenticated():
            return self.send_json(401, {'ok': False, 'error': {'code': 'unauthorized', 'message': 'Autenticação interna obrigatória.'}})
        if self.path == '/v1/schema':
            return self.send_json(200, {'ok': True, 'schema': load_schema(), 'schemaVersion': 1, 'readOnly': True})
        match = re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/configuration', urllib.parse.urlparse(self.path).path)
        if match:
            try:
                return self.send_json(200, current_project(match.group(1)))
            except LookupError as exc:
                return self.send_json(404, {'ok': False, 'error': {'code': str(exc), 'message': 'Projeto não encontrado.'}})
            except ValueError as exc:
                return self.send_json(400, {'ok': False, 'error': {'code': str(exc)}})
        return self.send_json(404, {'ok': False, 'error': {'code': 'not_found'}})

    def do_POST(self) -> None:
        if not self.authenticated():
            return self.send_json(401, {'ok': False, 'error': {'code': 'unauthorized', 'message': 'Autenticação interna obrigatória.'}})
        try:
            body = self.read_body()
            if self.path == '/v1/manifest/validate':
                result = validate_manifest(body.get('manifest'), body.get('overrides'))
                if not result.valid:
                    return self.send_json(422, {'ok': False, 'valid': False, 'error': {'code': 'validation_failed', 'message': 'O manifesto contém erros.', 'violations': result.errors}, 'warnings': result.warnings, 'secretsExposed': False})
                return self.send_json(200, {
                    'ok': True, 'valid': True, 'normalized': result.normalized,
                    'manifestDigest': result.manifest_digest, 'configDigest': result.config_digest,
                    'toolchainDigest': result.toolchain_digest, 'serviceGraph': result.service_graph,
                    'warnings': result.warnings, 'schemaVersion': 1, 'readOnly': True,
                    'secretValuesIncluded': False,
                })
            match = re.fullmatch(r'/v1/projects/([a-z0-9][a-z0-9-]{0,62})/(configuration/plan|configuration/apply|events)', urllib.parse.urlparse(self.path).path)
            if not match:
                return self.send_json(404, {'ok': False, 'error': {'code': 'not_found'}})
            slug, operation = match.groups()
            actor = str(body.get('actor') or 'internal').strip()[:128]
            if operation == 'configuration/plan':
                expected = int(body.get('expectedRevision', 0))
                result = plan_configuration(slug, body.get('manifest'), body.get('overrides') or {}, expected, actor, str(body.get('source') or 'portal'), int(body.get('ttlSeconds') or 900))
                return self.send_json(200 if result.get('ok') else 422, result)
            if operation == 'configuration/apply':
                if not body.get('approved'):
                    return self.send_json(403, {'ok': False, 'error': {'code': 'approval_required', 'message': 'A configuração só pode ser aplicada após aprovação humana.'}})
                result = apply_configuration(slug, str(body.get('planDigest') or ''), int(body.get('expectedRevision', 0)), actor)
                return self.send_json(200, result)
            event_type = str(body.get('eventType') or '')
            details = body.get('details') or {}
            if not isinstance(details, dict):
                raise ValueError('invalid_event_details')
            return self.send_json(200, record_event(slug, event_type, details))
        except LookupError as exc:
            return self.send_json(404, {'ok': False, 'error': {'code': str(exc)}})
        except RuntimeError as exc:
            code = str(exc)
            status = 409 if code.startswith('revision_conflict') or code in {'plan_already_consumed'} else 410 if code == 'plan_expired' else 409
            return self.send_json(status, {'ok': False, 'error': {'code': code.split(':', 1)[0], 'message': code, 'currentRevision': int(code.split(':', 1)[1]) if code.startswith('revision_conflict:') else None}})
        except ValueError as exc:
            return self.send_json(400, {'ok': False, 'error': {'code': str(exc), 'message': 'A solicitação é inválida.'}})
        except json.JSONDecodeError:
            return self.send_json(400, {'ok': False, 'error': {'code': 'invalid_json', 'message': 'O corpo deve ser JSON válido.'}})
        except Exception:
            return self.send_json(500, {'ok': False, 'error': {'code': 'internal_error', 'message': 'Falha interna no controlador de configuração.'}})


if __name__ == '__main__':
    init_db()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
