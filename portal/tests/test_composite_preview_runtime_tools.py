from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
PUB=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
BASE=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
KOMODO=(ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()

class CompositePreviewRuntimeToolsTests(unittest.TestCase):
    def test_preview_diagnostic_prefers_exact_composite_app(self):
        block=PUB[PUB.index('def runtime_diagnostic_target'):PUB.index('def recreate_preview',PUB.index('def runtime_diagnostic_target'))]
        self.assertIn("composite_app=f'cloudif-p{num}-w{generation}-preview-app'",block)
        self.assertIn("stage_bridge=f'cloudif-p{num}-w{generation}-preview-web'",block)
        self.assertIn("if stage_bridge in containers and composite_app not in containers:containers.insert(0,composite_app)",block)
        self.assertIn("'publicNumber':num",block)
        self.assertIn("'public_number':int(target.get('publicNumber')",BASE)

    def test_preview_terminal_passes_exact_composite_identity(self):
        block=PUB[PUB.rindex('def preview_terminal('):PUB.index('_v143_stage_terminal_portal',PUB.rindex('def preview_terminal('))]
        self.assertIn("expected_bridge=f'cloudif-p{num}-w{generation}-preview-web'",block)
        self.assertIn("if bridge==expected_bridge:payload['composite_app']",block)
        self.assertIn("terminalSource':'composite_preview_app'",block)
        self.assertIn("composite_preview_terminal_contract_invalid",block)

    def test_komodo_composite_terminal_requires_app_and_bridge_and_labels(self):
        block=KOMODO[KOMODO.rindex('def cloudif_preview_terminal('):KOMODO.index('def _cloudif_v144_runtime_env_replace',KOMODO.rindex('def cloudif_preview_terminal('))]
        self.assertIn("composite_preview_identity_invalid",block)
        self.assertIn("bridge=f'cloudif-p{num}-w{generation}-preview-web'",block)
        self.assertIn("labels.get('org.cloudiff.project')",block)
        self.assertIn("{'preview','restored-candidate'}",block)
        self.assertIn("'compositePreview':True",block)

    def test_runtime_info_filters_generic_preview_candidates_by_stage_identity(self):
        block=KOMODO[KOMODO.index('def cloudif_project_runtime_info'):KOMODO.index('def _cloudif_active_publication_stack',KOMODO.index('def cloudif_project_runtime_info'))]
        self.assertIn("public_number=int(payload.get('public_number')",block)
        self.assertIn("cloudif-p{public_number}-w{generation}-preview-app",block)
        self.assertIn("label_ok=str(labels.get('org.cloudiff.project')",block)

if __name__=='__main__':unittest.main()
