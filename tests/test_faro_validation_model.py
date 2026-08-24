#!/usr/bin/env python3
from pathlib import Path
import json,re
import jsonschema
root=Path(__file__).resolve().parents[1]
schema=json.load(open(root/'contratos/faro-validation.schema.json'));jsonschema.Draft202012Validator.check_schema(schema)
files=sorted((root/'config').glob('faro-validation-*.json'));assert len(files)==6
expected=['discovery','identity-network','pki-nats','agent-heartbeat','reconciliation-resilience','acceptance']
seen=[]; req_ids=[]; task_ids=[]
for p in files:
    x=json.load(open(p));jsonschema.validate(x,schema);seen.append(x['stage']);assert x['verification_status']=='not_verified'
    req_ids.extend(r['id'] for r in x['requirements']);task_ids.extend(t['id'] for t in x['tasks'])
assert seen==expected;assert len(req_ids)==len(set(req_ids))==21;assert len(task_ids)==len(set(task_ids))==19
first=json.load(open(files[0]));d={x['name']:x for x in first['decisions']};assert d['role']['status']=='unresolved' and d['capabilities']['status']=='unresolved';assert d['network_address']['status']=='fixed' and d['network_address']['allowed_values']==['10.62.91.5']
agent=json.load(open(files[3]));assert any(x['name']=='bootstrap_method' and x['status']=='fixed' and x['allowed_values'][0].startswith('SSH') for x in agent['decisions'])
for p in files:
    text=p.read_text().lower();assert not re.search(r'(password|secret|private_key|token)\s*[:=]\s*["\'][^"\']+["\']',text)
# Chain must be linear and explicit.
for i,p in enumerate(files):
    x=json.load(open(p));expected_dep=[] if i==0 else [expected[i-1]];assert x['depends_on']==expected_dep
# Existing contract anchors must still exist.
node=json.load(open(root/'contratos/node.schema.json'));assert set(node['properties']['role']['enum'])=={'control','forja','edge','other'}
nats=json.load(open(root/'contratos/nats-security.schema.json'));assert nats['properties']['shared_token_allowed']['const'] is False;assert nats['properties']['agent_subscribe_allowed']['const'] is False
rec=json.load(open(root/'contratos/reconciliation.schema.json'));assert set(rec['properties']['decision']['enum'])=={'noop','reconcile','blocked','degraded','failed'}
print('FARO_VALIDATION_MODEL=PASS')
