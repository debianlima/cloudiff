from pathlib import Path
import unittest

class RuntimeModalWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pub=Path('components/control-plane/current-apps/portal-current/cloudif_ui_publications.py').read_text()
        cls.base=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
    def test_runtime_cards_use_text_links(self):
        for marker in ('Ver informações do PHP','Ver informações do Node.js','publication-runtime-text','data-runtime-kind="php"','data-runtime-kind="node"'):
            self.assertIn(marker,self.pub)
        self.assertNotIn('Abrir no Komodo',self.pub)
        self.assertNotIn('publication-runtime-button',self.pub)
    def test_modal_is_part_of_modern_publication_page(self):
        for marker in ('runtime-modal-backdrop','runtime-modal-close','data-runtime-body','Informações do runtime','Diagnóstico autenticado'):
            self.assertIn(marker,self.pub)
    def test_modal_fetches_authenticated_api(self):
        self.assertIn('/cloudiff/portal/api/project-runtime-info?slug=',self.pub)
        self.assertIn('same-origin',self.pub)
        self.assertIn("path in ('/cloudiff/portal/api/project-runtime-info'",self.base)
        self.assertIn("_rd_projects(user)",self.base)
    def test_modal_has_all_close_behaviors(self):
        for marker in ('data-runtime-close','Escape','event.target===modal'):
            self.assertIn(marker,self.pub)
    def test_old_url_returns_to_modern_publication(self):
        route=self.base[self.base.index("project-runtime-info'"):self.base.index("open-project-terminal'",self.base.index("project-runtime-info'"))]
        self.assertIn('tab=publicacao',route)
        self.assertIn('runtime_info=',route)
        self.assertNotIn('open-project-terminal?slug=',route)

if __name__=='__main__': unittest.main()
