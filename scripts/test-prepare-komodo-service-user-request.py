#!/usr/bin/env python3
import copy,importlib.util,json,unittest
from pathlib import Path
p=Path(__file__).with_name('prepare-komodo-service-user-request.py')
spec=importlib.util.spec_from_file_location('prepare',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
BASE=json.loads(m.MANIFEST.read_text())
class PayloadTests(unittest.TestCase):
 def test_public_request_schema(self):
  out=m.prepare(copy.deepcopy(BASE))
  self.assertEqual(out['method'],'POST')
  self.assertEqual(out['path'],'/write/CreateServiceUser')
  self.assertEqual(set(out['body']),{'username','description'})
  self.assertEqual(out['body']['username'],'svc-pgh-cloudiff')
  self.assertFalse(out['account_created'])
  self.assertFalse(out['api_key_created'])
 def test_does_not_include_secrets(self):
  out=m.prepare(copy.deepcopy(BASE));txt=json.dumps(out)
  for word in ('api_secret','password','private_key','X-Api-Key','bearer'):
   self.assertNotIn(word,txt)
 def test_rejects_active_or_unknown(self):
  for key,val in (('state','ACTIVE'),('verified_in_komodo',True),('identity','other')):
   a=copy.deepcopy(BASE);a[key]=val
   with self.assertRaises(ValueError):m.prepare(a)
 def test_rejects_write_scope(self):
  a=copy.deepcopy(BASE);a['target_scope']['base_level']='Write'
  with self.assertRaises(ValueError):m.prepare(a)
 def test_rejects_other_resources_read(self):
  a=copy.deepcopy(BASE);a['target_scope']['other_resources_default']='Read'
  with self.assertRaises(ValueError):m.prepare(a)
if __name__=='__main__':unittest.main(verbosity=1)
