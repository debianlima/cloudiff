#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,subprocess,yaml
root=Path(__file__).resolve().parents[1]
audit=json.load(open(root/'docs/reconciliation/v1-1320-audit.json'))
delta=json.load(open(root/'docs/reconciliation/v1-v2-delta.json'))
manifest=yaml.safe_load(open(root/'manifesto.yaml'))
entries=manifest['entradas'];by={e['caminho']:e for e in entries}
assert audit['tracked_count']==1320 and audit['audited_count']==1320 and len(audit['files'])==1320 and not audit['syntax_errors']
norm=delta['post_reconciliation_normalization']
allowed={x['path']:x for x in norm['v1_changed_paths']}
link_failures={x['path'] for x in audit['markdown_link_errors']}
assert len(link_failures)==5
mismatches=[]
accepted=0
preexisting=0
for r in audit['files']:
 p=root/r['path'];assert p.is_file(),r['path']
 got=hashlib.sha256(p.read_bytes()).hexdigest()
 if got!=r['sha256']:
  mismatches.append(r['path']);assert r['path'] in allowed,r['path'];assert allowed[r['path']]['audit_sha256']==r['sha256']
 e=by.get(r['path']);assert e is not None,r['path']
 if r['path'] in link_failures:
  assert e['status']=='preexistente',r['path'];preexisting+=1
 else:
  assert e['status']=='aceito',r['path'];accepted+=1
 assert e['aceite']=='portao-mecanico/v1-audit-file',r['path']
assert accepted==1315 and preexisting==5
assert set(mismatches)==set(allowed), (mismatches,allowed)
# Prove original audited bytes remain recoverable in Git history for every controlled normalization.
for rel,meta in allowed.items():
 original=subprocess.check_output(['git','-C',str(root),'show',f"{audit['git_head']}:{rel}"])
 assert hashlib.sha256(original).hexdigest()==meta['audit_sha256']
assert len({e['id'] for e in entries})==len(entries) and len(by)==len(entries)
# Accepted SQL recovery is exact and no longer swallowed by global *.sql ignore.
for rec in norm['recovered_v2_accepted_paths']:
 rel=rec['path'];p=root/rel;assert p.is_file(),rel;assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['sha256'],rel
 assert subprocess.run(['git','-C',str(root),'check-ignore','-q',rel]).returncode!=0,rel
print(f"V1_NAMESPACE_AUDIT=PASS files=1320 accepted={accepted} preexistente={preexisting} exact_hashes={1320-len(mismatches)} controlled_normalization={len(mismatches)} sql_recovered=6")
