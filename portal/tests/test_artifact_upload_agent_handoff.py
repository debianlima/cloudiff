from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
GATEWAY=(ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py').read_text()
GUIDE=(ROOT/'components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py').read_text()
ONBOARDING=(ROOT/'components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py').read_text()

class ArtifactUploadAgentHandoffTests(unittest.TestCase):
    def test_ticket_is_scoped_human_upload_capability_and_status_is_agent_followup(self):
        self.assertIn("'upload_url_audience'",GATEWAY)
        self.assertIn("'human_user'",GATEWAY)
        self.assertIn("'agent_must_not_open_upload_url'",GATEWAY)
        self.assertIn("'agent_followup_tool'",GATEWAY)
        self.assertIn("'workspace.artifact.upload.status'",GATEWAY)
        self.assertIn('credencial temporária de upload do Portal',GATEWAY)
        self.assertIn('não exige cookie/login do Portal',GATEWAY)
    def test_import_path_like_input_is_automatically_rewritten_to_browser_upload(self):
        self.assertIn("artifact_import_upload_fallback=False",GATEWAY)
        self.assertIn("payload.get('code')=='host_file_param_not_hydrated'",GATEWAY)
        self.assertIn("tool='workspace.artifact.upload.start';artifact_import_upload_fallback=True",GATEWAY)
        self.assertIn("name=call_tool;args=call_args",GATEWAY)
        self.assertIn("content['automatic_fallback']=True",GATEWAY)
        self.assertIn("content['fallback_reason']='host_file_param_not_hydrated'",GATEWAY)
        self.assertIn("content['filesystem_access_attempted']=False",GATEWAY)
        self.assertIn("mcp_file_param_auto_fallback",GATEWAY)

    def test_start_creates_browser_upload_handoff_in_one_mcp_call(self):
        response=GATEWAY.index("content=data.get('result') or data",GATEWAY.index("elif name in {'workspace.artifact.upload.start'"))
        start=GATEWAY.index("if name=='workspace.artifact.upload.start':",response)
        end=GATEWAY.index("if name=='workspace.artifact.upload.ticket':",start)
        block=GATEWAY[start:end]
        self.assertIn("workspace_broker_post('/v1/artifact/ticket'",block)
        self.assertIn("content['upload_url']=PUBLIC_ORIGIN+'/cloudiff/portal/artifact-upload-capability#'",block)
        self.assertIn("content['upload_ticket_created']=True",block)
        self.assertIn("content['agent_followup_tool']='workspace.artifact.commit.plan'",block)
        self.assertIn("content['user_action_required']=True",block)

    def test_direct_commit_plan_reuses_sealed_artifact_without_base64(self):
        start=GATEWAY.index("elif name=='workspace.artifact.commit.plan':")
        end=GATEWAY.index("elif name=='workspace.change-set.validate':",start)
        block=GATEWAY[start:end]
        self.assertIn("workspace_broker_post('/v1/artifact/upload/status'",block)
        self.assertIn("'artifact_not_sealed'",block)
        self.assertIn("'artifact_too_large_for_forgejo_commit'",block)
        self.assertIn("'artifact_id':artifact_id",block)
        self.assertIn("workspace_broker_post('/v1/change-set/validate'",block)
        self.assertIn("change_set_resolve(slug,workspace_id,digest_value,trace_id)",block)
        self.assertIn("'next_tool':'approval.request-change-set-proposal'",block)
        self.assertIn("'after_approval_tool':'forgejo.proposal.change-set.create'",block)
        self.assertNotIn('content_base64',block)

    def test_portal_upload_ticket_is_one_time_capability_not_browser_session(self):
        self.assertIn("'/cloudiff/portal/artifact-upload-capability#'+urllib.parse.quote(token,safe='')",GATEWAY)
        self.assertIn("content['upload_method']='portal_capability_direct'",GATEWAY)
        self.assertIn("content['human_portal_authentication_required']=False",GATEWAY)
        self.assertIn("content['portal_cookie_required']=False",GATEWAY)
        self.assertIn("content['csrf_required']=False",GATEWAY)
        self.assertIn("content['authentication']='mcp_delegated_one_time_portal_capability'",GATEWAY)
        self.assertIn("content['credential_in_fragment']=True",GATEWAY)

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
            self.assertIn('workspace.artifact.commit.plan',text)
            self.assertIn('workspace:change-set-plan',text)

if __name__=='__main__': unittest.main()
