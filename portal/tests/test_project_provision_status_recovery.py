from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_provision_status.py'


def load_module():
    spec=importlib.util.spec_from_file_location('project_provision_status_test',SOURCE)
    module=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(module);return module


class ProjectProvisionStatusRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.module=load_module();self.module.DB=root/'portal.db';self.module.JOBDIR=root/'jobs';self.module.PROVISION_ROOT=root/'projects'
        self.module.JOBDIR.mkdir();self.module.PROVISION_ROOT.mkdir()
        con=sqlite3.connect(self.module.DB)
        con.executescript('''
          create table projects(slug text primary key,name text,description text,tenant text,owner text,status text,updated_at text);
          create table project_public_ids(project_slug text primary key,public_number integer,created_at text,updated_at text);
          create table project_publications(project_slug text,deploy_number integer,status text,is_active integer);
          insert into projects values('silvipro2','Silvipro 2','','iff1860746-silvipro2','iff1860746','draft','2026-08-06T19:30:00Z');
          insert into project_public_ids values('silvipro2',1003,'','');
        ''');con.commit();con.close()
        project=self.module.PROVISION_ROOT/'silvipro2';project.mkdir()
        (project/'provision-report.json').write_text(json.dumps({'ok':True,'finished_at':'2026-08-06T19:30:00Z','components':{
          'forgejo':{'ok':True,'status':'done'},'komodo':{'ok':True,'status':'done'},'supabase':{'ok':True,'status':'done'}}}))
        (project/'managed-runtime.json').write_text(json.dumps({'layout':'managed-root-v1','runtime_template':'node24','php_version':'8.4'}))
        (project/'template-applied.json').write_text(json.dumps({'template_kind':'links','runtime_template':'node24','php_version':'8.4'}))

    def tearDown(self):self.temp.cleanup()

    def test_missing_job_with_ready_infrastructure_is_recoverable(self):
        state=self.module.status('silvipro2')
        self.assertTrue(state['ok']);self.assertEqual(state['status'],'failed')
        self.assertEqual(state['current_step'],'initial-publication')
        self.assertTrue(state['recoverable']);self.assertEqual(state['recovery_action'],'resume_initial_publication')
        self.assertEqual(state['publication']['public_number'],1003)
        self.assertFalse(state['secrets_exposed'])
        self.assertNotIn('password',str(state).lower())

    def test_active_publication_changes_derived_state_to_succeeded_even_without_auxiliary_file(self):
        con=sqlite3.connect(self.module.DB);con.execute("insert into project_publications values('silvipro2',3,'published',1)");con.commit();con.close()
        state=self.module.status('silvipro2')
        self.assertEqual(state['status'],'succeeded');self.assertEqual(state['current_step'],'complete')
        self.assertFalse(state['recoverable'])
        self.assertTrue(state['publication']['active'])
        self.assertFalse(state['publication']['initial_record'])

    def test_failed_before_template_uses_original_create_job_as_recovery_metadata(self):
        project=self.module.PROVISION_ROOT/'silvipro2'
        (project/'managed-runtime.json').unlink();(project/'template-applied.json').unlink()
        create_job={'action':'create_project','status':'failed','current_step':'provision','slug':'silvipro2','tenant':'iff1860746-silvipro2','runtime_template':'node22','php_version':'8.3','runtime_layout':'managed-root-v1','template_kind':'links'}
        retry_job={'action':'update_project','status':'failed','current_step':'initial-publication','slug':'silvipro2','tenant':'iff1860746-silvipro2','runtime_template':'node24','php_version':'8.4','runtime_layout':'managed-root-v1','template_kind':'none'}
        (self.module.JOBDIR/'project-provision-a-silvipro2.json').write_text(json.dumps(create_job))
        (self.module.JOBDIR/'project-provision-b-silvipro2.json').write_text(json.dumps(retry_job))
        state=self.module.status('silvipro2')
        self.assertTrue(state['recoverable']);self.assertEqual(state['recovery_action'],'resume_initial_publication')
        material=self.module.resume_material('silvipro2',{'username':'iff1860746'})
        self.assertEqual(material['resume_from'],'template');self.assertEqual(material['current_step'],'template')
        self.assertEqual(material['runtime_template'],'node22');self.assertEqual(material['php_version'],'8.3')
        self.assertEqual(material['template_kind'],'links')

    def test_running_job_prevents_recovery(self):
        job={'status':'running','current_step':'initial-publication','updated_at':'now','slug':'silvipro2'}
        (self.module.JOBDIR/'project-provision-a-silvipro2.json').write_text(json.dumps(job))
        state=self.module.status('silvipro2')
        self.assertEqual(state['status'],'running');self.assertFalse(state['recoverable'])
        with self.assertRaisesRegex(RuntimeError,'initial_publication_not_recoverable'):
            self.module.resume_material('silvipro2',{'username':'iff1860746'})

    def test_resume_material_preserves_existing_project_and_runtime(self):
        material=self.module.resume_material('silvipro2',{'username':'iff1860746','email':'user@example.edu','groups':['CloudIF-Tenants']})
        self.assertEqual(material['action'],'resume_initial_publication')
        self.assertEqual(material['tenant'],'iff1860746-silvipro2')
        self.assertEqual(material['runtime_template'],'node24');self.assertEqual(material['php_version'],'8.4')
        self.assertEqual(material['runtime_layout'],'managed-root-v1');self.assertEqual(material['public_number'],1003)
        self.assertEqual(material['create_repo'],'0');self.assertEqual(material['setup_komodo'],'0')
        self.assertEqual(material['current_step'],'initial-publication')

    def test_non_owner_cannot_resume(self):
        with self.assertRaisesRegex(PermissionError,'project_owner_required'):
            self.module.resume_material('silvipro2',{'username':'other-user'})
        self.assertEqual(self.module.resume_material('silvipro2',{'username':'admin'},global_admin=True)['action'],'resume_initial_publication')


if __name__=='__main__':unittest.main()
