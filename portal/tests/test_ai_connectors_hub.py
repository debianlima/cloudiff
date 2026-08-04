import importlib.util
from pathlib import Path
import unittest


class AIConnectorsHubTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py')
        spec = importlib.util.spec_from_file_location('cloudif_ai_agents_guide_test', path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_empty_hub_keeps_guidance_and_separation(self):
        html = self.module.render([], 'csrf-test')
        for text in ('Portal e agentes funcionam de forma independente', 'ChatGPT', 'Claude', 'Llama / Ollama', 'Nenhum projeto disponível para conexão'):
            self.assertIn(text, html)
        self.assertNotIn('details open', html)

    def test_project_hub_uses_real_rotation_endpoint(self):
        row = {
            'project_slug': 'projeto-teste',
            'client_id': 'client-projeto-teste',
            'role_profile': 'developer',
            'environment': 'project',
            'scopes': ['project:read', 'workspace:prepare', 'forgejo:plan-edit'],
            'instructions': {'mcp_endpoint': 'https://cloudiff.example/mcp'},
        }
        html = self.module.render([row], 'csrf-test')
        self.assertIn('Gerar nova chave', html)
        self.assertIn('/cloudiff/portal/action/rotate-project-credential', html)
        self.assertIn('Exibição única', html)
        self.assertIn('não altera o funcionamento do Portal web', html)
        self.assertIn('Configuração para clientes MCP', html)


    def test_pending_approval_is_embedded_in_project_card(self):
        row = {
            'project_slug': 'projeto-teste', 'client_id': 'client-projeto-teste',
            'role_profile': 'developer', 'environment': 'project',
            'scopes': ['project:read'], 'instructions': {'mcp_endpoint': 'https://cloudiff.example/mcp'},
        }
        approval = {
            'approval_id': 'apr_test', 'project_slug': 'projeto-teste',
            'status': 'pending', 'action_label': 'Publicar em homologação', 'reason': 'Validar release',
        }
        html = self.module.render([row], 'csrf-test', [approval], True)
        self.assertIn('Aprovações humanas', html)
        self.assertIn('Publicar em homologação', html)
        self.assertIn('>Aceitar<', html)
        self.assertIn('>Rejeitar<', html)
        self.assertIn('name="return_to" value="agentes"', html)

    def test_global_services_has_dedicated_current_route(self):
        source = Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
        self.assertIn('def global_services_body', source)
        self.assertIn('tab == "admin-manutencao"', source)
        self.assertIn('Todos os containers', source)
        self.assertIn('Repositórios por usuário', source)

    def test_shell_does_not_append_legacy_identity_panel(self):
        source = Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
        self.assertNotIn('identities = getattr(owner, "_oi_panel")', source)


if __name__ == '__main__':
    unittest.main()
