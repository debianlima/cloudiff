from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class TenantHttpsEntryContractTest(unittest.TestCase):
    def test_active_tenant_root_opens_studio(self):
        source = (
            ROOT
            / "components/control-plane/srv/cloudif/bin/cloudif-apply-router-authz-v233.sh"
        ).read_text()
        block = source[
            source.index("# CloudIF v250: tenant ativo") :
            source.index("authz_locations = authz_locations + root_redirect_v250")
        ]
        self.assertIn('if ($cloudif_kong_port != "") { return 302 /project/default; }', block)
        self.assertIn("return 302 /cloudiff/portal/;", block)
        self.assertNotIn("location = / {\n        return 302 /cloudiff/portal/;", block)

    def test_tenant_certificates_use_rsa_and_x1_chain(self):
        for relative in (
            "components/proxy/current-apps/publisher-agent-current/cloudif-npm-publisher-agent.py",
            "components/proxy/usr/local/sbin/cloudif-npm-publisher-agent.py",
        ):
            source = (ROOT / relative).read_text()
            for marker in (
                "def cert_uses_rsa(name):",
                "'--key-type','rsa'",
                "'--rsa-key-size','2048'",
                "'--preferred-chain','ISRG Root X1'",
                "certificate_key_type_mismatch",
            ):
                self.assertIn(marker, source)
            self.assertIn(
                "cert_exists(name) and cert_covers(name,domains) and cert_uses_rsa(name)",
                source,
            )

    def test_tenant_proxy_enforces_secure_content(self):
        for relative in (
            "components/proxy/current-apps/publisher-agent-current/cloudif-npm-publisher-agent.py",
            "components/proxy/usr/local/sbin/cloudif-npm-publisher-agent.py",
        ):
            source = (ROOT / relative).read_text()
            tenant_start = source.index("for tenant,v in sorted(state.get('tenants',{}).items()):")
            project_start = source.index("for num_s,p in sorted(state.get('projects',{}).items()", tenant_start)
            tenant_block = source[tenant_start:project_start]
            for marker in (
                'add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;',
                "add_header X-Content-Type-Options nosniff always;",
                "add_header Referrer-Policy strict-origin-when-cross-origin always;",
                'add_header Content-Security-Policy "upgrade-insecure-requests; block-all-mixed-content" always;',
                "proxy_set_header X-Forwarded-Proto https;",
            ):
                self.assertIn(marker, tenant_block)


if __name__ == "__main__":
    unittest.main()
