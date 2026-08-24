#!/usr/bin/env python3
from pathlib import Path
import re,sys
root=Path(__file__).resolve().parents[1]
text=(root/'manifesto.yaml').read_text()
declared=set(re.findall(r'^\s+caminho:\s+(.+)$',text,re.M))
actual=set(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file())
extra=sorted(actual-declared); missing=sorted(declared-actual)
print(f'declared={len(declared)} actual={len(actual)} extra={len(extra)} missing={len(missing)}')
if extra: print('EXTRA',*extra,sep='\n- ')
if missing: print('MISSING',*missing,sep='\n- ')
sys.exit(1 if extra or missing else 0)
