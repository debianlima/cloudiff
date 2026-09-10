#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,yaml
root=Path(__file__).resolve().parents[1]
raw=(root/'skills/cloudiff/SKILL.md').read_text();assert raw.startswith('---\n')
fm=yaml.safe_load(raw.split('---',2)[1])
competencias=yaml.safe_load((root/'competencias.yaml').read_text())
project_skill=competencias['skill_projeto']
audit=json.load(open(root/'docs/reconciliation/v1-1320-audit.json'))
delta=json.load(open(root/'docs/reconciliation/v1-v2-delta.json'))
plan=json.load(open(root/'docs/reconciliation/normalization-plan.json'))
closure=json.load(open(root/'docs/reconciliation/skill-closure-v40.json'))
assert fm['name']=='cloudiff' and fm['tipo_competencia']=='projeto'
assert project_skill['id']=='cloudiff' and project_skill['tipo_competencia']=='projeto'
assert project_skill['fonte']=='skills/cloudiff/SKILL.md'
assert str(project_skill['versao'])==str(fm['versao'])
assert 'FrozenPortalInterface' in raw
assert 'ModularidadeObrigatoria' in raw
assert 'R-MOD-1' in (root/'docs/REQUIREMENTS.md').read_text()
assert 'Arquitetura modular obrigatória' in (root/'docs/ARCHITECTURE.md').read_text()
assert '### L012 — capability de certificado do servidor não vira trust bundle do agente' in raw
assert '### L013 — `apply` idempotente não reinicia runtime equivalente' in raw
assert '### L014 — release existente não dispensa prova do artefato recebido' in raw
assert '### L059 — polling terminal precisa assentar o estado visual após reconexão transitória' in raw
assert '### L060 — exclusão de tenant inclui workspace env gerenciado e audita metadados, nunca conteúdo' in raw
reference_versions={r['id']:str(r['versao_fixada']) for r in (fm.get('referencia') or [])}
for rid in ('desenvolvedor-de-software','github-incremental-reconciliation','governanca-ontologica-de-skills'):
 expected=f"{rid}@{reference_versions[rid]}"; assert expected in raw,expected
# Project ontology: exactly two internally-composed CloudIFF skills and a unique reconciled reference set.
compoe=fm.get('compoe') or [];refs=fm.get('referencia') or []
assert {x['id'] for x in compoe}=={'cloudiff-authentik-oidc','cloudiff-safe-release'}
assert refs and len({x['id'] for x in refs})==len(refs)
for x in compoe:
 assert x['estado']=='reconciliado' and x['versao_fixada']=='1.0.0' and x['fonte'].startswith('skills/')
 p=root/x['fonte'];assert p.is_file();sfm=yaml.safe_load(p.read_text().split('---',2)[1]);assert sfm['name']==x['id'] and sfm['versao']=='1.0.0'
for r in refs:
 for k in ('id','fonte','versao_fixada','delta_lido_ate','estado'):assert r.get(k), (r.get('id'),k)
 assert r['estado']=='reconciliado' and r['versao_fixada']!='NAO DECLARADO' and 'NAO DECLARADO' not in r['fonte']
# Anti-cycle for the local composition graph: composed nodes do not point back to root or to each other.
for x in compoe:
 sfm=yaml.safe_load((root/x['fonte']).read_text().split('---',2)[1]) or {}
 rel=[]
 for k in ('requer','compoe','referencia','especializa','roteia_para'):
  v=sfm.get(k) or [];rel += v if isinstance(v,list) else [v]
 ids={q.get('id') if isinstance(q,dict) else q for q in rel}
 assert 'cloudiff' not in ids and not ({z['id'] for z in compoe}&ids),x['id']
# Reconciliation evidence and source hashes.
assert closure['contract_version']==40 and closure['project_skill_after']=='0.1.2'
assert closure['gates']['DELTA_INVENTORY']=='PASS' and closure['gates']['LEARNING_PRESERVED']=='PASS' and closure['gates']['SOURCE_HASH_PARITY']=='PASS' and closure['gates']['CATALOG_SYNC']=='PASS' and closure['gates']['RECONCILIATION_CLOSURE']=='PASS' and closure['gates']['DEPENDENCY_REFERENCES']=='PASS'
assert closure['catalog']['commit']=='998b6256ad7d5e6e43fa1e3477cd83e86bef2632'
refs_by_id={r['id']:r for r in refs}
for r in closure['external_references']:
 assert r['id'] in refs_by_id,r['id']
 assert refs_by_id[r['id']]['versao_fixada']==r['versao_fixada'],r['id']
 assert r['repository'].startswith('https://github.com/'),r['id']
 assert len(r['commit'])==40 and all(c in '0123456789abcdef' for c in r['commit']),r['id']
 assert len(r['sha256'])==64 and all(c in '0123456789abcdef' for c in r['sha256']),r['id']
 assert r['path'],r['id']
for r in closure['internal_compositions']:
 p=root/'skills'/r['id']/'SKILL.md';assert p.is_file();assert hashlib.sha256(p.read_bytes()).hexdigest()==r['canonical_sha256'];assert r['body_preserved'] is True
# Existing project audit/frozen interface gates remain invariant.
assert audit['tracked_count']==1320 and audit['audited_count']==1320 and len(audit['syntax_errors'])==0
for key in ('DELTA_INVENTORY','LEARNING_PRESERVED','NORMALIZATION_ALLOWED'):assert delta['gates'].get(key) in ('PASS','YES'),key
assert delta['v2']['path_collisions_with_v1']==0
assert plan['python_files']==444 and plan['classification_counts']['runtime-service-cpp-candidate']==123 and plan['classification_counts']['portal-compatibility-cpp-candidate']==249
assert delta['frozen_interface']['status']=='master-invariant' and len(delta['frozen_interface']['assets_sha256'])==10
for rel,expected in delta['frozen_interface']['assets_sha256'].items():
 assert rel and len(expected)==64 and all(c in '0123456789abcdef' for c in expected),rel
frozen=(root/'portal/FROZEN_SURFACES.md').read_text()
for surface in delta['frozen_interface']['surfaces']:
 assert f'- {surface}' in frozen,surface
for f in ('tests/test_faro_node_preparation.py','tests/test_agent_update.py'):
 assert ('-----BEGIN '+'PRIVATE KEY-----') not in (root/f).read_text()
print(f"CLOUDIFF_PROJECT_SKILL=PASS version={fm['versao']} compoe={len(compoe)} referencia={len(refs)} anti_cycle=PASS")
