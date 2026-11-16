"""File-bind vs directory-bind runtime env contract, without Docker or credentials."""
import ast
import copy
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[2]/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py'
SRC=SCRIPT.read_text()
TREE=ast.parse(SRC)

class StackRoot(ast.NodeTransformer):
    def __init__(self,root):self.root=root
    def visit_Constant(self,node):
        if node.value=='/etc/komodo/stacks':
            return ast.copy_location(ast.Constant(self.root),node)
        return node

class RuntimeEnvDirectoryContract(unittest.TestCase):
    def replace_function(self,root):
        fn=[n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='_cloudif_v144_runtime_env_replace'][-1]
        body=StackRoot(root).visit(ast.Module(body=[copy.deepcopy(fn)],type_ignores=[]))
        ast.fix_missing_locations(body)
        env={'Path':Path,'shutil':shutil,'os':os,'re':re}
        exec(compile(body,'<runtime-env-dir-sandbox>','exec'),env)
        return env['_cloudif_v144_runtime_env_replace']

    def test_compose_binds_directory_not_file(self):
        self.assertIn('source: ./runtime-config\n        target: /run/cloudif',SRC)
        self.assertNotIn('source: ./runtime.env\n        target: /run/cloudif/runtime.env',SRC)
        self.assertIn("const file='/run/cloudif/runtime.env';",SRC)

    def test_directory_inode_stable_during_atomic_file_replacement(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            env_dir=root/'cloudif-p1999-d3'/'runtime-config'
            env_dir.mkdir(parents=True)
            old=env_dir/'runtime.env';old.write_text('AUDIT_STAGE=HOMOLOGATION\n')
            incoming=root/'production.env';incoming.write_text('AUDIT_STAGE=PRODUCTION\n')
            dir_inode=env_dir.stat().st_ino
            file_inode=old.stat().st_ino
            with old.open() as previous_handle:
                result=self.replace_function(d)('cloudif-p1999-d3',incoming)
                self.assertEqual(result,str(old))
                self.assertEqual(env_dir.stat().st_ino,dir_inode)
                self.assertNotEqual(old.stat().st_ino,file_inode)
                self.assertEqual(old.read_text(),'AUDIT_STAGE=PRODUCTION\n')
                self.assertEqual(previous_handle.read(),'AUDIT_STAGE=HOMOLOGATION\n')
            self.assertEqual(old.stat().st_mode&0o777,0o600)

    def test_legacy_file_mount_layout_is_rejected_without_change(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)/'cloudif-p1999-d3';base.mkdir()
            old=base/'runtime.env';old.write_text('AUDIT_STAGE=HOMOLOGATION\n')
            incoming=Path(d)/'production.env';incoming.write_text('AUDIT_STAGE=PRODUCTION\n')
            with self.assertRaisesRegex(RuntimeError,'runtime_environment_path_missing'):
                self.replace_function(d)('cloudif-p1999-d3',incoming)
            self.assertEqual(old.read_text(),'AUDIT_STAGE=HOMOLOGATION\n')

if __name__=='__main__':unittest.main()
