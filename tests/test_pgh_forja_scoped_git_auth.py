"""Independent local regression: no real credentials or remote connections."""
import ast
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import urllib.parse
import base64

SOURCE=Path(__file__).resolve().parents[1]/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py'

def auth():
    tree=ast.parse(SOURCE.read_text())
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_v119_git_ephemeral_auth']
    assert len(nodes)==1
    ns={'_v118_cfg':lambda key,default='': {'FORGEJO_URL':'https://forgejo.example.invalid/git','FORGEJO_TOKEN':'FAKE_TOKEN_TEST','FORGEJO_SERVICE_USER':'svc-test'}.get(key,default),'urllib':urllib,'base64':base64}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),ns,ns)
    return ns['_v119_git_ephemeral_auth']('team','project')

class ScopedGitAuth(unittest.TestCase):
    def test_auth_only_for_target_repo(self):
        url,env=auth()
        with tempfile.TemporaryDirectory() as d:
            full=os.environ.copy();full.update(env);full['HOME']=d;full['GIT_CONFIG_NOSYSTEM']='1'
            def get(candidate):
                p=subprocess.run(['git','config','--get-urlmatch','http.extraHeader',candidate],env=full,capture_output=True,text=True,timeout=10)
                return p.returncode,p.stdout.strip()
            self.assertEqual(get(url)[0],0)
            self.assertEqual(get('https://forgejo.example.invalid/git/other/project.git')[0],1)
            self.assertEqual(get('https://untrusted.example.invalid/repo.git')[0],1)
            self.assertEqual(get('http://forgejo.example.invalid/git/team/project.git')[0],1)
            self.assertEqual(get('https://forgejo.example.invalid/git/team/project.git-evil')[0],1)

    def test_git_config_is_ephemeral(self):
        url,env=auth()
        self.assertEqual(env['GIT_CONFIG_COUNT'],'2')
        self.assertEqual(env['GIT_CONFIG_KEY_1'],'http.followRedirects')
        self.assertEqual(env['GIT_CONFIG_VALUE_1'],'false')
        self.assertTrue(env['GIT_CONFIG_KEY_0'].startswith('http.https://'))
        self.assertNotIn('FAKE_TOKEN_TEST',url)
        self.assertNotIn('FAKE_TOKEN_TEST',env['GIT_CONFIG_KEY_0'])

if __name__=='__main__':unittest.main()
