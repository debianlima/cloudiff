from __future__ import annotations
import importlib.util,json,os,sys,tempfile,threading,unittest,urllib.error,urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
APPROVAL_DIR=ROOT/'components/control-plane/current-apps/approvals-current';API=APPROVAL_DIR/'cloudif-approval-api.py'

def load_api(root:Path):
 os.environ['CLOUDIF_APPROVAL_DB']=str(root/'approvals.db');os.environ['CLOUDIF_APPROVAL_TOKEN']='test-token';sys.path.insert(0,str(APPROVAL_DIR));name='approval_cancel_'+root.name.replace('-','_');spec=importlib.util.spec_from_file_location(name,API);module=importlib.util.module_from_spec(spec);assert spec.loader;sys.modules[name]=module;spec.loader.exec_module(module);return module

class ApprovalCancelTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.module=load_api(Path(self.temp.name));self.server=ThreadingHTTPServer(('127.0.0.1',0),self.module.H);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base=f'http://127.0.0.1:{self.server.server_port}'
 def tearDown(self):self.server.shutdown();self.server.server_close();self.temp.cleanup()
 def call(self,method,path,payload=None):
  data=None if payload is None else json.dumps(payload,separators=(',',':')).encode();req=urllib.request.Request(self.base+path,data=data,method=method,headers={'Authorization':'Bearer test-token','Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(req,timeout=5) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def create(self,requested_by='agent-a',action='forgejo.propose-change-set'):
  return self.call('POST','/v1/approvals',{'project_slug':'demo','action':action,'requested_by':requested_by,'requester_role':'agent','ttl_seconds':900,'reason':'Revisar proposta corrigida','metadata':{'workspace_id':'ws_'+'1'*24}})
 def test_requester_can_cancel_pending_and_create_corrected_request(self):
  code,first=self.create();self.assertEqual(code,201);self.assertEqual(first['status'],'pending')
  code,cancelled=self.call('POST',f"/v1/approvals/{first['approval_id']}/cancel",{'requested_by':'agent-a','cancellation_reason':'Snapshot substituído por versão corrigida.'});self.assertEqual(code,200);self.assertEqual(cancelled['status'],'cancelled');self.assertFalse(cancelled['idempotent'])
  code,again=self.call('POST',f"/v1/approvals/{first['approval_id']}/cancel",{'requested_by':'agent-a','cancellation_reason':'Snapshot substituído por versão corrigida.'});self.assertEqual(code,200);self.assertTrue(again['idempotent'])
  code,second=self.create();self.assertEqual(code,201);self.assertEqual(second['status'],'pending');self.assertNotEqual(first['approval_id'],second['approval_id'])
 def test_other_requester_cannot_cancel(self):
  _,first=self.create();code,result=self.call('POST',f"/v1/approvals/{first['approval_id']}/cancel",{'requested_by':'agent-b','cancellation_reason':'Tentar cancelar aprovação alheia.'});self.assertEqual(code,409);self.assertEqual(result['error'],'approval_requester_mismatch')
 def test_approved_request_cannot_be_cancelled(self):
  _,first=self.create();code,approved=self.call('POST',f"/v1/approvals/{first['approval_id']}/approve",{'approved_by':'reviewer','approver_role':'human'});self.assertEqual(code,200);self.assertEqual(approved['status'],'approved')
  code,result=self.call('POST',f"/v1/approvals/{first['approval_id']}/cancel",{'requested_by':'agent-a','cancellation_reason':'Não deve cancelar aprovação já aprovada.'});self.assertEqual(code,409);self.assertEqual(result['error'],'approval_not_cancellable')
 def test_pending_second_can_be_cancelled_and_policy_request_removed(self):
  _,first=self.create(action='deployment.production.activate');aid=first['approval_id']
  code,step=self.call('POST',f'/v1/approvals/{aid}/approve',{'approved_by':'admin-a','approver_role':'admin','always_allow':True});self.assertEqual(code,200);self.assertEqual(step['status'],'pending_second')
  code,cancelled=self.call('POST',f'/v1/approvals/{aid}/cancel',{'requested_by':'agent-a','cancellation_reason':'Fluxo substituído antes da segunda aprovação.'});self.assertEqual(code,200);self.assertEqual(cancelled['status'],'cancelled')
  con=self.module.c();count=con.execute('select count(*) from approval_policy_requests where approval_id=?',(aid,)).fetchone()[0];con.close();self.assertEqual(count,0)

if __name__=='__main__':unittest.main()
