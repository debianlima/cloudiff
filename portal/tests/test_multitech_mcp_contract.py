from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[2]
BROKER = ROOT / 'components/control-plane/current-apps/workspace-broker-current/cloudif-workspace-broker.py'
DETECTOR = ROOT / 'components/control-plane/current-apps/workspace-broker-current/cloudif_multitech_detector.py'
GATEWAY = ROOT / 'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
REGISTRY = ROOT / 'components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py'
ONBOARDING = ROOT / 'components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py'
GATEWAY_UNIT = ROOT / 'components/control-plane/etc/systemd/system/cloudif-mcp-gateway.service'
GUIDE = ROOT / 'components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py'
GUIDE_LEGACY = ROOT / 'portal/legacy/cloudif_ai_agents_guide.py'

TOOLS = {
    'project.technologies.detect',
    'project.manifest.validate',
    'project.configuration.get',
}


class MultitechMCPContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.broker = BROKER.read_text()
        cls.detector = DETECTOR.read_text()
        cls.gateway = GATEWAY.read_text()
        cls.registry = REGISTRY.read_text()
        cls.onboarding = ONBOARDING.read_text()
        cls.unit = GATEWAY_UNIT.read_text()
        cls.guide = GUIDE.read_text()

    def test_workspace_broker_exposes_recursive_detection_without_new_auth(self):
        self.assertIn("'/v1/detect-multiservice'", self.broker)
        self.assertIn("'workspace.detect-multiservice'", self.broker)
        self.assertIn('from cloudif_multitech_detector import detect_components', self.broker)
        self.assertIn("headers={'Authorization':'Bearer '+WORKSPACE_TOKEN", self.gateway)
        self.assertNotIn('CLOUDIF_MULTITECH_CLIENT_SECRET', self.broker + self.gateway)

    def test_detector_is_recursive_bounded_and_private_safe(self):
        for marker in (
            'DETECTION_MAX_DEPTH = 8', 'DETECTION_MAX_FILES = 25000',
            'IGNORED_TECH_DIRS', 'node_modules', 'vendor', '.next',
            'PRIVATE_FILE_RE', 'privateFilesExcluded', 'sideEffectFree',
            'manifestProposal', 'requiresHumanReview',
        ):
            self.assertIn(marker, self.detector)
        self.assertNotIn('shutil.move', self.detector)
        self.assertNotIn('os.rename', self.detector)
        self.assertNotIn('subprocess.', self.detector)

    def test_tools_are_in_existing_gateway_catalog_and_read_only(self):
        for tool in TOOLS:
            self.assertIn("'name':'" + tool + "'", self.gateway, tool)
        read_block = self.gateway[self.gateway.index('READ_ONLY_TOOLS='):self.gateway.index('DESTRUCTIVE_TOOLS=')]
        for tool in TOOLS:
            self.assertIn("'" + tool + "'", read_block)
        destructive = self.gateway[self.gateway.index('DESTRUCTIVE_TOOLS='):self.gateway.index('OPEN_WORLD_PREFIXES=')]
        for tool in TOOLS:
            self.assertNotIn("'" + tool + "'", destructive)
        ast.parse(self.gateway)

    def test_gateway_binds_detection_and_manifest_to_authorized_project(self):
        detection = self.gateway[self.gateway.index("elif name=='project.technologies.detect':"):self.gateway.index("elif name=='workspace.prepare':")]
        self.assertIn("control('/v1/projects/'", detection)
        self.assertIn('workspace_detect_multiservice(slug,ref,trace_id)', detection)
        self.assertIn("project_config_call('POST','/v1/manifest/validate'", detection)
        self.assertIn('O campo slug é obrigatório', detection)
        self.assertIn('O campo ref é incompatível', detection)
        self.assertIn('Os campos slug e manifest são obrigatórios', detection)

    def test_project_configuration_uses_internal_controller_token(self):
        for marker in (
            "PROJECT_CONFIG_URL=os.environ.get('CLOUDIF_PROJECT_CONFIG_URL','http://127.0.0.1:18219')",
            "PROJECT_CONFIG_TOKEN=os.environ.get('CLOUDIF_PROJECT_CONFIG_TOKEN','')",
            "EnvironmentFile=/etc/cloudif/project-config-controller.env",
            'cloudif-project-config-controller.service',
        ):
            self.assertIn(marker, self.gateway + self.unit)
        self.assertIn('IPAddressAllow=127.0.0.0/8', self.unit)
        self.assertIn('IPAddressDeny=any', self.unit)

    def test_existing_identities_receive_scopes_by_reconciliation(self):
        for scope in ('workspace:detect-multiservice', 'project:configuration-read'):
            self.assertIn(scope, self.registry)
            self.assertIn(scope, self.onboarding)
            self.assertIn(scope, self.gateway)
            self.assertIn(scope, self.guide)
        self.assertIn('PROJECT_DISCOVERY_SCOPES', self.registry)
        self.assertIn("for role,scopes in ROLE_SCOPES.items()", self.registry)
        reconcile = self.registry[self.registry.index("if p.startswith('/v1/clients/') and p.endswith('/reconcile')"):]
        self.assertIn('token_hash_preserved', reconcile)
        self.assertIn('created_at_preserved', reconcile)
        self.assertIn('token_returned', reconcile)

    def test_onboarding_recommends_tools_for_current_project_client(self):
        for tool in TOOLS:
            self.assertIn("'" + tool + "'", self.onboarding)
        self.assertIn("'additional_authentication':False", self.onboarding)
        self.assertIn("'same_mcp_endpoint':True", self.onboarding)

    def test_connector_guide_documents_all_new_tools(self):
        for tool in TOOLS:
            self.assertIn("'" + tool + "':", self.guide)
        self.assertIn('Detectar tecnologias e serviços', self.guide)
        self.assertIn('Validar manifesto CloudIFF', self.guide)
        self.assertIn('Consultar configuração efetiva', self.guide)
        self.assertIn("'documentation_version':'129A'", self.guide)
        self.assertEqual(GUIDE.read_bytes(), GUIDE_LEGACY.read_bytes())


if __name__ == '__main__':
    unittest.main()
