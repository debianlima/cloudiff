from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'components/control-plane/current-apps/project-config-controller-current/cloudif_project_environment.py'


def load_module(root:Path):
    state=root/'config.db';control=root/'control.db'
    c=sqlite3.connect(control)
    c.execute('create table projects(project_id text primary key,slug text unique,name text,owner text,tenant text,status text)')
    c.execute("insert into projects values('p1','demo','Demo','alice','tenant-demo','active')")
    c.commit();c.close()
    c=sqlite3.connect(state)
    c.executescript('''
      create table projects(project_slug text primary key,current_revision integer not null,manifest_digest text,config_digest text,toolchain_digest text,membership_revision integer,observation_status text,updated_at integer);
      create table revisions(project_slug text,revision integer,effective_json text,source text,created_by text,created_at integer,primary key(project_slug,revision));
    ''')
    effective={
      'environment':{'definitions':{'GLOBAL_REQUIRED':{'required':True,'secret':False}},'variables':{},'required':{}},
      'environments':{},
      'services':{
        'web':{'runtime':'static','environment':{'definitions':{},'variables':{},'required':[]}},
        'api':{'runtime':'node','environment':{'definitions':{'DATABASE_URL':{'required':True,'secret':True}},'variables':{},'required':['DATABASE_URL']}},
      },
    }
    c.execute("insert into projects values('demo',1,'m','c','t',0,'ready',1)")
    c.execute("insert into revisions values('demo',1,?,'portal','alice',1)",(json.dumps(effective),))
    c.commit();c.close()
    os.environ['CLOUDIF_PROJECT_CONFIG_DB']=str(state);os.environ['CLOUDIF_PROJECT_SNAPSHOT_DB']=str(control)
    name='project_environment_test_'+root.name.replace('-','_')
    spec=importlib.util.spec_from_file_location(name,SOURCE);module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[name]=module;spec.loader.exec_module(module);module.init_db();return module


class ProjectEnvironmentControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.module=load_module(Path(self.temp.name))

    def tearDown(self):self.temp.cleanup()

    def plan(self,changes,revision=0,environment='preview'):
        return self.module.plan_change('demo',environment,changes,revision,'alice',900)

    def test_public_and_secret_changes_are_planned_without_exposing_secret_values(self):
        plan=self.plan([
          {'operation':'upsert','name':'LOG_LEVEL','value':'info','definition':{'required':True,'runtime':True,'restartRequired':True}},
          {'operation':'upsert','name':'DATABASE_URL','service':'api','secret_reference':'vault://project/demo/database-url','definition':{'required':True,'secret':True,'runtime':True}},
        ])
        self.assertTrue(plan['sideEffectFree']);self.assertTrue(plan['approvalRequired'])
        self.assertEqual(plan['summary']['impact']['requiredAction'],'restart')
        self.assertEqual(plan['summary']['secretChanges'],1)
        self.assertFalse(plan['secretValuesIncluded'])
        serialized=json.dumps(plan)
        self.assertNotIn('database-password',serialized)
        self.assertNotIn('secret_reference',serialized)

    def test_apply_is_revisioned_idempotent_and_masked(self):
        plan=self.plan([
          {'name':'PUBLIC_API_URL','service':'web','value':'https://api.example.test','definition':{'runtime':True,'restartRequired':True,'exposeToClient':True}},
          {'name':'DATABASE_URL','service':'api','secret_reference':'vault://project/demo/database-url','definition':{'secret':True,'required':True}},
        ])
        applied=self.module.apply_plan('demo',plan['planDigest'],0,'alice')
        self.assertEqual(applied['revision'],1);self.assertEqual(applied['requiredAction'],'restart')
        self.assertFalse(applied['containersChanged']);self.assertTrue(applied['reconciliationPending'])
        again=self.module.apply_plan('demo',plan['planDigest'],0,'alice')
        self.assertTrue(again['idempotent']);self.assertEqual(again['revision'],1)
        hidden=self.module.list_environment('demo','preview',include_values=False)
        by_name={item['name']:item for item in hidden['entries']}
        self.assertIsNone(by_name['PUBLIC_API_URL']['value'])
        self.assertIsNone(by_name['DATABASE_URL']['value'])
        self.assertTrue(by_name['DATABASE_URL']['referenceConfigured'])
        visible=self.module.list_environment('demo','preview',include_values=True)
        visible_by={item['name']:item for item in visible['entries']}
        self.assertEqual(visible_by['PUBLIC_API_URL']['value'],'https://api.example.test')
        self.assertIsNone(visible_by['DATABASE_URL']['value'])
        self.assertNotIn('vault://',json.dumps(visible))

    def test_build_time_change_requires_rebuild(self):
        plan=self.plan([{'name':'PUBLIC_BUILD_MODE','value':'optimized','definition':{'buildTime':True,'runtime':False,'restartRequired':False}}])
        self.assertEqual(plan['summary']['impact']['requiredAction'],'rebuild')

    def test_secret_value_and_sensitive_public_name_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'secret_value_not_allowed'):
            self.plan([{'name':'JWT_SECRET','value':'plaintext','definition':{'secret':True}}])
        with self.assertRaisesRegex(ValueError,'sensitive_name_requires_secret'):
            self.plan([{'name':'API_TOKEN','value':'public'}])

    def test_revision_conflict_blocks_stale_plan_and_apply(self):
        first=self.plan([{'name':'LOG_LEVEL','value':'info'}]);self.module.apply_plan('demo',first['planDigest'],0,'alice')
        with self.assertRaisesRegex(RuntimeError,'environment_revision_conflict:1'):
            self.plan([{'name':'LOG_LEVEL','value':'debug'}],0)

    def test_immutable_variable_cannot_be_changed_or_deleted(self):
        first=self.plan([{'name':'APP_ID','value':'demo','definition':{'immutable':True}}]);self.module.apply_plan('demo',first['planDigest'],0,'alice')
        change=self.plan([{'name':'APP_ID','value':'other','definition':{'immutable':True}}],1)
        with self.assertRaisesRegex(RuntimeError,'immutable_environment_variable:APP_ID'):
            self.module.apply_plan('demo',change['planDigest'],1,'alice')
        deletion=self.plan([{'operation':'delete','name':'APP_ID'}],1)
        with self.assertRaisesRegex(RuntimeError,'immutable_environment_variable:APP_ID'):
            self.module.apply_plan('demo',deletion['planDigest'],1,'alice')

    def test_promotion_copies_metadata_without_revealing_secret(self):
        initial=self.plan([
          {'name':'LOG_LEVEL','value':'debug'},
          {'name':'DATABASE_URL','service':'api','secret_reference':'vault://project/demo/database-url-preview','definition':{'secret':True,'required':True}},
        ]);self.module.apply_plan('demo',initial['planDigest'],0,'alice')
        promotion=self.module.plan_promotion('demo','preview','homologation','',1,'alice')
        self.assertEqual(promotion['summary']['changeCount'],2)
        self.assertNotIn('vault://',json.dumps(promotion))
        applied=self.module.apply_plan('demo',promotion['planDigest'],1,'alice')
        self.assertEqual(applied['revision'],2)
        target=self.module.list_environment('demo','homologation',include_values=True)
        self.assertEqual({item['name'] for item in target['entries']},{'LOG_LEVEL','DATABASE_URL'})
        self.assertIsNone(next(item for item in target['entries'] if item['name']=='DATABASE_URL')['value'])

    def test_history_is_sanitized_and_missing_variables_are_reported(self):
        missing=self.module.missing_variables('demo','production')
        self.assertEqual({(item['service'],item['name']) for item in missing['missing']},{('','GLOBAL_REQUIRED'),('api','DATABASE_URL')})
        plan=self.module.plan_change('demo','production',[
          {'name':'GLOBAL_REQUIRED','value':'set'},
          {'name':'DATABASE_URL','service':'api','secret_reference':'vault://project/demo/db-prod','definition':{'secret':True,'required':True}},
        ],0,'alice');self.module.apply_plan('demo',plan['planDigest'],0,'alice')
        self.assertTrue(self.module.missing_variables('demo','production')['valid'])
        history=self.module.history('demo')
        self.assertEqual(history['count'],2);self.assertFalse(history['secretValuesIncluded'])
        self.assertNotIn('vault://',json.dumps(history))


if __name__=='__main__':unittest.main()
