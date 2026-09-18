from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
CONF=ROOT/'components/proxy/srv/cloudif/proxy/npm/data/nginx/custom/http_top.conf'

class TaigaEdgeCloudifEnterTests(unittest.TestCase):
    def test_cloudif_enter_is_handled_before_generic_proxy(self):
        s=CONF.read_text()
        route='location ~ "^/cloudif-enter/([a-z0-9][a-z0-9-]{0,62})/?$" {'
        self.assertIn(route,s)
        self.assertLess(s.index(route),s.index('    location / {',s.index('server_name taiga.cloudiff.duckdns.org;',s.index('listen 443 ssl;'))))
        self.assertIn('location.replace("/oidc/authenticate/?next=/project/$1")',s)
        self.assertIn('localStorage.removeItem("token")',s)
        self.assertIn('sessionStorage.removeItem("token")',s)
        self.assertIn('Cache-Control "no-store"',s)
        self.assertIn('sessionid=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax',s)

    def test_slug_pattern_does_not_accept_arbitrary_path(self):
        s=CONF.read_text()
        self.assertIn('[a-z0-9][a-z0-9-]{0,62}',s)
        self.assertNotIn('cloudif-enter/(.*)',s)

if __name__=='__main__': unittest.main()
