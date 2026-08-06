from __future__ import annotations
import importlib.util,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
MODULE_PATH=ROOT/'components/runtime/current-apps/multiservice-preview-executor-current/cloudif-multiservice-preview-executor.py'
UNIT=ROOT/'components/runtime/etc/systemd/system/cloudif-multiservice-preview-executor.service'

class PreviewExecutorTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();os.environ['CLOUDIF_PREVIEW_EXECUTOR_DB']=str(Path(cls.temp.name)/'preview.db')
  spec=importlib.util.spec_from_file_location('preview_executor_test',MODULE_PATH);cls.m=importlib.util.module_from_spec(spec);assert spec.loader;sys.modules[spec.name]=cls.m;spec.loader.exec_module(cls.m);cls.m.init_db()
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def payload(self):
  return {'preview_id':'pv_'+'1'*24,'project_slug':'project-a','build_job_id':'build_'+'2'*24,'plan_digest':'3'*64,'config_revision':1,'archive_sha256':'4'*64,'applications':[{'service':'web','image_id':'sha256:'+'5'*64,'application_digest':'6'*64,'port':8080,'healthcheck':'/'},{'service':'api','image_id':'sha256:'+'7'*64,'application_digest':'8'*64,'port':3000,'healthcheck':'/health'}],'routes':[{'pathPrefix':'/api','service':'api','stripPrefix':True},{'pathPrefix':'/','service':'web','stripPrefix':False}],'ttl_seconds':900}
 def test_payload_requires_immutable_images_routes_and_ttl(self):
  result=self.m.normalize_payload(self.payload());self.assertEqual(len(result['applications']),2);self.assertEqual(result['routes'][0]['pathPrefix'],'/api')
  bad=self.payload();bad['applications'][0]['image_id']='cloudif/app:latest'
  with self.assertRaisesRegex(self.m.PreviewError,'invalid_image_id'):self.m.normalize_payload(bad)
  bad=self.payload();bad['ttl_seconds']=30
  with self.assertRaisesRegex(self.m.PreviewError,'invalid_ttl'):self.m.normalize_payload(bad)
 def test_root_route_duplicate_port_and_path_escape_are_rejected(self):
  bad=self.payload();bad['routes']=[{'pathPrefix':'/api','service':'api'}]
  with self.assertRaisesRegex(self.m.PreviewError,'root_route_required'):self.m.normalize_payload(bad)
  bad=self.payload();bad['routes'][0]['pathPrefix']='/../api'
  with self.assertRaisesRegex(self.m.PreviewError,'invalid_route_prefix'):self.m.normalize_payload(bad)
 def test_image_labels_bind_project_service_revision_archive_and_app_digest(self):
  request=self.m.normalize_payload(self.payload());app=request['applications'][0]
  labels={'org.cloudiff.kind':'application','org.cloudiff.project':'project-a','org.cloudiff.service':'web','org.cloudiff.config-revision':'1','org.cloudiff.archive-sha256':'4'*64,'org.cloudiff.application-digest':'6'*64}
  image={'Id':app['image_id'],'Config':{'User':'65532:65532','Labels':labels}}
  with patch.object(self.m,'inspect_image',return_value=image):
   result=self.m.validate_image_labels(request,app);self.assertEqual(result['user'],'65532:65532')
  labels['org.cloudiff.archive-sha256']='0'*64
  with patch.object(self.m,'inspect_image',return_value=image):
   with self.assertRaisesRegex(self.m.PreviewError,'image_label_mismatch'):self.m.validate_image_labels(request,app)
 def test_route_uses_longest_prefix_and_strip(self):
  import sqlite3,json,time
  conn=self.m.db();conn.execute('delete from previews');conn.execute('insert into previews values(?,?,?,?,?,?,?,?,?,?,?,?,?)',('pv_'+'1'*24,'project-a','build_'+'2'*24,'3'*64,1,'4'*64,'running',json.dumps([{'service':'web','host_port':41000},{'service':'api','host_port':41001}]),json.dumps([{'pathPrefix':'/api','service':'api','stripPrefix':True},{'pathPrefix':'/','service':'web','stripPrefix':False}]),'{}',int(time.time()),int(time.time())+900,int(time.time())));conn.commit();row=conn.execute('select * from previews').fetchone();conn.close()
  service,target=self.m.route_target(row,'/api/health');self.assertEqual(service['service'],'api');self.assertEqual(target,'/health')
  service,target=self.m.route_target(row,'/assets/app.js');self.assertEqual(service['service'],'web');self.assertEqual(target,'/assets/app.js')
 def test_source_enforces_internal_network_loopback_readonly_and_cleanup(self):
  source=MODULE_PATH.read_text()
  for marker in ("'network','create','--internal'","'--read-only'","'--cap-drop','ALL'","'no-new-privileges'","'127.0.0.1::",'expire_loop','ttlCleanup','portsLoopbackOnly'):
   self.assertIn(marker,source)
  self.assertNotIn('0.0.0.0::',source)
 def test_proxy_drops_cookie_authorization_and_set_cookie(self):
  source=MODULE_PATH.read_text()
  self.assertNotIn("'cookie'",source[source.index('REQUEST_HEADERS='):source.index('RESPONSE_HEADERS=')])
  self.assertNotIn("'authorization'",source[source.index('REQUEST_HEADERS='):source.index('RESPONSE_HEADERS=')])
  self.assertIn("'set-cookie'",source[source.index('HOP_HEADERS='):source.index('class PreviewError')])
 def test_systemd_is_internal_and_hardened(self):
  unit=UNIT.read_text()
  for marker in ('CLOUDIF_MULTISERVICE_PREVIEW_EXECUTOR_HOST=10.62.91.2','SupplementaryGroups=docker','NoNewPrivileges=true','ProtectSystem=strict','CapabilityBoundingSet=','IPAddressDeny=any'):
   self.assertIn(marker,unit)

if __name__=='__main__':unittest.main()
