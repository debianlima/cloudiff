"""Regression: packaging runtime mirror must not ship legacy credentialed Git operations."""
import ast
import pathlib
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
CANON=ROOT/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py'
MIRROR=ROOT/'components/runtime/usr/local/sbin/cloudif-forja-agent.py'

class RuntimeMirrorSecurity(unittest.TestCase):
    def test_runtime_mirror_exact_canonical(self):
        self.assertEqual(MIRROR.read_bytes(),CANON.read_bytes())
    def test_no_call_to_credentialed_git_url_builder(self):
        for p in (CANON,MIRROR):
            t=ast.parse(p.read_text())
            calls=[n for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_v119_forgejo_repo_git_url']
            self.assertEqual(calls,[],str(p))
    def test_ephemeral_auth_exists_both(self):
        for p in (CANON,MIRROR):
            t=ast.parse(p.read_text())
            names={n.name for n in t.body if isinstance(n,ast.FunctionDef)}
            self.assertIn('_v119_git_ephemeral_auth',names)
    def test_git_error_masking_both(self):
        for p in (CANON,MIRROR):
            t=ast.parse(p.read_text());fn=next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='_v119_mask')
            src=ast.get_source_segment(p.read_text(),fn)
            self.assertIn('Authorization',src)
            self.assertIn('quote_plus',src)

if __name__=='__main__': unittest.main()
