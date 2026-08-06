from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]


class MultiserviceDeploymentExecutionMCPContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gateway=(ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py').read_text()
        cls.registry=(ROOT/'components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py').read_text()
        cls.onboarding=(ROOT/'components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py').read_text()
        cls.broker=(ROOT/'components/control-plane/current-apps/deployment-broker-current/cloudif-deployment-broker.py').read_text()
        cls.unit=(ROOT/'components/control-plane/etc/systemd/system/cloudif-deployment-broker.service').read_text()

    def test_gateway_has_plan_approval_execute_and_status(self):
        for marker in (
            "'name':'deployment.multiservice.plan'",
            "'name':'approval.request-multiservice-deployment'",
            "'name':'deployment.multiservice.execute'",
            "'name':'deployment.multiservice.status'",
            "elif name=='approval.request-multiservice-deployment':",
            "elif name=='deployment.multiservice.execute':",
            "elif name=='deployment.multiservice.status':",
        ):
            self.assertIn(marker,self.gateway)
        read=self.gateway[self.gateway.index('READ_ONLY_TOOLS='):self.gateway.index('DESTRUCTIVE_TOOLS=')]
        destructive=self.gateway[self.gateway.index('DESTRUCTIVE_TOOLS='):self.gateway.index('OPEN_WORLD_PREFIXES=')]
        self.assertIn("'deployment.multiservice.status'",read)
        self.assertIn("'deployment.multiservice.execute'",destructive)

    def test_approval_is_bound_to_acl_revision_variables_and_routes(self):
        helper=self.gateway[self.gateway.index('def approval_create_multiservice_deployment'):self.gateway.index('def deployment_call')]
        for marker in ('deployment_plan_digest','build_job_id','build_plan_digest','config_revision','config_digest','toolchain_digest','archive_sha256','variables_digest','routes','membership_revision','acl_digest',"'content_stored':False","'secret_values_in_metadata':False"):
            self.assertIn(marker,helper)
        dispatch=self.gateway[self.gateway.index("elif name=='deployment.multiservice.execute':"):self.gateway.index("elif name=='deployment.multiservice.status':")]
        for marker in ('approval_binding_mismatch','reserve','finalize','release','transaction_ids','approved_by','variables_digest','membership_revision','acl_digest'):
            self.assertIn(marker,dispatch)
        for forbidden in ('POSTGRES_PASSWORD','SERVICE_ROLE_KEY','DATABASE_URL'):
            self.assertNotIn(forbidden,helper+dispatch)

    def test_scopes_extend_existing_clients_without_new_authentication(self):
        self.assertIn("PROJECT_DEPLOYMENT_WRITE_SCOPES=['approval:request-multiservice-deployment','deployment:multiservice-execute']",self.registry)
        self.assertIn('PROJECT_DEPLOYMENT_WRITE_SCOPES',self.registry)
        self.assertIn('approval:request-multiservice-deployment',self.onboarding)
        self.assertIn('deployment:multiservice-execute',self.onboarding)
        self.assertNotIn('MULTISERVICE_DEPLOYMENT_CLIENT_SECRET',self.registry+self.onboarding+self.gateway)

    def test_broker_resolves_values_only_during_effect(self):
        for marker in ('_resolve_environment','variables_digest_changed','_deployment_executor_call','idem_mark_effect','MULTISERVICE_DEPLOYMENT_EXECUTOR_URL'):
            self.assertIn(marker,self.broker)
        plan=self.broker[self.broker.index('def _multiservice_deployment_plan'):self.broker.index('def _deployment_executor_call')]
        self.assertNotIn("'values':values",plan)
        self.assertIn("'secret_values_included':False",plan)
        self.assertIn('EnvironmentFile=/etc/cloudif/multiservice-deployment-executor.env',self.unit)
        self.assertIn('ReadOnlyPaths=/srv/cloudif/lib /srv/cloudif/tenants /etc/cloudif',self.unit)


if __name__=='__main__':unittest.main()
