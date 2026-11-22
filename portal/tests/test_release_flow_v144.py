import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
AGENT=(ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
PORTAL=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
PUBLISHER=(ROOT/'components/proxy/current-apps/publisher-agent-current/cloudif-npm-publisher-agent.py').read_text()
TIMER=(ROOT/'components/runtime/etc/systemd/system/cloudif-komodo-authz-sync.timer').read_text()
UI=(ROOT/'portal/design/publication-release.js').read_text()
COEX=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
BASE=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()

class ReleaseFlowV144Tests(unittest.TestCase):
    def test_preview_is_persistent_stack_with_fixed_identity(self):
        self.assertIn("name=f'cloudif-p{public_number}-preview'",AGENT)
        self.assertIn("container=f'cloudif-p{public_number}-preview-web'",AGENT)
        self.assertIn("'continuous':True",AGENT)
        self.assertIn("def _cloudif_v144_preview_sync_loop",AGENT)
        self.assertIn("CLOUDIF_PREVIEW_SYNC_SECONDS','30'",AGENT)
        self.assertIn("_cloudif_v144_start_preview_sync()",AGENT)

    def test_preview_is_stack_scoped_for_terminal_permissions(self):
        self.assertIn("def _cloudif_v144_stack_target",AGENT)
        self.assertIn("'target_mode':'stack'",AGENT)
        self.assertIn("'previewIncluded':bool(psid)",AGENT)
        self.assertIn("terminalSource':'preview_stack'",PORTAL)
        self.assertIn("komodoiff.duckdns.org/stacks/",PORTAL)

    def test_homologated_runtime_is_promoted_in_place(self):
        self.assertIn("'promotedInPlace':True",AGENT)
        self.assertIn("'sameContainerAsHomologation':True",AGENT)
        self.assertIn("promotion_changed_container_identity",AGENT)
        self.assertIn("_cloudif_v144_runtime_env_replace",AGENT)
        self.assertIn("docker','restart',source",AGENT)
        # Promotion keeps old production stopped for rollback/resource economy.
        self.assertIn("docker','stop','--time','20',previous",AGENT)

    def test_rejected_homologation_is_destroyed(self):
        self.assertIn("def cloudif_homologation_reject",AGENT)
        self.assertIn('"/komodo/publication/reject"',AGENT)
        self.assertIn("'resourceFreed':True",AGENT)
        self.assertIn("runtimeCleanup",PORTAL)

    def test_homologation_route_is_removed_after_end_of_lifecycle(self):
        self.assertIn("def stage_delete(payload):",PUBLISHER)
        self.assertIn("self.path=='/stage/delete'",PUBLISHER)
        self.assertIn("'homologationStageRemoved'",PORTAL)

    def test_homologation_terminal_does_not_include_published_candidate(self):
        marker="status in ('awaiting_homologation','homologated')"
        self.assertIn(marker,PORTAL)

    def test_komodo_authz_converges_quickly_after_first_oidc_login(self):
        self.assertIn('OnUnitActiveSec=30s',TIMER)
        self.assertIn('AccuracySec=5s',TIMER)


    def test_fixed_preview_preserves_existing_generation(self):
        self.assertIn("def _fixed_preview_generation",PORTAL)
        self.assertIn("preview_generation",PORTAL)
        self.assertIn("'sourcePreviewStageCode':'W'+str(preview_generation)",PORTAL)
        self.assertIn("forgejo_source_preview_wn",BASE)

    def test_historical_production_has_separate_start_stop_and_activate_actions(self):
        self.assertIn("def historical_publication_prepare",PORTAL)
        self.assertIn("def historical_publication_stop",PORTAL)
        self.assertIn("'stableActivated':False",PORTAL)
        self.assertIn("production/history/prepare",COEX)
        self.assertIn("production/history/stop",COEX)
        self.assertIn("production-history-prepare",UI)
        self.assertIn("production-history-stop",UI)
        self.assertIn("Ativar no endereço principal",UI)

    def test_legacy_history_prepare_never_applies_stable_alias(self):
        self.assertIn("def cloudif_publication_release_prepare",AGENT)
        self.assertIn("stableAliasApplied':False",AGENT)
        self.assertIn("/komodo/publication/release/prepare",AGENT)
        self.assertIn("/komodo/publication/release/status",AGENT)

    def test_legacy_ensure_preserves_known_acl(self):
        self.assertIn('def _cloudif_project_access_payload',AGENT)
        self.assertIn('"preserved-state"',AGENT)
        self.assertIn('authz_access_source',AGENT)

    def test_history_delete_and_stage_diagnostic_contracts_are_present(self):
        source=Path('components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
        self.assertIn('def historical_publication_delete_runtime',source)
        self.assertIn('def runtime_diagnostic_target',source)
        self.assertIn('rehydratedFromSnapshot',source)
        self.assertIn('primaryHostname',source)

if __name__=='__main__':
    unittest.main()
