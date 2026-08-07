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

    def runtime_configuration(self,environment='homologation',secret=False,environment_digest='6'*64,config_revision=2,config_digest='c'*64):
        return {
            'ok':True,'internal':True,'job_id':'build_'+'b'*24,'project_slug':'demo','environment':environment,
            'config_revision':config_revision,'config_digest':config_digest,'toolchain_digest':'t'*64,
            'archive_sha256':'f'*64,'plan_digest':'p'*64,
            'publicRuntimeEnvironment':{'web':{'PUBLIC_MODE':'school','API_PREFIX':'/api'},'api':{'LOG_LEVEL':'info'}},
            'secretRuntimeReferences':{'web':{},'api':({'DATABASE_URL':'vault://project/demo/database'} if secret else {})},
            'buildEnvironmentDigest':'4'*64,'runtimeEnvironmentDigest':'5'*64,'environmentDigest':environment_digest,
            'serviceArtifacts':[{'service':'web','imageRef':'cloudif-app/demo-web:1','imageId':'sha256:'+'2'*64},{'service':'api','imageRef':'cloudif-app/demo-api:1','imageId':'sha256:'+'4'*64}],
            'secretValuesIncluded':False,'secretReferencesIncluded':secret,'containersChanged':False,
        }

    def plan(self,configuration=None,state=None,build=None,environment='homologation',runtime_configuration=None):
        runtime_configuration = runtime_configuration or self.runtime_configuration(environment=environment)
        with patch.object(self.module,'_multiservice_configuration',return_value=configuration or self.configuration()),             patch.object(self.module,'_multiservice_reconciliation',return_value=state or self.state()),             patch.object(self.module,'_multiservice_build',return_value=build or self.build()),             patch.object(self.module,'_build_runtime_configuration',return_value=runtime_configuration),             patch.object(self.module,'_production_config',return_value={}):
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
        self.assertIn('PUBLIC_MODE',plan['summary']['runtimeEnvironment']['variableNames']['web'])
        self.assertIn('API_PREFIX',plan['summary']['runtimeEnvironment']['variableNames']['web'])
        self.assertEqual(plan['summary']['hooks'],[{'phase':'preBuild','service':'web','script':'scripts/prepare.sh'}])
        rendered=str(plan)
        self.assertNotIn('school',rendered)
        self.assertFalse(plan['secret_values_included'])

    def test_environment_revision_changes_digest_without_exposing_runtime_values(self):
        first=self.plan(runtime_configuration=self.runtime_configuration(environment_digest='6'*64))
        second=self.plan(runtime_configuration=self.runtime_configuration(environment_digest='7'*64))
        self.assertNotEqual(first['deployment_plan_digest'],second['deployment_plan_digest'])
        rendered=str(first)+str(second)
        self.assertNotIn('school',rendered)
        self.assertNotIn('vault://',rendered)
        self.assertFalse(first['secret_values_included'])
        self.assertFalse(first['secret_references_included'])

    def test_reconciliation_and_build_mismatch_block_execution(self):
        plan=self.plan(state=self.state('toolchain_build_required'),build=self.build(config_revision=1,config_digest='d'*64),runtime_configuration=self.runtime_configuration(config_revision=1,config_digest='d'*64))
        self.assertFalse(plan['execution_allowed'])
        self.assertIn('reconciliation-not-ready:toolchain_build_required',plan['blockers'])
        self.assertIn('build-config-revision-mismatch',plan['blockers'])
        self.assertIn('build-config-digest-mismatch',plan['blockers'])

    def test_secret_reference_is_actionable_and_value_is_not_exposed(self):
        plan=self.plan(runtime_configuration=self.runtime_configuration(secret=True))
        self.assertFalse(plan['execution_allowed'])
        self.assertIn('secret-resolver-unavailable',plan['blockers'])
        self.assertIn('DATABASE_URL',plan['summary']['runtimeEnvironment']['secretNames']['api'])
        rendered=str(plan)
        self.assertNotIn('vault://project/demo/database',rendered)
        self.assertFalse(plan['secret_references_included'])

    def test_secret_reference_is_allowed_when_internal_resolver_is_available(self):
        with patch.object(self.module,'SECRET_RESOLVER_TOKEN','resolver-token'):
            plan=self.plan(runtime_configuration=self.runtime_configuration(secret=True))
        self.assertTrue(plan['execution_allowed'],plan['blockers'])
        self.assertNotIn('secret-resolver-unavailable',plan['blockers'])
        self.assertTrue(plan['summary']['secretResolutionRequired'])
        self.assertTrue(plan['summary']['secretResolverAvailable'])
        self.assertIn('DATABASE_URL',plan['summary']['runtimeEnvironment']['secretNames']['api'])
        self.assertNotIn('vault://project/demo/database',str(plan))

    def test_production_requires_enabled_target(self):
        plan=self.plan(environment='production')
        self.assertFalse(plan['execution_allowed'])
        self.assertIn('production-target-not-enabled',plan['blockers'])


if __name__=='__main__':unittest.main()
