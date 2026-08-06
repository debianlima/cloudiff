#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from typing import Any

import yaml

IGNORED_TECH_DIRS = {
    '.git', '.hg', '.svn', 'node_modules', 'vendor', 'dist', 'build', 'out', '.next', '.nuxt',
    'coverage', '.cache', '.parcel-cache', '.turbo', '.gradle', 'target', '__pycache__', '.venv',
    'venv', 'tmp', 'temp', 'logs', 'artifacts', '.idea', '.vscode',
}
PRIVATE_FILE_RE = re.compile(
    r'(?i)(?:^|/)(?:\.env(?:\..*)?|secrets?(?:\..*)?|credentials?(?:\..*)?|id_(?:rsa|ed25519)|'
    r'.*\.(?:pem|key|p12|pfx|jks|keystore))$'
)
PACKAGE_MAX = 512 * 1024
DETECTION_MAX_DEPTH = 8
DETECTION_MAX_FILES = 25000
COMPOSE_FILES = ('docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml')
NODE_FRAMEWORKS = (
    ('nextjs', {'next'}), ('nuxt', {'nuxt'}), ('angular', {'@angular/core'}),
    ('sveltekit', {'@sveltejs/kit'}), ('astro', {'astro'}), ('vite', {'vite'}),
    ('nestjs', {'@nestjs/core'}), ('fastify', {'fastify'}), ('express', {'express'}),
    ('vue', {'vue'}), ('react', {'react'}),
)
SUPPORTED_RUNTIMES = {'static', 'node', 'php', 'docker', 'compose'}


def path_allowed(rel: str, max_depth: int = DETECTION_MAX_DEPTH) -> bool:
    rel = rel.replace('\\', '/').strip('/')
    if not rel:
        return False
    parts = rel.split('/')
    if len(parts) > max_depth + 1:
        return False
    if any(part in IGNORED_TECH_DIRS for part in parts[:-1]):
        return False
    if PRIVATE_FILE_RE.search(rel):
        return False
    return True


def safe_json_file(run_dir: str, rel: str) -> dict[str, Any]:
    path = os.path.join(run_dir, rel)
    try:
        if os.path.getsize(path) > PACKAGE_MAX:
            return {}
        with open(path, encoding='utf-8') as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def safe_yaml_file(run_dir: str, rel: str) -> dict[str, Any]:
    path = os.path.join(run_dir, rel)
    try:
        if os.path.getsize(path) > PACKAGE_MAX:
            return {}
        with open(path, encoding='utf-8') as handle:
            value = yaml.safe_load(handle)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def service_name(path: str, technology: str, used: set[str]) -> str:
    frontend = {'static', 'vite', 'react', 'vue', 'angular', 'nextjs', 'nuxt', 'sveltekit', 'astro'}
    if path in {'', '.'}:
        base = 'web' if technology in frontend else technology
    else:
        base = os.path.basename(path.rstrip('/'))
    base = re.sub(r'[^a-z0-9-]+', '-', base.lower()).strip('-') or technology
    if not re.match(r'^[a-z]', base):
        base = 'service-' + base
    base = base[:32].rstrip('-') or 'service'
    candidate = base
    index = 2
    while candidate in used:
        suffix = '-' + str(index)
        candidate = base[:32-len(suffix)].rstrip('-') + suffix
        index += 1
    used.add(candidate)
    return candidate


def node_version(value: object) -> str | None:
    match = re.search(r'(?<!\d)(20|22|24)(?!\d)', str(value or ''))
    return match.group(1) if match else None


