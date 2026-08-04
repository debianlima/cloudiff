from pathlib import Path
import unittest

class PlatformGuideGithubTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
        cls.modular=Path('components/control-plane/srv/cloudif/lib/cloudif_ui_pages.py').read_text()
        cls.focused=Path('components/control-plane/current-apps/portal-current/cloudif_portal_sections98.py').read_text()
    def test_both_help_renderers_link_documented_repository(self):
        for source in (self.base,self.modular,self.focused):
            self.assertIn('https://github.com/debianlima/cloudiff',source)
            self.assertIn('target="_blank"',source)
            self.assertIn('noopener noreferrer',source)
    def test_guide_explains_technical_scope(self):
        for marker in ('arquitetura','reconciliação','modelo de dados'):
            self.assertIn(marker,self.base.lower())

if __name__=='__main__':unittest.main()
