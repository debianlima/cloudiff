from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
GATEWAY=(ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py').read_text()
GUIDE=(ROOT/'components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py').read_text()
ONBOARDING=(ROOT/'components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py').read_text()

class ArtifactUploadAgentHandoffTests(unittest.TestCase):
    def test_ticket_is_explicitly_human_only_and_status_is_agent_followup(self):
        self.assertIn("'upload_url_audience'",GATEWAY)
        self.assertIn("'human_user'",GATEWAY)
        self.assertIn("'agent_must_not_open_upload_url'",GATEWAY)
        self.assertIn("'agent_followup_tool'",GATEWAY)
        self.assertIn("'workspace.artifact.upload.status'",GATEWAY)
        self.assertIn('Não abra a upload_url do Portal',GATEWAY)
    def test_status_tool_uses_mcp_broker_path_not_portal_url(self):
        start=GATEWAY.index("elif name=='workspace.artifact.upload.status':")
        end=GATEWAY.index("elif name=='workspace.change-set.validate':",start)
        block=GATEWAY[start:end]
        self.assertIn("workspace_broker_post('/v1/artifact/upload/status'",block)
        self.assertIn("control('/v1/projects/'",block)
        self.assertIn("artifact_project_mismatch",block)
        self.assertNotIn('PUBLIC_ORIGIN',block)
    def test_role_catalogs_expose_status_tool_under_existing_scope(self):
        for text in (GUIDE,ONBOARDING):
            self.assertIn('workspace.artifact.upload.status',text)
            self.assertIn('workspace:change-set-plan',text)

if __name__=='__main__': unittest.main()
