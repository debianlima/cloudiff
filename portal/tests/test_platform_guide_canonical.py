from pathlib import Path
import unittest

class CanonicalPlatformGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path('components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
    def test_repository_card_is_in_canonical_guide(self):
        for marker in ('GitHub e manual técnico','https://github.com/debianlima/cloudiff','Abrir GitHub do projeto','protocolos de reconciliação','modelo de dados','cada pasta e arquivo'):
            self.assertIn(marker,self.source)
        self.assertIn('rel="noopener noreferrer"',self.source)

if __name__=='__main__':unittest.main()
