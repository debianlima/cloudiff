#!/usr/bin/env python3
from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1]
skill=(root/'skills/cloudiff/SKILL.md').read_text()
audit=json.load(open(root/'docs/reconciliation/v1-1320-audit.json'))
delta=json.load(open(root/'docs/reconciliation/v1-v2-delta.json'))
plan=json.load(open(root/'docs/reconciliation/normalization-plan.json'))
assert 'name: cloudiff' in skill and 'tipo_competencia: projeto' in skill and 'versao: 0.1.0' in skill
for x in ('desenvolvedor-de-software@14','github-incremental-reconciliation@7','governanca-ontologica-de-skills@1.0.4','FrozenPortalInterface'):
    assert x in skill,x
assert audit['tracked_count']==1320 and audit['audited_count']==1320 and len(audit['syntax_errors'])==0

for key in ('DELTA_INVENTORY','LEARNING_PRESERVED','NORMALIZATION_ALLOWED'):
    assert delta['gates'].get(key) in ('PASS','YES'), key
assert delta['v2']['path_collisions_with_v1']==0
assert plan['python_files']==444
assert plan['classification_counts']['runtime-service-cpp-candidate']==123
assert plan['classification_counts']['portal-compatibility-cpp-candidate']==249
assert delta['frozen_interface']['status']=='master-invariant' and len(delta['frozen_interface']['assets_sha256'])==10
for rel,expected in delta['frozen_interface']['assets_sha256'].items():
    p=root/rel
    if p.exists(): assert hashlib.sha256(p.read_bytes()).hexdigest()==expected,rel
for f in ('tests/test_faro_node_preparation.py','tests/test_agent_update.py'):
    assert ('-----BEGIN ' + 'PRIVATE KEY-----') not in (root/f).read_text()
print('CLOUDIFF_PROJECT_SKILL=PASS')
