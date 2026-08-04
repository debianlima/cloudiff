#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEGIN = '<!-- CLOUDIFF-AUTO-DOC:BEGIN -->'
END = '<!-- CLOUDIFF-AUTO-DOC:END -->'
SKIP_DIRS = {'.git', '__pycache__', '.pytest_cache', '.mypy_cache', 'node_modules'}


def tracked_paths() -> list[Path]:
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT)
    paths = {ROOT / p.decode() for p in tracked.split(b'\0') if p}
    # Include the new documentation sources before their first commit, but do
    # not absorb arbitrary runtime artifacts present in the working tree.
    for base in (ROOT / 'docs' / 'manual-tecnico',):
        if base.exists():
            paths.update(p for p in base.rglob('*') if p.is_file())
    for rel in ('scripts/generate-directory-readmes.py', 'docs/INVENTARIO-DE-ARQUIVOS.md', 'docs/DOCUMENTATION-MANIFEST.json'):
        p = ROOT / rel
        if p.exists(): paths.add(p)
    return sorted(paths)


def title_for(path: Path) -> str:
    if path == ROOT:
        return 'CloudIFF'
    return path.name.replace('-', ' ').replace('_', ' ').title()


def py_summary(path: Path) -> str:
    try:
        tree = ast.parse(path.read_text(encoding='utf-8', errors='ignore'))
        doc = ast.get_docstring(tree)
        if doc:
            return re.sub(r'\s+', ' ', doc).strip().split('. ')[0][:180]
        defs = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        if defs:
            return 'Implementa ' + ', '.join(f'`{x}`' for x in defs[:6]) + ('.' if len(defs) <= 6 else ' e outros componentes.')
    except Exception:
        pass
    return 'Módulo Python da plataforma.'


def file_summary(path: Path) -> str:
    name = path.name
    low = name.lower()
    suffix = path.suffix.lower()
    rel = path.relative_to(ROOT).as_posix()
    if name == 'README.md': return 'Documentação deste diretório.'
    if low.endswith('.service'): return 'Unidade systemd que inicia e protege um serviço CloudIFF.'
    if low.endswith('.timer'): return 'Timer systemd que agenda a unidade correspondente.'
    if suffix == '.py': return py_summary(path)
    if suffix in {'.sh', '.bash'}:
        if 'backup' in low: return 'Script Shell de backup, retenção ou sincronização.'
        if 'restore' in low: return 'Script Shell de restauração ou teste de recuperação.'
        if 'tenant' in low: return 'Script Shell de criação, manutenção ou reconciliação de tenant.'
        if 'router' in low: return 'Script Shell que renderiza, valida ou recarrega rotas.'
        return 'Automação Shell operacional da plataforma.'
    if suffix in {'.json', '.jsonl'}:
        if 'schema' in low: return 'Esquema ou contrato de dados em JSON.'
        if 'policy' in low or 'permission' in low: return 'Política ou configuração declarativa em JSON.'
        return 'Configuração, inventário, evidência ou estado serializado em JSON.'
    if suffix in {'.yml', '.yaml'}:
        if 'compose' in low or 'docker' in low: return 'Definição declarativa de serviços Docker Compose.'
        return 'Configuração declarativa YAML.'
    if low.startswith('dockerfile') or name == 'Containerfile': return 'Receita de imagem de container.'
    if suffix in {'.conf', '.ini', '.cfg'}: return 'Configuração de serviço, proxy ou aplicação.'
    if suffix == '.env' or '.env.' in low: return 'Modelo de variáveis de ambiente; não deve conter segredos reais.'
    if suffix == '.sql': return 'DDL, migração ou consulta SQL.'
    if suffix in {'.html', '.htm'}: return 'Interface, protótipo ou evidência HTML.'
    if suffix == '.css': return 'Estilos da interface web.'
    if suffix == '.js': return 'Comportamento JavaScript da interface ou automação.'
    if suffix == '.md': return 'Documento técnico ou operacional.'
    if suffix == '.csv': return 'Registro tabular versionado.'
    if suffix in {'.crt', '.pem', '.key'}: return 'Material criptográfico de exemplo ou implantação; revisar antes de distribuir.'
    if suffix == '.gitkeep': return 'Mantém o diretório vazio sob controle de versão.'
    if 'test' in rel.lower(): return 'Artefato de teste ou evidência de validação.'
    return 'Arquivo de suporte da plataforma.'


