from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
EXEC=(ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py').read_text()

class PreviewRuntimeCompanionSnapshotTests(unittest.TestCase):
    def test_source_linked_preview_discovers_only_project_preview_companions(self):
        block=EXEC[EXEC.index('def _preview_runtime_services'):EXEC.index('def _preview_runtime_bind_ref',EXEC.index('def _preview_runtime_services'))]
        self.assertIn("prefix=f'cloudif-{slug}-preview-'",block)
        self.assertIn("project_label!=slug",block)
        self.assertIn("stage_label not in {'preview','restored-candidate'}",block)
        self.assertIn("preview_runtime_companion_not_running",block)
        self.assertIn("len(rows)>MAX_SERVICES",block)

    def test_source_linked_binds_are_confined_to_project_root(self):
        block=EXEC[EXEC.index('def _preview_runtime_bind_ref'):EXEC.index('def _preview_runtime_edge_port',EXEC.index('def _preview_runtime_bind_ref'))]
        self.assertIn("project_root:Path|None=None",block)
        self.assertIn("return 'project-runtime/'",block)
        self.assertIn("preview_runtime_bind_outside_allowed_roots",block)

    def test_snapshot_preserves_all_services_and_network_aliases(self):
        source=EXEC[EXEC.index('def preview_runtime_source_state'):EXEC.index('def create_preview_runtime_snapshot',EXEC.index('def preview_runtime_source_state'))]
        snap=EXEC[EXEC.index('def create_preview_runtime_snapshot'):EXEC.index('def _snapshot_safe_status',EXEC.index('def create_preview_runtime_snapshot'))]
        self.assertIn("services=_preview_runtime_services",source)
        self.assertIn("'network_aliases':aliases",source)
        self.assertIn("'service_count':len(safe)",source)
        self.assertIn("for service,name,row,aliases in services",snap)
        self.assertIn("'source_container':name",snap)
        self.assertIn("'network_aliases':aliases",snap)
        self.assertIn("for name in reversed(paused)",snap)

    def test_restore_recreates_source_network_aliases_inside_isolated_deployment(self):
        block=EXEC[EXEC.index('def deploy_compose_snapshot'):EXEC.index('def assigned_port',EXEC.index('def deploy_compose_snapshot'))]
        self.assertIn("spec.get('network_aliases')",block)
        self.assertIn("command.extend(['--network-alias',alias])",block)
        self.assertIn("--network-alias',service",block)

if __name__=='__main__':unittest.main()
