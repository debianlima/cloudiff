from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class TenantProxyLifecycleContractTest(unittest.TestCase):
    def test_router_exposes_exact_tenant_readiness_only_for_mapped_tenant(self):
        source = (ROOT / "components/control-plane/srv/cloudif/bin/cloudif-render-router-sso.sh").read_text()
        self.assertIn("location = /cloudiff/tenant-readiness", source)
        self.assertIn('if ($cloudif_kong_port = "") { return 404; }', source)
        self.assertIn("X-CloudIF-Tenant $cloudif_effective_tenant", source)
        self.assertIn('return 200 "$cloudif_effective_tenant', source)

    def test_certificate_helper_rejects_tenant_missing_from_registry_before_publishing(self):
        script = ROOT / "components/control-plane/srv/cloudif/bin/cloudif-ensure-tenant-certificate.sh"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / "tenants.csv"
            registry.write_text("tenant,kong_http_port\nakadmin,8102\n")
            tenant_root = root / "tenants"
            tenant_root.mkdir()
            env = os.environ.copy()
            env.update({
                "CLOUDIF_TENANT_REGISTRY": str(registry),
                "CLOUDIF_TENANT_ROOT": str(tenant_root),
                "CLOUDIF_NPM_PUBLISHER_ENV": str(root / "missing.env"),
            })
            run = subprocess.run([str(script), "iff0001-teste"], env=env, text=True, capture_output=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("Tenant não registrado", run.stderr)
            self.assertNotIn("NPM publisher token ausente", run.stderr)

    def test_publisher_supports_idempotent_tenant_route_removal(self):
        for relative in (
            "components/proxy/current-apps/publisher-agent-current/cloudif-npm-publisher-agent.py",
            "components/proxy/usr/local/sbin/cloudif-npm-publisher-agent.py",
        ):
            source = (ROOT / relative).read_text()
            self.assertIn("def remove_tenant(payload):", source)
            self.assertIn("state.setdefault('tenants',{}).pop(tenant,None)", source)
            self.assertIn("self.path=='/tenant/delete'", source)
            self.assertIn("'certificate_preserved'", source)

    def test_tenant_deletion_removes_public_proxy_route(self):
        source = (ROOT / "components/control-plane/srv/cloudif/lib/cloudif_admin_tenant_delete.py").read_text()
        for marker in (
            "def _remove_proxy_tenant",
            "http://10.62.91.3/tenant/delete",
            '"proxy_cleanup": proxy_cleanup',
            "Rota pública e rotas internas removidas",
        ):
            self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
