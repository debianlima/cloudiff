#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
import time
import uuid
from typing import Any

B = None
ENVIRONMENTS = {'development', 'preview', 'homologation', 'production'}


def configure(broker_module):
    global B
    B = broker_module


def _require_configured():
    if B is None:
        raise RuntimeError('toolchain_lifecycle_not_configured')


def _image_record(row) -> dict[str, Any]:
    return {
        'image_record_id': row['image_record_id'],
        'service': row['service'],
        'toolchain_digest': row['toolchain_digest'],
        'image_ref': row['image_ref'],
        'image_id': row['image_id'],
        'status': row['status'],
    }


def reusable(project_slug: str, services: list[dict[str, Any]]) -> dict[str, Any]:
    _require_configured()
    result = {}
    connection = B.db()
    for item in services:
        row = connection.execute(
            "select * from toolchain_images where project_slug=? and service=? and toolchain_digest=? and status in ('ready','active') order by updated_at desc limit 1",
            (project_slug, item['service'], item['toolchainDigest']),
        ).fetchone()
        if row:
            result[item['service']] = _image_record(row)
    connection.close()
    return result


def plan(payload: dict[str, Any]) -> dict[str, Any]:
    _require_configured()
    base = B.multiservice_plan(payload)
    validations = base.get('toolchain_validations') or []
    material = {
        'kind': 'toolchain-build-v1',
        'project_slug': base['project_slug'],
        'ref': base['ref'],
        'config_revision': base['config_revision'],
        'config_digest': base['config_digest'],
        'requested_toolchain_digest': base['toolchain_digest'],
        'archive_sha256': base['archive_sha256'],
        'services': [
            {
                'service': item['service'],
                'runtime': item['runtime'],
                'version': item.get('version'),
                'toolchainDigest': item['toolchainDigest'],
                'catalogVersion': item['catalogVersion'],
            }
            for item in validations
        ],
    }
    plan_digest = hashlib.sha256(B.canonical(material)).hexdigest()
    reusable_images = reusable(base['project_slug'], validations)
    all_reusable = bool(validations) and len(reusable_images) == len(validations)
    lifecycle_blocked = [item for item in (base.get('blocked') or []) if item.get('code') != 'image-outdated']
    warnings = [
        {'service': item['service'], **warning}
        for item in validations
        for warning in item.get('warnings') or []
    ]
    return {
        'ok': True,
        'side_effect_free': True,
        'project_slug': base['project_slug'],
        'ref': base['ref'],
        'config_revision': base['config_revision'],
        'config_digest': base['config_digest'],
        'requested_toolchain_digest': base['toolchain_digest'],
        'archive_sha256': base['archive_sha256'],
        'plan_digest': plan_digest,
        'services': validations,
        'toolchain': base.get('toolchain') or {},
        'blocked': lifecycle_blocked,
        'warnings': warnings,
        'source_validation_required': any(item.get('script', {}).get('ok') is None for item in validations),
        'reusable_images': reusable_images,
        'build_required': not all_reusable,
        'approval_required': not lifecycle_blocked and not all_reusable,
        'summary': {
            'serviceCount': len(validations),
            'catalogVersion': int(B.load_catalog(B.TOOLCHAIN_CATALOG).get('version') or 0),
            'networkPolicy': base.get('summary', {}).get('networkPolicy'),
            'scannerPolicy': 'block-high-critical',
            'signatureAlgorithm': 'Ed25519',
            'secretsIncluded': False,
        },
        'images_created': 0,
        'containers_changed': False,
        'secret_values_included': False,
    }


def _request_for_plan(plan_data: dict[str, Any], job_id: str, trace_id: str) -> dict[str, Any]:
    configuration = B.project_configuration(plan_data['project_slug']).get('configuration') or {}
    return {
        'job_id': job_id,
        'project_slug': plan_data['project_slug'],
        'ref': plan_data['ref'],
        'archive_sha256': plan_data['archive_sha256'],
        'config_revision': plan_data['config_revision'],
        'config_digest': plan_data['config_digest'],
        'toolchain_digest': plan_data['requested_toolchain_digest'],
        'plan_digest': plan_data['plan_digest'],
        'services': B.normalized_multiservice_services(configuration),
        'toolchain': plan_data['toolchain'],
        'trace_id': trace_id[:128],
    }


