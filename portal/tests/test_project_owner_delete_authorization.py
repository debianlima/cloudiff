from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MODULE_PATH=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py'
BASE_PATH=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
LEGACY_PATH=ROOT/'portal/legacy/cloudif-admin-portal-base.py'
COEXIST_PATH=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py'


def load_module():
    stub=types.ModuleType('cloudif_delete_git_komodo_action')
    stub.forja_rollback=lambda *args,**kwargs:{'ok':True}
    sys.modules['cloudif_delete_git_komodo_action']=stub
    spec=importlib.util.spec_from_file_location('project_delete_owner_test',MODULE_PATH)
    module=importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class ProjectOwnerDeleteAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.module=load_module();self.module.DB=root/'portal.db';self.module.JOB_ROOT=root/'jobs';self.module.WIZARD_ROOT=self.module.JOB_ROOT/'.wizard-tokens'
        con=sqlite3.connect(self.module.DB)
        con.executescript('''
            create table projects(slug text primary key,name text,owner text,tenant text,repo_url text,komodo_status text,status text);
            insert into projects values('silvipro','Silvipro','iff1860746','iff1860746-silvipro','','running','published');
            insert into projects values('shared-project','Shared','another-owner','tenant-shared','','running','published');
        ''')
        con.commit();con.close()

    def tearDown(self):self.temp.cleanup()

    def test_owner_can_delete_only_own_project(self):
        self.assertTrue(self.module.can_delete_project('silvipro','iff1860746'))
        self.assertTrue(self.module.can_delete_project('silvipro','IFF1860746'))
        self.assertFalse(self.module.can_delete_project('shared-project','iff1860746'))
        self.assertFalse(self.module.can_delete_project('missing','iff1860746'))

    def test_global_admin_can_delete_any_existing_or_recovery_target(self):
        self.assertTrue(self.module.can_delete_project('shared-project','admin',True))
        self.assertTrue(self.module.can_delete_project('missing','admin',True))

    def test_owner_scope_contains_only_owned_projects(self):
        self.assertEqual(self.module.project_slugs_for_owner('iff1860746'),{'silvipro'})
        self.assertEqual(self.module.project_slugs_for_owner('unknown'),set())

    def test_job_status_is_visible_to_actor_or_global_admin(self):
        self.module.JOB_ROOT.mkdir(parents=True)
        job_id='a'*32
        (self.module.JOB_ROOT/f'{job_id}.json').write_text(json.dumps({
            'ok':True,'job_id':job_id,'slug':'silvipro','actor':'iff1860746','status':'running'
        }))
        allowed,state=self.module.can_read_job(job_id,'iff1860746')
        self.assertTrue(allowed);self.assertEqual(state['slug'],'silvipro')
        self.assertFalse(self.module.can_read_job(job_id,'other')[0])
        self.assertTrue(self.module.can_read_job(job_id,'admin',True)[0])

    def test_render_filters_projects_for_non_admin_owner(self):
        self.module.preview=lambda slug:{'ok':True,'slug':slug,'already_deleted':False}
        self.module.issue_wizard_token=lambda slug:'wizard-token'
        html=self.module.render('csrf',selected='silvipro',allowed_slugs={'silvipro'})
        self.assertIn('Silvipro',html)
        self.assertNotIn('Shared',html)
        self.assertIn('wizard-token',html)


class ProjectOwnerDeleteRouteContractTests(unittest.TestCase):
    def test_active_and_legacy_routes_use_owner_authorization(self):
        active=BASE_PATH.read_text();legacy=LEGACY_PATH.read_text()
        for source in (active,legacy):
            self.assertIn('def _admin_project_delete_allowed(user,slug):',source)
            self.assertIn('_admin_project_delete.can_delete_project(',source)
            self.assertIn('_admin_project_delete_scope(user)',source)
            self.assertIn('Somente o proprietário do projeto ou um administrador global pode excluí-lo.',source)
            self.assertIn('allowed_slugs=_admin_project_delete_scope(user)',source)
        self.assertEqual(
            active.count('def _admin_project_delete_allowed(user,slug):'),
            legacy.count('def _admin_project_delete_allowed(user,slug):'),
        )

    def test_async_route_keeps_csrf_owner_and_single_use_wizard_checks(self):
        source=COEXIST_PATH.read_text()
        block=source[source.index('if value("async") == "1":'):source.index('self.rfile = BytesIO(raw)',source.index('if value("async") == "1":'))]
        for marker in ('_prod_csrf_equal','_admin_project_delete_allowed','consume_wizard_token','wizard_required','202 if job.get("ok") else 409'):
            self.assertIn(marker,block)
        self.assertLess(block.index('_prod_csrf_equal'),block.index('start_job'))
        self.assertLess(block.index('_admin_project_delete_allowed'),block.index('start_job'))
        self.assertLess(block.index('consume_wizard_token'),block.index('start_job'))

    def test_status_route_allows_job_actor_after_project_is_removed(self):
        source=COEXIST_PATH.read_text()
        start=source.index('if path in {"/cloudif/portal/api/admin-delete-project-status"')
        end=source.index('if path in {"/cloudif/portal/api/admin-ad-search"',start)
        block=source[start:end]
        self.assertIn('can_read_job',block)
        self.assertIn('user.get("username")',block)
        self.assertIn('403',block)


if __name__=='__main__':unittest.main()
