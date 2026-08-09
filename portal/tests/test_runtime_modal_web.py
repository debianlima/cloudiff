from pathlib import Path
import unittest

class RuntimeModalWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pub=Path('components/control-plane/current-apps/portal-current/cloudif_ui_publications.py').read_text()
        cls.base=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
    def test_runtime_summary_links_are_removed_in_favor_of_workspace_tools(self):
        runtime_cards=self.pub[self.pub.index('def _project_information'):self.pub.index('def _publication_snapshot_from_rows')]
        for marker in ('Ver informações do PHP','Ver informações do Node.js','publication-runtime-text','&amp;kind=php','&amp;kind=node','project-runtime-info?slug='):
            self.assertNotIn(marker,runtime_cards)
        self.assertIn('data-publication-tool="php"',self.base)
        self.assertIn('data-publication-tool="node"',self.base)

    def test_runtime_diagnostics_use_isolated_modern_page(self):
        self.assertNotIn('publication-runtime-card',self.pub)
        for marker in ('runtime-modal-backdrop','data-runtime-modal','document.body.appendChild(modal)'):
            self.assertNotIn(marker,self.pub)
    def test_runtime_route_remains_authenticated_and_project_scoped(self):
        self.assertIn('/cloudiff/portal/action/project-runtime-info?slug=',self.base)
        self.assertIn("path in ('/cloudiff/portal/api/project-runtime-info'",self.base)
        self.assertIn("_rd_projects(user)",self.base)
        self.assertIn('_rd_runtime_info_with_reconcile',self.base)
    def test_standalone_document_has_explicit_return_action(self):
        route=self.base[self.base.index("project-runtime-info'"):self.base.index("open-project-terminal'",self.base.index("project-runtime-info'"))]
        self.assertIn('Fechar e voltar',route)
        self.assertIn('<!doctype html>',route)
    def test_runtime_action_renders_standalone_document(self):
        route=self.base[self.base.index("project-runtime-info'"):self.base.index("open-project-terminal'",self.base.index("project-runtime-info'"))]
        self.assertIn('CloudIFF · diagnóstico autenticado',route)
        self.assertNotIn('open-project-terminal?slug=',route)

if __name__=='__main__': unittest.main()
