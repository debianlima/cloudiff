from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ENV=ROOT/'components/control-plane/current-apps/project-config-controller-current/cloudif_project_environment.py'
CONTROLLER=ROOT/'components/control-plane/current-apps/project-config-controller-current/cloudif-project-config-controller.py'
WEB=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_environment_web.py'
COEXIST=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py'
GATEWAY=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'


def load_module(root:Path):
    control=root/'control.db';state=root/'config.db'
    c=sqlite3.connect(control);c.execute('create table projects(project_id text primary key,slug text unique,name text,owner text,tenant text,status text)');c.execute("insert into projects values('p1','demo','Demo','alice','tenant-demo','active')");c.commit();c.close()
    effective={'environment':{'definitions':{},'variables':{},'required':{}},'environments':{},'services':{'api':{'runtime':'node','environment':{'definitions':{'DATABASE_URL':{'required':True,'secret':True,'runtime':True}},'variables':{},'required':['DATABASE_URL']}}}}
    c=sqlite3.connect(state);c.executescript('create table projects(project_slug text primary key,current_revision integer not null,manifest_digest text,config_digest text,toolchain_digest text,membership_revision integer,observation_status text,updated_at integer);create table revisions(project_slug text,revision integer,effective_json text,source text,created_by text,created_at integer,primary key(project_slug,revision));');c.execute("insert into projects values('demo',1,'m','c','t',0,'ready',1)");c.execute("insert into revisions values('demo',1,?,'portal','alice',1)",(json.dumps(effective),));c.commit();c.close()
    import os
    os.environ['CLOUDIF_PROJECT_CONFIG_DB']=str(state);os.environ['CLOUDIF_PROJECT_SNAPSHOT_DB']=str(control)
    spec=importlib.util.spec_from_file_location('dotenv_env_test_'+root.name.replace('-','_'),ENV);m=importlib.util.module_from_spec(spec);assert spec.loader;sys.modules[spec.name]=m;spec.loader.exec_module(m);m.init_db();return m


class ProjectEnvironmentDotenvContractTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.module=load_module(self.root)
    def tearDown(self):self.temp.cleanup()

    def test_import_plan_keeps_public_values_and_discards_secret_values(self):
        content='LOG_LEVEL=info\nDATABASE_URL=postgres://user:super-secret-password@db.example/demo\nAPI_TOKEN=another-secret\n'
        result=self.module.import_dotenv_plan('demo','preview','api',content,[],0,'alice',900)
        self.assertEqual(result['publicVariables'],['LOG_LEVEL']);self.assertEqual({x['name'] for x in result['secretVariables']},{'DATABASE_URL','API_TOKEN'})
        self.assertFalse(result['secretValuesImported']);self.assertFalse(result['contentStored']);self.assertFalse(result['secretValuesIncluded']);self.assertTrue(result['planDigest'])
        rendered=json.dumps(result);self.assertNotIn('super-secret-password',rendered);self.assertNotIn('another-secret',rendered)
        c=sqlite3.connect(self.root/'config.db');raw='\n'.join(str(x) for x in c.execute('select operations_json,summary_json from environment_plans').fetchall());c.close()
        self.assertNotIn('super-secret-password',raw);self.assertNotIn('another-secret',raw);self.assertIn('LOG_LEVEL',raw)

    def test_secret_only_file_creates_no_environment_plan(self):
        result=self.module.import_dotenv_plan('demo','production','api','DATABASE_URL=secret-value\nJWT_SECRET=other\n',[],0,'alice',900)
        self.assertIsNone(result['planDigest']);self.assertEqual(result['actionRequired'],'stage-secrets');self.assertEqual(result['publicCount'],0);self.assertEqual(result['secretCount'],2)
        c=sqlite3.connect(self.root/'config.db');self.assertEqual(c.execute('select count(*) from environment_plans').fetchone()[0],0);c.close()

    def test_explicit_secret_names_are_never_imported_as_public(self):
        result=self.module.import_dotenv_plan('demo','development','api','CUSTOM_CREDENTIAL=plain\nPUBLIC_MODE=demo\n',['CUSTOM_CREDENTIAL'],0,'alice',900)
        self.assertEqual(result['publicVariables'],['PUBLIC_MODE']);self.assertEqual(result['secretVariables'][0]['name'],'CUSTOM_CREDENTIAL')
        self.assertNotIn('plain',json.dumps(result))

    def test_parser_is_non_executing_and_rejects_shell_expansion(self):
        parsed=self.module.parse_dotenv("A='literal value'\nB=plain # comment\nexport C=ok\n")
        self.assertEqual(parsed,{'A':'literal value','B':'plain','C':'ok'})
        for bad in ('A=$(id)\n','A=${HOME}\n','A=`id`\n'):
            with self.assertRaisesRegex(ValueError,'dotenv_shell_expansion_forbidden'):self.module.parse_dotenv(bad)

    def test_export_contains_only_names_metadata_and_blank_example(self):
        plan=self.module.import_dotenv_plan('demo','preview','api','LOG_LEVEL=info\n',[],0,'alice',900);self.module.apply_plan('demo',plan['planDigest'],0,'alice')
        exported=self.module.export_environment_metadata('demo','preview','api');names={x['name'] for x in exported['variables']}
        self.assertEqual(names,{'DATABASE_URL','LOG_LEVEL'});self.assertFalse(exported['valuesIncluded']);self.assertFalse(exported['secretValuesIncluded']);self.assertFalse(exported['secretReferencesIncluded'])
        self.assertIn('DATABASE_URL=',exported['dotenvExample']);self.assertIn('LOG_LEVEL=',exported['dotenvExample']);self.assertNotIn('info',exported['dotenvExample'])
        self.assertNotIn('vault://',json.dumps(exported))

    def test_controller_web_and_mcp_share_import_export_contract(self):
        controller=CONTROLLER.read_text();web=WEB.read_text();coexist=COEXIST.read_text();gateway=GATEWAY.read_text()
        self.assertIn('project_environment.import_dotenv_plan',controller);self.assertIn('project_environment.export_environment_metadata',controller)
        self.assertIn("'import/plan':'/import/plan'",web);self.assertIn("operation=='export'",web)
        self.assertIn('import/plan',coexist);self.assertIn('effective|export',coexist)
        self.assertIn("'name':'project.environment.import.plan'",gateway);self.assertIn("'name':'project.environment.export'",gateway)
        self.assertNotIn('read_text(',ENV.read_text()[ENV.read_text().index('def import_dotenv_plan'):])


if __name__=='__main__':unittest.main()
