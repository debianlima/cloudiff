#!/usr/bin/env python3
"""Generate public, non-secret Komodo CreateServiceUser request locally.

Never authenticates to Komodo, never creates an account or key. Admin must first
check for an existing identity, use an authorized client and configure RBAC.
"""
import json,sys
from pathlib import Path

MANIFEST=Path(__file__).resolve().parent.parent/'service-accounts/komodo/svc-pgh-cloudiff.json'


def prepare(plan):
    if not isinstance(plan,dict):raise ValueError('INVALID_PLAN')
    if plan.get('state')!='PENDING_ADMIN_CREATION' or plan.get('verified_in_komodo') is not False:
        raise ValueError('NOT_PENDING')
    if plan.get('identity')!='svc-pgh-cloudiff' or plan.get('kind')!='service_user':
        raise ValueError('WRONG_IDENTITY')
    scope=plan.get('target_scope') or {}
    if scope.get('name')!='cloudif-agenda-unica' or scope.get('base_level')!='Read' or scope.get('other_resources_default')!='None':
        raise ValueError('INVALID_SCOPE')
    return {'method':'POST','path':'/write/CreateServiceUser',
            'body':{'username':'svc-pgh-cloudiff',
                    'description':'PGH CloudIFF — leitura auditada da stack Agenda; sem operacao de producao'},
            'warning':'ADMIN_ONLY_NOT_EXECUTED; verify existing user before POST; grant Stack Read separately; keys via broker',
            'account_created':False,'api_key_created':False,'credential_processed':False}


def main():
    try:
        from validate_pgh_komodo_service_user import validate
    except ImportError:
        import importlib.util
        p=Path(__file__).with_name('validate-pgh-komodo-service-user.py')
        spec=importlib.util.spec_from_file_location('policy',p)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        validate=m.validate
    try:
        plan=json.loads(MANIFEST.read_text())
        if validate(plan):raise ValueError('INVALID_POLICY')
        out=prepare(plan)
    except (OSError,json.JSONDecodeError,ValueError):
        print(json.dumps({'status':'BLOCKED_INVALID_PENDING_POLICY','account_created':False,'credential_processed':False}));return 2
    print(json.dumps(out,sort_keys=True,ensure_ascii=False))
    return 0
if __name__=='__main__':sys.exit(main())
