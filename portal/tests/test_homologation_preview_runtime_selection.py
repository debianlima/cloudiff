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
        self.assertIn("runtime_kind=='multiservice'",block)
        self.assertIn("return _create_preview_runtime_homologation_candidate",block)
        self.assertNotIn("/komodo/project/preview/snapshot",block)
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
        self.assertIn("snapshot_id=requested_snapshot or ('snap_'+secrets.token_hex(12))",block)
        self.assertIn("paused.clear()",block)
        self.assertNotIn("_compress_rootfs(rootfs_archive)",block)
        self.assertIn("for service,name,row,aliases in services",block)
        self.assertIn("for name in reversed(paused):docker('unpause',name",block)

    def test_broker_accepts_preview_runtime_only_with_matching_snapshot_kind(self):
        self.assertIn("source_kind not in {'linked-compose','preview-runtime'}",BROKER)
        self.assertIn("compose-snapshot-source-kind-mismatch",BROKER)
        self.assertIn("'source_kind':source_kind",BROKER)

    def test_executor_gateway_allows_preview_runtime_snapshot(self):
        self.assertIn("_EXECUTOR_PROXY_PREFIX+'/v1/preview-runtime-snapshots'",KOMODO)
        self.assertIn("'/v1/preview-runtime-snapshots':1200",KOMODO)


    def test_interrupted_capture_recovers_companion_project_labels(self):
        block=EXEC[EXEC.index('def recover_interrupted_preview_snapshots'):EXEC.index('class Handler',EXEC.index('def recover_interrupted_preview_snapshots'))]
        self.assertIn("labels.get('com.cloudiff.project')",block)
        self.assertIn("stage in {'preview','restored-candidate'}",block)
        self.assertIn("docker('unpause'",block)

    def test_snapshot_capture_is_pollable_and_restart_safe(self):
        block=EXEC[EXEC.index('def create_preview_runtime_snapshot'):EXEC.index('def _snapshot_safe_status',EXEC.index('def create_preview_runtime_snapshot'))]
        self.assertIn("'snapshot_id'",block)
        self.assertIn("'capturing'",block)
        self.assertIn("'failed'",block)
        self.assertIn("update compose_snapshots set",block)
        self.assertIn("def recover_interrupted_preview_snapshots",EXEC)
        self.assertIn("executor_restarted_during_capture",EXEC)
        self.assertIn("compose_snapshot_archive_failed",PUB)
        self.assertIn("compose_snapshot_archive_timeout",PUB)
        self.assertIn("recover_interrupted_preview_snapshots();recover_interrupted_compose_reconfigurations();ThreadingHTTPServer",EXEC)
        self.assertIn("except (BrokenPipeError,ConnectionResetError)",EXEC)

    def test_preview_unpauses_before_hashing_frozen_archives(self):
        block=EXEC[EXEC.index('def create_preview_runtime_snapshot'):EXEC.index('def _snapshot_safe_status',EXEC.index('def create_preview_runtime_snapshot'))]
        self.assertLess(block.index("paused.clear()"),block.index("rootfs_sha=_sha_file"))
        self.assertIn("safe_mount['sha256']=_sha_file",block)
        self.assertIn("spec['rootfs']['sha256']=rootfs_sha",block)

    def test_portal_uses_known_snapshot_id_and_polls(self):
        pblock=PUB[PUB.index('def _preview_runtime_snapshot'):PUB.index('def _create_preview_runtime_homologation_candidate')]
        self.assertIn("snapshot_id=str(snapshot_id or '').strip() or ('snap_'+os.urandom(12).hex())",pblock)
        self.assertIn("'snapshot_id':snapshot_id",pblock)
        candidate=PUB[PUB.index('def _create_preview_runtime_homologation_candidate'):PUB.index('def _supersede_prior_homologations')]
        self.assertIn("'|preview-runtime|'",candidate)
        self.assertIn("'|H'+str(candidate)",candidate)
        self.assertIn("source_commit).encode()).hexdigest()[:24]",candidate)
        self.assertIn("timeout=12",pblock)
        self.assertIn("'/v1/compose-snapshots/'+snapshot_id",pblock)
        self.assertIn("state=='ready'",pblock)
        self.assertIn("state=='failed'",pblock)

    def test_broker_rejects_capture_that_is_not_ready(self):
        self.assertIn("compose-snapshot-not-ready",BROKER)

    def test_compose_candidates_declare_same_instance_requirement(self):
        self.assertIn("'sameInstancePromotionRequired':True",PUB)
        self.assertIn("sourceMode':'preview-runtime'",PUB)
        self.assertIn("sourceKind':'preview-runtime'",PUB)

    def test_multiservice_ensure_keeps_existing_generic_preview(self):
        block=PUB[PUB.index('def ensure_preview('):PUB.index('def recreate_preview(',PUB.index('def ensure_preview('))]
        self.assertIn("current=preview_status(slug,user)",block)
        self.assertIn("runtimeKind",block)
        self.assertIn("or not current.get('configured')",block)

    def test_generic_preview_w1_is_an_explicit_allowed_runtime_identity(self):
        block=EXEC[EXEC.index('def _preview_runtime_row'):EXEC.index('def _preview_runtime_bind_ref',EXEC.index('def _preview_runtime_row'))]
        self.assertIn("generic=f'cloudif-p{int(public_number)}-preview-web'",block)
        self.assertIn("if int(generation)==1:allowed.add(generic)",block)
        self.assertIn("if name not in allowed",block)
        helper=PUB[PUB.index('def _create_preview_runtime_homologation_candidate'):PUB.index('def _supersede_prior_homologations',PUB.index('def _create_preview_runtime_homologation_candidate'))]
        self.assertIn("generic=f'cloudif-p{int(num)}-preview-web'",helper)
        self.assertIn("elif generation==1 and selected==generic",helper)
        self.assertIn("app_container=generic",helper)

    def test_final_candidate_wrapper_keeps_runtime_core_and_readmodel_event(self):
        pos=PUB.rindex('def create_homologation_candidate(')
        block=PUB[pos:PUB.index('def _executor_runtime_client',pos)]
        self.assertIn('_v144_create_homologation_candidate_base',block)
        self.assertIn("_rm.project_changed(slug,'homologation-created')",block)

if __name__=='__main__':unittest.main()
