from pathlib import Path
import unittest


class AdminDeleteIdentityObservabilityContractTest(unittest.TestCase):
    def setUp(self):
        self.source=Path('components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py').read_text(encoding='utf-8')

    def test_deletes_only_project_agent_clients_and_usage(self):
        self.assertIn("client_id LIKE 'project-%'",self.source)
        self.assertIn("DELETE FROM usage WHERE client_id=?",self.source)
        self.assertIn("slug in projects",self.source)

    def test_deletes_onboarding_secret_events_and_rotation_audit(self):
        self.assertIn("('credential_rotations','onboarding_events','project_onboarding')",self.source)
        self.assertIn("ONBOARDING_SECRETS/f'{slug}.json'",self.source)

    def test_deletes_project_observability(self):
        self.assertIn("DELETE FROM notifications WHERE project_slug=?",self.source)
        self.assertIn("DELETE FROM latest WHERE slug=?",self.source)
        self.assertIn("DELETE FROM samples WHERE slug=?",self.source)

    def test_panel_reports_identity_and_observability_stages(self):
        self.assertIn('Identidade do agente',self.source)
        self.assertIn('Onboarding e credencial',self.source)
        self.assertIn('Observabilidade',self.source)


if __name__=='__main__':
    unittest.main()
