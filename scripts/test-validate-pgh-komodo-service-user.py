#!/usr/bin/env python3
import copy,importlib.util,json,unittest
from pathlib import Path
p=Path(__file__).with_name('validate-pgh-komodo-service-user.py')
spec=importlib.util.spec_from_file_location('pgh_policy',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
BASE=json.loads(m.POLICY.read_text())
class PolicyTests(unittest.TestCase):
 def test_valid_pending_plan(self):self.assertEqual(m.validate(copy.deepcopy(BASE)),[])
 def test_rejects_claim_account_created(self):
  a=copy.deepcopy(BASE);a['verified_in_komodo']=True;self.assertIn('unverified_flag',m.validate(a))
 def test_rejects_admin_read_user(self):
  a=copy.deepcopy(BASE);a['target_scope']['base_level']='Write';self.assertIn('elevated_access_for_shared_user',m.validate(a))
 def test_rejects_all_resources(self):
  a=copy.deepcopy(BASE);a['target_scope']['other_resources_default']='Read';self.assertIn('default_allow',m.validate(a))
 def test_rejects_terminal(self):
  a=copy.deepcopy(BASE);a['target_scope']['specific_permissions']=['Terminal'];self.assertIn('dangerous_specific_permission',m.validate(a))
 def test_rejects_secret_sharing(self):
  a=copy.deepcopy(BASE);a['agent_credential_model']['sharing_one_api_secret_between_agents']=True;self.assertIn('shared_secret',m.validate(a))
 def test_rejects_long_lived_key(self):
  a=copy.deepcopy(BASE);a['agent_credential_model']['key_ttl_hours_max']=365*24;self.assertIn('expiry',m.validate(a))
 def test_rejects_fake_activation(self):
  a=copy.deepcopy(BASE);a['activation_checks']['service_user_exists_in_komodo']=True;self.assertIn('false_activation_claim',m.validate(a))
 def test_rejects_escalation(self):
  a=copy.deepcopy(BASE);a['elevated_operations']['status']='ACTIVE';self.assertIn('elevated_change_enabled',m.validate(a))
 def test_rejects_credential_injection_claim(self):
  a=copy.deepcopy(BASE);a['verified_credential_injection']=True;self.assertIn('credential_injection_unverified',m.validate(a))
 def test_rejects_missing_secret_reference_contract(self):
  a=copy.deepcopy(BASE);a['agent_credential_model']['secret_ref_pattern']='wrong-path';self.assertIn('secret_ref_pattern_drift',m.validate(a))
 def test_rejects_wrong_broker(self):
  a=copy.deepcopy(BASE);a['agent_credential_model']['secret_broker']='inline-key';self.assertIn('secret_broker_drift',m.validate(a))
 def test_rejects_missing_activation_proof(self):
  a=copy.deepcopy(BASE);del a['activation_checks']['read_config_secret_sanitization_confirmed'];self.assertIn('missing_activation_proof',m.validate(a))
 def test_rejects_claim_sanitization_without_live_evidence(self):
  a=copy.deepcopy(BASE);a['activation_checks']['read_config_secret_sanitization_confirmed']=True;self.assertIn('false_activation_claim',m.validate(a))
 def test_rejects_missing_agent(self):
  a=copy.deepcopy(BASE);a['agent_credential_model']['agents'].remove('aud-01');self.assertIn('agent_scope',m.validate(a))
 def test_rejects_unexpected_top_level_api_key(self):
  a=copy.deepcopy(BASE);a['api_key']='SYNTHETIC_NOT_REAL'
  self.assertIn('unexpected_manifest_field',m.validate(a))
 def test_rejects_nested_token_payload(self):
  a=copy.deepcopy(BASE);a['agent_credential_model']['api_token']='SYNTHETIC_NOT_REAL'
  self.assertIn('unexpected_manifest_field',m.validate(a))
 def test_rejects_unapproved_activation_proof_field(self):
  a=copy.deepcopy(BASE);a['activation_checks']['admin_override']=False
  self.assertIn('unexpected_manifest_field',m.validate(a))
 def test_rejects_extra_stack_grant_field(self):
  a=copy.deepcopy(BASE);a['target_scope']['force_global_write']=False
  self.assertIn('unexpected_manifest_field',m.validate(a))
 def test_rejects_non_object_manifest(self):
  self.assertIn('invalid_manifest_type',m.validate([]))
if __name__=='__main__':unittest.main(verbosity=1)
