from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
JS=(ROOT/'portal/design/publication-release.js').read_text()
BASE=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
class PublicationReleaseNoStoreTests(unittest.TestCase):
    def test_release_flow_fetch_never_uses_browser_cache(self):
        self.assertIn("cache: 'no-store'",JS)
        self.assertIn("'Cache-Control': 'no-store'",JS)
        self.assertIn("const data = await call(apiBase())",JS)
    def test_asset_version_is_bumped(self):
        self.assertIn('publication-release.js?v=20261123-release-nostore-v13',BASE)
        self.assertNotIn('publication-release.js?v=20261122-runtime-state-v12',BASE)
if __name__=='__main__':unittest.main()
