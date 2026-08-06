#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

DEFAULT_CATALOG = Path(os.environ.get('CLOUDIF_TOOLCHAIN_CATALOG', '/etc/cloudif/toolchain-catalog-v1.json'))
NETWORK_COMMAND_RE = re.compile(r'(?im)(?:^|[;&|]\s*)(?:curl|wget|git\s+clone|npm\s+(?:install|ci)|pnpm\s+(?:install|add)|yarn\s+(?:install|add)|pip(?:3)?\s+install|composer\s+install|apt(?:-get)?\s+(?:update|install)|apk\s+add|dnf\s+install|yum\s+install)\b')
SECRET_RE = re.compile(r'(?i)(?:password|secret|token|api[_-]?key)\s*[:=]\s*[^\s"\']{8,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|://[^/@:]+:[^/@]+@')


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def load_catalog(path: Path | str | None = None) -> dict[str, Any]:
    target = Path(path or DEFAULT_CATALOG)
    if not target.is_file():
        repository_catalog = Path(__file__).resolve().parents[2] / 'etc/cloudif/toolchain-catalog-v1.json'
        if repository_catalog.is_file():
            target = repository_catalog
    data = json.loads(target.read_text(encoding='utf-8'))
    if int(data.get('version') or 0) != 1:
        raise ValueError('toolchain_catalog_version_unsupported')
    return data


def safe_relative_path(value: Any, field: str = 'toolchain.provision.script') -> str:
    text = str(value or '').replace('\\', '/').strip().strip('/')
    if not text or len(text) > 240 or '\x00' in text:
        raise ValueError(f'invalid_path:{field}')
    path = PurePosixPath(text)
    if path.is_absolute() or '..' in path.parts or any(part in {'', '.'} for part in path.parts):
        raise ValueError(f'unsafe_path:{field}')
    if path.parts[0] in {'.git', 'node_modules', 'vendor', '.cache', 'dist', 'build', 'out'}:
        raise ValueError(f'protected_path:{field}')
    return str(path)


def _item_name_version(raw: Any, default_version: str = 'system') -> tuple[str, str, dict[str, Any]]:
    if isinstance(raw, str):
        return raw.strip().lower(), default_version, {'name': raw.strip().lower(), 'version': default_version}
    if not isinstance(raw, dict):
        raise ValueError('invalid_catalog_item')
    item = dict(raw)
    name = str(item.get('name') or '').strip().lower()
    version = str(item.get('version') or default_version).strip()
    item['name'] = name; item['version'] = version
    return name, version, item


