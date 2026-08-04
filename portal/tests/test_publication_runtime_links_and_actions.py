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
        self.assertIn('Informações do PHP',info)
        self.assertIn('Informações do Node.js',info)
    def test_runtime_pages_are_authenticated_project_routes(self):
        for marker in ('project-runtime-info','_rd_projects(user)','kind not in (\'php\',\'node\')','Voltar à publicação'):
            self.assertIn(marker,self.base)
    def test_agent_accepts_only_fixed_php_or_node_queries(self):
        for marker in ('kind not in {"php","node"}','php -v','php -m','process.versions','package.json'):
            self.assertIn(marker,self.agent)
        self.assertNotIn('payload.get("command")',self.agent)
    def test_publish_new_version_is_below_versions_table(self):
        panel=self.pub[self.pub.index('def publication_panel'):self.pub.index('def admin_publications')]
        table=panel.index('Versões publicadas')
        button=panel.index('Publicar nova versão')
        self.assertGreater(button,table)
        self.assertIn('publication-new-version',panel)
        self.assertIn('publication-site-actions',panel)
    def test_existing_publication_actions_remain(self):
        for marker in ('value="publish_version"','value="activate_version"','Abrir site'):
            self.assertIn(marker,self.pub)

if __name__=='__main__': unittest.main()
