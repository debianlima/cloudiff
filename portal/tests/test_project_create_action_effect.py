import email.message
import importlib.util
import io
import json
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
    def __init__(self, module, fields, csrf=True):
        self.path = '/cloudiff/portal/'
        self._user = {
            'username': 'alice',
            'email': 'alice@example.invalid',
            'groups': ['CloudIF-Aluno'],
            'admin': False,
        }
        payload = dict(fields)
        if csrf:
            payload['csrf_token'] = module._prod_csrf_token(self._user)
        body = urllib.parse.urlencode(payload).encode('utf-8')
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.headers = email.message.Message()
        self.headers['Content-Length'] = str(len(body))
        self.headers['Content-Type'] = 'application/x-www-form-urlencoded;charset=UTF-8'
        self.headers['Host'] = 'cloudiff.duckdns.org'
        self.headers['Origin'] = 'https://cloudiff.duckdns.org'
        self.headers['Accept'] = 'application/json'
        self.headers['X-CloudIF-Action'] = 'project_action'
        self.headers['X-CloudIF-Async'] = 'project-provision'
        self.headers['X-authentik-username'] = 'alice'
        self.headers['X-authentik-email'] = 'alice@example.invalid'
        self.headers['X-authentik-groups'] = 'CloudIF-Aluno'
        self.status = None
        self.response_headers = []

    def user(self):
        return dict(self._user)

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.response_headers.append((name, value))

    def end_headers(self):
        return None

    def send_html(self, body, status=200):
        self.status = status
        self.wfile.write(str(body).encode('utf-8'))
        return None

    def redirect(self, location):
        self.status = 303
        self.response_headers.append(('Location', location))
        return None


class ProjectCreateActionEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.db_path = cls.root / 'portal.db'
        cls.job_dir = cls.root / 'jobs'
        cls.lock_dir = cls.root / 'locks'
        cls.old_env = {key: os.environ.get(key) for key in (
            'CLOUDIF_PORTAL_DB', 'CLOUDIF_BASE', 'CLOUDIF_CSRF_SECRET',
            'CLOUDIF_PUBLIC_HOST', 'CLOUDIF_PORTAL_HOST', 'CLOUDIF_PORTAL_PORT',
            'CLOUDIF_ACCESS_INGEST_DB',
        )}
        os.environ.update({
            'CLOUDIF_PORTAL_DB': str(cls.db_path),
            'CLOUDIF_BASE': str(cls.root / 'cloudif'),
            'CLOUDIF_CSRF_SECRET': 'project-create-effect-test-secret',
            'CLOUDIF_PUBLIC_HOST': 'cloudiff.duckdns.org',
            'CLOUDIF_PORTAL_HOST': '127.0.0.1',
            'CLOUDIF_PORTAL_PORT': '19089',
            'CLOUDIF_ACCESS_INGEST_DB': str(cls.root / 'access-ingest.db'),
        })
        (cls.root / 'cloudif').mkdir(parents=True)
        sys.path.insert(0, str(PORTAL_CURRENT))
        sys.path.insert(0, str(LIB))
        cls.previous_delete_action_module = sys.modules.pop('cloudif_delete_git_komodo_action', None)
        delete_spec = importlib.util.spec_from_file_location(
            'cloudif_delete_git_komodo_action', LIB / 'cloudif_delete_git_komodo_action.py'
        )
        delete_module = importlib.util.module_from_spec(delete_spec)
        sys.modules['cloudif_delete_git_komodo_action'] = delete_module
        delete_spec.loader.exec_module(delete_module)

        spec = importlib.util.spec_from_file_location('cloudiff_project_create_effect_portal', BASE_PORTAL)
        cls.portal = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.portal)
        cls.portal.init_db()

        import cloudif_project_action_safe as safe
        import cloudif_reconcile_client as reconcile
        cls.safe = safe
        cls.reconcile = reconcile
        cls.old_safe_db = safe.DB
        cls.old_jobdir = safe.JOBDIR
        cls.old_lock_root = safe.LOCK_ROOT
        cls.old_log = safe.LOG
        cls.old_queue = safe.queue_provision_job
        cls.old_enqueue = reconcile.enqueue
        safe.DB = str(cls.db_path)
        safe.JOBDIR = cls.job_dir
        safe.LOCK_ROOT = cls.lock_dir
        safe.LOG = cls.root / 'project-provision.log'
        cls.events = []
        reconcile.enqueue = cls._enqueue
        safe.queue_provision_job = cls._queue

    @classmethod
    def tearDownClass(cls):
        cls.safe.DB = cls.old_safe_db
        cls.safe.JOBDIR = cls.old_jobdir
        cls.safe.LOCK_ROOT = cls.old_lock_root
        cls.safe.LOG = cls.old_log
        cls.safe.queue_provision_job = cls.old_queue
        cls.reconcile.enqueue = cls.old_enqueue
        cls.portal._close_db_anchor()
        if cls.previous_delete_action_module is None:
            sys.modules.pop('cloudif_delete_git_komodo_action', None)
        else:
            sys.modules['cloudif_delete_git_komodo_action'] = cls.previous_delete_action_module
        for path in (str(LIB), str(PORTAL_CURRENT)):
            try:
                sys.path.remove(path)
            except ValueError:
                pass
        for key, value in cls.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls.tmp.cleanup()

    @classmethod
    def _queue(cls, job):
        cls.job_dir.mkdir(parents=True, exist_ok=True)
        payload = dict(job)
        payload['job_id'] = 'job-effect-001'
        path = cls.job_dir / ('project-provision-job-effect-001-' + job['slug'] + '.json')
        path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
        return {'job_file': str(path), 'deduplicated': False, 'job': payload}

    @classmethod
    def _enqueue(cls, event, **kwargs):
        record = {'event': event, **kwargs}
        cls.events.append(record)
        return {'request_id': 'req-project-create-001', 'status': 'queued'}

    def setUp(self):
        self.events.clear()
        self.job_dir.mkdir(parents=True, exist_ok=True)
        for path in self.job_dir.glob('*'):
            path.unlink()
        with sqlite3.connect(self.db_path) as con:
            for table in ('project_acl', 'projects', 'tenants', 'action_log'):
                try:
                    con.execute(f'DELETE FROM {table}')
                except sqlite3.OperationalError:
                    pass
            con.commit()

    def _fields(self, **overrides):
        fields = {
            'action': 'create_project',
            'name': 'Sistema Biblioteca',
            'description': 'Aplicação de empréstimos',
            'db_mode': 'create',
            'tenant': '',
            'tenant_suffix': 'biblioteca',
            'tenant_keepalive_hours': '6',
            'runtime_template': 'node22',
            'php_version': '8.3',
            'create_repo': '1',
            'setup_komodo': '1',
        }
        fields.update(overrides)
        return fields

    def _post(self, csrf=True, **overrides):
        handler = _Handler(self.portal, self._fields(**overrides), csrf=csrf)
        self.portal.Portal.do_POST(handler)
        body = handler.wfile.getvalue().decode('utf-8')
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {'raw': body}
        return handler, data

    def _project(self, slug='sistema-biblioteca'):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            row = con.execute('SELECT * FROM projects WHERE slug=?', (slug,)).fetchone()
            return dict(row) if row else None

    def _acl(self, slug='sistema-biblioteca'):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            return [dict(row) for row in con.execute(
                'SELECT * FROM project_acl WHERE slug=? ORDER BY rowid', (slug,)
            )]

    def test_create_project_persists_owner_acl_durable_job_and_reconciliation(self):
        handler, data = self._post()
        self.assertEqual(handler.status, 202, data)
        self.assertTrue(data['ok'])
        self.assertEqual(data['slug'], 'sistema-biblioteca')
        self.assertEqual(data['tenant'], 'alice-biblioteca')
        self.assertEqual(
            data['status_url'],
            '/cloudiff/portal/api/project-provision-status?slug=sistema-biblioteca',
        )

        project = self._project()
        self.assertIsNotNone(project)
        self.assertEqual(project['name'], 'Sistema Biblioteca')
        self.assertEqual(project['description'], 'Aplicação de empréstimos')
        self.assertEqual(project['tenant'], 'alice-biblioteca')
        self.assertEqual(project['owner'], 'alice')

        acl = self._acl()
        self.assertEqual(len(acl), 1)
        self.assertEqual(acl[0]['subject_type'], 'user')
        self.assertEqual(acl[0]['subject'], 'alice')

        jobs = list(self.job_dir.glob('project-provision-*.json'))
        self.assertEqual(len(jobs), 1)
        job = json.loads(jobs[0].read_text(encoding='utf-8'))
        self.assertEqual(job['action'], 'create_project')
        self.assertEqual(job['slug'], 'sistema-biblioteca')
        self.assertEqual(job['tenant'], 'alice-biblioteca')
        self.assertEqual(job['runtime_template'], 'node22')
        self.assertEqual(job['php_version'], '8.3')
        self.assertEqual(job['tenant_keepalive_hours'], 6)
        self.assertEqual(job['status'], 'queued')

        self.assertEqual(len(self.events), 1)
        event = self.events[0]
        self.assertEqual(event['event'], 'project.created')
        self.assertEqual(event['actor'], 'alice')
        self.assertEqual(event['username'], 'alice')
        self.assertEqual(event['project'], 'sistema-biblioteca')
        self.assertEqual(event['tenant'], 'alice-biblioteca')
        self.assertEqual(event['payload']['runtime_template'], 'node22')
        self.assertEqual(event['payload']['runtime_layout'], 'managed-root-v1')

    def test_invalid_runtime_has_zero_project_acl_job_or_reconcile_effect(self):
        handler, data = self._post(runtime_template='node99')
        self.assertEqual(handler.status, 500, data)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'], 'project_provision_start_failed')
        self.assertIsNone(self._project())
        self.assertEqual(self._acl(), [])
        self.assertEqual(list(self.job_dir.glob('*')), [])
        self.assertEqual(self.events, [])

    def test_missing_csrf_has_zero_effect(self):
        handler, _ = self._post(csrf=False)
        self.assertEqual(handler.status, 403)
        self.assertIsNone(self._project())
        self.assertEqual(self._acl(), [])
        self.assertEqual(list(self.job_dir.glob('*')), [])
        self.assertEqual(self.events, [])


if __name__ == '__main__':
    unittest.main()
