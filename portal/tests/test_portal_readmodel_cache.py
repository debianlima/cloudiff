import importlib.util,sqlite3,tempfile,time,unittest
from types import SimpleNamespace
from unittest import mock
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
MOD=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_readmodel.py'

class PortalReadModelCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=str(Path(self.tmp.name)/'portal.db')
        spec=importlib.util.spec_from_file_location('cloudif_portal_readmodel_test',MOD);self.rm=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.rm);self.rm.DB=self.db
    def tearDown(self):self.tmp.cleanup()
    def test_cached_loader_runs_once_until_invalidation(self):
        calls=[]
        def loader():calls.append(1);return {'items':[1,2,3]}
        self.assertEqual(self.rm.cached('projects','all',60,loader),{'items':[1,2,3]})
        self.assertEqual(self.rm.cached('projects','all',60,loader),{'items':[1,2,3]})
        self.assertEqual(len(calls),1)
        self.rm.invalidate('projects','all')
        self.rm.cached('projects','all',60,loader)
        self.assertEqual(len(calls),2)
    def test_expired_row_is_not_returned(self):
        self.rm.put('approvals','rows',[{'id':1}])
        con=sqlite3.connect(self.db);con.execute("update portal_readmodel_cache set updated_at=?",(time.time()-120,));con.commit();con.close()
        self.assertIsNone(self.rm.get('approvals','rows',8))
    def test_namespace_invalidation_does_not_delete_other_namespace(self):
        self.rm.put('projects','a',{'ok':1});self.rm.put('connectors','a',{'ok':2});self.rm.invalidate('projects')
        self.assertIsNone(self.rm.get('projects','a',60));self.assertEqual(self.rm.get('connectors','a',60),{'ok':2})
    def test_trigger_refresh_is_fail_safe(self):
        with mock.patch.object(self.rm.subprocess,'run',return_value=SimpleNamespace(returncode=0)):
            self.assertTrue(self.rm.trigger_refresh())
    def test_tenant_namespace_can_be_prewarmed(self):
        self.rm.put('tenants','registry',[{'tenant':'demo'}])
        self.assertEqual(self.rm.get('tenants','registry',90),[{'tenant':'demo'}])

if __name__=='__main__':unittest.main()
