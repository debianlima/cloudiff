#!/usr/bin/env python3
from __future__ import annotations

import base64
import difflib
import hashlib
import json
import os
import re
import secrets
import time
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from cloudif_multitech_detector import IGNORED_TECH_DIRS, PRIVATE_FILE_RE

WORKSPACE_RE = re.compile(r'^ws_[a-f0-9]{24}$')
SHA_RE = re.compile(r'^[a-f0-9]{64}$')
MAX_CHANGES = 100
MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_EXISTING_FILE_BYTES = 64 * 1024 * 1024
MAX_PATH = 240
MAX_DIFF_LINES = 4000
DEFAULT_TTL = 3600
ALLOWED_OPERATIONS = {'create', 'update', 'delete', 'mkdir'}


class ChangeSetError(ValueError):
    def __init__(self, code: str, message: str, field: str = '', example: Any = None):
        super().__init__(code)
        self.code = code
        self.message = message
        self.field = field
        self.example = example

    def as_dict(self) -> dict[str, Any]:
        result = {
            'code': self.code,
            'message': self.message,
            'field': self.field,
            'documentation': 'workspace-change-set-v1',
        }
        if self.example is not None:
            result['example'] = self.example
        return result


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def change_set_digest(project_slug: str, ref: str, archive_sha256: str, title: str, description: str, changes: list[dict[str, Any]]) -> str:
    return sha256(canonical({
        'version': 1,
        'project_slug': project_slug,
        'ref': ref,
        'archive_sha256': archive_sha256,
        'title': title,
        'description': description,
        'changes': changes,
    }))


def normalize_path(value: Any, field: str) -> str:
    text = str(value or '').replace('\\', '/').strip().strip('/')
    if not text or len(text) > MAX_PATH or '\x00' in text:
        raise ChangeSetError('invalid_path', 'O caminho deve ser relativo e ter até 240 caracteres.', field, 'frontend/src/main.ts')
    path = PurePosixPath(text)
    if path.is_absolute() or '..' in path.parts or any(part in {'', '.'} for part in path.parts):
        raise ChangeSetError('unsafe_path', 'O caminho não pode ser absoluto nem sair do repositório.', field, 'frontend/src/main.ts')
    if path.parts[0] == '.git' or any(part in IGNORED_TECH_DIRS for part in path.parts[:-1]):
        raise ChangeSetError('protected_path', 'O caminho pertence a uma área protegida, dependência ou artefato gerado.', field)
    if PRIVATE_FILE_RE.search(text):
        raise ChangeSetError('private_file_path', 'Arquivos privados ou de credenciais não podem entrar no change set.', field)
    return str(path)


