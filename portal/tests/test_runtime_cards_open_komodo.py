from pathlib import Path
import unittest

class RuntimeCardsOpenKomodoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pub=Path('components/control-plane/current-apps/portal-current/cloudif_ui_publications.py').read_text()
        cls.base=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
        cls.coexist=Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
    def test_runtime_diagnostics_moved_out_of_summary_cards(self):
        info=self.pub[self.pub.index('def _project_information'):self.pub.index('def _publication_snapshot_from_rows')]
        for marker in ('publication-runtime-card','Configuração do PHP','Runtime do Node.js','Ver informações do PHP','project-runtime-info?slug='):
            self.assertNotIn(marker,info)
        for marker in ('data-publication-tool=\"php\"','data-publication-tool=\"node\"','project-runtime-info?slug='):
            self.assertIn(marker,self.base)

    def test_runtime_action_is_standalone_and_not_terminal_redirect(self):
        route=self.base[self.base.index("project-runtime-info'"):self.base.index("open-project-terminal'",self.base.index("project-runtime-info'"))]
        self.assertIn('<!doctype html>',route)
        self.assertIn('CloudIFF · diagnóstico autenticado',route)
        self.assertNotIn('self.send_response(302)',route)
        self.assertNotIn('open-project-terminal?slug=',route)
    def test_fixed_diagnostic_commands_end_in_interactive_shell(self):
        for marker in ('php -i','process.versions','package.json','exec sh','phpinfo-','nodeinfo-'):
            self.assertIn(marker,self.coexist)
        self.assertNotIn('q.get(\'command\')',self.base+self.coexist)

if __name__=='__main__': unittest.main()
