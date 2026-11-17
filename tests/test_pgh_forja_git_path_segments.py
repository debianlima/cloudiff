"""Reject ambiguous Git repository path components before auth header scoping."""
import ast
import base64
from pathlib import Path
import unittest
import urllib

SOURCE=Path(__file__).resolve().parents[1]/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py'

def candidate():
    fn=[n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='_v119_git_ephemeral_auth']
    assert len(fn)==1
    ns={'_v118_cfg':lambda k,default='': 'https://forgejo.example.invalid/git' if k=='FORGEJO_URL' else 'synthetic-token' if k=='FORGEJO_TOKEN' else 'synthetic-bot', 'base64':base64,'urllib':urllib}
    exec(compile(ast.Module(body=fn,type_ignores=[]),str(SOURCE),'exec'),ns,ns)
    return ns['_v119_git_ephemeral_auth']

class Segments(unittest.TestCase):
    def test_rejects_ambiguous_components(self):
        f=candidate()
        for bad in ('','.','..','a/b',r'a\b','a\nname','a\x7fname'):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(RuntimeError):f(bad,'repo')
                with self.assertRaises(RuntimeError):f('owner',bad)
    def test_rejects_wrong_types(self):
        f=candidate()
        for bad in (None,3,[],{}):
            with self.subTest(type=type(bad).__name__):
                with self.assertRaises(RuntimeError):f(bad,'repo')
    def test_keeps_regular_names(self):
        f=candidate()
        for owner,repo in [('team','repo'),('team-name','repo.v2'),('team_1','repo_1')]:
            with self.subTest(owner=owner,repo=repo):
                url,env=f(owner,repo)
                self.assertEqual(url,f'https://forgejo.example.invalid/git/{owner}/{repo}.git')
                self.assertEqual(env['GIT_CONFIG_KEY_1'],'http.followRedirects')
if __name__=='__main__':unittest.main()
