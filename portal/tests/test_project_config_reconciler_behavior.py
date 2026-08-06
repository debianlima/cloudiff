from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'components/control-plane/current-apps/project-config-reconciler-current/cloudif-project-config-reconciler.py'


class ProjectConfigReconcilerBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.config_db = root / 'config.db'
        self.control_db = root / 'control.db'
        self.build_db = root / 'build.db'
        self._create_control_db()
        self._create_config_db()
        self._create_build_db()
        name = 'project_config_reconciler_test_' + os.urandom(4).hex()
        spec = importlib.util.spec_from_file_location(name, SOURCE)
        self.module = importlib.util.module_from_spec(spec)
        assert spec.loader
        sys.modules[name] = self.module
        spec.loader.exec_module(self.module)
        self.module.CONFIG_DB = self.config_db
        self.module.CONTROL_DB = self.control_db
        self.module.BUILD_DB = self.build_db
        self.module.init_db()

    def tearDown(self):
        self.temp.cleanup()

    def _create_control_db(self):
        con = sqlite3.connect(self.control_db)
        con.executescript('''
            create table projects(
                project_id text primary key, slug text unique, owner text,
                tenant text, status text
            );
            create table project_acl(
                project_id text, subject_type text, subject text, role text
            );
            insert into projects values('p1','demo','alice','tenant-demo','active');
            insert into project_acl values('p1','user','alice','owner');
        ''')
        con.commit(); con.close()

    def _create_config_db(self):
        con = sqlite3.connect(self.config_db)
        con.executescript('''
            create table projects(
                project_slug text primary key,current_revision integer not null,
                manifest_digest text,config_digest text,toolchain_digest text,
                membership_revision integer not null,observation_status text,updated_at integer
            );
            create table revisions(
                project_slug text,revision integer,source text,manifest_json text,
                overrides_json text,effective_json text,manifest_digest text,
                config_digest text,toolchain_digest text,created_by text,created_at integer,
                primary key(project_slug,revision)
            );
            create table reconciliation_events(
                event_id text primary key,project_slug text,event_type text,
                config_revision integer,membership_revision integer,status text,
                details_json text,created_at integer,finished_at integer
            );
        ''')
        con.commit(); con.close()

    def _create_build_db(self):
        con = sqlite3.connect(self.build_db)
        con.execute('''create table multiservice_jobs(
            job_id text primary key,project_slug text,status text,config_revision integer,
            config_digest text,toolchain_digest text,archive_sha256 text,
            result_json text,updated_at integer
        )''')
        con.commit(); con.close()

    def configure(self, effective, revision=1, membership_revision=0):
        config_digest = 'c' * 64
        toolchain_digest = 't' * 64
        con = sqlite3.connect(self.config_db)
        con.execute(
            'insert or replace into projects values(?,?,?,?,?,?,?,?)',
            ('demo', revision, 'm' * 64, config_digest, toolchain_digest,
             membership_revision, 'reconcile_pending', 1),
        )
        con.execute(
            'insert or replace into revisions values(?,?,?,?,?,?,?,?,?,?,?)',
            ('demo', revision, 'test', '{}', '{}', json.dumps(effective),
             'm' * 64, config_digest, toolchain_digest, 'tester', 1),
        )
        con.commit(); con.close()
        return config_digest, toolchain_digest

    def add_build(self, status='succeeded', revision=1, config_digest='c' * 64,
                  toolchain_digest='t' * 64):
        con = sqlite3.connect(self.build_db)
        con.execute(
            'insert into multiservice_jobs values(?,?,?,?,?,?,?,?,?)',
            ('build_' + 'a' * 24, 'demo', status, revision, config_digest,
             toolchain_digest, 'f' * 64, '{"ok":true}', 10),
        )
        con.commit(); con.close()

    def state_row(self):
        con = sqlite3.connect(self.config_db)
        con.row_factory = sqlite3.Row
        row = con.execute(
            'select * from reconciliation_state where project_slug=?', ('demo',)
        ).fetchone()
        con.close()
        return dict(row)

    def test_service_required_variable_without_declaration_is_blocked(self):
        self.configure({
            'environment': {'variables': {}, 'required': {}},
            'hooks': {},
            'services': {
                'api': {
                    'runtime': 'node',
                    'environment': {'required': ['DATABASE_URL'], 'variables': {}},
                },
            },
        })
        result = self.module.reconcile('demo')
        self.assertEqual(result['status'], 'secret_reference_unresolved')
        self.assertIn('configure_required_references', result['requiredActions'])
        reference = next(x for x in result['checks']['requiredReferences'] if x['name'] == 'DATABASE_URL')
        self.assertFalse(reference['configured'])
        self.assertNotIn('reference', reference)
        self.assertFalse(result['secretsExposed'])

    def test_inline_hook_is_blocked_until_versioned(self):
        self.configure({
            'environment': {'variables': {}, 'required': {}},
            'hooks': {'preBuild': [{'service': 'api', 'run': ['npm', 'run', 'prepare']}]},
            'services': {'api': {'runtime': 'node', 'environment': {'required': [], 'variables': {}}}},
        })
        result = self.module.reconcile('demo')
        self.assertEqual(result['status'], 'hook_configuration_invalid')
        self.assertIn('version_hooks_in_repository', result['requiredActions'])
        self.assertFalse(result['checks']['hooksVersioned'])

    def test_versioned_hook_and_matching_build_are_ready(self):
        self.configure({
            'environment': {
                'variables': {},
                'required': {
                    'DATABASE_URL': {
                        'secretRef': 'supabase.database_url', 'services': ['api'],
                    },
                },
            },
            'hooks': {'preBuild': [{'service': 'api', 'script': 'scripts/prepare.sh'}]},
            'services': {'api': {'runtime': 'node', 'environment': {'required': ['DATABASE_URL'], 'variables': {}}}},
        })
        self.add_build()
        result = self.module.reconcile('demo')
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['requiredActions'], [])
        self.assertTrue(result['checks']['hooksVersioned'])
        self.assertTrue(result['checks']['matchingBuildSucceeded'])

    def test_failed_matching_build_requires_completion(self):
        self.configure({
            'environment': {'variables': {}, 'required': {}},
            'hooks': {},
            'services': {'web': {'runtime': 'static', 'environment': {'required': [], 'variables': {}}}},
        })
        self.add_build(status='failed')
        result = self.module.reconcile('demo')
        self.assertEqual(result['status'], 'application_build_required')
        self.assertIn('complete_multiservice_build', result['requiredActions'])

    def test_acl_and_membership_drift_are_detected_without_container_change(self):
        self.configure({
            'environment': {'variables': {}, 'required': {}},
            'hooks': {},
            'services': {'web': {'runtime': 'static', 'environment': {'required': [], 'variables': {}}}},
        })
        self.add_build()
        first = self.module.reconcile('demo')
        self.assertFalse(first['checks']['aclChanged'])
        con = sqlite3.connect(self.control_db)
        con.execute("insert into project_acl values('p1','user','bob','viewer')")
        con.commit(); con.close()
        con = sqlite3.connect(self.config_db)
        con.execute('update projects set membership_revision=1 where project_slug=?', ('demo',))
        con.commit(); con.close()
        second = self.module.reconcile('demo')
        self.assertTrue(second['checks']['aclChanged'])
        self.assertTrue(second['checks']['membershipRevisionChanged'])
        self.assertFalse(second['checks']['containersChanged'])
        self.assertEqual(second['status'], 'ready')


if __name__ == '__main__':
    unittest.main()
