from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
WEB=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_secret_web.py'
COEXIST=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py'
ENVWEB=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_environment_web.py'


def load_module(root:Path):
    control=root/'control.db';c=sqlite3.connect(control)
    c.executescript('''
      create table projects(project_id text primary key,slug text unique,name text,owner text,tenant text,status text);
      create table project_acl(project_id text,subject_type text,subject text,role text);
      insert into projects values('p1','demo','Demo','alice','tenant-demo','active');
      insert into project_acl values('p1','user','bob','maintainer');
      insert into project_acl values('p1','user','viewer','viewer');
    ''');c.commit();c.close()
    env_spec=importlib.util.spec_from_file_location('cloudif_project_environment_web',ENVWEB);env=importlib.util.module_from_spec(env_spec);assert env_spec.loader;env_spec.loader.exec_module(env);env.CONTROL_DB=control;sys.modules['cloudif_project_environment_web']=env
    spec=importlib.util.spec_from_file_location('project_secret_web_test',WEB);module=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(module);return module


class ProjectSecretWebAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.module=load_module(Path(self.temp.name))
    def tearDown(self):
        sys.modules.pop('cloudif_project_environment_web',None);self.temp.cleanup()

    def plan(self,action='rotate'):
        return {'ok':True,'projectSlug':'demo','planDigest':'a'*64,'action':action,'environment':'preview','service':'api','name':'DATABASE_URL','stageId':('stage_'+'1'*24 if action=='rotate' else None),'secretReference':'cloudiff-secret://demo/preview/api/DATABASE_URL/v1','expectedRevision':2,'targetVersion':1,'definition':{'secret':True,'required':True},'status':'planned','expiresAt':9999999999,'consumed':False,'secretValueIncluded':False,'ciphertextIncluded':False}

    def test_reader_and_writer_authorization_reuses_existing_project_acl(self):
        self.assertTrue(self.module._require_write('demo','alice',[])['canWrite'])
        self.assertTrue(self.module._require_write('demo','bob',[])['canWrite'])
        self.assertTrue(self.module._require_write('demo','prof',['CloudIF-Professor'])['canWrite'])
        self.assertTrue(self.module._require_read('demo','viewer',[])['canRead'])
        with self.assertRaises(PermissionError):self.module._require_write('demo','viewer',[])

    def test_stage_forwards_value_once_but_never_returns_or_retains_it(self):
        captured={}
        def config(method,slug,suffix='',payload=None,query=None,timeout=45):
            captured.update(payload or {});return 201,{'ok':True,'stageId':'stage_'+'1'*24,'secretValueIncluded':False,'ciphertextIncluded':False}
        self.module._config=config
        code,result=self.module.handle_post('demo','stage',{'environment':'preview','service':'api','name':'DATABASE_URL','secretValue':'do-not-echo'},'alice',[])
        self.assertEqual(code,201);self.assertFalse(result['secretValueIncluded']);self.assertNotIn('do-not-echo',json.dumps(result))
        self.assertEqual(captured['secretValue'],'do-not-echo')

    def test_approval_metadata_contains_digest_and_scope_not_secret_material(self):
        self.module._plan=lambda slug,digest:self.plan('rotate')
        captured={}
        def call(method,url,token,payload=None,timeout=45):
            captured.update(payload or {});return 201,{'ok':True,'approval_id':'apr_'+'1'*20,'status':'approved','expires_at':9999999999,'policy_applied':True,'approval_policy_id':'pol_'+'1'*20}
        self.module._json_call=call
        result=self.module.request_approval('demo','a'*64,'Rotacionar credencial','alice',[])
        self.assertTrue(result['policyApplied']);self.assertEqual(result['status'],'approved')
        metadata=captured['metadata'];self.assertEqual(metadata['secret_plan_digest'],'a'*64);self.assertFalse(metadata['content_stored']);self.assertFalse(metadata['secret_values_in_metadata']);self.assertFalse(metadata['ciphertext_in_metadata'])
        serialized=json.dumps(metadata);self.assertNotIn('secretValue',serialized);self.assertNotIn('ciphertext',serialized.lower().replace('ciphertext_in_metadata',''))

    def test_execute_uses_reserve_effect_finalize_and_exact_plan_binding(self):
        plan=self.plan('rotate');self.module._plan=lambda slug,digest:plan
        requested_by='portal:alice';approval_id='apr_'+'1'*20;reservation,execution=self.module._transaction_ids(self.module.ACTIONS['rotate'],approval_id,requested_by,'a'*64)
        metadata=self.module._approval_metadata(plan)
        approval={'status':'approved','project_slug':'demo','action':self.module.ACTIONS['rotate'],'requested_by':requested_by,'approved_by':'professor','reservation_id':None,'metadata_json':json.dumps(metadata)}
        states=[approval,{**approval,'status':'reserved','reservation_id':reservation}]
        self.module._approval_get=lambda aid:states.pop(0) if states else {**approval,'status':'consumed','reservation_id':reservation}
        transitions=[];self.module._approval_transition=lambda aid,op,payload:(transitions.append((op,payload)) or (200,{'status':'reserved' if op=='reserve' else 'consumed'}))
        captured={}
        self.module._config=lambda method,slug,suffix='',payload=None,query=None,timeout=45:(captured.update({'suffix':suffix,'payload':payload}) or (200,{'ok':True,'secretReference':plan['secretReference'],'secretValueIncluded':False,'ciphertextIncluded':False}))
        result=self.module.execute('demo','a'*64,approval_id,{},'alice',[])
        self.assertEqual([item[0] for item in transitions],['reserve','finalize']);self.assertEqual(captured['suffix'],'/rotate/apply');self.assertEqual(captured['payload']['stageId'],plan['stageId']);self.assertEqual(result['transaction']['executionId'],execution)

    def test_exceptional_read_requires_maintainer_or_higher(self):
        plan=self.plan('read');plan['stageId']=None;self.module._plan=lambda slug,digest:plan
        with self.assertRaisesRegex(PermissionError,'secret_read_forbidden'):
            self.module.request_approval('demo','a'*64,'Diagnóstico','viewer',[])
        self.assertEqual(self.module._require_secret_read('demo','alice',[])['role'],'owner')
        self.assertGreaterEqual(self.module._require_secret_read('demo','prof',['CloudIF-Professor'])['rank'],80)

    def test_exceptional_read_returns_value_once_with_no_store_contract(self):
        plan=self.plan('read');plan['stageId']=None;self.module._plan=lambda slug,digest:plan
        requested_by='portal:alice';approval_id='apr_'+'2'*20;reservation,execution=self.module._transaction_ids(self.module.ACTIONS['read'],approval_id,requested_by,'a'*64)
        metadata=self.module._approval_metadata(plan)
        approval={'status':'approved','project_slug':'demo','action':self.module.ACTIONS['read'],'requested_by':requested_by,'approved_by':'professor','reservation_id':None,'metadata_json':json.dumps(metadata)}
        states=[approval,{**approval,'status':'reserved','reservation_id':reservation}]
        self.module._approval_get=lambda aid:states.pop(0) if states else {**approval,'status':'consumed','reservation_id':reservation}
        transitions=[];self.module._approval_transition=lambda aid,op,payload:(transitions.append(op) or (200,{'status':'reserved' if op=='reserve' else 'consumed'}))
        self.module._config=lambda method,slug,suffix='',payload=None,query=None,timeout=45:(200,{'ok':True,'secretReference':plan['secretReference'],'secretValue':'one-time-value','secretValueIncluded':True,'ciphertextIncluded':False,'oneTime':True,'cacheControl':'no-store','auditRecorded':True})
        result=self.module.execute('demo','a'*64,approval_id,{'secretReference':plan['secretReference']},'alice',[])
        self.assertEqual(result['secretValue'],'one-time-value');self.assertTrue(result['secretValuesIncluded']);self.assertTrue(result['oneTime']);self.assertEqual(result['cacheControl'],'no-store');self.assertEqual(transitions,['reserve','finalize'])

    def test_common_get_never_resolves_plaintext(self):
        self.module._config=lambda method,slug,suffix='',payload=None,query=None,timeout=45:(200,{'ok':True,'secrets':[{'name':'DATABASE_URL','status':'active'}],'secretValuesIncluded':False,'ciphertextsIncluded':False})
        code,result=self.module.handle_get('demo','',{'environment':'preview'},'viewer',[])
        self.assertEqual(code,200);self.assertFalse(result['secretValuesIncluded']);self.assertNotIn('resolvedSecrets',result)
        self.assertNotIn('resolve-internal',WEB.read_text())

    def test_portal_routes_are_isolated_and_post_requires_existing_csrf_guard(self):
        source=COEXIST.read_text();self.assertIn('from cloudif_project_secret_web import handle_get as handle_secret_get',source);self.assertIn('from cloudif_project_secret_web import handle_post as handle_secret_post',source)
        start=source.index("secret_match = re.fullmatch(r'/cloudiff?/portal/api/projects/",source.index('def do_POST'))
        end=source.index('environment_match = re.fullmatch',start);block=source[start:end]
        self.assertIn("'X-CSRF-Token'",block);self.assertIn('_prod_csrf_equal',block);self.assertLess(block.index('_prod_csrf_equal'),block.index('handle_secret_post'))
        self.assertNotIn('resolve-internal',block)

    def test_portal_exceptional_read_is_post_only_and_no_store(self):
        source=COEXIST.read_text()
        self.assertIn('read/plan|read/approval/request|read/execute',source)
        self.assertIn("if operation=='read/execute':",source)
        self.assertIn("('Cache-Control','no-store, max-age=0')",source)
        self.assertIn("('Pragma','no-cache')",source)
        get_start=source.index('def do_GET') if 'def do_GET' in source else 0
        post_start=source.index('def do_POST') if 'def do_POST' in source else len(source)
        self.assertNotIn('read/execute',source[get_start:post_start])



if __name__=='__main__':unittest.main()
