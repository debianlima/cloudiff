#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import time
import threading
from pathlib import Path
from typing import Any

ARTIFACT_RE = re.compile(r'^art_[a-f0-9]{24}$')
SHA_RE = re.compile(r'^[a-f0-9]{64}$')
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_CHUNK_BYTES = 192 * 1024
DEFAULT_TTL = 3600
MAX_TTL = 86400
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()

def _artifact_lock(artifact_id: str) -> threading.RLock:
    if not ARTIFACT_RE.fullmatch(str(artifact_id or '')):
        raise ArtifactError('invalid_artifact_id', 'O artifact_id é inválido.', 'artifact_id')
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(artifact_id, threading.RLock())


class ArtifactError(ValueError):
    def __init__(self, code: str, message: str, field: str = ''):
        super().__init__(code)
        self.code = code
        self.message = message
        self.field = field

    def as_dict(self) -> dict[str, Any]:
        return {'code': self.code, 'message': self.message, 'field': self.field, 'documentation': 'workspace-artifact-v1'}


def _root(artifact_root: str) -> Path:
    return Path(artifact_root)


def _dir(artifact_root: str, artifact_id: str) -> Path:
    return _root(artifact_root) / artifact_id


def _meta_path(artifact_root: str, artifact_id: str) -> Path:
    return _dir(artifact_root, artifact_id) / 'metadata.json'


def _payload_path(artifact_root: str, artifact_id: str) -> Path:
    return _dir(artifact_root, artifact_id) / 'payload.bin'


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_name('.' + path.name + '.tmp-' + secrets.token_hex(4))
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, separators=(',', ':'))
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        try: tmp.unlink()
        except FileNotFoundError: pass
        raise


def _load(artifact_root: str, artifact_id: str) -> dict[str, Any]:
    if not ARTIFACT_RE.fullmatch(str(artifact_id or '')):
        raise ArtifactError('invalid_artifact_id', 'O artifact_id é inválido.', 'artifact_id')
    path = _meta_path(artifact_root, artifact_id)
    if not path.is_file() or path.is_symlink():
        raise ArtifactError('artifact_not_found', 'O artefato não existe ou já expirou.', 'artifact_id')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise ArtifactError('artifact_metadata_invalid', 'Os metadados do artefato são inválidos.', 'artifact_id') from exc
    now = int(time.time())
    if int(data.get('expires_at') or 0) <= now:
        cleanup_artifact(artifact_root, artifact_id)
        raise ArtifactError('artifact_expired', 'O artefato expirou. Faça o upload novamente.', 'artifact_id')
    return data


def cleanup_artifact(artifact_root: str, artifact_id: str) -> None:
    import shutil
    path = _dir(artifact_root, artifact_id)
    if path.exists() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)


def clean_expired_artifacts(artifact_root: str) -> int:
    root = _root(artifact_root)
    if not root.exists(): return 0
    now = int(time.time()); removed = 0
    for path in root.iterdir():
        if not path.is_dir() or path.is_symlink() or not ARTIFACT_RE.fullmatch(path.name): continue
        try: data = json.loads((path / 'metadata.json').read_text(encoding='utf-8'))
        except Exception: data = {}
        if int(data.get('expires_at') or 0) <= now:
            cleanup_artifact(artifact_root, path.name); removed += 1
    return removed


def start_artifact(artifact_root: str, project_slug: str, filename: str, expected_size: int, expected_sha256: str, ttl_seconds: int = DEFAULT_TTL) -> dict[str, Any]:
    project_slug = str(project_slug or '').strip()
    filename = str(filename or '').replace('\\', '/').split('/')[-1].strip()
    expected_sha256 = str(expected_sha256 or '').strip().lower()
    try: expected_size = int(expected_size)
    except Exception as exc: raise ArtifactError('invalid_size', 'expected_size deve ser inteiro.', 'expected_size') from exc
    try: ttl_seconds = int(ttl_seconds or DEFAULT_TTL)
    except Exception: ttl_seconds = DEFAULT_TTL
    if not project_slug: raise ArtifactError('project_required', 'O projeto é obrigatório.', 'project_slug')
    if not filename or len(filename) > 240 or '\x00' in filename:
        raise ArtifactError('invalid_filename', 'O nome do arquivo é inválido.', 'filename')
    if not (0 <= expected_size <= MAX_ARTIFACT_BYTES):
        raise ArtifactError('artifact_too_large', 'O artefato pode ter no máximo 64 MiB.', 'expected_size')
    if not SHA_RE.fullmatch(expected_sha256):
        raise ArtifactError('invalid_sha256', 'expected_sha256 deve conter 64 caracteres hexadecimais.', 'expected_sha256')
    if not (300 <= ttl_seconds <= MAX_TTL):
        raise ArtifactError('invalid_ttl', 'ttl_seconds deve ficar entre 300 e 86400.', 'ttl_seconds')
    clean_expired_artifacts(artifact_root)
    artifact_id = 'art_' + secrets.token_hex(12)
    root = _root(artifact_root); root.mkdir(parents=True, exist_ok=True); os.chmod(root, 0o700)
    directory = _dir(artifact_root, artifact_id); directory.mkdir(mode=0o700)
    payload = _payload_path(artifact_root, artifact_id)
    fd = os.open(payload, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600); os.close(fd)
    now = int(time.time())
    data = {
        'version': 1, 'artifact_id': artifact_id, 'project_slug': project_slug, 'filename': filename,
        'expected_size': expected_size, 'expected_sha256': expected_sha256,
        'received_bytes': 0, 'next_chunk': 0, 'chunks': [], 'status': 'uploading',
        'created_at': now, 'updated_at': now, 'expires_at': now + ttl_seconds,
    }
    _write_json_atomic(_meta_path(artifact_root, artifact_id), data)
    return public_metadata(data)


