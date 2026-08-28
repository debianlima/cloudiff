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
PORTAL_CURRENT = ROOT / 'components/control-plane/current-apps/portal-current'
LIB = ROOT / 'components/control-plane/srv/cloudif/lib'
BASE_PORTAL = PORTAL_CURRENT / 'cloudif-admin-portal-base.py'


class _Handler:
    def __init__(self, module, fields, csrf=True):
        self.path = '/cloudiff/portal/action/publication'
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
        self.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        self.headers['Host'] = 'cloudiff.duckdns.org'
        self.headers['Origin'] = 'https://cloudiff.duckdns.org'
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


class PublicationAliasActionEffectTests(unittest.TestCase):
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
            'CLOUDIF_CSRF_SECRET': 'publication-alias-effect-test-secret',
            'CLOUDIF_PUBLIC_HOST': 'cloudiff.duckdns.org',
            'CLOUDIF_PORTAL_HOST': '127.0.0.1',
            'CLOUDIF_PORTAL_PORT': '19089',
            'CLOUDIF_ACCESS_INGEST_DB': str(cls.root / 'access-ingest.db'),
        })
        (cls.root / 'cloudif').mkdir(parents=True)
        sys.path.insert(0, str(LIB))
        sys.path.insert(0, str(PORTAL_CURRENT))
        spec = importlib.util.spec_from_file_location('cloudiff_publication_alias_effect_portal', BASE_PORTAL)
        cls.portal = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.portal)
        cls.portal.init_db()
        import cloudif_portal_publications as publications
        cls.publications = publications
        cls.old_publication_db = publications.DB
        cls.old_clients = publications._clients
        cls.old_post = publications._post
        publications.DB = cls.db_path

    @classmethod
    def tearDownClass(cls):
        cls.publications.DB = cls.old_publication_db
        cls.publications._clients = cls.old_clients
        cls.publications._post = cls.old_post
        cls.portal._close_db_anchor()
        for path in (str(PORTAL_CURRENT), str(LIB)):
            if path in sys.path:
                sys.path.remove(path)
        for key, value in cls.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls.tmp.cleanup()

    def setUp(self):
        self.publisher_calls = []
        self.publications._clients = lambda: ('http://runtime.invalid', 'runtime-token', 'publisher-token')
        self.publications._post = self._publisher_post
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            self.publications._ensure_schema(con)
            con.execute('DELETE FROM project_publication_aliases')
            con.execute('DELETE FROM project_publications')
            con.execute('DELETE FROM projects')
            con.execute('DELETE FROM project_acl')
            con.execute('DELETE FROM action_log')
            con.execute(
                'INSERT INTO projects(slug,name,tenant,owner,description,repo_url,komodo_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
                ('demo', 'Demo', '', 'alice', '', '', 'ok', '2026-08-28T00:00:00Z', '2026-08-28T00:00:00Z'),
            )
            con.execute(
                '''INSERT INTO project_publications(
                   project_slug,public_number,deploy_number,stable_hostname,version_hostname,status,is_active,created_by,created_at
                   ) VALUES(?,?,?,?,?,?,?,?,?)''',
                ('demo', 42, 3, '42.cloudiff.duckdns.org', '42-d3.cloudiff.duckdns.org', 'published', 1, 'alice', '2026-08-28T00:00:00Z'),
            )
            con.commit()

    def _publisher_post(self, url, payload, token, host='', timeout=420):
        self.publisher_calls.append({
            'url': url,
            'payload': dict(payload),
            'token': token,
            'host': host,
            'timeout': timeout,
        })
        return 200, {'ok': True, 'hostname': payload['alias'] + '.cloudiff.duckdns.org'}

    def _alias_row(self):
        with sqlite3.connect(self.db_path) as con:
            return con.execute(
                'SELECT alias,project_slug,created_by FROM project_publication_aliases WHERE project_slug=?',
                ('demo',),
            ).fetchone()

    def test_save_address_persists_alias_and_updates_publisher(self):
        handler = _Handler(self.portal, {'op': 'set_alias', 'slug': 'demo', 'alias': 'meu-site'})
        self.portal.Portal.do_POST(handler)
        self.assertEqual(handler.status, 303)
        location = dict(handler.response_headers).get('Location', '')
        self.assertIn('tab=publicacao', location)
        self.assertIn('project=demo', location)
        self.assertEqual(self._alias_row(), ('meu-site', 'demo', 'alice'))
        self.assertEqual(len(self.publisher_calls), 1)
        call = self.publisher_calls[0]
        self.assertEqual(call['url'], 'http://10.62.91.3/alias')
        self.assertEqual(call['host'], 'cloudif-publisher.internal')
        self.assertEqual(call['token'], 'publisher-token')
        self.assertEqual(call['payload'], {
            'public_number': 42,
            'deploy_number': 3,
            'alias': 'meu-site',
        })
        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                "SELECT action,target,rc FROM action_log WHERE action='publication_set_alias' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        self.assertEqual(row, ('publication_set_alias', 'demo', 0))

    def test_missing_csrf_has_no_alias_or_publisher_effect(self):
        handler = _Handler(
            self.portal,
            {'op': 'set_alias', 'slug': 'demo', 'alias': 'nao-deve-salvar'},
            csrf=False,
        )
        self.portal.Portal.do_POST(handler)
        self.assertEqual(handler.status, 403)
        self.assertIsNone(self._alias_row())
        self.assertEqual(self.publisher_calls, [])


if __name__ == '__main__':
    unittest.main()
