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
SOURCE = ROOT / 'components/control-plane/current-apps/project-config-controller-current/cloudif-project-config-controller.py'
SCHEMA = ROOT / 'components/control-plane/etc/cloudif/schemas/cloudiff-v1.schema.json'


class ProjectManifestControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        cls.state_db = root / 'config.db'
        cls.control_db = root / 'control.db'
        conn = sqlite3.connect(cls.control_db)
        conn.execute('''create table projects(
            project_id text primary key, slug text unique, name text, owner text,
            tenant text, status text
        )''')
        conn.executemany(
            'insert into projects(project_id,slug,name,owner,tenant,status) values(?,?,?,?,?,?)',
            [
                ('p1', 'frontend-api', 'Frontend API', 'alice', 'tenant-frontend-api', 'active'),
                ('p2', 'simple-site', 'Simple Site', 'alice', 'tenant-simple-site', 'active'),
                ('p3', 'stale-site', 'Stale Site', 'alice', 'tenant-stale-site', 'active'),
            ],
        )
        conn.commit(); conn.close()
        os.environ['CLOUDIF_PROJECT_CONFIG_DB'] = str(cls.state_db)
        os.environ['CLOUDIF_PROJECT_SNAPSHOT_DB'] = str(cls.control_db)
        os.environ['CLOUDIF_PROJECT_MANIFEST_SCHEMA'] = str(SCHEMA)
        spec = importlib.util.spec_from_file_location('project_config_controller_test', SOURCE)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)
        cls.module.init_db()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_static_shorthand_remains_valid_without_manifest_services(self):
        result = self.module.validate_manifest('''
version: 1
runtime: static
publish: .
''')
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.normalized['project']['type'], 'single-service')
        self.assertEqual(result.normalized['services']['web']['runtime'], 'static')
        self.assertEqual(result.normalized['services']['web']['publish'], '.')

    def test_frontend_and_api_subdirectories_form_multiservice_graph(self):
        result = self.module.validate_manifest('''
version: 1
project:
  type: multi-service
  primaryService: web
services:
  web:
    path: frontend
    runtime: node
    version: "24"
    install: [npm, ci]
    build: [npm, run, build]
    publish: dist
    dependsOn: [api]
  api:
    path: api
    runtime: node
    version: "24"
    install: [npm, ci]
    start: [npm, start]
    port: 3000
    healthcheck:
      path: /api/health
''')
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.service_graph['serviceCount'], 2)
        self.assertEqual(result.service_graph['primaryService'], 'web')
        self.assertIn({'from': 'web', 'to': 'api'}, result.service_graph['edges'])
        self.assertTrue(result.manifest_digest)
        self.assertTrue(result.toolchain_digest)

    def test_static_root_does_not_hide_api_service(self):
        result = self.module.validate_manifest({
            'version': 1,
            'project': {'type': 'multi-service', 'primaryService': 'web'},
            'services': {
                'web': {'path': '.', 'runtime': 'static', 'publish': '.'},
                'api': {'path': 'api', 'runtime': 'node', 'version': '24', 'start': ['node', 'server.js'], 'port': 3000},
            },
        })
        self.assertTrue(result.valid, result.errors)
        self.assertEqual({x['name'] for x in result.service_graph['services']}, {'web', 'api'})

    def test_php_docker_and_compose_are_supported(self):
        manifests = (
            {'version': 1, 'services': {'web': {'runtime': 'php', 'version': '8.4', 'path': '.', 'publish': 'public'}}},
            {'version': 1, 'dockerfile': 'containers/web/Dockerfile'},
            {'version': 1, 'compose': 'deploy/docker-compose.yml'},
        )
        runtimes = []
        for manifest in manifests:
            result = self.module.validate_manifest(manifest)
            self.assertTrue(result.valid, result.errors)
            runtimes.append(result.normalized['services']['web']['runtime'])
        self.assertEqual(runtimes, ['php', 'docker', 'compose'])

    def test_direct_secret_values_are_rejected(self):
        result = self.module.validate_manifest({
            'version': 1,
            'runtime': 'static',
            'environment': {'variables': {'API_TOKEN': 'plaintext-secret'}},
        })
        self.assertFalse(result.valid)
        self.assertIn('secret_value_not_allowed', {item['code'] for item in result.errors})

    def test_database_url_with_embedded_credentials_is_rejected(self):
        result = self.module.validate_manifest({
            'version': 1,
            'runtime': 'static',
            'environment': {'variables': {'DATABASE_URL': 'postgres://user:password@db.internal/app'}},
        })
        self.assertFalse(result.valid)
        self.assertIn('secret_value_not_allowed', {item['code'] for item in result.errors})

    def test_service_environment_secret_is_rejected(self):
        result = self.module.validate_manifest({
            'version': 1,
            'services': {
                'api': {
                    'runtime': 'node', 'version': '24', 'start': ['node', 'server.js'],
                    'environment': {'variables': {'ACCESS_TOKEN': 'inline-value'}},
                },
            },
        })
        self.assertFalse(result.valid)
        issue = next(item for item in result.errors if item['code'] == 'secret_value_not_allowed')
        self.assertEqual(issue['field'], 'services.api.environment.variables.ACCESS_TOKEN')

    def test_versioned_script_hook_is_supported_without_inline_command(self):
        result = self.module.validate_manifest({
            'version': 1,
            'runtime': 'static',
            'hooks': {
                'preBuild': [{
                    'script': 'scripts/configure-integration.sh',
                    'shell': 'bash',
                    'timeoutSeconds': 60,
                    'network': 'restricted',
                }],
            },
        })
        self.assertTrue(result.valid, result.errors)
        hook = result.normalized['hooks']['preBuild'][0]
        self.assertEqual(hook['script'], 'scripts/configure-integration.sh')
        self.assertNotIn('run', hook)

    def test_hook_cannot_define_command_and_script_together(self):
        result = self.module.validate_manifest({
            'version': 1,
            'runtime': 'static',
            'hooks': {'preBuild': [{'run': ['npm', 'run', 'build'], 'script': 'scripts/build.sh'}]},
        })
        self.assertFalse(result.valid)
        self.assertIn('schema_validation_failed', {item['code'] for item in result.errors})

    def test_secret_references_are_valid_and_values_are_not_materialized(self):
        result = self.module.validate_manifest({
            'version': 1,
            'services': {
                'api': {
                    'runtime': 'node', 'version': '24', 'path': 'api',
                    'start': ['npm', 'start'], 'port': 3000,
                    'environment': {'required': ['DATABASE_URL']},
                },
            },
            'environment': {
                'required': {
                    'DATABASE_URL': {'secretRef': 'supabase.database_url', 'services': ['api']},
                },
            },
        })
        self.assertTrue(result.valid, result.errors)
        payload = json.dumps(result.normalized)
        self.assertIn('supabase.database_url', payload)
        self.assertNotIn('plaintext-secret', payload)

    def test_missing_required_variable_has_actionable_field(self):
        result = self.module.validate_manifest({
            'version': 1,
            'services': {
                'api': {
                    'runtime': 'node', 'version': '24', 'path': 'api',
                    'start': ['npm', 'start'], 'port': 3000,
                    'environment': {'required': ['DATABASE_URL']},
                },
            },
        })
        self.assertFalse(result.valid)
        issue = next(item for item in result.errors if item['code'] == 'required_variable_not_declared')
        self.assertEqual(issue['field'], 'services.api.environment.required')
        self.assertIn('DATABASE_URL', issue['message'])
        self.assertIn('documentation', issue)

    def test_shell_operators_require_versioned_script(self):
        result = self.module.validate_manifest({
            'version': 1,
            'services': {
                'web': {'runtime': 'node', 'version': '24', 'path': '.', 'build': 'npm ci && npm run build', 'publish': 'dist'},
            },
        })
        self.assertFalse(result.valid)
        issue = next(item for item in result.errors if item['code'] == 'implicit_shell_not_allowed')
        self.assertEqual(issue['field'], 'services.web.build')
        self.assertEqual(issue['example'], ['npm', 'run', 'build'])

    def test_dependency_cycles_duplicate_ports_and_unknown_services_are_rejected(self):
        result = self.module.validate_manifest({
            'version': 1,
            'project': {'primaryService': 'missing'},
            'services': {
                'a': {'runtime': 'node', 'version': '24', 'start': ['node', 'a.js'], 'port': 3000, 'dependsOn': ['b']},
                'b': {'runtime': 'node', 'version': '24', 'start': ['node', 'b.js'], 'port': 3000, 'dependsOn': ['a', 'ghost']},
            },
        })
        self.assertFalse(result.valid)
        codes = {item['code'] for item in result.errors}
        self.assertIn('duplicate_internal_port', codes)
        self.assertIn('unknown_service_dependency', codes)
        self.assertIn('service_dependency_cycle', codes)
        self.assertIn('primary_service_not_found', codes)

    def test_schema_error_identifies_missing_version(self):
        result = self.module.validate_manifest({'runtime': 'static'})
        self.assertFalse(result.valid)
        issue = next(item for item in result.errors if item['code'] == 'required_field_missing')
        self.assertEqual(issue['field'], 'version')
        self.assertEqual(issue['expectedType'], 'required field')

    def test_plan_apply_revision_and_idempotency(self):
        manifest = {'version': 1, 'runtime': 'static', 'publish': '.'}
        plan = self.module.plan_configuration('simple-site', manifest, {}, 0, 'alice', 'portal')
        self.assertTrue(plan['ok'])
        self.assertTrue(plan['sideEffectFree'])
        self.assertTrue(plan['approvalRequired'])
        self.assertFalse(plan['secretValuesIncluded'])
        applied = self.module.apply_configuration('simple-site', plan['planDigest'], 0, 'alice')
        self.assertEqual(applied['revision'], 1)
        self.assertFalse(applied['observationMode'])
        self.assertTrue(applied['reconciliationPending'])
        self.assertFalse(applied['runtimeChanged'])
        again = self.module.apply_configuration('simple-site', plan['planDigest'], 0, 'alice')
        self.assertTrue(again['idempotent'])
        self.assertEqual(again['revision'], 1)
        current = self.module.current_project('simple-site')
        self.assertEqual(current['currentRevision'], 1)
        self.assertEqual(current['observationStatus'], 'reconcile_pending')

    def test_stale_revision_is_rejected(self):
        manifest = {'version': 1, 'runtime': 'static', 'publish': '.'}
        plan = self.module.plan_configuration('stale-site', manifest, {}, 0, 'alice', 'portal')
        self.module.apply_configuration('stale-site', plan['planDigest'], 0, 'alice')
        with self.assertRaisesRegex(RuntimeError, 'revision_conflict:1'):
            self.module.plan_configuration('stale-site', manifest, {}, 0, 'alice', 'portal')

    def test_membership_events_do_not_change_runtime_or_configuration(self):
        before = self.module.current_project('frontend-api')
        event = self.module.record_event('frontend-api', 'project.member.added', {'subject': 'bob', 'role': 'viewer'})
        self.assertEqual(event['membershipRevision'], before['membershipRevision'] + 1)
        self.assertFalse(event['runtimeChanged'])
        self.assertFalse(event['containersChanged'])
        current = self.module.current_project('frontend-api')
        self.assertEqual(current['currentRevision'], before['currentRevision'])
        self.assertEqual(current['membershipRevision'], before['membershipRevision'] + 1)

    def test_overrides_cannot_persist_secret_values(self):
        result = self.module.validate_manifest(
            {'version': 1, 'runtime': 'static'},
            {'environment': {'variables': {'DATABASE_PASSWORD': 'do-not-store'}}},
        )
        self.assertFalse(result.valid)
        self.assertIn('secret_value_not_allowed', {item['code'] for item in result.errors})

    def test_toolchain_digest_changes_only_for_toolchain_material(self):
        base = {
            'version': 1,
            'services': {'web': {'runtime': 'node', 'version': '24', 'path': '.', 'build': ['npm', 'run', 'build'], 'publish': 'dist'}},
        }
        first = self.module.validate_manifest(base)
        env_changed = self.module.validate_manifest({**base, 'environment': {'variables': {'PUBLIC_NAME': 'one'}}})
        version_changed = self.module.validate_manifest({
            **base,
            'services': {'web': {**base['services']['web'], 'version': '22'}},
        })
        self.assertTrue(first.valid and env_changed.valid and version_changed.valid)
        self.assertEqual(first.toolchain_digest, env_changed.toolchain_digest)
        self.assertNotEqual(first.config_digest, env_changed.config_digest)
        self.assertNotEqual(first.toolchain_digest, version_changed.toolchain_digest)


if __name__ == '__main__':
    unittest.main()
