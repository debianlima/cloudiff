import datetime as dt
import email.message
import importlib.util
import io
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
import urllib.parse

ROOT = Path(__file__).resolve().parents[2]
BASE_PORTAL = ROOT / 'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
LIB = ROOT / 'components/control-plane/srv/cloudif/lib'
PORTAL_CURRENT = ROOT / 'components/control-plane/current-apps/portal-current'


class _Handler:
    def __init__(self, module, user, fields):
        self._module = module
        self._user = dict(user)
        self.path = '/cloudiff/portal/action/tenant_action'
        payload = dict(fields)
        payload['csrf_token'] = module._prod_csrf_token(self._user)
        body = urllib.parse.urlencode(payload).encode('utf-8')
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.headers = email.message.Message()
        self.headers['Content-Length'] = str(len(body))
        self.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        self.headers['Host'] = 'cloudiff.duckdns.org'
        self.headers['Origin'] = 'https://cloudiff.duckdns.org'
        self.status = None
        self.redirected = None
        self.response_headers = []

    def user(self):
        return dict(self._user)

    def redirect(self, location):
        self.status = 303
        self.redirected = location
        return None

    def send_html(self, body, status=200):
        self.status = status
        self.wfile.write(str(body).encode('utf-8'))
        return None

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.response_headers.append((name, value))

    def end_headers(self):
        return None


class TenantActionEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.base = cls.root / 'cloudif'
        cls.base.mkdir(parents=True)
        cls.db_path = cls.root / 'portal.db'
        cls.old_env = {key: os.environ.get(key) for key in (
            'CLOUDIF_PORTAL_DB', 'CLOUDIF_BASE', 'CLOUDIF_CSRF_SECRET',
            'CLOUDIF_PUBLIC_HOST', 'CLOUDIF_PORTAL_HOST', 'CLOUDIF_PORTAL_PORT',
            'CLOUDIF_ACCESS_INGEST_DB',
        )}
        os.environ.update({
            'CLOUDIF_PORTAL_DB': str(cls.db_path),
            'CLOUDIF_BASE': str(cls.base),
            'CLOUDIF_CSRF_SECRET': 'tenant-action-effect-test-secret',
            'CLOUDIF_PUBLIC_HOST': 'cloudiff.duckdns.org',
            'CLOUDIF_PORTAL_HOST': '127.0.0.1',
            'CLOUDIF_PORTAL_PORT': '19089',
            'CLOUDIF_ACCESS_INGEST_DB': str(cls.root / 'access-ingest.db'),
        })
        sys.path.insert(0, str(PORTAL_CURRENT))
        sys.path.insert(0, str(LIB))
        spec = importlib.util.spec_from_file_location('cloudiff_tenant_action_effect_portal', BASE_PORTAL)
        cls.portal = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.portal)
        cls.portal.init_db()
        for tenant in ('student', 'course-db'):
            tdir = cls.base / 'tenants' / tenant
            tdir.mkdir(parents=True, exist_ok=True)
            (tdir / '.env').write_text('TENANT=' + tenant + '\n', encoding='utf-8')
        cls.student = {
            'username': 'student', 'email': 'student@example.invalid',
            'groups': ['CloudIF-Aluno'], 'admin': False,
        }
        cls.admin = {
            'username': 'ui-audit-admin', 'email': 'ui-audit-admin@example.invalid',
            'groups': ['CloudIF-Tenants-Admin'], 'admin': True,
        }
        cls.old_run = cls.portal.run
        cls.old_running = cls.portal.tenant_is_running

    @classmethod
    def tearDownClass(cls):
        cls.portal.run = cls.old_run
        cls.portal.tenant_is_running = cls.old_running
        cls.portal._close_db_anchor()
        for path in (str(LIB), str(PORTAL_CURRENT)):
            if path in sys.path:
                sys.path.remove(path)
        for key, value in cls.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls.tmp.cleanup()

    def setUp(self):
        self.commands = []
        self.running = False
        self.portal.run = lambda command, timeout=120: self._run(command, timeout)
        self.portal.tenant_is_running = lambda tenant: self.running
        with sqlite3.connect(self.db_path) as con:
            con.execute('DELETE FROM tenant_policy')
            con.execute('DELETE FROM action_log')
            con.commit()

    def _run(self, command, timeout):
        self.commands.append((command, timeout))
        return 0, 'ok', ''

    def _post(self, user, **fields):
        handler = _Handler(self.portal, user, fields)
        self.portal.Portal.do_POST(handler)
        return handler

    def _policy(self, tenant):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            row = con.execute(
                'SELECT tenant,always_alive,keepalive_until,max_hours FROM tenant_policy WHERE tenant=?',
                (tenant,),
            ).fetchone()
            return dict(row) if row else None

    def test_student_keepalive_starts_stopped_tenant_and_persists_timed_policy(self):
        before = dt.datetime.now(dt.timezone.utc)
        result = self._post(self.student, op='keepalive', tenant='student', hours='3')
        after = dt.datetime.now(dt.timezone.utc)
        self.assertEqual(result.status, 303)
        self.assertIn('tab=bancos', result.redirected or '')
        self.assertEqual(len(self.commands), 1)
        command = self.commands[0][0]
        self.assertEqual(command[:2], ['bash', '-lc'])
        self.assertIn('docker compose --env-file .env up -d', command[2])
        policy = self._policy('student')
        self.assertEqual(policy['always_alive'], 0)
        self.assertEqual(policy['max_hours'], 3)
        deadline = dt.datetime.fromisoformat(policy['keepalive_until'])
        self.assertGreaterEqual(deadline, before + dt.timedelta(hours=3, seconds=-1))
        self.assertLessEqual(deadline, after + dt.timedelta(hours=3, seconds=2))

    def test_admin_always_on_start_starts_stopped_tenant_and_persists_exclusive_policy(self):
        result = self._post(self.admin, op='always_on_start', tenant='course-db')
        self.assertEqual(result.status, 303)
        self.assertEqual(len(self.commands), 1)
        self.assertIn('docker compose --env-file .env up -d', self.commands[0][0][2])
        policy = self._policy('course-db')
        self.assertEqual(policy['always_alive'], 1)
        self.assertIsNone(policy['keepalive_until'])
        self.assertEqual(policy['max_hours'], 24)

    def test_admin_always_off_persists_one_hour_deadline_without_starting_docker(self):
        self.running = True
        before = dt.datetime.now(dt.timezone.utc)
        result = self._post(self.admin, op='always_off', tenant='course-db')
        after = dt.datetime.now(dt.timezone.utc)
        self.assertEqual(result.status, 303)
        self.assertEqual(self.commands, [])
        policy = self._policy('course-db')
        self.assertEqual(policy['always_alive'], 0)
        self.assertEqual(policy['max_hours'], 0)
        deadline = dt.datetime.fromisoformat(policy['keepalive_until'])
        self.assertGreaterEqual(deadline, before + dt.timedelta(hours=1, seconds=-1))
        self.assertLessEqual(deadline, after + dt.timedelta(hours=1, seconds=2))

    def test_start_and_stop_delegate_to_operational_docker_commands_for_owner(self):
        started = self._post(self.student, op='start', tenant='student')
        stopped = self._post(self.student, op='stop', tenant='student')
        self.assertEqual(started.status, 303)
        self.assertEqual(stopped.status, 303)
        self.assertEqual(len(self.commands), 2)
        self.assertIn('docker compose --env-file .env up -d', self.commands[0][0][2])
        self.assertIn('docker compose --env-file .env stop', self.commands[1][0][2])


if __name__ == '__main__':
    unittest.main()
