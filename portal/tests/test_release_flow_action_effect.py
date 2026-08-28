import contextlib
import hmac
import http.server
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / 'components/control-plane/srv/cloudif/lib'
PORTAL_CURRENT = ROOT / 'components/control-plane/current-apps/portal-current'
COEXIST = LIB / 'cloudif_portal_v2_coexist.py'
CSRF = 'release-flow-action-effect-csrf'


def _prod_csrf_token(user):
    return CSRF


def _prod_csrf_equal(left, right):
    return hmac.compare_digest(str(left or ''), str(right or ''))


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        self.send_response(404)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_POST(self):
        self.send_response(404)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def log_message(self, fmt, *args):
        return None


class ReleaseFlowActionEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.db_path = cls.root / 'portal.db'
        cls.old_env = os.environ.get('CLOUDIF_PORTAL_V2')
        cls.old_server = http.server.ThreadingHTTPServer
        os.environ.pop('CLOUDIF_PORTAL_V2', None)

        sys.path.insert(0, str(PORTAL_CURRENT))
        sys.path.insert(0, str(LIB))
        import cloudif_portal_publications as publications
        cls.publications = publications
        cls.old_db = publications.DB
        cls.old_approval_status = publications.production_approval_status
        publications.DB = cls.db_path

        with sqlite3.connect(cls.db_path) as con:
            con.row_factory = sqlite3.Row
            con.executescript('''
                CREATE TABLE projects(
                    slug TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    tenant TEXT NOT NULL DEFAULT '',
                    owner TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE project_acl(
                    slug TEXT NOT NULL,
                    subject_type TEXT NOT NULL,
                    subject TEXT NOT NULL
                );
            ''')
            publications._ensure_schema(con)
            con.execute(
                'INSERT INTO projects(slug,name,tenant,owner,created_by) VALUES(?,?,?,?,?)',
                ('demo', 'Demo', '', 'alice', 'alice'),
            )
            con.execute(
                'INSERT INTO project_public_ids(project_slug,public_number,created_at,updated_at) VALUES(?,?,?,?)',
                ('demo', 42, '2026-08-27T23:00:00Z', '2026-08-27T23:00:00Z'),
            )
            con.commit()

        spec = importlib.util.spec_from_file_location('cloudiff_release_flow_action_coexist', COEXIST)
        cls.coexist = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.coexist)
        cls.coexist.LIB = str(LIB)
        cls.coexist.DESIGN = str(ROOT / 'portal/design')
        os.environ['CLOUDIF_PORTAL_V2'] = '1'
        cls.coexist._install()

        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.publications.DB = cls.old_db
        cls.publications.production_approval_status = cls.old_approval_status
        http.server.ThreadingHTTPServer = cls.old_server
        if hasattr(http.server, '_v2_server_hooked'):
            delattr(http.server, '_v2_server_hooked')
        for path in (str(LIB), str(PORTAL_CURRENT)):
            while path in sys.path:
                sys.path.remove(path)
        if cls.old_env is None:
            os.environ.pop('CLOUDIF_PORTAL_V2', None)
        else:
            os.environ['CLOUDIF_PORTAL_V2'] = cls.old_env
        cls.tmp.cleanup()

    def setUp(self):
        self.publications.production_approval_status = self.old_approval_status
        with sqlite3.connect(self.db_path) as con:
            con.execute('DELETE FROM publication_jobs')
            con.execute('DELETE FROM production_activation_requests')
            con.execute('DELETE FROM publication_candidates')
            con.commit()

    def _post(self, operation, payload=None, csrf=CSRF):
        body = json.dumps(payload or {}, separators=(',', ':')).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Host': 'cloudiff.duckdns.org',
            'X-authentik-username': 'alice',
            'X-authentik-email': 'alice@example.invalid',
            'X-authentik-groups': 'CloudIF-Aluno',
        }
        if csrf is not None:
            headers['X-CSRF-Token'] = csrf
        request = urllib.request.Request(
            self.base + '/cloudiff/portal/api/projects/demo/release-flow/' + operation,
            data=body,
            method='POST',
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            with contextlib.closing(exc):
                return exc.code, json.load(exc)

    def _jobs(self):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            return [dict(row) for row in con.execute(
                '''SELECT id,project_slug,actor,status,step,operation,candidate_number,
                          publication_number,environment,approval_id,activation_digest
                   FROM publication_jobs ORDER BY id'''
            )]

    def test_homologation_enqueue_http_creates_one_queued_candidate_job(self):
        status, data = self._post('homologation/enqueue')
        self.assertEqual(status, 202)
        self.assertTrue(data['ok'])
        self.assertTrue(data['queued'])
        self.assertEqual(data['candidateNumber'], 1)
        self.assertEqual(data['stageCode'], 'H1')
        rows = self._jobs()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['project_slug'], 'demo')
        self.assertEqual(rows[0]['actor'], 'alice')
        self.assertEqual(rows[0]['status'], 'queued')
        self.assertEqual(rows[0]['operation'], 'homologation_candidate')
        self.assertEqual(rows[0]['candidate_number'], 1)
        self.assertEqual(rows[0]['environment'], 'homologation')

        again_status, again = self._post('homologation/enqueue')
        self.assertEqual(again_status, 202)
        self.assertTrue(again['existing'])
        self.assertEqual(again['job_id'], data['job_id'])
        self.assertEqual(len(self._jobs()), 1)

    def test_invalid_csrf_has_no_release_job_effect(self):
        status, data = self._post('homologation/enqueue', csrf=None)
        self.assertEqual(status, 403)
        self.assertEqual(data['error']['code'], 'invalid_csrf')
        self.assertEqual(self._jobs(), [])

    def test_production_enqueue_binds_approved_activation_to_queue(self):
        digest = 'd' * 64
        approval = 'apr_' + 'a' * 20
        with sqlite3.connect(self.db_path) as con:
            self.publications._ensure_schema(con)
            con.execute(
                '''INSERT INTO publication_candidates(
                    project_slug,public_number,candidate_number,deploy_number,preview_generation,
                    stage_code,hostname,status,parent_commit,commit_sha,artifact_image,artifact_image_id,
                    diff_json,runtime_diff_json,environment_revision,environment_digest,created_by,created_at,
                    homologated_by,homologated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (
                    'demo', 42, 7, 7, 3, 'H7', '42-h7-homologation.cloudiff.duckdns.org',
                    'homologated', 'parent', 'commit7', 'image', 'sha256:' + '7' * 64,
                    '{}', '{}', 4, 'env-digest', 'alice', '2026-08-27T23:00:00Z',
                    'alice', '2026-08-27T23:01:00Z',
                ),
            )
            con.execute(
                '''INSERT INTO production_activation_requests(
                    project_slug,candidate_number,publication_number,activation_digest,
                    approval_id,requested_by,status,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?)''',
                ('demo', 7, 3, digest, approval, 'portal:alice', 'approved',
                 '2026-08-27T23:02:00Z', '2026-08-27T23:02:00Z'),
            )
            con.commit()

        self.publications.production_approval_status = lambda slug, approval_id, user: {
            'approvalId': approval_id,
            'status': 'approved',
            'candidateNumber': 7,
            'publicationNumber': 3,
            'activationDigest': digest,
        }
        status, data = self._post('production/enqueue', {
            'candidateNumber': 7,
            'approvalId': approval,
            'activationDigest': digest,
        })
        self.assertEqual(status, 202)
        self.assertTrue(data['queued'])
        self.assertEqual(data['publicationNumber'], 3)
        rows = self._jobs()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['operation'], 'production_release')
        self.assertEqual(rows[0]['candidate_number'], 7)
        self.assertEqual(rows[0]['publication_number'], 3)
        self.assertEqual(rows[0]['environment'], 'production')
        self.assertEqual(rows[0]['approval_id'], approval)
        self.assertEqual(rows[0]['activation_digest'], digest)
        with sqlite3.connect(self.db_path) as con:
            queued = con.execute(
                'SELECT status FROM production_activation_requests WHERE project_slug=? AND candidate_number=?',
                ('demo', 7),
            ).fetchone()[0]
        self.assertEqual(queued, 'queued')

    def test_production_enqueue_rejects_digest_mismatch_without_queue_effect(self):
        digest = 'e' * 64
        approval = 'apr_' + 'b' * 20
        with sqlite3.connect(self.db_path) as con:
            self.publications._ensure_schema(con)
            con.execute(
                '''INSERT INTO publication_candidates(
                    project_slug,public_number,candidate_number,deploy_number,preview_generation,
                    stage_code,hostname,status,parent_commit,commit_sha,artifact_image,artifact_image_id,
                    diff_json,runtime_diff_json,environment_revision,environment_digest,created_by,created_at,
                    homologated_by,homologated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('demo', 42, 8, 8, 3, 'H8', '42-h8-homologation.cloudiff.duckdns.org',
                 'homologated', 'parent', 'commit8', 'image', 'sha256:' + '8' * 64,
                 '{}', '{}', 4, 'env-digest', 'alice', '2026-08-27T23:00:00Z',
                 'alice', '2026-08-27T23:01:00Z'),
            )
            con.execute(
                '''INSERT INTO production_activation_requests(
                    project_slug,candidate_number,publication_number,activation_digest,
                    approval_id,requested_by,status,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?)''',
                ('demo', 8, 4, digest, approval, 'portal:alice', 'approved',
                 '2026-08-27T23:02:00Z', '2026-08-27T23:02:00Z'),
            )
            con.commit()

        status, data = self._post('production/enqueue', {
            'candidateNumber': 8,
            'approvalId': approval,
            'activationDigest': 'f' * 64,
        })
        self.assertEqual(status, 403)
        self.assertEqual(data['error']['code'], 'approval_binding_mismatch')
        self.assertEqual(self._jobs(), [])
        with sqlite3.connect(self.db_path) as con:
            state = con.execute(
                'SELECT status FROM production_activation_requests WHERE project_slug=? AND candidate_number=?',
                ('demo', 8),
            ).fetchone()[0]
        self.assertEqual(state, 'approved')


if __name__ == '__main__':
    unittest.main()
