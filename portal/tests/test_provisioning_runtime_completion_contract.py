from pathlib import Path
import unittest


class ProvisioningRuntimeCompletionContractTest(unittest.TestCase):
    def test_router_authz_does_not_parse_css_as_f_string(self):
        source = Path('components/control-plane/srv/cloudif/bin/cloudif-apply-router-authz-v233.sh').read_text(encoding='utf-8')
        self.assertIn("authz_locations = '''", source)
        self.assertIn(".replace('__AUTHZ_UPSTREAM__', authz_upstream)", source)
        self.assertNotIn("authz_locations = f'''", source)

    def test_supabase_requires_runtime_health_and_certificate(self):
        source = Path('components/control-plane/srv/cloudif/lib/cloudif_project_provision_real.py').read_text(encoding='utf-8')
        self.assertIn('cloudif-auto-ensure-supabase-tenant.sh', source)
        self.assertIn('cloudif_supabase_wait_until_ready', source)
        self.assertIn('cloudif-ensure-tenant-certificate.sh', source)
        self.assertIn('tenant_runtime_error', source)

    def test_certificate_step_verifies_public_tls_instead_of_internal_http_only(self):
        source = Path('components/control-plane/srv/cloudif/bin/cloudif-ensure-tenant-certificate.sh').read_text(encoding='utf-8')
        self.assertIn('https://${HOST}/project/default', source)
        self.assertIn('tls_verified', source)
        self.assertIn('route_verified', source)
        self.assertIn('CLOUDIF_TENANT_CERTIFICATE_WAIT_SECONDS', source)
        self.assertIn("--write-out '%{http_code}'", source)
        self.assertIn('2??|3??|401|403', source)
        self.assertNotIn('curl -k', source)
        self.assertIn('exit 1', source)

    def test_tenant_library_uses_the_same_public_hostname(self):
        source = Path('components/control-plane/srv/cloudif/lib/cloudif-supabase.sh').read_text(encoding='utf-8')
        self.assertIn('https://${TENANT}.$(cloudif_supabase_domain)/project/default', source)

    def test_initial_publication_retries_transient_deploys(self):
        source = Path('components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py').read_text(encoding='utf-8')
        self.assertIn('deploy_retries=0', source)
        self.assertIn('Repetindo o deploy após falha transitória do registry.', source)
        self.assertIn('deploy_retries < 2', source)


if __name__ == '__main__':
    unittest.main()
