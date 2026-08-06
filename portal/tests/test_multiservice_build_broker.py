from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / 'components/control-plane/current-apps/build-broker-current/cloudif-build-broker.py'
UNIT = ROOT / 'components/control-plane/etc/systemd/system/cloudif-build-broker.service'


class MultiserviceBuildBrokerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        os.environ['CLOUDIF_BUILD_DB'] = str(Path(cls.temp.name) / 'builds.db')
        spec = importlib.util.spec_from_file_location('cloudif_build_broker_multiservice_test', MODULE_PATH)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)
        cls.module.init_db()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.original_config = self.module.project_configuration
        self.original_detection = self.module.source_detection
        self.module.project_configuration = lambda slug: {
            'ok': True, 'projectSlug': slug, 'currentRevision': 3,
            'configDigest': 'b' * 64, 'toolchainDigest': 'c' * 64,
            'configuration': {
                'project': {'type': 'multi-service', 'primaryService': 'web'},
                'hooks': {'preBuild': [{'service': 'api', 'script': 'scripts/check-api.sh'}]},
                'services': {
                    'web': {'path': '.', 'runtime': 'static', 'publish': '.'},
                    'api': {'path': 'api', 'runtime': 'node', 'version': '24', 'start': ['node', 'server.js'], 'port': 3000, 'healthcheck': {'path': '/health'}},
                },
            },
        }
        self.module.source_detection = lambda slug, ref, trace: {'archiveSha256': 'a' * 64, 'projectType': 'multi-service', 'componentCount': 2}
        conn = self.module.db(); conn.execute('delete from multiservice_jobs'); conn.commit(); conn.close()

    def tearDown(self):
        self.module.project_configuration = self.original_config
        self.module.source_detection = self.original_detection

    def test_plan_binds_revision_config_toolchain_archive_and_services(self):
        plan = self.module.multiservice_plan({'project_slug': 'project-a', 'ref': 'main', 'expected_revision': 3, 'trace_id': 'trace'})
        self.assertTrue(plan['ok'])
        self.assertTrue(plan['side_effect_free'])
        self.assertTrue(plan['approval_required'])
        self.assertEqual(plan['config_revision'], 3)
        self.assertEqual(plan['archive_sha256'], 'a' * 64)
        self.assertEqual(len(plan['plan_digest']), 64)
        self.assertFalse(plan['blocked'])
        self.assertEqual(plan['summary']['networkPolicy'], 'none')
        self.assertFalse(plan['summary']['secretsIncluded'])

    def test_root_static_service_excludes_api_directory(self):
        plan = self.module.multiservice_plan({'project_slug': 'project-a', 'trace_id': 'trace'})
        services = {item['name']: item for item in plan['services']}
        self.assertEqual(services['web']['excludePaths'], ['api'])
        self.assertEqual(services['api']['hookSteps'], [{'phase': 'preBuild', 'path': 'scripts/check-api.sh'}])

    def test_php_is_blocked_with_actionable_security_reason(self):
        self.module.project_configuration = lambda slug: {
            'ok': True, 'currentRevision': 1, 'configDigest': 'b' * 64, 'toolchainDigest': 'c' * 64,
            'configuration': {'project': {'type': 'single-service'}, 'services': {'web': {'path': '.', 'runtime': 'php', 'version': '8.3', 'publish': 'public'}}},
        }
        plan = self.module.multiservice_plan({'project_slug': 'project-a', 'trace_id': 'trace'})
        self.assertFalse(plan['approval_required'])
        self.assertEqual(plan['blocked'][0]['reason'], 'php_base_failed_security_scan')
        self.assertEqual(plan['blocked'][0]['scannerCounts']['CRITICAL'], 1)

    def test_configuration_is_required_and_revision_mismatch_is_rejected(self):
        self.module.project_configuration = lambda slug: {'ok': True, 'currentRevision': 0}
        with self.assertRaisesRegex(ValueError, 'configuration_required'):
            self.module.multiservice_plan({'project_slug': 'project-a', 'trace_id': 'trace'})
        self.module.project_configuration = lambda slug: {
            'ok': True, 'currentRevision': 2, 'configDigest': 'b' * 64, 'toolchainDigest': 'c' * 64,
            'configuration': {'services': {'web': {'path': '.', 'runtime': 'static', 'publish': '.'}}},
        }
        with self.assertRaisesRegex(ValueError, 'configuration_revision_mismatch'):
            self.module.multiservice_plan({'project_slug': 'project-a', 'expected_revision': 1, 'trace_id': 'trace'})

    def test_queue_requires_approval_and_is_idempotent_by_plan(self):
        plan = self.module.multiservice_plan({'project_slug': 'project-a', 'trace_id': 'trace'})
        with self.assertRaisesRegex(PermissionError, 'approval_required'):
            self.module.queue_multiservice({'project_slug': 'project-a', 'ref': 'main', 'expected_revision': 3, 'plan_digest': plan['plan_digest'], 'approved': False, 'trace_id': 'trace'})
        first = self.module.queue_multiservice({'project_slug': 'project-a', 'ref': 'main', 'expected_revision': 3, 'plan_digest': plan['plan_digest'], 'approved': True, 'trace_id': 'trace'})
        second = self.module.queue_multiservice({'project_slug': 'project-a', 'ref': 'main', 'expected_revision': 3, 'plan_digest': plan['plan_digest'], 'approved': True, 'trace_id': 'trace'})
        self.assertTrue(first['ok'])
        self.assertFalse(first['idempotent'])
        self.assertTrue(second['idempotent'])
        self.assertEqual(first['job_id'], second['job_id'])

    def test_status_redacts_service_payload(self):
        plan = self.module.multiservice_plan({'project_slug': 'project-a', 'trace_id': 'trace'})
        queued = self.module.queue_multiservice({'project_slug': 'project-a', 'ref': 'main', 'expected_revision': 3, 'plan_digest': plan['plan_digest'], 'approved': True, 'trace_id': 'trace'})
        status = self.module.multiservice_status(queued['job_id'])
        self.assertTrue(status['ok'])
        self.assertNotIn('services', status['payload'])
        self.assertEqual(status['status'], 'queued')

    def test_unit_reuses_internal_controller_and_workspace_tokens(self):
        unit = UNIT.read_text()
        self.assertIn('cloudif-project-config-controller.service', unit)
        self.assertIn('EnvironmentFile=/etc/cloudif/project-config-controller.env', unit)
        self.assertIn('EnvironmentFile=/etc/cloudif/workspace-broker.env', unit)

    def test_legacy_static_routes_remain_available(self):
        source = MODULE_PATH.read_text()
        self.assertIn("if self.path=='/v1/plan'", source)
        self.assertIn("if self.path=='/v1/execute'", source)
        self.assertIn("if self.path=='/v1/multiservice/plan'", source)
        self.assertIn("if self.path=='/v1/multiservice/execute'", source)
        self.assertIn("'/v1/multiservice/build'", source)


if __name__ == '__main__':
    unittest.main()
