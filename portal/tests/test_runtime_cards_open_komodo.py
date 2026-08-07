from pathlib import Path
import unittest

class RuntimeCardsOpenKomodoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pub=Path('components/control-plane/current-apps/portal-current/cloudif_ui_publications.py').read_text()
        cls.base=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
    def test_cards_use_internal_buttons(self):
        for marker in ('publication-runtime-card','Configuração do PHP','Runtime do Node.js','Ver informações do PHP'):
            self.assertIn(marker,self.pub)
        self.assertNotIn('class="publication-info-card publication-runtime-link"',self.pub)
    def test_links_open_dedicated_terminal(self):
        self.assertIn('project-runtime-info?slug=',self.pub)
        self.assertIn('&amp;kind=php',self.pub)
        self.assertIn('&amp;kind=node',self.pub)
    def test_runtime_action_is_standalone_and_not_terminal_redirect(self):
        route=self.base[self.base.index("project-runtime-info'"):self.base.index("open-project-terminal'",self.base.index("project-runtime-info'"))]
        self.assertIn('<!doctype html>',route)
        self.assertIn('CloudIFF · diagnóstico autenticado',route)
        self.assertNotIn('self.send_response(302)',route)
        self.assertNotIn('open-project-terminal?slug=',route)
    def test_fixed_diagnostic_commands_end_in_interactive_shell(self):
        for marker in ('php -i','process.versions','package.json','exec sh','phpinfo-','nodeinfo-'):
            self.assertIn(marker,self.base)
        self.assertNotIn('q.get(\'command\')',self.base)

if __name__=='__main__': unittest.main()