def _append_chunk_unlocked(artifact_root: str, project_slug: str, artifact_id: str, chunk_index: int, content_base64: str, chunk_sha256: str) -> dict[str, Any]:
    data = _load(artifact_root, artifact_id)
    if data.get('project_slug') != project_slug: raise ArtifactError('artifact_project_mismatch', 'O artefato pertence a outro projeto.', 'artifact_id')
    if data.get('status') != 'uploading': raise ArtifactError('artifact_already_sealed', 'O artefato já foi selado.', 'artifact_id')
    try: chunk_index = int(chunk_index)
    except Exception as exc: raise ArtifactError('invalid_chunk_index', 'chunk_index deve ser inteiro.', 'chunk_index') from exc
    chunk_sha256 = str(chunk_sha256 or '').strip().lower()
    if chunk_index < 0 or not SHA_RE.fullmatch(chunk_sha256): raise ArtifactError('invalid_chunk_metadata', 'Índice ou SHA-256 do chunk inválido.', 'chunk_index')
    if not isinstance(content_base64, str) or not content_base64:
        raise ArtifactError('chunk_content_required', 'content_base64 é obrigatório para o chunk.', 'content_base64')
    try: raw = base64.b64decode(content_base64, validate=True)
    except Exception as exc: raise ArtifactError('invalid_chunk_base64', 'O chunk deve ser Base64 válido.', 'content_base64') from exc
    if len(raw) > MAX_CHUNK_BYTES: raise ArtifactError('chunk_too_large', 'Cada chunk pode ter no máximo 192 KiB.', 'content_base64')
    actual = hashlib.sha256(raw).hexdigest()
    if actual != chunk_sha256: raise ArtifactError('chunk_sha256_mismatch', 'O SHA-256 do chunk não confere.', 'chunk_sha256')
    chunks = list(data.get('chunks') or [])
    if chunk_index < int(data.get('next_chunk') or 0):
        previous = next((x for x in chunks if int(x.get('index', -1)) == chunk_index), None)
        if previous and previous.get('sha256') == actual and int(previous.get('size') or -1) == len(raw):
            result = public_metadata(data); result['idempotent'] = True; return result
        raise ArtifactError('chunk_conflict', 'O chunk já existe com conteúdo diferente.', 'chunk_index')
    if chunk_index != int(data.get('next_chunk') or 0):
        raise ArtifactError('chunk_out_of_order', 'Envie os chunks em ordem sequencial.', 'chunk_index')
    received = int(data.get('received_bytes') or 0)
    if received + len(raw) > int(data.get('expected_size') or 0):
        raise ArtifactError('artifact_size_overflow', 'Os chunks excedem expected_size.', 'content_base64')
    payload = _payload_path(artifact_root, artifact_id)
    with open(payload, 'ab', buffering=0) as handle:
        handle.write(raw); os.fsync(handle.fileno())
    chunks.append({'index': chunk_index, 'offset': received, 'size': len(raw), 'sha256': actual})
    data.update({'received_bytes': received + len(raw), 'next_chunk': chunk_index + 1, 'chunks': chunks, 'updated_at': int(time.time())})
    _write_json_atomic(_meta_path(artifact_root, artifact_id), data)
    result = public_metadata(data); result['idempotent'] = False; return result



def append_chunk(artifact_root: str, project_slug: str, artifact_id: str, chunk_index: int, content_base64: str, chunk_sha256: str) -> dict[str, Any]:
    with _artifact_lock(artifact_id):
        return _append_chunk_unlocked(artifact_root, project_slug, artifact_id, chunk_index, content_base64, chunk_sha256)


