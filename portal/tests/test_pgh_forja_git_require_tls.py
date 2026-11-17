"""Reject plaintext remote Git authentication except loopback test fixtures."""
import ast
import base64
from pathlib import Path
import unittest
import urllib

P=Path(__file__).resolve().parents[2]/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py'

class TransportTLS(unittest.TestCase):
    def helper(self,base):
        funcs=[x for x in ast.parse(P.read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='_v119_git_ephemeral_auth']
        assert len(funcs)==1
        values={'FORGEJO_URL':base,'FORGEJO_TOKEN':'SYNTHETIC-NOT-REAL','FORGEJO_SERVICE_USER':'test'}
        ns={'_v118_cfg':lambda k,default='':values.get(k,default),'urllib':urllib,'base64':base64}
        exec(compile(ast.Module(body=funcs,type_ignores=[]),str(P),'exec'),ns,ns)
        return ns['_v119_git_ephemeral_auth']('team','repo')
    def test_remote_http_rejected(self):
        for host in ('forgejo.example.invalid','10.62.91.2','192.168.1.1','127.0.0.2','example.invalid:8080'):
            with self.subTest(host=host),self.assertRaisesRegex(RuntimeError,'HTTPS'):
                self.helper('http://'+host+'/git')
    def test_https_remote_allowed(self):
        url,env=self.helper('https://forgejo.example.invalid/git')
        self.assertEqual(url,'https://forgejo.example.invalid/git/team/repo.git')
        self.assertEqual(env['GIT_CONFIG_VALUE_1'],'false')
    def test_http_loopback_fixtures_allowed(self):
        for host in ('127.0.0.1:18080','localhost:18080','[::1]:18080'):
            with self.subTest(host=host):
                url,_=self.helper('http://'+host+'/git')
                self.assertTrue(url.startswith('http://'))
if __name__=='__main__':unittest.main()
