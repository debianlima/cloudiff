#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def esc(value: str) -> str:
    return value.replace('|', '\\|').replace('\n', ' ')


def service_catalog() -> None:
    rows=[]
    for path in sorted(ROOT.glob('components/*/etc/systemd/system/*')):
        if not path.is_file() or path.suffix not in {'.service','.timer'}:
            continue
        text=path.read_text(errors='ignore')
        desc=re.search(r'^Description=(.+)$',text,re.M)
        execs=re.findall(r'^ExecStart=(.+)$',text,re.M)
        schedule=re.findall(r'^(?:OnCalendar|OnBootSec|OnUnitActiveSec)=(.+)$',text,re.M)
        node=path.parts[path.parts.index('components')+1]
        rows.append((path.relative_to(ROOT).as_posix(),node,path.suffix[1:],desc.group(1).strip() if desc else 'Unidade CloudIFF', '; '.join(execs[:2]) or '—','; '.join(schedule) or '—'))
    out=['# Catálogo de serviços systemd','',f'Catálogo derivado de **{len(rows)} unidades e timers** versionados.','','| Arquivo | Nó | Tipo | Descrição | Execução | Agenda |','|---|---|---|---|---|---|']
    out += [f'| [`{p}`](../{p}) | {n} | {t} | {esc(d)} | `{esc(e)}` | {esc(a)} |' for p,n,t,d,e,a in rows]
    (ROOT/'docs/CATALOGO-DE-SERVICOS.md').write_text('\n'.join(out)+'\n')


def route_catalog() -> None:
    roots=[ROOT/'components/control-plane/current-apps',ROOT/'components/runtime/current-apps',ROOT/'portal/modules']
    seen=set();rows=[]
    route_re=re.compile(r"['\"](/(?:cloudif|cloudiff|api|v1|internal|komodo|forgejo|project|oauth|health|status|auth)[A-Za-z0-9_{}?&=./:-]*)['\"]")
    for base in roots:
        if not base.exists(): continue
        for path in sorted(base.rglob('*.py')):
            text=path.read_text(errors='ignore')
            for m in route_re.finditer(text):
                route=m.group(1)
                key=(path,route)
                if key in seen: continue
                seen.add(key)
                before=text[max(0,m.start()-180):m.start()]
                method='GET/POST'
                if 'do_GET' in before: method='GET'
                elif 'do_POST' in before: method='POST'
                elif "'GET'" in before or '"GET"' in before: method='GET'
                elif "'POST'" in before or '"POST"' in before: method='POST'
                rows.append((path.relative_to(ROOT).as_posix(),method,route))
    out=['# Catálogo de rotas e endpoints','',f'Catálogo estático de **{len(rows)} referências de rota** encontradas nos serviços e módulos. Uma rota pode aparecer em mais de um adaptador por compatibilidade.','','| Componente | Método observado | Rota |','|---|---|---|']
    out += [f'| [`{p}`](../{p}) | {m} | `{esc(r)}` |' for p,m,r in sorted(rows,key=lambda x:(x[0],x[2]))]
    (ROOT/'docs/CATALOGO-DE-ROTAS.md').write_text('\n'.join(out)+'\n')


def agents_catalog() -> None:
    rows=[]
    bases=[ROOT/'components/control-plane/current-apps',ROOT/'components/runtime/current-apps']
    for base in bases:
        for directory in sorted(base.glob('*-current')):
            if not directory.is_dir(): continue
            pyfiles=sorted(directory.glob('*.py'))
            funcs=[];classes=[];routes=set()
            for path in pyfiles:
                text=path.read_text(errors='ignore')
                try:
                    tree=ast.parse(text)
                    funcs += [n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and not n.name.startswith('_')]
                    classes += [n.name for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and not n.name.startswith('_')]
                except Exception: pass
                routes.update(re.findall(r"['\"](/(?:v1|internal|komodo|forgejo|project|oauth|health|status|auth)[A-Za-z0-9_{}?&=./:-]*)['\"]",text))
            rows.append((directory.relative_to(ROOT).as_posix(),', '.join(classes[:8]) or '—',', '.join(sorted(set(funcs))[:16]) or '—',', '.join(sorted(routes)[:20]) or '—'))
    out=['# Catálogo de agentes e aplicações','',f'Inventário derivado de **{len(rows)} aplicações ativas**.','','| Aplicação | Classes públicas | Funções públicas | Endpoints principais |','|---|---|---|---|']
    out += [f'| [`{p}`](../{p}/) | {esc(c)} | {esc(f)} | `{esc(r)}` |' for p,c,f,r in rows]
    (ROOT/'docs/CATALOGO-DE-AGENTES.md').write_text('\n'.join(out)+'\n')


def extract_create_table_snippet(text: str, table: str) -> str:
    """Return only the balanced CREATE TABLE statement, never following fixtures/code."""
    pattern = re.compile(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?["`\[]?' + re.escape(table) + r'["`\]]?\s*\(',
        re.I,
    )
    match = pattern.search(text)
    if not match:
        return ''
    start = match.start()
    open_pos = text.find('(', match.start(), match.end() + 1)
    if open_pos < 0:
        return ''
    depth = 0
    quote = None
    escaped = False
    end = min(len(text), start + 4000)
    for pos in range(open_pos, end):
        ch = text[pos]
        if quote:
            if escaped:
                escaped = False
                continue
            if ch == '\\':
                escaped = True
                continue
            if ch == quote:
                quote = None
            continue
        if ch in {"'", '"'}:
            quote = ch
            continue
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return re.sub(r'\s+', ' ', text[start:pos + 1]).strip()[:1200]
    return re.sub(r'\s+', ' ', text[start:min(end, open_pos + 1200)]).strip()[:1200]


def schema_catalog() -> None:
    rows=[]
    create_re=re.compile(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?["`\[]?([A-Za-z0-9_]+)',re.I)
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file() or '.git' in path.parts or path.suffix.lower() not in {'.py','.sql','.sh'}: continue
        text=path.read_text(errors='ignore')
        for table in sorted(set(create_re.findall(text))):
            snippet=extract_create_table_snippet(text,table)
            rows.append((table,path.relative_to(ROOT).as_posix(),snippet[:500]))
    out=['# Dicionário de dados estático','',f'Foram encontradas **{len(rows)} declarações de tabela** no código versionado. Este catálogo é estático; o schema efetivo de produção deve ser confirmado por migração e `PRAGMA table_info`.','','| Tabela | Definida em | DDL observado |','|---|---|---|']
    out += [f'| `{t}` | [`{p}`](../{p}) | `{esc(s)}` |' for t,p,s in sorted(rows,key=lambda x:(x[0],x[1]))]
    (ROOT/'docs/DICIONARIO-DE-DADOS-ESTATICO.md').write_text('\n'.join(out)+'\n')


if __name__=='__main__':
    service_catalog();route_catalog();agents_catalog();schema_catalog()
