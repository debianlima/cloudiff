from pathlib import Path
import unittest

class RouterWarmupVisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path('components/control-plane/srv/cloudif/bin/cloudif-apply-router-authz-v233.sh').read_text()
    def test_initial_warmup_uses_preparation_screen(self):
        for marker in ('CloudIF está preparando seu ambiente','Inicializando serviços do tenant','Validando banco e API','Aguarde 5 segundos para estabilizar o ambiente.'):
            self.assertIn(marker,self.source)
    def test_white_legacy_warmup_is_removed(self):
        self.assertNotIn('CloudIF está carregando seu ambiente',self.source)
        self.assertNotIn('Se não abrir, pressione F5.',self.source)
    def test_warmup_contract_is_unchanged(self):
        for marker in ('cloudif_router_warmup=1','Max-Age=20','meta http-equiv="refresh" content="5"','error_page 418 = @cloudif_router_warmup_v256'):
            self.assertIn(marker,self.source)

if __name__=='__main__': unittest.main()
