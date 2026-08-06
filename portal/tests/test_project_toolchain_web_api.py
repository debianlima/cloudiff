from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
WEB=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_toolchain_web.py'
COEXIST=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py'


def load_module():
    spec=importlib.util.spec_from_file_location('project_toolchain_web_api_test',WEB)
    module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


class ProjectToolchainWebAPITests(unittest.TestCase):
    def setUp(self):
        self.module=load_module()
        self.module.authorization=lambda slug,user,groups:{'canRead':user!='denied','canWrite':user in {'owner','professor'},'role':'owner' if user=='owner' else 'administrator','project':{'slug':slug}}

    def plan(self):
        return {
          'ok':True,'valid':True,'project_slug':'demo','ref':'main','config_revision':4,
          'config_digest':'b'*64,'requested_toolchain_digest':'c'*64,'archive_sha256':'a'*64,
          'plan_digest':'d'*64,'blocked':[],'services':[{'service':'api','toolchainDigest':'e'*64}],
          'summary':{'serviceCount':1,'secretsIncluded':False},
        }

    def activation_plan(self):
        return {'ok':True,'project_slug':'demo','environment':'preview','job_id':'toolchain_'+'1'*24,'expected_revision':0,'next_revision':1,'plan_digest':'f'*64,'after':[{'service':'api','image_record_id':'img_'+'2'*24,'toolchain_digest':'e'*64}],'containers_changed':False}

    def test_read_routes_require_project_access(self):
        self.module._build=lambda method,path,payload=None,timeout=180:(200,{'ok':True,'secret_values_included':False,'path':path})
        code,data=self.module.handle_get('demo','',{'ref':'main'},'viewer',[])
        self.assertEqual(code,200);self.assertIn('/v1/projects/demo/toolchain?',data['path'])
        code,data=self.module.handle_get('demo','images',{},'viewer',[])
        self.assertEqual(code,200);self.assertTrue(data['path'].endswith('/toolchain/images'))
        code,data=self.module.handle_get('demo','',{},'denied',[])
        self.assertEqual(code,403);self.assertEqual(data['error']['code'],'forbidden')

    def test_viewer_cannot_plan_build_or_activate(self):
        for operation in ('validate','build/plan','build/approval/request','build/execute','activation/plan','activation/approval/request','activation/execute'):
            with self.subTest(operation=operation),self.assertRaisesRegex(PermissionError,'forbidden'):
                self.module.handle_post('demo',operation,{},'viewer',[])

    def test_build_approval_contains_only_digests_names_and_flags(self):
        self.module._plan=lambda slug,ref,expected,validate=False:self.plan()
        captured={}
        def fake_json(method,url,token,payload=None,timeout=45):
            captured.update(payload or {});return 201,{'ok':True,'approval_id':'apr_'+'1'*20,'status':'pending','expires_at':9999999999}
        self.module._json_call=fake_json
        result=self.module.request_build_approval('demo',{'ref':'main','expectedRevision':4,'planDigest':'d'*64,'reason':'Construir toolchain'},'owner',[])
        self.assertEqual(result['action'],'project.toolchain.build')
        metadata=captured['metadata']
        self.assertEqual(metadata['toolchain_plan_digest'],'d'*64)
        self.assertEqual(metadata['services'],[{'service':'api','toolchainDigest':'e'*64}])
        self.assertFalse(metadata['content_stored']);self.assertFalse(metadata['secret_values_in_metadata'])
        serialized=json.dumps(metadata)
        self.assertNotIn('scriptContent',serialized);self.assertNotIn('secret_reference',serialized)

    def test_build_execute_uses_reserve_then_broker_then_finalize(self):
        plan=self.plan();self.module._plan=lambda *args,**kwargs:plan
        requested='portal:owner';approval_id='apr_'+'1'*20
        reservation,execution=self.module._transaction_ids('project.toolchain.build',approval_id,requested,'d'*64)
        approval={'status':'approved','project_slug':'demo','action':'project.toolchain.build','requested_by':requested,'approved_by':'admin','reservation_id':None,'metadata_json':json.dumps({'toolchain_plan_digest':'d'*64,'config_revision':4,'config_digest':'b'*64,'requested_toolchain_digest':'c'*64,'archive_sha256':'a'*64,'ref':'main','services':[{'service':'api','toolchainDigest':'e'*64}],'content_stored':False,'secret_values_in_metadata':False})}
        states=[approval,{**approval,'status':'reserved','reservation_id':reservation}]
        self.module._approval_get=lambda aid:states.pop(0) if states else {**approval,'status':'consumed','reservation_id':reservation}
        transitions=[]
        self.module._approval_transition=lambda aid,op,payload:(transitions.append(op) or (200,{'status':'reserved' if op=='reserve' else 'consumed'}))
        calls=[]
        self.module._build=lambda method,path,payload=None,timeout=180:(calls.append((method,path,payload)) or (202,{'ok':True,'job_id':'toolchain_'+'3'*24,'status':'queued'}))
        result=self.module.execute_build('demo',{'ref':'main','expectedRevision':4,'planDigest':'d'*64,'approvalId':approval_id},'owner',[])
        self.assertEqual(transitions,['reserve','finalize'])
        self.assertEqual(calls[0][1],'/v1/toolchain/build')
        self.assertTrue(calls[0][2]['approved'])
        self.assertEqual(result['transaction']['executionId'],execution)
        self.assertFalse(result['imagesActivated']);self.assertFalse(result['containersChanged'])

    def test_activation_approval_and_execution_are_separate_from_build(self):
        plan=self.activation_plan();self.module._activation_plan=lambda *args,**kwargs:plan
        captured={}
        self.module._json_call=lambda method,url,token,payload=None,timeout=45:(captured.update(payload or {}) or (201,{'ok':True,'approval_id':'apr_'+'4'*20,'status':'pending','expires_at':9999999999}))
        approval=self.module.request_activation_approval('demo',{'environment':'preview','jobId':plan['job_id'],'expectedRevision':0,'planDigest':'f'*64,'reason':'Ativar em preview'},'owner',[])
        self.assertEqual(approval['action'],'project.toolchain.activation')
        self.assertEqual(captured['metadata']['after'],plan['after'])
        self.assertFalse(captured['metadata']['content_stored'])

    def test_activation_execute_rejects_build_approval(self):
        plan=self.activation_plan();self.module._activation_plan=lambda *args,**kwargs:plan
        self.module._approval_get=lambda aid:{'status':'approved','project_slug':'demo','action':'project.toolchain.build','requested_by':'portal:owner','approved_by':'admin','metadata_json':'{}'}
        with self.assertRaisesRegex(PermissionError,'approval_binding_mismatch'):
            self.module.execute_activation('demo',{'environment':'preview','jobId':plan['job_id'],'expectedRevision':0,'planDigest':'f'*64,'approvalId':'apr_'+'5'*20},'owner',[])

    def test_portal_routes_require_csrf_before_toolchain_handler(self):
        source=COEXIST.read_text()
        self.assertIn("toolchain/(validate|build/plan|build/approval/request|build/execute|activation/plan|activation/approval/request|activation/execute)",source)
        self.assertIn('from cloudif_project_toolchain_web import handle_get as handle_toolchain_get',source)
        self.assertIn('from cloudif_project_toolchain_web import handle_post as handle_toolchain_post',source)
        start=source.index("toolchain_match = re.fullmatch(r'/cloudiff?/portal/api/projects/",source.index('def do_POST'))
        end=source.index('environment_match = re.fullmatch',start)
        block=source[start:end]
        self.assertIn('_prod_csrf_equal',block);self.assertIn('application/json',block)
        self.assertLess(block.index('_prod_csrf_equal'),block.index('handle_toolchain_post'))


if __name__=='__main__':unittest.main()
