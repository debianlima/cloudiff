from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'components/control-plane/current-apps/project-config-controller-current/cloudif-project-config-controller.py'
SCHEMA = ROOT / 'components/control-plane/etc/cloudif/schemas/cloudiff-v1.schema.json'
UNIT = ROOT / 'components/control-plane/etc/systemd/system/cloudif-project-config-controller.service'


class ProjectConfigControllerHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        cls.control = root / 'control.db'
        cls.state = root / 'state.db'
        conn = sqlite3.connect(cls.control)
        conn.execute('create table projects(project_id text primary key,slug text,name text,owner text,tenant text,status text)')
        conn.execute('insert into projects values(?,?,?,?,?,?)', ('p1', 'http-project', 'HTTP Project', 'alice', 'tenant-http', 'active'))
        conn.commit(); conn.close()
        sock = socket.socket(); sock.bind(('127.0.0.1', 0)); cls.port = sock.getsockname()[1]; sock.close()
        cls.token = 'test-token-configuration-controller'
        env = os.environ.copy()
        env.update({
            'CLOUDIF_PROJECT_CONFIG_HOST': '127.0.0.1',
            'CLOUDIF_PROJECT_CONFIG_PORT': str(cls.port),
            'CLOUDIF_PROJECT_CONFIG_TOKEN': cls.token,
            'CLOUDIF_PROJECT_CONFIG_DB': str(cls.state),
            'CLOUDIF_PROJECT_SNAPSHOT_DB': str(cls.control),
            'CLOUDIF_PROJECT_MANIFEST_SCHEMA': str(SCHEMA),
        })
        cls.process = subprocess.Popen(['python3', str(APP)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{cls.port}/health', timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.1)
        else:
            stdout, stderr = cls.process.communicate(timeout=2)
            raise RuntimeError(f'controller failed to start: {stdout!r} {stderr!r}')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        try:
            cls.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.process.kill()
        cls.temp.cleanup()

    def request(self, method, path, body=None, authenticated=True):
        raw = json.dumps(body or {}, separators=(',', ':')).encode() if body is not None else None
        headers = {'Content-Type': 'application/json'}
        if authenticated:
            headers['Authorization'] = 'Bearer ' + self.token
        request = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}', data=raw, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_health_is_public_and_reports_observation_mode(self):
        status, body = self.request('GET', '/health', authenticated=False)
        self.assertEqual(status, 200)
        self.assertTrue(body['ok'])
        self.assertEqual(body['mode'], 'observation')
        self.assertFalse(body['secretsExposed'])

    def test_internal_routes_require_bearer_authentication(self):
        status, body = self.request('GET', '/v1/schema', authenticated=False)
        self.assertEqual(status, 401)
        self.assertEqual(body['error']['code'], 'unauthorized')

    def test_validation_returns_actionable_422(self):
        status, body = self.request('POST', '/v1/manifest/validate', {'manifest': {'runtime': 'static'}})
        self.assertEqual(status, 422)
        self.assertEqual(body['error']['code'], 'validation_failed')
        violation = next(item for item in body['error']['violations'] if item['field'] == 'version')
        self.assertEqual(violation['code'], 'required_field_missing')
        self.assertIn('documentation', violation)

    def test_plan_requires_approval_and_apply_is_idempotent(self):
        manifest = {
            'version': 1,
            'project': {'type': 'multi-service', 'primaryService': 'web'},
            'services': {
                'web': {'path': 'frontend', 'runtime': 'static', 'publish': 'dist', 'dependsOn': ['api']},
                'api': {'path': 'api', 'runtime': 'node', 'version': '24', 'start': ['npm', 'start'], 'port': 3000},
            },
        }
        status, plan = self.request('POST', '/v1/projects/http-project/configuration/plan', {
            'manifest': manifest, 'expectedRevision': 0, 'actor': 'alice', 'source': 'portal',
        })
        self.assertEqual(status, 200)
        self.assertTrue(plan['sideEffectFree'])
        self.assertTrue(plan['approvalRequired'])
        self.assertEqual(plan['serviceGraph']['serviceCount'], 2)
        status, denied = self.request('POST', '/v1/projects/http-project/configuration/apply', {
            'planDigest': plan['planDigest'], 'expectedRevision': 0, 'actor': 'alice',
        })
        self.assertEqual(status, 403)
        self.assertEqual(denied['error']['code'], 'approval_required')
        status, applied = self.request('POST', '/v1/projects/http-project/configuration/apply', {
            'planDigest': plan['planDigest'], 'expectedRevision': 0, 'actor': 'alice', 'approved': True,
        })
        self.assertEqual(status, 200)
        self.assertEqual(applied['revision'], 1)
        self.assertTrue(applied['observationMode'])
        status, repeated = self.request('POST', '/v1/projects/http-project/configuration/apply', {
            'planDigest': plan['planDigest'], 'expectedRevision': 0, 'actor': 'alice', 'approved': True,
        })
        self.assertEqual(status, 200)
        self.assertTrue(repeated['idempotent'])
        status, current = self.request('GET', '/v1/projects/http-project/configuration')
        self.assertEqual(status, 200)
        self.assertEqual(current['currentRevision'], 1)
        self.assertEqual(current['configuration']['project']['type'], 'multi-service')

    def test_membership_event_only_changes_membership_revision(self):
        status, before = self.request('GET', '/v1/projects/http-project/configuration')
        self.assertEqual(status, 200)
        status, event = self.request('POST', '/v1/projects/http-project/events', {
            'eventType': 'project.member.removed',
            'details': {
                'subject': 'bob', 'role': 'viewer', 'password': 'must-not-persist',
                'nested': {'databaseUrl': 'postgres://user:password@db.internal/app'},
            },
        })
        self.assertEqual(status, 200)
        self.assertEqual(event['membershipRevision'], before['membershipRevision'] + 1)
        self.assertFalse(event['runtimeChanged'])
        status, after = self.request('GET', '/v1/projects/http-project/configuration')
        self.assertEqual(after['currentRevision'], before['currentRevision'])
        details = after['events'][0]['details']
        self.assertEqual(details['password'], '<redacted>')
        self.assertEqual(details['nested']['databaseUrl'], '<redacted>')
        self.assertFalse(details['secretValuesIncluded'])

    def test_systemd_unit_is_local_and_hardened(self):
        unit = UNIT.read_text()
        for marker in (
            'CLOUDIF_PROJECT_CONFIG_HOST=127.0.0.1',
            'CLOUDIF_PROJECT_CONFIG_PORT=18219',
            'NoNewPrivileges=true',
            'ProtectSystem=strict',
            'IPAddressAllow=127.0.0.0/8',
            'IPAddressDeny=any',
            'CapabilityBoundingSet=',
        ):
            self.assertIn(marker, unit)


if __name__ == '__main__':
    unittest.main()
