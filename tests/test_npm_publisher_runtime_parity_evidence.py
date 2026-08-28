import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/reconciliation/npm-publisher-runtime-parity-v57.json"
CONTRACT = ROOT / "contratos/npm-publisher.schema.json"
PROVIDER = ROOT / "src/agent/npm_publisher_provider.cpp"
PORTAL = ROOT / "components/control-plane/current-apps/portal-current/cloudif_portal_publications.py"
PROJECT_DELETE = ROOT / "components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py"
TENANT_DELETE = ROOT / "components/control-plane/srv/cloudif/lib/cloudif_admin_tenant_delete.py"
CONTROL = ROOT / "src/control/main.cpp"
AGENT = ROOT / "src/agent/main.cpp"


class NpmPublisherRuntimeParityEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.provider = PROVIDER.read_text(encoding="utf-8")
        cls.portal = PORTAL.read_text(encoding="utf-8")
        cls.project_delete = PROJECT_DELETE.read_text(encoding="utf-8")
        cls.tenant_delete = TENANT_DELETE.read_text(encoding="utf-8")
        cls.control = CONTROL.read_text(encoding="utf-8")
        cls.agent = AGENT.read_text(encoding="utf-8")

    def test_portal_routes_exist_in_contract_and_cpp_provider(self):
        routes = set(self.contract["properties"]["routes"]["items"]["enum"])
        required = {
            "GET /health", "POST /publish", "POST /version", "POST /stage",
            "POST /alias", "POST /unpublish", "POST /tenant", "POST /tenant/delete",
        }
        self.assertEqual(routes, required)
        for route in required:
            method, path = route.split(" ", 1)
            if method == "POST":
                self.assertIn(f'path=="{path}"', self.provider, route)
        self.assertIn('path=="/health"', self.provider)
        for path in ("/stage", "/publish", "/alias"):
            self.assertIn("10.62.91.3" + path, self.portal)
        self.assertIn("10.62.91.3/unpublish", self.project_delete)
        self.assertIn("10.62.91.3/tenant/delete", self.tenant_delete)

    def test_observed_ingress_and_runtime_negative_effects_match(self):
        e = self.evidence
        self.assertEqual(e["schema_version"], 1)
        self.assertEqual(e["consumer_ingress"]["source"], "10.62.92.7")
        self.assertEqual(e["consumer_ingress"]["host_header"], "cloudif-publisher.internal")
        self.assertEqual(e["consumer_ingress"]["health"]["status"], 200)
        self.assertEqual(e["consumer_ingress"]["invalid_token_stage"]["status"], 403)
        for name in ("shadow", "live"):
            runtime = e["runtime"][name]
            self.assertEqual(runtime["health"]["status"], 200)
            self.assertEqual(runtime["invalid_token_stage"]["status"], 403)
            self.assertEqual(runtime["valid_token_invalid_stage"]["status"], 422)
            self.assertEqual(runtime["valid_token_invalid_stage"]["error"], "ValueError")
            self.assertEqual(runtime["valid_token_invalid_stage"]["detail"], "invalid_stage")
            self.assertTrue(runtime["valid_token_invalid_stage"]["state_unchanged"])
            self.assertTrue(runtime["valid_token_invalid_stage"]["nginx_conf_unchanged"])

    def test_evidence_does_not_overclaim_current_source_or_project_reconciliation(self):
        e = self.evidence
        self.assertEqual(e["runtime"]["live"]["binary_version"], "0.10.0-shadow")
        self.assertIn('0.36.0-shadow', self.agent)
        self.assertEqual(e["source_snapshot"]["repo_agent_version"], "0.36.0-shadow")
        self.assertEqual(e["source_snapshot"]["live_source_commit"], "NAO DECLARADO")
        self.assertFalse(e["conclusions"]["current_repo_binary_is_live"])
        self.assertFalse(e["conclusions"]["project_reconciliation_cpp_migrated"])
        self.assertIn('cloudiff.v2.node.observed', self.control)
        self.assertNotIn('project.created', self.control)
        self.assertNotIn('project.membership.changed', self.control)

    def test_host_capacity_blocks_new_npm_deploy(self):
        host = self.evidence["provider_host"]
        self.assertEqual(host["verifier"]["errors"], 1)
        self.assertEqual(host["verifier"]["root_filesystem_percent"], 91)
        self.assertFalse(host["new_deploy_allowed"])


if __name__ == "__main__":
    unittest.main()
