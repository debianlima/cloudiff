from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[2]
BROKER = ROOT / 'components/control-plane/current-apps/workspace-broker-current/cloudif-workspace-broker.py'
CHANGE_SET = ROOT / 'components/control-plane/current-apps/workspace-broker-current/cloudif_change_set.py'
GATEWAY = ROOT / 'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
FORJA = ROOT / 'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py'
FORJA_MIRROR = ROOT / 'components/runtime/usr/local/sbin/cloudif-forja-agent.py'
REGISTRY = ROOT / 'components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py'
ONBOARDING = ROOT / 'components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py'
WORKSPACE_UNIT = ROOT / 'components/control-plane/etc/systemd/system/cloudif-workspace-broker.service'
GUIDE = ROOT / 'components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py'
GUIDE_LEGACY = ROOT / 'portal/legacy/cloudif_ai_agents_guide.py'
APPROVAL = ROOT / 'components/control-plane/current-apps/portal-current/cloudif_approval_panel.py'
APPROVAL_LEGACY = ROOT / 'portal/legacy/cloudif_approval_panel.py'

READ_TOOLS = {
    'workspace.normalize.plan', 'workspace.change-set.validate',
    'forgejo.proposal.change-set.plan',
}
WRITE_TOOLS = {
    'workspace.artifact.upload.start', 'workspace.artifact.upload.chunk', 'workspace.artifact.upload.batch', 'workspace.artifact.import', 'workspace.artifact.upload.ticket', 'workspace.artifact.upload.complete',
    'approval.request-change-set-proposal', 'approval.cancel',
    'forgejo.proposal.change-set.create',
}


class ChangeSetMCPContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.broker = BROKER.read_text()
        cls.change_set = CHANGE_SET.read_text()
        cls.gateway = GATEWAY.read_text()
        cls.forja = FORJA.read_text()
        cls.registry = REGISTRY.read_text()
        cls.onboarding = ONBOARDING.read_text()
        cls.guide = GUIDE.read_text()

    def test_workspace_profiles_are_internal_and_sealed(self):
        for route in ('/v1/artifact/start','/v1/artifact/chunk','/v1/artifact/batch','/v1/artifact/complete','/v1/artifact/read','/v1/normalize-plan', '/v1/change-set/validate', '/v1/change-set/resolve'):
            self.assertIn(route, self.broker)
        for marker in (
            'seal_change_set', 'load_sealed', 'source_changed',
            'archive_sha256', 'change_set_digest', 'workspace_id',
            'repositoryModified', 'pullRequestCreated',
        ):
            self.assertIn(marker, self.broker + self.change_set)
        self.assertIn("PROJECT_CONFIG_URL = os.environ.get('CLOUDIF_PROJECT_CONFIG_URL'", self.broker)
        self.assertIn("PROJECT_CONFIG_TOKEN = os.environ.get('CLOUDIF_PROJECT_CONFIG_TOKEN'", self.broker)

    def test_workspace_service_reuses_controller_auth_and_writable_root(self):
        unit = WORKSPACE_UNIT.read_text()
        self.assertIn('cloudif-project-config-controller.service', unit)
        self.assertIn('EnvironmentFile=/etc/cloudif/project-config-controller.env', unit)
        self.assertIn('ReadWritePaths=/var/lib/cloudif/workspaces', unit)
        self.assertNotIn('CLOUDIF_CHANGE_SET_CLIENT_SECRET', unit + self.broker)

    def test_change_set_security_limits_are_explicit(self):
        for marker in (
            'MAX_CHANGES = 100', 'MAX_FILE_BYTES = 256 * 1024',
            'MAX_TOTAL_BYTES = 128 * 1024 * 1024', 'MAX_EXISTING_FILE_BYTES = 64 * 1024 * 1024', 'PRIVATE_FILE_RE',
            'binary_content_not_allowed', 'artifact_id', 'expected_sha256_required',
            'hash_mismatch', 'workspace_expired', 'workspace_project_mismatch',
        ):
            self.assertIn(marker, self.change_set)
        for forbidden in ('shell=True', 'os.system(', 'eval(', 'exec('):
            self.assertNotIn(forbidden, self.change_set)

    def test_new_tools_are_in_existing_catalog_with_correct_annotations(self):
        for tool in READ_TOOLS | WRITE_TOOLS:
            self.assertIn("'name':'" + tool + "'", self.gateway)
        read_block = self.gateway[self.gateway.index('READ_ONLY_TOOLS='):self.gateway.index('DESTRUCTIVE_TOOLS=')]
        for tool in READ_TOOLS:
            self.assertIn("'" + tool + "'", read_block)
        for tool in WRITE_TOOLS:
            self.assertNotIn("'" + tool + "'", read_block)
        destructive = self.gateway[self.gateway.index('DESTRUCTIVE_TOOLS='):self.gateway.index('OPEN_WORLD_PREFIXES=')]
        self.assertIn("'forgejo.proposal.change-set.create'", destructive)
        ast.parse(self.gateway)

    def test_approval_stores_no_file_contents_and_uses_transaction(self):
        block = self.gateway[self.gateway.index('def approval_create_change_set'):self.gateway.index('def session_file_resolve')]
        self.assertIn("'content_stored':False", block)
        self.assertIn("'secret_values_in_metadata':False", block)
        self.assertNotIn('content_base64', block)
        execute = self.gateway[self.gateway.index("elif name=='forgejo.proposal.change-set.create':"):self.gateway.index("elif name in {'forgejo.propose-edit.plan'")]
        for marker in (
            "transaction_ids('forgejo.propose-change-set'",
            "approval_transition(approval_id,'reserve'",
            "approval_transition(approval_id,'finalize'",
            "approval_transition(approval_id,'release'",
            'approval_binding_mismatch', 'change_set_resolve',
        ):
            self.assertIn(marker, execute)

    def test_artifact_transport_stays_out_of_change_set_json(self):
        for marker in ('workspace.artifact.upload.start','workspace.artifact.upload.chunk','workspace.artifact.upload.batch','workspace.artifact.import','workspace.artifact.upload.ticket','workspace.artifact.upload.complete',"'artifact_id':{'type':'string'",'def session_file_resolve','CLOUDIF_SESSION_FILE_RESOLVER_URL','def workspace_artifact_import_bytes','def workspace_artifact_read','application/octet-stream','def forgejo_artifact_stage','def stage_change_set_artifacts'):
            self.assertIn(marker,self.gateway)
        self.assertIn('/v1/artifact/batch',self.broker)
        self.assertIn('/v1/artifact/ticket',self.broker)
        artifact_source=(ROOT/'components/control-plane/current-apps/workspace-broker-current/cloudif_workspace_artifact.py').read_text()
        self.assertIn('MAX_BATCH_CHUNK_BYTES = 8 * 1024',artifact_source)
        self.assertIn('def create_upload_ticket',artifact_source)
        self.assertIn('def direct_upload_artifact',artifact_source)
        self.assertIn("'/cloudiff/portal/artifact-upload/'",self.gateway)
        self.assertNotIn("'/cloudiff/portal/artifact-upload#'",self.gateway)
        self.assertIn('browser_secret_required',self.gateway)
        router=(ROOT/'components/control-plane/srv/cloudif/router/conf.d/default.conf').read_text()
        router_apply=(ROOT/'components/control-plane/srv/cloudif/bin/cloudif-apply-router-portal-v1.sh').read_text()
        self.assertIn('client_max_body_size 70m;',router)
        self.assertIn('client_max_body_size 70m;',router_apply)
        for marker in ('/project/proposal/artifact/stage','def _change_set_artifact_stage','def _change_set_artifact_load','def _change_set_put_bytes','_CHANGESET_ARTIFACT_MAX_BYTES = 64 * 1024 * 1024',"if len(raw)>1024*1024",'def _change_set_git_commit_bytes'):
            self.assertIn(marker,self.forja)
        self.assertIn("'content_stored':False",self.gateway)

    def test_approval_cancel_is_own_pending_request_only_contract(self):
        self.assertIn("'name':'approval.cancel'",self.gateway)
        self.assertIn("'approval.cancel':'approval:read-own'",self.gateway)
        read_block=self.gateway[self.gateway.index('READ_ONLY_TOOLS='):self.gateway.index('DESTRUCTIVE_TOOLS=')]
        self.assertNotIn("'approval.cancel'",read_block)

    def test_agent_preflights_all_files_and_rolls_back_branch(self):
        for marker in (
            'def _change_set_validate_payload',
            'def cloudif_proposal_change_set_create',
            "branch='cloudif-proposal-'+request['change_set_digest'][:20]",
            "if operation in {'update','delete'}",
            'hash_mismatch', 'branch_cleaned', 'main_modified',
            "_proposal_api('DELETE'", "'draft':True",
            "'content_stored':False",
        ):
            self.assertIn(marker, self.forja)
        self.assertEqual(FORJA.read_bytes(), FORJA_MIRROR.read_bytes())

    def test_scopes_are_reconciled_without_token_rotation(self):
        for scope in ('workspace:change-set-plan', 'approval:request-change-set', 'forgejo:propose-change-set'):
            self.assertIn(scope, self.registry)
            self.assertIn(scope, self.onboarding)
            self.assertIn(scope, self.gateway)
            self.assertIn(scope, self.guide)
        self.assertIn('PROJECT_CHANGE_SET_SCOPES', self.registry)
        reconcile = self.registry[self.registry.index("if p.startswith('/v1/clients/') and p.endswith('/reconcile')"):]
        self.assertIn('token_hash_preserved', reconcile)
        self.assertIn('created_at_preserved', reconcile)
        viewer_line = next(line for line in self.registry.splitlines() if line.startswith(" 'viewer':"))
        developer_line = next(line for line in self.registry.splitlines() if line.startswith(" 'developer':"))
        self.assertNotIn('PROJECT_CHANGE_SET_SCOPES', viewer_line)
        self.assertIn('PROJECT_CHANGE_SET_SCOPES', developer_line)

    def test_portal_documents_and_labels_change_set_flow(self):
        for tool in READ_TOOLS | WRITE_TOOLS:
            self.assertIn("'" + tool + "':", self.guide)
        self.assertIn("'documentation_version':'130A'", self.guide)
        self.assertIn('Criar proposta multifarquivo no Forgejo', APPROVAL.read_text())
        self.assertEqual(GUIDE.read_bytes(), GUIDE_LEGACY.read_bytes())
        self.assertEqual(APPROVAL.read_bytes(), APPROVAL_LEGACY.read_bytes())


if __name__ == '__main__':
    unittest.main()