def _resolve_catalog_items(raw_items: Any, catalog_items: dict[str, Any], architecture: str, kind: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(raw_items, list):
        raise ValueError(f'invalid_{kind}_list')
    resolved: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(raw_items):
        name, version, requested = _item_name_version(raw)
        field = f'toolchain.{kind}.{index}'
        if not re.fullmatch(r'[a-z0-9][a-z0-9+._-]{0,79}', name):
            blockers.append({'code': 'invalid_catalog_name', 'field': field + '.name', 'name': name})
            continue
        key = (name, version)
        if key in seen:
            blockers.append({'code': 'duplicate_catalog_item', 'field': field, 'name': name, 'version': version})
            continue
        seen.add(key)
        entry = catalog_items.get(name)
        if not entry:
            blockers.append({'code': 'catalog_item_not_approved', 'field': field, 'name': name, 'version': version})
            continue
        versions = [str(item) for item in entry.get('versions') or []]
        if version not in versions:
            blockers.append({'code': 'catalog_version_not_approved', 'field': field + '.version', 'name': name, 'version': version, 'allowedValues': versions})
            continue
        architectures = [str(item) for item in entry.get('architectures') or []]
        if architecture not in architectures:
            blockers.append({'code': 'catalog_architecture_not_supported', 'field': field, 'name': name, 'architecture': architecture, 'allowedValues': architectures})
            continue
        install_method = str(requested.get('installMethod') or requested.get('source') or entry.get('installMethods', ['catalog'])[0])
        if kind == 'tools' and install_method not in (entry.get('installMethods') or []):
            blockers.append({'code': 'install_method_not_approved', 'field': field + '.installMethod', 'name': name, 'installMethod': install_method, 'allowedValues': entry.get('installMethods') or []})
            continue
        resolved_item = {
            'name': name, 'version': version, 'source': str(entry.get('source') or ''),
            'verify': list(entry.get('verify') or []), 'license': str(entry.get('license') or ''),
            'architectures': architectures, 'networkRequired': bool(entry.get('networkRequired')),
        }
        if kind == 'tools': resolved_item['installMethod'] = install_method
        if requested.get('checksum'):
            checksum = str(requested['checksum']).lower()
            if not re.fullmatch(r'sha256:[a-f0-9]{64}', checksum):
                blockers.append({'code': 'invalid_catalog_checksum', 'field': field + '.checksum', 'name': name})
                continue
            resolved_item['checksum'] = checksum
        if not resolved_item['license']:
            warnings.append({'code': 'catalog_license_missing', 'field': field, 'name': name})
        resolved.append(resolved_item)
    return sorted(resolved, key=lambda item: (item['name'], item['version'])), blockers, warnings


def validate_script(source_root: Path, provision: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    path = safe_relative_path(provision.get('script'))
    script = source_root / path
    if not script.is_file() or script.is_symlink():
        return {'ok': False, 'path': path, 'digest': '', 'size': 0, 'blockers': [{'code': 'provision_script_not_found', 'field': 'toolchain.provision.script', 'path': path}], 'warnings': [], 'networkCommandsDetected': False}
    raw = script.read_bytes()
    maximum = int((catalog.get('provisionPolicy') or {}).get('maxBytes') or 262144)
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if len(raw) > maximum or b'\x00' in raw:
        blockers.append({'code': 'invalid_provision_script', 'field': 'toolchain.provision.script', 'maximumBytes': maximum})
        return {'ok': False, 'path': path, 'digest': hashlib.sha256(raw).hexdigest(), 'size': len(raw), 'blockers': blockers, 'warnings': warnings, 'networkCommandsDetected': False}
    try: text = raw.decode('utf-8')
    except UnicodeDecodeError:
        blockers.append({'code': 'provision_script_not_utf8', 'field': 'toolchain.provision.script'})
        return {'ok': False, 'path': path, 'digest': hashlib.sha256(raw).hexdigest(), 'size': len(raw), 'blockers': blockers, 'warnings': warnings, 'networkCommandsDetected': False}
    shebang = text.splitlines()[0].strip() if text.splitlines() else ''
    allowed_shebangs = set((catalog.get('provisionPolicy') or {}).get('requiredShebangs') or [])
    if shebang not in allowed_shebangs:
        blockers.append({'code': 'provision_shebang_not_allowed', 'field': 'toolchain.provision.script', 'allowedValues': sorted(allowed_shebangs)})
    if not re.search(r'(?m)^\s*set\s+-[^\n]*e[^\n]*u[^\n]*(?:o\s+pipefail|x)', text) and 'set -euo pipefail' not in text:
        warnings.append({'code': 'provision_strict_mode_recommended', 'field': 'toolchain.provision.script', 'example': 'set -euo pipefail'})
    if SECRET_RE.search(text):
        blockers.append({'code': 'secret_value_in_provision_script', 'field': 'toolchain.provision.script'})
    for pattern in (catalog.get('provisionPolicy') or {}).get('forbiddenPatterns') or []:
        try: matched = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        except re.error:
            blockers.append({'code': 'catalog_forbidden_pattern_invalid', 'field': 'catalog.provisionPolicy.forbiddenPatterns'})
            continue
        if matched:
            blockers.append({'code': 'provision_command_forbidden', 'field': 'toolchain.provision.script', 'patternDigest': hashlib.sha256(pattern.encode()).hexdigest()[:16], 'line': text[:matched.start()].count('\n') + 1})
    syntax = subprocess.run(['/bin/bash', '-n', str(script)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    if syntax.returncode:
        blockers.append({'code': 'provision_syntax_invalid', 'field': 'toolchain.provision.script', 'detail': (syntax.stderr or '')[-500:]})
    network_detected = bool(NETWORK_COMMAND_RE.search(text))
    network = provision.get('network') or {'mode': 'none', 'domains': []}
    if isinstance(network, str): network = {'mode': network, 'domains': []}
    if str(network.get('mode') or 'none') == 'none' and network_detected:
        blockers.append({'code': 'provision_network_command_forbidden', 'field': 'toolchain.provision.network', 'message': 'O script usa comandos de rede, mas network está definido como none.'})
    return {'ok': not blockers, 'path': path, 'digest': hashlib.sha256(raw).hexdigest(), 'size': len(raw), 'blockers': blockers, 'warnings': warnings, 'networkCommandsDetected': network_detected, 'syntaxValid': syntax.returncode == 0}


def validate_toolchain(toolchain: Any, runtime: str, version: str | None, source_root: Path | None = None, catalog_path: Path | str | None = None) -> dict[str, Any]:
    catalog = load_catalog(catalog_path)
    configuration = dict(toolchain or {}) if isinstance(toolchain, dict) else {}
    declared_base_runtime = str(((configuration.get('base') or {}).get('runtime') or '')).lower()
    ignored_for_static = bool(str(runtime or '').lower() == 'static' and declared_base_runtime and declared_base_runtime != 'static')
    if ignored_for_static:
        configuration = {}
    architecture = str(configuration.get('architecture') or 'amd64')
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if ignored_for_static:
        warnings.append({'code': 'project_toolchain_not_applied_to_static_service', 'field': 'toolchain.base.runtime', 'serviceRuntime': 'static', 'declaredRuntime': declared_base_runtime})
    if architecture not in (catalog.get('architectures') or []):
        blockers.append({'code': 'architecture_not_approved', 'field': 'toolchain.architecture', 'architecture': architecture, 'allowedValues': catalog.get('architectures') or []})
    base = dict(configuration.get('base') or {})
    base_runtime = str(base.get('runtime') or runtime or '').lower()
    base_version = str(base.get('version') or version or ('default' if base_runtime == 'static' else ''))
    if base.get('runtime') and base_runtime != str(runtime or '').lower():
        blockers.append({'code': 'base_runtime_service_mismatch', 'field': 'toolchain.base.runtime', 'runtime': base_runtime, 'serviceRuntime': runtime})
    base_entry = (((catalog.get('baseImages') or {}).get(base_runtime) or {}).get('versions') or {}).get(base_version)
    if not base_entry:
        blockers.append({'code': 'base_image_not_approved', 'field': 'toolchain.base', 'runtime': base_runtime, 'version': base_version})
        base_entry = {}
    elif architecture not in (base_entry.get('architectures') or []):
        blockers.append({'code': 'base_image_architecture_not_supported', 'field': 'toolchain.base', 'architecture': architecture})
    requested_image = str(base.get('image') or '')
    catalog_image = str(base_entry.get('image') or '')
    if requested_image and requested_image != catalog_image:
        blockers.append({'code': 'base_image_not_catalog_pinned', 'field': 'toolchain.base.image', 'expected': catalog_image})
    expected_image_id = str(base_entry.get('imageId') or '')
    if base_entry and not re.fullmatch(r'sha256:[a-f0-9]{64}', expected_image_id):
        blockers.append({'code': 'base_image_identity_missing', 'field': 'catalog.baseImages', 'image': catalog_image})
    packages, package_blockers, package_warnings = _resolve_catalog_items(configuration.get('systemPackages') or [], catalog.get('systemPackages') or {}, architecture, 'systemPackages')
    tools, tool_blockers, tool_warnings = _resolve_catalog_items(configuration.get('tools') or [], catalog.get('tools') or {}, architecture, 'tools')
    blockers.extend(package_blockers + tool_blockers); warnings.extend(package_warnings + tool_warnings)
    provision = dict(configuration.get('provision') or {})
    if provision:
        timeout = int(provision.get('timeoutSeconds') or 600)
        maximum_timeout = int((catalog.get('provisionPolicy') or {}).get('maxTimeoutSeconds') or 1800)
        if not 1 <= timeout <= maximum_timeout:
            blockers.append({'code': 'provision_timeout_not_allowed', 'field': 'toolchain.provision.timeoutSeconds', 'maximum': maximum_timeout})
        provision['timeoutSeconds'] = timeout
        network = provision.get('network') or {'mode': 'none', 'domains': []}
        if isinstance(network, str): network = {'mode': network, 'domains': []}
        network.setdefault('domains', [])
        provision['network'] = network
    else:
        provision = {'script': '', 'timeoutSeconds': 0, 'network': {'mode': 'none', 'domains': []}}
    network_mode = str((provision.get('network') or {}).get('mode') or 'none')
    network_policy = (catalog.get('networkPolicies') or {}).get(network_mode)
    if not network_policy:
        blockers.append({'code': 'network_policy_unknown', 'field': 'toolchain.provision.network.mode', 'mode': network_mode})
    elif not network_policy.get('supported'):
        blockers.append({'code': 'network_policy_executor_unavailable', 'field': 'toolchain.provision.network.mode', 'mode': network_mode, 'requires': network_policy.get('requires')})
    if any(item.get('networkRequired') for item in packages + tools) and network_mode == 'none':
        blockers.append({'code': 'catalog_item_requires_network', 'field': 'toolchain', 'items': sorted(item['name'] for item in packages + tools if item.get('networkRequired'))})
    script_result = {'ok': True, 'path': '', 'digest': hashlib.sha256(b'').hexdigest(), 'size': 0, 'blockers': [], 'warnings': [], 'networkCommandsDetected': False, 'syntaxValid': True}
    if provision.get('script'):
        if source_root is None:
            script_result = {'ok': None, 'path': safe_relative_path(provision['script']), 'digest': '', 'size': None, 'blockers': [], 'warnings': [{'code': 'provision_script_requires_source_validation', 'field': 'toolchain.provision.script'}], 'networkCommandsDetected': None, 'syntaxValid': None}
        else:
            script_result = validate_script(source_root, provision, catalog)
            blockers.extend(script_result['blockers']); warnings.extend(script_result['warnings'])
    material = {
        'catalogVersion': int(catalog.get('version') or 0), 'architecture': architecture,
        'base': {
            'runtime': base_runtime, 'version': base_version, 'image': catalog_image,
            'imageId': base_entry.get('imageId'), 'runtimeImage': base_entry.get('runtimeImage'),
            'runtimeImageId': base_entry.get('runtimeImageId'), 'user': base_entry.get('user'),
        },
        'systemPackages': packages, 'tools': tools,
        'provision': {'path': script_result.get('path') or '', 'digest': script_result.get('digest') or '', 'timeoutSeconds': provision.get('timeoutSeconds') or 0, 'network': provision.get('network') or {'mode': 'none', 'domains': []}},
    }
    return {
        'ok': not blockers, 'buildable': not blockers and script_result.get('ok') is not None,
        'runtime': runtime, 'version': version, 'architecture': architecture,
        'base': material['base'], 'systemPackages': packages, 'tools': tools,
        'provision': provision, 'script': script_result,
        'blockers': blockers, 'warnings': warnings,
        'toolchainMaterial': material, 'toolchainDigest': digest(material),
        'catalogVersion': int(catalog.get('version') or 0), 'secretValuesIncluded': False,
    }
