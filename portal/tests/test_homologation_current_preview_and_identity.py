from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
PUB=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
BROKER=(ROOT/'components/control-plane/current-apps/deployment-broker-current/cloudif-deployment-broker.py').read_text()

class HomologationCurrentPreviewAndIdentityTests(unittest.TestCase):
    def test_owner_role_precedes_global_admin_professor(self):
        block=PUB[PUB.index('def _release_permission_role'):PUB.index('def homologators',PUB.index('def _release_permission_role'))]
        self.assertLess(block.index("return 'owner'"),block.index("publication_permissions.is_admin"))
        self.assertIn('publication_permissions._grant',block)
        self.assertIn("return 'delegated'",block)

    def test_async_admin_professor_revalidated_from_current_directory(self):
        self.assertIn('def _current_release_directory_user',PUB)
        helper=PUB[PUB.index('def _current_release_directory_user'):PUB.index('def _validate_homologation_job',PUB.index('def _current_release_directory_user'))]
        self.assertIn('directory.cache_status()',helper)
        self.assertIn("directory.search(actor,'user'",helper)
        self.assertIn('release_directory_stale',helper)
        validator=PUB[PUB.index('def _validate_homologation_job'):PUB.index('def _homologation_job_update_if_running',PUB.index('def _validate_homologation_job'))]
        self.assertIn("role in {'admin','professor'}",validator)
        self.assertIn('_current_release_directory_user(actor)',validator)
        self.assertIn('return user',validator)
        start=PUB.index('def run_job');end=PUB.find('\ndef ',start+12);run=PUB[start:end if end>start else len(PUB)]
        self.assertIn('current_user=_validate_homologation_job',run)
        self.assertIn('create_homologation_candidate(slug,current_user',run)

    def test_multiservice_unhealthy_prefers_healthy_visible_preview(self):
        block=PUB[PUB.index('def preview_status'):PUB.index('def ensure_preview',PUB.index('def preview_status'))]
        self.assertIn("if multi and multi.get('healthy'):return multi",block)
        self.assertIn("'fallbackFrom':'multiservice-unhealthy' if multi else 'multiservice'",block)
        self.assertIn("if fallback.get('healthy') or not multi:return fallback",block)
        self.assertIn("if linked_source and (linked_source.get('healthy') or not multi):return linked_source",block)

    def test_preview_runtime_snapshot_does_not_require_linked_compose_manifest(self):
        block=BROKER[BROKER.index('def _compose_publication_plan'):BROKER.index('def _compose_publication_execute',BROKER.index('def _compose_publication_plan'))]
        self.assertIn("source_kind=='linked-compose' and services",block)
        self.assertIn("compose-snapshot-not-ready",block)
        self.assertIn("source_kind not in {'linked-compose','preview-runtime'}",block)

    def test_reject_broker_managed_h_removes_runtime(self):
        block=PUB[PUB.rindex('def homologate_candidate('):PUB.index('# CloudIFF v144 END',PUB.rindex('def homologate_candidate('))]
        self.assertIn("runtime_meta.get('homologationDeploymentId')",block)
        self.assertIn('_multiservice_deactivate_bridge',block)
        self.assertIn("cleanup['runtime']=_remove_compose_runtime(deployment_id)",block)
        self.assertIn("missing_deployment_id",block)

if __name__=='__main__':unittest.main()
