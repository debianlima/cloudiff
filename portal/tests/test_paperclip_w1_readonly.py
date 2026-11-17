#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest
import unittest.mock
from urllib.error import HTTPError

P = pathlib.Path(__file__).resolve().parents[1] / "tools" / "check_paperclip_w1_readonly.py"
spec = importlib.util.spec_from_file_location("paperclip_w1", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class TestPaperclipW1Readonly(unittest.TestCase):
    def fixture(self, root_public=403, root_origin=403, ui=200, vite=True, asset=404):
        return {"public": {"/": {"http": root_public}},
                "origin": {"/": {"http": root_origin},
                           "/ui/": {"http": ui, "vite_raw_index": vite},
                           "/src/main.tsx": {"http": asset},
                           "/@vite/client": {"http": asset}}}

    def test_reproduced_problem(self):
        self.assertEqual(m.classify(self.fixture()), "BROKEN_ROOT_403_VITE_SOURCE_UNBUILT")

    def test_403_without_vite_hint(self):
        self.assertEqual(m.classify(self.fixture(vite=False)), "BROKEN_ROOT_403")

    def test_403_origin_not_public(self):
        self.assertEqual(m.classify(self.fixture(root_public=200)), "HTTP_ROOT_200_E2E_NOT_VERIFIED")

    def test_origin_missing_not_falsely_healthy(self):
        self.assertEqual(m.classify(self.fixture(root_origin=None)), "NOT_VALIDATED")

    def test_vite_client_exists_no_false_specificity(self):
        self.assertEqual(m.classify(self.fixture(asset=200)), "BROKEN_ROOT_403")

    def test_200_unbuilt_vite_must_fail(self):
        d = self.fixture(root_public=200)
        d["public"]["/"].update({"raw_vite_source": True, "built_asset_path": ""})
        self.assertEqual(m.classify(d), "BROKEN_HTTP_200_RAW_VITE_SOURCE")

    def test_200_onboarding_not_marked_functional(self):
        d = self.fixture(root_public=200)
        d["public"]["/"].update({"title_is_paperclip": True, "built_asset_path": ""})
        self.assertEqual(m.classify(d), "HTTP_ROOT_200_E2E_NOT_VERIFIED")

    def test_built_assets_pass_only_static_gate(self):
        d = self.fixture(root_public=200)
        d["public"]["/"].update({"title_is_paperclip": True, "built_asset_path": "/assets/main-abc.js"})
        d["public"]["/assets/main-abc.js"] = {"http": 200, "content_type": "application/javascript"}
        self.assertEqual(m.classify(d), "STATIC_APP_ASSET_200_AUTH_E2E_PENDING")
        d["public"]["/assets/main-abc.js"] = {"http": 404, "content_type": "text/html"}
        self.assertEqual(m.classify(d), "HTTP_ROOT_200_E2E_NOT_VERIFIED")

    def test_safe_same_origin_asset_regex(self):
        for s in ['<script src="/assets/main.js"></script>',
                  '<link href="/ui/assets/x.css">']:
            self.assertIsNotNone(m.ASSET_RE.search(s))
        for s in ['<script src="https://evil.example/assets/x.js">',
                  '<script src="//evil.example/x.js">',
                  '<script src="/../private.js">']:
            self.assertIsNone(m.ASSET_RE.search(s))

    def test_no_status_not_validated(self):
        self.assertEqual(m.classify({}), "NOT_VALIDATED")

    def test_rejects_external_redirects(self):
        import urllib.request
        redirect=m._NoRedirect()
        req=urllib.request.Request(m.PUBLIC + "/assets/main.js")
        redirected=redirect.redirect_request(req,None,302,"Found",{},'https://example.com/other.js')
        self.assertIsNone(redirected)

    def test_strict_fixed_hosts(self):
        self.assertEqual(m.ORIGIN, "http://10.62.91.2:18150")
        self.assertEqual(m.HOST, "1025-w1-preview.cloudiff.duckdns.org")
        self.assertEqual(m.PUBLIC, "https://1025-w1-preview.cloudiff.duckdns.org")

    def test_http_error_does_not_read_body(self):
        e = HTTPError("https://example.invalid", 403, "Forbidden", {"Content-Type": "text/plain"}, None)
        with unittest.mock.patch.object(m, "_urlopen_no_redirect", side_effect=e):
            result = m.request_once(m.PUBLIC, "/", origin=False)
        self.assertEqual(result["http"], 403)
        self.assertEqual(result["content_type"], "text/plain")

    def test_tls_verification_is_default(self):
        with unittest.mock.patch.object(m.ssl, "create_default_context", wraps=m.ssl.create_default_context) as verify:
            with unittest.mock.patch.object(m.urllib.request, "build_opener", side_effect=TimeoutError):
                m.request_once(m.PUBLIC, "/", origin=False)
        verify.assert_called_once()

if __name__ == "__main__":
    unittest.main()
