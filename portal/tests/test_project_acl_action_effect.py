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
    def __init__(self, module, fields):
        self.path = '/cloudiff/portal/action/project_acl'
        self._user = {
            'username': 'alice',
            'email': 'alice@example.invalid',
            'groups': ['CloudIF-Aluno'],
            'admin': False,
        }
        body = urllib.parse.urlencode(fields).encode('utf-8')
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.headers = email.message.Message()
        self.headers['Content-Length'] = str(len(body))
        self.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        self.headers['Host'] = 'cloudiff.duckdns.org'
        self.headers['Origin'] = 'https://cloudiff.duckdns.org'
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


class ProjectAclActionEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.db_path = cls.root / 'portal.db'
        cls.old_env = {key: os.environ.get(key) for key in (
            'CLOUDIF_PORTAL_DB', 'CLOUDIF_BASE', 'CLOUDIF_CSRF_SECRET',
            'CLOUDIF_PUBLIC_HOST', 'CLOUDIF_PORTAL_HOST', 'CLOUDIF_PORTAL_PORT',
            'CLOUDIF_ACCESS_INGEST_DB',
        )}
        os.environ.update({
            'CLOUDIF_PORTAL_DB': str(cls.db_path),
            'CLOUDIF_BASE': str(cls.root / 'cloudif'),
            'CLOUDIF_CSRF_SECRET': 'project-acl-effect-test-secret',
            'CLOUDIF_PUBLIC_HOST': 'cloudiff.duckdns.org',
            'CLOUDIF_PORTAL_HOST': '127.0.0.1',
            'CLOUDIF_PORTAL_PORT': '19089',
            'CLOUDIF_ACCESS_INGEST_DB': str(cls.root / 'access-ingest.db'),
        })
        (cls.root / 'cloudif').mkdir(parents=True)
        sys.path.insert(0, str(PORTAL_CURRENT))
        sys.path.insert(0, str(LIB))
        spec = importlib.util.spec_from_file_location('cloudiff_project_acl_effect_portal', BASE_PORTAL)
        cls.portal = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.portal)
        cls.portal.init_db()

        import cloudif_project_acl_module as project_acl
        import cloudif_reconcile_client as reconcile
        cls.project_acl = project_acl
        cls.reconcile = reconcile
        cls.old_acl_db = project_acl.DB
        cls.old_sync = project_acl.sync_komodo_acl
        cls.old_enqueue = reconcile.enqueue
        project_acl.DB = str(cls.db_path)
        cls.events = []
        cls.sync_calls = []
        reconcile.enqueue = lambda event, **kwargs: cls.events.append((event, kwargs)) or {'ok': True}

    @classmethod
    def tearDownClass(cls):
        cls.project_acl.DB = cls.old_acl_db
        cls.project_acl.sync_komodo_acl = cls.old_sync
        cls.reconcile.enqueue = cls.old_enqueue
        cls.portal._close_db_anchor()
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

    def setUp(self):
        self.events.clear()
        self.sync_calls.clear()
        self.project_acl.sync_komodo_acl = self._sync_ok
        with sqlite3.connect(self.db_path) as con:
            con.execute('DELETE FROM project_acl')
            con.execute('DELETE FROM projects')
            con.execute('DELETE FROM action_log')
            con.execute(
                '''INSERT INTO projects(slug,name,tenant,owner,description,repo_url,komodo_status,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?)''',
                ('demo', 'Demo', 'alice-db', 'alice', 'demo', '', 'running',
                 '2026-08-27T23:00:00Z', '2026-08-27T23:00:00Z'),
            )
            con.commit()

    def _sync_ok(self, slug):
        self.sync_calls.append(slug)
        return {'ok': True}

    def _post(self, **fields):
        user = {
            'username': 'alice',
            'email': 'alice@example.invalid',
            'groups': ['CloudIF-Aluno'],
            'admin': False,
        }
        payload = dict(fields)
        payload['csrf_token'] = self.portal._prod_csrf_token(user)
        handler = _Handler(self.portal, payload)
        self.portal.Portal.do_POST(handler)
        return handler

    def _rows(self):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            return [dict(row) for row in con.execute(
                'SELECT id,slug,subject_type,subject FROM project_acl ORDER BY id'
            )]

    def _location(self, handler):
        return dict(handler.response_headers).get('Location', '')

    def test_add_and_remove_change_acl_sync_komodo_and_enqueue_reconciliation(self):
        added = self._post(
            op='add', slug='demo', principal_type='user', principal='bob',
        )
        self.assertEqual(added.status, 303)
        rows = self._rows()
        self.assertEqual([(r['slug'], r['subject_type'], r['subject']) for r in rows], [
            ('demo', 'user', 'bob')
        ])
        self.assertEqual(self.sync_calls, ['demo'])
        self.assertEqual(len(self.events), 1)
        self.assertEqual(self.events[0][0], 'project.membership.changed')
        self.assertEqual(self.events[0][1]['project'], 'demo')
        self.assertEqual(self.events[0][1]['payload']['operation'], 'add')
        self.assertEqual(self.events[0][1]['payload']['principal'], 'bob')
        self.assertEqual(self.events[0][1]['payload']['targets'], ['portal','forgejo','tenant','publication'])

        removed = self._post(
            op='remove', slug='demo', row_id=str(rows[0]['id']),
            principal_type='user', principal='bob',
        )
        self.assertEqual(removed.status, 303)
        self.assertEqual(self._rows(), [])
        self.assertEqual(self.sync_calls, ['demo', 'demo'])
        self.assertEqual(len(self.events), 2)
        self.assertEqual(self.events[1][1]['payload']['operation'], 'remove')
        self.assertEqual(self.events[1][1]['payload']['principal'], 'bob')

    def test_owner_remove_is_blocked_without_db_sync_or_queue_effect(self):
        with sqlite3.connect(self.db_path) as con:
            cur = con.execute(
                'INSERT INTO project_acl(slug,subject_type,subject) VALUES(?,?,?)',
                ('demo', 'user', 'alice'),
            )
            owner_id = cur.lastrowid
            con.commit()
        before = self._rows()
        blocked = self._post(
            op='remove', slug='demo', row_id=str(owner_id),
            principal_type='user', principal='alice',
        )
        self.assertEqual(blocked.status, 303)
        self.assertEqual(self._rows(), before)
        self.assertEqual(self.sync_calls, [])
        self.assertEqual(self.events, [])
        self.assertIn('proibido', urllib.parse.unquote(self._location(blocked)).lower())

    def test_saved_acl_is_still_reconciled_when_immediate_komodo_sync_fails(self):
        self.project_acl.sync_komodo_acl = lambda slug: {'ok': False, 'error': 'synthetic_sync_failure'}
        result = self._post(
            op='add', slug='demo', principal_type='user', principal='carol',
        )
        self.assertEqual(result.status, 303)
        self.assertEqual([(r['subject_type'], r['subject']) for r in self._rows()], [('user', 'carol')])
        # Central ACL is already committed; recovery must still be durable.
        self.assertEqual(len(self.events), 1)
        self.assertEqual(self.events[0][0], 'project.membership.changed')
        self.assertEqual(self.events[0][1]['payload']['operation'], 'add')
        self.assertIn('pendente', urllib.parse.unquote(self._location(result)).lower())

    def test_missing_csrf_has_no_acl_sync_or_queue_effect(self):
        handler = _Handler(self.portal, {
            'op': 'add', 'slug': 'demo', 'principal_type': 'user', 'principal': 'mallory',
        })
        self.portal.Portal.do_POST(handler)
        self.assertEqual(handler.status, 403)
        self.assertEqual(self._rows(), [])
        self.assertEqual(self.sync_calls, [])
        self.assertEqual(self.events, [])


if __name__ == '__main__':
    unittest.main()
