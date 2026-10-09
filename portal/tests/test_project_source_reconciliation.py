from __future__ import annotations

import importlib.util
import io
import tarfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_source_reconcile.py'
WORKER = ROOT/'components/control-plane/current-apps/reconcile-worker-current/cloudif-reconcile-worker.py'
CLIENT = ROOT/'components/control-plane/srv/cloudif/lib/cloudif_reconcile_client.py'
TEMPLATE = ROOT/'components/control-plane/usr/local/sbin/cloudif-project-template-apply.py'
SERVICE = ROOT/'components/control-plane/etc/systemd/system/cloudif-project-source-reconcile.service'
TIMER = ROOT/'components/control-plane/etc/systemd/system/cloudif-project-source-reconcile.timer'
MEMBERSHIP_SERVICE = ROOT/'components/control-plane/etc/systemd/system/cloudif-project-membership-reconcile.service'
MEMBERSHIP_TIMER = ROOT/'components/control-plane/etc/systemd/system/cloudif-project-membership-reconcile.timer'
FORJA = ROOT/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py'

spec = importlib.util.spec_from_file_location('source_reconcile_test', MODULE)
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


def archive(files):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w:gz') as tar:
        for name, content in files.items():
            data = content if isinstance(content, bytes) else content.encode()
            info = tarfile.TarInfo('cloudif-demo-main/' + name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return raw.getvalue()


class ProjectSourceReconciliationTests(unittest.TestCase):
    def test_legacy_site_is_preserved_and_bridged(self):
        snap = source.inspect_archive(archive({
            'README.md': '# Existing docs\n',
            'site/index.html': '<html>legacy</html>',
            'site/assets/logo.png': b'\x89PNG\x00binary',
            'site/api/server.js': 'console.log("legacy")\n',
            'site/api/package.json': '{"name":"legacy"}\n',
        }))
        plan = source.plan_snapshot('demo', snap)
        actions = {item['path']: item for item in plan['actions']}
        self.assertIn('index.html', actions)
        self.assertIn('api/server.js', actions)
        self.assertIn('api/package.json', actions)
        self.assertNotIn('README.md', actions)
        self.assertEqual(plan['destructive_actions'], 0)
        self.assertIn('site/', plan['legacy_paths_preserved'])
        self.assertIn('site/', actions['index.html']['content'])

    def test_current_files_are_never_overwritten(self):
        snap = source.inspect_archive(archive({
            'index.html': '<html>current</html>',
            'README.md': '# Mine\n',
            'api/server.js': 'console.log("current")\n',
            'site/index.html': '<html>old copy</html>',
            'site/api/server.js': 'console.log("old")\n',
        }))
        plan = source.plan_snapshot('demo', snap)
        actions = {item['path'] for item in plan['actions']}
        self.assertNotIn('index.html', actions)
        self.assertNotIn('api/server.js', actions)
        self.assertNotIn('README.md', actions)
        self.assertTrue(any(x['path']=='api/server.js' and x['reason']=='current_target_exists' for x in plan['skipped']))

    def test_missing_readme_is_added_without_touching_application(self):
        snap = source.inspect_archive(archive({'index.php': '<?php echo "ok";'}))
        plan = source.plan_snapshot('demo', snap)
        self.assertEqual([x['path'] for x in plan['actions']], ['README.md'])

    def test_large_archive_is_waiting_not_permanent_failure(self):
        original = source.fetch_archive
        source.fetch_archive = lambda slug, ref='main': {'ok': False, 'status': 413, 'error': 'archive_too_large'}
        try:
            snap = source.repository_snapshot('large-demo')
        finally:
            source.fetch_archive = original
        self.assertFalse(snap['ok'])
        self.assertTrue(snap['waiting'])
        self.assertEqual(snap['status'], 413)
        self.assertEqual(snap['error'], 'archive_too_large')

    def test_reconcile_worker_supports_all_project_source_audit(self):
        worker = WORKER.read_text()
        client = CLIENT.read_text()
        self.assertIn('"project.source.reconcile"', client)
        self.assertIn('source_reconcile.reconcile_project(project,apply=True)', worker)
        self.assertIn('def enqueue_all_source_reconciliation', worker)
        self.assertIn('enqueue-all-sources', worker)

    def test_template_verifies_repository_and_skips_existing_source(self):
        template = TEMPLATE.read_text()
        self.assertIn('source_reconcile.repository_snapshot(slug)', template)
        self.assertIn('template_already_applied_verified', template)
        self.assertIn('skipped_existing', template)
        self.assertIn("'version': 13", template)
        self.assertIn('legacy_source_reconcile_failed', template)

    def test_forja_archive_streams_large_payloads_via_tempfile(self):
        forja=Path('components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py').read_text()
        self.assertIn("CLOUDIF_ARCHIVE_MAX_BYTES",forja)
        self.assertIn("tempfile.mkstemp(prefix='cloudif-forgejo-archive-'",forja)
        self.assertIn("chunk=r.read(1024*1024)",forja)
        self.assertNotIn("r.read(_CLOUDIF_ARCHIVE_MAX + 1)",forja)

    def test_forja_archive_accepts_all_platform_slug_characters(self):
        text = FORJA.read_text()
        self.assertIn("_CLOUDIF_ARCHIVE_SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9._-]{0,62}$')", text)

    def test_periodic_membership_reconcile_recovers_post_oidc_login(self):
        worker = WORKER.read_text()
        self.assertIn('def enqueue_all_membership_reconciliation', worker)
        self.assertIn('enqueue-all-memberships', worker)
        self.assertIn("periodic_membership_audit','operation':'reconcile'},dedupe_seconds=0", worker)
        self.assertIn('project.membership.changed', worker)
        self.assertIn('periodic_membership_audit', worker)
        self.assertIn('enqueue-all-memberships', MEMBERSHIP_SERVICE.read_text())
        timer = MEMBERSHIP_TIMER.read_text()
        self.assertIn('OnUnitActiveSec=30min', timer)
        self.assertIn('Persistent=true', timer)

    def test_periodic_service_queues_all_projects(self):
        self.assertIn('enqueue-all-sources', SERVICE.read_text())
        timer = TIMER.read_text()
        self.assertIn('OnUnitActiveSec=6h', timer)
        self.assertIn('Persistent=true', timer)


if __name__ == '__main__':
    unittest.main()
