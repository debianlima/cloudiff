"""Fail-closed base URL normalization for Git auth scope; synthetic only."""
import ast
import base64
from pathlib import Path
import unittest
import urllib

SOURCE=Path(__file__).resolve().parents[1]/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py'

def build(base):
    f=[n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='_v119_git_ephemeral_auth']
    assert len(f)==1
    def config(k,default=''):
        return {'FORGEJO_URL':base,'FORGEJO_TOKEN':'SYNTHETIC_TOKEN_ONLY','FORGEJO_SERVICE_USER':'test-bot'}.get(k,default)
    ns={'_v118_cfg':config,'urllib':urllib,'base64':base64}
    exec(compile(ast.Module(body=f,type_ignores=[]),str(SOURCE),'exec'),ns,ns)
    return ns['_v119_git_ephemeral_auth']

class BaseURL(unittest.TestCase):
    def test_reject_ambiguous_base_url(self):
        for base in ('https://forgejo.example.invalid/git?x=1',
                     'https://forgejo.example.invalid/git#fragment',
                     'https://forgejo.example.invalid/git/../other',
                     'https://forgejo.example.invalid/git/./other',
                     'https://forgejo.example.invalid/git/%2e%2e/other',
                     'https://forgejo.example.invalid/git/%2f/other',
                     'https://forgejo.example.invalid/git\\other',
                     'https://forgejo.example.invalid/git\nother'):
            with self.subTest(base=repr(base)):
                with self.assertRaises(RuntimeError):build(base)('team','repo')
    def test_valid_base_url(self):
        for base in ('https://forgejo.example.invalid/git','https://forgejo.example.invalid/git/'):
            with self.subTest(base=base):
                url,env=build(base)('team','repo')
                self.assertEqual(url,'https://forgejo.example.invalid/git/team/repo.git')
                self.assertEqual(env['GIT_CONFIG_VALUE_1'],'false')
if __name__=='__main__':unittest.main()