def _complete_artifact_unlocked(artifact_root: str, project_slug: str, artifact_id: str) -> dict[str, Any]:
    data = _load(artifact_root, artifact_id)
    if data.get('project_slug') != project_slug: raise ArtifactError('artifact_project_mismatch', 'O artefato pertence a outro projeto.', 'artifact_id')
    if data.get('status') == 'sealed':
        result = public_metadata(data); result['idempotent'] = True; return result
    if data.get('status') != 'uploading': raise ArtifactError('artifact_invalid_state', 'O artefato não pode ser concluído neste estado.', 'artifact_id')
    payload = _payload_path(artifact_root, artifact_id)
    if not payload.is_file() or payload.is_symlink(): raise ArtifactError('artifact_payload_missing', 'O payload do artefato não foi encontrado.', 'artifact_id')
    size = payload.stat().st_size
    if size != int(data.get('expected_size') or -1) or size != int(data.get('received_bytes') or -2):
        raise ArtifactError('artifact_size_mismatch', 'O tamanho recebido não confere com expected_size.', 'artifact_id')
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    if digest != data.get('expected_sha256'):
        raise ArtifactError('artifact_sha256_mismatch', 'O SHA-256 final do artefato não confere.', 'artifact_id')
    data.update({'status': 'sealed', 'size': size, 'sha256': digest, 'sealed_at': int(time.time()), 'updated_at': int(time.time())})
    _write_json_atomic(_meta_path(artifact_root, artifact_id), data)
    os.chmod(payload, 0o400)
    result = public_metadata(data); result['idempotent'] = False; return result



def complete_artifact(artifact_root: str, project_slug: str, artifact_id: str) -> dict[str, Any]:
    with _artifact_lock(artifact_id):
        return _complete_artifact_unlocked(artifact_root, project_slug, artifact_id)


def public_metadata(data: dict[str, Any]) -> dict[str, Any]:
    return {k: data.get(k) for k in ('artifact_id','project_slug','filename','status','expected_size','expected_sha256','received_bytes','next_chunk','size','sha256','created_at','updated_at','sealed_at','expires_at') if data.get(k) is not None}


def _resolve_artifact_unlocked(artifact_root: str, project_slug: str, artifact_id: str, *, expected_sha256: str = '', expected_size: int | None = None, hold_until: int = 0) -> dict[str, Any]:
    data = _load(artifact_root, artifact_id)
    if data.get('project_slug') != project_slug: raise ArtifactError('artifact_project_mismatch', 'O artefato pertence a outro projeto.', 'artifact_id')
    if data.get('status') != 'sealed': raise ArtifactError('artifact_not_sealed', 'Conclua o upload antes de usar o artifact_id.', 'artifact_id')
    digest = str(data.get('sha256') or '')
    size = int(data.get('size') or 0)
    if expected_sha256 and digest != str(expected_sha256).lower(): raise ArtifactError('artifact_sha256_mismatch', 'O SHA-256 do artefato não confere.', 'artifact_id')
    if expected_size is not None and size != int(expected_size): raise ArtifactError('artifact_size_mismatch', 'O tamanho do artefato não confere.', 'artifact_id')
    if hold_until:
        data['expires_at'] = max(int(data.get('expires_at') or 0), min(int(hold_until), int(time.time()) + MAX_TTL))
        data['updated_at'] = int(time.time()); _write_json_atomic(_meta_path(artifact_root, artifact_id), data)
    result = public_metadata(data); result['payload_path'] = str(_payload_path(artifact_root, artifact_id)); return result



def resolve_artifact(artifact_root: str, project_slug: str, artifact_id: str, *, expected_sha256: str = '', expected_size: int | None = None, hold_until: int = 0) -> dict[str, Any]:
    with _artifact_lock(artifact_id):
        return _resolve_artifact_unlocked(artifact_root, project_slug, artifact_id, expected_sha256=expected_sha256, expected_size=expected_size, hold_until=hold_until)


def read_artifact(artifact_root: str, project_slug: str, artifact_id: str, expected_sha256: str = '', expected_size: int | None = None) -> tuple[dict[str, Any], bytes]:
    data = resolve_artifact(artifact_root, project_slug, artifact_id, expected_sha256=expected_sha256, expected_size=expected_size)
    payload = Path(data['payload_path'])
    raw = payload.read_bytes()
    if len(raw) != int(data.get('size') or -1) or hashlib.sha256(raw).hexdigest() != data.get('sha256'):
        raise ArtifactError('artifact_integrity_failed', 'A integridade do artefato armazenado falhou.', 'artifact_id')
    data.pop('payload_path', None)
    return data, raw
