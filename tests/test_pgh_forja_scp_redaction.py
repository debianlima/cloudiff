"""Synthetic credentials only; no runtime secret access."""
import ast
import pathlib
import re
import unittest
import urllib.parse

SOURCE=pathlib.Path(__file__).resolve().parents[1]/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py'

def mask(value):
    fn=[x for x in ast.parse(SOURCE.read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='_v119_mask']
    assert len(fn)==1
    ns={'_v118_cfg':lambda key,default='':'','urllib':urllib,'re':re}
    exec(compile(ast.Module(body=fn,type_ignores=[]),str(SOURCE),'exec'),ns,ns)
    return ns['_v119_mask'](value)

class ScpCredentialTests(unittest.TestCase):
    def test_scp_like_embedded_credential_is_redacted(self):
        msg='fatal: svc:FAKESECRET@example.invalid:group/repo.git'
        result=mask(msg)
        self.assertNotIn('FAKESECRET',result)
        self.assertIn('example.invalid:group/repo.git',result)
    def test_standard_scp_user_remote_preserved(self):
        msg='fatal: git@example.invalid:group/repo.git'
        self.assertEqual(mask(msg),msg)
    def test_plain_colon_at_text_preserved(self):
        msg='Diagnostic a:b@example.invalid without repository suffix'
        self.assertEqual(mask(msg),msg)
    def test_http_userinfo_still_redacted(self):
        result=mask('fatal: https://svc:FAKESECRET@example.invalid/group/repo.git')
        self.assertNotIn('FAKESECRET',result)
    def test_no_credentials_in_regular_error(self):
        msg='fatal: repository not found'
        self.assertEqual(mask(msg),msg)

if __name__=='__main__':unittest.main()
