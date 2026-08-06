from pathlib import Path
import ast
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

INITIAL_PATH = Path('components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py')
TEMPLATE_PATH = Path('components/control-plane/usr/local/sbin/cloudif-project-template-apply.py')
DELETE_PATH = Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InitialPublicationImmutableRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.initial = load_module('cloudif_initial_publish_test', INITIAL_PATH)
        cls.template = load_module('cloudif_template_apply_test', TEMPLATE_PATH)

    def test_immutable_versions_are_preserved_and_next_version_is_used(self):
        calls = []
        responses = [
            (409, {'ok': False, 'error': 'immutable_deploy_conflict', 'existing_commit': 'a' * 40, 'requested_commit': 'c' * 40}),
            (409, {'ok': False, 'error': 'immutable_deploy_conflict', 'existing_commit': 'b' * 40, 'requested_commit': 'c' * 40}),
            (200, {
                'ok': True, 'healthy': True, 'container': 'cloudif-p1003-d3-web',
                'deploy_number': 3, 'stack_id': 'stack-d3', 'commit': 'c' * 40,
                'terminal': {'ok': True},
            }),
        ]

        def fake_request(_url, _method='GET', payload=None, _headers=None, timeout=420):
            calls.append(dict(payload or {}))
            return responses.pop(0)

        with patch.object(self.initial, 'request', side_effect=fake_request), patch.object(self.initial.time, 'sleep'):
            result = self.initial.deploy_initial_runtime(
                'http://komodo', {'Authorization': 'Bearer test'},
                {'project': 'silvipro2', 'public_number': 1003, 'deploy_number': 1, 'timeout': 600},
            )

        self.assertEqual([call['deploy_number'] for call in calls], [1, 2, 3])
        self.assertEqual(result['deploy_number'], 3)
        self.assertEqual(result['container'], 'cloudif-p1003-d3-web')
        self.assertEqual([item['deploy_number'] for item in result['immutable_conflicts_skipped']], [1, 2])

    def test_actual_deploy_number_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'portal.db'
            con = sqlite3.connect(db)
            con.executescript('''
                create table project_publications(
                  id integer primary key autoincrement, project_slug text not null, public_number integer not null,
                  deploy_number integer not null, version text not null, commit_sha text not null,
                  stable_hostname text not null, version_hostname text not null, status text not null,
                  is_active integer not null, created_by text not null, created_at text not null,
                  published_at text not null, message text not null, detail_json text not null,
                  unique(project_slug,deploy_number)
                );
                create table project_integrations(project text primary key,status text,message text,updated_at text);
                create table projects(slug text primary key,status text,komodo_status text,updated_at text);
                insert into project_integrations(project,status,message,updated_at) values('silvipro2','draft','','');
                insert into projects(slug,status,komodo_status,updated_at) values('silvipro2','draft','running','');
            ''')
            con.commit();con.close()
            old_db = self.initial.DB
            self.initial.DB = str(db)
            try:
                self.initial.update_db(
                    'silvipro2', 'iff1860746-silvipro2', 'iff1860746', 1003, 3,
                    {'commit': 'c' * 40, 'container': 'cloudif-p1003-d3-web'},
                    {'version_url': 'https://1003-d3.cloudiff.duckdns.org/', 'stable_url': 'https://1003.cloudiff.duckdns.org/'},
                    {'ok': True},
                )
            finally:
                self.initial.DB = old_db
            con = sqlite3.connect(db)
            row = con.execute('select deploy_number,version,version_hostname,is_active from project_publications').fetchone()
            con.close()
            self.assertEqual(row, (3, 'd3', '1003-d3.cloudiff.duckdns.org', 1))

    def test_public_number_reservation_is_atomic_and_monotonic(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'portal.db'
            old_db = self.template.DB
            self.template.DB = str(db)
            try:
                first = self.template.public_number('deleted-project')
                second = self.template.public_number('silvipro2')
                again = self.template.public_number('deleted-project')
            finally:
                self.template.DB = old_db
            self.assertEqual((first, second, again), (1001, 1002, 1001))

    def test_project_deletion_preserves_public_number_reservation(self):
        tree = ast.parse(DELETE_PATH.read_text())
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_delete_rows')
        module = ast.Module(body=[fn], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace = {'sqlite3': sqlite3}
        exec(compile(module, '<delete-rows>', 'exec'), namespace)
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'portal.db'
            con = sqlite3.connect(db)
            con.executescript('''
                create table projects(slug text primary key);
                create table project_public_ids(project_slug text primary key,public_number integer unique);
                create table project_publications(project_slug text,deploy_number integer);
                insert into projects values('silvipro2');
                insert into project_public_ids values('silvipro2',1003);
                insert into project_publications values('silvipro2',1);
            ''')
            removed = namespace['_delete_rows'](con, 'silvipro2')
            con.commit()
            reservation = con.execute('select public_number from project_public_ids where project_slug=?', ('silvipro2',)).fetchone()
            project = con.execute('select * from projects').fetchone()
            publication = con.execute('select * from project_publications').fetchone()
            con.close()
            self.assertEqual(reservation, (1003,))
            self.assertIsNone(project)
            self.assertIsNone(publication)
            self.assertNotIn('project_public_ids', removed)


if __name__ == '__main__':
    unittest.main()
