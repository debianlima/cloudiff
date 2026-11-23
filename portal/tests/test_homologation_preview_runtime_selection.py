from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
PUB=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
EXEC=(ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py').read_text()
BROKER=(ROOT/'components/control-plane/current-apps/deployment-broker-current/cloudif-deployment-broker.py').read_text()
KOMODO=(ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()

class HomologationPreviewRuntimeSelectionTests(unittest.TestCase):
    def test_candidate_flow_uses_live_runtime_kind_not_historical_project_flag(self):
        block=PUB[PUB.index('def create_homologation_candidate('):PUB.index('def homologate_candidate(',PUB.index('def create_homologation_candidate('))]
        self.assertIn("current_preview=preview_status(slug,user)",block)
        self.assertIn("runtime_kind=str(current_preview.get('runtimeKind')",block)
        self.assertIn("if runtime_kind=='multiservice'",block)
        self.assertIn("runtime_kind=='source-linked-preview'",block)
        self.assertNotIn("if _is_multiservice_project(slug):return _create_multiservice_homologation_candidate",block)

    def test_preview_runtime_snapshot_is_strictly_derived_from_stage_identity(self):
        self.assertIn("def create_preview_runtime_snapshot(payload",EXEC)
        self.assertIn("cloudif-p{int(public_number)}-w{int(generation)}-preview-app",EXEC)
        self.assertIn("preview_runtime_identity_invalid",EXEC)
        self.assertIn("preview_runtime_source_commit_mismatch",EXEC)
        self.assertIn("preview_runtime_bind_outside_allowed_roots",EXEC)
        self.assertIn("'source_kind':'preview-runtime'",EXEC)
        self.assertIn("if self.path=='/v1/preview-runtime-snapshots'",EXEC)

    def test_preview_runtime_snapshot_preserves_mounts_rootfs_and_private_environment(self):
        block=EXEC[EXEC.index('def create_preview_runtime_snapshot'):EXEC.index('def _snapshot_safe_status',EXEC.index('def create_preview_runtime_snapshot'))]
        self.assertIn("_tar_container_path(name,dest,archive)",block)
        self.assertIn("_tar_path(source,archive)",block)
        self.assertIn("_export_rootfs(name,rootfs_archive)",block)
        self.assertIn("'environment':env",block)
        self.assertIn("private-spec.json",block)
        self.assertIn("os.chmod(private_path,0o600)",block)

    def test_broker_accepts_preview_runtime_only_with_matching_snapshot_kind(self):
        self.assertIn("source_kind not in {'linked-compose','preview-runtime'}",BROKER)
        self.assertIn("compose-snapshot-source-kind-mismatch",BROKER)
        self.assertIn("'source_kind':source_kind",BROKER)

    def test_executor_gateway_allows_preview_runtime_snapshot(self):
        self.assertIn("_EXECUTOR_PROXY_PREFIX+'/v1/preview-runtime-snapshots'",KOMODO)
        self.assertIn("'/v1/preview-runtime-snapshots':1200",KOMODO)

    def test_compose_candidates_declare_same_instance_requirement(self):
        self.assertIn("'sameInstancePromotionRequired':True",PUB)
        self.assertIn("sourceMode':'preview-runtime'",PUB)
        self.assertIn("sourceKind':'preview-runtime'",PUB)

    def test_multiservice_ensure_keeps_existing_generic_preview(self):
        block=PUB[PUB.index('def ensure_preview('):PUB.index('def recreate_preview(',PUB.index('def ensure_preview('))]
        self.assertIn("current=preview_status(slug,user)",block)
        self.assertIn("runtimeKind",block)
        self.assertIn("or not current.get('configured')",block)

if __name__=='__main__':unittest.main()