def decode_content(value: Any, field: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ChangeSetError('required_field_missing', 'O campo content_base64 é obrigatório para create e update.', field, 'dmVyc2lvbjogMQo=')
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ChangeSetError('invalid_base64', 'O conteúdo deve ser base64 válido.', field) from exc
    if len(raw) > MAX_FILE_BYTES:
        raise ChangeSetError('file_too_large', 'Cada arquivo pode ter no máximo 256 KiB.', field)
    if b'\x00' in raw:
        raise ChangeSetError('binary_content_not_allowed', 'A primeira versão aceita somente arquivos textuais.', field)
    try:
        raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ChangeSetError('invalid_utf8', 'O conteúdo deve ser UTF-8 válido.', field) from exc
    return raw


def normalize_changes(changes: Any, artifact_resolver: Callable[[str], dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(changes, list) or not changes:
        raise ChangeSetError(
            'required_field_missing',
            'O campo changes deve conter ao menos uma alteração.',
            'changes',
            [{'operation': 'create', 'path': 'cloudiff.yaml', 'content_base64': 'dmVyc2lvbjogMQo='}],
        )
    if len(changes) > MAX_CHANGES:
        raise ChangeSetError('too_many_changes', 'Um change set pode conter no máximo 100 operações.', 'changes')
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    total = 0
    for index, raw_change in enumerate(changes):
        field = f'changes.{index}'
        if not isinstance(raw_change, dict):
            raise ChangeSetError('invalid_field_type', 'Cada alteração deve ser um objeto.', field)
        operation = str(raw_change.get('operation') or '').strip().lower()
        if operation not in ALLOWED_OPERATIONS:
            raise ChangeSetError('invalid_operation', 'A operação deve ser create, update, delete ou mkdir.', field + '.operation', sorted(ALLOWED_OPERATIONS))
        path = normalize_path(raw_change.get('path'), field + '.path')
        effective_path = path.rstrip('/') + '/.gitkeep' if operation == 'mkdir' else path
        if effective_path in seen:
            raise ChangeSetError('duplicate_path', f'O caminho {effective_path} aparece mais de uma vez.', field + '.path')
        seen.add(effective_path)
        expected = str(raw_change.get('expected_sha256') or '').strip().lower()
        if operation in {'update', 'delete'} and not SHA_RE.fullmatch(expected):
            raise ChangeSetError('expected_sha256_required', 'Update e delete exigem expected_sha256 com 64 caracteres hexadecimais.', field + '.expected_sha256')
        if operation in {'create', 'mkdir'} and expected:
            raise ChangeSetError('incompatible_field', 'Create e mkdir não aceitam expected_sha256.', field + '.expected_sha256')
        item: dict[str, Any] = {'operation': operation, 'path': path}
        if operation in {'create', 'update'}:
            encoded = raw_change.get('content_base64')
            artifact_id = str(raw_change.get('artifact_id') or '').strip()
            if bool(encoded) == bool(artifact_id):
                raise ChangeSetError('content_source_required', 'Create e update exigem exatamente um de content_base64 ou artifact_id.', field, {'content_base64':'... ou ...','artifact_id':'art_...'} )
            if artifact_id:
                if artifact_resolver is None:
                    raise ChangeSetError('artifact_resolver_unavailable', 'artifact_id não está disponível neste contexto.', field + '.artifact_id')
                try: artifact = artifact_resolver(artifact_id)
                except ChangeSetError: raise
                except Exception as exc:
                    code = getattr(exc, 'code', 'artifact_invalid')
                    message = getattr(exc, 'message', 'O artifact_id não pôde ser validado.')
                    raise ChangeSetError(str(code), str(message), field + '.artifact_id') from exc
                size = int(artifact.get('size') or 0); digest = str(artifact.get('sha256') or '')
                if not SHA_RE.fullmatch(digest) or size < 0:
                    raise ChangeSetError('artifact_metadata_invalid', 'O artefato selado retornou metadados inválidos.', field + '.artifact_id')
                total += size
                item.update({'artifact_id':artifact_id,'content_sha256':digest,'size':size})
            else:
                content = decode_content(encoded, field + '.content_base64')
                total += len(content)
                item['content_base64'] = base64.b64encode(content).decode()
                item['content_sha256'] = sha256(content)
                item['size'] = len(content)
            if total > MAX_TOTAL_BYTES:
                raise ChangeSetError('change_set_too_large', 'O conteúdo total referenciado pelo change set pode ter no máximo 128 MiB.', 'changes')
        elif operation == 'mkdir':
            content = b''
            item['effective_path'] = effective_path
            item['content_base64'] = ''
            item['content_sha256'] = sha256(content)
            item['size'] = 0
        else:
            item['expected_sha256'] = expected
        if operation == 'update':
            item['expected_sha256'] = expected
        normalized.append(item)
    return normalized, total


def _read_file(root: str, rel: str) -> bytes | None:
    path = Path(root) / rel
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise ChangeSetError('invalid_target_type', 'O caminho deve apontar para um arquivo regular.', rel)
    raw = path.read_bytes()
    if len(raw) > MAX_EXISTING_FILE_BYTES:
        raise ChangeSetError('existing_file_too_large', 'O arquivo existente excede 64 MiB.', rel)
    return raw


def _write_file(root: str, rel: str, content: bytes) -> None:
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def apply_changes(root: str, changes: list[dict[str, Any]], artifact_reader: Callable[[str, str, int], bytes] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    applied: list[dict[str, Any]] = []
    diff_lines: list[str] = []
    for item in changes:
        operation = item['operation']
        requested_path = item['path']
        path = item.get('effective_path') or requested_path
        before = _read_file(root, path)
        if operation in {'create', 'mkdir'}:
            if before is not None:
                raise ChangeSetError('path_already_exists', f'O caminho {path} já existe.', requested_path)
            if item.get('artifact_id'):
                if artifact_reader is None: raise ChangeSetError('artifact_reader_unavailable', 'O conteúdo do artefato não está disponível.', requested_path)
                after = artifact_reader(str(item['artifact_id']), str(item['content_sha256']), int(item['size']))
            else:
                after = base64.b64decode(item.get('content_base64') or '')
            _write_file(root, path, after)
        elif operation == 'update':
            if before is None:
                raise ChangeSetError('file_not_found', f'O arquivo {path} não existe para atualização.', requested_path)
            actual = sha256(before)
            if actual != item['expected_sha256']:
                raise ChangeSetError('hash_mismatch', f'O arquivo {path} mudou desde o snapshot.', requested_path, {'actual_sha256': actual})
            if item.get('artifact_id'):
                if artifact_reader is None: raise ChangeSetError('artifact_reader_unavailable', 'O conteúdo do artefato não está disponível.', requested_path)
                after = artifact_reader(str(item['artifact_id']), str(item['content_sha256']), int(item['size']))
            else:
                after = base64.b64decode(item['content_base64'])
            _write_file(root, path, after)
        else:
            if before is None:
                raise ChangeSetError('file_not_found', f'O arquivo {path} não existe para remoção.', requested_path)
            actual = sha256(before)
            if actual != item['expected_sha256']:
                raise ChangeSetError('hash_mismatch', f'O arquivo {path} mudou desde o snapshot.', requested_path, {'actual_sha256': actual})
            after = None
            (Path(root) / path).unlink()
        if item.get('artifact_id'):
            unified = [f'Binary artifact a/{path} -> b/{path}', f'Before-SHA256: {sha256(before) if before is not None else "none"}', f'After-SHA256: {sha256(after) if after is not None else "none"}', f'After-Bytes: {len(after) if after is not None else 0}']
        else:
            try:
                before_text = (before or b'').decode('utf-8'); after_text = (after or b'').decode('utf-8')
                unified = list(difflib.unified_diff(before_text.splitlines(), after_text.splitlines(), fromfile='a/' + path, tofile='b/' + path, lineterm='', n=3))
            except UnicodeDecodeError:
                unified = [f'Binary files a/{path} and b/{path} differ', f'Before-SHA256: {sha256(before) if before is not None else "none"}', f'After-SHA256: {sha256(after) if after is not None else "none"}']
        remaining = max(0, MAX_DIFF_LINES - len(diff_lines))
        diff_lines.extend(unified[:remaining])
        applied.append({
            'operation': operation,
            'path': requested_path,
            'effective_path': path,
            'before_sha256': sha256(before) if before is not None else None,
            'after_sha256': sha256(after) if after is not None else None,
            'before_bytes': len(before) if before is not None else 0,
            'after_bytes': len(after) if after is not None else 0,
        })
    return applied, diff_lines


def seal_path(sealroot: str, workspace_id: str) -> Path:
    return Path(sealroot) / (workspace_id + '.json')


def seal_change_set(sealroot: str, data: dict[str, Any], ttl_seconds: int = DEFAULT_TTL) -> dict[str, Any]:
    workspace_id = 'ws_' + secrets.token_hex(12)
    created = int(time.time())
    sealed = dict(data)
    sealed.update({'workspace_id': workspace_id, 'created_at': created, 'expires_at': created + max(300, min(int(ttl_seconds), 86400))})
    path = seal_path(sealroot, workspace_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(sealed, handle, ensure_ascii=False, separators=(',', ':'))
            handle.flush(); os.fsync(handle.fileno())
    except Exception:
        try:path.unlink()
        except FileNotFoundError:pass
        raise
    return sealed


def load_sealed(sealroot: str, workspace_id: str, expected_digest: str, project_slug: str) -> dict[str, Any]:
    if not WORKSPACE_RE.fullmatch(workspace_id):
        raise ChangeSetError('invalid_workspace_id', 'O workspace_id é inválido.', 'workspace_id', 'ws_0123456789abcdef01234567')
    if not SHA_RE.fullmatch(expected_digest):
        raise ChangeSetError('invalid_change_set_digest', 'O change_set_digest deve ter 64 caracteres hexadecimais.', 'change_set_digest')
    path = seal_path(sealroot, workspace_id)
    if not path.is_file() or path.is_symlink():
        raise ChangeSetError('workspace_not_found', 'O workspace selado não existe ou já expirou.', 'workspace_id')
    data = json.loads(path.read_text(encoding='utf-8'))
    if int(data.get('expires_at') or 0) < int(time.time()):
        try:path.unlink()
        except FileNotFoundError:pass
        raise ChangeSetError('workspace_expired', 'O workspace selado expirou. Valide novamente o change set.', 'workspace_id')
    if data.get('project_slug') != project_slug:
        raise ChangeSetError('workspace_project_mismatch', 'O workspace pertence a outro projeto.', 'workspace_id')
    if data.get('change_set_digest') != expected_digest:
        raise ChangeSetError('change_set_digest_mismatch', 'O digest não corresponde ao workspace validado.', 'change_set_digest')
    return data


def clean_expired(sealroot: str) -> int:
    root = Path(sealroot)
    if not root.is_dir():
        return 0
    removed = 0
    current = int(time.time())
    for path in root.glob('ws_*.json'):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if int(data.get('expires_at') or 0) < current:
                path.unlink(); removed += 1
        except Exception:
            try:path.unlink(); removed += 1
            except Exception:pass
    return removed
