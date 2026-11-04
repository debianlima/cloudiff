from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONF = ROOT / 'components/faro/current-apps/taiga-current/taiga.conf'
RULE = r'location ~* \.(?:php(?:[0-9]+)?|phtml|phar)(?:/|$) { return 404; }'


class TaigaGatewayPhpPathTests(unittest.TestCase):
    def test_php_like_paths_are_rejected_before_frontend_proxy(self):
        source = CONF.read_text()
        self.assertEqual(source.count(RULE), 1)
        self.assertLess(source.index(RULE), source.index('location / { proxy_pass http://taiga-front/;'))

    def test_core_taiga_routes_remain_present(self):
        source = CONF.read_text()
        for marker in (
            'location /api/',
            'location /oidc/',
            'location /admin/',
            'location /media/',
            'location /events',
        ):
            self.assertIn(marker, source)


if __name__ == '__main__':
    unittest.main()
