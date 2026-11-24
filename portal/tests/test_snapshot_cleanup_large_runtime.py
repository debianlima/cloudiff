from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
EXEC=(ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py').read_text()
class SnapshotCleanupLargeRuntimeTests(unittest.TestCase):
    def test_deployment_cleanup_allows_large_snapshot_layer_removal(self):
        start=EXEC.index('def cleanup_resources(');end=EXEC.index('\ndef ',start+4);block=EXEC[start:end]
        self.assertIn("docker('rm','-f',name,timeout=300,check=False)",block)
        self.assertIn("docker('volume','rm',volume,timeout=300,check=False)",block)
        self.assertNotIn("docker('rm','-f',name,timeout=30,check=False)",block)
if __name__=='__main__':unittest.main()
