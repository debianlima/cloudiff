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
import shutil
from pathlib import Path
from typing import Any

ARTIFACT_RE = re.compile(r'^art_[a-f0-9]{24}$')
SHA_RE = re.compile(r'^[a-f0-9]{64}$')
MAX_ARTIFACT_BYTES = 1024 * 1024 * 1024
MIN_FREE_RESERVE_BYTES = 1024 * 1024 * 1024
STREAM_CHUNK_BYTES = 1024 * 1024
MAX_CHUNK_BYTES = 192 * 1024
MAX_BATCH_CHUNK_BYTES = 8 * 1024
MAX_BATCH_CHUNKS = 16
DEFAULT_TTL = 3600
MAX_TTL = 86400
MAX_UPLOAD_TICKET_TTL = 7200
UPLOAD_TICKET_RE = re.compile(r'^upt_([a-f0-9]{24})_([a-f0-9]{48})$')
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


def _sha256_file(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb',buffering=0) as handle:
        while True:
            chunk=handle.read(STREAM_CHUNK_BYTES)
            if not chunk:break
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_artifact_capacity(artifact_root: str, expected_size: int) -> None:
    root=_root(artifact_root);root.mkdir(parents=True,exist_ok=True);os.chmod(root,0o700)
    free=int(shutil.disk_usage(root).free)
    required=int(expected_size)+MIN_FREE_RESERVE_BYTES
    if free < required:
        raise ArtifactError('artifact_storage_pressure','Não há espaço livre suficiente para receber o artefato com a reserva operacional exigida.','expected_size')


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
        raise ArtifactError('artifact_too_large', 'O artefato pode ter no máximo 1024 MiB.', 'expected_size')
    if not SHA_RE.fullmatch(expected_sha256):
        raise ArtifactError('invalid_sha256', 'expected_sha256 deve conter 64 caracteres hexadecimais.', 'expected_sha256')
    if not (300 <= ttl_seconds <= MAX_TTL):
        raise ArtifactError('invalid_ttl', 'ttl_seconds deve ficar entre 300 e 86400.', 'ttl_seconds')
    clean_expired_artifacts(artifact_root)
    _ensure_artifact_capacity(artifact_root,expected_size)
    artifact_id = 'art_' + secrets.token_hex(12)
    root = _root(artifact_root)
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



def _ticket_artifact_id(ticket: str) -> str:
    match=UPLOAD_TICKET_RE.fullmatch(str(ticket or '').strip())
    if not match:
        raise ArtifactError('invalid_upload_ticket','O ticket de upload é inválido.','upload_ticket')
    return 'art_'+match.group(1)


def _ticket_digest(ticket: str) -> str:
    return hashlib.sha256(str(ticket).encode('utf-8')).hexdigest()


def _validate_ticket_unlocked(artifact_root: str, ticket: str, *, allow_used: bool = False) -> tuple[dict[str, Any], str]:
    artifact_id=_ticket_artifact_id(ticket)
    data=_load(artifact_root,artifact_id)
    record=data.get('upload_ticket') if isinstance(data.get('upload_ticket'),dict) else {}
    stored=str(record.get('sha256') or '')
    if not stored or not secrets.compare_digest(stored,_ticket_digest(ticket)):
        raise ArtifactError('upload_ticket_not_found','O ticket de upload não existe ou foi substituído.','upload_ticket')
    now=int(time.time())
    if int(record.get('expires_at') or 0)<=now:
        raise ArtifactError('upload_ticket_expired','O ticket de upload expirou. Gere um novo ticket.','upload_ticket')
    if record.get('used_at') and not allow_used:
        raise ArtifactError('upload_ticket_used','O ticket de upload já foi utilizado.','upload_ticket')
    return data,artifact_id


def create_upload_ticket(artifact_root: str, project_slug: str, artifact_id: str, requested_by: str = '', ttl_seconds: int = 900) -> dict[str, Any]:
    try: ttl_seconds=int(ttl_seconds or 900)
    except Exception as exc: raise ArtifactError('invalid_ticket_ttl','ttl_seconds deve ser inteiro.','ttl_seconds') from exc
    if not (60<=ttl_seconds<=MAX_UPLOAD_TICKET_TTL):
        raise ArtifactError('invalid_ticket_ttl','O ticket pode durar entre 60 e 7200 segundos.','ttl_seconds')
    with _artifact_lock(artifact_id):
        data=_load(artifact_root,artifact_id)
        if data.get('project_slug')!=project_slug:
            raise ArtifactError('artifact_project_mismatch','O artefato pertence a outro projeto.','artifact_id')
        if data.get('status')!='uploading':
            raise ArtifactError('artifact_already_sealed','O artefato já foi selado.','artifact_id')
        now=int(time.time())
        ticket='upt_'+artifact_id[4:]+'_'+secrets.token_hex(24)
        expires=min(now+ttl_seconds,int(data.get('expires_at') or now+ttl_seconds))
        if expires<=now:
            raise ArtifactError('artifact_expired','O artefato expirou. Faça o upload novamente.','artifact_id')
        data['upload_ticket']={
            'sha256':_ticket_digest(ticket),'created_at':now,'expires_at':expires,
            'requested_by':str(requested_by or '')[:160],'used_at':None,
        }
        data['updated_at']=now
        _write_json_atomic(_meta_path(artifact_root,artifact_id),data)
        result=public_metadata(data)
        result.update({'upload_ticket':ticket,'upload_ticket_expires_at':expires,'upload_ticket_ttl_seconds':expires-now})
        return result


def inspect_upload_ticket(artifact_root: str, ticket: str) -> dict[str, Any]:
    artifact_id=_ticket_artifact_id(ticket)
    with _artifact_lock(artifact_id):
        data,artifact_id=_validate_ticket_unlocked(artifact_root,ticket,allow_used=True)
        record=data.get('upload_ticket') or {}
        status='used' if record.get('used_at') else 'pending'
        result=public_metadata(data)
        result.update({'upload_ticket_status':status,'upload_ticket_expires_at':int(record.get('expires_at') or 0),'upload_ticket_used_at':record.get('used_at')})
        return result


def _validate_active_upload_window_unlocked(artifact_root: str, artifact_id: str, *, allow_used: bool = False) -> dict[str, Any]:
    if not ARTIFACT_RE.fullmatch(str(artifact_id or '')):
        raise ArtifactError('invalid_artifact_id','artifact_id inválido.','artifact_id')
    data=_load(artifact_root,artifact_id)
    record=data.get('upload_ticket') if isinstance(data.get('upload_ticket'),dict) else {}
    if not str(record.get('sha256') or ''):
        raise ArtifactError('upload_ticket_not_found','Não existe janela de upload ativa para este artifact.','artifact_id')
    now=int(time.time())
    if int(record.get('expires_at') or 0)<=now:
        raise ArtifactError('upload_ticket_expired','A janela de upload expirou. Gere um novo link.','artifact_id')
    if record.get('used_at') and not allow_used:
        raise ArtifactError('upload_ticket_used','A janela de upload já foi utilizada.','artifact_id')
    return data


def inspect_upload_artifact(artifact_root: str, artifact_id: str) -> dict[str, Any]:
    with _artifact_lock(artifact_id):
        data=_validate_active_upload_window_unlocked(artifact_root,artifact_id,allow_used=True)
        record=data.get('upload_ticket') or {}
        status='used' if record.get('used_at') else 'pending'
        result=public_metadata(data)
        result.update({'upload_ticket_status':status,'upload_ticket_expires_at':int(record.get('expires_at') or 0),'upload_ticket_used_at':record.get('used_at')})
        return result


def _direct_upload_unlocked(artifact_root: str, artifact_id: str, data: dict[str, Any], stream, content_length: int) -> dict[str, Any]:
    if data.get('status')!='uploading':
        raise ArtifactError('artifact_already_sealed','O artefato já foi selado.','artifact_id')
    expected_size=int(data.get('expected_size') or -1)
    if content_length!=expected_size:
        raise ArtifactError('artifact_size_mismatch','O tamanho enviado não confere com expected_size.','content_length')
    _ensure_artifact_capacity(artifact_root,content_length)
    directory=_dir(artifact_root,artifact_id)
    tmp=directory/('.direct-upload-'+secrets.token_hex(8)+'.tmp')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    digest=hashlib.sha256();remaining=content_length;written=0
    try:
        with os.fdopen(fd,'wb',buffering=0) as handle:
            while remaining:
                chunk=stream.read(min(STREAM_CHUNK_BYTES,remaining))
                if not chunk:
                    raise ArtifactError('upload_incomplete','O upload terminou antes do tamanho esperado.','content')
                handle.write(chunk);digest.update(chunk);written+=len(chunk);remaining-=len(chunk)
            os.fsync(handle.fileno())
        actual=digest.hexdigest();expected=str(data.get('expected_sha256') or '')
        if written!=expected_size:
            raise ArtifactError('artifact_size_mismatch','O tamanho recebido não confere com expected_size.','content')
        if not secrets.compare_digest(actual,expected):
            raise ArtifactError('artifact_sha256_mismatch','O SHA-256 do arquivo enviado não confere.','content')
        payload=_payload_path(artifact_root,artifact_id)
        os.replace(tmp,payload);os.chmod(payload,0o400)
        now=int(time.time())
        record=dict(data.get('upload_ticket') or {});record['used_at']=now
        data.update({
            'status':'sealed','size':written,'sha256':actual,'received_bytes':written,
            'next_chunk':0,'chunks':[],'sealed_at':now,'updated_at':now,
            'upload_transport':'browser_direct','upload_ticket':record,
        })
        _write_json_atomic(_meta_path(artifact_root,artifact_id),data)
        result=public_metadata(data)
        result.update({'upload_transport':'browser_direct','upload_ticket_status':'used'})
        return result
    except Exception:
        try: tmp.unlink()
        except FileNotFoundError: pass
        raise


def direct_upload_artifact(artifact_root: str, ticket: str, stream, content_length: int) -> dict[str, Any]:
    artifact_id=_ticket_artifact_id(ticket)
    try: content_length=int(content_length)
    except Exception as exc: raise ArtifactError('invalid_upload_size','Content-Length inválido.','content_length') from exc
    with _artifact_lock(artifact_id):
        data,artifact_id=_validate_ticket_unlocked(artifact_root,ticket,allow_used=False)
        return _direct_upload_unlocked(artifact_root,artifact_id,data,stream,content_length)


def direct_upload_artifact_by_id(artifact_root: str, artifact_id: str, stream, content_length: int) -> dict[str, Any]:
    try: content_length=int(content_length)
    except Exception as exc: raise ArtifactError('invalid_upload_size','Content-Length inválido.','content_length') from exc
    with _artifact_lock(artifact_id):
        data=_validate_active_upload_window_unlocked(artifact_root,artifact_id,allow_used=False)
        return _direct_upload_unlocked(artifact_root,artifact_id,data,stream,content_length)


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



def append_chunk_batch(artifact_root: str, project_slug: str, artifact_id: str, chunks: Any) -> dict[str, Any]:
    if not isinstance(chunks, list) or not (1 <= len(chunks) <= MAX_BATCH_CHUNKS):
        raise ArtifactError('invalid_chunk_batch', f'O batch deve conter entre 1 e {MAX_BATCH_CHUNKS} chunks.', 'chunks')
    with _artifact_lock(artifact_id):
        data = _load(artifact_root, artifact_id)
        if data.get('project_slug') != project_slug:
            raise ArtifactError('artifact_project_mismatch', 'O artefato pertence a outro projeto.', 'artifact_id')
        if data.get('status') != 'uploading':
            raise ArtifactError('artifact_already_sealed', 'O artefato já foi selado.', 'artifact_id')
        next_chunk = int(data.get('next_chunk') or 0)
        known = {int(x.get('index', -1)): x for x in (data.get('chunks') or [])}
        prevalidated = []
        new_bytes = 0
        new_count = 0
        idempotent_count = 0
        for position, item in enumerate(chunks):
            if not isinstance(item, dict) or set(item) != {'chunk_index','content_base64','chunk_sha256'}:
                raise ArtifactError('invalid_chunk_batch_item', 'Cada item exige chunk_index, content_base64 e chunk_sha256.', f'chunks.{position}')
            try: index = int(item.get('chunk_index'))
            except Exception as exc: raise ArtifactError('invalid_chunk_index', 'chunk_index deve ser inteiro.', f'chunks.{position}.chunk_index') from exc
            encoded = item.get('content_base64'); digest = str(item.get('chunk_sha256') or '').lower().strip()
            if index < 0 or not SHA_RE.fullmatch(digest) or not isinstance(encoded, str) or not encoded:
                raise ArtifactError('invalid_chunk_metadata', 'Metadados do chunk são inválidos.', f'chunks.{position}')
            try: raw = base64.b64decode(encoded, validate=True)
            except Exception as exc: raise ArtifactError('invalid_chunk_base64', 'O chunk deve ser Base64 válido.', f'chunks.{position}.content_base64') from exc
            if len(raw) > MAX_BATCH_CHUNK_BYTES:
                raise ArtifactError('batch_chunk_too_large', 'No batch, cada chunk pode ter no máximo 8 KiB.', f'chunks.{position}.content_base64')
            actual = hashlib.sha256(raw).hexdigest()
            if actual != digest:
                raise ArtifactError('chunk_sha256_mismatch', 'O SHA-256 do chunk não confere.', f'chunks.{position}.chunk_sha256')
            if index < next_chunk:
                previous = known.get(index)
                if not previous or previous.get('sha256') != digest or int(previous.get('size') or -1) != len(raw):
                    raise ArtifactError('chunk_conflict', 'O chunk já existe com conteúdo diferente.', f'chunks.{position}.chunk_index')
                idempotent_count += 1; prevalidated.append((index, raw, digest, True)); continue
            expected_index = next_chunk + new_count
            if index != expected_index:
                raise ArtifactError('chunk_out_of_order', f'O próximo chunk esperado é {expected_index}.', f'chunks.{position}.chunk_index')
            new_bytes += len(raw); new_count += 1; prevalidated.append((index, raw, digest, False))
        received = int(data.get('received_bytes') or 0)
        if received + new_bytes > int(data.get('expected_size') or 0):
            raise ArtifactError('artifact_size_overflow', 'O batch excede expected_size.', 'chunks')
        result = None
        for index, raw, digest, idempotent in prevalidated:
            if idempotent: continue
            result = _append_chunk_unlocked(artifact_root, project_slug, artifact_id, index, base64.b64encode(raw).decode(), digest)
        if result is None:
            result = public_metadata(_load(artifact_root, artifact_id))
        result.update({'batch_count':len(chunks),'new_count':new_count,'idempotent_count':idempotent_count,'batch_max_chunk_bytes':MAX_BATCH_CHUNK_BYTES})
        return result


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
    digest = _sha256_file(payload)
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
    if len(raw) != int(data.get('size') or -1) or not secrets.compare_digest(hashlib.sha256(raw).hexdigest(),str(data.get('sha256') or '')):
        raise ArtifactError('artifact_integrity_failed', 'A integridade do artefato armazenado falhou.', 'artifact_id')
    data.pop('payload_path', None)
    return data, raw
