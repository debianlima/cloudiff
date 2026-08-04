from pathlib import Path
import unittest


class ProjectProvisioningLiveWizardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()

    def test_async_creation_uses_authenticated_portal_route(self):
        self.assertIn("'X-CloudIF-Action':'project_action'", self.source)
        self.assertIn("'X-CloudIF-Async':'project-provision'", self.source)
        self.assertIn("internal_action=='project_action'", self.source)
        self.assertIn("self.send_response(202)", self.source)

    def test_status_api_is_authorized_and_hides_secrets(self):
        self.assertIn("api=='project-provision-status'", self.source)
        self.assertIn("project_not_authorized", self.source)
        self.assertIn("'secrets_exposed':False", self.source)

    def test_modal_tracks_real_provisioning_stages(self):
        for marker in (
            'pm197_provision_live', 'Provisionamento em andamento',
            'Registro do projeto', 'Repositório Forgejo', 'Stack e containers',
            'Banco e tenant', 'Identidade e permissões', 'Template da aplicação',
            'Publicação inicial', 'Aguardando a etapa anterior.',
        ):
            self.assertIn(marker, self.source)


if __name__ == '__main__':
    unittest.main()
