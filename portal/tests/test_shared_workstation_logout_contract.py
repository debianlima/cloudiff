from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
SHELL=(ROOT/'portal/ui/shell.py').read_text()
CURRENT=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
LEGACY=(ROOT/'portal/legacy/cloudif-admin-portal-base.py').read_text()

class SharedWorkstationLogoutContractTests(unittest.TestCase):
    def test_logout_uses_global_authentik_invalidation(self):
        for src in (SHELL,CURRENT,LEGACY):
            self.assertIn('default-invalidation-flow',src)
            self.assertIn('authiff.duckdns.org',src)
            self.assertNotIn('href=\"/outpost.goauthentik.io/sign_out\"',src)

    def test_logout_returns_to_portal_and_is_configurable(self):
        self.assertIn('CLOUDIF_AUTHENTIK_GLOBAL_LOGOUT_URL',SHELL)
        self.assertIn('cloudiff.duckdns.org%2Fcloudiff%2Fportal%2F',SHELL)
        for src in (CURRENT,LEGACY):
            self.assertIn('def auth_logout_url():',src)
            self.assertIn('CLOUDIF_AUTHENTIK_GLOBAL_LOGOUT_URL',src)
            self.assertIn('cloudiff.duckdns.org%2Fcloudiff%2Fportal%2F',src)

if __name__=='__main__': unittest.main()
