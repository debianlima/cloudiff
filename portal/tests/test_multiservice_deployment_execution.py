from __future__ import annotations

import importlib.util
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

    def plan(self):
        return {
            'ok':True,'execution_allowed':True,'blockers':[],
            'project_slug':'demo','environment':'homologation',
            'deployment_plan_digest':'d'*64,'variables_digest':'v'*64,
            'operation':{
                'build_job_id':'build_'+'b'*24,'build_plan_digest':'e'*64,
                'config_revision':2,'config_digest':'c'*64,'toolchain_digest':'a'*64,
                'archive_sha256':'f'*64,
                'applications':[
                    {'service':'api','imageId':'sha256:'+'1'*64,'applicationDigest':'2'*64,'port':3000,'healthcheck':'/health'},
                ],
                'routes':[{'pathPrefix':'/','service':'api','stripPrefix':False}],
            },
        }

    def request(self):
        return {
            'project_slug':'demo','build_job_id':'build_'+'b'*24,
            'environment':'homologation','trace_id':'trace-test',
            'deployment_plan_digest':'d'*64,
        }

    def test_secret_values_are_sent_only_to_internal_executor(self):
        captured={}
        resolved={'values':{'api':{'DATABASE_URL':'postgres://private-value'}},'variablesDigest':'v'*64,'unresolved':[]}
        def executor(method,path,payload=None,timeout=300):
            captured.update({'method':method,'path':path,'payload':payload})
            return 201,{'ok':True,'deployment_id':'dep_'+'a'*24,'status':'running'}
        with patch.object(self.module,'_multiservice_deployment_plan',return_value=self.plan()),\
             patch.object(self.module,'_multiservice_configuration',return_value={'configuration':{}}),\
             patch.object(self.module,'_resolve_environment',return_value=resolved),\
             patch.object(self.module,'_deployment_executor_call',side_effect=executor),\
             patch.object(self.module,'idem_mark_effect') as mark:
            code,result=self.module._multiservice_execute(self.request(),'exec_'+'3'*32)
        self.assertEqual(code,201);self.assertTrue(result['ok'])
        self.assertEqual(captured['method'],'POST');self.assertEqual(captured['path'],'/v1/deployments')
        self.assertEqual(captured['payload']['variables']['api']['DATABASE_URL'],'postgres://private-value')
        self.assertNotIn('postgres://private-value',str(result))
        self.assertFalse(result['variable_values_returned'])
        self.assertFalse(result['secret_values_in_metadata'])
        mark.assert_called_once_with('exec_'+'3'*32)

    def test_rotated_variables_block_execution_before_executor(self):
        resolved={'values':{'api':{'DATABASE_URL':'rotated'}},'variablesDigest':'9'*64,'unresolved':[]}
        with patch.object(self.module,'_multiservice_deployment_plan',return_value=self.plan()),\
             patch.object(self.module,'_multiservice_configuration',return_value={'configuration':{}}),\
             patch.object(self.module,'_resolve_environment',return_value=resolved),\
             patch.object(self.module,'_deployment_executor_call') as executor:
            with self.assertRaisesRegex(ValueError,'variables_digest_changed'):
                self.module._multiservice_execute(self.request(),'exec_'+'4'*32)
        executor.assert_not_called()

    def test_blocked_plan_never_resolves_values_or_calls_executor(self):
        blocked={**self.plan(),'execution_allowed':False,'blockers':['configuration_required']}
        with patch.object(self.module,'_multiservice_deployment_plan',return_value=blocked),\
             patch.object(self.module,'_resolve_environment') as resolver,\
             patch.object(self.module,'_deployment_executor_call') as executor:
            with self.assertRaises(PermissionError):
                self.module._multiservice_execute(self.request(),'exec_'+'5'*32)
        resolver.assert_not_called();executor.assert_not_called()

    def test_execution_id_deterministically_selects_deployment_id(self):
        first=self.module._deployment_id('exec_'+'1'*32)
        second=self.module._deployment_id('exec_'+'1'*32)
        other=self.module._deployment_id('exec_'+'2'*32)
        self.assertRegex(first,r'^dep_[a-f0-9]{24}$')
        self.assertEqual(first,second);self.assertNotEqual(first,other)


if __name__=='__main__':unittest.main()
