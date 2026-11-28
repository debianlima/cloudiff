import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
READMODEL_PATH=ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_readmodel.py'
PANEL_PATH=ROOT/'components/control-plane/current-apps/portal-current/cloudif_approval_panel.py'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[name]=mod;spec.loader.exec_module(mod);return mod


def row(aid,status,slug='teste-sofa',created=1):
    return {'approval_id':aid,'project_slug':slug,'action':'deployment.production.activate',
            'status':status,'reason':'QA','created_at':created,'requested_by':'portal:owner'}


class ApprovalReadmodelIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.rm=load('rm_t046_'+self.temp.name.replace('/','_').replace('\\','_'),READMODEL_PATH)
        self.rm.DB=str(Path(self.temp.name)/'readmodel.db')
        self.panel=load('panel_t046_'+self.temp.name.replace('/','_').replace('\\','_'),PANEL_PATH)

    def test_background_refresh_updates_approval_index(self):
        from unittest import mock
        source=ROOT/'components/control-plane/usr/local/sbin/cloudif-portal-refresh-cache.py'
        with mock.patch.dict('os.environ',{'CLOUDIF_PORTAL_DB':str(Path(self.temp.name)/'portal.db')}):
            refresh=load('approval_background_refresh_test',source)
        rows=[row('a1','pending'),row('a2','consumed',created=2)]
        refresh.cache_approval_rows(self.rm,200,{'ok':True,'approvals':rows})
        self.assertEqual(self.rm.approval_index_counts(['teste-sofa']),{'pending':1,'approved':0,'history':1})
        self.assertEqual(len(self.rm.get('approvals','rows',60)),2)

    def test_background_refresh_failure_keeps_last_valid_index(self):
        from unittest import mock
        source=ROOT/'components/control-plane/usr/local/sbin/cloudif-portal-refresh-cache.py'
        with mock.patch.dict('os.environ',{'CLOUDIF_PORTAL_DB':str(Path(self.temp.name)/'portal.db')}):
            refresh=load('approval_background_refresh_failure_test',source)
        refresh.cache_approval_rows(self.rm,200,{'ok':True,'approvals':[row('a1','pending')]})
        refresh.cache_approval_rows(self.rm,503,{'ok':False})
        self.assertEqual(self.rm.approval_index_counts(['teste-sofa'])['pending'],1)

    def test_counts_and_pagination_are_normalized(self):
        self.rm.approval_index_replace([
            row('a1','pending',created=10),row('a2','pending_second',created=20),
            row('a3','approved',created=30),row('a4','consumed',created=40),
            row('a5','expired',created=50),row('a6','rejected',slug='outro',created=60)])
        counts=self.rm.approval_index_counts(['teste-sofa'])
        self.assertEqual(counts,{'pending':2,'approved':1,'history':2})
        page1=self.rm.approval_index_page(['teste-sofa'],exclude_statuses=list(self.rm.APPROVAL_LIVE_STATUSES),limit=1,offset=0)
        page2=self.rm.approval_index_page(['teste-sofa'],exclude_statuses=list(self.rm.APPROVAL_LIVE_STATUSES),limit=1,offset=1)
        self.assertEqual([x['approval_id'] for x in page1],['a5'])
        self.assertEqual([x['approval_id'] for x in page2],['a4'])
        live=self.rm.approval_index_page(['teste-sofa'],statuses=list(self.rm.APPROVAL_LIVE_STATUSES),limit=80)
        self.assertEqual([x['approval_id'] for x in live],['a3','a2','a1'])

    def test_index_is_replaced_and_scoped_by_slug(self):
        self.rm.approval_index_replace([row('a1','pending')])
        self.assertTrue(self.rm.approval_index_available())
        self.rm.approval_index_replace([row('b1','expired',slug='cpuhub',created=99)])
        self.assertEqual(self.rm.approval_index_counts(['teste-sofa']),{'pending':0,'approved':0,'history':0})
        self.assertEqual(self.rm.approval_index_counts(['cpuhub'])['history'],1)
        self.assertEqual(self.rm.approval_index_counts([]),{'pending':0,'approved':0,'history':0})

    def test_lazy_history_keeps_cards_out_of_first_render(self):
        rows=[self.panel.sanitize(row('apr_live','pending')),self.panel.sanitize(row('apr_old_a','expired',created=2)),self.panel.sanitize(row('apr_old_b','consumed',created=1))]
        html=self.panel.render(rows[:1],'csrf',False,[],actor_username='owner',history_total=2,history_lazy=True,counts={'pending':1,'approved':0,'history':2})
        self.assertIn('Carregar histórico (2)',html)
        self.assertIn('<dialog id="approval-history-dialog"',html)
        self.assertIn('data-endpoint="/cloudiff/portal/api/approvals?history=1"',html)
        self.assertIn('approval-history-more',html)
        self.assertNotIn('apr_old_a',html)
        self.assertNotIn('apr_old_b',html)
        self.assertIn('apr_live',html)
        self.assertIn('class="kpi">2<',html)

    def test_history_card_is_sanitized_and_complete(self):
        raw=row('apr_old','expired',created=1)
        raw['metadata_json']=json.dumps({'secret_token':'nunca-exibir','commit_sha':'abc123'})
        card=self.panel.history_card(self.panel.sanitize(raw))
        self.assertIn('apr_old',card)
        self.assertIn('abc123',card)
        self.assertNotIn('nunca-exibir',card)
        self.assertNotIn('Aprovar',card)

    def test_default_render_keeps_legacy_embedded_history(self):
        rows=[self.panel.sanitize(row('apr_old','expired'))]
        html=self.panel.render(rows,'csrf',False,[],actor_username='owner')
        self.assertIn('apr_old',html)
        self.assertIn('<dialog id="approval-history-dialog"',html)


if __name__=='__main__':
    unittest.main()
