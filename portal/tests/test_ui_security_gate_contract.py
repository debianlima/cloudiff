from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
GATE=ROOT/'components/control-plane/srv/cloudif/tests/cloudif-ui-security-tests.py'
SHELL=ROOT/'portal/ui/shell.py'

class UISecurityGateContractTests(unittest.TestCase):
    def test_gate_uses_canonical_shell_markers(self):
        gate=GATE.read_text();shell=SHELL.read_text()
        for marker in ('<nav class=\"nav\"','class=\"profile-card\"','class=\"profile-role\">Professor<','Administração do AD','class=\"skip-link\" href=\"#conteudo-principal\"'):
            self.assertIn(marker,gate)
        self.assertNotIn('cloudif-ui-v2',gate);self.assertNotIn('portal-hero',gate);self.assertNotIn('profile-chip teacher',gate)
        self.assertIn('class=\"skip-link\" href=\"#conteudo-principal\"',shell)
    def test_professor_and_admin_contracts_are_distinct(self):
        gate=GATE.read_text()
        self.assertIn("'Administração do AD' not in prof",gate)
        self.assertIn("'Administração do AD' in admin",gate)

if __name__=='__main__':unittest.main()
