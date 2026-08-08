from pathlib import Path
import unittest

class PublicationRuntimeLinksAndActionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pub=Path('components/control-plane/current-apps/portal-current/cloudif_ui_publications.py').read_text()
        cls.base=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
        cls.agent=Path('components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
    def test_framework_and_environment_cards_are_replaced(self):
        info=self.pub[self.pub.index('def _project_information'):self.pub.index('def publication_panel')]
        self.assertNotIn('<span>Framework</span>',info)
        self.assertNotIn('<span>Ambiente</span>',info)
        self.assertIn('Configuração do PHP',info)
        self.assertIn('Runtime do Node.js',info)
        self.assertIn('Ver informações do PHP',info)
    def test_runtime_pages_are_authenticated_project_routes(self):
        for marker in ('project-runtime-info','_rd_projects(user)','kind not in (\'php\',\'node\')','open-project-terminal'):
            self.assertIn(marker,self.base)
    def test_agent_accepts_only_fixed_php_or_node_queries(self):
        for marker in ('kind not in {"php","node"}','php -v','php -m','process.versions','package.json'):
            self.assertIn(marker,self.agent)
        self.assertNotIn('payload.get("command")',self.agent)
    def test_release_wizard_replaces_direct_publish_controls(self):
        panel=self.pub[self.pub.index('def _configuration_controls'):self.pub.index('def admin_publications')]
        self.assertIn('data-release-flow-open',panel)
        self.assertIn('Detalhes técnicos e versões legadas',panel)
        self.assertNotIn('Publicar nova versão',panel)
        self.assertNotIn('publication-new-version',panel)
    def test_direct_publish_and_activation_actions_are_not_rendered(self):
        self.assertNotIn('value="publish_version"',self.pub)
        self.assertNotIn('value="activate_version"',self.pub)
        self.assertIn('Produção atual',self.pub)

if __name__=='__main__': unittest.main()
