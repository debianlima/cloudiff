#!/usr/bin/env python3
import argparse, ast, hashlib, shutil, subprocess, tempfile
from pathlib import Path

BASE_SHA='d0329556d5c83665a455a0c6f82321b6e4dcd6a11bc1081a8bb652c54223ad74'
PATCHED_SHA='67c1b4ba2673333775957bad68796241f19debe9be858f5a7fa9ed991a086194'

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def source_of(tree: ast.AST, text: str, name: str) -> str:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return ast.get_source_segment(text, node) or ''
    raise AssertionError(f'missing AST node: {name}')

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--patch', required=True)
    ap.add_argument('--source')
    args=ap.parse_args()
    base=Path(args.base); patch=Path(args.patch)
    assert sha256(base)==BASE_SHA, sha256(base)
    with tempfile.TemporaryDirectory(prefix='cloudiff-p11-offline-') as td:
        target=Path(td)/'cloudif-forja-agent.py'; shutil.copy2(base,target)
        with patch.open('rb') as stdin:
            r=subprocess.run(['patch','--batch','--forward','-p1'],cwd=td,stdin=stdin,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert r.returncode==0, (r.stdout+r.stderr).decode('utf-8','replace')
        assert sha256(target)==PATCHED_SHA, sha256(target)
        subprocess.run(['python3','-m','py_compile',str(target)],check=True)
        text=target.read_text(); tree=ast.parse(text)
        assert 'SYSTEM_FIXTURE_DIR = Path("/var/lib/cloudif/forja-agent/system-fixtures")' in text
        assert text.count('load_system_fixture(slug)')==2
        load_fixture=source_of(tree,text,'load_system_fixture')
        archive=source_of(tree,text,'cloudif_workspace_archive')
        handler=source_of(tree,text,'Handler')
        assert "data.get('system_fixture') is not True" in load_fixture
        assert "project = load_project(slug) or load_system_fixture(slug)" in archive
        assert 'load_system_fixture(' not in handler
        assert 'return json_response(self, 200, {"ok": True, "projects": list_projects()})' in handler
        assert 'project = load_project(slug)' in handler
        assert 'STATE_DIR = Path("/var/lib/cloudif/forja-agent/projects")' in text
        if args.source:
            assert sha256(Path(args.source))==PATCHED_SHA
            assert Path(args.source).read_bytes()==target.read_bytes()
    print('FORJA_SYSTEM_FIXTURE_OFFLINE=PASS')

if __name__=='__main__': main()
