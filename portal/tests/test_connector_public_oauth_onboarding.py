from pathlib import Path
import unittest


class ConnectorPublicOAuthOnboardingTest(unittest.TestCase):
    def test_onboarding_publishes_public_oauth_configuration(self):
        source = Path('components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py').read_text()
        for marker in (
            "OAuth 2.1 público com PKCE",
            "'client_secret':''",
            "'token_endpoint_auth_method':'none'",
            "'code_challenge_method':'S256'",
            "'scopes':['mcp','offline_access']",
            "'legacy_bearer'",
        ):
            self.assertIn(marker, source)
        primary = source[source.index('def instructions'):source.index('def write_secret')]
        self.assertNotIn("'client_secret':'Use a chave", primary)

    def test_control_registry_includes_project_and_tenant_acl(self):
        source = Path('components/control-plane/usr/local/sbin/cloudif-control-plane-sync.py').read_text()
        self.assertIn('select slug,subject_type,subject from project_acl', source)
        self.assertIn('project_acl.setdefault', source)
        self.assertIn('list(project_acl.get(slug,[]))+list(tenant_acl.get', source)

    def test_connector_guide_mirrors_are_identical(self):
        current = Path('components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py').read_bytes()
        legacy = Path('portal/legacy/cloudif_ai_agents_guide.py').read_bytes()
        self.assertEqual(current, legacy)


if __name__ == '__main__':
    unittest.main()
