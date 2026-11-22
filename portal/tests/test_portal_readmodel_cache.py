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
    def test_stale_while_revalidate_returns_stale_without_loader(self):
        self.rm.put('projects','discovered',[{'slug':'demo'}])
        con=sqlite3.connect(self.db);con.execute("update portal_readmodel_cache set updated_at=?",(time.time()-120,));con.commit();con.close()
        calls=[]
        with mock.patch.object(self.rm,'trigger_refresh',return_value=True) as refresh:
            value=self.rm.stale_while_revalidate('projects','discovered',30,600,lambda:calls.append(1) or [])
        self.assertEqual(value,[{'slug':'demo'}]);self.assertEqual(calls,[]);refresh.assert_called_once()

    def test_invalidate_prefix_only_removes_project_keys(self):
        self.rm.put('publication-project-context','a|',{'a':1});self.rm.put('publication-project-context','a|php',{'a':2});self.rm.put('publication-project-context','b|',{'b':1})
        self.rm.invalidate_prefix('publication-project-context','a|')
        self.assertIsNone(self.rm.get('publication-project-context','a|',60));self.assertIsNone(self.rm.get('publication-project-context','a|php',60));self.assertEqual(self.rm.get('publication-project-context','b|',60),{'b':1})

    def test_project_changed_records_event_and_invalidates_project(self):
        self.rm.put('project-runtime-state','demo',{'online':True});self.rm.put('publication-project-context','demo|',{'ok':True})
        with mock.patch.object(self.rm,'trigger_refresh',return_value=True):self.assertTrue(self.rm.project_changed('demo','runtime-stop'))
        self.assertIsNone(self.rm.get('project-runtime-state','demo',60));self.assertIsNone(self.rm.get('publication-project-context','demo|',60))
        con=sqlite3.connect(self.db);row=con.execute('select event_type,project_slug from portal_readmodel_events order by id desc limit 1').fetchone();con.close()
        self.assertEqual(row,('runtime-stop','demo'))

if __name__=='__main__':unittest.main()
