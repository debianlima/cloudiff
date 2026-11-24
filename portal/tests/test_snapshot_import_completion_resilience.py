from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
EXEC=(ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py').read_text()
class SnapshotImportCompletionResilienceTests(unittest.TestCase):
    def test_import_accepts_daemon_image_with_exact_snapshot_identity(self):
        block=EXEC[EXEC.index('def _snapshot_rootfs_image'):EXEC.index('def _tar_contents',EXEC.index('def _snapshot_rootfs_image'))]
        self.assertIn('subprocess.Popen(command',block)
        self.assertIn("docker('image','inspect',tag",block)
        self.assertIn("labels.get('org.cloudiff.snapshot')==snapshot_id",block)
        self.assertIn("labels.get('org.cloudiff.rootfs-sha256')==expected_sha256",block)
        self.assertIn("labels.get('org.cloudiff.service')==service",block)
        self.assertIn('process.terminate()',block)
        self.assertIn('compose_snapshot_image_import_timeout',block)
if __name__=='__main__':unittest.main()
