import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'docs/reconciliation/mcp-upload-wiring-candidate-v65.json'
GW=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
class McpUploadWiringCandidateEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.e=json.loads(E.read_text()); cls.gw=GW.read_text()
 def test_audit_branch_has_no_consumer_wiring(self):
  for p in ('18234','CLOUDIFF_MCP_UPLOAD','mcp-upload','mcp_upload'): self.assertNotIn(p,self.gw)
  self.assertEqual(self.e['audit_branch_consumer_reference_count'],0)
 def test_remote_search_has_no_candidate(self):
  self.assertEqual(self.e['remote_branch_count'],30)
  self.assertEqual(self.e['branches_with_consumer_wiring'],[])
  self.assertFalse(self.e['candidate_present'])
 def test_unit_is_blocked_not_auto_implemented(self):
  self.assertFalse(self.e['safe_to_execute_wiring'])
  self.assertTrue(self.e['conclusions']['t024_blocked_by_missing_migration_artifact'])
  self.assertFalse(self.e['conclusions']['integration_created_by_audit'])
 def test_restart_is_not_wiring(self):
  self.assertFalse(self.e['conclusions']['service_restart_is_wiring'])
  self.assertFalse(self.e['conclusions']['mcp_gateway_consumes_cpp_planner_in_any_remote_branch'])
if __name__=='__main__': unittest.main()
