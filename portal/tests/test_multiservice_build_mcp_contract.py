from pathlib import Path
import ast
import unittest

ROOT=Path(__file__).resolve().parents[2]
GATEWAY=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
BUILD=ROOT/'components/control-plane/current-apps/build-broker-current/cloudif-build-broker.py'
ARTIFACT=ROOT/'components/runtime/current-apps/artifact-executor-current/cloudif_multiservice_artifact.py'
EXECUTOR=ROOT/'components/runtime/current-apps/artifact-executor-current/cloudif-artifact-executor.py'
REGISTRY=ROOT/'components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py'
ONBOARDING=ROOT/'components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py'
GUIDE=ROOT/'components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py'
GUIDE_LEGACY=ROOT/'portal/legacy/cloudif_ai_agents_guide.py'
APPROVAL=ROOT/'components/control-plane/current-apps/portal-current/cloudif_approval_panel.py'
TRANSACTION=ROOT/'components/control-plane/current-apps/portal-current/cloudif_transaction_panel.py'
BUILD_UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-build-broker.service'
ARTIFACT_UNIT=ROOT/'components/runtime/etc/systemd/system/cloudif-artifact-executor.service'
FORJA=ROOT/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py'

READ_TOOLS={'project.toolchain.plan','build.multiservice.plan','build.multiservice.status'}
WRITE_TOOLS={'approval.request-multiservice-build','build.multiservice.execute'}

class MultiserviceBuildMCPContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gateway=GATEWAY.read_text();cls.build=BUILD.read_text();cls.artifact=ARTIFACT.read_text()
        cls.executor=EXECUTOR.read_text();cls.registry=REGISTRY.read_text();cls.onboarding=ONBOARDING.read_text();cls.guide=GUIDE.read_text()

    def test_tools_exist_in_current_mcp_catalog(self):
        for tool in READ_TOOLS|WRITE_TOOLS:
            self.assertIn("'name':'"+tool+"'",self.gateway,tool)
        ast.parse(self.gateway)

    def test_annotations_keep_plans_read_only_and_execution_destructive(self):
        read=self.gateway[self.gateway.index('READ_ONLY_TOOLS='):self.gateway.index('DESTRUCTIVE_TOOLS=')]
        destructive=self.gateway[self.gateway.index('DESTRUCTIVE_TOOLS='):self.gateway.index('OPEN_WORLD_PREFIXES=')]
        for tool in READ_TOOLS:self.assertIn("'"+tool+"'",read)
        for tool in WRITE_TOOLS:self.assertNotIn("'"+tool+"'",read)
        self.assertIn("'build.multiservice.execute'",destructive)
        self.assertNotIn("'approval.request-multiservice-build'",destructive)

    def test_plan_is_bound_to_configuration_toolchain_and_archive(self):
        dispatch=self.gateway[self.gateway.index("elif name in {'project.toolchain.plan','build.multiservice.plan'}:"):self.gateway.index("elif name=='build.multiservice.status':")]
        for marker in ('expected_revision','multiservice_build_plan','config_revision','config_digest','toolchain_digest','archive_sha256','scanner_policy','signature_algorithm','secrets_included'):
            self.assertIn(marker,dispatch)
        for marker in ('config_revision','config_digest','toolchain_digest','archive_sha256','plan_digest','services'):
            self.assertIn(marker,self.build)

    def test_approval_metadata_contains_no_code_or_secrets(self):
        helper=self.gateway[self.gateway.index('def approval_create_multiservice_build'):self.gateway.index('def build_plan') if 'def build_plan' in self.gateway else self.gateway.index('def workspace_prepare')]
        self.assertIn("'content_stored':False",helper)
        self.assertIn("'secret_values_in_metadata':False",helper)
        for forbidden in ('content_base64','POSTGRES_PASSWORD','SERVICE_ROLE_KEY',"'secret_value':"):
            self.assertNotIn(forbidden,helper)

    def test_execute_uses_reserve_effect_finalize_and_exact_binding(self):
        block=self.gateway[self.gateway.index("elif name=='build.multiservice.execute':"):]
        for marker in (
            "transaction_ids('build.multiservice'", "approval_transition(approval_id,'reserve'",
            "approval_transition(approval_id,'finalize'", "approval_transition(approval_id,'release'",
            'approval_binding_mismatch','plan_digest_mismatch','config_digest','toolchain_digest','archive_sha256',
            "'/v1/multiservice/execute'",
        ):
            self.assertIn(marker,block)

    def test_build_broker_keeps_legacy_and_adds_multiservice_routes(self):
        for route in ('/v1/plan','/v1/execute','/v1/multiservice/plan','/v1/multiservice/execute','/v1/multiservice/jobs/'):
            self.assertIn(route,self.build)
        self.assertIn("'/v1/multiservice/build'",self.build)
        self.assertIn('multiservice_jobs',self.build)
        self.assertIn('reusable_build',self.build)

    def test_executor_enforces_security_evidence(self):
        for marker in (
            "'--network', 'none'", "'--skip-db-update'", 'block-high-critical',
            'signatureVerified', 'Ed25519', 'secretsIncluded', 'archive_digest_mismatch',
            'dependency_proxy_required', 'USER 65532:65532', 'USER node',
        ):
            self.assertIn(marker,self.artifact+self.executor)

    def test_scopes_reconcile_without_token_rotation(self):
        for scope in ('build:multiservice-plan','approval:request-multiservice-build','build:multiservice-execute'):
            self.assertIn(scope,self.registry);self.assertIn(scope,self.onboarding);self.assertIn(scope,self.gateway);self.assertIn(scope,self.guide)
        self.assertIn('PROJECT_BUILD_READ_SCOPES',self.registry)
        self.assertIn('PROJECT_BUILD_WRITE_SCOPES',self.registry)
        reconcile=self.registry[self.registry.index("if p.startswith('/v1/clients/') and p.endswith('/reconcile')"):]
        self.assertIn('token_hash_preserved',reconcile);self.assertIn('created_at_preserved',reconcile)
        viewer=next(line for line in self.registry.splitlines() if line.startswith(" 'viewer':"))
        developer=next(line for line in self.registry.splitlines() if line.startswith(" 'developer':"))
        self.assertIn('PROJECT_BUILD_READ_SCOPES',viewer);self.assertNotIn('PROJECT_BUILD_WRITE_SCOPES',viewer)
        self.assertIn('PROJECT_BUILD_READ_SCOPES',developer);self.assertIn('PROJECT_BUILD_WRITE_SCOPES',developer)

    def test_internal_services_reuse_existing_tokens(self):
        build_unit=BUILD_UNIT.read_text();artifact_unit=ARTIFACT_UNIT.read_text()
        self.assertIn('cloudif-project-config-controller.service',build_unit)
        self.assertIn('EnvironmentFile=/etc/cloudif/project-config-controller.env',build_unit)
        self.assertIn('EnvironmentFile=/etc/cloudif/workspace-broker.env',build_unit)
        self.assertIn('cloudif-forja-agent.service',artifact_unit)
        self.assertIn('EnvironmentFile=-/etc/cloudif/forja-komodo-client.env',artifact_unit)
        self.assertIn('CLOUDIF_FORJA_LOCAL_URL=http://127.0.0.1:18095',artifact_unit)
        self.assertIn('ReadWritePaths=/srv/cloudif/artifacts/multiservice',artifact_unit)
        self.assertNotIn('CLOUDIF_MULTISERVICE_USER_TOKEN',self.gateway+self.build+self.artifact)

    def test_local_forja_archive_access_still_requires_internal_token(self):
        self.assertIn("{'127.0.0.1','::1'}",FORJA.read_text())
        self.assertIn("headers={'Authorization': 'Bearer ' + FORJA_TOKEN",self.artifact)
        self.assertIn("X-CloudIF-Token",self.artifact)

    def test_portal_documents_and_labels_phase_four(self):
        for tool in READ_TOOLS|WRITE_TOOLS:self.assertIn("'"+tool+"':",self.guide)
        self.assertIn("'documentation_version':'131A'",self.guide)
        self.assertIn('Construir aplicação multissserviço',APPROVAL.read_text())
        self.assertIn('Construir aplicação multissserviço',TRANSACTION.read_text())
        self.assertEqual(GUIDE.read_bytes(),GUIDE_LEGACY.read_bytes())

if __name__=='__main__':unittest.main()
