import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'docs/reconciliation/project-onboarding-urllerror-v69.json'
ONBOARD=ROOT/'components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py'
UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-supabase-release-agent.service'
class ProjectOnboardingUrlErrorEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.e=json.loads(E.read_text()); cls.code=ONBOARD.read_text(); cls.unit=UNIT.read_text()
 def test_root_cause_is_pinned_to_namespace_path(self):
  r=self.e['root_cause']
  self.assertEqual(r['systemd_result'],'226/NAMESPACE')
  self.assertTrue(r['required_path_missing_before_recovery'])
  self.assertFalse(r['python_exec_reached_during_failure'])
  self.assertIn('/srv/cloudif/managed-backups/releases',self.unit)
  self.assertIn('ReadWritePaths=',self.unit)
 def test_last_failed_cycle_excludes_forja_and_komodo(self):
  f=self.e['observed_failure']
  self.assertEqual(f['forja_ensure_repo_http_during_failed_cycle'],[200,200])
  self.assertEqual(f['komodo_project_ensure_http_during_failed_cycle'],[200,200])
  self.assertTrue(f['forja_and_komodo_excluded_as_failed_upstream_for_last_cycle'])
  self.assertLess(self.code.index("'/komodo/project/ensure'"), self.code.index("'/supabase/release/inspect'"))
 def test_recovery_timeline_and_current_health(self):
  c=self.e['concurrent_recovery']; s=self.e['current_state']
  self.assertFalse(c['performed_by_this_unit'])
  self.assertEqual(c['onboarding_first_success_utc'],'2026-08-29T01:04:51Z')
  self.assertTrue(c['temporal_correlation_with_root_cause'])
  self.assertEqual(s['supabase_release_agent_health_http'],200)
  self.assertEqual(s['onboarding_health_http'],200)
  self.assertEqual(s['onboarding_ready'],2)
 def test_no_effect_or_historical_overclaim(self):
  c=self.e['conclusions']
  self.assertTrue(c['exact_current_root_cause_proven'])
  self.assertTrue(c['onboarding_issue_currently_resolved'])
  self.assertFalse(c['repair_attributed_to_this_unit'])
  self.assertFalse(c['manual_reconcile_triggered_by_this_unit'])
  self.assertFalse(c['historical_august_5_7_membership_deadletters_reclassified'])
if __name__=='__main__': unittest.main()
