#!/usr/bin/env python3
"""Validate PGH Komodo service-user plan, never query Komodo or read credentials."""
import json,sys
from pathlib import Path
POLICY=Path(__file__).resolve().parent.parent/'service-accounts/komodo/svc-pgh-cloudiff.json'
EXPECTED_AGENTS={'infra-01','dev-01','dev-02','aud-01','doc-01','surface-01'}
DENY={'admin','super_admin','create_server_permissions','create_build_permissions','Terminal','Inspect','Server','GlobalWrite'}
REQUIRED_PROOFS={'service_user_exists_in_komodo','user_is_enabled_and_non_admin','read_only_stack_scope_confirmed','negative_other_stack_access_confirmed','api_key_created_by_authorized_admin_and_brokered','audit_provenance_confirmed','read_config_secret_sanitization_confirmed'}
# Fail closed on unexpected fields: the manifest is documentation, not a vault.
# This guards against accidental persistence of secret payloads or new grants.
ALLOWED_FIELDS = {
    'root': {'schema','identity','provider','kind','state','verified_in_komodo',
             'verified_credential_injection','requested_by','target_scope',
             'agent_credential_model','elevated_operations','activation_checks',
             'release_authorized'},
    'target_scope': {'type','name','base_level','specific_permissions',
                     'denied_global_privileges','other_resources_default',
                     'transparent_mode_must_be_false'},
    'agent_credential_model': {'sharing_one_api_secret_between_agents',
                               'one_key_per_agent','agents','secret_broker',
                               'secret_ref_pattern','plain_secret_in_pgh',
                               'plain_secret_in_git','key_ttl_hours_max',
                               'rotation','all_agent_keys_inherit_identical_user_permissions'},
    'elevated_operations': {'status','principle','stack','requires',
                            'no_automatic_role_escalation'},
    'activation_checks': REQUIRED_PROOFS,
}


def validate(d):
 errors=[]
 if not isinstance(d,dict):
  return ['invalid_manifest_type']
 for name,allowed in ALLOWED_FIELDS.items():
  obj=d if name=='root' else d.get(name)
  if not isinstance(obj,dict):
   errors.append('invalid_manifest_structure')
   continue
  if set(obj)-allowed:
   errors.append('unexpected_manifest_field')
 def required(test,code):
  if not test:errors.append(code)
 required(d.get('identity')=='svc-pgh-cloudiff','identity')
 required(d.get('kind')=='service_user','kind')
 required(d.get('state')=='PENDING_ADMIN_CREATION','not_pending')
 required(d.get('verified_in_komodo') is False,'unverified_flag')
 required(d.get('release_authorized') is False,'release_flag')
 required(d.get('verified_credential_injection') is False,'credential_injection_unverified')
 scope=d.get('target_scope') or {}
 required(scope.get('type')=='Stack' and scope.get('name')=='cloudif-agenda-unica','scope')
 required(scope.get('base_level')=='Read','elevated_access_for_shared_user')
 required(scope.get('other_resources_default')=='None','default_allow')
 required(scope.get('specific_permissions')==[],'dangerous_specific_permission')
 required(scope.get('transparent_mode_must_be_false') is True,'transparent_mode_assumption')
 required(DENY.issubset(set(scope.get('denied_global_privileges') or [])),'denylist')
 auth=d.get('agent_credential_model') or {}
 required(set(auth.get('agents') or [])==EXPECTED_AGENTS,'agent_scope')
 required(auth.get('sharing_one_api_secret_between_agents') is False,'shared_secret')
 required(auth.get('one_key_per_agent') is True,'per_agent_keys')
 required(auth.get('plain_secret_in_pgh') is False and auth.get('plain_secret_in_git') is False,'plaintext_secret')
 required(auth.get('secret_ref_pattern')=='komodo/cloudiff/svc-pgh-cloudiff/<agent-code>','secret_ref_pattern_drift')
 required(auth.get('secret_broker')=='OpenBao-or-institutional-secret-manager','secret_broker_drift')
 required(auth.get('all_agent_keys_inherit_identical_user_permissions') is True,'per_key_acl_false_assumption')
 required(isinstance(auth.get('key_ttl_hours_max'),int) and 0<auth['key_ttl_hours_max']<=24,'expiry')
 elevated=d.get('elevated_operations') or {}
 required(elevated.get('status')=='NOT_AUTHORIZED_BY_THIS_READ_IDENTITY','elevated_change_enabled')
 required(elevated.get('no_automatic_role_escalation') is True,'automatic_escalation')
 checks=d.get('activation_checks') or {}
 required(bool(checks) and all(v is False for v in checks.values()),'false_activation_claim')
 required(REQUIRED_PROOFS.issubset(checks),'missing_activation_proof')
 return sorted(set(errors))

def main():
 try:d=json.loads(POLICY.read_text())
 except (OSError,json.JSONDecodeError):
  print(json.dumps({'status':'BLOCKED_INVALID_MANIFEST'}));return 2
 issues=validate(d)
 print(json.dumps({'schema':'pgh/service-user-policy-validator/1','status':'PASS_PENDING_PLAN' if not issues else 'BLOCKED','issues':issues,'authenticated_to_komodo':False,'service_user_created':False,'credentials_processed':False},sort_keys=True))
 return 0 if not issues else 2
if __name__=='__main__':sys.exit(main())
