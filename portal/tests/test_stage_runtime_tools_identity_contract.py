from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
PUB=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
RUNTIME=(ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
BASE=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()

class StageRuntimeToolsIdentityContractTests(unittest.TestCase):
    def test_compose_terminal_uses_executor_candidates_not_web_guess(self):
        block=PUB[PUB.rindex('def stage_terminal('):PUB.index('_v143_homologate_candidate',PUB.rindex('def stage_terminal('))]
        self.assertIn("deployment_targets=_compose_deployment_runtime_targets(slug,deployment_id)",block)
        self.assertIn("payload['container_candidates']=deployment_targets['containers']",block)
        self.assertIn("payload['service_candidates']=deployment_targets['services']",block)
        self.assertIn("allowed={(x['container'],x['service'])",block)
        self.assertNotIn("expected='cloudif-'+deployment_id.replace('_','-')+'-web'",block)

    def test_komodo_terminal_validates_real_deployment_labels(self):
        block=RUNTIME[RUNTIME.rindex('def cloudif_stage_terminal('):RUNTIME.index('_v143_membership_reconcile',RUNTIME.rindex('def cloudif_stage_terminal('))]
        self.assertIn("label=org.cloudiff.deployment=",block)
        self.assertIn("labels.get('org.cloudiff.deployment')",block)
        self.assertIn("labels.get('org.cloudiff.project')",block)
        self.assertIn("selected_service",block)
        self.assertNotIn("+'-web';inspected=",block)

    def test_runtime_info_receives_stage_identity(self):
        block=BASE[BASE.index('def _rd_runtime_info_with_reconcile'):BASE.index("if 'Portal' in globals()",BASE.index('def _rd_runtime_info_with_reconcile'))]
        self.assertIn("target.get('deploymentId')",block)
        self.assertIn("target.get('stackId')",block)
        self.assertIn("target.get('containers')",block)


    def test_legacy_active_production_terminal_uses_exact_versioned_container(self):
        pblock=PUB[PUB.rindex('def stage_terminal('):PUB.index('_v143_homologate_candidate',PUB.rindex('def stage_terminal('))]
        self.assertIn("payload['container_candidates']=[f'cloudif-p{num}-p{publication}-publication-web']",pblock)
        self.assertIn("terminalSource':'legacy_publication_container'",pblock)
        self.assertIn("stage_terminal_legacy_contract_invalid",pblock)
        kblock=RUNTIME[RUNTIME.rindex('def cloudif_stage_terminal('):RUNTIME.index('_v143_membership_reconcile',RUNTIME.rindex('def cloudif_stage_terminal('))]
        self.assertIn("legacy_publication_terminal_identity_invalid",kblock)
        self.assertIn("stage_production_releases",kblock)
        self.assertIn("status='ready' and is_active=1",kblock)
        self.assertIn("legacyPublication':True",kblock)

    def test_legacy_runtime_info_validates_exact_active_publication_name(self):
        block=RUNTIME[RUNTIME.index('def cloudif_project_runtime_info'):RUNTIME.index('def _cloudif_active_publication_stack',RUNTIME.index('def cloudif_project_runtime_info'))]
        self.assertIn("environment=='production'",block)
        self.assertIn("cloudif-p{public_number}-p{publication}-publication-web",block)

if __name__=='__main__':unittest.main()