def _artifact(path: str, request: dict[str, Any], timeout: int) -> dict[str, Any]:
    code, data = B.internal_json('POST', B.ARTIFACT_URL + path, B.ARTIFACT_TOKEN, request, timeout=timeout)
    if code != 200:
        error = data.get('error') or {}
        message = error.get('message') if isinstance(error, dict) else str(error)
        raise RuntimeError(message or 'toolchain_executor_failed')
    return data


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    plan_data = plan(payload)
    if plan_data['blocked']:
        return {**plan_data, 'valid': False, 'runtime_validation': None}
    request = _request_for_plan(
        plan_data,
        'toolchain_' + secrets.token_hex(12),
        str(payload.get('trace_id') or 'toolchain-validate'),
    )
    runtime = _artifact('/v1/toolchain/validate', request, 600)
    return {
        **plan_data,
        'valid': bool(runtime.get('valid')),
        'runtime_validation': runtime,
        'blocked': runtime.get('blockers') or [],
        'warnings': runtime.get('warnings') or [],
        'source_validation_required': False,
        'images_created': 0,
        'containers_changed': False,
        'secret_values_included': False,
    }


def _register_images(job: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    connection = B.db()
    timestamp = B.now()
    records = []
    for item in result.get('toolchains') or []:
        image = item.get('image') or {}
        image_ref = str(image.get('image') or '')
        image_id = str(image.get('imageId') or '')
        service = str(item.get('service') or '')
        toolchain_digest = str(item.get('effectiveToolchainDigest') or '')
        if not service or not image_ref or not image_id or not re.fullmatch(r'[a-f0-9]{64}', toolchain_digest):
            connection.close()
            raise RuntimeError('toolchain_result_invalid')
        record_id = 'img_' + hashlib.sha256(
            (job['project_slug'] + '|' + service + '|' + toolchain_digest + '|' + image_id).encode()
        ).hexdigest()[:24]
        payload = {**item, 'imageRecordId': record_id}
        connection.execute(
            '''insert into toolchain_images(
                 image_record_id,project_slug,service,toolchain_digest,image_ref,image_id,
                 config_revision,config_digest,archive_sha256,plan_digest,status,result_json,created_at,updated_at
               ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               on conflict(project_slug,service,toolchain_digest,image_id)
               do update set result_json=excluded.result_json,updated_at=excluded.updated_at''',
            (
                record_id, job['project_slug'], service, toolchain_digest, image_ref, image_id,
                job['config_revision'], job['config_digest'], job['archive_sha256'], job['plan_digest'],
                'ready', json.dumps(payload, ensure_ascii=False, separators=(',', ':')), timestamp, timestamp,
            ),
        )
        records.append({
            'image_record_id': record_id,
            'service': service,
            'toolchain_digest': toolchain_digest,
            'image_ref': image_ref,
            'image_id': image_id,
            'status': 'ready',
        })
    connection.commit()
    connection.close()
    return records


def _run_job(job_id: str) -> None:
    connection = B.db()
    row = connection.execute('select * from toolchain_jobs where job_id=?', (job_id,)).fetchone()
    if not row or row['status'] not in {'queued', 'running'}:
        connection.close()
        return
    connection.execute(
        "update toolchain_jobs set status='running',attempts=attempts+1,updated_at=?,log_text=log_text||? where job_id=?",
        (B.now(), 'executor:start\n', job_id),
    )
    connection.commit()
    payload = json.loads(row['payload_json'])
    job = dict(row)
    connection.close()
    try:
        result = _artifact('/v1/toolchain/build', payload, 7200)
        if not result.get('ok'):
            raise RuntimeError('toolchain_build_failed')
        records = _register_images(job, result)
        result['images'] = records
        result['activationRequired'] = True
        result['containersChanged'] = False
        connection = B.db()
        connection.execute(
            "update toolchain_jobs set status='succeeded',result_json=?,last_error='',updated_at=?,log_text=log_text||? where job_id=?",
            (json.dumps(result, ensure_ascii=False, separators=(',', ':')), B.now(), 'executor:succeeded\n', job_id),
        )
        connection.commit()
        connection.close()
    except Exception as exc:
        connection = B.db()
        connection.execute(
            "update toolchain_jobs set status='failed',last_error=?,result_json=?,updated_at=?,log_text=log_text||? where job_id=?",
            (
                B.sanitize(str(exc)),
                json.dumps({'ok': False, 'error': {'code': 'toolchain_build_failed', 'message': 'A construção da toolchain falhou.'}, 'secretValuesIncluded': False}, separators=(',', ':')),
                B.now(), 'executor:failed\n', job_id,
            ),
        )
        connection.commit()
        connection.close()


def queue(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError('invalid_request')
    if payload.get('approved') is not True:
        raise PermissionError('approval_required')
    validation = validate(payload)
    provided = str(payload.get('plan_digest') or '').lower()
    if not hmac.compare_digest(validation['plan_digest'], provided):
        raise ValueError('plan_digest_mismatch')
    if not validation.get('valid') or validation.get('blocked'):
        raise ValueError('toolchain_policy_blocked')
    key = hashlib.sha256((validation['project_slug'] + '|' + validation['ref'] + '|' + provided).encode()).hexdigest()
    connection = B.db()
    row = connection.execute('select * from toolchain_jobs where idempotency_key=?', (key,)).fetchone()
    if row:
        connection.close()
        return {'ok': True, 'job_id': row['job_id'], 'status': row['status'], 'idempotent': True, 'plan_digest': provided}
    job_id = 'toolchain_' + secrets.token_hex(12)
    timestamp = B.now()
    request = _request_for_plan(validation, job_id, str(payload.get('trace_id') or job_id))
    connection.execute(
        '''insert into toolchain_jobs(
             job_id,idempotency_key,project_slug,ref,config_revision,config_digest,toolchain_digest,
             archive_sha256,plan_digest,status,payload_json,result_json,log_text,created_at,updated_at
           ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (
            job_id, key, validation['project_slug'], validation['ref'], validation['config_revision'],
            validation['config_digest'], validation['requested_toolchain_digest'], validation['archive_sha256'],
            provided, 'queued', json.dumps(request, ensure_ascii=False, separators=(',', ':')),
            '{}', 'reserved\n', timestamp, timestamp,
        ),
    )
    connection.commit()
    connection.close()
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return {
        'ok': True, 'job_id': job_id, 'status': 'queued', 'idempotent': False,
        'plan_digest': provided, 'config_revision': validation['config_revision'],
        'archive_sha256': validation['archive_sha256'], 'containers_changed': False,
    }


def status(job_id: str) -> dict[str, Any]:
    if not re.fullmatch(r'toolchain_[a-f0-9]{24}', str(job_id or '')):
        raise ValueError('invalid_toolchain_job_id')
    connection = B.db()
    row = connection.execute('select * from toolchain_jobs where job_id=?', (job_id,)).fetchone()
    connection.close()
    if not row:
        raise LookupError('toolchain_job_not_found')
    return {
        'ok': True, 'job_id': job_id, 'project_slug': row['project_slug'], 'status': row['status'],
        'attempts': row['attempts'], 'plan_digest': row['plan_digest'],
        'config_revision': row['config_revision'], 'config_digest': row['config_digest'],
        'toolchain_digest': row['toolchain_digest'], 'archive_sha256': row['archive_sha256'],
        'result': json.loads(row['result_json'] or '{}'), 'error': row['last_error'] or None,
        'created_at': row['created_at'], 'updated_at': row['updated_at'],
        'containers_changed': False, 'secret_values_included': False,
    }


def logs(job_id: str) -> dict[str, Any]:
    if not re.fullmatch(r'toolchain_[a-f0-9]{24}', str(job_id or '')):
        raise ValueError('invalid_toolchain_job_id')
    connection = B.db()
    row = connection.execute(
        'select project_slug,status,log_text,last_error from toolchain_jobs where job_id=?', (job_id,)
    ).fetchone()
    connection.close()
    if not row:
        raise LookupError('toolchain_job_not_found')
    return {
        'ok': True, 'job_id': job_id, 'project_slug': row['project_slug'], 'status': row['status'],
        'logs': B.sanitize(row['log_text'] or ''), 'error': B.sanitize(row['last_error'] or '') or None,
        'secret_values_included': False,
    }


def images(project_slug: str, service: str = '') -> dict[str, Any]:
    if not B.SLUG.fullmatch(project_slug):
        raise ValueError('invalid_project_slug')
    connection = B.db()
    query = 'select * from toolchain_images where project_slug=?'
    args: list[Any] = [project_slug]
    if service:
        query += ' and service=?'
        args.append(service)
    query += ' order by created_at desc'
    rows = connection.execute(query, tuple(args)).fetchall()
    activations = connection.execute(
        'select * from toolchain_activations where project_slug=?', (project_slug,)
    ).fetchall()
    connection.close()
    active = {(row['environment'], row['service']): row['image_record_id'] for row in activations}
    result = []
    for row in rows:
        details = json.loads(row['result_json'] or '{}')
        result.append({
            'image_record_id': row['image_record_id'], 'service': row['service'],
            'toolchain_digest': row['toolchain_digest'], 'image_ref': row['image_ref'],
            'image_id': row['image_id'], 'config_revision': row['config_revision'],
            'config_digest': row['config_digest'], 'archive_sha256': row['archive_sha256'],
            'status': row['status'], 'created_at': row['created_at'],
            'active_environments': sorted(
                environment for (environment, svc), record in active.items()
                if svc == row['service'] and record == row['image_record_id']
            ),
            'sbom': {'ready': bool(details.get('sbomReady')), 'sha256': details.get('sbomSha256')},
            'scanner': {'blocked': bool(details.get('scannerBlocked')), 'counts': details.get('scannerCounts') or {}},
            'signature': {'verified': bool(details.get('signatureVerified'))},
            'secret_values_included': False,
        })
    return {'ok': True, 'project_slug': project_slug, 'images': result, 'count': len(result), 'secret_values_included': False}


def image_get(project_slug: str, image_record_id: str) -> dict[str, Any]:
    listing = images(project_slug)
    item = next((image for image in listing['images'] if image['image_record_id'] == image_record_id), None)
    if not item:
        raise LookupError('toolchain_image_not_found')
    connection = B.db()
    row = connection.execute(
        'select result_json from toolchain_images where image_record_id=? and project_slug=?',
        (image_record_id, project_slug),
    ).fetchone()
    connection.close()
    details = json.loads(row['result_json'] or '{}')
    details.pop('verification', None)
    return {'ok': True, 'project_slug': project_slug, 'image': {**item, 'details': details}, 'secret_values_included': False}


def activation_state(project_slug: str, environment: str) -> dict[str, Any]:
    connection = B.db()
    row = connection.execute(
        'select * from toolchain_activation_state where project_slug=? and environment=?',
        (project_slug, environment),
    ).fetchone()
    rows = connection.execute(
        'select service,image_record_id,toolchain_digest,activation_revision from toolchain_activations where project_slug=? and environment=? order by service',
        (project_slug, environment),
    ).fetchall()
    connection.close()
    return {
        'revision': int(row['revision']) if row else 0,
        'activation_digest': str(row['activation_digest']) if row else hashlib.sha256(b'[]').hexdigest(),
        'images': [dict(item) for item in rows],
    }


def activation_plan(payload: dict[str, Any]) -> dict[str, Any]:
    slug = str(payload.get('project_slug') or '').strip()
    environment = str(payload.get('environment') or '').strip().lower()
    job_id = str(payload.get('job_id') or '').strip()
    expected = int(payload.get('expected_revision') or 0)
    if not B.SLUG.fullmatch(slug):
        raise ValueError('invalid_project_slug')
    if environment not in ENVIRONMENTS:
        raise ValueError('invalid_environment')
    job = status(job_id)
    if job['project_slug'] != slug or job['status'] != 'succeeded':
        raise ValueError('toolchain_job_not_ready')
    current = activation_state(slug, environment)
    if expected != current['revision']:
        raise ValueError('activation_revision_mismatch')
    job_images = job['result'].get('images') or []
    if not job_images:
        raise ValueError('toolchain_images_missing')
    target = sorted([
        {
            'service': item['service'],
            'image_record_id': item['image_record_id'],
            'toolchain_digest': item['toolchain_digest'],
        }
        for item in job_images
    ], key=lambda item: item['service'])
    material = {
        'kind': 'toolchain-activation-v1', 'project_slug': slug, 'environment': environment,
        'job_id': job_id, 'expected_revision': expected, 'before': current['images'], 'after': target,
    }
    plan_digest = hashlib.sha256(B.canonical(material)).hexdigest()
    return {
        'ok': True, 'side_effect_free': True, 'project_slug': slug, 'environment': environment,
        'job_id': job_id, 'expected_revision': expected, 'next_revision': expected + 1,
        'plan_digest': plan_digest, 'before': current['images'], 'after': target,
        'approval_required': True, 'containers_changed': False, 'pending_rebuild': True,
        'secret_values_included': False,
    }


def activation_apply(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get('approved') is not True:
        raise PermissionError('approval_required')
    plan_data = activation_plan(payload)
    provided = str(payload.get('plan_digest') or '').lower()
    if not hmac.compare_digest(plan_data['plan_digest'], provided):
        raise ValueError('activation_plan_digest_mismatch')
    approval_id = str(payload.get('approval_id') or '')
    if not re.fullmatch(r'apr_[a-f0-9]{20}', approval_id):
        raise ValueError('invalid_approval_id')
    actor = str(payload.get('actor') or 'internal')[:128]
    timestamp = B.now()
    connection = B.db()
    connection.execute('begin immediate')
    current = connection.execute(
        'select revision from toolchain_activation_state where project_slug=? and environment=?',
        (plan_data['project_slug'], plan_data['environment']),
    ).fetchone()
    actual = int(current['revision']) if current else 0
    if actual != plan_data['expected_revision']:
        connection.rollback(); connection.close()
        raise ValueError('activation_revision_mismatch')
    for item in plan_data['after']:
        before = connection.execute(
            'select image_record_id from toolchain_activations where project_slug=? and environment=? and service=?',
            (plan_data['project_slug'], plan_data['environment'], item['service']),
        ).fetchone()
        before_id = before['image_record_id'] if before else None
        connection.execute(
            '''insert into toolchain_activations(
                 project_slug,environment,service,image_record_id,toolchain_digest,activation_revision,
                 approval_id,activated_by,activated_at
               ) values(?,?,?,?,?,?,?,?,?)
               on conflict(project_slug,environment,service) do update set
                 image_record_id=excluded.image_record_id,toolchain_digest=excluded.toolchain_digest,
                 activation_revision=excluded.activation_revision,approval_id=excluded.approval_id,
                 activated_by=excluded.activated_by,activated_at=excluded.activated_at''',
            (
                plan_data['project_slug'], plan_data['environment'], item['service'], item['image_record_id'],
                item['toolchain_digest'], plan_data['next_revision'], approval_id, actor, timestamp,
            ),
        )
        connection.execute(
            'insert into toolchain_activation_history(event_id,project_slug,environment,service,before_image_record_id,after_image_record_id,activation_revision,approval_id,actor,created_at) values(?,?,?,?,?,?,?,?,?,?)',
            (
                uuid.uuid4().hex, plan_data['project_slug'], plan_data['environment'], item['service'],
                before_id, item['image_record_id'], plan_data['next_revision'], approval_id, actor, timestamp,
            ),
        )
        connection.execute(
            "update toolchain_images set status='active',updated_at=? where image_record_id=?",
            (timestamp, item['image_record_id']),
        )
    connection.execute(
        '''insert into toolchain_activation_state(project_slug,environment,revision,activation_digest,updated_by,updated_at)
           values(?,?,?,?,?,?)
           on conflict(project_slug,environment) do update set
             revision=excluded.revision,activation_digest=excluded.activation_digest,
             updated_by=excluded.updated_by,updated_at=excluded.updated_at''',
        (
            plan_data['project_slug'], plan_data['environment'], plan_data['next_revision'],
            provided, actor, timestamp,
        ),
    )
    connection.commit(); connection.close()
    return {
        'ok': True, 'project_slug': plan_data['project_slug'], 'environment': plan_data['environment'],
        'revision': plan_data['next_revision'], 'activation_digest': provided,
        'images': plan_data['after'], 'approval_id': approval_id,
        'containers_changed': False, 'pending_rebuild': True, 'secret_values_included': False,
    }


def get(project_slug: str, ref: str = 'main') -> dict[str, Any]:
    plan_data = plan({'project_slug': project_slug, 'ref': ref, 'expected_revision': 0, 'trace_id': 'toolchain-get'})
    activations = {environment: activation_state(project_slug, environment) for environment in sorted(ENVIRONMENTS)}
    return {
        'ok': True, 'project_slug': project_slug, 'ref': ref,
        'configuration': {
            'config_revision': plan_data['config_revision'], 'config_digest': plan_data['config_digest'],
            'requested_toolchain_digest': plan_data['requested_toolchain_digest'], 'toolchain': plan_data['toolchain'],
        },
        'validation': {
            'blocked': plan_data['blocked'], 'warnings': plan_data['warnings'],
            'source_validation_required': plan_data['source_validation_required'],
        },
        'reusable_images': plan_data['reusable_images'], 'activations': activations,
        'secret_values_included': False,
    }


def recover_jobs() -> None:
    connection = B.db()
    rows = connection.execute(
        "select job_id from toolchain_jobs where status in ('queued','running') order by created_at"
    ).fetchall()
    connection.execute("update toolchain_jobs set status='queued' where status='running'")
    connection.commit(); connection.close()
    for row in rows:
        threading.Thread(target=_run_job, args=(row['job_id'],), daemon=True).start()


def compatible_activations(project_slug:str,environment:str,validations:list[dict[str,Any]],archive_sha256:str,config_digest:str)->dict[str,Any]:
    _require_configured()
    if environment not in ENVIRONMENTS:
        raise ValueError('invalid_environment')
    connection=B.db()
    rows=connection.execute(
        '''select a.service,a.image_record_id,a.toolchain_digest,a.activation_revision,
                  i.image_ref,i.image_id,i.config_digest,i.archive_sha256,i.status,i.result_json
           from toolchain_activations a
           join toolchain_images i on i.image_record_id=a.image_record_id
           where a.project_slug=? and a.environment=?''',
        (project_slug,environment),
    ).fetchall()
    connection.close()
    activated={row['service']:row for row in rows}
    active_images={};states=[];blocked=[]
    for validation in validations:
        service=validation['service'];row=activated.get(service)
        if not row:
            states.append({'service':service,'status':'not-activated','fallback':'default-build'})
            continue
        details=json.loads(row['result_json'] or '{}')
        source_bound=bool((details.get('script') or {}).get('path') or details.get('hooks'))
        reasons=[]
        if row['status'] not in {'ready','active'}:reasons.append('image-not-ready')
        if str(row['config_digest'])!=str(config_digest):reasons.append('config-digest-mismatch')
        if str(details.get('validatedToolchainDigest') or '')!=str(validation.get('toolchainDigest') or ''):reasons.append('toolchain-digest-mismatch')
        if source_bound and str(row['archive_sha256'])!=str(archive_sha256):reasons.append('source-archive-mismatch')
        if not bool(details.get('signatureVerified')):reasons.append('signature-not-verified')
        if bool(details.get('scannerBlocked')):reasons.append('scanner-blocked')
        if reasons:
            issue={'service':service,'code':'image-outdated','field':'toolchain.activation','environment':environment,'image_record_id':row['image_record_id'],'reasons':reasons}
            blocked.append(issue);states.append({'service':service,'status':'image-outdated','image_record_id':row['image_record_id'],'reasons':reasons})
            continue
        active_images[service]={
            'imageRecordId':row['image_record_id'],'imageRef':row['image_ref'],'imageId':row['image_id'],
            'effectiveToolchainDigest':row['toolchain_digest'],'validatedToolchainDigest':details.get('validatedToolchainDigest'),
            'configDigest':row['config_digest'],'archiveSha256':row['archive_sha256'],
            'activationRevision':int(row['activation_revision']),'environment':environment,
            'hooks':details.get('hooks') or [],'script':details.get('script') or {},
            'sbomReady':bool(details.get('sbomReady')),'sbomSha256':details.get('sbomSha256'),
            'scannerBlocked':False,'scannerCounts':details.get('scannerCounts') or {},
            'signatureVerified':True,'sourceArchiveBound':source_bound,'secretValuesIncluded':False,
        }
        states.append({'service':service,'status':'synchronized','image_record_id':row['image_record_id'],'activation_revision':int(row['activation_revision'])})
    return {'environment':environment,'images':active_images,'states':states,'blocked':blocked,'activeCount':len(active_images),'secretValuesIncluded':False}
