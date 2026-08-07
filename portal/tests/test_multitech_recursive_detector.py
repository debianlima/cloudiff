from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DETECTOR_PATH = ROOT / 'components/control-plane/current-apps/workspace-broker-current/cloudif_multitech_detector.py'
CONTROLLER_PATH = ROOT / 'components/control-plane/current-apps/project-config-controller-current/cloudif-project-config-controller.py'
SCHEMA = ROOT / 'components/control-plane/etc/cloudif/schemas/cloudiff-v1.schema.json'
BROKER = ROOT / 'components/control-plane/current-apps/workspace-broker-current/cloudif-workspace-broker.py'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


DETECTOR = load_module('cloudif_multitech_detector_test', DETECTOR_PATH)


class MultitechRecursiveDetectorTests(unittest.TestCase):
    def make_repo(self, files):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, (dict, list)):
                path.write_text(json.dumps(content), encoding='utf-8')
            else:
                path.write_text(content, encoding='utf-8')
        return temp, root, sorted(files)

    def test_root_static_and_subdirectory_api_are_both_detected(self):
        temp, root, files = self.make_repo({
            'index.html': '<!doctype html><h1>web</h1>',
            'api/package.json': {
                'engines': {'node': '>=24'},
                'scripts': {'start': 'node server.js'},
                'dependencies': {'express': '^5.0.0'},
            },
            'api/package-lock.json': {'lockfileVersion': 3},
            'api/server.js': 'console.log("api")',
        })
        try:
            result = DETECTOR.detect_components(str(root), files)
        finally:
            temp.cleanup()
        self.assertEqual(result['projectType'], 'multi-service')
        self.assertEqual(result['componentCount'], 2)
        by_runtime = {item['runtime']: item for item in result['components']}
        self.assertEqual(by_runtime['static']['path'], '.')
        self.assertEqual(by_runtime['node']['path'], 'api')
        self.assertEqual(by_runtime['node']['technology'], 'express')
        self.assertEqual(by_runtime['node']['version'], '24')
        self.assertEqual(result['manifestProposal']['project']['primaryService'], 'web')
        self.assertEqual(set(result['manifestProposal']['services']), {'web', 'api'})

    def test_vite_frontend_and_node_api_generate_dist_and_start(self):
        temp, root, files = self.make_repo({
            'frontend/package.json': {
                'scripts': {'build': 'vite build'},
                'devDependencies': {'vite': '^7.0.0'},
            },
            'frontend/package-lock.json': {},
            'api/package.json': {
                'scripts': {'start': 'node src/server.js'},
                'dependencies': {'fastify': '^5.0.0'},
            },
            'api/package-lock.json': {},
        })
        try:
            result = DETECTOR.detect_components(str(root), files)
        finally:
            temp.cleanup()
        services = result['manifestProposal']['services']
        self.assertEqual(services['frontend']['publish'], 'dist')
        self.assertEqual(services['frontend']['build'], ['npm', 'run', 'build'])
        self.assertEqual(services['api']['start'], ['npm', 'run', 'start'])
        self.assertEqual(services['api']['port'], 3000)
        self.assertEqual(services['api']['healthcheck']['path'], '/health')

    def test_node_modules_vendor_build_and_private_files_are_ignored(self):
        temp, root, files = self.make_repo({
            'index.html': '<html></html>',
            'node_modules/evil/package.json': {'dependencies': {'express': '*'}},
            'vendor/acme/package.json': {'dependencies': {'next': '*'}},
            'dist/package.json': {'dependencies': {'vite': '*'}},
            '.env': 'TOKEN=secret',
            'keys/private.pem': '-----BEGIN ' + 'PRIVATE KEY-----',
        })
        try:
            result = DETECTOR.detect_components(str(root), files)
        finally:
            temp.cleanup()
        self.assertEqual(result['componentCount'], 1)
        self.assertEqual(result['components'][0]['runtime'], 'static')
        self.assertTrue(result['privateFilesExcluded'])
        self.assertGreaterEqual(result['limits']['filesIgnored'], 5)
        payload = json.dumps(result)
        self.assertNotIn('TOKEN=secret', payload)
        self.assertNotIn('PRIVATE KEY', payload)

    def test_monorepo_workspaces_are_reported_without_moving_files(self):
        temp, root, files = self.make_repo({
            'package.json': {
                'packageManager': 'pnpm@10.0.0',
                'workspaces': ['apps/*', 'packages/*'],
                'scripts': {'build': 'turbo build'},
                'devDependencies': {'turbo': '^2.0.0'},
            },
            'pnpm-lock.yaml': 'lockfileVersion: 9',
            'apps/web/package.json': {'scripts': {'build': 'vite build'}, 'devDependencies': {'vite': '^7'}},
            'apps/api/package.json': {'scripts': {'start': 'node server.js'}, 'dependencies': {'fastify': '^5'}},
        })
        try:
            result = DETECTOR.detect_components(str(root), files)
        finally:
            temp.cleanup()
        root_component = next(item for item in result['components'] if item['path'] == '.')
        self.assertEqual(root_component['workspaces'], ['apps/*', 'packages/*'])
        self.assertEqual(result['componentCount'], 3)
        self.assertTrue(result['requiresHumanReview'])
        self.assertIn('multi_service_detected', {item['code'] for item in result['warnings']})

    def test_php_dockerfile_and_compose_in_subdirectories_are_detected(self):
        temp, root, files = self.make_repo({
            'legacy/composer.json': {
                'require': {'php': '^8.4', 'laravel/framework': '^12'},
                'config': {'platform': {'php': '8.4.1'}},
            },
            'legacy/public/index.php': '<?php echo "ok";',
            'worker/Dockerfile': 'FROM scratch',
            'deploy/docker-compose.yml': {'services': {'web': {'image': 'nginx'}, 'api': {'build': '../api'}}},
        })
        try:
            result = DETECTOR.detect_components(str(root), files)
        finally:
            temp.cleanup()
        technologies = {item['technology'] for item in result['components']}
        self.assertEqual(technologies, {'laravel', 'dockerfile', 'docker-compose'})
        php = next(item for item in result['components'] if item['runtime'] == 'php')
        self.assertEqual(php['version'], '8.4')
        self.assertEqual(php['publish'], 'public')
        compose = next(item for item in result['components'] if item['runtime'] == 'compose')
        self.assertEqual(compose['serviceNames'], ['api', 'web'])

    def test_unsupported_runtime_is_reported_but_not_put_in_manifest(self):
        temp, root, files = self.make_repo({
            'web/index.html': '<html></html>',
            'ml/pyproject.toml': '[project]\nname="ml"',
        })
        try:
            result = DETECTOR.detect_components(str(root), files)
        finally:
            temp.cleanup()
        python = next(item for item in result['components'] if item['runtime'] == 'python')
        self.assertFalse(python['supported'])
        self.assertNotIn(python['suggestedName'], result['manifestProposal']['services'])
        warning = next(item for item in result['warnings'] if item['code'] == 'unsupported_runtime_detected')
        self.assertIn(python['suggestedName'], warning['services'])

    def test_depth_limit_and_manifest_presence_are_explicit(self):
        temp, root, files = self.make_repo({
            'cloudiff.yaml': 'version: 1\nruntime: static',
            'a/b/c/d/e/f/g/h/i/package.json': {'dependencies': {'express': '*'}},
            'site/index.html': '<html></html>',
        })
        try:
            result = DETECTOR.detect_components(str(root), files)
        finally:
            temp.cleanup()
        self.assertEqual(result['manifestPath'], 'cloudiff.yaml')
        self.assertEqual(result['componentCount'], 1)
        self.assertEqual(result['components'][0]['path'], 'site')
        self.assertGreaterEqual(result['limits']['filesIgnored'], 1)

    def test_manifest_proposal_is_valid_in_phase_one_controller(self):
        temp, root, files = self.make_repo({
            'frontend/package.json': {'scripts': {'build': 'vite build'}, 'devDependencies': {'vite': '^7'}},
            'frontend/package-lock.json': {},
            'api/package.json': {'scripts': {'start': 'node server.js'}, 'dependencies': {'express': '^5'}},
            'api/package-lock.json': {},
        })
        try:
            detection = DETECTOR.detect_components(str(root), files)
        finally:
            temp.cleanup()
        os.environ.setdefault('CLOUDIF_PROJECT_CONFIG_DB', str(ROOT / '.unused-config.db'))
        os.environ.setdefault('CLOUDIF_PROJECT_SNAPSHOT_DB', str(ROOT / '.unused-control.db'))
        os.environ['CLOUDIF_PROJECT_MANIFEST_SCHEMA'] = str(SCHEMA)
        controller = load_module('cloudif_project_config_validation_test', CONTROLLER_PATH)
        validated = controller.validate_manifest(detection['manifestProposal'])
        self.assertTrue(validated.valid, validated.errors)
        self.assertEqual(validated.service_graph['serviceCount'], 2)

    def test_workspace_broker_exposes_read_only_detection_profile(self):
        source = BROKER.read_text()
        self.assertIn("from cloudif_multitech_detector import detect_components", source)
        self.assertIn("'/v1/detect-multiservice'", source)
        self.assertIn("'workspace.detect-multiservice'", source)
        self.assertIn("'sideEffectFree': True", DETECTOR_PATH.read_text())
        self.assertIn('shutil.rmtree(run_dir, ignore_errors=True)', source)


if __name__ == '__main__':
    unittest.main()
