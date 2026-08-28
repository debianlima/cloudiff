import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'docs/reconciliation/admin-observability-cpp-audit-v64.json'
CONTRACT=ROOT/'contratos/admin-observability.schema.json'
CPP=ROOT/'src/agent/admin_observability.cpp'
PATCH=ROOT/'compat/portal-admin-observability.patch'
class AdminObservabilityCppAuditEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.e=json.loads(E.read_text()); cls.c=json.loads(CONTRACT.read_text()); cls.cpp=CPP.read_text(); cls.patch=PATCH.read_text()
 def test_static_contract_and_portal_wiring(self):
  self.assertEqual(self.c['properties']['backend']['properties']['port']['const'],18260)
  self.assertIn('http://127.0.0.1:18260',self.patch)
  self.assertIn('/cloudiff/portal/api/admin-observability',self.patch)
  self.assertIn('/cloudiff/portal/api/node-recovery-policy',self.patch)
  self.assertIn('/cloudiff/portal/action/node-recovery',self.patch)
  self.assertIn('cloudif-tenants-admin',self.patch)
 def test_cpp_reads_environment_policy_and_separates_write_route(self):
  self.assertIn('GET',self.cpp); self.assertIn('/v1/environment',self.cpp)
  self.assertIn('/policy',self.cpp); self.assertIn('/recovery',self.cpp)
  self.assertIn("INSERT INTO cloudiff_v2.audit_log",self.cpp)
  self.assertIn("ROLLBACK",self.cpp)
 def test_network_lacuna_blocks_live_authority_claim(self):
  e=self.e
  self.assertTrue(e['network_observation']['labiff_route_present'])
  self.assertTrue(all(not v['icmp'] and not v['ssh'] for v in e['network_observation']['hosts'].values()))
  self.assertFalse(e['live_gate']['passed'])
  self.assertFalse(e['conclusions']['admin_observability_cpp_live_authority_proven'])
  self.assertFalse(e['conclusions']['safe_to_claim_live_authority'])
 def test_audit_remained_read_only(self):
  self.assertFalse(self.e['static_wiring']['recovery_post_executed_in_audit'])
  self.assertFalse(self.e['conclusions']['audit_changed_recovery_policy'])
  self.assertFalse(self.e['conclusions']['frozen_portal_visual_change'])
if __name__=='__main__': unittest.main()
