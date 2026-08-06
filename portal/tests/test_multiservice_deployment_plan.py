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
    spec=importlib.util.spec_from_file_location('multiservice_deployment_plan_test',SOURCE)
    module=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(module)
    return module


class MultiserviceDeploymentPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.module=load_module()

    def configuration(self,secret_ref=True):
        required={'DATABASE_URL':{'services':['api']}}
        if secret_ref:required['DATABASE_URL']['secretRef']='supabase.database_url'
        return {
            'ok':True,'configured':True,'currentRevision':2,
            'configDigest':'c'*64,'toolchainDigest':'t'*64,
            'configuration':{
                'project':{'type':'multi-service','primaryService':'web'},
                'environment':{'variables':{'PUBLIC_MODE':'school'},'required':required},
                'hooks':{'preBuild':[{'service':'web','script':'scripts/prepare.sh'}]},
                'services':{
                    'web':{'runtime':'static','routes':[{'path':'/'}],'environment':{'variables':{'API_PREFIX':'/api'},'required':[]}},
                    'api':{'runtime':'node','routes':[{'path':'/api'}],'environment':{'variables':{},'required':['DATABASE_URL']}},
                },
            },
        }

    def state(self,status='ready'):
        return {'ok':True,'status':status,'configRevision':2,'membershipRevision':4,'aclDigest':'a'*64,'latestBuildJobId':'build_'+'b'*24}

    def build(self,status='succeeded',config_revision=2,config_digest='c'*64):
        return {
            'ok':True,'status':status,
            'payload':{'config_revision':config_revision,'config_digest':config_digest,'toolchain_digest':'t'*64,'archive_sha256':'f'*64},
            'result':{
                'ok':True,'planDigest':'p'*64,'configRevision':config_revision,
                'configDigest':config_digest,'toolchainDigest':'t'*64,'archiveSha256':'f'*64,
                'applications':[
                    {'service':'web','runtime':'static','containerPort':8080,'healthcheck':'/__cloudif_health','applicationDigest':'1'*64,'image':{'immutableReference':'sha256:'+'2'*64}},
                    {'service':'api','runtime':'node','containerPort':3000,'healthcheck':'/health','applicationDigest':'3'*64,'image':{'immutableReference':'sha256:'+'4'*64}},
                ],
            },
        }

    def plan(self,configuration=None,state=None,build=None,environment='homologation'):
        tenant_env={
            'POSTGRES_PASSWORD':'database-password-for-test',
            'POSTGRES_PORT':'54400',
            'SUPABASE_PUBLIC_URL':'https://tenant-demo.cloudiff.duckdns.org',
            'ANON_KEY':'anon-test',
            'SERVICE_ROLE_KEY':'service-role-test',
            'JWT_SECRET':'jwt-test',
        }
        with patch.object(self.module,'_multiservice_configuration',return_value=configuration or self.configuration()),\
             patch.object(self.module,'_multiservice_reconciliation',return_value=state or self.state()),\
             patch.object(self.module,'_multiservice_build',return_value=build or self.build()),\
             patch.object(self.module,'_tenant_env',return_value=('tenant-demo',tenant_env)),\
             patch.object(self.module,'_production_config',return_value={}):
            return self.module._multiservice_deployment_plan({
                'project_slug':'demo','build_job_id':'build_'+'b'*24,
                'environment':environment,'trace_id':'test-trace',
            })

    def test_ready_homologation_plan_binds_all_material(self):
        plan=self.plan()
        self.assertTrue(plan['execution_allowed'])
        self.assertEqual(plan['blockers'],[])
        self.assertTrue(plan['side_effect_free'])
        self.assertFalse(plan['containers_created'])
        self.assertEqual(plan['operation']['config_revision'],2)
        self.assertEqual(plan['operation']['config_digest'],'c'*64)
        self.assertEqual(plan['operation']['toolchain_digest'],'t'*64)
        self.assertEqual(plan['operation']['archive_sha256'],'f'*64)
        self.assertEqual({x['service'] for x in plan['summary']['services']},{'web','api'})
        self.assertEqual({x['pathPrefix'] for x in plan['summary']['routes']},{'/','/api'})
        self.assertIn('PUBLIC_MODE',plan['summary']['variables']['web'])
        self.assertIn('API_PREFIX',plan['summary']['variables']['web'])
        self.assertEqual(plan['summary']['hooks'],[{'phase':'preBuild','service':'web','script':'scripts/prepare.sh'}])
        rendered=str(plan)
        self.assertNotIn('school',rendered)
        self.assertFalse(plan['secret_values_included'])

    def test_secret_rotation_changes_digest_without_exposing_value(self):
        configuration=self.configuration()
        with patch.object(self.module,'_multiservice_configuration',return_value=configuration),\
             patch.object(self.module,'_multiservice_reconciliation',return_value=self.state()),\
             patch.object(self.module,'_multiservice_build',return_value=self.build()),\
             patch.object(self.module,'_production_config',return_value={}):
            with patch.object(self.module,'_tenant_env',return_value=('tenant-demo',{'POSTGRES_PASSWORD':'first-secret','POSTGRES_PORT':'54400'})):
                first=self.module._multiservice_deployment_plan({'project_slug':'demo','build_job_id':'build_'+'b'*24,'environment':'homologation','trace_id':'one'})
            with patch.object(self.module,'_tenant_env',return_value=('tenant-demo',{'POSTGRES_PASSWORD':'second-secret','POSTGRES_PORT':'54400'})):
                second=self.module._multiservice_deployment_plan({'project_slug':'demo','build_job_id':'build_'+'b'*24,'environment':'homologation','trace_id':'two'})
        self.assertNotEqual(first['variables_digest'],second['variables_digest'])
        self.assertNotEqual(first['deployment_plan_digest'],second['deployment_plan_digest'])
        rendered=str(first)+str(second)
        self.assertNotIn('first-secret',rendered)
        self.assertNotIn('second-secret',rendered)
        self.assertFalse(first['secret_values_included'])

    def test_reconciliation_and_build_mismatch_block_execution(self):
        plan=self.plan(state=self.state('toolchain_build_required'),build=self.build(config_revision=1,config_digest='d'*64))
        self.assertFalse(plan['execution_allowed'])
        self.assertIn('reconciliation_not_ready:toolchain_build_required',plan['blockers'])
        self.assertIn('build_config_revision_mismatch',plan['blockers'])
        self.assertIn('build_config_digest_mismatch',plan['blockers'])

    def test_missing_reference_is_actionable_and_value_is_not_exposed(self):
        plan=self.plan(configuration=self.configuration(secret_ref=False))
        self.assertFalse(plan['execution_allowed'])
        self.assertIn('required_environment_unresolved',plan['blockers'])
        ref=next(x for x in plan['summary']['requiredReferences'] if x['name']=='DATABASE_URL')
        self.assertFalse(ref['configured'])
        self.assertNotIn('reference',ref)

    def test_production_requires_enabled_target(self):
        plan=self.plan(environment='production')
        self.assertFalse(plan['execution_allowed'])
        self.assertIn('production_target_not_enabled',plan['blockers'])


if __name__=='__main__':unittest.main()
