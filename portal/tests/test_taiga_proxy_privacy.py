from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
CONF=ROOT/'components/proxy/srv/cloudif/proxy/npm/data/nginx/custom/http_top.conf'

class TaigaProxyPrivacyTests(unittest.TestCase):
    def test_taiga_has_dedicated_privacy_safe_log(self):
        source=CONF.read_text()
        line=next(x for x in source.splitlines() if x.startswith('log_format cloudif_taiga_safe'))
        self.assertIn('$uri',line)
        self.assertNotIn('$request_uri',line)
        self.assertNotIn('$http_referer',line)
        self.assertGreaterEqual(source.count('access_log /data/logs/taiga_safe_access.log cloudif_taiga_safe;'),2)

    def test_login_is_no_store(self):
        source=CONF.read_text()
        self.assertIn('map $uri $cloudif_taiga_cache_control',source)
        self.assertIn('/login "no-store";',source)
        self.assertIn('add_header Cache-Control $cloudif_taiga_cache_control always;',source)

if __name__=='__main__': unittest.main()
