import email.message
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import urllib.parse

ROOT=Path(__file__).resolve().parents[2]
LIB=ROOT/'components/control-plane/srv/cloudif/lib'
PORTAL_CURRENT=ROOT/'components/control-plane/current-apps/portal-current'
BASE_PORTAL=PORTAL_CURRENT/'cloudif-admin-portal-base.py'
STATUS_SOURCE=LIB/'cloudif_project_provision_status.py'
WORKER_SOURCE=LIB/'cloudif_project_provision_worker.py'


class _Handler:
    def __init__(self,module,fields,csrf=True):
        self.path='/cloudiff/portal/action/project_action'
        self._user={'username':'alice','email':'alice@example.invalid','groups':['CloudIF-Aluno'],'admin':False}
        payload=dict(fields)
        if csrf: payload['csrf_token']=module._prod_csrf_token(self._user)
        body=urllib.parse.urlencode(payload).encode()
        self.rfile=io.BytesIO(body);self.wfile=io.BytesIO();self.headers=email.message.Message()
        self.headers['Content-Length']=str(len(body));self.headers['Content-Type']='application/x-www-form-urlencoded'
        self.headers['Host']='cloudiff.duckdns.org';self.headers['Origin']='https://cloudiff.duckdns.org'
        self.headers['X-authentik-username']='alice';self.headers['X-authentik-email']='alice@example.invalid';self.headers['X-authentik-groups']='CloudIF-Aluno'
        self.status=None;self.response_headers=[]
    def user(self):return dict(self._user)
    def send_response(self,status):self.status=status
    def send_header(self,name,value):self.response_headers.append((name,value))
    def end_headers(self):return None
    def send_html(self,body,status=200):self.status=status;self.wfile.write(str(body).encode());return None
    def redirect(self,location):self.status=303;self.response_headers.append(('Location',location));return None


class ProjectResumeActionEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        cls.db=cls.root/'portal.db';cls.jobs=cls.root/'jobs';cls.provision=cls.root/'provisioning'/'projects';cls.jobs.mkdir(parents=True);cls.provision.mkdir(parents=True)
        cls.old_env={k:os.environ.get(k) for k in ('CLOUDIF_PORTAL_DB','CLOUDIF_BASE','CLOUDIF_CSRF_SECRET','CLOUDIF_PUBLIC_HOST','CLOUDIF_PORTAL_HOST','CLOUDIF_PORTAL_PORT','CLOUDIF_ACCESS_INGEST_DB')}
        os.environ.update({'CLOUDIF_PORTAL_DB':str(cls.db),'CLOUDIF_BASE':str(cls.root/'cloudif'),'CLOUDIF_CSRF_SECRET':'project-resume-effect-test-secret','CLOUDIF_PUBLIC_HOST':'cloudiff.duckdns.org','CLOUDIF_PORTAL_HOST':'127.0.0.1','CLOUDIF_PORTAL_PORT':'19089','CLOUDIF_ACCESS_INGEST_DB':str(cls.root/'access.db')})
        (cls.root/'cloudif').mkdir(parents=True)
        sys.path.insert(0,str(PORTAL_CURRENT));sys.path.insert(0,str(LIB))

        cls.previous_delete_action_module=sys.modules.pop('cloudif_delete_git_komodo_action',None)
        ds=importlib.util.spec_from_file_location('cloudif_delete_git_komodo_action',LIB/'cloudif_delete_git_komodo_action.py');dm=importlib.util.module_from_spec(ds);sys.modules['cloudif_delete_git_komodo_action']=dm;ds.loader.exec_module(dm)

        ps=importlib.util.spec_from_file_location('cloudiff_project_resume_effect_portal',BASE_PORTAL);cls.portal=importlib.util.module_from_spec(ps);ps.loader.exec_module(cls.portal);cls.portal.init_db()
        with sqlite3.connect(cls.db) as con:
            con.executescript('''
              CREATE TABLE IF NOT EXISTS project_public_ids(project_slug TEXT PRIMARY KEY,public_number INTEGER UNIQUE,created_at TEXT,updated_at TEXT);
              CREATE TABLE IF NOT EXISTS project_publications(project_slug TEXT,deploy_number INTEGER,status TEXT,is_active INTEGER);
            ''')
            con.commit()
        import cloudif_project_action_safe as safe
        cls.safe=safe;cls.old_safe_db=safe.DB;cls.old_queue=safe.queue_provision_job;safe.DB=str(cls.db)

        cls.previous_status_module=sys.modules.pop('cloudif_project_provision_status',None)
        ss=importlib.util.spec_from_file_location('cloudif_project_provision_status',STATUS_SOURCE);cls.status=importlib.util.module_from_spec(ss);sys.modules['cloudif_project_provision_status']=cls.status;ss.loader.exec_module(cls.status)
        cls.status.DB=cls.db;cls.status.JOBDIR=cls.jobs;cls.status.PROVISION_ROOT=cls.provision
        cls.queue_calls=[];safe.queue_provision_job=cls._queue

    @classmethod
    def tearDownClass(cls):
        cls.safe.DB=cls.old_safe_db;cls.safe.queue_provision_job=cls.old_queue;cls.portal._close_db_anchor()
        if cls.previous_status_module is None:sys.modules.pop('cloudif_project_provision_status',None)
        else:sys.modules['cloudif_project_provision_status']=cls.previous_status_module
        if cls.previous_delete_action_module is None:sys.modules.pop('cloudif_delete_git_komodo_action',None)
        else:sys.modules['cloudif_delete_git_komodo_action']=cls.previous_delete_action_module
        for path in (str(LIB),str(PORTAL_CURRENT)):
            try:sys.path.remove(path)
            except ValueError:pass
        for k,v in cls.old_env.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
        cls.tmp.cleanup()

    @classmethod
    def _queue(cls,job):
        payload=dict(job);payload['job_id']='resume-job-001';path=cls.jobs/f"project-provision-resume-job-001-{job['slug']}.json";path.write_text(json.dumps(payload,ensure_ascii=False,sort_keys=True)+'\n');cls.queue_calls.append(payload);return {'job_file':str(path),'deduplicated':False,'job':payload}

    def setUp(self):
        self.queue_calls.clear()
        for p in self.jobs.glob('*'):p.unlink()
        with sqlite3.connect(self.db) as con:
            for table in ('project_publications','project_public_ids','project_acl','projects','action_log'):
                try:con.execute(f'DELETE FROM {table}')
                except sqlite3.OperationalError:pass
            con.execute("INSERT INTO projects(slug,name,tenant,owner,description,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",('demo','Demo','alice-db','alice','Projeto pronto','2026-08-27T22:00:00Z','2026-08-27T22:00:00Z'))
            con.execute("INSERT OR IGNORE INTO project_acl(slug,subject_type,subject) VALUES(?,?,?)",('demo','user','alice'))
            con.execute("INSERT INTO project_public_ids(project_slug,public_number,created_at,updated_at) VALUES(?,?,?,?)",('demo',42,'',''))
            con.commit()
        root=self.provision/'demo';root.mkdir(parents=True,exist_ok=True)
        (root/'provision-report.json').write_text(json.dumps({'ok':True,'finished_at':'2026-08-27T22:10:00Z','components':{'forgejo':{'ok':True,'status':'done'},'komodo':{'ok':True,'status':'done'},'supabase':{'ok':True,'status':'done'}}}))
        (root/'managed-runtime.json').write_text(json.dumps({'layout':'managed-root-v1','runtime_template':'node22','php_version':'8.3'}))
        (root/'template-applied.json').write_text(json.dumps({'template_kind':'links','runtime_template':'node22','php_version':'8.3','runtime_layout':'managed-root-v1'}))
        try:(root/'initial-publication.json').unlink()
        except FileNotFoundError:pass

    def _post(self,csrf=True):
        h=_Handler(self.portal,{'action':'resume_initial_publication','slug':'demo'},csrf=csrf);self.portal.Portal.do_POST(h);return h

    def test_resume_handler_queues_resume_only_material_without_rewriting_project(self):
        with sqlite3.connect(self.db) as con:
            before=con.execute('SELECT name,tenant,owner,description FROM projects WHERE slug=?',('demo',)).fetchone()
        handler=self._post();self.assertEqual(handler.status,303)
        self.assertIn('project=demo',dict(handler.response_headers).get('Location',''))
        self.assertEqual(len(self.queue_calls),1)
        job=self.queue_calls[0]
        self.assertEqual(job['action'],'resume_initial_publication');self.assertEqual(job['resume_from'],'initial-publication')
        self.assertEqual(job['create_repo'],'0');self.assertEqual(job['setup_komodo'],'0')
        self.assertEqual(job['runtime_template'],'node22');self.assertEqual(job['php_version'],'8.3');self.assertEqual(job['public_number'],42)
        self.assertEqual(job['current_step'],'initial-publication')
        with sqlite3.connect(self.db) as con:
            after=con.execute('SELECT name,tenant,owner,description FROM projects WHERE slug=?',('demo',)).fetchone()
        self.assertEqual(after,before)

    def test_non_owner_cannot_resume_and_creates_no_job(self):
        handler=_Handler(self.portal,{'action':'resume_initial_publication','slug':'demo'})
        handler._user={'username':'mallory','email':'mallory@example.invalid','groups':['CloudIF-Aluno'],'admin':False}
        handler.headers.replace_header('X-authentik-username','mallory');handler.headers.replace_header('X-authentik-email','mallory@example.invalid')
        # CSRF must correspond to the changed identity.
        body=urllib.parse.urlencode({'action':'resume_initial_publication','slug':'demo','csrf_token':self.portal._prod_csrf_token(handler._user)}).encode();handler.rfile=io.BytesIO(body);handler.headers.replace_header('Content-Length',str(len(body)))
        self.portal.Portal.do_POST(handler)
        self.assertEqual(handler.status,403);self.assertEqual(self.queue_calls,[]);self.assertEqual(list(self.jobs.glob('*')),[])

    def test_worker_resume_executes_only_initial_publication_then_reconciles(self):
        handler=self._post();self.assertEqual(handler.status,303)
        job_path=next(self.jobs.glob('project-provision-*.json'))
        ws=importlib.util.spec_from_file_location('cloudiff_project_resume_effect_worker',WORKER_SOURCE);worker=importlib.util.module_from_spec(ws);ws.loader.exec_module(worker)
        commands=[];events=[]
        worker.log=lambda msg:None
        worker.run=lambda cmd,timeout=180:(commands.append((list(cmd),timeout)) or subprocess.CompletedProcess(cmd,0,stdout=json.dumps({'ok':True,'publicationNumber':1})+'\n',stderr=''))
        worker.enqueue_post_provision=lambda slug,job,event='project.updated':(events.append((slug,event)) or {'request_id':'req-resume-001','status':'queued'})
        old_argv=sys.argv[:]
        try:
            sys.argv=['cloudif_project_provision_worker.py',str(job_path)];worker.main()
        finally:sys.argv=old_argv
        self.assertEqual(len(commands),1)
        self.assertEqual(commands[0][0],["/usr/local/sbin/cloudif-project-initial-publish.py",str(job_path)])
        self.assertEqual(events,[('demo','project.membership.changed')])
        final=json.loads(job_path.read_text())
        self.assertEqual(final['status'],'succeeded');self.assertEqual(final['current_step'],'complete')
        self.assertTrue(final['result']['resume_only']);self.assertTrue(final['result']['provisioned'])
        self.assertNotIn('tenant_policy',final['result']);self.assertNotIn('backup_policy',final['result'])

    def test_missing_csrf_has_zero_job_effect(self):
        h=self._post(csrf=False);self.assertEqual(h.status,403);self.assertEqual(self.queue_calls,[]);self.assertEqual(list(self.jobs.glob('*')),[])


if __name__=='__main__':unittest.main()
