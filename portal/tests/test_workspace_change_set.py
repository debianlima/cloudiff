from __future__ import annotations

import base64
import importlib.util
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / 'components/control-plane/current-apps/workspace-broker-current/cloudif_change_set.py'
DETECTOR_PATH = ROOT / 'components/control-plane/current-apps/workspace-broker-current'
sys.path.insert(0, str(DETECTOR_PATH))
spec = importlib.util.spec_from_file_location('cloudif_change_set_test', MODULE_PATH)
MODULE = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = MODULE
spec.loader.exec_module(MODULE)


def b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


class WorkspaceChangeSetTests(unittest.TestCase):
    def test_create_update_delete_and_mkdir_apply_only_to_temporary_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'update.txt').write_text('before\n')
            (root / 'delete.txt').write_text('remove\n')
            changes, total = MODULE.normalize_changes([
                {'operation': 'create', 'path': 'frontend/new.txt', 'content_base64': b64('new\n')},
                {'operation': 'update', 'path': 'update.txt', 'expected_sha256': MODULE.sha256(b'before\n'), 'content_base64': b64('after\n')},
                {'operation': 'delete', 'path': 'delete.txt', 'expected_sha256': MODULE.sha256(b'remove\n')},
                {'operation': 'mkdir', 'path': 'scripts'},
            ])
            applied, diff = MODULE.apply_changes(directory, changes)
            self.assertEqual(total, len(b'new\n') + len(b'after\n'))
            self.assertEqual((root / 'frontend/new.txt').read_text(), 'new\n')
            self.assertEqual((root / 'update.txt').read_text(), 'after\n')
            self.assertFalse((root / 'delete.txt').exists())
            self.assertTrue((root / 'scripts/.gitkeep').is_file())
            self.assertEqual(len(applied), 4)
            self.assertTrue(any('new.txt' in line for line in diff))

    def test_hash_mismatch_is_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'file.txt').write_text('actual')
            changes, _ = MODULE.normalize_changes([
                {'operation': 'update', 'path': 'file.txt', 'expected_sha256': '0' * 64, 'content_base64': b64('next')},
            ])
            with self.assertRaises(MODULE.ChangeSetError) as context:
                MODULE.apply_changes(directory, changes)
            self.assertEqual(context.exception.code, 'hash_mismatch')
            self.assertEqual(context.exception.field, 'file.txt')
            self.assertIn('actual_sha256', context.exception.example)

    def test_private_generated_and_escaping_paths_are_rejected(self):
        paths = ('.env', '.git/config', 'node_modules/x.js', '../outside', 'keys/private.pem')
        for path in paths:
            with self.subTest(path=path):
                with self.assertRaises(MODULE.ChangeSetError):
                    MODULE.normalize_changes([{'operation': 'create', 'path': path, 'content_base64': b64('x')}])

    def test_duplicate_paths_binary_and_oversized_sets_are_rejected(self):
        with self.assertRaisesRegex(MODULE.ChangeSetError, 'duplicate_path'):
            MODULE.normalize_changes([
                {'operation': 'create', 'path': 'a.txt', 'content_base64': b64('a')},
                {'operation': 'create', 'path': 'a.txt', 'content_base64': b64('b')},
            ])
        with self.assertRaisesRegex(MODULE.ChangeSetError, 'binary_content_not_allowed'):
            MODULE.normalize_changes([{'operation': 'create', 'path': 'a.bin', 'content_base64': base64.b64encode(b'a\x00b').decode()}])
        with self.assertRaisesRegex(MODULE.ChangeSetError, 'too_many_changes'):
            MODULE.normalize_changes([{'operation': 'mkdir', 'path': f'd{i}'} for i in range(101)])

    def test_digest_binds_title_archive_and_complete_contents(self):
        changes, _ = MODULE.normalize_changes([{'operation': 'create', 'path': 'cloudiff.yaml', 'content_base64': b64('version: 1\nruntime: static\n')}])
        first = MODULE.change_set_digest('project', 'main', 'a' * 64, 'Title', 'Body', changes)
        second = MODULE.change_set_digest('project', 'main', 'a' * 64, 'Title changed', 'Body', changes)
        changed = [dict(changes[0], content_base64=b64('version: 1\nruntime: php\n'), content_sha256=MODULE.sha256(b'version: 1\nruntime: php\n'), size=len(b'version: 1\nruntime: php\n'))]
        third = MODULE.change_set_digest('project', 'main', 'a' * 64, 'Title', 'Body', changed)
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, third)

    def test_sealed_workspace_is_project_and_digest_bound(self):
        with tempfile.TemporaryDirectory() as workroot:
            sealed = MODULE.seal_change_set(workroot, {
                'project_slug': 'project-a', 'change_set_digest': 'b' * 64,
                'ref': 'main', 'archive_sha256': 'a' * 64, 'changes': [],
            }, 300)
            loaded = MODULE.load_sealed(workroot, sealed['workspace_id'], 'b' * 64, 'project-a')
            self.assertEqual(loaded['project_slug'], 'project-a')
            with self.assertRaisesRegex(MODULE.ChangeSetError, 'workspace_project_mismatch'):
                MODULE.load_sealed(workroot, sealed['workspace_id'], 'b' * 64, 'project-b')
            with self.assertRaisesRegex(MODULE.ChangeSetError, 'change_set_digest_mismatch'):
                MODULE.load_sealed(workroot, sealed['workspace_id'], 'c' * 64, 'project-a')

    def test_expired_workspace_is_removed(self):
        with tempfile.TemporaryDirectory() as workroot:
            sealed = MODULE.seal_change_set(workroot, {
                'project_slug': 'project-a', 'change_set_digest': 'b' * 64,
                'ref': 'main', 'archive_sha256': 'a' * 64, 'changes': [],
            }, 300)
            path = MODULE.seal_path(workroot, sealed['workspace_id'])
            data = json.loads(path.read_text())
            data['expires_at'] = int(time.time()) - 1
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(MODULE.ChangeSetError, 'workspace_expired'):
                MODULE.load_sealed(workroot, sealed['workspace_id'], 'b' * 64, 'project-a')
            self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
