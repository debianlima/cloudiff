from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
EXEC=(ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py').read_text()

class SnapshotContainerCreateTimeoutTests(unittest.TestCase):
    def test_snapshot_backed_container_create_allows_large_layer_materialization(self):
        start=EXEC.index('def deploy_compose_snapshot(')
        end=EXEC.index('def ',start+4)
        block=EXEC[start:end]
        self.assertIn('try:cid=docker(*command,timeout=900).stdout.strip()',block)
        self.assertIn('deadline=time.time()+900',block)
        self.assertNotIn('try:cid=docker(*command,timeout=180).stdout.strip()',block)

if __name__=='__main__':unittest.main()
