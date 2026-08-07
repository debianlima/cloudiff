from __future__ import annotations

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'components/control-plane/current-apps/deployment-broker-current/cloudif-deployment-broker.py'


def load_module():
    fake=types.ModuleType('cloudif_release_manager')
    fake.project_setting=lambda slug:{'tenant':'tenant-'+slug}
    sys.modules['cloudif_release_manager']=fake
    spec=importlib.util.spec_from_file_location('multiservice_deployment_execution_test',SOURCE)
    module=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(module)
    return module


class MultiserviceDeploymentExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.module=load_module()

    def plan(self,public_value='info',secret_reference=''):
        public={'api':{'LOG_LEVEL':public_value}}
        variables_digest=self.module.hashlib.sha256(self.module.json.dumps(public,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        runtime={
            'ok':True,'internal':True,'job_id':'build_'+'b'*24,'project_slug':'demo','environment':'homologation',
            'config_revision':2,'config_digest':'c'*64,'toolchain_digest':'a'*64,'archive_sha256':'f'*64,'plan_digest':'e'*64,
            'publicRuntimeEnvironment':public,'secretRuntimeReferences':{'api':({'DATABASE_URL':secret_reference} if secret_reference else {})},
            'buildEnvironmentDigest':'4'*64,'runtimeEnvironmentDigest':'5'*64,'environmentDigest':'6'*64,
            'secretValuesIncluded':False,
        }
        return {
            'ok':True,'execution_allowed':not bool(secret_reference),'blockers':(['secret-resolution-unavailable'] if secret_reference else []),
            'project_slug':'demo','environment':'homologation','deployment_plan_digest':'d'*64,'variables_digest':variables_digest,
            '_internal_runtime_configuration':runtime,
            'operation':{
                'build_job_id':'build_'+'b'*24,'build_plan_digest':'e'*64,
                'config_revision':2,'config_digest':'c'*64,'toolchain_digest':'a'*64,'archive_sha256':'f'*64,
                'applications':[{'service':'api','imageId':'sha256:'+'1'*64,'applicationDigest':'2'*64,'port':3000,'healthcheck':'/health'}],
                'routes':[{'pathPrefix':'/','service':'api','stripPrefix':False}],
            },
        }

    def request(self):
        return {
            'project_slug':'demo','build_job_id':'build_'+'b'*24,
            'environment':'homologation','trace_id':'trace-test',
            'deployment_plan_digest':'d'*64,
        }

    def test_public_runtime_values_are_sent_only_to_internal_executor(self):
        captured={}
        def executor(method,path,payload=None,timeout=300):
            captured.update({'method':method,'path':path,'payload':payload})
            return 201,{'ok':True,'deployment_id':'dep_'+'a'*24,'status':'running'}
        with patch.object(self.module,'_multiservice_deployment_plan',return_value=self.plan()),             patch.object(self.module,'_deployment_executor_call',side_effect=executor),             patch.object(self.module,'idem_mark_effect') as mark:
            code,result=self.module._multiservice_execute(self.request(),'exec_'+'3'*32)
        self.assertEqual(code,201);self.assertTrue(result['ok'])
        self.assertEqual(captured['method'],'POST');self.assertEqual(captured['path'],'/v1/deployments')
        self.assertEqual(captured['payload']['variables']['api']['LOG_LEVEL'],'info')
        self.assertEqual(captured['payload']['runtimeConfiguration']['publicRuntimeEnvironment']['api']['LOG_LEVEL'],'info')
        self.assertNotIn('info',str(result))
        self.assertFalse(result['variable_values_returned']);self.assertFalse(result['secret_values_in_metadata'])
        mark.assert_called_once_with('exec_'+'3'*32)

    def test_runtime_configuration_digest_change_blocks_execution_before_executor(self):
        plan=self.plan();plan['variables_digest']='9'*64
        with patch.object(self.module,'_multiservice_deployment_plan',return_value=plan),             patch.object(self.module,'_deployment_executor_call') as executor:
            with self.assertRaisesRegex(ValueError,'variables_digest_changed'):
                self.module._multiservice_execute(self.request(),'exec_'+'4'*32)
        executor.assert_not_called()

    def test_secret_reference_is_resolved_only_after_approval_bound_plan(self):
        plan=self.plan(secret_reference='cloudiff-secret://demo/homologation/api/DATABASE_URL/v1')
        plan['execution_allowed']=True;plan['blockers']=[]
        resolved={'api':{'DATABASE_URL':'runtime-only-secret'}};captured={}
        def executor(method,path,payload=None,timeout=300):
            captured['payload']=json.loads(json.dumps(payload));return 201,{'ok':True,'deployment_id':'dep_'+'a'*24,'status':'running'}
        with patch.object(self.module,'_multiservice_deployment_plan',return_value=plan),             patch.object(self.module,'_resolve_runtime_secrets',return_value=resolved),             patch.object(self.module,'_deployment_executor_call',side_effect=executor),             patch.object(self.module,'idem_mark_effect'):
            code,result=self.module._multiservice_execute(self.request(),'exec_'+'5'*32)
        self.assertEqual(code,201);self.assertEqual(captured['payload']['variables']['api']['DATABASE_URL'],'runtime-only-secret')
        self.assertEqual(captured['payload']['runtimeConfiguration']['secretRuntimeReferences'],{'api':{}})
        self.assertNotIn('runtime-only-secret',json.dumps(result));self.assertFalse(result['secret_values_in_metadata']);self.assertFalse(result['secret_references_in_metadata'])
        self.assertEqual(resolved,{})

    def test_secret_resolution_failure_happens_before_executor_effect(self):
        plan=self.plan(secret_reference='cloudiff-secret://demo/homologation/api/DATABASE_URL/v1');plan['execution_allowed']=True;plan['blockers']=[]
        with patch.object(self.module,'_multiservice_deployment_plan',return_value=plan),             patch.object(self.module,'_resolve_runtime_secrets',side_effect=RuntimeError('secret_resolution_failed')),             patch.object(self.module,'_deployment_executor_call') as executor:
            with self.assertRaisesRegex(RuntimeError,'secret_resolution_failed'):
                self.module._multiservice_execute(self.request(),'exec_'+'6'*32)
        executor.assert_not_called()

    def test_execution_id_deterministically_selects_deployment_id(self):
        first=self.module._deployment_id('exec_'+'1'*32)
        second=self.module._deployment_id('exec_'+'1'*32)
        other=self.module._deployment_id('exec_'+'2'*32)
        self.assertRegex(first,r'^dep_[a-f0-9]{24}$')
        self.assertEqual(first,second);self.assertNotEqual(first,other)


if __name__=='__main__':unittest.main()
