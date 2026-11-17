"""Static regression: bundle import must not persist Forgejo userinfo in git remotes."""
import ast
from pathlib import Path
import unittest
SOURCE=Path(__file__).resolve().parents[1]/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py'
class BundleImportAuthTests(unittest.TestCase):
    def test_all_network_git_calls_receive_ephemeral_auth(self):
        tree=ast.parse(SOURCE.read_text())
        funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and any('target_url' in ast.unparse(n) and '_cloudif_v122_import' in n.name for _ in [0])]
        self.assertEqual(len(funcs),1)
        fn=funcs[0]
        assignments=[n for n in ast.walk(fn) if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='_v119_git_ephemeral_auth']
        self.assertEqual(len(assignments),1)
        calls=[]
        for n in ast.walk(fn):
            if not isinstance(n,ast.Call) or not isinstance(n.func,ast.Name) or n.func.id!='_v119_run' or not n.args:continue
            arg=n.args[0]
            if not isinstance(arg,ast.List) or len(arg.elts)<2:continue
            op=arg.elts[1]
            if isinstance(op,ast.Constant) and op.value in ('ls-remote','fetch','push'):
                calls.append(n)
        self.assertGreaterEqual(len(calls),7)
        for c in calls:
            self.assertIn('git_auth_env',[k.arg for k in c.keywords])
    def test_old_credential_url_helper_not_used_in_bundle_import(self):
        tree=ast.parse(SOURCE.read_text())
        funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and '_cloudif_v122_import' in n.name]
        self.assertTrue(funcs)
        for fn in funcs:
            for n in ast.walk(fn):
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Name):
                    self.assertNotEqual(n.func.id,'_v119_forgejo_repo_git_url')
if __name__=='__main__':unittest.main()
