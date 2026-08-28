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
        self._module = module
        self.path = '/cloudiff/portal/action/tenant_acl'
        self._user = {
            'username': 'ui-audit-admin',
            'email': 'ui-audit-admin@example.invalid',
            'groups': ['CloudIF-Tenants-Admin'],
            'admin': True,
        }
        body = urllib.parse.urlencode(fields).encode('utf-8')
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


class TenantAclActionEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.tmp.name) / 'cloudif'
        cls.base.mkdir(parents=True)
        cls.db_path = Path(cls.tmp.name) / 'portal.db'
        cls.old_env = {k: os.environ.get(k) for k in (
            'CLOUDIF_PORTAL_DB', 'CLOUDIF_BASE', 'CLOUDIF_CSRF_SECRET',
            'CLOUDIF_PUBLIC_HOST', 'CLOUDIF_PORTAL_HOST', 'CLOUDIF_PORTAL_PORT',
            'CLOUDIF_ACCESS_INGEST_DB',
        )}
        os.environ.update({
            'CLOUDIF_PORTAL_DB': str(cls.db_path),
            'CLOUDIF_BASE': str(cls.base),
            'CLOUDIF_CSRF_SECRET': 'tenant-acl-effect-test-secret',
            'CLOUDIF_PUBLIC_HOST': 'cloudiff.duckdns.org',
            'CLOUDIF_PORTAL_HOST': '127.0.0.1',
            'CLOUDIF_PORTAL_PORT': '19089',
            'CLOUDIF_ACCESS_INGEST_DB': str(Path(cls.tmp.name) / 'access-ingest.db'),
        })
        sys.path.insert(0, str(PORTAL_CURRENT))
        sys.path.insert(0, str(LIB))
        spec = importlib.util.spec_from_file_location('cloudiff_tenant_acl_effect_portal', BASE_PORTAL)
        cls.portal = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.portal)
        cls.portal.init_db()

        import cloudif_ad_directory_module as directory
        import cloudif_reconcile_client as reconcile
        cls.directory = directory
        cls.reconcile = reconcile
        cls.old_user_from_headers = directory.user_from_headers
        cls.old_search = directory.search
        cls.old_enqueue = reconcile.enqueue
        directory.user_from_headers = lambda headers: {'username': 'ui-audit-admin'}
        directory.search = lambda subject, stype, user=None, diagnostics=False: {
            'items': [{'principal': subject, 'type': stype}]
        }
        cls.events = []
        reconcile.enqueue = lambda event, **kwargs: cls.events.append((event, kwargs)) or {'ok': True}

    @classmethod
    def tearDownClass(cls):
        cls.directory.user_from_headers = cls.old_user_from_headers
        cls.directory.search = cls.old_search
        cls.reconcile.enqueue = cls.old_enqueue
        cls.portal._close_db_anchor()
        if str(LIB) in sys.path:
            sys.path.remove(str(LIB))
        if str(PORTAL_CURRENT) in sys.path:
            sys.path.remove(str(PORTAL_CURRENT))
        for key, value in cls.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls.tmp.cleanup()

    def setUp(self):
        self.events.clear()
        with sqlite3.connect(self.db_path) as con:
            con.execute('DELETE FROM tenant_acl')
            con.execute('DELETE FROM action_log')
            con.commit()

    def _post(self, **fields):
        user = {
            'username': 'ui-audit-admin',
            'email': 'ui-audit-admin@example.invalid',
            'groups': ['CloudIF-Tenants-Admin'],
            'admin': True,
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
                'SELECT id,tenant,subject_type,subject FROM tenant_acl ORDER BY id'
            )]

    def test_add_and_remove_change_sqlite_and_enqueue_reconciliation(self):
        added = self._post(
            op='add', tenant='alice-db', subject_type='user', subject='bob',
            identity_verified='user:bob',
        )
        self.assertEqual(added.status, 303)
        self.assertIn('tab=bancos', added.redirected or '')
        rows = self._rows()
        self.assertEqual([(r['tenant'], r['subject_type'], r['subject']) for r in rows], [
            ('alice-db', 'user', 'bob')
        ])
        self.assertEqual(len(self.events), 1)
        self.assertEqual(self.events[0][0], 'tenant.membership.changed')
        self.assertEqual(self.events[0][1]['payload']['operation'], 'add')
        self.assertEqual(self.events[0][1]['tenant'], 'alice-db')

        removed = self._post(op='remove', id=str(rows[0]['id']))
        self.assertEqual(removed.status, 303)
        self.assertEqual(self._rows(), [])
        self.assertEqual(len(self.events), 2)
        self.assertEqual(self.events[1][1]['payload']['operation'], 'remove')
        self.assertEqual(self.events[1][1]['payload']['principal'], 'bob')

    def test_owner_remove_is_blocked_without_db_or_queue_effect(self):
        with sqlite3.connect(self.db_path) as con:
            cur = con.execute(
                'INSERT INTO tenant_acl(tenant,subject_type,subject) VALUES(?,?,?)',
                ('alice-db', 'user', 'alice-db'),
            )
            owner_id = cur.lastrowid
            con.commit()
        before = self._rows()
        blocked = self._post(op='remove', id=str(owner_id))
        self.assertEqual(blocked.status, 409)
        self.assertEqual(self._rows(), before)
        self.assertEqual(self.events, [])
        self.assertIn('não pode ser removido', blocked.wfile.getvalue().decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
