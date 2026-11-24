from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
PUB=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
BASE=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
KOMODO=(ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()

class PaperclipLegacyProductionBackendTests(unittest.TestCase):
    def test_runtime_target_prioritizes_explicit_legacy_backend(self):
        block=PUB[PUB.index('def runtime_diagnostic_target'):PUB.index('def recreate_preview',PUB.index('def runtime_diagnostic_target'))]
        self.assertIn("legacy_backend=str(detail.get('legacyBackendContainer')",block)
        self.assertIn("containers=([legacy_backend] if valid_legacy_backend else [])+[bridge]",block)
        self.assertIn("result['legacyBackendContainer']=legacy_backend",block)
        self.assertIn("legacy_backend_container':str(target.get('legacyBackendContainer')",BASE)

    def test_runtime_agent_accepts_only_labeled_legacy_backend(self):
        block=KOMODO[KOMODO.index('def cloudif_project_runtime_info'):KOMODO.index('def _cloudif_active_publication_stack',KOMODO.index('def cloudif_project_runtime_info'))]
        self.assertIn("legacy_backend_container=str(payload.get('legacy_backend_container')",block)
        self.assertIn("re.fullmatch(rf'cloudif-p{public_number}-d[1-9][0-9]*-(?:app|web)'",block)
        self.assertIn("labels.get('cloudif.project')",block)
        self.assertIn("labels.get('cloudif.stage')",block)

    def test_terminal_prefers_validated_backend_over_http_bridge(self):
        pblock=PUB[PUB.rindex('def stage_terminal('):PUB.index('_v143_homologate_candidate',PUB.rindex('def stage_terminal('))]
        self.assertIn("payload['legacy_backend_container']=legacy_backend_container",pblock)
        self.assertIn("source='legacy_publication_backend'",pblock)
        kblock=KOMODO[KOMODO.rindex('def cloudif_stage_terminal('):KOMODO.index('_v143_membership_reconcile',KOMODO.rindex('def cloudif_stage_terminal('))]
        self.assertIn("selected=backend if backend and backend in requested else expected",kblock)
        self.assertIn("legacy_publication_backend_labels_invalid",kblock)
        self.assertIn("'legacyBackend':selected!=expected",kblock)

if __name__=='__main__':unittest.main()
