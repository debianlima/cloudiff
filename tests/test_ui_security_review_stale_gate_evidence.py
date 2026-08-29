import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'docs/reconciliation/ui-security-review-stale-gate-v70.json'
GATE=ROOT/'components/control-plane/srv/cloudif/tests/cloudif-ui-security-tests.py'
CONTRACT=ROOT/'portal/tests/test_ui_security_gate_contract.py'
class UISecurityReviewStaleGateEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.e=json.loads(E.read_text()); cls.gate=GATE.read_text(); cls.contract=CONTRACT.read_text()
 def test_current_failure_is_five_ui_marker_assertions(self):
  r=self.e['current_report']
  self.assertEqual(r['tests'],20)
  self.assertEqual(r['failures'],5)
  self.assertEqual(r['failed_checks'],['novo_layout','hero_professor','chip_professor','admin_visivel_admin','chip_admin'])
  self.assertTrue(r['ui_test_exit_short_circuits_remaining_gate'])
  self.assertFalse(r['full_secure_release_gate_passed_in_current_execution'])
 def test_security_headers_are_not_overclaimed_as_failed(self):
  d=self.e['diagnosis']; r=self.e['current_report']
  self.assertFalse(d['security_header_regression_proven'])
  self.assertFalse(d['live_portal_http_failure_proven'])
  self.assertGreaterEqual(len(r['passed_security_header_checks']),9)
  self.assertTrue(d['stale_ui_marker_contract_proven'])
 def test_repository_contract_itself_pins_obsolete_markers(self):
  a=self.e['repository_alignment']
  self.assertTrue(a['live_and_repository_gate_identical'])
  self.assertTrue(a['contract_test_requires_obsolete_markers'])
  self.assertTrue(a['static_suite_can_pass_while_periodic_live_gate_fails'])
  self.assertIn('<nav class=\\"nav\\"',self.contract)
  self.assertIn("self.assertNotIn('portal-hero',gate)",self.contract)
  self.assertIn("self.assertNotIn('profile-chip teacher',gate)",self.contract)
  self.assertIn("ok('novo_layout','<nav class=\"nav\"' in prof",self.gate)
 def test_no_restart_or_visual_mutation_and_followup_is_blocked(self):
  self.assertFalse(self.e['mutation_performed'])
  self.assertFalse(self.e['service_restart_performed'])
  self.assertFalse(self.e['diagnosis']['frozen_portal_visual_change_by_this_unit'])
  self.assertEqual(self.e['follow_up']['state'],'BLOCKED')
  self.assertTrue(self.e['follow_up']['requires_human_authorization'])
  self.assertFalse(self.e['timeline']['portal_restart_proven_as_root_cause'])
if __name__=='__main__': unittest.main()
