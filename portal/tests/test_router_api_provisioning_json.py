from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONF = ROOT / "components/control-plane/srv/cloudif/router/conf.d/default.conf"
APPLY = ROOT / "components/control-plane/srv/cloudif/bin/cloudif-apply-router-authz-v233.sh"


class RouterApiProvisioningJsonTests(unittest.TestCase):
    def test_static_api_location_uses_json_forbidden_handler(self):
        source = CONF.read_text(encoding="utf-8")
        self.assertIn("location @cloudif_forbidden_api_v257 {", source)
        self.assertIn('default_type application/json;', source)
        self.assertIn('return 503 \'{"ok":false,"error":"tenant_provisioning","retry_after_seconds":5}\';', source)
        start = source.index("location ^~ /api/ {")
        end = source.index("\n    location ", start + 1)
        api = source[start:end]
        self.assertIn("error_page 403 = @cloudif_forbidden_api_v257;", api)
        self.assertNotIn("error_page 403 = @cloudif_forbidden_v244;", api)

    def test_browser_navigation_keeps_html_provisioning_page(self):
        source = CONF.read_text(encoding="utf-8")
        start = source.index("location @cloudif_forbidden_v244 {")
        end = source.index("\n    location ", start + 1)
        browser = source[start:end]
        self.assertIn("default_type text/html;", browser)
        self.assertIn("<title>CloudIF preparando ambiente</title>", browser)
        self.assertIn("return 202", browser)

    def test_authz_apply_script_preserves_api_safe_contract(self):
        source = APPLY.read_text(encoding="utf-8")
        self.assertIn("location @cloudif_forbidden_api_v257", source)
        self.assertIn("api_auth_snippet = auth_snippet.replace(", source)
        self.assertIn("'error_page 403 = @cloudif_forbidden_api_v257;'", source)
        self.assertIn('out.append(api_auth_snippet.rstrip("\\n"))', source)


if __name__ == "__main__":
    unittest.main()
