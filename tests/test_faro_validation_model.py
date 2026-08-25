#!/usr/bin/env python3
from pathlib import Path
import json,re
import jsonschema
root=Path(__file__).resolve().parents[1]
schema=json.load(open(root/'contratos/faro-validation.schema.json'));jsonschema.Draft202012Validator.check_schema(schema)
files=sorted((root/'config').glob('faro-validation-*.json'));assert len(files)==6
expected=['discovery','identity-network','pki-nats','agent-heartbeat','reconciliation-resilience','acceptance']
expected_status=['verified','verified','verified','verified','verified','partially_verified']
seen=[];req_ids=[];task_ids=[]
for i,p in enumerate(files):
 x=json.load(open(p));jsonschema.validate(x,schema);seen.append(x['stage']);assert x['version']==2;assert x['verification_status']==expected_status[i]
 req_ids.extend(r['id'] for r in x['requirements']);task_ids.extend(t['id'] for t in x['tasks'])
assert seen==expected;assert len(req_ids)==len(set(req_ids))==21;assert len(task_ids)==len(set(task_ids))==19
first=json.load(open(files[0]));d={x['name']:x for x in first['decisions']};assert d['role']['status']=='fixed' and d['role']['allowed_values']==['edge'];assert d['capabilities']['status']=='derived' and 'agent-auto-update' in d['capabilities']['allowed_values'];assert 'portal-host' not in d['capabilities']['allowed_values'];assert d['network_address']['status']=='fixed' and d['network_address']['allowed_values']==['10.62.91.5'];assert d['form_factor']['status']=='fixed'
agent=json.load(open(files[3]));assert any(x['name']=='bootstrap_method' and x['status']=='fixed' and x['allowed_values'][0].startswith('SSH') for x in agent['decisions'])
rec_stage=json.load(open(files[4]));r14=next(r for r in rec_stage['requirements'] if r['id']=='FARO-R14');assert 'cloudiff-reconcile v42' in r14['evidence'];assert next(t for t in rec_stage['tasks'] if t['id']=='FARO-T13')['gate']=='passed:cloudiff-reconcile-v42-noop-reconcile'
for p in files:
 text=p.read_text().lower();assert not re.search(r'(password|secret|private_key|token)\s*[:=]\s*["\'][^"\']+["\']',text)
for i,p in enumerate(files):
 x=json.load(open(p));assert x['depends_on']==([] if i==0 else [expected[i-1]])
node=json.load(open(root/'contratos/node.schema.json'));assert set(node['properties']['role']['enum'])=={'control','forja','edge','other'}
nats=json.load(open(root/'contratos/nats-security.schema.json'));assert nats['properties']['shared_token_allowed']['const'] is False;assert nats['properties']['agent_subscribe_allowed']['const'] is False;assert nats['properties']['agent_server_trust_source']['const']=='system-ca-plus-expected-hostname';assert nats['properties']['server_certificate_distribution_scope']['const']=='nats-server-host-only';assert nats['properties']['agent_may_receive_server_private_key']['const'] is False
pki=json.load(open(files[2]));r10=next(r for r in pki['requirements'] if r['id']=='FARO-R10');assert 'nunca expõe sua privkey ao agente' in r10['statement']
rec=json.load(open(root/'contratos/reconciliation.schema.json'));assert set(rec['properties']['decision']['enum'])=={'noop','reconcile','blocked','degraded','failed'}
print('FARO_VALIDATION_MODEL=PASS v2 verified=5 partial=1 R14=verified R19=verified')
