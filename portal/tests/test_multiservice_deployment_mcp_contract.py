from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]

class MultiserviceDeploymentMCPContractTests(unittest.TestCase):
    def test_gateway_exposes_read_only_plan(self):
        source=(ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py').read_text()
        self.assertIn("'name':'deployment.multiservice.plan'",source)
        self.assertIn("'deployment.multiservice.plan':'deployment:multiservice-plan'",source)
        read=source[source.index('READ_ONLY_TOOLS='):source.index('DESTRUCTIVE_TOOLS=')]
        self.assertIn("'deployment.multiservice.plan'",read)
        destructive=source[source.index('DESTRUCTIVE_TOOLS='):source.index('OPEN_WORLD_PREFIXES=')]
        self.assertNotIn("'deployment.multiservice.plan'",destructive)
        self.assertIn("elif name=='deployment.multiservice.plan':",source)
        self.assertIn("'/v1/multiservice-plan'",source)

    def test_scopes_are_reconciled_without_new_authentication(self):
        registry=(ROOT/'components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py').read_text()
        onboarding=(ROOT/'components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py').read_text()
        self.assertIn("PROJECT_DEPLOYMENT_READ_SCOPES=['deployment:multiservice-plan']",registry)
        self.assertIn('PROJECT_DEPLOYMENT_READ_SCOPES',registry)
        self.assertIn('deployment:multiservice-plan',onboarding)
        self.assertNotIn('CLOUDIF_MULTISERVICE_DEPLOYMENT_CLIENT_SECRET',registry+onboarding)

    def test_deployment_broker_depends_on_reconciled_sources(self):
        source=(ROOT/'components/control-plane/current-apps/deployment-broker-current/cloudif-deployment-broker.py').read_text()
        unit=(ROOT/'components/control-plane/etc/systemd/system/cloudif-deployment-broker.service').read_text()
        for marker in ('PROJECT_CONFIG_URL','PROJECT_RECONCILER_URL','BUILD_BROKER_URL','_multiservice_deployment_plan','required_environment_unresolved','secret_values_included'):
            self.assertIn(marker,source)
        for marker in ('cloudif-project-config-controller.service','cloudif-project-config-reconciler.service','cloudif-build-broker.service','EnvironmentFile=/etc/cloudif/project-config-controller.env','EnvironmentFile=/etc/cloudif/project-config-reconciler.env','EnvironmentFile=/etc/cloudif/build-broker.env'):
            self.assertIn(marker,unit)

    def test_portal_guide_documents_single_summary(self):
        guide=(ROOT/'components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py').read_text()
        legacy=(ROOT/'portal/legacy/cloudif_ai_agents_guide.py').read_text()
        self.assertEqual(guide,legacy)
        self.assertIn("'deployment.multiservice.plan':",guide)
        self.assertIn("'deployment:multiservice-plan':['deployment.multiservice.plan']",guide)


if __name__=='__main__':unittest.main()
