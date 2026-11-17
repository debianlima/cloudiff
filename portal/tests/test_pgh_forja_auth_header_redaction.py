"""Synthetic credentials only; tests a local AST-extracted redactor."""
import ast,base64,pathlib,re,unittest,urllib
SOURCE=pathlib.Path(__file__).resolve().parents[2]/'components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py'
def redact(msg):
 f=[n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='_v119_mask']
 assert len(f)==1
 ns={'_v118_cfg':lambda k,d='':'FAKE_TOKEN' if 'TOKEN' in k else 'svc', 'urllib':urllib,'re':re}
 exec(compile(ast.Module(body=f,type_ignores=[]),str(SOURCE),'exec'),ns,ns)
 return ns['_v119_mask'](msg)
class TestAuthHeader(unittest.TestCase):
 def test_basic(self):
  secret=base64.b64encode(b'synthetic:credential').decode()
  out=redact('fatal: http.extraheader=Authorization: Basic '+secret)
  self.assertNotIn(secret,out);self.assertIn('Authorization: Basic [auth-redacted]',out)
 def test_bearer(self):
  secret='synthetic-BEARER-credential'
  out=redact('error Authorization: Bearer '+secret)
  self.assertNotIn(secret,out)
 def test_case_insensitive(self):
  self.assertNotIn('synthetic-credential',redact('authorization: bearer synthetic-credential'))
 def test_ordinary_errors_preserved(self):
  self.assertEqual(redact('fatal: unable to resolve example.invalid'),'fatal: unable to resolve example.invalid')
 def test_previous_url_mask_preserved(self):
  self.assertNotIn('synthetic-password',redact('fatal ' + 'https://' + 'svc:synthetic-password' + '@example.invalid/repo.git'))
if __name__=='__main__':unittest.main()
