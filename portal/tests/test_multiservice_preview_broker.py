from __future__ import annotations
import importlib.util,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
MODULE_PATH=ROOT/'components/control-plane/current-apps/multiservice-preview-current/cloudif-multiservice-preview-broker.py'
UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-multiservice-preview-broker.service'
class PreviewBrokerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();os.environ['CLOUDIF_MULTISERVICE_PREVIEW_DB']=str(Path(cls.temp.name)/'broker.db')
  spec=importlib.util.spec_from_file_location('preview_broker_test',MODULE_PATH);cls.m=importlib.util.module_from_spec(spec);assert spec.loader;sys.modules[spec.name]=cls.m;spec.loader.exec_module(cls.m);cls.m.init_db()
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def build(self):
  return {'ok':True,'status':'succeeded','result':{'ok':True,'projectSlug':'project-a','planDigest':'1'*64,'configRevision':3,'configDigest':'2'*64,'archiveSha256':'3'*64,'applications':[{'service':'web','runtime':'static','containerPort':8080,'healthcheck':'/','applicationDigest':'4'*64,'image':{'imageId':'sha256:'+'5'*64,'immutableReference':'sha256:'+'5'*64}},{'service':'api','runtime':'node','containerPort':3000,'healthcheck':'/health','applicationDigest':'6'*64,'image':{'imageId':'sha256:'+'7'*64,'immutableReference':'sha256:'+'7'*64}}]}}
 def test_default_plan_has_root_api_routes_and_digest(self):
  with patch.object(self.m,'build_status',return_value=self.build()):plan=self.m.preview_plan({'build_job_id':'build_'+'8'*24,'ttl_seconds':900})
  self.assertTrue(plan['side_effect_free']);self.assertTrue(plan['approval_required']);self.assertEqual(len(plan['preview_plan_digest']),64);self.assertEqual(plan['routes'][0]['pathPrefix'],'/api');self.assertEqual(plan['routes'][-1]['pathPrefix'],'/');self.assertFalse(plan['security']['secretsIncluded'])
 def test_plan_rejects_unready_build_and_invalid_routes(self):
  with patch.object(self.m,'build_status',side_effect=self.m.BrokerError('build_not_ready','not ready',409)):
   with self.assertRaisesRegex(self.m.BrokerError,'build_not_ready'):self.m.preview_plan({'build_job_id':'build_'+'8'*24})
  with patch.object(self.m,'build_status',return_value=self.build()):
   with self.assertRaisesRegex(self.m.BrokerError,'root_route_required'):self.m.preview_plan({'build_job_id':'build_'+'8'*24,'routes':[{'pathPrefix':'/api','service':'api'}]})
 def test_acl_allows_creator_and_admin_only(self):
  class Row(dict):__getattr__=dict.get
  row={'created_by':'alice'}
  self.assertTrue(self.m.authorized(row,'alice',[]));self.assertTrue(self.m.authorized(row,'bob',['CloudIF-Tenants-Admin']));self.assertFalse(self.m.authorized(row,'bob',['Domain Users']))
 def test_public_url_stays_under_authenticated_portal(self):
  with patch.object(self.m,'build_status',return_value=self.build()):plan=self.m.preview_plan({'build_job_id':'build_'+'8'*24})
  self.assertIn('/cloudiff/portal/preview/{preview_id}/',plan['public_url_template'])
  self.assertNotIn('10.62.91.2',plan['public_url_template'])
 def test_source_does_not_store_secrets_or_build_payload(self):
  source=MODULE_PATH.read_text();self.assertIn('secret_values_in_metadata',Path('components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py').read_text());self.assertNotIn('services_json',source);self.assertNotIn('payload_json',source)
 def test_unit_binds_localhost_and_calls_private_executor(self):
  unit=UNIT.read_text();self.assertIn('CLOUDIF_MULTISERVICE_PREVIEW_HOST=127.0.0.1',unit);self.assertIn('CLOUDIF_PREVIEW_EXECUTOR_URL=http://10.62.91.2:18227',unit);self.assertIn('IPAddressDeny=any',unit)
if __name__=='__main__':unittest.main()
