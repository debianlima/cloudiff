"""Strict, non-throwing validation of *synthetic* malformed service-user manifests.

No Komodo API call, credential, user creation or production permission mutation.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'scripts' / 'validate-pgh-komodo-service-user.py'
POLICY = ROOT / 'service-accounts' / 'komodo' / 'svc-pgh-cloudiff.json'
_spec = importlib.util.spec_from_file_location('pgh_komodo_manifest_validator', SOURCE)
validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator)


class KomodoManifestSchemaTypesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.valid = json.loads(POLICY.read_text(encoding='utf8'))

    def test_valid_manifest_remains_pending_without_activating_anything(self):
        self.assertEqual(validator.validate(deepcopy(self.valid)), [])
        self.assertEqual(self.valid['state'], 'PENDING_ADMIN_CREATION')
        self.assertIs(self.valid['verified_in_komodo'], False)
        self.assertIs(self.valid['release_authorized'], False)
        self.assertIs(self.valid['verified_credential_injection'], False)

    def test_previous_twenty_offline_policy_tests_still_pass(self):
        script = ROOT / 'scripts' / 'test-validate-pgh-komodo-service-user.py'
        completed = subprocess.run([sys.executable, str(script)], cwd=ROOT,
                                   text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, timeout=15)
        self.assertEqual(completed.returncode, 0,
                         'prior_manifest_tests_failed')
        self.assertIn('Ran 20 tests', completed.stderr + completed.stdout)


# Each malformed input becomes a separately addressable CI regression.
CASES = [
    ('scope_list', lambda d: d.update(target_scope=['Stack'])),
    ('scope_string', lambda d: d.update(target_scope='Stack')),
    ('auth_list', lambda d: d.update(agent_credential_model=['agent'])),
    ('auth_string', lambda d: d.update(agent_credential_model='agent')),
    ('checks_list', lambda d: d.update(activation_checks=['service_user_exists_in_komodo'])),
    ('checks_number', lambda d: d.update(activation_checks=1)),
    ('elevated_list', lambda d: d.update(elevated_operations=['NOT_AUTHORIZED'])),
    ('denied_privileges_dict', lambda d: d['target_scope'].update(
        denied_global_privileges={'admin': True})),
    ('denied_privileges_nested_list', lambda d: d['target_scope'].update(
        denied_global_privileges=[{'admin': True}])),
    ('agents_nested_list', lambda d: d['agent_credential_model'].update(
        agents=[{'code': 'infra-01'}])),
    ('agents_string', lambda d: d['agent_credential_model'].update(agents='infra-01')),
    ('activation_checks_null', lambda d: d.update(activation_checks=None)),
    ('target_scope_number', lambda d: d.update(target_scope=1)),
    ('unknown_root_field', lambda d: d.update(unapproved_field='SYNTHETIC_VALUE')),
    ('extra_nested_field', lambda d: d['target_scope'].update(
        unapproved_field='SYNTHETIC_VALUE')),
    ('bool_ttl', lambda d: d['agent_credential_model'].update(key_ttl_hours_max=True)),
    ('duplicate_agent_list', lambda d: d['agent_credential_model']['agents'].append('infra-01')),
]


def make_test(label, mutation):
    def test(self):
        candidate = deepcopy(self.valid)
        mutation(candidate)
        try:
            issues = validator.validate(candidate)
        except Exception as exc:
            self.fail('malformed_manifest_must_fail_closed_without_exception:'
                      + type(exc).__name__)
        self.assertTrue(isinstance(issues, list) and issues,
                        'malformed_manifest_accepted:' + label)
    return test


for _label, _mutation in CASES:
    setattr(KomodoManifestSchemaTypesTests, 'test_reject_' + _label,
            make_test(_label, _mutation))

if __name__ == '__main__':
    unittest.main()
