from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / 'components/runtime/current-apps/artifact-executor-current/cloudif_multiservice_artifact.py'
EXECUTOR = ROOT / 'components/runtime/current-apps/artifact-executor-current/cloudif-artifact-executor.py'
UNIT = ROOT / 'components/runtime/etc/systemd/system/cloudif-artifact-executor.service'
FORJA = ROOT / 'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py'

spec = importlib.util.spec_from_file_location('cloudif_multiservice_artifact_test', MODULE_PATH)
MODULE = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = MODULE
spec.loader.exec_module(MODULE)


class MultiserviceArtifactPolicyTests(unittest.TestCase):
    def service(self, **changes):
        value = {
            'name': 'api', 'path': 'api', 'runtime': 'node', 'version': '24',
            'install': None, 'build': None, 'start': ['node', 'server.js'],
            'port': 3000, 'healthcheck': '/health', 'hookSteps': [],
            'excludePaths': [],
        }
        value.update(changes)
        return value

    def request(self, services):
        return {
            'job_id': 'build_' + '1' * 24,
            'project_slug': 'project-a', 'ref': 'main',
            'archive_sha256': 'a' * 64, 'config_revision': 1,
            'config_digest': 'b' * 64, 'toolchain_digest': 'c' * 64,
            'plan_digest': 'd' * 64, 'services': services,
            'trace_id': 'trace-phase4',
        }

    def test_static_and_node24_are_ready_by_pinned_digest(self):
        static = MODULE.runtime_policy(self.service(runtime='static', version=None))
        node = MODULE.runtime_policy(self.service())
        self.assertEqual(static['status'], 'ready')
        self.assertIn('@sha256:', static['builder'])
        self.assertEqual(node['status'], 'ready')
        self.assertIn('@sha256:', node['builder'])
        self.assertIn('@sha256:', node['runtimeImage'])

    def test_node_old_versions_php_and_custom_containers_are_blocked(self):
        cases = (
            (self.service(version='22'), 'node_version_not_homologated'),
            (self.service(runtime='php', version='8.3'), 'php_base_failed_security_scan'),
            (self.service(runtime='docker', version=None), 'custom_container_policy_not_enabled_in_phase4'),
            (self.service(runtime='compose', version=None), 'custom_container_policy_not_enabled_in_phase4'),
        )
        for service, reason in cases:
            with self.subTest(service=service):
                policy = MODULE.runtime_policy(service)
                self.assertEqual(policy['status'], 'blocked')
                self.assertEqual(policy['reason'], reason)
        php = MODULE.runtime_policy(self.service(runtime='php', version='8.3'))
        self.assertEqual(php['scannerCounts'], {'HIGH': 17, 'CRITICAL': 1})

    def test_request_rejects_blocked_runtime_before_docker(self):
        with self.assertRaises(MODULE.ArtifactError) as context:
            MODULE.validate_request(self.request([self.service(runtime='php', version='8.3')]))
        self.assertEqual(context.exception.code, 'runtime_policy_blocked')
        self.assertEqual(context.exception.detail[0]['scannerCounts']['CRITICAL'], 1)

    def test_commands_are_argv_and_secret_values_are_rejected(self):
        normalized = MODULE.normalize_command(['npm', 'run', 'build'], 'build')
        self.assertEqual(normalized, ['npm', 'run', 'build'])
        with self.assertRaisesRegex(MODULE.ArtifactError, 'invalid_command'):
            MODULE.normalize_command('npm run build', 'build')
        with self.assertRaisesRegex(MODULE.ArtifactError, 'secret_value_not_allowed'):
            MODULE.normalize_command(['node', 'script.js', 'TOKEN=visible'], 'build')
        self.assertEqual(MODULE.dockerfile_run(['npm', 'ci']), 'RUN ["npm", "ci"]\n')

    def test_service_context_excludes_other_monorepo_services_and_private_files(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source = Path(source_dir)
            (source / 'index.html').write_text('<html></html>')
            (source / 'api').mkdir(); (source / 'api/server.js').write_text('api')
            (source / '.env').write_text('SECRET=x')
            (source / 'assets').mkdir(); (source / 'assets/app.js').write_text('web')
            MODULE.copy_context(source, Path(target_dir), ['api'])
            self.assertTrue((Path(target_dir) / 'index.html').is_file())
            self.assertTrue((Path(target_dir) / 'assets/app.js').is_file())
            self.assertFalse((Path(target_dir) / 'api').exists())
            self.assertFalse((Path(target_dir) / '.env').exists())

    def test_toolchain_digest_is_configuration_and_hook_bound_not_commit_bound(self):
        source = MODULE_PATH.read_text()
        start = source.index('def build_toolchain')
        end = source.index('def copy_context', start)
        block = source[start:end]
        self.assertIn("'configDigest':request['config_digest']", block)
        self.assertIn("'requestedToolchainDigest':request['toolchain_digest']", block)
        self.assertIn("'sha256':item['sha256']", block)
        self.assertNotIn("'archiveSha256':request['archive_sha256']", block)
        self.assertIn("'sourceArchiveBound':bool(validation.get('script',{}).get('path'))", block)
        self.assertIn('base_image_identity_mismatch', block)
        self.assertIn("base_inspection.get('imageId')!=expected_base_id", block)
        self.assertIn("'validatedToolchainDigest':validation['toolchainDigest']", block.replace(" ", ""))

    def test_hooks_are_phase_bound_json_run_and_static_hooks_are_blocked(self):
        source = MODULE_PATH.read_text()
        self.assertIn("hook_dockerfile_runs(toolchain.get('hooks') or [],'preBuild')", source)
        self.assertIn("hook_dockerfile_runs(toolchain.get('hooks') or [],'postBuild')", source)
        self.assertIn("'RUN '+json.dumps([hook['imagePath']]", source)
        self.assertIn('static_hook_runtime_required', source)
        self.assertNotIn('RUN /opt/cloudiff/hooks/', source)

    def test_static_publish_removes_platform_metadata_and_hook_sources(self):
        source = MODULE_PATH.read_text()
        for marker in ('cloudiff.yaml', 'cloudiff.yml', 'Dockerfile', 'docker-compose.yml'):
            self.assertIn(marker, source)
        self.assertIn("hook_path=site/hook['path']", source)

    def test_archive_paths_links_devices_and_private_files_are_safe(self):
        source = MODULE_PATH.read_text()
        for marker in (
            'member.issym()', 'member.islnk()', 'member.isdev()',
            'MAX_ARCHIVE = 64 * 1024 * 1024',
            'MAX_UNPACKED = 256 * 1024 * 1024', 'MAX_FILES = 25000',
            'archive_digest_mismatch', 'PRIVATE_RE.search(rel)',
        ):
            self.assertIn(marker, source)

    def test_scanner_is_offline_cached_and_blocks_high_critical(self):
        source = MODULE_PATH.read_text()
        for marker in (
            "'--skip-db-update'", "'--network', 'none'",
            'TRIVY_CACHE', "'block-high-critical'",
            "counts.get('HIGH')", "counts.get('CRITICAL')",
        ):
            self.assertIn(marker, source)
        self.assertIn('scannerOfflineCache', EXECUTOR.read_text())

    def test_node_server_final_stage_is_distroless_and_immutable(self):
        source = MODULE_PATH.read_text()
        self.assertIn("FROM {service['policy']['runtimeImage']}", source)
        self.assertIn('distroless_start_required', source)
        self.assertIn("CMD {json.dumps(runtime_args", source)
        self.assertIn("USER 65532:65532", source)
        self.assertIn("'immutableReference': data.get('Id')", source)
        self.assertIn('immutable_image_conflict', source)
        self.assertIn("'built': built, 'reused': not built", source)

    def test_provenance_is_signed_and_verified_with_ed25519(self):
        source = MODULE_PATH.read_text()
        for marker in (
            "'openssl', 'pkeyutl', '-sign'",
            "'openssl', 'pkeyutl', '-verify'",
            "'signatureAlgorithm': 'Ed25519'",
            "'signatureVerified': True",
            "'secretsIncluded': False",
        ):
            self.assertIn(marker, source)

    def test_executor_keeps_legacy_endpoint_and_adds_multiservice(self):
        source = EXECUTOR.read_text()
        self.assertIn("{'/v1/build', '/v1/multiservice/build'}", source)
        self.assertIn("'static-v1', 'multiservice-v1'", source)
        self.assertIn('build_multiservice(payload)', source)
        self.assertIn('except ArtifactError as exc', source)

    def test_executor_uses_local_forja_agent_with_same_internal_token(self):
        unit = UNIT.read_text()
        self.assertIn('cloudif-forja-agent.service', unit)
        self.assertIn('EnvironmentFile=-/etc/cloudif/forja-komodo-client.env', unit)
        self.assertIn('CLOUDIF_FORJA_LOCAL_URL=http://127.0.0.1:18095', unit)
        forja = FORJA.read_text()
        self.assertIn("{'127.0.0.1','::1'}", forja)
        self.assertIn("re.split(r'[,;|]',configured)", forja)

    def test_source_contains_no_implicit_shell_or_unpinned_defaults(self):
        source = MODULE_PATH.read_text()
        self.assertNotIn('shell=True', source)
        self.assertNotIn('os.system(', source)
        self.assertIn('node@sha256:', source)
        self.assertIn('gcr.io/distroless/nodejs24-debian12@sha256:', source)
        self.assertIn('cgr.dev/chainguard/nginx@sha256:', source)


if __name__ == '__main__':
    unittest.main()
