#!/usr/bin/env python3
from pathlib import Path
import re
import json
root=Path(__file__).resolve().parents[1]
lines=(root/'manifesto.yaml').read_text().splitlines()
entries=[]; cur=None
for line in lines:
    m=re.match(r'\s+- id: (\d+)',line)
    if m:
        if cur: entries.append(cur)
        cur={'id':int(m.group(1)),'consome':[]}
        continue
    if not cur: continue
    m=re.match(r'\s+caminho: (.+)',line)
    if m: cur['caminho']=m.group(1)
    m=re.match(r'\s+proposito: (.+)',line)
    if m: cur['proposito']=m.group(1)
    m=re.match(r'\s+tipo: (.+)',line)
    if m: cur['tipo']=m.group(1)
    m=re.match(r'\s+produz: (.+)',line)
    if m: cur['produz']=m.group(1)
    m=re.match(r'\s+consome: \[(.*)\]',line)
    if m: cur['consome']=[x.strip() for x in m.group(1).split(',') if x.strip()]
    m=re.match(r'\s+status: (.+)',line)
    if m: cur['status']=m.group(1)
if cur: entries.append(cur)
prod={e.get('produz'):e for e in entries}
print('## 1. Mapa de módulos\n```mermaid\ngraph TD')
for e in entries: print(f'  E{e["id"]}["{e["caminho"]}"]')
print('```\n\n## 2. Grafo de dependências\n```mermaid\ngraph LR')
for e in entries:
    for c in e.get('consome',[]):
        if c in prod: print(f'  E{prod[c]["id"]} --> E{e["id"]}')
print('```\n\n## 3. Fluxo de execução derivado\n```mermaid\nflowchart TD')
print('  Portal[Portal legado] --> Compat[Contratos compatíveis]\n  Compat --> Control[cloudiff-control]\n  Control --> DB[(PostgreSQL)]\n  Control --> NATS[NATS]\n  NATS --> Worker[cloudiff-worker]\n  NATS --> Agent[cloudiff-agent]')
print('```\n\n## 4. Progresso\n```mermaid\ngraph TD')
for e in entries:
    tag='ACEITO' if e.get('status')=='aceito' else 'PENDENTE'
    print(f'  E{e["id"]}["{e["id"]} {tag} {e["caminho"]}"]')
print('```\n\n## 5. Cobertura de competência\n```mermaid\ngraph TD')
for e in entries: print(f'  E{e["id"]}["{e.get("tipo","?")} :: {e["caminho"]}"]')
print('```')
print('```\n\n## 6. P06 / Faro — validação distribuída derivada do manifesto\n```mermaid\nflowchart TD')
faro=[e for e in entries if 'faro-validation-' in e.get('caminho','') and not e.get('caminho','').endswith('schema.json')]
for e in faro:
    label=(e.get('proposito') or e.get('caminho','')).replace('"',"'")
    print(f'  E{e["id"]}["{label}"]')
for e in faro:
    for c in e.get('consome',[]):
        if c in prod and prod[c] in faro: print(f'  E{prod[c]["id"]} --> E{e["id"]}')
print('  E118 -. decisão explícita .-> DROLE{"role/capabilities confirmados"}')
print('  DROLE -. pré-condição .-> E119')
print('```')
print('```\n\n## 7. Faro — topologia física reservada\n```mermaid\nflowchart LR')
try:
  faro_cfg=json.loads((root/'config/faro-node-reservation.json').read_text())
  addr=faro_cfg['identity']['address'];nid=faro_cfg['identity']['nodeId']
  print(f'  FARO["Faro {addr}\\nnode_id {nid[:8]}…\\nVM ou físico via VPN"]')
  print('  HOS["Hospedagem 10.62.92.7\\nNATS :14222 + control + PostgreSQL"]')
  print('  MAU["Maurício 10.62.91.3\\nHTTPS/SecureDistribution\\nfora do heartbeat"]')
  print('  FOR["Forja 10.62.91.2\\nbuild/runtime opcional\\nfora do heartbeat"]')
  print('  FARO -->|mTLS node.observed| HOS')
  print('  FARO -. bootstrap/update opcional .-> MAU')
  print('  FARO -. somente capability futura .-> FOR')
except Exception:
  print('  FARO["Faro reservation unavailable"]')
print('```')
