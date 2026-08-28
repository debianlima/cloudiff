import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'docs/reconciliation/admin-observability-cpp-live-v67.json'
CPP=ROOT/'src/agent/admin_observability.cpp'
PATCH=ROOT/'compat/portal-admin-observability.patch'
class AdminObservabilityCppLiveEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.e=json.loads(E.read_text()); cls.cpp=CPP.read_text(); cls.patch=PATCH.read_text()
 def test_live_identity_and_consumer_path(self):
  e=self.e
  self.assertTrue(e['live']['service_active'])
  self.assertEqual(e['live']['bind'],'127.0.0.1:18260')
  self.assertEqual(e['live']['version'],'0.34.0-shadow')
  self.assertEqual(e['auth_and_consumer_proof']['portal_admin_environment_http'],200)
  self.assertEqual(e['auth_and_consumer_proof']['portal_admin_policy_http'],200)
  self.assertTrue(e['auth_and_consumer_proof']['portal_to_cpp_consumption_observed'])
  self.assertIn('http://127.0.0.1:18260',self.patch)
 def test_auth_boundary_is_observed(self):
  a=self.e['auth_and_consumer_proof']
  self.assertEqual(a['backend_unauthenticated_environment_http'],401)
  self.assertEqual(a['portal_non_admin_environment_http'],403)
  self.assertEqual(a['portal_admin_group'],'CloudIF-Tenants-Admin')
 def test_gets_are_read_only_and_recovery_post_was_not_used(self):
  d=self.e['read_only_delta']
  self.assertEqual(d['before'],d['after'])
  self.assertTrue(d['desired_state_unchanged'])
  self.assertTrue(d['recovery_audit_unchanged'])
  self.assertFalse(self.e['recovery_post_executed'])
  self.assertTrue(self.e['scope']['readonly_observability_authority_proven'])
  self.assertFalse(self.e['scope']['recovery_write_effect_proven'])
 def test_provenance_and_authority_are_not_overclaimed(self):
  p=self.e['provenance']; c=self.e['conclusions']
  self.assertFalse(p['release_manifest_present'])
  self.assertFalse(p['live_version_present_in_remote_cpp_history'])
  self.assertEqual(p['exact_source_commit'],'NAO DECLARADO')
  self.assertFalse(p['source_commit_attribution_proven'])
  self.assertTrue(c['safe_to_claim_readonly_authority'])
  self.assertFalse(c['safe_to_claim_recovery_effect_parity'])
  self.assertFalse(c['provenance_gate_passed_for_exact_source_commit'])
if __name__=='__main__': unittest.main()
