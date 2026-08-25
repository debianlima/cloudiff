#!/usr/bin/env python3
from pathlib import Path
import subprocess,sys,yaml
root=Path(__file__).resolve().parents[1]
manifest=yaml.safe_load((root/'manifesto.yaml').read_text())
entries=manifest['entradas']
by_path={}
dup=[]
for e in entries:
 p=e['caminho']
 if p in by_path: dup.append(p)
 by_path[p]=e
try:
 actual=set(subprocess.check_output(['git','-C',str(root),'ls-files'],text=True).splitlines())
 source='git'
except Exception:
 actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and '.git' not in p.parts}
 source='filesystem'
declared=set(by_path)
extra=sorted(actual-declared)
missing_required=sorted(p for p in declared-actual if by_path[p].get('status') not in ('pendente','em_curso'))
missing_pending=sorted(p for p in declared-actual if by_path[p].get('status') in ('pendente','em_curso'))
print(f'source={source} declared={len(declared)} actual={len(actual)} extra={len(extra)} missing_required={len(missing_required)} missing_pending={len(missing_pending)} duplicates={len(dup)}')
if extra:print('EXTRA',*extra,sep='\n- ')
if missing_required:print('MISSING_REQUIRED',*missing_required,sep='\n- ')
if dup:print('DUPLICATE_PATH',*sorted(set(dup)),sep='\n- ')
if missing_pending:print('PENDING_NOT_GENERATED',*missing_pending,sep='\n- ')
sys.exit(1 if extra or missing_required or dup else 0)
