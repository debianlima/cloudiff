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
        self.assertIn("delete from compose_snapshots",block)
        self.assertIn("idempotent",block)
        self.assertIn("docker('image','rm'",block)
    def test_removed_snapshot_is_not_usable(self):
        block=EXEC[EXEC.index('def _snapshot_safe_status'):EXEC.index('def compose_snapshot_status',EXEC.index('def _snapshot_safe_status'))]
        self.assertIn("'ok':status in {'capturing','ready'}",block)
        self.assertIn("cloneIncludesPrivateEnvironment':status=='ready'",block)

    def test_delete_response_reports_success_after_retirement(self):
        block=EXEC[EXEC.index('def remove_compose_snapshot'):EXEC.index('def _snapshot_archive_record',EXEC.index('def remove_compose_snapshot'))]
        self.assertIn("safe.update({'ok':True,'status':'removed','removed':True",block)
        self.assertIn("delete from compose_snapshots",block)
        self.assertIn("idempotent",block)
    def test_delete_snapshot_is_exposed_through_executor_and_gateway(self):
        self.assertIn("remove_compose_snapshot(snapshot_match.group(1))",EXEC)
        self.assertIn("elif snapshot:downstream='/v1/compose-snapshots/'",GATEWAY)
    def test_rejected_compose_h_removes_runtime_then_snapshot(self):
        block=PUB[PUB.rindex('def homologate_candidate('):PUB.index('# CloudIFF v144 END',PUB.rindex('def homologate_candidate('))]
        self.assertLess(block.index("cleanup['runtime']=_remove_compose_runtime"),block.index("cleanup['snapshot']=_remove_compose_snapshot_artifact"))
        self.assertIn("runtime_meta.get('composeSnapshotId')",block)
        self.assertIn('def _remove_compose_snapshot_artifact',PUB)
        self.assertIn("purge_environment_configuration(slug,'homologation',actor)",block)

    def test_each_new_h_rebuilds_configuration_from_current_preview(self):
        self.assertGreaterEqual(PUB.count("clone_environment_configuration(slug,'preview','homologation',actor)"),3)

    def test_rejected_candidate_is_not_rendered_as_active_homologation(self):
        js=(ROOT/'portal/design/publication-release.js').read_text()
        self.assertIn("['awaiting_homologation', 'homologated'].includes",js)
        self.assertIn('const candidate = latestCandidate(data);',js)
        self.assertNotIn("return ((model.data || {}).candidates || [])[0] || null;",js)

    def test_executor_removes_deployment_and_runtime_state_rows(self):
        block=EXEC[EXEC.index('def remove_deployment'):EXEC.index('def _recover_completed_preview_snapshot',EXEC.index('def remove_deployment'))]
        self.assertIn("delete from runtime_states where deployment_id=?",block)
        self.assertIn("delete from deployments where deployment_id=?",block)
        self.assertIn("idempotent",block)

if __name__=='__main__':unittest.main()
