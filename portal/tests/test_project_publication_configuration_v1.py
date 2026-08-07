from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from portal.tests.test_project_environment_controller import load_module

ROOT=Path(__file__).resolve().parents[2]
KOMODO=ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py'
PUBLICATIONS=ROOT/'components/control-plane/current-apps/portal-current/cloudif_portal_publications.py'
PUB_CONFIG=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_publication_config.py'
ENV_WEB=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_environment_web.py'
PORTAL=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
PUB_UI=ROOT/'components/control-plane/current-apps/portal-current/cloudif_ui_publications.py'
RECONCILE=ROOT/'components/control-plane/current-apps/reconcile-worker-current/cloudif-reconcile-worker.py'
RECONCILE_CLIENT=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_reconcile_client.py'
RECONCILE_UNIT=ROOT/'components/control-plane/etc/systemd/system/cloudif-reconcile-worker.service'


def load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[name]=module;spec.loader.exec_module(module);return module


class ProjectPublicationConfigurationV1Tests(unittest.TestCase):
    def test_komodo_has_editable_base_and_immutable_snapshot_contract(self):
        source=KOMODO.read_text()
        self.assertIn('create table if not exists project_base_state',source)
        self.assertIn('create table if not exists project_base_revisions',source)
        self.assertIn("workspace=f'cloudif-p{public_number}-base-editor'",source)
        self.assertIn("tag=f'cloudif/project-{int(public_number)}:base-r{revision}'",source)
        self.assertIn("['docker','commit','--pause=true',workspace,tag]",source)
        self.assertIn('"/komodo/project/base/ensure"',source)
        self.assertIn('"/komodo/project/base/snapshot"',source)
        self.assertIn("_cloudif_ensure_container_terminal(server_id,workspace)",source)
        self.assertIn("'terminal':terminal.get('terminal')",source)
        self.assertIn("dockerfile=f'''FROM {base['image_id']}",source)
        self.assertIn("base_editor_re=re.compile",source);self.assertIn("delete from project_base_revisions where project=?",source)
        self.assertIn("Path('/srv/cloudif/publication-secrets')/('p'+number)",source)

    def test_publication_environment_is_private_and_bound_to_version(self):
        source=KOMODO.read_text()
        self.assertIn("root=Path('/srv/cloudif/publication-secrets')",source)
        self.assertIn("path.chmod(0o600)",source)
        self.assertIn(".cloudif-runtime-snapshot.json",source)
        self.assertIn('environmentRevision',source);self.assertIn('environmentDigest',source)
        self.assertIn("'variableValuesReturned':False",source);self.assertIn("'secretValuesIncluded':False",source)
        self.assertGreaterEqual(source.count('/srv/cloudif/publication-secrets/p{public_number}/d{deploy_number}/runtime.env'),2);self.assertNotIn("'environment_variables':environment_values",source)

    def test_portal_job_freezes_base_and_environment_identity(self):
        source=PUBLICATIONS.read_text();helper=PUB_CONFIG.read_text()
        for marker in ('base_revision','base_image_id','environment_revision','environment_digest','capture_snapshot','execution_environment'):
            self.assertIn(marker,source)
        self.assertIn("raise RuntimeError('publication_environment_changed')",helper)
        self.assertIn("'X-CloudIF-Secret-Resolver-Token':resolver",helper)
        self.assertIn("secret_data.get('internal') is not True",helper)
        self.assertIn("set(raw_resolved)!=set(references)",helper)
        self.assertIn("'secretValuesIncluded':False",source)
        self.assertIn("transient_values.clear()",source)
        self.assertIn("environment_runtime['values']={}",source)

    def test_wizard_and_base_controls_are_in_project_publication_ui(self):
        portal=PORTAL.read_text();ui=PUB_UI.read_text();env=ENV_WEB.read_text()
        self.assertIn('data-env-wizard',ui);self.assertIn('Abrir base no Komodo',ui)
        self.assertIn('env-wizard-layer',portal);self.assertIn("change/plan",portal);self.assertIn("approval/request",portal);self.assertIn("change/execute",portal)
        self.assertIn('approval/status',env);self.assertIn('valores secretos nunca são carregados',portal)
        self.assertIn('open_base_workspace',portal);self.assertIn('canWrite',PUBLICATIONS.read_text())

    def test_configuration_change_uses_partitioned_reconcile_and_runtime_reconciler(self):
        client=RECONCILE_CLIENT.read_text();worker=RECONCILE.read_text();unit=RECONCILE_UNIT.read_text()
        self.assertIn('"project.configuration.changed"',client)
        self.assertIn('event=="project.configuration.changed"',worker)
        self.assertIn('reconcile_project_runtime(project,environment)',worker)
        self.assertIn("return 'configuration.changed'",(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_config_events.py').read_text())
        self.assertIn('EnvironmentFile=/etc/cloudif/runtime-reconciler.env',unit)

    def test_revision_zero_project_can_use_global_environment_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            module=load_module(Path(tmp))
            con=sqlite3.connect(module.STATE_DB);con.execute("update projects set current_revision=0 where project_slug='demo'");con.execute("delete from revisions where project_slug='demo'");con.commit();con.close()
            plan=module.plan_change('demo','production',[{'name':'APP_MODE','value':'production','definition':{'runtime':True}}],0,'alice')
            result=module.apply_plan('demo',plan['planDigest'],0,'alice')
            self.assertEqual(result['revision'],1)
            effective=module.effective_internal('demo','production')
            self.assertEqual(effective['configurationRevision'],0);self.assertEqual(effective['environmentRevision'],1)
            self.assertEqual(effective['publicRuntimeEnvironment']['']['APP_MODE'],'production')

    def test_enqueue_persists_snapshot_without_variable_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            module=load(PUBLICATIONS,'publication_snapshot_test')
            module.DB=Path(tmp)/'portal.db'
            con=sqlite3.connect(module.DB)
            con.executescript("""
              create table projects(slug text primary key,owner text,created_by text,status text);
              create table project_acl(slug text,subject_type text,subject text);
              insert into projects values('demo','alice','alice','active');
            """);con.commit();module._ensure_schema(con)
            con.execute("insert into project_public_ids(project_slug,public_number,created_at,updated_at) values('demo',1234,'now','now')");con.commit();con.close()
            class Fake:
                @staticmethod
                def capture_snapshot(slug,num,actor):return {'baseRevision':7,'baseImage':'cloudif/project-1234:base-r7','baseImageId':'sha256:'+'a'*64,'environment':'production','environmentRevision':11,'environmentDigest':'b'*64}
            with patch.object(module,'_publication_config',return_value=Fake):
                result=module.enqueue_publish('demo',{'username':'alice','groups':[],'admin':False})
            self.assertEqual(result['baseRevision'],7);self.assertEqual(result['environmentRevision'],11)
            con=sqlite3.connect(module.DB);con.row_factory=sqlite3.Row;row=con.execute('select * from publication_jobs where id=?',(result['job_id'],)).fetchone();con.close()
            self.assertEqual(row['base_revision'],7);self.assertEqual(row['environment_revision'],11);self.assertEqual(row['environment_digest'],'b'*64)
            self.assertNotIn('environment_variables',dict(row))


if __name__=='__main__':unittest.main()
