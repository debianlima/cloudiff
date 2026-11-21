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
WEB=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_environment_web.py'
COEXIST=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py'


def load_module(root:Path):
    control=root/'control.db';c=sqlite3.connect(control)
    c.executescript('''
      create table projects(project_id text primary key,slug text unique,name text,owner text,tenant text,status text);
      create table project_acl(project_id text,subject_type text,subject text,role text);
      insert into projects values('p1','demo','Demo','alice','tenant-demo','active');
      insert into project_acl values('p1','user','bob','maintainer');
      insert into project_acl values('p1','user','viewer','viewer');
      insert into project_acl values('p1','group','researchers','developer');
    ''');c.commit();c.close()
    spec=importlib.util.spec_from_file_location('environment_web_api_test',WEB);module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[spec.name]=module;spec.loader.exec_module(module);module.CONTROL_DB=control;return module


class ProjectEnvironmentWebAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.module=load_module(Path(self.temp.name))

    def tearDown(self):self.temp.cleanup()

    def test_authorization_matches_owner_acl_and_global_groups(self):
        self.assertTrue(self.module.authorization('demo','alice',[])['canWrite'])
        self.assertTrue(self.module.authorization('demo','bob',[])['canWrite'])
        self.assertTrue(self.module.authorization('demo','carol',['researchers'])['canWrite'])
        self.assertTrue(self.module.authorization('demo','prof',['CloudIF-Professor'])['canWrite'])
        self.assertTrue(self.module.authorization('demo','admin',['CloudIF-Tenants-Admin'])['canWrite'])
        viewer=self.module.authorization('demo','viewer',[]);self.assertTrue(viewer['canRead']);self.assertFalse(viewer['canWrite'])
        denied=self.module.authorization('demo','unknown',[]);self.assertFalse(denied['canRead']);self.assertFalse(denied['canWrite'])

    def test_get_proxies_only_for_authorized_reader(self):
        self.module._config=lambda method,slug,suffix='',payload=None,query=None:(200,{'ok':True,'entries':[],'secretValuesIncluded':False})
        code,data=self.module.handle_get('demo','',{'environment':'preview'},'viewer',[])
        self.assertEqual(code,200);self.assertTrue(data['ok'])
        code,data=self.module.handle_get('demo','',{},'unknown',[])
        self.assertEqual(code,403);self.assertEqual(data['error']['code'],'forbidden')

    def test_viewer_cannot_plan_or_execute(self):
        code,data=self.module.handle_post('demo','change/plan',{'environment':'preview','changes':[]},'viewer',[])
        self.assertEqual(code,403);self.assertEqual(data['error']['code'],'forbidden')

    def test_approval_request_stores_only_digest_summary_and_metadata_flags(self):
        plan={'ok':True,'projectSlug':'demo','planDigest':'a'*64,'action':'change','sourceEnvironment':None,'targetEnvironment':'preview','expectedRevision':0,'summary':{'changeCount':1,'changes':[{'name':'DATABASE_URL','secret':True}],'secretValuesIncluded':False},'expiresAt':9999999999,'consumed':False}
        self.module._plan=lambda slug,digest:plan
        captured={}
        def fake_call(method,url,token,payload=None,timeout=45):
            captured.update(payload or {});return 201,{'ok':True,'approval_id':'apr_'+'1'*20,'status':'pending','expires_at':9999999999}
        self.module._json_call=fake_call
        result=self.module.request_approval('demo','a'*64,'Aplicar configuração','alice',[])
        self.assertEqual(result['status'],'pending');self.assertFalse(result['secretValuesIncluded'])
        metadata=captured['metadata'];self.assertFalse(metadata['content_stored']);self.assertFalse(metadata['secret_values_in_metadata'])
        self.assertNotIn('operations',metadata);self.assertNotIn('secret_reference',json.dumps(metadata))

    def test_execute_checks_exact_binding_and_reserve_finalize(self):
        plan={'ok':True,'projectSlug':'demo','planDigest':'a'*64,'action':'change','sourceEnvironment':None,'targetEnvironment':'preview','expectedRevision':2,'summary':{},'expiresAt':9999999999,'consumed':False}
        self.module._plan=lambda slug,digest:plan
        requested_by='portal:alice';reservation,execution=self.module._transaction_ids('project.environment.change','apr_'+'1'*20,requested_by,'a'*64)
        approval={'approval_id':'apr_'+'1'*20,'status':'approved','project_slug':'demo','action':'project.environment.change','requested_by':requested_by,'approved_by':'professor','reservation_id':None,'metadata_json':json.dumps({'environment_plan_digest':'a'*64,'environment_action':'change','source_environment':None,'target_environment':'preview','expected_revision':2,'content_stored':False,'secret_values_in_metadata':False})}
        states=[approval,{**approval,'status':'reserved','reservation_id':reservation}]
        self.module._approval_get=lambda aid:states.pop(0) if states else {**approval,'status':'consumed','reservation_id':reservation}
        transitions=[]
        self.module._approval_transition=lambda aid,op,payload:(transitions.append((op,payload)) or (200,{'status':'reserved' if op=='reserve' else 'consumed'}))
        self.module._config=lambda method,slug,suffix='',payload=None,query=None:(200,{'ok':True,'revision':3,'secretValuesIncluded':False})
        result=self.module.execute('demo','a'*64,'apr_'+'1'*20,'alice',[])
        self.assertEqual(result['revision'],3);self.assertEqual(result['transaction']['executionId'],execution)
        self.assertEqual([item[0] for item in transitions],['reserve','finalize'])

    def test_human_save_bypasses_approval_service_and_applies_runtime(self):
        calls=[]
        def config(method,slug,suffix='',payload=None,query=None):
            calls.append((method,suffix,payload,query))
            if method=='GET':return 200,{'ok':True,'revision':2,'entries':[],'environmentDigest':'d'*64}
            if suffix=='/change/plan':return 200,{'ok':True,'planDigest':'a'*64,'expectedRevision':2}
            if suffix=='/change/apply':return 200,{'ok':True,'revision':3,'affectedServices':['api'],'environmentDigest':'e'*64}
            raise AssertionError((method,suffix))
        self.module._config=config
        self.module._json_call=lambda *a,**k:(_ for _ in ()).throw(AssertionError('approval_service_must_not_be_called'))
        fake=types.SimpleNamespace(
            environment_runtime_target=lambda slug,env:{'environment':env},
            apply_environment_to_runtime=lambda slug,env,actor:{'ok':True,'environment':env,'changedServices':['api'],'containersRecreated':True,'databasePreserved':True,'secretValuesIncluded':False},
        )
        sys.modules['cloudif_portal_publications']=fake
        try:
            result=self.module.human_save('demo',{'environment':'preview','expectedRevision':2,'changes':[{'operation':'upsert','service':'api','name':'APP_ENV','value':'production','definition':{'secret':False,'runtime':True,'buildTime':False,'restartRequired':True}}],'secretChanges':[]},'alice',[])
        finally:sys.modules.pop('cloudif_portal_publications',None)
        self.assertTrue(result['humanInteractive']);self.assertFalse(result['approvalRequired']);self.assertTrue(result['runtimeApply']['ok'])
        self.assertEqual(result['revision'],2 if calls[-1][0]=='GET' and calls[-1][3] else 3)
        self.assertTrue(any(suffix=='/change/apply' for _,suffix,_,_ in calls))

    def test_human_save_rotates_secret_without_returning_plaintext(self):
        sample_value='TEST_ONLY_MATERIAL_NOT_A_CREDENTIAL'
        entries=[{'service':'api','name':'JWT_SECRET','secret':True,'metadata':{'secret':True,'runtime':True,'buildTime':False,'restartRequired':True}}]
        self.module._config=lambda method,slug,suffix='',payload=None,query=None:(200,{'ok':True,'revision':3,'entries':entries,'environmentDigest':'f'*64})
        seen=[]
        def secret_config(method,slug,suffix='',payload=None,query=None,timeout=45):
            if suffix=='/stage':
                seen.append(payload.get('secretValue'));return 201,{'ok':True,'stageId':'stage_'+'1'*24,'secretValueIncluded':False,'ciphertextIncluded':False}
            if suffix=='/rotate/plan':return 200,{'ok':True,'planDigest':'b'*64}
            if suffix=='/rotate/apply':return 200,{'ok':True,'environmentRevision':3,'secretValueIncluded':False,'ciphertextIncluded':False}
            raise AssertionError(suffix)
        self.module._secret_config=secret_config
        fake=types.SimpleNamespace(environment_runtime_target=lambda slug,env:{'environment':env},apply_environment_to_runtime=lambda slug,env,actor:{'ok':True,'changedServices':['api'],'secretValuesIncluded':False})
        sys.modules['cloudif_portal_publications']=fake
        try:result=self.module.human_save('demo',{'environment':'preview','expectedRevision':3,'changes':[],'secretChanges':[{'service':'api','name':'JWT_SECRET','value':sample_value}]},'alice',[])
        finally:sys.modules.pop('cloudif_portal_publications',None)
        self.assertEqual(seen,[sample_value]);self.assertNotIn(sample_value,json.dumps(result));self.assertEqual(result['secretNamesChanged'],['JWT_SECRET']);self.assertFalse(result['approvalRequired'])

    def test_execute_rejects_wrong_requester_binding(self):
        plan={'ok':True,'planDigest':'a'*64,'action':'change','sourceEnvironment':None,'targetEnvironment':'preview','expectedRevision':0}
        self.module._plan=lambda slug,digest:plan
        self.module._approval_get=lambda aid:{'status':'approved','project_slug':'demo','action':'project.environment.change','requested_by':'portal:other','approved_by':'admin','metadata_json':json.dumps({'environment_plan_digest':'a'*64,'environment_action':'change','source_environment':None,'target_environment':'preview','expected_revision':0,'content_stored':False,'secret_values_in_metadata':False})}
        with self.assertRaisesRegex(PermissionError,'approval_binding_mismatch'):
            self.module.execute('demo','a'*64,'apr_'+'1'*20,'alice',[])

    def test_coexist_routes_require_json_csrf_and_use_environment_module(self):
        source=COEXIST.read_text()
        for marker in (
          "environment/(validate|change/plan|promote/plan|import/plan|human/save|approval/request|change/execute|promote/execute)",
          "from cloudif_project_environment_web import handle_get",
          "from cloudif_project_environment_web import handle_post",
          "'X-CSRF-Token'","_prod_csrf_equal","application/json","payload_too_large",
        ):self.assertIn(marker,source)
        post_start=source.index("environment_match = re.fullmatch(r'/cloudiff?/portal/api/projects/")
        post_start=source.index("environment_match = re.fullmatch",post_start+1)
        post_end=source.index('query_action =',post_start)
        block=source[post_start:post_end]
        self.assertLess(block.index('_prod_csrf_equal'),block.index('handle_post'))


if __name__=='__main__':unittest.main()
