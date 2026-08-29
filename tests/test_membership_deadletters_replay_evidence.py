import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'docs/reconciliation/membership-deadletters-replay-v68.json'
class MembershipDeadlettersReplayEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.e=json.loads(E.read_text())
 def test_human_authorized_replay_preserves_history(self):
  self.assertTrue(self.e['human_authorization']['replay_two_membership_events'])
  self.assertTrue(all(x['preserved'] for x in self.e['original_deadletters']))
  self.assertTrue(self.e['conclusions']['deadletters_mutated_in_place'] is False)
  self.assertEqual(self.e['final_state']['original_deadletters_preserved'],2)
  self.assertEqual(self.e['final_state']['failed_replay_deadletters_preserved'],2)
 def test_root_cause_and_minimal_fix_are_pinned(self):
  r=self.e['root_cause']; f=self.e['fix']
  self.assertEqual(r['error_type'],'NameError')
  self.assertEqual(r['error_message'],"name 'safe_slug' is not defined")
  self.assertEqual(f['change'],'safe_slug(...) -> _v118_slug(...)')
  self.assertTrue(f['defined_helper_preexists'])
  self.assertTrue(f['live_release_derived_from_live_base'])
  self.assertFalse(f['whole_repository_file_deployed'])
  self.assertEqual(f['service_health_after_restart_http'],200)
 def test_second_generation_succeeds_idempotently(self):
  rows=self.e['successful_replay_generation']
  self.assertEqual(len(rows),2)
  for x in rows:
   self.assertEqual(x['status'],'ready')
   self.assertEqual(x['attempts'],1)
   self.assertTrue(x['forgejo_ok'] and x['komodo_ok'] and x['tenant_access_ok'])
   self.assertEqual(x['forgejo_added'],[])
   self.assertEqual(x['forgejo_removed'],[])
   self.assertEqual(x['terminals_created'],[])
   self.assertFalse(x['onboarding_ok'])
  self.assertEqual(self.e['final_state']['successful_replays_ready'],2)
  self.assertTrue(self.e['final_state']['membership_effects_idempotent_in_observed_replay'])
 def test_onboarding_is_not_overclaimed(self):
  self.assertTrue(self.e['final_state']['onboarding_issue_separate'])
  self.assertEqual(self.e['final_state']['onboarding_follow_up'],'T-031')
  self.assertFalse(self.e['conclusions']['onboarding_declared_fixed'])
if __name__=='__main__': unittest.main()
