from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
EXEC=(ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py').read_text()
class SnapshotCompletedCaptureRecoveryTests(unittest.TestCase):
    def test_final_directory_is_verified_before_marking_ready(self):
        self.assertIn('def _recover_completed_preview_snapshot(',EXEC)
        start=EXEC.index('def _recover_completed_preview_snapshot(');end=EXEC.index('\ndef recover_interrupted_preview_snapshots',start);block=EXEC[start:end]
        self.assertIn("manifest_path=root/'manifest.json'",block)
        self.assertIn("private_path=root/'private-spec.json'",block)
        self.assertIn('_sha_file(private_path)!=private_sha',block)
        self.assertIn("_sha_file(rootfs_path)!=str(rootfs.get('sha256') or '')",block)
        self.assertIn("_sha_file(archive)!=str(mount.get('sha256') or '')",block)
        self.assertIn("status=?",block)
        self.assertIn("'ready'",block)
    def test_restart_marks_only_incomplete_captures_failed(self):
        start=EXEC.index('def recover_interrupted_preview_snapshots(');end=EXEC.index('\n\nclass Handler',start);block=EXEC[start:end]
        self.assertIn('_recover_completed_preview_snapshot(connection,row)',block)
        self.assertIn("'completedCaptures':sorted(completed)",block)
        self.assertIn("captureErrorCode':'executor_restarted_during_capture'",block)
if __name__=='__main__':unittest.main()
