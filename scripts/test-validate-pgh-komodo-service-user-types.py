"""Security regressions for malformed Komodo service user manifest types.
17 tests: reject malformed inputs without exceptions; all data are synthetic.
No Komodo API calls, secrets or production changes.
"""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'scripts/validate-pgh-komodo-service-user.py'
BASE=json.loads((ROOT/'service-accounts/komodo/svc-pgh-cloudiff.json').read_text())
spec=importlib.util.spec_from_file_location('pgh_komodo_svc_validator',SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

MUTATIONS={
 'scope_list':lambda d:d.update(target_scope=['Stack']),
 'scope_string':lambda d:d.update(target_scope='Stack'),
 'auth_list':lambda d:d.update(agent_credential_model=['agent']),
 'auth_string':lambda d:d.update(agent_credential_model='agent'),
 'checks_list':lambda d:d.update(activation_checks=['service_user_exists_in_komodo']),
 'checks_number':lambda d:d.update(activation_checks=1),
 'elevated_list':lambda d:d.update(elevated_operations=['NOT_AUTHORIZED']),
 'denied_privileges_dict':lambda d:d['target_scope'].update(denied_global_privileges={'admin':True}),
 'denied_privileges_nested_list':lambda d:d['target_scope'].update(denied_global_privileges=[{'admin':True}]),
 'agents_nested_list':lambda d:d['agent_credential_model'].update(agents=[{'code':'infra-01'}]),
 'agents_string':lambda d:d['agent_credential_model'].update(agents='infra-01'),
 'activation_checks_null':lambda d:d.update(activation_checks=None),
 'target_scope_number':lambda d:d.update(target_scope=1),
 'unknown_root_field':lambda d:d.update(unapproved_field='SYNTHETIC_VALUE'),
 'extra_nested_field':lambda d:d['target_scope'].update(unapproved_field='SYNTHETIC_VALUE'),
 'bool_ttl':lambda d:d['agent_credential_model'].update(key_ttl_hours_max=True),
 'duplicate_agent_list':lambda d:d['agent_credential_model']['agents'].append('infra-01'),
}
class FailClosedManifestTypes(unittest.TestCase):
 pass

def case(mutate):
 def test(self):
  obj=copy.deepcopy(BASE)
  mutate(obj)
  result=m.validate(obj)  # Any exception is a test failure.
  self.assertIsInstance(result,list)
  self.assertTrue(result,'malformed manifest was accepted')
 return test

for name,mutation in MUTATIONS.items():
 setattr(FailClosedManifestTypes,'test_'+name,case(mutation))

if __name__=='__main__':
 unittest.main(verbosity=1)

