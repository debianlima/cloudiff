import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'docs/reconciliation/membership-deadletters-readonly-v66.json'
WORKER=ROOT/'components/control-plane/current-apps/reconcile-worker-current/cloudif-reconcile-worker.py'
class MembershipDeadlettersReadonlyEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.e=json.loads(E.read_text()); cls.worker=WORKER.read_text()
 def test_worker_contract_matches_evidence(self):
  self.assertIn("ok=bool(forgejo.get('ok') and komodo.get('ok') and tenant_result.get('ok'))",self.worker)
  self.assertIn("{'error_type':etype,'secrets_exposed':False}",self.worker)
  self.assertFalse(self.e['worker_contract']['onboarding_result_participates_in_membership_ok'])
  self.assertTrue(self.e['worker_contract']['deadletter_result_persists_only_error_type'])
 def test_both_historical_rows_are_preserved_without_replay(self):
  self.assertEqual(len(self.e['deadletters']),2)
  self.assertTrue(all(x['attempts']==5 for x in self.e['deadletters']))
  self.assertTrue(all(not x['historical_error_detail_preserved'] for x in self.e['deadletters']))
  self.assertFalse(self.e['queue_replay_performed'])
  self.assertFalse(self.e['mutation_performed'])
 def test_current_membership_is_converged(self):
  for x in self.e['deadletters']:
   self.assertEqual(x['current_nonterminal_queue_items'],0)
   self.assertTrue(x['forgejo_repo_exists'])
   self.assertTrue(x['forgejo_owner_matches'])
   self.assertEqual(x['forgejo_collaborators'],[])
   self.assertTrue(x['komodo_owner_terminal_present'])
   self.assertEqual(x['komodo_integration_status'],'ready')
   self.assertEqual(x['tenant_access_users'],[x['owner']])
  self.assertTrue(self.e['historical_reconstruction']['current_membership_state_converged'])
  self.assertFalse(self.e['historical_reconstruction']['current_drift_observed'])
 def test_no_root_cause_or_replay_overclaim(self):
  self.assertFalse(self.e['historical_reconstruction']['exact_root_cause_proven'])
  self.assertFalse(self.e['replay_decision']['technically_required_now'])
  self.assertFalse(self.e['replay_decision']['safe_to_replay_without_separate_authorization'])
  self.assertFalse(self.e['conclusions']['historical_exact_cause_declared'])
  self.assertFalse(self.e['conclusions']['replay_recommended'])
  self.assertTrue(self.e['conclusions']['onboarding_issue_is_separate'])
if __name__=='__main__': unittest.main()
