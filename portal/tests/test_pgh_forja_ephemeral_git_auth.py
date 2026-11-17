"""Offline Git credential transport tests with synthetic secrets only."""
import ast
import base64
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import urllib.parse

SOURCE=(Path(__file__).resolve().parents[2]/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py')
FAKE_TOKEN='TEST+/CREDENTIAL:ONLY'

def helpers():
    tree=ast.parse(SOURCE.read_text())
    funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_v119_git_ephemeral_auth','_v119_run')]
    assert len(funcs)==2
    ns={'_v118_cfg':lambda key,default='': {'FORGEJO_URL':'https://forge.example.invalid/git','FORGEJO_TOKEN':FAKE_TOKEN,'FORGEJO_SERVICE_USER':'testsvc'}.get(key,default),
        'urllib':urllib,'base64':base64,'os':os,'subprocess':subprocess,'_v119_mask':lambda x:x}
    exec(compile(ast.Module(body=funcs,type_ignores=[]),str(SOURCE),'exec'),ns,ns)
    return ns

class GitEphemeralAuthTests(unittest.TestCase):
    def test_clean_url_and_ephemeral_header(self):
        url,env=helpers()['_v119_git_ephemeral_auth']('owner','repo')
        self.assertEqual(url,'https://forge.example.invalid/git/owner/repo.git')
        self.assertNotIn(FAKE_TOKEN,url)
        self.assertNotIn('@',url)
        self.assertEqual(env['GIT_CONFIG_COUNT'],'2')
        self.assertEqual(env['GIT_CONFIG_KEY_1'],'http.followRedirects')
        self.assertEqual(env['GIT_CONFIG_VALUE_1'],'false')
        self.assertEqual(env['GIT_CONFIG_KEY_0'],f'http.{url}.extraHeader')
        self.assertEqual(env['GIT_CONFIG_VALUE_0'],'Authorization: Basic '+base64.b64encode(('testsvc:'+FAKE_TOKEN).encode()).decode())

    def test_missing_token_rejected(self):
        ns=helpers();ns['_v118_cfg']=lambda k,d='': '' if k=='FORGEJO_TOKEN' else ('https://forge.example.invalid' if k=='FORGEJO_URL' else d)
        with self.assertRaises(RuntimeError):ns['_v119_git_ephemeral_auth']('owner','repo')

    def test_plain_http_endpoint_is_refused_before_auth_header_generation(self):
        ns=helpers()
        ns['_v118_cfg']=lambda key,default='': {
            'FORGEJO_URL':'http://forge.example.invalid/git',
            'FORGEJO_TOKEN':FAKE_TOKEN,'FORGEJO_SERVICE_USER':'testsvc',
        }.get(key,default)
        with self.assertRaisesRegex(RuntimeError,'HTTPS'):
            ns['_v119_git_ephemeral_auth']('owner','repo')

    def test_url_query_and_fragment_cannot_change_canonical_authority(self):
        for suffix in ('?path=invalid','#fragment'):
            with self.subTest(suffix=suffix):
                ns=helpers()
                ns['_v118_cfg']=lambda key,default='', suffix=suffix: {
                    'FORGEJO_URL':'https://forge.example.invalid/git'+suffix,
                    'FORGEJO_TOKEN':FAKE_TOKEN,'FORGEJO_SERVICE_USER':'testsvc',
                }.get(key,default)
                with self.assertRaisesRegex(RuntimeError,'HTTPS'):
                    ns['_v119_git_ephemeral_auth']('owner','repo')

    def test_git_subprocess_receives_env_without_argv_secret(self):
        ns=helpers();url,env=ns['_v119_git_ephemeral_auth']('owner','repo')
        class FakeResult: returncode=0;stdout='ok';stderr=''
        called=[]
        def fake_run(argv,**kwargs):
            called.append((argv,kwargs));return FakeResult()
        ns['subprocess']=type('FakeSubprocess',(),{'run':staticmethod(fake_run),'PIPE':-1})
        result=ns['_v119_run'](['git','clone',url,'/tmp/destination'],git_auth_env=env)
        self.assertEqual(result['returncode'],0)
        self.assertNotIn(FAKE_TOKEN,repr(called[0][0]))
        self.assertNotIn(base64.b64encode(FAKE_TOKEN.encode()).decode(),repr(called[0][0]))
        self.assertEqual(called[0][1]['env']['GIT_CONFIG_VALUE_0'],env['GIT_CONFIG_VALUE_0'])

    def test_git_local_clone_origin_does_not_persist_header(self):
        # No network or live token; local repository exercises real Git config.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);origin=root/'origin.git';clone=root/'clone'
            subprocess.run(['git','init','--bare','-q',str(origin)],check=True)
            env={'**': 'ignored'};env=os.environ.copy()
            env.update({'GIT_CONFIG_COUNT':'1','GIT_CONFIG_KEY_0':'http.extraHeader',
                        'GIT_CONFIG_VALUE_0':'Authorization: Basic '+base64.b64encode(('testsvc:'+FAKE_TOKEN).encode()).decode()})
            subprocess.run(['git','clone','-q',str(origin),str(clone)],check=True,env=env,stderr=subprocess.PIPE)
            config=(clone/'.git/config').read_text()
            self.assertNotIn(FAKE_TOKEN,config)
            self.assertNotIn('Authorization:',config)
            self.assertNotIn('extraHeader',config)
            self.assertIn(str(origin),config)

    def test_both_fallbacks_use_auth_context(self):
        tree=ast.parse(SOURCE.read_text())
        for name in ('_v119_git_commit_file','_change_set_git_commit_bytes'):
            fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            calls=[n for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_v119_run']
            network=[]
            for c in calls:
                if not c.args or not isinstance(c.args[0],ast.List):continue
                cmd=c.args[0].elts
                if len(cmd)>1 and isinstance(cmd[1],ast.Constant) and cmd[1].value in ('clone','push'):
                    network.append(c)
            self.assertGreaterEqual(len(network),3)
            for c in network:self.assertIn('git_auth_env',[k.arg for k in c.keywords])

if __name__=='__main__':unittest.main()
