import unittest
from pathlib import Path


class UiDependencyDegradationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]
        cls.source = (root / 'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()

    def test_publication_page_degrades_without_executing_actions(self):
        block = self.source[self.source.index('# CloudIF unified publication page BEGIN'):self.source.index('# CloudIF unified publication page END')]
        self.assertIn("try: body=_pub110.render", block)
        self.assertIn('Publicação temporariamente indisponível.', block)
        self.assertIn('Nenhuma publicação foi executada.', block)
        self.assertIn("data={'ok':False,'error':'publication_unavailable'", block)
        self.assertIn('code=503', block)

    def test_agent_page_degrades_when_onboarding_is_unavailable(self):
        block = self.source[self.source.index('# CloudIF AI agents guide BEGIN'):self.source.index('# CloudIF AI agents guide END')]
        self.assertIn('try: identities=_oi_visible(user)', block)
        self.assertIn('Onboarding temporariamente indisponível.', block)
        self.assertIn('Nenhuma credencial foi alterada.', block)
        self.assertIn("data={'ok':False,'error':'agent_guide_unavailable'", block)
        self.assertIn('code=503', block)

    def test_reconciliation_page_degrades_while_api_keeps_503(self):
        block = self.source[self.source.index('# CloudIF asynchronous reconciliation tab BEGIN'):self.source.index('# CloudIF asynchronous reconciliation tab END')]
        self.assertIn('try: body=_rec.render()', block)
        self.assertIn('Reconciliação temporariamente indisponível.', block)
        self.assertIn('Nenhuma ação foi executada.', block)
        self.assertIn("data={'ok':False,'error':'reconciliation_unavailable'", block)
        self.assertIn('code=503', block)


if __name__ == '__main__':
    unittest.main()