def node_component(run_dir: str, rel: str, visible: set[str]) -> dict[str, Any]:
    directory = os.path.dirname(rel) or '.'
    model = safe_json_file(run_dir, rel)
    dependencies: set[str] = set()
    for key in ('dependencies', 'devDependencies', 'peerDependencies'):
        values = model.get(key) or {}
        if isinstance(values, dict):
            dependencies.update(str(name) for name in values)
    technology = 'node'
    for label, markers in NODE_FRAMEWORKS:
        if dependencies & markers:
            technology = label
            break
    scripts = model.get('scripts') if isinstance(model.get('scripts'), dict) else {}
    lockfiles = {
        'npm': 'package-lock.json', 'pnpm': 'pnpm-lock.yaml',
        'yarn': 'yarn.lock', 'bun': 'bun.lockb',
    }
    package_manager = None
    install = None
    evidence = [rel]
    for manager, marker in lockfiles.items():
        candidate = marker if directory == '.' else directory + '/' + marker
        if candidate in visible:
            package_manager = manager
            install = {
                'npm': ['npm', 'ci'],
                'pnpm': ['pnpm', 'install', '--frozen-lockfile'],
                'yarn': ['yarn', 'install', '--immutable'],
                'bun': ['bun', 'install', '--frozen-lockfile'],
            }[manager]
            evidence.append(candidate)
            break
    if package_manager is None:
        declared = str(model.get('packageManager') or '').split('@', 1)[0]
        if declared in lockfiles:
            package_manager = declared
    manager = package_manager or 'npm'
    build = [manager, 'run', 'build'] if 'build' in scripts else None
    start = [manager, 'run', 'start'] if 'start' in scripts else None
    api_like = technology in {'express', 'fastify', 'nestjs'} or ('start' in scripts and technology == 'node')
    publish = None
    if technology in {'vite', 'react', 'vue', 'angular', 'sveltekit', 'astro'}:
        publish = 'dist'
    elif technology == 'nextjs' and 'export' in scripts:
        publish = 'out'
    workspaces = model.get('workspaces')
    if isinstance(workspaces, dict):
        workspaces = workspaces.get('packages')
    if not isinstance(workspaces, list):
        workspaces = []
    engines = model.get('engines') if isinstance(model.get('engines'), dict) else {}
    return {
        'path': directory,
        'technology': technology,
        'runtime': 'node',
        'version': node_version(engines.get('node')),
        'packageManager': package_manager,
        'install': install,
        'build': build,
        'start': start,
        'port': 3000 if api_like or technology in {'nextjs', 'nuxt'} else None,
        'healthcheck': '/health' if api_like else '/',
        'publish': publish,
        'workspaces': [str(item) for item in workspaces[:64]],
        'dependencies': sorted(dependencies)[:200],
        'evidence': evidence,
        'confidence': 0.98 if technology != 'node' else 0.90,
    }


def php_component(run_dir: str, rel: str) -> dict[str, Any]:
    directory = os.path.dirname(rel) or '.'
    model = safe_json_file(run_dir, rel)
    require = model.get('require') if isinstance(model.get('require'), dict) else {}
    technology = 'php'
    if 'laravel/framework' in require:
        technology = 'laravel'
    elif 'symfony/framework-bundle' in require:
        technology = 'symfony'
    platform = ((model.get('config') or {}).get('platform') or {}) if isinstance(model.get('config'), dict) else {}
    version = str(platform.get('php') or '') or None
    if version:
        match = re.search(r'(8\.[234])', version)
        version = match.group(1) if match else None
    public_dir = 'public' if os.path.isdir(os.path.join(run_dir, directory, 'public')) else '.'
    return {
        'path': directory, 'technology': technology, 'runtime': 'php', 'version': version,
        'install': ['composer', 'install', '--no-dev', '--no-interaction', '--prefer-dist'],
        'build': None, 'start': None, 'port': None, 'healthcheck': '/', 'publish': public_dir,
        'dependencies': sorted(str(name) for name in require)[:200],
        'evidence': [rel], 'confidence': 0.97,
    }


def compose_component(run_dir: str, rel: str) -> dict[str, Any]:
    model = safe_yaml_file(run_dir, rel)
    services = model.get('services') if isinstance(model.get('services'), dict) else {}
    return {
        'path': os.path.dirname(rel) or '.', 'technology': 'docker-compose', 'runtime': 'compose',
        'version': None, 'compose': os.path.basename(rel),
        'serviceNames': sorted(str(name) for name in services)[:64],
        'install': None, 'build': None, 'start': None, 'port': None, 'healthcheck': None,
        'publish': None, 'dependencies': [], 'evidence': [rel], 'confidence': 0.99,
    }


def manifest_service(component: dict[str, Any]) -> dict[str, Any] | None:
    runtime = component.get('runtime')
    if runtime not in SUPPORTED_RUNTIMES:
        return None
    service: dict[str, Any] = {'path': component.get('path') or '.', 'runtime': runtime}
    if runtime in {'node', 'php'}:
        service['version'] = component.get('version') or ('24' if runtime == 'node' else '8.4')
    for key in ('install', 'build', 'start', 'publish', 'port'):
        if component.get(key) is not None:
            service[key] = component[key]
    if component.get('healthcheck') and runtime not in {'static', 'docker', 'compose'}:
        service['healthcheck'] = {'path': component['healthcheck']}
    if runtime == 'docker':
        service['dockerfile'] = component.get('dockerfile') or 'Dockerfile'
    if runtime == 'compose':
        service['compose'] = component.get('compose') or 'docker-compose.yml'
    return service


