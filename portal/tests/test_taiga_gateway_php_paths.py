from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONF = ROOT / 'components/faro/current-apps/taiga-current/taiga.conf'
RULE = r'location ~* \.(?:php(?:[0-9]+)?|phtml|phar)(?:/|$) { return 404; }'


class TaigaGatewayPhpPathTests(unittest.TestCase):
    def test_php_like_paths_are_rejected_before_frontend_proxy(self):
        source = CONF.read_text()
        self.assertEqual(source.count(RULE), 1)
        rule_pos=source.index(RULE)
        frontend_pos=source.index('  location / {',rule_pos)
        api_pos=source.index('  location /api/',frontend_pos)
        self.assertLess(rule_pos,frontend_pos)
        self.assertLess(frontend_pos,api_pos)
        self.assertIn('proxy_pass http://taiga-front/;',source[frontend_pos:api_pos])

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
