"""No real credentials. Regression for Forgejo Git CLI error redaction."""
import ast
from pathlib import Path
import re
import unittest
import urllib.parse

SOURCE=(Path(__file__).resolve().parents[1]/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py')
FAKE_TOKEN='FAKE+/TOKEN:TEST'
FAKE_USER='svc-test'

def mask(message,token=FAKE_TOKEN,user=FAKE_USER):
    functions=[node for node in ast.parse(SOURCE.read_text()).body
               if isinstance(node,ast.FunctionDef) and node.name=='_v119_mask']
    assert len(functions)==1
    def cfg(key,default=''):
        # The only secrets in tests are synthetic and never access the runtime config.
        if 'token' in key.lower():return token
        return user
    ns={'_v118_cfg':cfg,'urllib':urllib,'re':re}
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(SOURCE),'exec'),ns,ns)
    return ns['_v119_mask'](message)

class RedactionTests(unittest.TestCase):
    def test_raw_token_redacted(self):
        self.assertNotIn(FAKE_TOKEN,mask('failed '+FAKE_TOKEN))

    def test_percent_encoded_token_redacted(self):
        encoded=urllib.parse.quote(FAKE_TOKEN,safe='')
        result=mask('failed: https://'+FAKE_USER+':'+encoded+'@example.invalid/repo.git')
        self.assertNotIn(encoded,result)
        self.assertNotIn(FAKE_TOKEN,result)
        self.assertIn('example.invalid/repo.git',result)
        self.assertNotIn(FAKE_USER+':',result)

    def test_authorization_userinfo_redacted_without_known_token(self):
        result=mask('fatal: https://one-user:unknown-password@example.invalid/repo.git',token='')
        self.assertNotIn('unknown-password',result)
        self.assertNotIn('one-user',result)
        self.assertIn('https://[auth-redacted]@example.invalid/repo.git',result)

    def test_unauthed_url_unchanged(self):
        url='https://example.invalid/repo.git'
        self.assertIn(url,mask('failure '+url))

    def test_double_at_userinfo_redacted(self):
        result=mask('failure https://user@tenant:credential@example.invalid/repo.git',token='')
        self.assertNotIn('credential',result)
        self.assertNotIn('user@tenant',result)

    def test_exception_with_quoted_token_percent_encoded(self):
        encoded=urllib.parse.quote_plus(FAKE_TOKEN)
        self.assertNotIn(encoded,mask("TimeoutExpired cmd=['git', 'clone', 'https://"+FAKE_USER+':'+encoded+"@example.invalid/repo.git']"))

if __name__=='__main__':unittest.main()
