import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
PUB=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
RUNTIME=(ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()

class PublicationRuntimeDiagnosticStageTests(unittest.TestCase):
    def test_linked_compose_preview_uses_reported_runtime_identity(self):
        block=PUB[PUB.index('def runtime_diagnostic_target'):PUB.index('def recreate_preview',PUB.index('def runtime_diagnostic_target'))]
        self.assertIn('_linked_compose_status(slug,num,binding)',block)
        self.assertIn("candidate=str(status.get('container')",block)
        self.assertIn("result['stackId']=stack_id",block)
        self.assertNotIn("containers=[base+'-api-1',base+'-web-1']",block)
        self.assertIn("'deployment_id':str(target.get('deploymentId') or '')",BASE)
        self.assertIn("'stack_id':str(target.get('stackId') or '')",BASE)

    def test_compose_h_and_p_use_executor_service_inventory(self):
        self.assertIn('def _compose_deployment_runtime_targets',PUB)
        helper=PUB[PUB.index('def _compose_deployment_runtime_targets'):PUB.index('def _compose_publication_preflight',PUB.index('def _compose_deployment_runtime_targets'))]
        self.assertIn("runtime.get('services')",helper)
        self.assertIn("runtime.get('routes')",helper)
        self.assertIn("item.get('container_name')",helper)
        self.assertIn("'databaseLike'",helper)
        block=PUB[PUB.index('def runtime_diagnostic_target'):PUB.index('def recreate_preview',PUB.index('def runtime_diagnostic_target'))]
        self.assertGreaterEqual(block.count('_compose_deployment_runtime_targets(slug,deployment_id)'),2)
        self.assertIn("'serviceTargets':targets['targets']",block)

    def test_runtime_agent_validates_stack_or_deployment_identity(self):
        block=RUNTIME[RUNTIME.index('def cloudif_project_runtime_info'):RUNTIME.index('def _cloudif_active_publication_stack',RUNTIME.index('def cloudif_project_runtime_info'))]
        self.assertIn("ambiguous_runtime_identity",block)
        self.assertIn("ListStackServices",block)
        self.assertIn("stage_container_not_in_stack",block)
        self.assertIn("org.cloudiff.deployment",block)
        self.assertIn("org.cloudiff.project",block)
        self.assertIn("candidate_services",block)

    def test_absent_php_node_is_reported_not_fabricated(self):
        self.assertIn("PHP' if kind=='php' else 'Node.js')+' não está instalado",RUNTIME)
        self.assertIn("php node npm python python3",RUNTIME)
        self.assertIn("available\":False",RUNTIME)

if __name__=='__main__':unittest.main()
