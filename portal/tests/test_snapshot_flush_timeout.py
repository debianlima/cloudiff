from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
EXEC=(ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py').read_text()
class SnapshotFlushTimeoutTests(unittest.TestCase):
    def test_preview_and_compose_snapshot_flush_allow_busy_disk(self):
        self.assertEqual(EXEC.count("subprocess.run(['sync'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=300)"),2)
        self.assertNotIn("subprocess.run(['sync'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)",EXEC)
if __name__=='__main__':unittest.main()
