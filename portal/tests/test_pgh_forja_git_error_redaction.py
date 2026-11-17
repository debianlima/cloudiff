"""No real credentials. Regression for Forgejo Git CLI error redaction."""
import ast
from pathlib import Path
import re
import unittest
import urllib.parse

SOURCE=(Path(__file__).resolve().parents[2]/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py')
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

def fake_https_remote(userinfo, resource='repo.git'):
    """Assemble a synthetic userinfo URL during tests; never commit one."""
    return 'https://' + userinfo + '@example.invalid/' + resource


class RedactionTests(unittest.TestCase):
    def test_raw_token_redacted(self):
        self.assertNotIn(FAKE_TOKEN,mask('failed '+FAKE_TOKEN))

    def test_percent_encoded_token_redacted(self):
        encoded=urllib.parse.quote(FAKE_TOKEN,safe='')
        result=mask('failed: '+fake_https_remote(FAKE_USER+':'+encoded))
        self.assertNotIn(encoded,result)
        self.assertNotIn(FAKE_TOKEN,result)
        self.assertIn('example.invalid/repo.git',result)
        self.assertNotIn(FAKE_USER+':',result)

    def test_authorization_userinfo_redacted_without_known_token(self):
        result=mask('fatal: '+fake_https_remote('one-user:unknown-password'),token='')
        self.assertNotIn('unknown-password',result)
        self.assertNotIn('one-user',result)
        self.assertIn('https://[auth-redacted]@example.invalid/repo.git',result)

    def test_unauthed_url_unchanged(self):
        url='https://example.invalid/repo.git'
        self.assertIn(url,mask('failure '+url))

    def test_double_at_userinfo_redacted(self):
        result=mask('failure '+fake_https_remote('user@tenant:credential'),token='')
        self.assertNotIn('credential',result)
        self.assertNotIn('user@tenant',result)

    def test_unknown_query_token_not_echoed(self):
        result=mask('fatal https://example.invalid/repo.git?access_token=SYNTHETIC-QUERY-SECRET',token='')
        self.assertNotIn('SYNTHETIC-QUERY-SECRET',result)
        self.assertIn('https://example.invalid/repo.git[query-redacted]',result)

    def test_fragment_not_echoed(self):
        result=mask('fatal https://example.invalid/repo.git#SYNTHETIC-FRAGMENT-SECRET',token='')
        self.assertNotIn('SYNTHETIC-FRAGMENT-SECRET',result)

    def test_ssh_scheme_userinfo_not_echoed(self):
        result=mask('fatal ssh://svc:SYNTHETIC-SSH-SECRET@example.invalid/repo.git',token='')
        self.assertNotIn('SYNTHETIC-SSH-SECRET',result)
        self.assertIn('ssh://[auth-redacted]@example.invalid/repo.git',result)

    def test_exception_with_quoted_token_percent_encoded(self):
        encoded=urllib.parse.quote_plus(FAKE_TOKEN)
        self.assertNotIn(encoded,mask("TimeoutExpired cmd=['git', 'clone', '"+fake_https_remote(FAKE_USER+':'+encoded)+"']"))

if __name__=='__main__':unittest.main()
