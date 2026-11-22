import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
PUB=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
RUNTIME=(ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
class PublicationRuntimeDiagnosticStageTests(unittest.TestCase):
    def test_linked_compose_preview_targets_real_api_and_web(self):
        self.assertIn("containers=[base+'-api-1',base+'-web-1']",PUB)
        self.assertIn("_rd_runtime_info_with_reconcile(project,kind,environment,user)",BASE)
    def test_absent_php_node_is_reported_not_fabricated(self):
        self.assertIn("PHP' if kind=='php' else 'Node.js')+' não está instalado",RUNTIME)
        self.assertIn("php node npm python python3",RUNTIME)
        self.assertIn("available\":False",RUNTIME)
if __name__=='__main__':unittest.main()
