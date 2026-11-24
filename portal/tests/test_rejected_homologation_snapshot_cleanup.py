from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
EXEC=(ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py').read_text()
GATEWAY=(ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
PUB=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()

class RejectedHomologationSnapshotCleanupTests(unittest.TestCase):
    def test_executor_snapshot_retirement_is_fail_closed(self):
        block=EXEC[EXEC.index('def remove_compose_snapshot'):EXEC.index('def _snapshot_archive_record',EXEC.index('def remove_compose_snapshot'))]
        self.assertIn("status='running'",block)
        self.assertIn('compose_snapshot_in_use',block)
        self.assertIn('compose_snapshot_containers_exist',block)
        self.assertIn("status=?",block)
        self.assertIn("'removed'",block)
        self.assertIn("docker('image','rm'",block)
    def test_removed_snapshot_is_not_usable(self):
        block=EXEC[EXEC.index('def _snapshot_safe_status'):EXEC.index('def compose_snapshot_status',EXEC.index('def _snapshot_safe_status'))]
        self.assertIn("'ok':status in {'capturing','ready'}",block)
        self.assertIn("cloneIncludesPrivateEnvironment':status=='ready'",block)

    def test_delete_response_reports_success_after_retirement(self):
        block=EXEC[EXEC.index('def remove_compose_snapshot'):EXEC.index('def _snapshot_archive_record',EXEC.index('def remove_compose_snapshot'))]
        self.assertIn("safe.update({'ok':True,'removed':True",block)
        self.assertIn("status=?",block)
        self.assertIn("'removed'",block)
    def test_delete_snapshot_is_exposed_through_executor_and_gateway(self):
        self.assertIn("remove_compose_snapshot(snapshot_match.group(1))",EXEC)
        self.assertIn("elif snapshot:downstream='/v1/compose-snapshots/'",GATEWAY)
    def test_rejected_compose_h_removes_runtime_then_snapshot(self):
        block=PUB[PUB.rindex('def homologate_candidate('):PUB.index('# CloudIFF v144 END',PUB.rindex('def homologate_candidate('))]
        self.assertLess(block.index("cleanup['runtime']=_remove_compose_runtime"),block.index("cleanup['snapshot']=_remove_compose_snapshot_artifact"))
        self.assertIn("runtime_meta.get('composeSnapshotId')",block)
        self.assertIn('def _remove_compose_snapshot_artifact',PUB)

if __name__=='__main__':unittest.main()
