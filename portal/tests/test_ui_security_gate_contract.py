from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
GATE=ROOT/'components/control-plane/srv/cloudif/tests/cloudif-ui-security-tests.py'
SHELL=ROOT/'portal/ui/shell.py'

class UISecurityGateContractTests(unittest.TestCase):
    def test_gate_uses_canonical_shell_markers(self):
        gate=GATE.read_text(); shell=SHELL.read_text()
        for marker in (
            '<nav class="nav" id="nav"',
            '<main class="page" id="conteudo-principal"',
            'class="profile-card"',
            'class="profile-role">Professor<',
            'Administração do AD',
            'class="skip-link" href="#conteudo-principal"',
            'Sair da plataforma',
            '/if/flow/default-invalidation-flow/',
        ):
            self.assertIn(marker,gate)
        self.assertNotIn('/outpost.goauthentik.io/sign_out',gate)
        self.assertIn('class="skip-link" href="#conteudo-principal"',shell)
        self.assertIn('default-invalidation-flow',shell)

    def test_professor_and_admin_contracts_are_distinct_and_uncached(self):
        gate=GATE.read_text()
        self.assertIn("fetch('teste.professor'",gate)
        self.assertIn("fetch('teste.admin'",gate)
        self.assertIn("'Administração do AD' not in prof",gate)
        self.assertIn("'Administração do AD' in admin",gate)
        self.assertIn("'Host':CANONICAL_HOST",gate)

if __name__=='__main__':
    unittest.main()