def detect_components(run_dir: str, files: list[str], max_depth: int = DETECTION_MAX_DEPTH, max_files: int = DETECTION_MAX_FILES) -> dict[str, Any]:
    visible_list = [rel for rel in files if path_allowed(rel, max_depth)][:max_files]
    visible = set(visible_list)
    ignored_count = len(files) - len(visible_list)
    components: list[dict[str, Any]] = []
    component_dirs: set[str] = set()
    for rel in sorted(visible):
        base = os.path.basename(rel)
        directory = os.path.dirname(rel) or '.'
        if base == 'package.json':
            components.append(node_component(run_dir, rel, visible)); component_dirs.add(directory)
        elif base == 'composer.json':
            components.append(php_component(run_dir, rel)); component_dirs.add(directory)
        elif base in COMPOSE_FILES:
            components.append(compose_component(run_dir, rel)); component_dirs.add(directory)
        elif base == 'Dockerfile' or base.startswith('Dockerfile.'):
            components.append({
                'path': directory, 'technology': 'dockerfile', 'runtime': 'docker', 'version': None,
                'dockerfile': base, 'install': None, 'build': None, 'start': None, 'port': None,
                'healthcheck': None, 'publish': None, 'dependencies': [], 'evidence': [rel], 'confidence': 0.99,
            }); component_dirs.add(directory)
    for rel in sorted(visible):
        if os.path.basename(rel).lower() != 'index.html':
            continue
        directory = os.path.dirname(rel) or '.'
        if directory in component_dirs:
            continue
        components.append({
            'path': directory, 'technology': 'static', 'runtime': 'static', 'version': None,
            'install': None, 'build': None, 'start': None, 'port': None, 'healthcheck': '/',
            'publish': '.', 'dependencies': [], 'evidence': [rel], 'confidence': 0.96,
        }); component_dirs.add(directory)
    for rel in sorted(visible):
        base = os.path.basename(rel)
        directory = os.path.dirname(rel) or '.'
        if directory in component_dirs:
            continue
        if base in {'pyproject.toml', 'requirements.txt', 'setup.py'}:
            components.append({
                'path': directory, 'technology': 'python', 'runtime': 'python', 'version': None,
                'install': None, 'build': None, 'start': None, 'port': None, 'healthcheck': None,
                'publish': None, 'dependencies': [], 'evidence': [rel], 'confidence': 0.86,
                'supported': False,
            }); component_dirs.add(directory)
    used: set[str] = set()
    components.sort(key=lambda item: (item['path'] != '.', item['path'], item['technology']))
    for component in components:
        component['suggestedName'] = service_name(component['path'], component['technology'], used)
        component.setdefault('supported', component['runtime'] in SUPPORTED_RUNTIMES)
    supported = [item for item in components if item.get('supported')]
    frontend = {'static', 'vite', 'react', 'vue', 'angular', 'nextjs', 'nuxt', 'sveltekit', 'astro'}
    primary = next((item['suggestedName'] for item in supported if item['path'] == '.' and item['technology'] in frontend), None)
    if primary is None and supported:
        primary = supported[0]['suggestedName']
    services: dict[str, Any] = {}
    for component in supported:
        service = manifest_service(component)
        if service:
            services[component['suggestedName']] = service
    proposal = None
    if services:
        proposal = {
            'version': 1,
            'project': {'type': 'multi-service' if len(services) > 1 else 'single-service', 'primaryService': primary},
            'services': services,
        }
    manifest_path = next((rel for rel in visible_list if rel in {'cloudiff.yaml', 'cloudiff.yml'}), None)
    warnings: list[dict[str, Any]] = []
    if len(components) > 1:
        warnings.append({'code': 'multi_service_detected', 'message': f'{len(components)} componentes foram encontrados. Revise o manifesto antes do build.'})
    unsupported = [item['suggestedName'] for item in components if not item.get('supported')]
    if unsupported:
        warnings.append({'code': 'unsupported_runtime_detected', 'message': 'Há componentes ainda não suportados pelo schema v1.', 'services': unsupported})
    return {
        'projectType': 'multi-service' if len(components) > 1 else 'single-service' if components else 'unknown',
        'componentCount': len(components),
        'components': components,
        'primaryService': primary,
        'manifestPath': manifest_path,
        'manifestProposal': proposal,
        'requiresHumanReview': bool(len(components) > 1 or unsupported or not components),
        'warnings': warnings,
        'limits': {
            'maxDepth': max_depth, 'maxFiles': max_files,
            'filesConsidered': len(visible_list), 'filesIgnored': ignored_count,
            'truncated': len([rel for rel in files if path_allowed(rel, max_depth)]) > max_files,
        },
        'ignoredDirectories': sorted(IGNORED_TECH_DIRS),
        'privateFilesExcluded': True,
        'sideEffectFree': True,
    }
