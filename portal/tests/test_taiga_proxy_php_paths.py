from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONF = ROOT / 'components/proxy/srv/cloudif/proxy/npm/data/nginx/custom/http_top.conf'
RULE = r'location ~* \.(?:php(?:[0-9]+)?|phtml|phar)(?:/|$) { return 404; }'


class TaigaProxyPhpPathTests(unittest.TestCase):
    def test_php_like_paths_are_rejected_in_http_and_https_servers(self):
        source = CONF.read_text()
        self.assertEqual(source.count(RULE), 2)

    def test_taiga_proxy_upstream_remains_unchanged(self):
        source = CONF.read_text()
        self.assertIn('proxy_pass http://10.62.91.5:19000;', source)
        self.assertIn('server_name taiga.cloudiff.duckdns.org;', source)


if __name__ == '__main__':
    unittest.main()
