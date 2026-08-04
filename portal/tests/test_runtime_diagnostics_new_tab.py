from pathlib import Path
import unittest

class RuntimeDiagnosticsNewTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pub=Path('components/control-plane/current-apps/portal-current/cloudif_ui_publications.py').read_text()
        cls.base=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
    def test_links_open_isolated_page(self):
        self.assertIn('target="_blank" rel="noopener"',self.pub)
        self.assertIn('Ver informações do PHP',self.pub)
        self.assertIn('Ver informações do Node.js',self.pub)
    def test_inline_modal_is_removed(self):
        for marker in ('runtime-modal-backdrop','data-runtime-modal','document.body.appendChild(modal)','runtime_script ='):
            self.assertNotIn(marker,self.pub)
    def test_route_renders_standalone_modern_document(self):
        route=self.base[self.base.index("project-runtime-info'"):self.base.index("open-project-terminal'",self.base.index("project-runtime-info'"))]
        for marker in ('<!doctype html>','CloudIFF · diagnóstico autenticado','Fechar e voltar','background:#f4f7f5','font-family:Inter'):
            self.assertIn(marker,route)
        self.assertNotIn('page(user',route)
        self.assertNotIn('open-project-terminal',route)
    def test_route_remains_authenticated_and_project_scoped(self):
        route=self.base[self.base.index("project-runtime-info'"):self.base.index("open-project-terminal'",self.base.index("project-runtime-info'"))]
        self.assertIn('_rd_projects(user)',route)
        self.assertIn('_rd_runtime_info_with_reconcile',route)
        self.assertIn("kind not in ('php','node')",route)

if __name__=='__main__':unittest.main()
