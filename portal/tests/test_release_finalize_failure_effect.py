import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_publications.py'


class ReleaseFinalizeFailureEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.db=Path(cls.tmp.name)/'portal.db'
        spec=importlib.util.spec_from_file_location('cloudiff_release_finalize_failure_effect',SOURCE)
        cls.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.m)
        cls.old_db=cls.m.DB;cls.old_validate=cls.m._validate_production_approval;cls.old_publish=cls.m.publish_homologated_candidate;cls.old_finalize=cls.m._finalize_production_approval;cls.old_approval_call=cls.m._approval_call
        cls.m.DB=cls.db

    @classmethod
    def tearDownClass(cls):
        cls.m.DB=cls.old_db;cls.m._validate_production_approval=cls.old_validate;cls.m.publish_homologated_candidate=cls.old_publish;cls.m._finalize_production_approval=cls.old_finalize;cls.m._approval_call=cls.old_approval_call;cls.tmp.cleanup()

    def setUp(self):
        if self.db.exists():self.db.unlink()
        con=sqlite3.connect(self.db);con.row_factory=sqlite3.Row
        con.execute('create table projects(slug text primary key,owner text,created_by text)')
        con.execute("insert into projects values('demo','alice','alice')")
        self.m._ensure_schema(con)
        self.approval='apr_'+'a'*20;self.digest='d'*64;self.reservation='res_'+'r'*32
        con.execute('''insert into production_activation_requests(project_slug,candidate_number,publication_number,activation_digest,approval_id,requested_by,status,created_at,updated_at)
                       values(?,?,?,?,?,?,?,?,?)''',('demo',7,3,self.digest,self.approval,'portal:alice','queued','2026-08-28T00:00:00Z','2026-08-28T00:00:00Z'))
        cur=con.execute('''insert into publication_jobs(project_slug,actor,status,step,message,created_at,operation,candidate_number,publication_number,environment,approval_id,activation_digest)
                           values(?,?,?,?,?,?,?,?,?,?,?,?)''',('demo','alice','running','preparing','P','2026-08-28T00:00:00Z','production_release',7,3,'production',self.approval,self.digest))
        self.job_id=int(cur.lastrowid);con.commit();con.close()
        self.publish_calls=[];self.finalize_calls=[];self.get_state='reserved'
        self.m._validate_production_approval=lambda *args: ({'candidate_number':7},self.reservation,self.digest)
        self.m.publish_homologated_candidate=self._publish
        self.m._finalize_production_approval=self._finalize
        self.m._approval_call=self._approval_call

    def _publish(self,slug,candidate_number,user,progress=None,publication_number=None):
        self.publish_calls.append((slug,candidate_number,publication_number,user.get('username')))
        return {'ok':True,'project':slug,'candidateNumber':candidate_number,'publicationNumber':publication_number,'stageCode':'P3','artifactImageId':'sha256:'+'7'*64,'sameArtifactAsHomologation':True}

    def _finalize(self,approval_id,reservation,success):
        self.finalize_calls.append((approval_id,reservation,success))
        if success:return 503,{'ok':False,'error':'synthetic_finalize_transport_failure'}
        return 200,{'ok':True,'status':'approved','released':True}

    def _approval_call(self,method,path,payload=None,timeout=45):
        if method=='GET' and path=='/v1/approvals?status=all':
            return 200,{'ok':True,'approvals':[{'approval_id':self.approval,'status':self.get_state,'reservation_id':self.reservation}]}
        raise AssertionError((method,path,payload))

    def _job(self):
        con=sqlite3.connect(self.db);con.row_factory=sqlite3.Row;row=dict(con.execute('select * from publication_jobs where id=?',(self.job_id,)).fetchone());con.close();return row

    def _activation(self):
        con=sqlite3.connect(self.db);row=con.execute('select status from production_activation_requests where approval_id=?',(self.approval,)).fetchone();con.close();return row[0]

    def test_lost_finalize_response_but_consumed_same_reservation_closes_as_success(self):
        self.get_state='consumed'
        result=self.m.run_job(self._job())
        self.assertIsNotNone(result)
        self.assertEqual(result['stageCode'],'P3')
        self.assertEqual(self.publish_calls,[('demo',7,3,'alice')])
        self.assertEqual(self.finalize_calls,[(self.approval,self.reservation,True)])
        job=self._job();self.assertEqual(job['status'],'succeeded');self.assertEqual(job['step'],'completed')
        self.assertEqual(self._activation(),'consumed')

    def test_finalize_still_reserved_after_publish_is_partial_not_failed_and_never_released(self):
        self.get_state='reserved'
        result=self.m.run_job(self._job())
        self.assertIsNotNone(result)
        self.assertFalse(result['ok'])
        self.assertEqual(result['status'],'deployed_unfinalized')
        self.assertEqual(result['publication']['stageCode'],'P3')
        self.assertEqual(self.publish_calls,[('demo',7,3,'alice')])
        self.assertEqual(self.finalize_calls,[(self.approval,self.reservation,True)])
        job=self._job();self.assertEqual(job['status'],'deployed_unfinalized');self.assertEqual(job['step'],'finalization_pending')
        self.assertEqual(self._activation(),'deployed_unfinalized')
        # A terminal partial job must never be claimed as a fresh publish.
        self.assertIsNone(self.m.claim_next_job())


if __name__=='__main__':unittest.main()
