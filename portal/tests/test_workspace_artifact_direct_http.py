from __future__ import annotations
import hashlib,http.client,importlib.util,json,os,sys,tempfile,threading,unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ.setdefault('CLOUDIF_WORKSPACE_TOKEN','test-broker-token')
DIR=ROOT/'components/control-plane/current-apps/workspace-broker-current'
sys.path.insert(0,str(DIR))
spec=importlib.util.spec_from_file_location('workspace_broker_direct_http',DIR/'cloudif-workspace-broker.py');B=importlib.util.module_from_spec(spec);assert spec.loader;sys.modules[spec.name]=B;spec.loader.exec_module(B)

class WorkspaceArtifactDirectHTTPTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.old_root=B.ARTIFACT_ROOT;self.old_token=B.TOKEN;B.ARTIFACT_ROOT=self.temp.name;B.TOKEN='test-broker-token'
  self.server=ThreadingHTTPServer(('127.0.0.1',0),B.H);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.port=self.server.server_port
 def tearDown(self):
  self.server.shutdown();self.server.server_close();B.ARTIFACT_ROOT=self.old_root;B.TOKEN=self.old_token;self.temp.cleanup()
 def json_post(self,path,payload,auth=True):
  body=json.dumps(payload,separators=(',',':')).encode();headers={'Content-Type':'application/json','Accept':'application/json'}
  if auth:headers['Authorization']='Bearer test-broker-token'
  c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=30);c.request('POST',path,body=body,headers=headers);r=c.getresponse();raw=r.read();c.close();return r.status,json.loads(raw)
 def test_ticket_status_and_exact_problem_size_direct_upload(self):
  size=1_390_970;raw=(bytes(range(256))*((size//256)+1))[:size];digest=hashlib.sha256(raw).hexdigest();aid=B.start_artifact(self.temp.name,'demo','archive.zip',size,digest,900)['artifact_id']
  code,data=self.json_post('/v1/artifact/ticket',{'project_slug':'demo','trace_id':'ticket-http-test','artifact_id':aid,'requested_by':'client-a','ttl_seconds':300});self.assertEqual(code,200);ticket=data['result']['upload_ticket']
  code,status=self.json_post('/v1/artifact/ticket/status',{'upload_ticket':ticket},auth=False);self.assertEqual(code,200);self.assertEqual(status['result']['upload_ticket_status'],'pending')
  c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=60);c.request('POST','/v1/artifact/direct-upload',body=raw,headers={'Content-Type':'application/octet-stream','Content-Length':str(size),'X-CloudIF-Upload-Ticket':ticket,'Accept':'application/json'});r=c.getresponse();result=json.loads(r.read());c.close()
  self.assertEqual(r.status,200);self.assertTrue(result['ok']);self.assertEqual(result['result']['sha256'],digest);self.assertEqual(result['result']['size'],size);self.assertEqual(result['result']['upload_transport'],'browser_direct')
  code,status=self.json_post('/v1/artifact/ticket/status',{'upload_ticket':ticket},auth=False);self.assertEqual(code,200);self.assertEqual(status['result']['upload_ticket_status'],'used')
  meta,loaded=B.read_artifact(self.temp.name,'demo',aid,digest,size);self.assertEqual(loaded,raw);self.assertEqual(meta['status'],'sealed')
 def test_direct_endpoints_are_loopback_only_by_contract(self):
  source=(DIR/'cloudif-workspace-broker.py').read_text();self.assertIn("self.client_address",source);self.assertIn("{'127.0.0.1','::1'}",source)

if __name__=='__main__':unittest.main()
