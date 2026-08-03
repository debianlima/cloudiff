#!/usr/bin/env python3
import datetime
import fcntl
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

LABEL = 'cloudif.managed=true'
MAX_AGE = 900
LOCK = '/run/lock/cloudif-workspace-cleanup.lock'
STATE = '/var/lib/cloudif/health/workspace-cleanup.json'
WORKSPACE_ROOT = '/var/lib/cloudif/workspaces'


def atomic_write(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.workspace-cleanup-', dir=str(target.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(',', ':'))
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def docker(*args, tolerate_missing=False, tolerate_removing=False):
    env = dict(os.environ)
    env['DOCKER_CONFIG'] = '/run/cloudif-docker-config-empty'
    os.makedirs(env['DOCKER_CONFIG'], mode=0o700, exist_ok=True)
    process = subprocess.run(
        ['/usr/bin/docker', *args],
        text=True,
        capture_output=True,
        timeout=30,
        env=env,
    )
    message = (process.stderr or process.stdout or '').strip()
    if process.returncode:
        lowered = message.lower()
        if tolerate_missing and ('no such container' in lowered or 'not found' in lowered):
            return ''
        if tolerate_removing and 'removal of container' in lowered and 'already in progress' in lowered:
            return ''
        raise RuntimeError(message[:500] or f'docker exited {process.returncode}')
    return process.stdout


def main():
    Path(LOCK).parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK, 'w', encoding='utf-8') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'ok': True, 'execution_mode': 'busy'}, separators=(',', ':')))
            return 0

        started = time.time()
        removed, kept, ignored = [], [], []
        removed_dirs, kept_dirs = [], []
        ids = [item for item in docker('ps', '-aq', '--filter', 'label=' + LABEL).split() if item]
        now = time.time()
        live_ids = set()
        for container_id in ids:
            try:
                raw = docker('inspect', container_id, tolerate_missing=True)
                if not raw:
                    ignored.append({'id': container_id[:12], 'reason': 'already_removed'})
                    continue
                data = json.loads(raw)[0]
                created = data['Created']
                timestamp = datetime.datetime.fromisoformat(created.replace('Z', '+00:00')).timestamp()
                age = max(0, now - timestamp)
                state = data['State']['Status']
                if state != 'running' or age > MAX_AGE:
                    docker('rm', '-f', container_id, tolerate_missing=True, tolerate_removing=True)
                    removed.append({'id': container_id[:12], 'state': state, 'age_seconds': round(age)})
                else:
                    live_ids.add(container_id)
                    kept.append({'id': container_id[:12], 'state': state, 'age_seconds': round(age)})
            except Exception as exc:
                ignored.append({'id': container_id[:12], 'reason': type(exc).__name__, 'message': str(exc)[:180]})

        if os.path.isdir(WORKSPACE_ROOT):
            for entry in os.scandir(WORKSPACE_ROOT):
                if not entry.is_dir(follow_symlinks=False):
                    kept_dirs.append({'name': entry.name, 'reason': 'not_directory'})
                    continue
                try:
                    age = max(0, now - entry.stat(follow_symlinks=False).st_mtime)
                except FileNotFoundError:
                    continue
                if live_ids:
                    kept_dirs.append({'name': entry.name, 'age_seconds': round(age), 'reason': 'managed_container_exists'})
                elif age > MAX_AGE:
                    try:
                        shutil.rmtree(entry.path)
                        removed_dirs.append({'name': entry.name, 'age_seconds': round(age)})
                    except FileNotFoundError:
                        pass
                else:
                    kept_dirs.append({'name': entry.name, 'age_seconds': round(age), 'reason': 'fresh'})

        payload = {
            'ok': True,
            'generated_at': datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
            'execution_mode': 'cleanup',
            'removed': removed,
            'kept': kept,
            'ignored': ignored,
            'removed_dirs': removed_dirs,
            'kept_dirs': kept_dirs,
            'max_age_seconds': MAX_AGE,
            'duration_ms': round((time.time() - started) * 1000),
            'secrets_exposed': False,
        }
        atomic_write(STATE, payload)
        print(json.dumps(payload, separators=(',', ':')))
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
