from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
LIB=ROOT/'components/control-plane/srv/cloudif/lib'
sys.path.insert(0,str(LIB))


class PublicationPermissionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/'portal.db'
        self.con=sqlite3.connect(self.db)
        self.con.row_factory=sqlite3.Row
        self.con.executescript('''
        create table projects(slug text primary key,owner text,created_by text);
        create table project_acl(id integer primary key autoincrement,slug text,subject_type text,subject text);
        insert into projects values('demo','alice','alice');
        insert into project_acl(slug,subject_type,subject) values('demo','user','alice');
        insert into project_acl(slug,subject_type,subject) values('demo','user','bob');
        insert into project_acl(slug,subject_type,subject) values('demo','user','carol');
        ''')

    def tearDown(self):
        self.con.close(); self.tmp.cleanup()

    def module(self):
        import cloudif_publication_permissions as permissions
        permissions.ensure_schema(self.con)
        return permissions

    def user(self,username,groups=(),admin=False):
        return {'username':username,'groups':list(groups),'admin':admin}

    def test_admin_professor_and_owner_have_implicit_release_permissions(self):
        p=self.module()
        admin=self.user('root',['CloudIF-Tenants-Admin'])
        professor=self.user('teacher',['CloudIF-Professor'])
        owner=self.user('alice')
        for user in (admin,professor,owner):
            self.assertTrue(p.can_homologate(self.con,'demo',user))
            self.assertTrue(p.can_publish(self.con,'demo',user))
        self.assertTrue(p.can_manage_permissions(admin))
        self.assertTrue(p.can_manage_permissions(professor))
        self.assertFalse(p.can_manage_permissions(owner))

    def test_member_requires_explicit_homologate_or_publish_grant(self):
        p=self.module(); bob=self.user('bob'); professor=self.user('teacher',['CloudIF-Professor'])
        self.assertFalse(p.can_homologate(self.con,'demo',bob))
        self.assertFalse(p.can_publish(self.con,'demo',bob))
        p.set_permissions(self.con,'demo',professor,[{'username':'bob','homologate':True,'publish':False}])
        self.assertTrue(p.can_homologate(self.con,'demo',bob))
        self.assertFalse(p.can_publish(self.con,'demo',bob))
        p.set_permissions(self.con,'demo',professor,[{'username':'bob','homologate':True,'publish':True}])
        self.assertTrue(p.can_publish(self.con,'demo',bob))

    def test_only_explicit_project_members_can_be_delegated(self):
        p=self.module(); professor=self.user('teacher',['CloudIF-Professor'])
        with self.assertRaisesRegex(PermissionError,'vinculado ao projeto'):
            p.set_permissions(self.con,'demo',professor,[{'username':'mallory','homologate':True,'publish':True}])

    def test_permission_snapshot_lists_project_users_and_locked_owner(self):
        p=self.module(); professor=self.user('teacher',['CloudIF-Professor'])
        p.set_permissions(self.con,'demo',professor,[{'username':'bob','homologate':True,'publish':False}])
        snap=p.snapshot(self.con,'demo',professor)
        self.assertTrue(snap['canManagePermissions'])
        rows={row['username']:row for row in snap['users']}
        self.assertEqual(set(rows),{'alice','bob','carol','teacher'})
        self.assertTrue(rows['alice']['locked'])
        self.assertTrue(rows['alice']['homologate'])
        self.assertTrue(rows['alice']['publish'])
        self.assertTrue(rows['bob']['homologate'])
        self.assertFalse(rows['bob']['publish'])
        self.assertEqual(rows['teacher']['source'],'Professor')
        self.assertTrue(rows['teacher']['locked'])

    def test_professor_cannot_remove_admin_or_profile_defaults(self):
        p=self.module(); professor=self.user('teacher',['CloudIF-Professor'])
        # Profile defaults are implicit and never represented as removable grants.
        p.set_permissions(self.con,'demo',professor,[])
        self.assertTrue(p.can_homologate(self.con,'demo',professor))
        self.assertTrue(p.can_publish(self.con,'demo',professor))
        admin=self.user('root',['CloudIF-Tenants-Admin'])
        self.assertTrue(p.can_homologate(self.con,'demo',admin))
        self.assertTrue(p.can_publish(self.con,'demo',admin))

    def test_stale_legacy_grant_is_inert_when_user_is_no_longer_project_member(self):
        p=self.module()
        self.con.execute('create table if not exists project_homologators(project_slug text,username text,created_by text,created_at text,primary key(project_slug,username))')
        self.con.execute("insert into project_homologators values('demo','mallory','legacy','2026-09-09T00:00:00Z')")
        self.con.execute("delete from publication_permission_migrations where name='legacy_homologators_v1'")
        self.con.commit(); p.ensure_schema(self.con); self.con.commit()
        self.assertFalse(p.can_homologate(self.con,'demo',self.user('mallory')))
        self.assertFalse(p.can_publish(self.con,'demo',self.user('mallory')))
        snap=p.snapshot(self.con,'demo',self.user('alice'))
        self.assertNotIn('mallory',{row['username'] for row in snap['users']})

    def test_removed_legacy_homologator_does_not_reappear_after_schema_check(self):
        p=self.module(); professor=self.user('teacher',['CloudIF-Professor'])
        self.con.execute('create table if not exists project_homologators(project_slug text,username text,created_by text,created_at text,primary key(project_slug,username))')
        self.con.execute("insert into project_homologators(project_slug,username,created_by,created_at) values('demo','bob','legacy','2026-09-09T00:00:00Z')")
        self.con.execute("delete from publication_permission_migrations where name='legacy_homologators_v1'")
        self.con.commit(); p.ensure_schema(self.con); self.con.commit()
        self.assertTrue(p.can_homologate(self.con,'demo',self.user('bob')))
        p.set_permissions(self.con,'demo',professor,[])
        self.assertFalse(p.can_homologate(self.con,'demo',self.user('bob')))
        p.ensure_schema(self.con); self.con.commit()
        self.assertFalse(p.can_homologate(self.con,'demo',self.user('bob')))
        self.assertEqual(self.con.execute("select count(*) from project_homologators where project_slug='demo'").fetchone()[0],0)

    def test_authorized_member_enqueues_direct_production_without_generic_approval(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('cloudif_portal_publications_under_test',ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_publications.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.DB=self.db
        module._ensure_schema(self.con);self.con.commit()
        p=self.module();professor=self.user('teacher',['CloudIF-Professor'])
        p.set_permissions(self.con,'demo',professor,[{'username':'bob','homologate':True,'publish':True}])
        now='2026-09-10T00:00:00Z'
        self.con.execute("insert into project_public_ids(project_slug,public_number,created_at,updated_at) values('demo',1011,?,?)",(now,now))
        self.con.execute("""insert into publication_candidates(
          project_slug,public_number,candidate_number,deploy_number,preview_generation,stage_code,hostname,status,parent_commit,commit_sha,
          artifact_image,artifact_image_id,diff_json,runtime_diff_json,environment_revision,environment_digest,created_by,created_at,homologated_by,homologated_at
        ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          ('demo',1011,3,3,1,'H3','1011-h3-homologation.cloudiff.duckdns.org','homologated','parent','a'*40,'img','sha256:'+'b'*64,'{}','{}',0,'env','alice',now,'alice',now))
        self.con.commit()
        class Config:
            @staticmethod
            def environment_summary(slug,environment='production'):
                return {'valid':True,'environmentRevision':7,'environmentDigest':'c'*64}
        module._publication_config=lambda:Config
        result=module.enqueue_authorized_publication('demo',3,self.user('bob'))
        self.assertTrue(result['queued'])
        self.assertEqual(result['authorizationMode'],'project_permission')
        self.assertEqual(result['authorizationRole'],'delegated')
        row=self.con.execute('select authorization_mode,authorization_role,approval_id,activation_digest,status from publication_jobs where id=?',(result['job_id'],)).fetchone()
        self.assertEqual(row['authorization_mode'],'project_permission')
        self.assertEqual(row['authorization_role'],'delegated')
        self.assertEqual(row['approval_id'],'')
        self.assertEqual(len(row['activation_digest']),64)
        self.assertEqual(self.con.execute('select count(*) from production_activation_requests').fetchone()[0],0)
        module._validate_project_permission_job('demo',3,result['publicationNumber'],row['activation_digest'])

    def test_direct_publish_supersedes_and_cancels_pending_generic_approval(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('cloudif_portal_publications_cancel_test',ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_publications.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.DB=self.db
        module._ensure_schema(self.con);self.con.commit()
        p=self.module();professor=self.user('teacher',['CloudIF-Professor'])
        now='2026-09-10T00:00:00Z'
        self.con.execute("insert into project_public_ids(project_slug,public_number,created_at,updated_at) values('demo',1011,?,?)",(now,now))
        self.con.execute("""insert into publication_candidates(
          project_slug,public_number,candidate_number,deploy_number,preview_generation,stage_code,hostname,status,parent_commit,commit_sha,
          artifact_image,artifact_image_id,diff_json,runtime_diff_json,environment_revision,environment_digest,created_by,created_at,homologated_by,homologated_at
        ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          ('demo',1011,3,3,1,'H3','1011-h3-homologation.cloudiff.duckdns.org','homologated','parent','a'*40,'img','sha256:'+'b'*64,'{}','{}',0,'env','alice',now,'alice',now))
        self.con.execute("""insert into production_activation_requests(
          project_slug,candidate_number,publication_number,activation_digest,approval_id,requested_by,status,created_at,updated_at
        ) values('demo',3,2,?,'apr_1234567890abcdef1234','portal:alice','pending',?,?)""",('d'*64,now,now))
        self.con.execute("""insert into production_activation_requests(
          project_slug,candidate_number,publication_number,activation_digest,approval_id,requested_by,status,created_at,updated_at
        ) values('demo',2,1,?,'apr_abcdef1234567890abcd','portal:alice','pending',?,?)""",('e'*64,now,now))
        self.con.commit()
        class Config:
            @staticmethod
            def environment_summary(slug,environment='production'):
                return {'valid':True,'environmentRevision':7,'environmentDigest':'c'*64}
        module._publication_config=lambda:Config
        calls=[]
        module._approval_call=lambda method,path,payload=None,timeout=45: (calls.append((method,path,payload)) or (200,{'ok':True,'status':'cancelled'}))
        result=module.enqueue_authorized_publication('demo',3,professor)
        self.assertEqual(result['authorizationMode'],'project_permission')
        self.assertEqual(len(calls),2)
        self.assertTrue(calls[0][1].endswith('/cancel'))
        self.assertEqual(calls[0][2]['requested_by'],'portal:alice')
        self.assertEqual(self.con.execute("select status from production_activation_requests where approval_id='apr_1234567890abcdef1234'").fetchone()[0],'superseded')
        self.assertEqual(self.con.execute("select status from production_activation_requests where approval_id='apr_abcdef1234567890abcd'").fetchone()[0],'superseded')
        portal=(ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_publications.py').read_text()
        self.assertIn("status<>'superseded'",portal)

    def test_worker_authorization_does_not_require_reconstructing_admin_or_professor_groups(self):
        portal=(ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_publications.py').read_text()
        start=portal.index('def publish_homologated_candidate(')
        end=portal.index('def rollback_publication',start)
        block=portal[start:end]
        self.assertIn("project=con.execute('select * from projects where slug=?',(slug,)).fetchone() if authorization_checked else _project_allowed",block)
        worker=portal[portal.index('def run_job(job):'):portal.index('def set_alias',portal.index('def run_job(job):'))]
        self.assertIn('authorization_checked=True',worker)
        self.assertNotIn("user['admin']=True",worker)

    def test_worker_claim_commits_schema_migration_before_begin_immediate(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('cloudif_portal_publications_claim_test',ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        db=Path(self.tmp.name)/'claim-worker.db'
        module.DB=db
        self.assertIsNone(module.claim_next_job())
        con=sqlite3.connect(db)
        try:
            row=con.execute("select applied_at from publication_permission_migrations where name='legacy_homologators_v1'").fetchone()
            self.assertIsNotNone(row)
        finally:
            con.close()

    def test_release_backend_uses_project_permission_jobs_without_worker_privilege_escalation(self):
        portal=(ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_publications.py').read_text()
        coexist=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py').read_text()
        self.assertIn('def enqueue_authorized_publication(',portal)
        self.assertIn("'project_permission'",portal)
        self.assertIn('authorization_mode',portal)
        self.assertIn('authorization_checked=True',portal)
        self.assertNotIn("user['admin']=True",portal[portal.index('def run_job(job):'):portal.index('def set_alias',portal.index('def run_job(job):'))])
        self.assertIn("operation=='production/publish'",coexist)
        self.assertIn("operation=='permissions'",coexist)
        self.assertIn("'admin':'cloudif-tenants-admin' in lower,'professor':'cloudif-professor' in lower",coexist)
        self.assertNotIn("bool(lower.intersection({'cloudif-tenants-admin','cloudif-professor'}))",coexist[coexist.index('release_flow_match = re.fullmatch'):coexist.index('environments_match',coexist.index('release_flow_match = re.fullmatch'))])

    def test_release_status_exposes_distinct_capabilities(self):
        portal=(ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_publications.py').read_text()
        for marker in ('canSubmitHomologation','canHomologate','canPublish','canManagePermissions','permissionUsers','isAdmin','isProfessor','isOwner'):
            self.assertIn(marker,portal)



if __name__=='__main__': unittest.main()