def dir_summary(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix() if path != ROOT else '.'
    mapping = {
        'components/control-plane': 'Componentes implantados no plano de controle e no host de hospedagem.',
        'components/runtime': 'Componentes implantados no host de runtime, Forgejo, Komodo e executores.',
        'components/proxy': 'Componentes implantados no host de proxy e publicação.',
        'portal': 'Arquitetura modular, interface, configuração e testes do Portal.',
        'docs': 'Documentação técnica, inventários e evidências.',
        'config': 'Configurações por nó e contratos declarativos.',
        'scripts': 'Ferramentas de validação, documentação e manutenção do repositório.',
        'tenant-templates': 'Modelos e snapshots de tenants Supabase.',
        '.github': 'Automação e integração contínua do GitHub.',
    }
    for prefix, text in mapping.items():
        if rel == prefix or rel.startswith(prefix + '/'):
            return text
    if 'current-apps' in rel: return 'Aplicação ativa versionada para implantação por ponteiro `current`.'
    if '/systemd/system' in rel: return 'Unidades e timers systemd versionados.'
    if '/komodo/stacks' in rel: return 'Definições de stacks gerenciadas pelo Komodo.'
    if '/nginx' in rel or '/router' in rel: return 'Configuração de roteamento e proxy.'
    if '/tests' in rel: return 'Testes automatizados e contratos de regressão.'
    return 'Diretório versionado da CloudIFF.'


def update_readme(directory: Path, files: list[Path], subdirs: list[Path]) -> None:
    readme = directory / 'README.md'
    existing = readme.read_text(encoding='utf-8', errors='ignore') if readme.exists() else f'# {title_for(directory)}\n\n{dir_summary(directory)}\n'
    rows = []
    for d in sorted(subdirs, key=lambda p: p.name.lower()):
        rows.append(f'| [`{d.name}/`]({d.name}/) | Diretório | {dir_summary(d)} |')
    for f in sorted(files, key=lambda p: p.name.lower()):
        if f.name == 'README.md':
            continue
        rows.append(f'| [`{f.name}`]({f.name}) | `{f.suffix or "arquivo"}` | {file_summary(f)} |')
    rel = directory.relative_to(ROOT).as_posix() if directory != ROOT else '.'
    auto = [BEGIN, '', f'## Inventário automático de `{rel}`', '', dir_summary(directory), '', '| Item | Tipo | Finalidade |', '|---|---|---|']
    auto.extend(rows or ['| — | — | Nenhum item versionado imediato. |'])
    auto.extend(['', '> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.', '', END])
    block = '\n'.join(auto)
    if BEGIN in existing and END in existing:
        existing = re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END), block, existing, flags=re.S)
    else:
        existing = existing.rstrip() + '\n\n' + block + '\n'
    readme.write_text(existing, encoding='utf-8')


def main() -> None:
    paths = tracked_paths()
    directories = {ROOT}
    for path in paths:
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        directories.add(path.parent)
        cur = path.parent
        while cur != ROOT:
            directories.add(cur)
            cur = cur.parent
    for directory in sorted(directories, key=lambda p: (len(p.parts), p.as_posix())):
        immediate_files = [p for p in paths if p.parent == directory]
        immediate_dirs = sorted({p for p in directories if p.parent == directory})
        update_readme(directory, immediate_files, immediate_dirs)

    all_files = sorted([p for p in tracked_paths() if not any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts)], key=lambda p: p.relative_to(ROOT).as_posix())
    lines = ['# Inventário de arquivos', '', f'Este catálogo descreve **{len(all_files)} arquivos versionados**. Ele é regenerado pelo script de documentação.', '', '| Caminho | Finalidade |', '|---|---|']
    for p in all_files:
        rel = p.relative_to(ROOT).as_posix()
        lines.append(f'| [`{rel}`](../{rel}) | {file_summary(p)} |')
    (ROOT / 'docs' / 'INVENTARIO-DE-ARQUIVOS.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    manifest = {
        'files': len(all_files),
        'directories': len(directories),
        'generator': 'scripts/generate-directory-readmes.py',
        'manual': 'docs/manual-tecnico/README.md',
    }
    (ROOT / 'docs' / 'DOCUMENTATION-MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
