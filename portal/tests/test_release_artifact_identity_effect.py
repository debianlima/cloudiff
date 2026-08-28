import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_publications.py'


class _Config:
    def environment_summary(self,slug,environment):
        assert slug=='demo' and environment=='production'
        return {'valid':True,'environmentRevision':4,'environmentDigest':'env-'+'4'*60}


class ReleaseArtifactIdentityEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.db=Path(cls.tmp.name)/'portal.db'
        spec=importlib.util.spec_from_file_location('cloudiff_release_artifact_identity_effect',SOURCE)
        cls.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.m)
        cls.old_db=cls.m.DB;cls.old_cfg=cls.m._publication_config;cls.old_approval=cls.m._approval_call;cls.old_publish=cls.m.publish_homologated_candidate
        cls.m.DB=cls.db;cls.m._publication_config=lambda:_Config()

    @classmethod
    def tearDownClass(cls):
        cls.m.DB=cls.old_db;cls.m._publication_config=cls.old_cfg;cls.m._approval_call=cls.old_approval;cls.m.publish_homologated_candidate=cls.old_publish;cls.tmp.cleanup()

    def setUp(self):
        if self.db.exists():self.db.unlink()
        con=sqlite3.connect(self.db);con.row_factory=sqlite3.Row
        con.executescript('''
          create table projects(slug text primary key,owner text,created_by text,status text);
          create table project_acl(slug text,subject_type text,subject text);
          insert into projects values('demo','alice','alice','active');
        ''')
        self.m._ensure_schema(con)
        self.artifact_a='sha256:'+'a'*64;self.artifact_b='sha256:'+'b'*64;self.approval='apr_'+'c'*20
        con.execute('''insert into publication_candidates(
          project_slug,public_number,candidate_number,deploy_number,preview_generation,stage_code,hostname,status,
          parent_commit,commit_sha,artifact_image,artifact_image_id,diff_json,runtime_diff_json,
          environment_revision,environment_digest,created_by,created_at,homologated_by,homologated_at
        ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
          'demo',42,7,7,2,'H7','42-h7-homologation.cloudiff.duckdns.org','homologated',
          'parent','commit7','cloudif/demo:h7',self.artifact_a,'{}','{}',3,'env-h','alice','2026-08-27T22:00:00Z','alice','2026-08-27T22:10:00Z'))
        candidate=con.execute('select * from publication_candidates where project_slug=? and candidate_number=?',('demo',7)).fetchone()
        self.material,self.digest=self.m._production_activation_material('demo',candidate,3,_Config().environment_summary('demo','production'))
        con.execute('''insert into production_activation_requests(
          project_slug,candidate_number,publication_number,activation_digest,approval_id,requested_by,status,created_at,updated_at
        ) values(?,?,?,?,?,?,?,?,?)''',('demo',7,3,self.digest,self.approval,'portal:alice','approved','2026-08-27T22:11:00Z','2026-08-27T22:11:00Z'))
        cur=con.execute("""insert into publication_jobs(
          project_slug,actor,status,step,message,created_at,operation,candidate_number,publication_number,environment,approval_id,activation_digest
        ) values(?,?,?,?,?,?,?,?,?,?,?,?)""",('demo','alice','queued','queued','P','2026-08-27T22:12:00Z','production_release',7,3,'production',self.approval,self.digest))
        self.job_id=int(cur.lastrowid);con.commit();con.close()
        self.approval_calls=[];self.publish_calls=[]
        self.m._approval_call=self._approval_call
        self.m.publish_homologated_candidate=self._publish

    def _approval_record(self,metadata=None):
        data=dict(self.material);data.update({'activationDigest':self.digest,'content_stored':False,'secret_values_in_metadata':False,'artifact_content_stored':False})
        if metadata:data.update(metadata)
        return {'approval_id':self.approval,'status':'approved','project_slug':'demo','action':'deployment.production.activate','requested_by':'portal:alice','approved_by':'professor','metadata_json':json.dumps(data,separators=(',',':'))}

    def _approval_call(self,method,path,payload=None,timeout=45):
        self.approval_calls.append((method,path,payload))
        if method=='GET':return 200,{'ok':True,'approvals':[self._approval_record()]}
        if path.endswith('/reserve'):return 200,{'ok':True,'status':'reserved'}
        if path.endswith('/finalize'):return 200,{'ok':True,'status':'consumed'}
        if path.endswith('/release'):return 200,{'ok':True,'status':'approved'}
        raise AssertionError((method,path,payload))

    def _publish(self,slug,candidate_number,user,progress=None,publication_number=None):
        self.publish_calls.append((slug,candidate_number,publication_number,user.get('username')))
        return {'ok':True,'stageCode':'P3','artifactImageId':self.artifact_a,'sameArtifactAsHomologation':True}

    def _job(self):
        con=sqlite3.connect(self.db);con.row_factory=sqlite3.Row;row=dict(con.execute('select * from publication_jobs where id=?',(self.job_id,)).fetchone());con.close();return row

    def _activation(self):
        con=sqlite3.connect(self.db);row=con.execute('select status from production_activation_requests where approval_id=?',(self.approval,)).fetchone();con.close();return row[0]

    def test_worker_publishes_only_when_approved_artifact_identity_is_unchanged(self):
        result=self.m.run_job(self._job())
        self.assertEqual(result['artifactImageId'],self.artifact_a)
        self.assertTrue(result['sameArtifactAsHomologation'])
        self.assertEqual(self.publish_calls,[('demo',7,3,'alice')])
        paths=[x[1] for x in self.approval_calls]
        self.assertTrue(any(x.endswith('/reserve') for x in paths));self.assertTrue(any(x.endswith('/finalize') for x in paths))
        job=self._job();self.assertEqual(job['status'],'succeeded');self.assertEqual(job['step'],'completed')
        self.assertEqual(self._activation(),'consumed')

    def test_artifact_change_after_approval_fails_before_publish_or_reservation(self):
        con=sqlite3.connect(self.db);con.execute('update publication_candidates set artifact_image_id=? where project_slug=? and candidate_number=?',(self.artifact_b,'demo',7));con.commit();con.close()
        result=self.m.run_job(self._job())
        self.assertIsNone(result)
        self.assertEqual(self.publish_calls,[])
        self.assertEqual(self.approval_calls,[])
        job=self._job();self.assertEqual(job['status'],'failed');self.assertEqual(job['step'],'failed')
        detail=json.loads(job['detail_json']);self.assertEqual(detail['error'],'PermissionError');self.assertIn('approval_binding_mismatch',detail['message'])
        self.assertEqual(self._activation(),'approved')


if __name__=='__main__':unittest.main()
